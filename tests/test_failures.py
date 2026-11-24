import shutil
from pathlib import Path

import pytest

from daedro import config as cfgmod
from daedro import failures as failmod
from daedro.cli import main
from daedro.compare import compare, render_markdown

EX = Path(__file__).resolve().parents[1] / "examples" / "custom_controller"


def test_roundtrip_and_duplicate_ids(tmp_path):
    lib = tmp_path / failmod.DEFAULT_FILE
    f = failmod.Pinned("a", 1, 0.5, 0.2, 0.02, 0.0, 'sim: "quoted"', "note")
    failmod.append(lib, f)
    assert failmod.load(lib)[0].source == 'sim: "quoted"'
    with pytest.raises(ValueError, match="already pinned"):
        failmod.append(lib, f)


def test_pinned_failure_that_comes_back_fails_the_gate(tmp_path):
    shutil.copy(EX / "pick.py", tmp_path / "pick.py")
    body = ('[suite]\nn = 2\nseed = 1\n[suite.envelope]\nfriction = [0.6, 1.2]\nmass = [0.05, 0.2]\n'
            'half_size = [0.03, 0.035]\nik_noise = [0.0, 0.001]\n')  # big parts: sampled scenarios still pass
    (tmp_path / "base.toml").write_text('[controller]\nmodule = "pick.py"\nclass = "WaypointPick"\n' + body)
    (tmp_path / "head.toml").write_text('[controller]\nmodule = "pick.py"\nclass = "WaypointPick"\n'
                                        'params = { close_early_s = 0.35 }\n' + body)
    assert main(["pin", "--config", str(tmp_path / "base.toml"), "--field", "cell 1", "--friction", "0.8",
                 "--mass", "0.2", "--half-size", "0.011", "--id", "tiny-part"]) == 0
    b, suite = cfgmod.load(tmp_path / "base.toml")
    h, _ = cfgmod.load(tmp_path / "head.toml")
    cmp = compare(b, h, suite, workers=2)
    assert [x["scenario"] for _, x in cmp.pinned_regressions()] == ["tiny-part"]
    assert "A known failure came back" in render_markdown(cmp, "main", "pr", "head.toml")
    rc = main(["compare", "--base", str(tmp_path / "base.toml"), "--head", str(tmp_path / "head.toml"),
               "--report", str(tmp_path / "r.md"), "--fail-on", "0", "--workers", "2"])
    assert rc == 1
