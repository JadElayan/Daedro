import pytest

from daedro import config as cfgmod
from daedro.compare import compare, mcnemar_exact, render_markdown, wilson
from daedro.episode import ControllerConfig


def test_mcnemar_exact_matches_hand_calculation():
    assert mcnemar_exact(7, 0) == pytest.approx(2 / 2**7)  # all 7 discordant pairs one way
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 5) == 1.0


def test_wilson_bounds():
    lo, hi = wilson(194, 200)
    assert 0.93 < lo < 0.94 and 0.98 < hi < 0.99


def _toml(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body)
    return p


def test_config_rejects_unknown_keys(tmp_path):
    with pytest.raises(ValueError, match="unknown"):
        cfgmod.load(_toml(tmp_path, "a.toml", "[controller]\nsped = 1.2\n"))


def test_config_rejects_envelope_outside_supported_range(tmp_path):
    with pytest.raises(ValueError, match="within the supported range"):
        cfgmod.load(_toml(tmp_path, "a.toml", "[suite.envelope]\nmass = [0.01, 5.0]\n"))


def test_identical_configs_have_no_regressions(tmp_path):
    ctrl, suite = cfgmod.load(_toml(tmp_path, "a.toml", "[suite]\nn = 6\nseed = 3\n"))
    cmp = compare(ctrl, ctrl, suite, workers=2)
    assert cmp.regressions == [] and cmp.fixes == []
    assert [r["scenario"] for r in cmp.base] == list(range(6))
    assert "No regressions" in render_markdown(cmp, "a", "b", "a.toml")


def test_stock_gripper_regresses_against_70n(tmp_path):
    _, suite = cfgmod.load(_toml(tmp_path, "a.toml",
        "[suite]\nn = 6\nseed = 1\n[suite.envelope]\nmass = [0.3, 1.0]\nfriction = [0.5, 1.2]\nik_noise = [0.0, 0.002]\n"))
    cmp = compare(ControllerConfig(), ControllerConfig(grip_force_n=None), suite, workers=2)
    assert len(cmp.regressions) >= 4  # the ~2 N stock gripper can't carry 0.3-1 kg
