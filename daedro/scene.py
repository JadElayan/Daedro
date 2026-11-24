"""Build the pick-and-place scene from the unmodified MuJoCo Menagerie Franka Panda.

Design choice: we load Menagerie's panda.xml with MjSpec and add the object, target
and TCP site in code, instead of copying or editing the vendored XML. That keeps the
robot model traceable to a specific upstream commit, and lets each episode rebuild the
model with its own physical parameters (size changes need recompiled inertia and
collision bounds, which is error-prone to patch in a compiled MjModel).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import mujoco

DEFAULT_MENAGERIE = Path(__file__).resolve().parents[2] / "external" / "mujoco_menagerie"

# Fixed task layout (metres, world frame; robot base at origin, floor at z=0).
OBJECT_XY = (0.50, -0.15)
TARGET_XY = (0.50, 0.15)
HOME_QPOS = (0.0, 0.0, 0.0, -1.57079, 0.0, 1.57079, -0.7853)


@dataclass(frozen=True)
class SceneParams:
    """The four swept parameters. Ranges live in sampling.PARAM_SPACE."""

    friction: float  # sliding friction coefficient of the object (MuJoCo combines pairs with max)
    mass: float  # object mass, kg
    half_size: float  # half edge length of the cube, m (gripper opens to 0.08 m total)
    ik_noise: float  # std of Gaussian noise on commanded joint targets, rad


def menagerie_panda_path() -> Path:
    root = Path(os.environ.get("MENAGERIE_PATH", DEFAULT_MENAGERIE))
    path = root / "franka_emika_panda" / "panda.xml"
    if not path.exists():
        raise FileNotFoundError(
            f"Menagerie Panda not found at {path}. Clone https://github.com/google-deepmind/mujoco_menagerie "
            "and set MENAGERIE_PATH to it."
        )
    return path


def build_model(p: SceneParams, grip_force_n: float | None = None, finger_contact: str = "flat_pad") -> mujoco.MjModel:
    """Compile the scene for one episode.

    grip_force_n: None keeps Menagerie's gripper exactly as shipped (a 100 N/m position
    servo, which squeezes only a few newtons). A number replaces it with a stiff servo
    whose tendon force is clipped to that value, as a stand-in for the real Panda
    gripper's force-controlled grasp. Either way the choice is recorded in results.
    """
    spec = mujoco.MjSpec.from_file(str(menagerie_panda_path()))
    wb = spec.worldbody

    wb.add_light(pos=[0, 0, 2.0], dir=[0, 0, -1])
    wb.add_geom(name="floor", type=mujoco.mjtGeom.mjGEOM_PLANE, size=[0, 0, 0.05], rgba=[0.3, 0.35, 0.4, 1])

    obj = wb.add_body(name="object", pos=[OBJECT_XY[0], OBJECT_XY[1], p.half_size])
    obj.add_freejoint(name="object_free")
    obj.add_geom(
        name="object",
        type=mujoco.mjtGeom.mjGEOM_BOX,
        size=[p.half_size] * 3,
        mass=p.mass,
        friction=[p.friction, 0.005, 0.0001],
        condim=4,  # adds torsional friction so the cube can't spin freely in the grasp
        # MuJoCo's default contact (solref 0.02) is too soft for a 70 N squeeze: the pads
        # sink ~8 mm and pop the cube out. 0.005 s is still >= 2x the 2 ms timestep, which
        # MuJoCo's docs give as the stability floor. Found by sweep, see docs/mujoco_loop.md.
        solref=[0.005, 1.0],
        solimp=[0.95, 0.99, 0.001, 0.5, 2.0],
        rgba=[0.9, 0.4, 0.1, 1],
    )
    wb.add_site(name="target", pos=[TARGET_XY[0], TARGET_XY[1], 0.001], size=[0.03, 0.03, 0.001],
                type=mujoco.mjtGeom.mjGEOM_BOX, rgba=[0, 1, 0, 0.4])
    spec.body("hand").add_site(name="tcp", pos=[0, 0, 0.1034])  # centre of the fingertip pads

    # MuJoCo combines contact friction as the max of the pair. Menagerie fingers and floor
    # default to mu=1, which would mask the object's friction entirely. Set everything
    # else low so the object's coefficient governs the finger-object contact.
    for g in spec.geoms:
        if g.name != "object":
            g.friction = [0.01, 0.005, 0.0001] if g.name != "floor" else [0.5, 0.005, 0.0001]

    if finger_contact == "flat_pad":
        # Menagerie fingers collide through a convex-hull mesh plus five small pad boxes.
        # In our sweep a tilted cube came to rest ON the small boxes and was carried by
        # that ledge, so outcomes stopped following friction (docs/mujoco_loop.md, finding 2).
        # Keep only the main 17 x 17 mm pad on each finger: a flat face whose grip is
        # governed by Coulomb friction, which we can check against a closed-form bound.
        for g in spec.geoms:
            if g.parent.name in ("left_finger", "right_finger") and g.contype:
                if g.classname.name != "fingertip_pad_collision_1":
                    g.contype = 0
                    g.conaffinity = 0
    elif finger_contact != "as_shipped":
        raise ValueError(f"unknown finger_contact {finger_contact!r}")

    if grip_force_n is not None:
        act = spec.actuator("actuator8")
        kp = 5000.0  # stiff enough that the clip, not the gain, sets the squeeze
        act.gainprm[0] = 0.04 * kp / 255.0
        act.biasprm[1] = -kp
        act.biasprm[2] = -50.0
        act.forcerange = [-grip_force_n, grip_force_n]

    return spec.compile()
