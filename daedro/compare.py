"""Paired regression comparison between two controller versions.

Both versions run the *same* scenarios (identical physical parameters and noise seeds),
so every difference in outcome is attributable to the controller change, not to luck in
which scenarios were drawn. That pairing is what lets a few hundred sim episodes say
something useful: an exact McNemar test on the discordant pairs, plus per-scenario
regressions that can each be replayed with one command.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from multiprocessing import Pool

import mujoco

from .config import Suite
from .episode import ControllerConfig, run_episode
from .plugin import PluginSpec, run_plugin_episode
from .sampling import NAMES, sample
from .scene import menagerie_panda_path


def _run(job):
    idx, seed, params, ctrl = job
    r = run_plugin_episode(params, seed, ctrl) if isinstance(ctrl, PluginSpec) else run_episode(params, seed, controller=ctrl).to_dict()
    r["scenario"] = idx
    return r


def run_suite(ctrl: ControllerConfig, suite: Suite, workers: int = 4) -> list[dict]:
    jobs = [(i, s, p, ctrl) for i, (s, p) in enumerate(sample(suite.method, suite.n, suite.seed, suite.space()))]
    with Pool(workers) as pool:
        return pool.map(_run, jobs, chunksize=4)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact binomial test on discordant pairs (b = regressions, c = fixes)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


@dataclass
class Comparison:
    base_cfg: ControllerConfig
    head_cfg: ControllerConfig
    suite: Suite
    base: list[dict]
    head: list[dict]

    @property
    def regressions(self) -> list[tuple[dict, dict]]:
        return [(b, h) for b, h in zip(self.base, self.head) if b["success"] and not h["success"]]

    @property
    def fixes(self) -> list[tuple[dict, dict]]:
        return [(b, h) for b, h in zip(self.base, self.head) if not b["success"] and h["success"]]

    def p_value(self) -> float:
        return mcnemar_exact(len(self.regressions), len(self.fixes))

    def to_json(self) -> dict:
        sr = lambda rows: sum(r["success"] for r in rows) / len(rows)
        return {
            "suite": {"method": self.suite.method, "n": self.suite.n, "seed": self.suite.seed, "envelope": self.suite.space()},
            "base_config": self.base_cfg.to_dict(), "head_config": self.head_cfg.to_dict(),
            "base_success_rate": sr(self.base), "head_success_rate": sr(self.head),
            "regressions": [h["scenario"] for _, h in self.regressions],
            "fixes": [h["scenario"] for _, h in self.fixes],
            "mcnemar_p": self.p_value(),
            "environment": environment(),
        }


def compare(base_cfg: ControllerConfig, head_cfg: ControllerConfig, suite: Suite, workers: int = 4) -> Comparison:
    return Comparison(base_cfg, head_cfg, suite, run_suite(base_cfg, suite, workers), run_suite(head_cfg, suite, workers))


def environment() -> dict:
    import subprocess
    try:
        commit = subprocess.check_output(["git", "-C", str(menagerie_panda_path().parents[1]), "rev-parse", "--short", "HEAD"],
                                         text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        commit = "unknown"
    return {"simulator": f"MuJoCo {mujoco.__version__}", "robot": f"Franka Panda (MuJoCo Menagerie {commit})",
            "task": "scripted pick-and-place, 3 cm success radius"}


def _fmt_params(r: dict) -> str:
    return (f"μ={r['friction']:.2f} · m={r['mass']:.2f} kg · size={2 * r['half_size'] * 100:.1f} cm · "
            f"noise={r['ik_noise']:.3f} rad")


def _clusters(cmp: Comparison, bins: int = 4) -> list[str]:
    """Per-parameter regression rate by quartile of the envelope: where did it break?"""
    import numpy as np
    lines = []
    space = cmp.suite.space()
    base_ok = [b for b in cmp.base if b["success"]]
    if not base_ok:
        return lines
    reg_ids = {h["scenario"] for _, h in cmp.regressions}
    for name in NAMES:
        lo, hi, kind = space[name]
        tf = (lambda x: math.log(x)) if kind == "log" else (lambda x: x)
        edges = np.linspace(tf(lo), tf(hi), bins + 1)
        cells = []
        worst = 0.0
        for i in range(bins):
            inb = [b for b in base_ok if edges[i] <= tf(b[name]) <= edges[i + 1]]
            rate = sum(b["scenario"] in reg_ids for b in inb) / len(inb) if inb else 0.0
            worst = max(worst, rate)
            a, z = (math.exp(edges[i]), math.exp(edges[i + 1])) if kind == "log" else (edges[i], edges[i + 1])
            cells.append(f"{a:.3g}–{z:.3g}: **{rate:.0%}**" if rate >= 0.2 else f"{a:.3g}–{z:.3g}: {rate:.0%}")
        lines.append((worst, f"| `{name}` | " + " | ".join(cells) + " |"))
    lines.sort(key=lambda t: -t[0])
    return [l for _, l in lines]


def render_markdown(cmp: Comparison, base_label: str, head_label: str, head_config_path: str, max_rows: int = 10,
                    videos: list | None = None, videos_url: str | None = None) -> str:
    n = cmp.suite.n
    kb, kh = sum(r["success"] for r in cmp.base), sum(r["success"] for r in cmp.head)
    lb, ub = wilson(kb, n)
    lh, uh = wilson(kh, n)
    regs, fixes, p = cmp.regressions, cmp.fixes, cmp.p_value()
    env = environment()

    if regs and p < 0.05 and kh < kb:
        verdict = f"🔴 **Regression detected.** {len(regs)} scenarios that passed on `{base_label}` fail on `{head_label}`."
    elif regs:
        verdict = (f"🟡 **{len(regs)} scenario(s) regressed**, {len(fixes)} fixed. The net change is not statistically "
                   f"significant (p={p:.2g}); inspect the regressions below.")
    else:
        verdict = f"🟢 **No regressions** across {n} paired scenarios."

    out = [f"## Daedro regression report: `{base_label}` → `{head_label}`", "", verdict, "",
           "| | Success rate | 95% CI |", "|---|---|---|",
           f"| `{base_label}` (base) | {kb}/{n} = {kb / n:.1%} | {lb:.1%}–{ub:.1%} |",
           f"| `{head_label}` (head) | {kh}/{n} = {kh / n:.1%} | {lh:.1%}–{uh:.1%} |", "",
           f"Paired on identical scenarios: **{len(regs)} regressed**, **{len(fixes)} fixed**, "
           f"{n - len(regs) - len(fixes)} unchanged. Exact McNemar p = {p:.3g}.", ""]

    bd, hd = cmp.base_cfg.to_dict(), cmp.head_cfg.to_dict()
    diff = {k: (bd.get(k, "—"), hd.get(k, "—")) for k in dict.fromkeys([*bd, *hd]) if bd.get(k) != hd.get(k)}
    if diff:
        out += ["**What changed in the controller**", "", "| Parameter | Base | Head |", "|---|---|---|"]
        out += [f"| `{k}` | {a} | {b} |" for k, (a, b) in diff.items()] + [""]

    from collections import Counter
    cb, ch = Counter(r["outcome"] for r in cmp.base), Counter(r["outcome"] for r in cmp.head)
    out += ["**Outcomes**", "", "| Outcome | Base | Head | Δ |", "|---|---|---|---|"]
    for o in ("success", "grasp_miss", "slip_on_lift", "drop_in_transit", "never_lifted", "dropped", "misplaced", "controller_error"):
        if cb[o] or ch[o]:
            out.append(f"| {o} | {cb[o]} | {ch[o]} | {ch[o] - cb[o]:+d} |")
    out.append("")

    if regs:
        cl = _clusters(cmp)
        out += ["**Where the regressions cluster** (share of base-passing scenarios that regressed, by quarter of the envelope)",
                "", "| Parameter | Q1 | Q2 | Q3 | Q4 |", "|---|---|---|---|---|", *cl, ""]
        out += [f"**Regressed scenarios** (showing {min(max_rows, len(regs))} of {len(regs)})", "",
                "| # | Conditions | Head outcome | Reproduce |", "|---|---|---|---|"]
        for b, h in sorted(regs, key=lambda t: -t[1]["mass"])[:max_rows]:
            out.append(f"| {h['scenario']} | {_fmt_params(h)} | {h['outcome']} | "
                       f"`daedro repro --config {head_config_path} --scenario {h['scenario']}` |")
        out.append("")

    if videos:
        where = (f"[download the videos]({videos_url}) (zip: open `index.html`)" if videos_url
                 else "saved to the preview folder for this run")
        out += [f"🎬 **Side-by-side replays** of {len(videos)} regressed scenario(s) "
                f"({', '.join('#' + str(v['scenario']) for v in videos)}): {where}.", ""]
    out += ["<details markdown=\"1\"><summary>Scenario suite and environment</summary>", "",
            f"- Suite: {cmp.suite.method.upper()}, n={n}, seed={cmp.suite.seed}; both versions ran the identical scenarios.",
            "- Declared operating envelope: " + "; ".join(f"`{k}` {lo:g}–{hi:g}" for k, (lo, hi, _) in cmp.suite.space().items()),
            f"- {env['simulator']} · {env['robot']} · {env['task']}", "", "</details>", "",
            "> ⚠️ **Simulation only.** These results come from a MuJoCo model, not hardware. A pass here does not "
            "guarantee real-world performance or safety; a regression here is a lead to investigate, not proof of a "
            "hardware failure."]
    return "\n".join(out)
