"""ROS 2 recordings: read the bags robotics teams already record.

ROS 2 records to MCAP with CDR-encoded messages. Daedro decodes them with mcap-ros2-support
(no ROS installation needed) and maps standard message types onto a Recording:

    sensor_msgs/msg/JointState       -> joint positions; gripper opening from chosen joint(s)
    geometry_msgs/msg/PoseStamped    -> the part's pose
    tf2_msgs/msg/TFMessage           -> the part's pose, from one child frame (alternative)
    sensor_msgs/msg/CompressedImage  -> camera frames (jpeg/png)
    std_msgs/msg/String              -> task events (optional)

Every team names topics differently, so a small TOML map says which is which:

    [topics]
    joints = "/joint_states"
    object_pose = "/part/pose"            # or: object_tf_frame = "part"
    camera = "/camera/front/image_raw/compressed"
    events = "/pick/events"
    gripper_joints = ["finger_joint1", "finger_joint2"]   # summed

    [metadata]                            # what the bag itself doesn't say
    cell = "Cell 2"
    software_version = "v2.5"
    part = "bracket"
    part_mass_kg = 0.93
    half_size_m = 0.028
    part_friction_estimate = 0.3          # measured or estimated; needed to simulate
    robot = "franka_panda"

The writer below produces genuine ROS 2 bags from our simulation; it's used for the example
and tests, and its output is marked source="simulation (example)".
"""
from __future__ import annotations

import base64
import tomllib
from pathlib import Path

import numpy as np

from .recording import Recording

DEFAULT_TOPICS = {"joints": "/joint_states", "object_pose": "/object/pose", "object_tf_frame": None,
                  "camera": "/camera/front/image_raw/compressed", "events": "/task/events", "gripper_joints": None}

# ROS 2 message definitions, in the concatenated form rosbag2 stores in MCAP schemas.
_SEP = "\n" + "=" * 80 + "\n"
_TIME = "MSG: builtin_interfaces/Time\nint32 sec\nuint32 nanosec"
_HEADER = "MSG: std_msgs/Header\nbuiltin_interfaces/Time stamp\nstring frame_id"
MSGDEFS = {
    "sensor_msgs/msg/JointState": "std_msgs/Header header\nstring[] name\nfloat64[] position\nfloat64[] velocity\nfloat64[] effort"
                                  + _SEP + _HEADER + _SEP + _TIME,
    "geometry_msgs/msg/PoseStamped": "std_msgs/Header header\ngeometry_msgs/Pose pose" + _SEP + _HEADER + _SEP + _TIME
                                     + _SEP + "MSG: geometry_msgs/Pose\ngeometry_msgs/Point position\ngeometry_msgs/Quaternion orientation"
                                     + _SEP + "MSG: geometry_msgs/Point\nfloat64 x\nfloat64 y\nfloat64 z"
                                     + _SEP + "MSG: geometry_msgs/Quaternion\nfloat64 x 0\nfloat64 y 0\nfloat64 z 0\nfloat64 w 1",
    "sensor_msgs/msg/CompressedImage": "std_msgs/Header header\nstring format\nuint8[] data" + _SEP + _HEADER + _SEP + _TIME,
    "std_msgs/msg/String": "string data",
}


def load_topic_map(path: str | Path | None) -> tuple[dict, dict]:
    topics, meta = dict(DEFAULT_TOPICS), {}
    if path:
        raw = tomllib.loads(Path(path).read_text())
        unknown = set(raw.get("topics", {})) - set(DEFAULT_TOPICS)
        if unknown:
            raise ValueError(f"{path}: unknown [topics] keys {sorted(unknown)}; allowed: {sorted(DEFAULT_TOPICS)}")
        topics.update(raw.get("topics", {}))
        meta = {k: str(v) for k, v in raw.get("metadata", {}).items()}
    return topics, meta


def is_ros2(path: str | Path) -> bool:
    from mcap.reader import make_reader
    with open(path, "rb") as f:
        s = make_reader(f).get_summary()
    return bool(s and any(c.message_encoding == "cdr" for c in s.channels.values()))


def read_ros2(path: str | Path, topic_map: str | Path | None = None) -> Recording:
    from mcap.reader import make_reader
    from mcap_ros2.decoder import DecoderFactory
    topics, meta_override = load_topic_map(topic_map)
    path = Path(path)
    meta, ts, pos, quat, jt, jpos, frames, events = {}, [], [], [], [], [], [], []
    with open(path, "rb") as f:
        r = make_reader(f, decoder_factories=[DecoderFactory()])
        for md in r.iter_metadata():
            if md.name == "daedro":
                meta.update(md.metadata)
        for schema, channel, message, ros in r.iter_decoded_messages():
            t = message.log_time / 1e9
            topic, kind = channel.topic, schema.name if schema else ""
            if topic == topics["joints"] and kind.endswith("JointState"):
                jt.append(t)
                jpos.append(dict(zip(ros.name, ros.position)))
            elif topic == topics["object_pose"] and kind.endswith("PoseStamped"):
                p, q = ros.pose.position, ros.pose.orientation
                ts.append(t); pos.append([p.x, p.y, p.z]); quat.append([q.w, q.x, q.y, q.z])
            elif topics["object_tf_frame"] and kind.endswith("TFMessage"):
                for tr in ros.transforms:
                    if tr.child_frame_id == topics["object_tf_frame"]:
                        p, q = tr.transform.translation, tr.transform.rotation
                        ts.append(t); pos.append([p.x, p.y, p.z]); quat.append([q.w, q.x, q.y, q.z])
            elif topic == topics["camera"] and kind.endswith("CompressedImage"):
                if any(x in ros.format.lower() for x in ("jpeg", "jpg", "png")):
                    frames.append((t, bytes(ros.data)))
            elif topic == topics["events"] and kind.endswith("String"):
                ev, _, detail = ros.data.partition(":")
                events.append((t, ev.strip(), detail.strip()))
    meta.update(meta_override)
    if not ts:
        raise ValueError(f"{path}: found no part pose on {topics['object_pose']!r}"
                         + (f" or tf frame {topics['object_tf_frame']!r}" if topics["object_tf_frame"] else "")
                         + ". Set [topics] object_pose / object_tf_frame in a topic map (--topics).")
    grip_names = topics["gripper_joints"]
    if not grip_names and jpos:
        grip_names = [n for n in jpos[0] if "finger" in n or n == "gripper"]
    g = np.array([sum(j.get(n, 0.0) for n in grip_names) for j in jpos]) if jpos and grip_names else np.zeros(len(jt))
    grip = np.interp(np.array(ts), np.array(jt), g) if len(jt) else np.zeros(len(ts))
    joints = [(t, j) for t, j in zip(jt, jpos)]
    return Recording(path, meta, np.array(ts), np.array(pos), grip, joints, events, frames)


def write_ros2(path: str | Path, samples: list, metadata: dict, events: list) -> Path:
    """Write RecordingHook samples as a genuine ROS 2 (CDR) bag. For examples and tests."""
    from mcap_ros2.writer import Writer
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        w = Writer(f)
        sch = {k: w.register_msgdef(k, v) for k, v in MSGDEFS.items()}

        def hdr(t, frame):
            s = int(t)
            return {"stamp": {"sec": s, "nanosec": int((t - s) * 1e9)}, "frame_id": frame}

        rows = sorted(samples, key=lambda r: r[1])
        for topic, t, msg in rows:
            ns = int(t * 1e9)
            if topic == "/robot/joints":
                names = list(msg["position"])
                w.write_message("/joint_states", sch["sensor_msgs/msg/JointState"],
                                {"header": hdr(t, "base"), "name": names,
                                 "position": [float(msg["position"][n]) for n in names], "velocity": [], "effort": []}, ns, ns)
            elif topic == "/object/pose":
                p, q = msg["position"], msg["orientation"]
                w.write_message("/object/pose", sch["geometry_msgs/msg/PoseStamped"],
                                {"header": hdr(t, "world"), "pose": {"position": {"x": p[0], "y": p[1], "z": p[2]},
                                                                     "orientation": {"w": q[0], "x": q[1], "y": q[2], "z": q[3]}}}, ns, ns)
            elif topic == "/camera/front":
                w.write_message("/camera/front/image_raw/compressed", sch["sensor_msgs/msg/CompressedImage"],
                                {"header": hdr(t, "front"), "format": "jpeg", "data": base64.b64decode(msg["data"])}, ns, ns)
        for t, ev, detail in events:
            ns = int(t * 1e9)
            w.write_message("/task/events", sch["std_msgs/msg/String"], {"data": f"{ev}: {detail}"}, ns, ns)
        w.add_metadata("daedro", {k: (v if isinstance(v, str) else str(v)) for k, v in metadata.items()})
        w.finish()
    return path
