"""Load a daedro.toml: the controller version under test plus the scenario suite.

    [controller]            # any ControllerConfig field; omitted fields keep defaults
    speed = 1.0
    grip_force_n = 70

    [suite]
    method = "lhs"          # or "random"
    n = 200
    seed = 2026

    [suite.envelope]        # declared operating conditions; failures outside don't count
    mass = [0.05, 1.0, "log"]
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

from .episode import ControllerConfig
from .plugin import PluginSpec
from .sampling import NAMES, PARAM_SPACE


@dataclass(frozen=True)
class Suite:
    method: str = "lhs"
    n: int = 200
    seed: int = 2026
    envelope: tuple = tuple(sorted(PARAM_SPACE.items()))

    def space(self) -> dict:
        return dict(self.envelope)


def load(path: str | Path) -> tuple[ControllerConfig | PluginSpec, Suite]:
    raw = tomllib.loads(Path(path).read_text())
    allowed = {f.name for f in fields(ControllerConfig)}
    ctrl_raw = dict(raw.get("controller", {}))
    if "module" in ctrl_raw:  # bring-your-own controller
        extra = set(ctrl_raw) - {"module", "class", "params", "grip_force_n", "episode_s"}
        if extra:
            raise ValueError(f"{path}: unknown [controller] keys {sorted(extra)} for a custom module")
        if "class" not in ctrl_raw:
            raise ValueError(f"{path}: [controller] needs `class` alongside `module`")
        gf = ctrl_raw.get("grip_force_n", 70.0)
        ctrl = PluginSpec.make(Path(path).resolve().parent / ctrl_raw["module"], ctrl_raw["class"],
                               ctrl_raw.get("params", {}), None if gf in (0, "stock") else float(gf),
                               ctrl_raw.get("episode_s", 10.0))
        return ctrl, _suite(raw, path)
    unknown = set(ctrl_raw) - allowed
    if unknown:
        raise ValueError(f"{path}: unknown [controller] keys {sorted(unknown)}; allowed: {sorted(allowed)}")
    if ctrl_raw.get("grip_force_n", 1) in (0, "stock"):
        ctrl_raw["grip_force_n"] = None
    ctrl = ControllerConfig(**ctrl_raw)
    return ctrl, _suite(raw, path)


def _suite(raw: dict, path) -> Suite:
    s = raw.get("suite", {})
    env = dict(PARAM_SPACE)
    for k, v in s.get("envelope", {}).items():
        if k not in NAMES:
            raise ValueError(f"{path}: unknown envelope parameter {k!r}; allowed: {NAMES}")
        lo, hi, kind = float(v[0]), float(v[1]), (v[2] if len(v) > 2 else PARAM_SPACE[k][2])
        dlo, dhi, _ = PARAM_SPACE[k]
        if not (dlo <= lo < hi <= dhi):
            raise ValueError(f"{path}: envelope {k}=[{lo},{hi}] must lie within the supported range [{dlo},{dhi}]")
        env[k] = (lo, hi, kind)
    return Suite(method=s.get("method", "lhs"), n=int(s.get("n", 200)), seed=int(s.get("seed", 2026)),
                 envelope=tuple(sorted(env.items())))
