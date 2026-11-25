"""Make the example incident recording used by the demo case.

We have no customer data yet, so this simulates the Site B incident from the example release
(v2.5 drops a heavy bracket mid-transport) and saves it as an MCAP recording, the same format a
real cell would log. The file's metadata says source = "simulation (example)".

    PYTHONPATH=. python examples/cases/make_example_recording.py
"""
import dataclasses
from pathlib import Path

from daedro import config as cfgmod
from daedro.recording import record_episode
from daedro.release import _override
from daedro.sampling import sample

HERE = Path(__file__).resolve().parent
ctrl, suite = cfgmod.load(HERE.parent / "release" / "v2.5.toml")
ctrl, suite = _override(ctrl, suite, {"envelope": {"mass": [0.3, 1.0]}}, HERE)  # Site B: heavy parts
seed, params = sample(suite.method, suite.n, suite.seed, suite.space())[14]
path, result = record_episode(params, seed, ctrl, HERE / "recordings" / "cell-b2_2026-11-20_shift2_pick-0417.mcap",
                              cell="Site B · cell 2 (example)", software_version="pick-cycle v2.5",
                              gripper="parallel jaw, 40 N", part="steel bracket (example)")
print(path, result["outcome"], params)
