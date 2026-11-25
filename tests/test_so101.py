import pytest

from daedro import config as cfgmod
from daedro.scene import SceneParams
from daedro.so101 import So101Config, run_episode


def test_easy_part_is_picked_and_placed():
    r = run_episode(SceneParams(1.0, 0.03, 0.012, 0.0), 0)
    assert r["success"], r


def test_slippery_heavy_part_is_not_carried():
    r = run_episode(SceneParams(0.1, 0.2, 0.011, 0.0), 0)
    assert r["outcome"] in ("slip_on_lift", "drop_in_transit"), r


def test_episode_is_deterministic():
    p = SceneParams(0.5, 0.08, 0.011, 0.0)
    assert run_episode(p, 3) == run_episode(p, 3)


def test_config_selects_so101_and_validates_its_envelope(tmp_path):
    ok = tmp_path / "a.toml"
    ok.write_text('[controller]\nrobot = "so101"\njaw_close = 0.1\n[suite]\nn = 2\n')
    ctrl, suite = cfgmod.load(ok)
    assert isinstance(ctrl, So101Config) and ctrl.jaw_close == 0.1
    assert suite.space()["mass"][1] <= 0.2
    bad = tmp_path / "b.toml"
    bad.write_text('[controller]\nrobot = "so101"\n[suite.envelope]\nmass = [0.05, 2.0]\n')
    with pytest.raises(ValueError, match="supported range"):
        cfgmod.load(bad)
    unknown = tmp_path / "c.toml"
    unknown.write_text('[controller]\nrobot = "ur5"\n')
    with pytest.raises(ValueError, match="unknown robot"):
        cfgmod.load(unknown)
