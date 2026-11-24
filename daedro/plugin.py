"""Bring your own controller.

A team points daedro.toml at a Python file in their repo:

    [controller]
    module = "controllers/my_pick.py"   # relative to daedro.toml
    class  = "MyPickController"
    [controller.params]                 # optional, passed to __init__(**params)
    grip = 0.0

The class implements two methods:

    class MyPickController:
        def reset(self, obs: dict) -> None: ...
        def act(self, obs: dict) -> dict: ...

`act` is called at 100 Hz and returns either
    {"tcp": [x, y, z], "gripper": g}   # Cartesian target; Daedro solves IK (gripper fixed pointing down)
or  {"q": [7 joint angles], "gripper": g}
with g in [0, 1]: 1 = fully open, 0 = closed.

`obs` keys (numpy arrays, metres / radians / seconds):
    t, q (7), qd (7), tcp (3), gripper_width, object_pos (3), object_quat (4),
    target_pos (3), object_half_size, params (the scenario's physical parameters)

Object pose is privileged simulator state, which is what a scripted controller needs;
perception-based policies are not supported yet.

Outcome classification here is phase-independent, because we can't know a custom
controller's internal phases: success / never_lifted / dropped / misplaced.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import mujoco
import numpy as np

from .episode import CTRL_EVERY, SUCCESS_RADIUS, _ik_step
from .scene import HOME_QPOS, TARGET_XY, SceneParams, build_model

PLUGIN_OUTCOMES = ("success", "never_lifted", "dropped", "misplaced")
LIFT_THRESHOLD = 0.05  # object bottom higher than this counts as lifted, m


@dataclass(frozen=True)
class PluginSpec:
    module: str  # absolute path to the controller file
    cls: str
    params: tuple = ()  # sorted (key, value) pairs; hashable for pickling and comparison
    grip_force_n: float | None = 70.0
    episode_s: float = 10.0
    code_sha256: str = field(default="", compare=True)

    @staticmethod
    def make(module: str | Path, cls: str, params: dict | None = None, grip_force_n=70.0, episode_s=10.0) -> "PluginSpec":
        path = Path(module).resolve()
        if not path.exists():
            raise FileNotFoundError(f"controller module not found: {path}")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        return PluginSpec(str(path), cls, tuple(sorted((params or {}).items())), grip_force_n, float(episode_s), sha)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["module"] = Path(self.module).name
        d["params"] = dict(self.params)
        return d

    def instantiate(self):
        name = f"daedro_user_{self.code_sha256}_{abs(hash(self.module))}"
        spec = importlib.util.spec_from_file_location(name, self.module)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        if not hasattr(mod, self.cls):
            raise AttributeError(f"{self.module} has no class {self.cls!r}")
        return getattr(mod, self.cls)(**dict(self.params))


def run_plugin_episode(p: SceneParams, seed: int, spec: PluginSpec) -> dict:
    rng = np.random.default_rng(seed)
    m = build_model(p, spec.grip_force_n)
    d = mujoco.MjData(m)
    arm_q = np.array([m.joint(f"joint{i}").qposadr[0] for i in range(1, 8)])
    arm_v = np.array([m.joint(f"joint{i}").dofadr[0] for i in range(1, 8)])
    obj_q = m.joint("object_free").qposadr[0]
    obj_v = m.joint("object_free").dofadr[0]
    tcp = m.site("tcp").id
    f1, f2 = m.joint("finger_joint1").qposadr[0], m.joint("finger_joint2").qposadr[0]
    grip = m.actuator("actuator8").id

    d.qpos[arm_q] = HOME_QPOS
    d.qpos[[f1, f2]] = 0.04
    d.ctrl[:7] = HOME_QPOS
    d.ctrl[grip] = 255.0
    mujoco.mj_forward(m, d)
    R_down = d.site_xmat[tcp].reshape(3, 3).copy()
    target = np.array([TARGET_XY[0], TARGET_XY[1], 0.0])
    phys = {"friction": p.friction, "mass": p.mass, "half_size": p.half_size, "ik_noise": p.ik_noise}

    def obs() -> dict:
        return {"t": d.time, "q": d.qpos[arm_q].copy(), "qd": d.qvel[arm_v].copy(), "tcp": d.site_xpos[tcp].copy(),
                "gripper_width": float(d.qpos[f1] + d.qpos[f2]), "object_pos": d.qpos[obj_q:obj_q + 3].copy(),
                "object_quat": d.qpos[obj_q + 3:obj_q + 7].copy(), "target_pos": target.copy(),
                "object_half_size": p.half_size, "params": dict(phys)}

    ctrl = spec.instantiate()
    ctrl.reset(obs())
    lifted, dropped_after_lift, max_lift = False, False, 0.0
    error = None
    n_steps = int(spec.episode_s / m.opt.timestep)
    for k in range(n_steps):
        if k % CTRL_EVERY == 0:
            try:
                a = ctrl.act(obs())
                if "q" in a:
                    q_t = np.asarray(a["q"], float).reshape(7)
                else:
                    q_t = _ik_step(m, d, tcp, np.asarray(a["tcp"], float).reshape(3), R_down, arm_v)
                g = float(np.clip(a.get("gripper", 1.0), 0.0, 1.0))
            except Exception as e:  # a crashing controller is a result, not a harness failure
                error = f"{type(e).__name__}: {e}"
                break
            d.ctrl[:7] = q_t + rng.normal(0.0, p.ik_noise, 7)
            d.ctrl[grip] = 255.0 * g
        mujoco.mj_step(m, d)
        z = d.qpos[obj_q + 2] - p.half_size
        max_lift = max(max_lift, z)
        if z > LIFT_THRESHOLD:
            lifted = True
        elif lifted and z < 0.01 and np.linalg.norm(d.qpos[obj_q:obj_q + 2] - target[:2]) > 0.05:
            dropped_after_lift = True

    err = float(np.linalg.norm(d.qpos[obj_q:obj_q + 2] - target[:2]))
    resting = (d.qpos[obj_q + 2] - p.half_size) < 0.01 and np.linalg.norm(d.qvel[obj_v:obj_v + 3]) < 0.05
    if error:
        outcome = "controller_error"
    elif err <= SUCCESS_RADIUS and resting:
        outcome = "success"
    elif not lifted:
        outcome = "never_lifted"
    elif dropped_after_lift:
        outcome = "dropped"
    else:
        outcome = "misplaced"
    return {"seed": seed, **phys, "outcome": outcome, "success": outcome == "success",
            "place_error_m": err, "max_lift_m": float(max_lift), "controller_error": error}
