import json

import pytest

from daedro import case as cm
from daedro.cli import main
from daedro.recording import find_incident, read_mcap

BASE = ("[suite]\nn = 4\nseed = 1\n[suite.envelope]\nmass = [0.6, 1.0]\nfriction = [0.6, 1.2]\nik_noise = [0.0, 0.001]\n")


@pytest.fixture
def setup(tmp_path):
    (tmp_path / "weak.toml").write_text('[controller]\ngrip_force_n = "stock"\n' + BASE)  # ~2 N: can't lift heavy parts
    (tmp_path / "fix.toml").write_text("[controller]\ngrip_force_n = 70\n" + BASE)
    rec = tmp_path / "r.mcap"
    assert main(["record", "--config", str(tmp_path / "weak.toml"), "--scenario", "0", "--out", str(rec),
                 "--cell", "test cell", "--software", "v1", "--part", "block"]) == 0
    return tmp_path, rec


def test_recording_roundtrip_and_incident(setup):
    _, rec = setup
    r = read_mcap(rec)
    assert r.metadata["source"] == "simulation (example)" and r.metadata["cell"] == "test cell"
    assert len(r.t) > 10
    assert find_incident(r).kind == "never_lifted"


def test_case_loop_reproduce_fix_pin_and_status(setup, tmp_path):
    d, rec = setup
    assert main(["case", "new", "--recording", str(rec), "--cases-dir", str(d / "cases"), "--id", "c1"]) == 0
    c = d / "cases" / "c1"
    assert main(["case", "reproduce", "--case", str(c), "--config", str(d / "weak.toml"), "--n", "6",
                 "--workers", "2"]) == 0
    assert json.loads((c / "case.json").read_text())["status"] == "reproduced"
    assert main(["case", "test", "--case", str(c), "--base", str(d / "weak.toml"), "--head", str(d / "fix.toml"),
                 "--n", "6", "--workers", "2", "--pin", str(d / "daedro-failures.toml"), "--fail-unverified"]) == 0
    case = json.loads((c / "case.json").read_text())
    assert case["status"] == "fix verified (simulation)"
    assert "c1" in (d / "daedro-failures.toml").read_text()
    assert "Next step" in (c / "index.html").read_text() and (d / "cases" / "index.html").exists()
    with pytest.raises(ValueError):
        cm.add_evidence(c, "hardware", "maybe", "x")
    cm.add_evidence(c, "hardware", "pass", "supervised trial")
    assert json.loads((c / "case.json").read_text())["status"] == "hardware tested"


def test_fix_is_not_verified_without_reproduction(setup):
    d, rec = setup
    c = cm.new_case(rec, d / "cases", "c2")
    ev = cm.test_fix(c, d / "weak.toml", d / "fix.toml", n=4, workers=2)
    assert ev["verified"] is False and "not a verification" in ev["summary"]
