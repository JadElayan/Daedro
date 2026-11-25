"""Robot recordings in MCAP (the open format Foxglove and ROS 2 use), and incident detection.

Real teams already record their robots. A case should start from those recordings, so Daedro
reads MCAP with JSON-encoded channels:

    /robot/joints      {"t", "position": {joint: rad}}
    /gripper/state     {"t", "opening"}            (metres for parallel jaws, rad for rotating jaws)
    /object/pose       {"t", "position": [x,y,z], "orientation": [w,x,y,z]}
    /task/events       {"t", "event", "detail"}    (phase changes, final outcome)
    /camera/front      foxglove.CompressedImage    ({"timestamp", "frame_id", "format", "data" base64})
plus an MCAP metadata record "daedro" with the cell, robot, gripper, software version and part.

We have no customer recordings yet, so `record_episode` writes the same format from our own
simulation. Every file written this way is marked source="simulation (example)" in its
metadata and stays labelled as such everywhere downstream.
"""
from __future__ import annotations

import base64
import io
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SAMPLE_HZ = 20
CAMERA_HZ = 5

_SCHEMAS = {
    "/robot/joints": {"type": "object", "properties": {"t": {"type": "number"}, "position": {"type": "object"}}},
    "/gripper/state": {"type": "object", "properties": {"t": {"type": "number"}, "opening": {"type": "number"}}},
    "/object/pose": {"type": "object", "properties": {"t": {"type": "number"}, "position": {"type": "array"},
                                                      "orientation": {"type": "array"}}},
    "/task/events": {"type": "object", "properties": {"t": {"type": "number"}, "event": {"type": "string"},
                                                      "detail": {"type": "string"}}},
    "/camera/front": {"type": "object", "title": "foxglove.CompressedImage",
                      "properties": {"timestamp": {"type": "object"}, "frame_id": {"type": "string"},
                                     "format": {"type": "string"}, "data": {"type": "string", "contentEncoding": "base64"}}},
}
_SCHEMA_NAMES = {"/camera/front": "foxglove.CompressedImage"}


class RecordingHook:
    """Pass as `recorder=` to any episode runner; samples robot, gripper, object and camera."""

    def __init__(self, camera: bool = True, width: int = 480, height: int = 320):
        self.samples: list[tuple[str, float, dict]] = []
        self.camera = camera
        self.w, self.h = width, height
        self._r = None
        self._k = 0
        self._every = self._cam_every = None
        self._names = None

    def _setup(self, m):
        import mujoco
        self._every = max(1, int(round(1.0 / (SAMPLE_HZ * m.opt.timestep))))
        self._cam_every = max(1, int(round(1.0 / (CAMERA_HZ * m.opt.timestep))))
        keep = (int(mujoco.mjtJoint.mjJNT_HINGE), int(mujoco.mjtJoint.mjJNT_SLIDE))
        self._names = [m.joint(i).name for i in range(m.njnt) if int(m.jnt_type[i]) in keep]
        self._obj = m.joint("object_free").qposadr[0]
        if "finger_joint1" in self._names:
            a, b = m.joint("finger_joint1").qposadr[0], m.joint("finger_joint2").qposadr[0]
            self._grip = lambda d: float(d.qpos[a] + d.qpos[b])
        else:
            g = m.joint("gripper").qposadr[0]
            self._grip = lambda d: float(d.qpos[g])
        if self.camera:
            from .video import Recorder
            self._cam = Recorder(self.w, self.h)
            self._r = mujoco.Renderer(m, self.h, self.w)

    def step(self, m, d) -> None:
        if self._every is None:
            self._setup(m)
        t = float(d.time)
        if self._k % self._every == 0:
            self.samples.append(("/robot/joints", t, {"t": t, "position": {
                n: round(float(d.qpos[m.joint(n).qposadr[0]]), 5) for n in self._names}}))
            self.samples.append(("/gripper/state", t, {"t": t, "opening": round(self._grip(d), 5)}))
            o = self._obj
            self.samples.append(("/object/pose", t, {"t": t, "position": [round(float(x), 5) for x in d.qpos[o:o + 3]],
                                                     "orientation": [round(float(x), 5) for x in d.qpos[o + 3:o + 7]]}))
        if self._r is not None and self._k % self._cam_every == 0:
            from PIL import Image
            self._r.update_scene(d, camera=self._cam.cam)
            buf = io.BytesIO()
            Image.fromarray(self._r.render()).save(buf, format="JPEG", quality=80)
            sec = int(t)
            self.samples.append(("/camera/front", t, {"timestamp": {"sec": sec, "nsec": int((t - sec) * 1e9)},
                                                      "frame_id": "front", "format": "jpeg",
                                                      "data": base64.b64encode(buf.getvalue()).decode()}))
        self._k += 1

    def close(self):
        if self._r is not None:
            self._r.close()
            self._r = None


def write_mcap(path: str | Path, samples: list, metadata: dict, events: list[tuple[float, str, str]]) -> Path:
    from mcap.writer import Writer
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        w = Writer(f)
        w.start(profile="", library="daedro")
        ch = {}
        for topic, schema in _SCHEMAS.items():
            sid = w.register_schema(name=_SCHEMA_NAMES.get(topic, topic.strip("/").replace("/", ".")),
                                    encoding="jsonschema", data=json.dumps(schema).encode())
            ch[topic] = w.register_channel(topic=topic, message_encoding="json", schema_id=sid)
        rows = list(samples) + [("/task/events", t, {"t": t, "event": e, "detail": dt}) for t, e, dt in events]
        rows.sort(key=lambda r: r[1])
        for topic, t, msg in rows:
            ns = int(t * 1e9)
            w.add_message(channel_id=ch[topic], log_time=ns, publish_time=ns, data=json.dumps(msg).encode())
        w.add_metadata("daedro", {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in metadata.items()})
        w.finish()
    return path


def record_episode(params, seed: int, ctrl, out: str | Path, *, cell: str, software_version: str,
                   gripper: str, part: str, camera: bool = True) -> tuple[Path, dict]:
    """Run one simulated episode and save it as an MCAP recording (an example stand-in for real data)."""
    from .compare import run_any
    hook = RecordingHook(camera=camera)
    from .so101 import So101Config
    if isinstance(ctrl, So101Config):
        hook_cam = (0.55, 180.0, -32.0, [0.18, 0.0, 0.05])
    else:
        hook_cam = None
    if hook_cam and camera:
        from .video import Recorder
        hook._cam = Recorder(hook.w, hook.h)
    result = run_any(params, seed, ctrl, recorder=hook)
    hook.close()
    events = [(0.0, "task_start", "pick and place"), (hook.samples[-1][1], "task_end", result["outcome"])]
    meta = {
        "source": "simulation (example)", "cell": cell, "software_version": software_version, "gripper": gripper,
        "part": part, "part_mass_kg": round(params.mass, 4), "part_size_m": round(2 * params.half_size, 4),
        "part_friction_estimate": round(params.friction, 3), "joint_noise_rad": round(params.ik_noise, 5),
        "half_size_m": round(params.half_size, 5), "seed": str(seed),
        "robot": "so101" if isinstance(ctrl, So101Config) else "franka_panda",
        "controller": json.dumps(ctrl.to_dict()), "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return write_mcap(out, hook.samples, meta, events), result


@dataclass
class Recording:
    path: Path
    metadata: dict
    t: np.ndarray
    object_pos: np.ndarray
    gripper: np.ndarray
    joints: list = field(default_factory=list)
    events: list = field(default_factory=list)
    frames: list = field(default_factory=list)  # (t, jpeg bytes)


def read_mcap(path: str | Path) -> Recording:
    from mcap.reader import make_reader
    path = Path(path)
    meta, ts, pos, grip_t, grip, joints, events, frames = {}, [], [], [], [], [], [], []
    with open(path, "rb") as f:
        r = make_reader(f)
        for md in r.iter_metadata():
            if md.name == "daedro":
                meta.update(md.metadata)
        for schema, channel, message in r.iter_messages():
            if channel.message_encoding != "json":
                continue
            msg = json.loads(message.data)
            t = message.log_time / 1e9
            if channel.topic == "/object/pose":
                ts.append(t); pos.append(msg["position"])
            elif channel.topic == "/gripper/state":
                grip_t.append(t); grip.append(msg["opening"])
            elif channel.topic == "/robot/joints":
                joints.append((t, msg["position"]))
            elif channel.topic == "/task/events":
                events.append((t, msg["event"], msg.get("detail", "")))
            elif channel.topic == "/camera/front" and msg.get("format") in ("jpeg", "jpg", "png"):
                frames.append((t, base64.b64decode(msg["data"])))
    if not ts:
        raise ValueError(f"{path}: no /object/pose messages; Daedro needs the part's pose to find the incident")
    g = np.interp(np.array(ts), np.array(grip_t), np.array(grip)) if grip else np.zeros(len(ts))
    return Recording(path, meta, np.array(ts), np.array(pos), g, joints, events, frames)


@dataclass
class Incident:
    t: float
    kind: str  # "never_lifted" | "dropped" | "misplaced" | "none"
    description: str


def find_incident(rec: Recording, target_xy=None, lift_threshold: float = 0.05) -> Incident:
    """Find the moment that matters: the drop, the failed lift, or the bad placement."""
    half = float(rec.metadata.get("half_size_m", 0.0))
    z = rec.object_pos[:, 2] - half
    xy = rec.object_pos[:, :2]
    if target_xy is None:
        from .scene import TARGET_XY
        from .so101 import TARGET_XY as SO_TARGET
        target_xy = SO_TARGET if rec.metadata.get("robot") == "so101" else TARGET_XY
    tgt = np.array(target_xy)
    lifted = np.where(z > lift_threshold)[0]
    if len(lifted) == 0:
        # never lifted: the moment the arm should have been carrying it (largest gripper closing, then nothing)
        i = int(np.argmin(rec.gripper)) if len(rec.gripper) else 0
        return Incident(float(rec.t[i]), "never_lifted",
                        "The gripper closed but the part never left the table (slipped or missed).")
    first = lifted[0]
    peak = first + int(np.argmax(z[first:]))
    after = np.where((np.arange(len(z)) > peak) & (z < 0.01))[0]
    if len(after):
        j = int(after[0])
        if np.linalg.norm(xy[j] - tgt) > 0.05:
            k = peak + int(np.argmax(np.diff(z[peak:j + 1]) < -0.002)) if j > peak else j
            return Incident(float(rec.t[k]), "dropped",
                            f"The part was lifted to {z[peak] * 100:.0f} cm, then fell "
                            f"{np.linalg.norm(xy[j] - tgt) * 100:.0f} cm from the target.")
    final = float(np.linalg.norm(xy[-1] - tgt))
    if final > 0.03:
        return Incident(float(rec.t[-1]), "misplaced", f"The part ended {final * 100:.1f} cm from the target.")
    return Incident(float(rec.t[-1]), "none", "No incident: the part was placed on target.")


def clip_video(rec: Recording, t0: float, t1: float, out: str | Path) -> Path | None:
    import shutil
    import subprocess
    sel = [b for t, b in rec.frames if t0 <= t <= t1]
    if not sel or not shutil.which("ffmpeg"):
        return None
    out = Path(out)
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(CAMERA_HZ),
                          "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "fps=15", "-movflags", "+faststart",
                          str(out)], stdin=subprocess.PIPE)
    for b in sel:
        p.stdin.write(b)
    p.stdin.close()
    return out if p.wait() == 0 else None
