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
html = (root / "site" / "template.html").read_text().replace("{{MARK}}", mark).replace("{{REPORT}}", report).replace("{{FORM}}", form)
(dist / "index.html").write_text(html)
shutil.copy(root / "brand" / "favicon.svg", dist / "favicon.svg")
for asset in ("Daedro-demo.mp4", "Daedro-demo-poster.jpg"):
    shutil.copy(root / "site" / asset, dist / asset)
print("built", dist / "index.html")
