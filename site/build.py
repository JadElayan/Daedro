"""Build the static site: inject the logo and the real demo report into the template.

    python site/build.py   ->  site/dist/index.html
The report is regenerated from examples/pick_place/report.md, so the page can't drift
from what `daedro compare` actually produced.
"""
import re, shutil
from pathlib import Path
import markdown

root = Path(__file__).resolve().parents[1]
dist = root / "site" / "dist"; dist.mkdir(parents=True, exist_ok=True)
mark = re.sub(r"<!--.*?-->\s*", "", (root / "brand" / "mark.svg").read_text(), flags=re.S)
mark = mark.replace('role="img" aria-label="Daedro"', 'aria-hidden="true"')
report = markdown.markdown((root / "examples" / "pick_place" / "report.md").read_text(), extensions=["tables", "md_in_html"])
form = Path(root / "site" / "form.html").read_text() if (root / "site" / "form.html").exists() else (
    '<p class="formnote">Email <b>hello@daedro.ai</b> (inbox not set up yet).</p>')
import json, html as _h
rec_dir = root / "examples" / "release" / "record"
rec = json.loads((rec_dir / "record.json").read_text())
_cls = {"ready": "ready", "blocked": "blocked", "review": "blocked", "hardware": "hw"}
_lbl = {"ready": "Ready", "blocked": "Blocked", "review": "Review", "hardware": "Needs hardware test"}
def _ev(s):
    if s["verdict"] == "hardware":
        return "No simulation model yet"
    return f"{s['regressed']} of {s['n']} scenarios regressed · success {s['base_success']} → {s['head_success']}"
rows = "".join(f"<tr><td>{_h.escape(s['name'])}</td><td><span class='v {_cls[s['verdict']]}'>{_lbl[s['verdict']]}</span></td>"
               f"<td>{_h.escape(_ev(s))}</td></tr>" for s in rec["setups"])
release_table = (f"<div class='release' role='region' aria-label='Release record summary' tabindex='0'><table>"
                 f"<thead><tr><th>Setup · {_h.escape(rec['release'])}</th><th>Verdict</th><th>Evidence (simulation)</th></tr></thead>"
                 f"<tbody>{rows}</tbody></table></div>")
html = ((root / "site" / "template.html").read_text().replace("{{MARK}}", mark).replace("{{REPORT}}", report)
        .replace("{{FORM}}", form).replace("{{RELEASE_TABLE}}", release_table))
(dist / "release").mkdir(exist_ok=True)
shutil.copy(rec_dir / "index.html", dist / "release" / "index.html")
(dist / "index.html").write_text(html)
shutil.copy(root / "brand" / "favicon.svg", dist / "favicon.svg")
for asset in ("Daedro-demo.mp4", "Daedro-demo-poster.jpg"):
    shutil.copy(root / "site" / asset, dist / asset)
print("built", dist / "index.html")
