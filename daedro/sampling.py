"""Random and Latin Hypercube sampling over the 4-parameter space.

LHS is implemented here in ~10 lines instead of importing scipy.stats.qmc so that the
exact stratification is visible and testable; scipy's version gives the same guarantee
(one point per stratum per dimension). Ranges follow RoboGate's Franka space where the
parameter exists there; half_size is capped so the cube fits the 8 cm gripper opening.
"""
from __future__ import annotations

import numpy as np

from .scene import SceneParams

# name: (low, high, scale)
PARAM_SPACE: dict[str, tuple[float, float, str]] = {
    "friction": (0.05, 1.2, "log"),
    "mass": (0.05, 2.0, "log"),
    "half_size": (0.01, 0.035, "linear"),
    "ik_noise": (0.0, 0.04, "linear"),
}
NAMES = list(PARAM_SPACE)


def _scale(u: np.ndarray, space: dict | None = None) -> np.ndarray:
    space = space or PARAM_SPACE
    out = np.empty_like(u)
    for j, name in enumerate(NAMES):
        lo, hi, kind = space[name]
        out[:, j] = np.exp(np.log(lo) + u[:, j] * (np.log(hi) - np.log(lo))) if kind == "log" else lo + u[:, j] * (hi - lo)
    return out


def random_unit(n: int, rng: np.random.Generator) -> np.ndarray:
    return rng.random((n, len(NAMES)))


def lhs_unit(n: int, rng: np.random.Generator) -> np.ndarray:
    """Each column is a random permutation of the n strata, jittered within its stratum."""
    u = (rng.random((n, len(NAMES))) + np.arange(n)[:, None]) / n
    for j in range(len(NAMES)):
        u[:, j] = u[rng.permutation(n), j]
    return u


def sample(method: str, n: int, seed: int, space: dict | None = None) -> list[tuple[int, SceneParams]]:
    """Return (episode_seed, params) pairs. Episode seeds derive from the campaign seed.
    `space` overrides PARAM_SPACE (same keys) to declare a narrower operating envelope."""
    rng = np.random.default_rng(seed)
    u = {"random": random_unit, "lhs": lhs_unit}[method](n, rng)
    x = _scale(u, space)
    ep_seeds = rng.integers(0, 2**31 - 1, size=n)
    return [(int(s), SceneParams(**dict(zip(NAMES, map(float, row))))) for s, row in zip(ep_seeds, x)]
