"""Cases: turn one real robot incident into something a team can investigate, fix and verify.

A case lives in its own folder:

    cases/<id>/case.json      context, incident, evidence log, status
    cases/<id>/clip.mp4       camera clip around the incident (from the recording)
    cases/<id>/timeline.svg   part height and gripper opening over time, incident marked
    cases/<id>/index.html     the case page

Evidence kinds and what they can claim:
    recording        what happened. Supports investigation only: it cannot show what a
                     changed controller would have done.
    reproduction     whether simulation recreates the incident at the recorded conditions
                     and at nearby variations (if not, simulation can't verify a fix).
    fix_test         original vs proposed controller on the case and the same variations.
    hardware         a supervised physical test, entered by the team.
    outcome          real results after the change went out, entered by the team.

Status follows the evidence: open → reproduced → fix verified (simulation) → hardware tested
→ outcome recorded. A fix is only "verified in simulation" when the incident reproduced.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import html
import json
import math
from pathlib import Path

import numpy as np

from .recording import Incident, clip_video, find_incident, read_mcap
from .scene import SceneParams

FAMILY = {"slip_on_lift": "never_lifted", "grasp_miss": "never_lifted", "never_lifted": "never_lifted",
          "drop_in_transit": "dropped", "dropped": "dropped", "misplaced": "misplaced", "success": "none",
          "controller_error": "error"}
STATUS_ORDER = ["open", "not reproduced", "reproduced", "fix verified (simulation)", "hardware tested", "outcome recorded"]


def _pool(n):
    """Worker pool that never forks a process holding rendering (EGL) threads."""
    import multiprocessing as mp
    ctx = mp.get_context("forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn")
    return ctx.Pool(n)


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _load(case_dir) -> dict:
    return json.loads((Path(case_dir) / "case.json").read_text())


def _save(case_dir, case: dict) -> None:
    d = Path(case_dir)
    case["status"] = status(case)
    (d / "case.json").write_text(json.dumps(case, indent=1))
    (d / "index.html").write_text(render_html(case, d))


def status(case: dict) -> str:
    kinds = {e["kind"]: e for e in case["evidence"]}
    s = "open"
    rep = [e for e in case["evidence"] if e["kind"] == "reproduction"]
    if rep:
        s = "reproduced" if rep[-1]["reproduced"] else "not reproduced"
    fix = [e for e in case["evidence"] if e["kind"] == "fix_test"]
    if fix and fix[-1]["verified"] and s == "reproduced":
        s = "fix verified (simulation)"
    if any(e["kind"] == "hardware" and e["result"] == "pass" for e in case["evidence"]):
        s = "hardware tested"
    if "outcome" in kinds:
        s = "outcome recorded"
    return s


def _timeline_svg(rec, inc: Incident, half: float) -> str:
    t = rec.t
    z = (rec.object_pos[:, 2] - half) * 100  # cm
    g = rec.gripper
    W, H, P = 720, 220, 36
    t0, t1 = float(t[0]), float(t[-1]) or 1.0
    X = lambda v: P + (v - t0) / (t1 - t0) * (W - 2 * P)
    zmax = max(5.0, float(z.max()) * 1.1)
    Yz = lambda v: H - P - v / zmax * (H - 2 * P)
    gmin, gmax = float(g.min()), float(g.max()) if float(g.max()) > float(g.min()) else float(g.min()) + 1
    Yg = lambda v: H - P - (v - gmin) / (gmax - gmin) * (H - 2 * P)
    pz = " ".join(f"{X(a):.1f},{Yz(b):.1f}" for a, b in zip(t, z))
    pg = " ".join(f"{X(a):.1f},{Yg(b):.1f}" for a, b in zip(t, g))
    xi = X(inc.t)
    ticks = "".join(f'<text x="{X(s):.1f}" y="{H - 12}" fill="#aaaab0" font-size="11" text-anchor="middle">{s:.0f}s</text>'
                    for s in np.arange(math.ceil(t0), t1 + 1e-9, 1.0))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="Part height and gripper opening over time; incident at {inc.t:.1f} s">'
            f'<rect width="{W}" height="{H}" fill="#101318"/>'
            f'<line x1="{P}" y1="{H - P}" x2="{W - P}" y2="{H - P}" stroke="#2b343f"/>{ticks}'
            f'<polyline points="{pg}" fill="none" stroke="#526071" stroke-width="2" stroke-dasharray="4 3"/>'
            f'<polyline points="{pz}" fill="none" stroke="#9ab0c7" stroke-width="2.5"/>'
            f'<line x1="{xi:.1f}" y1="{P - 10}" x2="{xi:.1f}" y2="{H - P}" stroke="#e2665c" stroke-width="2"/>'
            f'<text x="{xi + 6:.1f}" y="{P - 14}" fill="#e2665c" font-size="12">incident · {inc.t:.1f}s</text>'
            f'<text x="{P}" y="18" fill="#9ab0c7" font-size="12">part height (cm, max {z.max():.0f})</text>'
            f'<text x="{P + 190}" y="18" fill="#7f8b99" font-size="12">- - gripper opening</text></svg>')


def new_case(recording: str | Path, cases_dir: str | Path, case_id: str | None = None, title: str | None = None,
             conditions: dict | None = None, topic_map: str | Path | None = None) -> Path:
    """Create a case from a recording. `conditions` overrides the part properties read from metadata."""
    rec = read_mcap(recording, topic_map)
    md = rec.metadata
    inc = find_incident(rec)
    raw = Path(recording).read_bytes()
    cid = case_id or f"case-{hashlib.sha256(raw).hexdigest()[:8]}"
    d = Path(cases_dir) / cid
    d.mkdir(parents=True, exist_ok=True)
    c = conditions or {}
    try:
        cond = {"friction": float(c.get("friction", md["part_friction_estimate"])),
                "mass": float(c.get("mass", md["part_mass_kg"])),
                "half_size": float(c.get("half_size", md["half_size_m"])),
                "ik_noise": float(c.get("ik_noise", md.get("joint_noise_rad", 0.0))),
                "seed": int(c.get("seed", md.get("seed", 0)))}
    except KeyError as e:
        raise ValueError(f"recording metadata lacks {e}; pass it explicitly (e.g. --friction, --mass, --half-size)") from None
    clip = clip_video(rec, inc.t - 2.5, inc.t + 1.5, d / "clip.mp4")
    half = cond["half_size"]
    (d / "timeline.svg").write_text(_timeline_svg(rec, inc, half))
    case = {
        "id": cid,
        "title": title or f"{inc.kind.replace('_', ' ').capitalize()}: {md.get('part', 'part')} at {md.get('cell', 'unknown cell')}",
        "created": _now(),
        "source": {"recording": Path(recording).name, "sha256": hashlib.sha256(raw).hexdigest(),
                   "origin": md.get("source", "unknown"), "recorded_at": md.get("recorded_at", "")},
        "context": {k: md.get(k, "") for k in ("cell", "robot", "gripper", "software_version", "part")},
        "incident": {"t": round(inc.t, 2), "kind": inc.kind, "description": inc.description},
        "conditions": cond,
        "clip": "clip.mp4" if clip else None,
        "evidence": [{"kind": "recording", "at": _now(), "summary": inc.description,
                      "note": "Shows what happened. It cannot show what a changed controller would have done."}],
    }
    _save(d, case)
    return d


def _variations(cond: dict, n: int, space: dict | None) -> list[tuple[int, SceneParams]]:
    """The recorded conditions, plus n nearby variations (measurements are never exact)."""
    rng = np.random.default_rng(cond["seed"] + 7919)
    out = [(cond["seed"], SceneParams(cond["friction"], cond["mass"], cond["half_size"], cond["ik_noise"]))]
    for _ in range(n):
        f = cond["friction"] * math.exp(rng.normal(0, 0.12))
        m = cond["mass"] * math.exp(rng.normal(0, 0.08))
        h = cond["half_size"] * (1 + rng.normal(0, 0.05))
        q = max(0.0, cond["ik_noise"] * (1 + rng.normal(0, 0.3)))
        if space:  # stay inside what the robot model supports
            clamp = lambda v, k: float(min(max(v, space[k][0]), space[k][1]))
            f, m, h, q = clamp(f, "friction"), clamp(m, "mass"), clamp(h, "half_size"), clamp(q, "ik_noise")
        out.append((int(rng.integers(0, 2**31 - 1)), SceneParams(f, m, h, q)))
    return out


def _run(ctrl, scen, workers):
    from .compare import run_any
    with _pool(workers) as pool:
        return pool.starmap(run_any, [(p, s, ctrl) for s, p in scen])


def _space(ctrl):
    from .sampling import PARAM_SPACE
    from .so101 import SO101_SPACE, So101Config
    return SO101_SPACE if isinstance(ctrl, So101Config) else PARAM_SPACE


def reproduce(case_dir, config: str | Path, n: int = 20, workers: int = 4) -> dict:
    """Does simulation recreate the incident at the recorded conditions and nearby?"""
    from . import config as cfgmod
    case = _load(case_dir)
    ctrl, _ = cfgmod.load(config)
    scen = _variations(case["conditions"], n, _space(ctrl))
    rows = _run(ctrl, scen, workers)
    want = case["incident"]["kind"]
    exact = FAMILY.get(rows[0]["outcome"]) == want
    same = sum(FAMILY.get(r["outcome"]) == want for r in rows[1:])
    failed = sum(not r["success"] for r in rows[1:])
    # Reproduced = the same failure at the recorded conditions, and most nearby variations fail too
    # (often by a sibling mode: a weak grip slips at some conditions and drops at others).
    ok = exact and failed >= 0.5 * n
    from collections import Counter
    modes = ", ".join(f"{k} {v}" for k, v in Counter(r["outcome"] for r in rows[1:]).most_common())
    ev = {"kind": "reproduction", "at": _now(), "config": Path(config).name, "reproduced": bool(ok),
          "exact_outcome": rows[0]["outcome"], "variations": n, "variations_failed": int(failed),
          "variations_same_mode": int(same),
          "summary": (f"Simulation {'reproduced' if exact else 'did not reproduce'} the incident at the recorded "
                      f"conditions ({rows[0]['outcome']}). Nearby variations: {failed} of {n} fail ({modes}).")}
    case["evidence"].append(ev)
    _save(case_dir, case)
    return ev


def test_fix(case_dir, base: str | Path, head: str | Path, n: int = 20, workers: int = 4,
             pin: str | Path | None = None) -> dict:
    """Run the current and proposed controllers on the case and the same variations."""
    from . import config as cfgmod
    case = _load(case_dir)
    bctrl, _ = cfgmod.load(base)
    hctrl, _ = cfgmod.load(head)
    scen = _variations(case["conditions"], n, _space(hctrl))
    b, h = _run(bctrl, scen, workers), _run(hctrl, scen, workers)
    resolved = sum(not x["success"] and y["success"] for x, y in zip(b, h))
    still = sum(not x["success"] and not y["success"] for x, y in zip(b, h))
    broke = sum(x["success"] and not y["success"] for x, y in zip(b, h))
    reproduced = case["status"] in ("reproduced",) or any(e["kind"] == "reproduction" and e["reproduced"]
                                                          for e in case["evidence"])
    verified = bool(h[0]["success"] and still == 0 and broke == 0 and reproduced)
    ev = {"kind": "fix_test", "at": _now(), "base": Path(base).name, "head": Path(head).name, "verified": verified,
          "exact": {"base": b[0]["outcome"], "head": h[0]["outcome"]}, "variations": n + 1,
          "resolved": int(resolved), "still_failing": int(still), "newly_broken": int(broke),
          "base_success": int(sum(x["success"] for x in b)), "head_success": int(sum(y["success"] for y in h)),
          "summary": (f"{Path(head).name}: the recorded incident {'is fixed' if h[0]['success'] else 'still fails'} "
                      f"({b[0]['outcome']} → {h[0]['outcome']}). Across {n + 1} runs: {resolved} resolved, "
                      f"{still} still failing, {broke} newly broken.")
          + ("" if reproduced else " Simulation has not reproduced this incident, so this is not a verification.")}
    case["evidence"].append(ev)
    if pin:
        from . import failures as failmod
        c = case["conditions"]
        lib = Path(pin)
        if not any(f.id == case["id"] for f in failmod.load(lib)):
            failmod.append(lib, failmod.Pinned(case["id"], c["seed"], c["friction"], c["mass"], c["half_size"],
                                               c["ik_noise"], f"case: {case['title']}", case["incident"]["description"]))
            ev["pinned_to"] = str(lib)
    _save(case_dir, case)
    return ev


def add_evidence(case_dir, kind: str, result: str, note: str, by: str = "", metrics: dict | None = None) -> dict:
    if kind not in ("hardware", "outcome"):
        raise ValueError("kind must be 'hardware' (a supervised physical test) or 'outcome' (results after rollout)")
    if kind == "hardware" and result not in ("pass", "fail"):
        raise ValueError("hardware result must be 'pass' or 'fail'")
    case = _load(case_dir)
    ev = {"kind": kind, "at": _now(), "result": result, "by": by, "summary": note, "metrics": metrics or {}}
    case["evidence"].append(ev)
    _save(case_dir, case)
    return ev


# ---------- pages ----------

_CSS = """:root{--bg:#08090b;--surface:#101318;--raised:#171c23;--line:#2b343f;--ink:#fafafa;--muted:#aaaab0;--accent:#9ab0c7;
--good:#5fb98a;--warn:#d9a84a;--bad:#e2665c}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 system-ui,sans-serif;padding:24px 16px}main{max-width:980px;margin:0 auto}a{color:var(--accent)}
h1{font-size:26px;letter-spacing:-.03em;margin:4px 0 6px}h2{font-size:13px;color:var(--muted);text-transform:uppercase;
letter-spacing:.07em;margin:26px 0 10px}.muted{color:var(--muted)}.pill{display:inline-block;padding:2px 10px;border-radius:99px;
border:1px solid currentColor;font-size:12px;font-weight:600}.s-open,.s-not{color:var(--warn)}.s-rep{color:var(--accent)}
.s-fix,.s-hw,.s-out{color:var(--good)}.grid{display:grid;grid-template-columns:1.3fr 1fr;gap:16px}.card{background:var(--surface);
border:1px solid var(--line);border-radius:8px;padding:14px}video,svg{width:100%;border-radius:6px;display:block}table{width:100%;
border-collapse:collapse;font-size:14px}td{padding:6px 0;border-bottom:1px solid var(--line);vertical-align:top}td:first-child{color:var(--muted);
width:42%}ol{margin:0;padding-left:20px}li{margin:0 0 12px}.k{font:600 12px ui-monospace,monospace;color:var(--accent)}
.badge{font-size:11px;padding:1px 7px;border-radius:99px;background:var(--raised);color:var(--muted);margin-left:6px}
.warn{border-left:3px solid var(--warn);padding:10px 12px;background:var(--raised);border-radius:0 6px 6px 0;margin:12px 0;color:var(--muted)}
code{font:12px ui-monospace,monospace;background:var(--raised);padding:2px 5px;border-radius:4px}footer{color:var(--muted);font-size:13px;margin-top:24px}
@media(max-width:700px){.grid{grid-template-columns:1fr}}"""

_STATUS_CLASS = {"open": "s-open", "not reproduced": "s-not", "reproduced": "s-rep", "fix verified (simulation)": "s-fix",
                 "hardware tested": "s-hw", "outcome recorded": "s-out"}
_KIND = {"recording": "Recording", "reproduction": "Simulation: reproduce", "fix_test": "Simulation: test a fix",
         "hardware": "Hardware test", "outcome": "Outcome after rollout"}


def _next_steps(case: dict, st: str) -> str:
    e = html.escape
    steps = {
        "open": ("Reproduce it in simulation", "daedro case reproduce --case <case> --config <current controller>"),
        "not reproduced": ("Simulation can't recreate this incident, so it can't verify a fix. Test fixes on hardware, "
                           "under supervision", "daedro case evidence --case <case> --kind hardware --result pass|fail --note ..."),
        "reproduced": ("Test a proposed fix against the case and nearby variations",
                       "daedro case test --case <case> --base <current> --head <proposed>"),
        "fix verified (simulation)": ("Run a supervised hardware trial before rolling out",
                                      "daedro case evidence --case <case> --kind hardware --result pass|fail --note ..."),
        "hardware tested": ("After rollout, record what changed on the floor",
                            "daedro case evidence --case <case> --kind outcome --result improved|no change|worse --note ..."),
    }
    if st not in steps:
        return ""
    what, cmd = steps[st]
    return (f"<p class='muted' style='margin:14px 0 4px'><b style='color:var(--ink)'>Next step:</b> {e(what)}.</p>"
            f"<code>{e(cmd)}</code>")


def render_html(case: dict, case_dir=None) -> str:
    e = html.escape
    st = status(case)
    ctx = case["context"]
    c = case["conditions"]
    rows = "".join(f"<tr><td>{e(k)}</td><td>{e(str(v))}</td></tr>" for k, v in [
        ("Cell", ctx.get("cell")), ("Robot", ctx.get("robot")), ("Gripper", ctx.get("gripper")),
        ("Software", ctx.get("software_version")), ("Part", ctx.get("part")),
        ("Part mass", f"{c['mass']:.2f} kg"), ("Part size", f"{2 * c['half_size'] * 100:.1f} cm"),
        ("Friction (estimate)", f"{c['friction']:.2f}"), ("Recording", case["source"]["recording"]),
        ("Recording origin", case["source"]["origin"])])
    ev = []
    for x in case["evidence"]:
        extra = ""
        if x["kind"] == "fix_test":
            extra = (f"<br><span class='muted'>{e(x['base'])}: {x['base_success']}/{x['variations']} succeed → "
                     f"{e(x['head'])}: {x['head_success']}/{x['variations']}</span>")
        if x.get("metrics"):
            extra = "<br><span class='muted'>" + " · ".join(f"{e(k)}: {e(str(v))}" for k, v in x["metrics"].items()) + "</span>"
        tag = ""
        if x["kind"] == "fix_test":
            tag = "<span class='badge'>verified in simulation</span>" if x["verified"] else "<span class='badge'>not verified</span>"
        if x["kind"] == "hardware":
            tag = f"<span class='badge'>{e(x['result'])}</span>"
        who = f" · {e(x['by'])}" if x.get("by") else ""
        ev.append(f"<li><span class='k'>{e(_KIND[x['kind']])}</span>{tag} <span class='muted'>{e(x['at'])}{who}</span>"
                  f"<br>{e(x['summary'])}{extra}</li>")
    origin_warn = ""
    if "example" in case["source"]["origin"] or "simulation" in case["source"]["origin"]:
        origin_warn = ("<p class='warn'>Example case. The recording was generated from Daedro's simulation in the same "
                       "format a real cell would log, because we don't have customer recordings yet. Cell, part and "
                       "people are illustrative.</p>")
    clip = (f"<video src='clip.mp4' controls muted loop playsinline></video>" if case.get("clip")
            else "<p class='muted'>No camera frames in this recording.</p>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(case['title'])} · Daedro case</title><style>{_CSS}</style></head><body><main>
<p class="muted" style="margin:0"><a href="../">Case library</a> · {e(case['id'])}</p>
<h1>{e(case['title'])}</h1>
<p><span class="pill {_STATUS_CLASS.get(st, 's-open')}">{e(st)}</span></p>
{origin_warn}
<div class="grid"><div class="card"><h2 style="margin-top:0">What happened · {case['incident']['t']:.1f}s</h2>{clip}
<p>{e(case['incident']['description'])}</p></div>
<div class="card"><h2 style="margin-top:0">Context</h2><table>{rows}</table></div></div>
<h2>Timeline</h2><div class="card">{(Path(case_dir) / 'timeline.svg').read_text() if case_dir and (Path(case_dir) / 'timeline.svg').exists() else ''}</div>
<h2>Evidence</h2><div class="card"><ol>{''.join(ev)}</ol>{_next_steps(case, st)}</div>
<footer>A recording shows what happened; it cannot show what a changed controller would have done. A fix is
"verified in simulation" only when simulation reproduced the incident, and that is not hardware validation.</footer>
</main></body></html>"""


def render_library(cases_dir) -> Path:
    e = html.escape
    d = Path(cases_dir)
    cases = sorted((json.loads(p.read_text()) for p in d.glob("*/case.json")), key=lambda c: c["created"], reverse=True)
    rows = "".join(
        f"<tr><td><a href='{e(c['id'])}/'>{e(c['title'])}</a><br><span class='muted'>{e(c['incident']['description'])}</span></td>"
        f"<td>{e(c['context'].get('cell', ''))}</td><td>{e(c['context'].get('software_version', ''))}</td>"
        f"<td><span class='pill {_STATUS_CLASS.get(c['status'], 's-open')}'>{e(c['status'])}</span></td></tr>" for c in cases)
    (d / "index.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Case library · Daedro</title><style>{_CSS}
td{{padding:10px 8px 10px 0}}td:first-child{{width:auto;color:var(--ink)}}</style></head><body><main>
<p class="muted" style="margin:0">Daedro</p><h1>Case library</h1>
<p class="muted">Every incident your team investigated, with its evidence. When an engineer leaves or a new cell comes online, this is what the next person inherits.</p>
<div class="card" style="overflow-x:auto"><table><tr><td class="muted">Case</td><td class="muted">Cell</td><td class="muted">Software</td><td class="muted">Status</td></tr>{rows}</table></div>
</main></body></html>""")
    return d / "index.html"
