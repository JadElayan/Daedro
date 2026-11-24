"""One scripted pick-and-place episode and its outcome classification.

Controller: a six-phase state machine (approach, descend, grasp, lift, move, place/release),
the same shape as RoboGate's scripted baseline. Each phase interpolates a Cartesian TCP
target; a damped-least-squares IK step turns it into joint position targets for
Menagerie's joint servos. The gripper keeps a fixed downward orientation.

Everything stochastic comes from one numpy Generator seeded per episode, and MuJoCo itself
is deterministic on a given machine and build, so (params, seed) -> identical result.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import mujoco
import numpy as np

from .scene import HOME_QPOS, OBJECT_XY, TARGET_XY, SceneParams, build_model

CTRL_EVERY = 5  # physics at 500 Hz (Menagerie timestep 2 ms), control at 100 Hz
GRIP_OPEN, GRIP_CLOSED = 255.0, 0.0
SUCCESS_RADIUS = 0.03  # same 3 cm criterion RoboGate uses
HOVER = 0.15  # approach height above grasp point, m
CARRY = 0.20  # lift height, m

OUTCOMES = ("success", "grasp_miss", "slip_on_lift", "drop_in_transit", "misplaced")


@dataclass(frozen=True)
class ControllerConfig:
    """The behaviour a team versions and compares. Defaults reproduce the baseline
    controller used for docs/mujoco_loop.md, so earlier results stay valid."""

    speed: float = 1.0  # >1 runs every phase faster (durations divided by this)
    hover_m: float = HOVER
    carry_m: float = CARRY
    grasp_offset_m: float = 0.0  # TCP height relative to the cube's centre at grasp
    grip_force_n: float | None = 70.0  # None = stock Menagerie gripper
    ik_damping: float = 1e-2

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EpisodeResult:
    seed: int
    friction: float
    mass: float
    half_size: float
    ik_noise: float
    grip_force_n: float | None
    finger_contact: str
    outcome: str
    success: bool
    place_error_m: float  # final object-to-target distance in the xy plane
    max_lift_m: float  # highest object-bottom height reached
    grasp_gap_m: float  # finger opening after the grasp phase
    squeeze_n: float  # mean gripper tendon force while holding
    finger_normal_n: float  # mean normal force, left finger on object, while holding (measured)

    def to_dict(self) -> dict:
        return asdict(self)


def _ik_step(m, d, site_id, x_goal, R_goal, dof, damping=1e-2):
    """One damped-least-squares step toward a TCP pose; returns joint targets for the arm."""
    jacp = np.zeros((3, m.nv)); jacr = np.zeros((3, m.nv))
    mujoco.mj_jacSite(m, d, jacp, jacr, site_id)
    J = np.vstack([jacp[:, dof], jacr[:, dof]])
    e_pos = x_goal - d.site_xpos[site_id]
    R = d.site_xmat[site_id].reshape(3, 3)
    e_rot = 0.5 * (np.cross(R[:, 0], R_goal[:, 0]) + np.cross(R[:, 1], R_goal[:, 1]) + np.cross(R[:, 2], R_goal[:, 2]))
    err = np.concatenate([e_pos, e_rot])
    dq = J.T @ np.linalg.solve(J @ J.T + damping * np.eye(6), err)
    return d.qpos[dof] + dq


def run_episode(p: SceneParams, seed: int, grip_force_n: float | None = 70.0, finger_contact: str = "flat_pad",
                controller: ControllerConfig | None = None, recorder=None) -> EpisodeResult:
    """Run one episode. If `controller` is given, its grip_force_n wins over the argument."""
    c = controller or ControllerConfig(grip_force_n=grip_force_n)
    grip_force_n = c.grip_force_n
    rng = np.random.default_rng(seed)
    m = build_model(p, grip_force_n, finger_contact)
    d = mujoco.MjData(m)

    arm_q = np.array([m.joint(f"joint{i}").qposadr[0] for i in range(1, 8)])
    arm_v = np.array([m.joint(f"joint{i}").dofadr[0] for i in range(1, 8)])
    obj_adr = m.joint("object_free").qposadr[0]
    tcp = m.site("tcp").id
    f1, f2 = m.joint("finger_joint1").qposadr[0], m.joint("finger_joint2").qposadr[0]
    grip_act = m.actuator("actuator8").id
    obj_geom = m.geom("object").id
    left_body = m.body("left_finger").id
    f6 = np.zeros(6)

    def left_normal() -> float:
        total = 0.0
        for i in range(d.ncon):
            c = d.contact[i]
            pair = {c.geom1, c.geom2}
            if obj_geom in pair and m.geom_bodyid[(pair - {obj_geom}).pop()] == left_body:
                mujoco.mj_contactForce(m, d, i, f6)
                total += f6[0]
        return total

    d.qpos[arm_q] = HOME_QPOS
    d.qpos[[f1, f2]] = 0.04
    d.ctrl[:7] = HOME_QPOS
    d.ctrl[grip_act] = GRIP_OPEN
    mujoco.mj_forward(m, d)
    R_down = d.site_xmat[tcp].reshape(3, 3).copy()

    # Grasp at the cube's centre height (no tilting lever arm); the pad is 17 mm tall, so
    # keep the TCP >= 9.5 mm up or the pad's lower edge would hit the floor on small cubes.
    gz = max(p.half_size + c.grasp_offset_m, 0.0095)
    pick = np.array([OBJECT_XY[0], OBJECT_XY[1], gz])
    place = np.array([TARGET_XY[0], TARGET_XY[1], gz + 0.005])
    up = np.array([0, 0, 1.0])

    # (name, duration s, tcp start, tcp end, gripper command)
    start = d.site_xpos[tcp].copy()
    H, C, v = c.hover_m, c.carry_m, c.speed
    phases = [
        ("approach", 1.5 / v, start, pick + H * up, GRIP_OPEN),
        ("descend", 1.0 / v, pick + H * up, pick, GRIP_OPEN),
        ("grasp", 0.8, pick, pick, GRIP_CLOSED),  # gripper closing time is hardware, not speed
        ("lift", 1.0 / v, pick, pick + C * up, GRIP_CLOSED),
        ("move", 1.5 / v, pick + C * up, place + C * up, GRIP_CLOSED),
        ("place", 1.0 / v, place + C * up, place, GRIP_CLOSED),
        ("release", 0.5, place, place, GRIP_OPEN),
        ("retreat", 0.5 / v, place, place + H * up, GRIP_OPEN),
    ]

    obj_bottom = lambda: d.qpos[obj_adr + 2] - p.half_size
    marks: dict[str, float] = {}
    max_lift, squeeze, normal = 0.0, [], []
    steps_per_s = int(round(1.0 / m.opt.timestep))
    for name, dur, a, b, grip in phases:
        n = int(dur * steps_per_s)
        for k in range(n):
            if k % CTRL_EVERY == 0:
                s = min(1.0, (k + CTRL_EVERY) / (0.8 * n))  # reach the waypoint at 80 %, then settle
                s = 3 * s**2 - 2 * s**3  # smoothstep
                q_t = _ik_step(m, d, tcp, a + s * (b - a), R_down, arm_v, c.ik_damping)
                d.ctrl[:7] = q_t + rng.normal(0.0, p.ik_noise, 7)
                d.ctrl[grip_act] = grip
            mujoco.mj_step(m, d)
            if recorder is not None:
                recorder.step(m, d)
            if name in ("lift", "move", "place"):
                max_lift = max(max_lift, obj_bottom())
                squeeze.append(abs(d.actuator_force[grip_act]))
                if k % CTRL_EVERY == 0:
                    normal.append(left_normal())
        if name == "grasp":
            marks["gap"] = d.qpos[f1] + d.qpos[f2]
        elif name == "lift":
            marks["lift"] = obj_bottom()
        elif name == "move":
            marks["move_z"] = obj_bottom()
            marks["move_xy_err"] = float(np.linalg.norm(d.qpos[obj_adr:obj_adr + 2] - np.array(TARGET_XY)))

    # Let the object come to rest before scoring.
    for _ in range(steps_per_s // 2):
        mujoco.mj_step(m, d)
        if recorder is not None:
            recorder.step(m, d)
    err = float(np.linalg.norm(d.qpos[obj_adr:obj_adr + 2] - np.array(TARGET_XY)))
    resting = obj_bottom() < 0.01 and np.linalg.norm(d.qvel[m.joint("object_free").dofadr[0]:][:3]) < 0.05

    width = 2 * p.half_size
    if marks["gap"] < 0.6 * width:  # fingers closed past the object: nothing between them
        outcome = "grasp_miss"
    elif marks["lift"] < 0.5 * c.carry_m:
        outcome = "slip_on_lift"
    elif marks["move_z"] < 0.5 * c.carry_m or marks["move_xy_err"] > 0.05:
        outcome = "drop_in_transit"
    elif err <= SUCCESS_RADIUS and resting:
        outcome = "success"
    else:
        outcome = "misplaced"

    return EpisodeResult(
        seed=seed, friction=p.friction, mass=p.mass, half_size=p.half_size, ik_noise=p.ik_noise,
        grip_force_n=grip_force_n, finger_contact=finger_contact, outcome=outcome, success=outcome == "success",
        place_error_m=err, max_lift_m=float(max_lift), grasp_gap_m=float(marks["gap"]),
        squeeze_n=float(np.mean(squeeze)) if squeeze else 0.0,
        finger_normal_n=float(np.mean(normal)) if normal else 0.0,
    )
