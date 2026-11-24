"""The failure library: confirmed failures pinned as permanent regression tests.

Stored next to daedro.toml as daedro-failures.toml (committed to the team's repo):

    [[failure]]
    id = "small-heavy-cube"
    seed = 1234567
    friction = 0.39
    mass = 0.79
    half_size = 0.0105
    ik_noise = 0.0
    source = "sim: PR #1 regression, scenario 32"   # or "field: cell 3, 2026-11-20"
    note = "gripper closed before reaching a 2 cm part"
    added = "2026-11-24"

Every comparison runs all pinned failures on both versions, reported separately from the
sampled scenarios (they were chosen *because* they failed, so they must not feed the
statistics). A pinned scenario that passes on base and fails on head is a regression of a
known, previously fixed failure: the worst kind.

Field failures: `daedro pin --field` records the conditions measured on a real robot.
The simulator re-creates those conditions; it does not replay the real event, so a pinned
field failure is an approximation to investigate with, not a recording.
"""
from __future__ import annotations

import datetime as _dt
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from .scene import SceneParams

DEFAULT_FILE = "daedro-failures.toml"


@dataclass(frozen=True)
class Pinned:
    id: str
    seed: int
    friction: float
    mass: float
    half_size: float
    ik_noise: float
    source: str = ""
    note: str = ""
    added: str = ""

    @property
    def params(self) -> SceneParams:
        return SceneParams(self.friction, self.mass, self.half_size, self.ik_noise)


def library_path(config_path: str | Path, raw_suite: dict | None = None) -> Path:
    name = (raw_suite or {}).get("failures", DEFAULT_FILE)
    return Path(config_path).resolve().parent / name


def load(path: str | Path) -> tuple[Pinned, ...]:
    p = Path(path)
    if not p.exists():
        return ()
    raw = tomllib.loads(p.read_text())
    out = []
    for i, f in enumerate(raw.get("failure", [])):
        try:
            out.append(Pinned(id=str(f["id"]), seed=int(f["seed"]), friction=float(f["friction"]),
                              mass=float(f["mass"]), half_size=float(f["half_size"]),
                              ik_noise=float(f.get("ik_noise", 0.0)), source=str(f.get("source", "")),
                              note=str(f.get("note", "")), added=str(f.get("added", ""))))
        except KeyError as e:
            raise ValueError(f"{p}: [[failure]] #{i + 1} is missing {e}") from None
    ids = [f.id for f in out]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{p}: duplicate failure ids")
    return tuple(out)


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def append(path: str | Path, f: Pinned) -> None:
    p = Path(path)
    existing = load(p)
    if any(e.id == f.id for e in existing):
        raise ValueError(f"a failure with id {f.id!r} is already pinned in {p}")
    header = "" if p.exists() else ("# Daedro failure library: confirmed failures, re-run on every comparison.\n"
                                    "# Add with `daedro pin`; remove an entry only when the behaviour it covers is retired.\n")
    block = (f"\n[[failure]]\nid = {_q(f.id)}\nseed = {f.seed}\nfriction = {f.friction:.6g}\nmass = {f.mass:.6g}\n"
             f"half_size = {f.half_size:.6g}\nik_noise = {f.ik_noise:.6g}\nsource = {_q(f.source)}\n"
             f"note = {_q(f.note)}\nadded = {_q(f.added or _dt.date.today().isoformat())}\n")
    with open(p, "a") as fh:
        fh.write(header + block)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "failure"


def to_dict(f: Pinned) -> dict:
    return asdict(f)
