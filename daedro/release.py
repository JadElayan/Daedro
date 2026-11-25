"""Release records: which robot setups can take this update, and what is the evidence?

A release file lists the controller versions and the hardware setups the release must cover:

    [release]
    name = "pick-cycle v2.4 -> v2.5"
    base = "v2.4.toml"            # controller as deployed (a daedro.toml)
    head = "v2.5.toml"            # controller proposed for release

    [[setup]]
    name = "Site A · light parts"
    grip_force_n = 70             # hardware differences from the controller files
    [setup.envelope]
    mass = [0.05, 0.5]

    [[setup]]
    name = "Site B · suction cell"
    evidence = "none"             # no simulation model: the record says hardware test needed

    [[setup]]
    name = "Lab · SO-101"
    base = "so101_v1.toml"        # a setup can name its own controller files
    head = "so101_v2.toml"

`daedro release` writes record.json (the data), record.md (for PRs) and index.html (for
the release lead). `daedro approve` appends approvals and hand-offs and re-renders.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import html
import json
import tomllib
from pathlib import Path

from . import config as cfgmod
from .compare import compare, environment

VERDICTS = {
    "ready": ("Ready", "No regressions and no returning failures in simulation."),
    "review": ("Review", "Some scenarios regressed, but the change is not statistically significant. Inspect before approving."),
    "blocked": ("Blocked", "Significant regressions or a known failure came back."),
    "hardware": ("Needs hardware test", "No simulation model for this setup: there is no evidence yet. Run a supervised hardware test."),
}


def _override(ctrl, suite, setup: dict, path: Path):
    """Apply a setup's hardware differences to a controller and suite."""
    if "grip_force_n" in setup and hasattr(ctrl, "grip_force_n"):
        gf = setup["grip_force_n"]
        ctrl = dataclasses.replace(ctrl, grip_force_n=None if gf in (0, "stock") else float(gf))
    if "envelope" in setup or "n" in setup or "seed" in setup:
        raw = {"suite": {"method": suite.method, "n": setup.get("n", suite.n), "seed": setup.get("seed", suite.seed),
                         "envelope": {k: list(v) for k, v in suite.space().items()} | setup.get("envelope", {})}}
        from .so101 import SO101_SPACE, So101Config
        space = SO101_SPACE if isinstance(ctrl, So101Config) else None
        new = cfgmod._suite(raw, path, space)
        suite = dataclasses.replace(new, pinned=suite.pinned, failures_file=suite.failures_file)
    return ctrl, suite


def _verdict(cmp) -> str:
    regs, preg = cmp.regressions, cmp.pinned_regressions()
    kb = sum(r["success"] for r in cmp.base)
    kh = sum(r["success"] for r in cmp.head)
    if preg or (regs and cmp.p_value() < 0.05 and kh < kb):
        return "blocked"
    if regs:
        return "review"
    return "ready"


def run_release(release_file: str | Path, workers: int = 4) -> dict:
    rf = Path(release_file).resolve()
    raw = tomllib.loads(rf.read_text())
    rel = raw.get("release", {})
    setups = raw.get("setup", [])
    if not setups:
        raise ValueError(f"{rf}: add at least one [[setup]]")
    out = []
    for s in setups:
        name = s.get("name") or f"setup {len(out) + 1}"
        if s.get("evidence", "sim") == "none":
            out.append({"name": name, "verdict": "hardware", "notes": s.get("notes", "")})
            continue
        bpath = rf.parent / s.get("base", rel.get("base", ""))
        hpath = rf.parent / s.get("head", rel.get("head", ""))
        bctrl, _ = cfgmod.load(bpath)
        hctrl, suite = cfgmod.load(hpath)
        bctrl, _ = _override(bctrl, suite, s, rf)
        hctrl, suite = _override(hctrl, suite, s, rf)
        cmp = compare(bctrl, hctrl, suite, workers)
        kb, kh, n = sum(r["success"] for r in cmp.base), sum(r["success"] for r in cmp.head), suite.n
        regs = sorted(cmp.regressions, key=lambda t: -t[1]["mass"])
        out.append({
            "name": name, "verdict": _verdict(cmp), "notes": s.get("notes", ""),
            "base_config": str(bpath.relative_to(rf.parent)), "head_config": str(hpath.relative_to(rf.parent)),
            "n": n, "base_success": kb, "head_success": kh, "regressed": len(cmp.regressions), "fixed": len(cmp.fixes),
            "p_value": cmp.p_value(), "envelope": suite.space(),
            "pinned": [{"id": h["scenario"], "base": b["outcome"], "head": h["outcome"]}
                       for b, h in zip(cmp.pinned_base, cmp.pinned_head)],
            "top_regressions": [{"scenario": h["scenario"], "outcome": h["outcome"], "friction": h["friction"],
                                 "mass": h["mass"], "size_cm": round(2 * h["half_size"] * 100, 1),
                                 "repro": f"daedro repro --config {hpath.relative_to(rf.parent)} --scenario {h['scenario']}"}
                                for _, h in regs[:5]],
            "environment": environment(hctrl),
        })
    return {"release": rel.get("name", rf.stem), "created": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "setups": out, "approvals": [], "handoffs": []}


def save(record: dict, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "record.json").write_text(json.dumps(record, indent=1))
    (out / "record.md").write_text(render_markdown(record))
    (out / "index.html").write_text(render_html(record))
    return out


def approve(record_dir: str | Path, by: str, setups: list[str], note: str = "", handoff: str = "") -> dict:
    d = Path(record_dir)
    rec = json.loads((d / "record.json").read_text())
    names = {s["name"]: s for s in rec["setups"]}
    for n in setups:
        if n not in names:
            raise ValueError(f"unknown setup {n!r}; setups: {list(names)}")
        if names[n]["verdict"] in ("blocked", "hardware") and "override" not in note.lower():
            raise ValueError(f"{n!r} is {VERDICTS[names[n]['verdict']][0]!r}; approving it needs a note containing "
                             f"'override' that says why")
    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    rec["approvals"].append({"by": by, "setups": setups, "note": note, "at": now})
    if handoff:
        rec["handoffs"].append({"to": handoff, "setups": setups, "by": by, "at": now})
    save(rec, d)
    return rec


def _summary(rec: dict) -> tuple[int, int]:
    approved = {n for a in rec["approvals"] for n in a["setups"]}
    return len(approved), len(rec["setups"])


def render_markdown(rec: dict) -> str:
    rows = []
    for s in rec["setups"]:
        label = VERDICTS[s["verdict"]][0]
        if s["verdict"] == "hardware":
            ev = "No simulation model"
        else:
            pinned = sum(1 for p in s["pinned"] if p["head"] == "success")
            ev = (f"{s['regressed']} regressed / {s['n']} · success {s['base_success']}→{s['head_success']}"
                  + (f" · pinned {pinned}/{len(s['pinned'])} hold" if s["pinned"] else ""))
        rows.append(f"| {s['name']} | **{label}** | {ev} |")
    a, n = _summary(rec)
    out = [f"## Release record: {rec['release']}", "", f"{a} of {n} setups approved.", "",
           "| Setup | Verdict | Evidence (simulation) |", "|---|---|---|", *rows, ""]
    for s in rec["setups"]:
        if s.get("top_regressions"):
            out += [f"**{s['name']}: replay the failures**", ""]
            out += [f"- #{r['scenario']} {r['outcome']} (μ={r['friction']:.2f}, {r['mass']:.2f} kg, {r['size_cm']} cm): "
                    f"`{r['repro']}`" for r in s["top_regressions"]] + [""]
    if rec["approvals"]:
        out += ["**Approvals**", ""] + [f"- {x['at']}: {x['by']} approved {', '.join(x['setups'])}"
                                         + (f" ({x['note']})" if x['note'] else "") for x in rec["approvals"]] + [""]
    if rec["handoffs"]:
        out += ["**Hand-offs**", ""] + [f"- {x['at']}: {', '.join(x['setups'])} → {x['to']} (by {x['by']})"
                                         for x in rec["handoffs"]] + [""]
    out.append("> Simulation evidence only. A Ready verdict means no regressions were found in simulation for the "
               "declared conditions; it does not guarantee real-world performance or safety.")
    return "\n".join(out)


def render_html(rec: dict) -> str:
    e = html.escape
    cards = []
    for s in rec["setups"]:
        label, expl = VERDICTS[s["verdict"]]
        if s["verdict"] == "hardware":
            body = f"<p class='muted'>{e(expl)}</p>"
        else:
            regs = "".join(f"<li><b>#{r['scenario']}</b> {e(r['outcome'])} · μ={r['friction']:.2f} · {r['mass']:.2f} kg · "
                           f"{r['size_cm']} cm<br><code>{e(r['repro'])}</code></li>" for r in s["top_regressions"])
            pinned = "".join(f"<li><code>{e(p['id'])}</code> {e(p['base'])} → {e(p['head'])}</li>" for p in s["pinned"])
            body = (f"<div class='stats'><div><span>{s['base_success']}/{s['n']}</span>before</div>"
                    f"<div><span>{s['head_success']}/{s['n']}</span>after</div>"
                    f"<div><span>{s['regressed']}</span>regressed</div><div><span>{s['p_value']:.2g}</span>p-value</div></div>"
                    f"<p class='muted'>{e(expl)}</p>"
                    + (f"<h4>Replay what broke</h4><ul>{regs}</ul>" if regs else "")
                    + (f"<h4>Failure library</h4><ul>{pinned}</ul>" if pinned else "")
                    + f"<p class='env'>{e(s['environment']['robot'])} · {e(s['environment']['simulator'])}</p>")
        cards.append(f"<article class='card v-{s['verdict']}'><header><h3>{e(s['name'])}</h3>"
                     f"<span class='badge'>{e(label)}</span></header>"
                     + (f"<p class='notes'>{e(s['notes'])}</p>" if s.get("notes") else "") + body + "</article>")
    a, n = _summary(rec)
    log = "".join(f"<li>{e(x['at'])} · <b>{e(x['by'])}</b> approved {e(', '.join(x['setups']))}"
                  + (f" — {e(x['note'])}" if x['note'] else "") + "</li>" for x in rec["approvals"]) or "<li class='muted'>No approvals yet. Run <code>daedro approve</code>.</li>"
    hand = "".join(f"<li>{e(x['at'])} · {e(', '.join(x['setups']))} → <b>{e(x['to'])}</b> (by {e(x['by'])})</li>"
                   for x in rec["handoffs"]) or "<li class='muted'>Not handed off.</li>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Release record · {e(rec['release'])}</title>
<style>
:root{{--bg:#08090b;--surface:#101318;--raised:#171c23;--line:#2b343f;--ink:#fafafa;--muted:#aaaab0;--accent:#9ab0c7;
--ready:#5fb98a;--review:#d9a84a;--blocked:#e2665c;--hardware:#9ab0c7}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,sans-serif;padding:24px 16px}}
main{{max-width:1000px;margin:0 auto}}h1{{font-size:28px;letter-spacing:-.03em;margin:0 0 4px}}h3{{margin:0;font-size:17px}}
h4{{margin:16px 0 6px;font-size:13px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.06em}}
.muted{{color:var(--muted)}}.top{{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:20px}}
.grid{{display:grid;gap:14px}}.card{{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--c);border-radius:8px;padding:16px}}
.card header{{display:flex;justify-content:space-between;gap:12px;align-items:center}}
.badge{{font-size:12px;font-weight:600;padding:3px 9px;border-radius:99px;background:var(--raised);color:var(--c);border:1px solid var(--c);white-space:nowrap}}
.v-ready{{--c:var(--ready)}}.v-review{{--c:var(--review)}}.v-blocked{{--c:var(--blocked)}}.v-hardware{{--c:var(--hardware)}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0 4px}}.stats div{{background:var(--raised);border-radius:6px;padding:8px;color:var(--muted);font-size:12px}}
.stats span{{display:block;color:var(--ink);font-size:20px;font-weight:600}}ul{{margin:0;padding-left:18px}}li{{margin:4px 0}}
code{{font:12px ui-monospace,monospace;background:var(--raised);padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}}
.env,.notes{{color:var(--muted);font-size:13px;margin:10px 0 0}}.log{{margin-top:24px;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:16px}}
footer{{color:var(--muted);font-size:13px;margin-top:20px}}@media(max-width:600px){{.stats{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><main>
<div class="top"><div><p class="muted" style="margin:0">Daedro release record</p><h1>{e(rec['release'])}</h1></div>
<p class="muted" style="margin:0">{a} of {n} setups approved · created {e(rec['created'])}</p></div>
<div class="grid">{''.join(cards)}</div>
<section class="log"><h4 style="margin-top:0">Approvals</h4><ul>{log}</ul><h4>Hand-offs</h4><ul>{hand}</ul></section>
<footer>Simulation evidence only. “Ready” means no regressions were found in simulation for the declared conditions; it does not guarantee real-world performance or safety.</footer>
</main></body></html>"""
