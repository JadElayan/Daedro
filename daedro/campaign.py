"""Run a sampling campaign and write results as JSON Lines plus a metadata header.

    python -m daedro.campaign --method lhs --n 1000 --seed 2026 --out results/lhs_2026.jsonl

The metadata records everything needed to rerun: method, n, seed, grip setting,
MuJoCo version and the Menagerie commit, plus a hash of the result rows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from multiprocessing import Pool
from pathlib import Path

import mujoco

from .episode import run_episode
from .sampling import PARAM_SPACE, sample
from .scene import menagerie_panda_path


def _menagerie_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(menagerie_panda_path().parents[1]), "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def _run(args):
    seed, params, grip = args
    return run_episode(params, seed, grip).to_dict()


def run_campaign(method: str, n: int, seed: int, grip_force_n: float | None = 70.0, workers: int = 4) -> dict:
    jobs = [(s, p, grip_force_n) for s, p in sample(method, n, seed)]
    t0 = time.time()
    with Pool(workers) as pool:
        rows = pool.map(_run, jobs, chunksize=8)  # map preserves order -> deterministic file
    digest = hashlib.sha256("\n".join(json.dumps(r, sort_keys=True) for r in rows).encode()).hexdigest()
    meta = {
        "method": method, "n": n, "seed": seed, "grip_force_n": grip_force_n,
        "param_space": PARAM_SPACE, "mujoco": mujoco.__version__, "menagerie_commit": _menagerie_commit(),
        "python": platform.python_version(), "elapsed_s": round(time.time() - t0, 1),
        "success_rate": sum(r["success"] for r in rows) / n, "rows_sha256": digest,
    }
    return {"metadata": meta, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["random", "lhs"], required=True)
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--grip-force", type=float, default=70.0, help="tendon force limit, N; <=0 = stock Menagerie gripper")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    res = run_campaign(a.method, a.n, a.seed, a.grip_force if a.grip_force > 0 else None, a.workers)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as f:
        f.write(json.dumps({"metadata": res["metadata"]}) + "\n")
        for r in res["rows"]:
            f.write(json.dumps(r) + "\n")
    print(json.dumps(res["metadata"], indent=2))


if __name__ == "__main__":
    main()
