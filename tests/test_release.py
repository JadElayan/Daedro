import json

import pytest

from daedro import release as rel

BASE = ("[suite]\nn = 8\nseed = 1\n[suite.envelope]\nfriction = [0.5, 1.2]\nik_noise = [0.0, 0.002]\n")


def _files(tmp_path):
    (tmp_path / "v1.toml").write_text("[controller]\ngrip_force_n = 70\n" + BASE)
    (tmp_path / "v2.toml").write_text('[controller]\ngrip_force_n = "stock"\n' + BASE)  # ~2 N squeeze
    (tmp_path / "r.toml").write_text(
        '[release]\nname = "t"\nbase = "v1.toml"\nhead = "v2.toml"\n'
        '[[setup]]\nname = "heavy"\n[setup.envelope]\nmass = [0.4, 1.0]\n'
        '[[setup]]\nname = "no model"\nevidence = "none"\n')
    return tmp_path / "r.toml"


def test_release_gives_each_setup_a_verdict_and_guards_approval(tmp_path):
    rec = rel.run_release(_files(tmp_path), workers=2)
    v = {s["name"]: s["verdict"] for s in rec["setups"]}
    assert v == {"heavy": "blocked", "no model": "hardware"}
    out = rel.save(rec, tmp_path / "rec")
    assert (out / "index.html").read_text().count("Needs hardware test") >= 1
    with pytest.raises(ValueError, match="override"):
        rel.approve(out, "lead", ["heavy"])
    rel.approve(out, "lead", ["heavy"], note="override: supervised hardware test passed", handoff="deploy tool")
    saved = json.loads((out / "record.json").read_text())
    assert saved["approvals"][0]["by"] == "lead" and saved["handoffs"][0]["to"] == "deploy tool"
    with pytest.raises(ValueError, match="unknown setup"):
        rel.approve(out, "lead", ["nope"])
