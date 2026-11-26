import math

import pytest

from daedro.recording import find_incident, read_mcap

TF = ("geometry_msgs/TransformStamped[] transforms" + "\n" + "=" * 80 + "\n"
      "MSG: geometry_msgs/TransformStamped\nstd_msgs/Header header\nstring child_frame_id\ngeometry_msgs/Transform transform\n"
      + "=" * 80 + "\nMSG: std_msgs/Header\nbuiltin_interfaces/Time stamp\nstring frame_id\n"
      + "=" * 80 + "\nMSG: builtin_interfaces/Time\nint32 sec\nuint32 nanosec\n"
      + "=" * 80 + "\nMSG: geometry_msgs/Transform\ngeometry_msgs/Vector3 translation\ngeometry_msgs/Quaternion rotation\n"
      + "=" * 80 + "\nMSG: geometry_msgs/Vector3\nfloat64 x\nfloat64 y\nfloat64 z\n"
      + "=" * 80 + "\nMSG: geometry_msgs/Quaternion\nfloat64 x 0\nfloat64 y 0\nfloat64 z 0\nfloat64 w 1")


def _team_bag(path):
    """A bag shaped like a real team's: custom topic names, part pose only on /tf, no Daedro metadata."""
    from mcap_ros2.writer import Writer
    from daedro.ros2 import MSGDEFS
    with open(path, "wb") as f:
        w = Writer(f)
        js = w.register_msgdef("sensor_msgs/msg/JointState", MSGDEFS["sensor_msgs/msg/JointState"])
        tf = w.register_msgdef("tf2_msgs/msg/TFMessage", TF)
        for i in range(60):  # 3 s at 20 Hz: lift to 15 cm, then fall far from the target
            t = i * 0.05
            z = 0.02 + (0.15 * min(t, 1.5) / 1.5 if t < 1.6 else 0.0)
            hdr = {"stamp": {"sec": int(t), "nanosec": int((t % 1) * 1e9)}, "frame_id": "world"}
            ns = int(t * 1e9)
            w.write_message("/arm/joint_states", js, {"header": hdr, "name": ["j1", "left_finger", "right_finger"],
                            "position": [0.1, 0.02, 0.02], "velocity": [], "effort": []}, ns, ns)
            w.write_message("/tf", tf, {"transforms": [{"header": hdr, "child_frame_id": "bracket",
                            "transform": {"translation": {"x": 0.5, "y": -0.15 + 0.1 * t, "z": z},
                                          "rotation": {"x": 0, "y": 0, "z": 0, "w": 1}}}]}, ns, ns)
        w.finish()


def test_team_shaped_bag_reads_with_a_topic_map(tmp_path):
    bag = tmp_path / "team.mcap"
    _team_bag(bag)
    m = tmp_path / "topics.toml"
    m.write_text('[topics]\njoints = "/arm/joint_states"\nobject_tf_frame = "bracket"\n'
                 'gripper_joints = ["left_finger", "right_finger"]\n'
                 '[metadata]\ncell = "cell 7"\nsoftware_version = "v3"\nhalf_size_m = 0.02\n'
                 'part_mass_kg = 0.5\npart_friction_estimate = 0.4\nrobot = "franka_panda"\n')
    rec = read_mcap(bag, m)
    assert rec.metadata["cell"] == "cell 7" and len(rec.t) == 60
    assert rec.gripper[0] == pytest.approx(0.04)
    inc = find_incident(rec)
    assert inc.kind == "dropped" and 1.5 < inc.t < 1.8


def test_bag_without_mapping_explains_what_is_missing(tmp_path):
    bag = tmp_path / "team.mcap"
    _team_bag(bag)
    with pytest.raises(ValueError, match="object_tf_frame"):
        read_mcap(bag)


def test_ros2_example_bag_matches_json_recording():
    from pathlib import Path
    ex = Path(__file__).resolve().parents[1] / "examples" / "cases" / "recordings"
    a = find_incident(read_mcap(ex / "cell-b2_2026-11-20_shift2_pick-0417.mcap"))
    b = find_incident(read_mcap(ex / "cell-b2_ros2_example.mcap"))
    assert (a.kind, round(a.t, 2)) == (b.kind, round(b.t, 2))
