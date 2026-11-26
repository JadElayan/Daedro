"""Outcome tracking from the recordings a fleet already logs.

Point Daedro at a folder of recordings (Daedro JSON or ROS 2 MCAP). For each one it detects
success or the incident type, groups by cell and software version, and compares versions:

    daedro outcomes --recordings logs/ --before "pick-cycle v2.5" --after "pick-cycle v2.5.1" --cell "Site B · cell 2"

Before/after picks are different picks (not paired), so the comparison uses Fisher's exact
test plus Wilson intervals. The data source (real floor logs vs example simulation) is read
from each recording's metadata and carried into every summary, so simulated example data is
never presented as floor data.
"""
from __future__ import annotations

import html
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from .compare import wilson
from .recording import find_incident, read_mcap


def scan(folder: str | Path, topic_map: str | Path | None = None) -> list[dict]:
    rows = []
    for p in sorted(Path(folder).rglob("*.mcap")):
        try:
            rec = read_mcap(p, topic_map)
            inc = find_incident(rec)
        except Exception as e:  # one bad file shouldn't hide the rest
            rows.append({"file": p.name, "error": f"{type(e).__name__}: {e}"})
            continue
        md = rec.metadata
        rows.append({"file": p.name, "cell": md.get("cell", "unknown"), "software": md.get("software_version", "unknown"),
                     "source": md.get("source", "unknown"), "outcome": inc.kind, "success": inc.kind == "none",
                     "t": round(inc.t, 2)})
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for r in rows:
        if "error" not in r:
            groups[(r["cell"], r["software"])].append(r)
    out = []
    for (cell, sw), rs in sorted(groups.items()):
        k, n = sum(r["success"] for r in rs), len(rs)
        lo, hi = wilson(k, n)
        out.append({"cell": cell, "software": sw, "n": n, "success": k, "rate": k / n, "ci": [lo, hi],
                    "incidents": dict(Counter(r["outcome"] for r in rs if not r["success"])),
                    "sources": sorted({r["source"] for r in rs})})
    return out


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact test for [[a, b], [c, d]] (successes/failures before, after)."""
    n1, n2, k = a + b, c + d, a + c
    n = n1 + n2
    def p(x):
        return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n, k)
    obs = p(a)
    lo, hi = max(0, k - n2), min(k, n1)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs * (1 + 1e-9)))


def compare_versions(rows: list[dict], before: str, after: str, cell: str | None = None) -> dict:
    sel = [r for r in rows if "error" not in r and (cell is None or r["cell"] == cell)]
    b = [r for r in sel if r["software"] == before]
    a = [r for r in sel if r["software"] == after]
    if not b or not a:
        raise ValueError(f"need recordings for both versions (found {len(b)} for {before!r}, {len(a)} for {after!r})")
    kb, ka = sum(r["success"] for r in b), sum(r["success"] for r in a)
    p = fisher_exact(kb, len(b) - kb, ka, len(a) - ka)
    rb, ra = kb / len(b), ka / len(a)
    verdict = ("improved" if ra > rb else "worse") if p < 0.05 else "no clear change"
    sources = sorted({r["source"] for r in b + a})
    example = any("example" in s or "simulation" in s for s in sources)
    summary = (f"{cell or 'All cells'}: {before} {kb}/{len(b)} succeeded ({rb:.0%}) → {after} {ka}/{len(a)} ({ra:.0%}). "
               f"Fisher exact p = {p:.2g}: {verdict}."
               + (" Computed from example recordings generated in simulation, not floor data." if example else ""))
    return {"cell": cell, "before": before, "after": after, "n_before": len(b), "n_after": len(a),
            "success_before": kb, "success_after": ka, "p_value": p, "verdict": verdict, "sources": sources,
            "example_data": example, "summary": summary,
            "incidents_before": dict(Counter(r["outcome"] for r in b if not r["success"])),
            "incidents_after": dict(Counter(r["outcome"] for r in a if not r["success"]))}


def attach_to_case(case_dir, comparison: dict) -> dict:
    """Record the comparison as outcome evidence on a case (computed, with its data source)."""
    from . import case as cm
    c = comparison
    res = {"improved": "improved", "worse": "worse", "no clear change": "no change"}[c["verdict"]]
    metrics = {f"success {c['before']}": f"{c['success_before']}/{c['n_before']}",
               f"success {c['after']}": f"{c['success_after']}/{c['n_after']}", "p-value": f"{c['p_value']:.2g}",
               "data": ", ".join(c["sources"])}
    return cm.add_evidence(case_dir, "outcome", res, c["summary"], by="daedro outcomes (computed)", metrics=metrics)


def render_html(rows: list[dict], comparisons: list[dict], title: str = "Outcomes") -> str:
    from .case import _CSS
    e = html.escape
    summ = summarize(rows)
    example = any("example" in s or "simulation" in s for g in summ for s in g["sources"])
    trs = "".join(f"<tr><td>{e(g['cell'])}</td><td>{e(g['software'])}</td><td>{g['success']}/{g['n']} ({g['rate']:.0%})</td>"
                  f"<td>{g['ci'][0]:.0%}–{g['ci'][1]:.0%}</td><td>{e(', '.join(f'{k} {v}' for k, v in g['incidents'].items()) or '—')}</td></tr>"
                  for g in summ)
    cmp_html = "".join(
        f"<div class='card' style='margin-bottom:12px'><span class='pill {'s-fix' if c['verdict'] == 'improved' else 's-not'}'>"
        f"{e(c['verdict'])}</span><p>{e(c['summary'])}</p></div>" for c in comparisons)
    errors = [r for r in rows if "error" in r]
    err = (f"<p class='warn'>{len(errors)} recording(s) couldn't be read: "
           + "; ".join(e(f"{r['file']}: {r['error']}") for r in errors[:5]) + "</p>") if errors else ""
    warn = ("<p class='warn'>Example data: these recordings were generated in simulation, in the format a cell logs. "
            "They demonstrate the pipeline; they are not floor results.</p>") if example else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} · Daedro</title><style>{_CSS} td{{padding:8px 10px 8px 0}} td:first-child{{width:auto;color:var(--ink)}}</style></head><body><main>
<p class="muted" style="margin:0"><a href="../">Daedro</a></p><h1>{e(title)}</h1>
<p class="muted">Success and incident rates per cell and software version, detected automatically from {len(rows)} recordings.</p>
{warn}{err}<h2>Before and after</h2>{cmp_html or "<p class='muted'>No comparison requested.</p>"}
<h2>By cell and version</h2><div class="card" style="overflow-x:auto"><table>
<tr><td class="muted">Cell</td><td class="muted">Software</td><td class="muted">Succeeded</td><td class="muted">95% CI</td><td class="muted">Incidents</td></tr>
{trs}</table></div>
<footer>Outcomes describe what happened in the recordings. Rates from small samples are uncertain; read the intervals.</footer>
</main></body></html>"""
