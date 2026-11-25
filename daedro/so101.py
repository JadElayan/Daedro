"""SO-101 (RobotStudio / Hugging Face LeRobot arm) scripted pick-and-place.

Uses MuJoCo Menagerie's robotstudio_so101 model unmodified, apart from what the task adds:
floor, cube, target and object contact settings. The arm has 5 joints plus a rotating jaw,
and hobby servos (STS3215, torque limit 2.94 N·m as shipped), so the workspace and payloads
are small: parts of 10–200 g within ~30 cm of the base.

Design note: Menagerie gives the SO-101's gripper geoms contact *priority*, so their
friction (μ=1) would override the object's and make a friction sweep meaningless. We give
the object a higher priority so the object's own friction governs the grasp, the same trap
we hit (and checked against Coulomb) on the Franka.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

import mujoco
import numpy as np

from .scene import DEFAULT_MENAGERIE, SceneParams

OBJECT_XY = (0.18, -0.07)
TARGET_XY = (0.18, 0.07)
SUCCESS_RADIUS = 0.02  # 2 cm: scaled to the small arm
JAW_OPEN, JAW_CLOSED = 1.2, -0.17
JAW_RELEASE = 0.6  # open only part-way at release: a fully swinging jaw flicks the part away
CTRL_EVERY = 2  # physics 200 Hz (Menagerie timestep 5 ms), control 100 Hz
ARM = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll")

# Supported ranges for the SO-101 (narrower than the Franka's: a hobby arm, small parts).
SO101_SPACE = {  # preview: outcomes are physically consistent in this range (see docs/so101_preview.md)
    "friction": (0.1, 1.2, "log"),
    "mass": (0.01, 0.2, "log"),
    "half_size": (0.009, 0.013, "linear"),
    "ik_noise": (0.0, 0.0001, "linear"),  # grasp is tip-contact and fragile: joint noise >= 0.0003 rad breaks it
}


@dataclass(frozen=True)
class So101Config:
    robot: str = "so101"
    speed: float = 1.0
    hover_m: float = 0.06
    carry_m: float = 0.08
    grasp_offset_m: float = 0.0
    jaw_close: float = JAW_CLOSED  # commanded jaw angle when gripping (rad); higher = gentler squeeze
    servo_torque_nm: float = 2.94  # STS3215 limit as shipped in Menagerie

    def to_dict(self) -> dict:
        return asdict(self)


def model_path() -> Path:
    root = Path(os.environ.get("MENAGERIE_PATH", DEFAULT_MENAGERIE))
    p = root / "robotstudio_so101" / "so101.xml"
    if not p.exists():
        raise FileNotFoundError(f"SO-101 model not found at {p}; set MENAGERIE_PATH to a mujoco_menagerie checkout")
    return p


def build_model(p: SceneParams, c: So101Config) -> mujoco.MjModel:
    spec = mujoco.MjSpec.from_file(str(model_path()))
    wb = spec.worldbody
    wb.add_light(pos=[0, 0, 1.5], dir=[0, 0, -1])
    wb.add_geom(name="floor", type=mujoco.mjtGeom.mjGEOM_PLANE, size=[0, 0, 0.05], rgba=[0.3, 0.35, 0.4, 1],
                friction=[0.5, 0.005, 0.0001])
    obj = wb.add_body(name="object", pos=[OBJECT_XY[0], OBJECT_XY[1], p.half_size])
    obj.add_freejoint(name="object_free")
    obj.add_geom(name="object", type=mujoco.mjtGeom.mjGEOM_BOX, size=[p.half_size] * 3, mass=p.mass,
                 friction=[p.friction, 0.005, 0.0001], condim=4, priority=2,  # see module docstring
                 solref=[0.01, 1.0], solimp=[0.95, 0.99, 0.001, 0.5, 2.0], rgba=[0.9, 0.4, 0.1, 1])
    wb.add_site(name="target", pos=[TARGET_XY[0], TARGET_XY[1], 0.001], size=[0.02, 0.02, 0.001],
                type=mujoco.mjtGeom.mjGEOM_BOX, rgba=[0, 1, 0, 0.4])
    wb.add_camera(name="front", pos=[0.75, 0.0, 0.35], xyaxes=[0, 1, 0, -0.42, 0, 0.91], fovy=45)
    if c.servo_torque_nm != 2.94:
        for a in spec.actuators:
            a.forcerange = [-c.servo_torque_nm, c.servo_torque_nm]
    # Grasp point. Menagerie's "gripperframe" sits on the fixed jaw, so steering it onto the
    # cube's centre lands the fixed jaw on top of the part. Measure the fixed jaw's tips in
    # the gripper body frame, then put the grasp point half a cube (+3 mm) inside them,
    # 8 mm up from the fingertips so the pads close on the cube's sides.
    m0 = spec.compile()
    d0 = mujoco.MjData(m0)
    d0.qpos[m0.joint("gripper").qposadr[0]] = JAW_OPEN
    mujoco.mj_forward(m0, d0)
    g = m0.body("gripper").id
    Rg, og = d0.xmat[g].reshape(3, 3), d0.xpos[g]
    fixed = np.mean([Rg.T @ (d0.geom_xpos[m0.geom(f"fixed_jaw_sph_tip{i}").id] - og) for i in (1, 2, 3)], axis=0)
    moving = np.mean([Rg.T @ (d0.geom_xpos[m0.geom(f"moving_jaw_sph_tip{i}").id] - og) for i in (1, 2, 3)], axis=0)
    close_dir = np.array([np.sign(moving[0] - fixed[0]), 0.0, 0.0])  # jaws open along the body x-axis
    grasp = fixed + close_dir * (p.half_size + 0.003) + np.array([0.0, 0.0, 0.008])
    spec.body("gripper").add_site(name="grasp", pos=grasp.tolist(), size=[0.003], rgba=[0, 0.6, 1, 1])
    return spec.compile()


def _ik_step(m, d, site, x_goal, dof, lo=None, hi=None, w_rot=0.3, damping=1e-3):
    """Position first, plus a soft 'fingers point down' preference.

    The grasp site uses the gripper body frame, where the fingers point along local -z, so
    "down" means the site's z-axis should point to world +z. A 5-joint arm can't always hold
    a strictly vertical approach within its joint limits near the table, so orientation is
    weighted below position and the arm may tilt, as real SO-101 users' grasps do.
    """
    jacp = np.zeros((3, m.nv)); jacr = np.zeros((3, m.nv))
    mujoco.mj_jacSite(m, d, jacp, jacr, site)
    zax = d.site_xmat[site].reshape(3, 3)[:, 2]
    e_rot = np.cross(zax, np.array([0.0, 0.0, 1.0]))
    J = np.vstack([jacp[:, dof], w_rot * jacr[:, dof]])
    err = np.concatenate([x_goal - d.site_xpos[site], w_rot * 0.5 * e_rot])
    dq = J.T @ np.linalg.solve(J @ J.T + damping * np.eye(6), err)
    q = d.qpos[dof] + np.clip(dq, -0.2, 0.2)
    return q if lo is None else np.clip(q, lo, hi)


def _settle_home(m, d, site, dof, x, lo, hi):
    """Solve IK statically for the start pose (fingers down above the workspace)."""
    for _ in range(300):
        d.qpos[dof] = _ik_step(m, d, site, x, dof, lo, hi)
        mujoco.mj_forward(m, d)


def run_episode(p: SceneParams, seed: int, c: So101Config | None = None, recorder=None) -> dict:
    c = c or So101Config()
    rng = np.random.default_rng(seed)
    m = build_model(p, c)
    d = mujoco.MjData(m)
    dof = np.array([m.joint(n).dofadr[0] for n in ARM])
    qadr = np.array([m.joint(n).qposadr[0] for n in ARM])
    jaw = m.actuator("gripper").id
    arm_act = [m.actuator(n).id for n in ARM]
    site = m.site("grasp").id
    lo = np.array([m.jnt_range[m.joint(n).id][0] for n in ARM])
    hi = np.array([m.jnt_range[m.joint(n).id][1] for n in ARM])
    oq, ov = m.joint("object_free").qposadr[0], m.joint("object_free").dofadr[0]

    gz = max(p.half_size + c.grasp_offset_m, 0.006)
    pick = np.array([OBJECT_XY[0], OBJECT_XY[1], gz])
    place = np.array([TARGET_XY[0], TARGET_XY[1], gz + 0.004])
    up = np.array([0, 0, 1.0])
    start = np.array([0.20, 0.0, 0.10])
    d.qpos[m.joint("gripper").qposadr[0]] = JAW_OPEN
    _settle_home(m, d, site, dof, start, lo, hi)
    d.qpos[oq:oq + 3] = [OBJECT_XY[0], OBJECT_XY[1], p.half_size]  # IK warm-up must not move the part
    d.qvel[:] = 0
    d.ctrl[arm_act] = d.qpos[qadr]
    d.ctrl[jaw] = JAW_OPEN
    mujoco.mj_forward(m, d)

    H, C, v = c.hover_m, c.carry_m, c.speed
    phases = [
        ("approach", 1.2 / v, start, pick + H * up, JAW_OPEN),
        ("descend", 1.0 / v, pick + H * up, pick, JAW_OPEN),
        ("grasp", 0.8, pick, pick, c.jaw_close),
        ("lift", 1.0 / v, pick, pick + C * up, c.jaw_close),
        ("move", 1.2 / v, pick + C * up, place + C * up, c.jaw_close),
        ("place", 1.0 / v, place + C * up, place, c.jaw_close),
        ("release", 0.6, place, place, JAW_RELEASE),  # jaw opens on a ramp, see below
        ("retreat", 0.5 / v, place, place + H * up, JAW_RELEASE),
    ]
    bottom = lambda: d.qpos[oq + 2] - p.half_size
    marks, max_lift = {}, 0.0
    sps = int(round(1.0 / m.opt.timestep))
    for name, dur, a, b, g in phases:
        n = max(1, int(dur * sps))
        for k in range(n):
            if k % CTRL_EVERY == 0:
                s = min(1.0, (k + CTRL_EVERY) / (0.8 * n))
                s = 3 * s * s - 2 * s ** 3
                q = _ik_step(m, d, site, a + s * (b - a), dof, lo, hi)
                d.ctrl[arm_act] = q + rng.normal(0.0, p.ik_noise, len(ARM))
                d.ctrl[jaw] = c.jaw_close + s * (g - c.jaw_close) if name == "release" else g
            mujoco.mj_step(m, d)
            if recorder is not None:
                recorder.step(m, d)
            if name in ("lift", "move", "place"):
                max_lift = max(max_lift, bottom())
        if name == "lift":
            marks["lift"] = bottom()
        elif name == "move":
            marks["move_z"] = bottom()
            marks["move_xy"] = float(np.linalg.norm(d.qpos[oq:oq + 2] - np.array(TARGET_XY)))
    for _ in range(sps // 2):
        mujoco.mj_step(m, d)
        if recorder is not None:
            recorder.step(m, d)
    err = float(np.linalg.norm(d.qpos[oq:oq + 2] - np.array(TARGET_XY)))
    resting = bottom() < 0.008 and np.linalg.norm(d.qvel[ov:ov + 3]) < 0.05
    if marks["lift"] < 0.5 * C:
        outcome = "slip_on_lift"
    elif marks["move_z"] < 0.5 * C or marks["move_xy"] > 0.04:
        outcome = "drop_in_transit"
    elif err <= SUCCESS_RADIUS and resting:
        outcome = "success"
    else:
        outcome = "misplaced"
    return {"seed": seed, "friction": p.friction, "mass": p.mass, "half_size": p.half_size, "ik_noise": p.ik_noise,
            "robot": "so101", "outcome": outcome, "success": outcome == "success", "place_error_m": err,
            "max_lift_m": float(max_lift)}
