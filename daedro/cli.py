"""daedro command line.

    daedro compare --base base.toml --head daedro.toml [--report report.md] [--json out.json] [--fail-on N]
    daedro repro   --config daedro.toml --scenario 17
    daedro run     --config daedro.toml --out results.jsonl
    daedro ci      --config daedro.toml --base-ref origin/main --report daedro-report.md
"""
from __future__ import annotations

import argparse
import json
import sys

from . import config as cfgmod
from .compare import compare, render_markdown, run_suite
from .episode import run_episode
from .sampling import sample


def _compare(a) -> int:
    base_ctrl, base_suite = cfgmod.load(a.base)
    head_ctrl, head_suite = cfgmod.load(a.head)
    if base_suite != head_suite:
        print("note: [suite] differs between base and head; using the head suite for both so scenarios stay paired.",
              file=sys.stderr)
    cmp = compare(base_ctrl, head_ctrl, head_suite, a.workers)
    md = render_markdown(cmp, a.base_label, a.head_label, a.head)
    if a.report:
        open(a.report, "w").write(md + "\n")
    else:
        print(md)
    if a.json:
        json.dump(cmp.to_json(), open(a.json, "w"), indent=1)
    n_reg = len(cmp.regressions)
    if a.fail_on is not None and n_reg > a.fail_on:
        print(f"daedro: {n_reg} regressions > --fail-on {a.fail_on}", file=sys.stderr)
        return 1
    return 0


def _repro(a) -> int:
    ctrl, suite = cfgmod.load(a.config)
    scenarios = sample(suite.method, suite.n, suite.seed, suite.space())
    if not 0 <= a.scenario < len(scenarios):
        print(f"scenario must be in 0..{len(scenarios) - 1}", file=sys.stderr)
        return 2
    seed, params = scenarios[a.scenario]
    r = run_episode(params, seed, controller=ctrl).to_dict()
    print(json.dumps({"scenario": a.scenario, "params": params.__dict__, "seed": seed, "result": r}, indent=1))
    return 0


def _run(a) -> int:
    ctrl, suite = cfgmod.load(a.config)
    rows = run_suite(ctrl, suite, a.workers)
    with open(a.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"{sum(r['success'] for r in rows)}/{len(rows)} succeeded -> {a.out}")
    return 0


def _ci(a) -> int:
    """Compare the config on the base git ref against the working tree (what a PR changes)."""
    import os
    import subprocess
    import tempfile
    try:
        base_text = subprocess.check_output(["git", "show", f"{a.base_ref}:{a.config}"], text=True, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        msg = (f"## Daedro\n\n`{a.config}` does not exist on `{a.base_ref}` yet, so there is no baseline to compare "
               f"against. Merge this PR to set the baseline; later PRs will be compared to it.")
        open(a.report, "w").write(msg + "\n")
        print(msg)
        return 0
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
        f.write(base_text)
        base_path = f.name
    try:
        ns = argparse.Namespace(base=base_path, head=a.config, base_label=a.base_ref.split("/")[-1],
                                head_label=a.head_label, report=a.report, json=a.json, fail_on=a.fail_on,
                                workers=a.workers)
        return _compare(ns)
    finally:
        os.unlink(base_path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="daedro", description="Catch robot behaviour regressions before they ship (simulation).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare", help="run base and head on identical scenarios and report regressions")
    c.add_argument("--base", required=True); c.add_argument("--head", required=True)
    c.add_argument("--base-label", default="base"); c.add_argument("--head-label", default="head")
    c.add_argument("--report"); c.add_argument("--json")
    c.add_argument("--fail-on", type=int, default=None, help="exit 1 if regressions exceed this count")
    c.add_argument("--workers", type=int, default=4)
    c.set_defaults(fn=_compare)
    r = sub.add_parser("repro", help="replay one scenario exactly")
    r.add_argument("--config", required=True); r.add_argument("--scenario", type=int, required=True)
    r.set_defaults(fn=_repro)
    u = sub.add_parser("run", help="run the suite for one config")
    u.add_argument("--config", required=True); u.add_argument("--out", required=True)
    u.add_argument("--workers", type=int, default=4)
    u.set_defaults(fn=_run)
    ci = sub.add_parser("ci", help="compare the config on a base git ref with the working tree")
    ci.add_argument("--config", default="daedro.toml"); ci.add_argument("--base-ref", default="origin/main")
    ci.add_argument("--head-label", default="this PR"); ci.add_argument("--report", default="daedro-report.md")
    ci.add_argument("--json", default=None); ci.add_argument("--fail-on", type=int, default=None)
    ci.add_argument("--workers", type=int, default=4)
    ci.set_defaults(fn=_ci)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
