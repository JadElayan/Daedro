import os
import shutil

import numpy as np
import pytest

os.environ.setdefault("MUJOCO_GL", "egl")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def test_side_by_side_writes_mp4(tmp_path):
    from daedro.video import Recorder, side_by_side
    a, b = Recorder(), Recorder()
    a.frames = [np.full((64, 96, 3), 90, np.uint8)] * 5
    b.frames = [np.full((64, 96, 3), 160, np.uint8)] * 3  # shorter: padded to match
    out = side_by_side(a, b, "main", "pr", "success", "never_lifted", "#1", tmp_path / "v.mp4")
    assert out.exists() and out.stat().st_size > 1000


def test_recorder_renders_the_scene():
    import mujoco
    from daedro.scene import SceneParams, build_model
    from daedro.video import Recorder
    try:
        m = build_model(SceneParams(1.0, 0.2, 0.02, 0.0), 70.0)
        d = mujoco.MjData(m)
        mujoco.mj_forward(m, d)
        r = Recorder(width=96, height=64)
        r.step(m, d)
    except Exception as e:  # no GL on this machine
        pytest.skip(f"off-screen rendering unavailable: {e}")
    assert r.frames and r.frames[0].shape == (64, 96, 3) and r.frames[0].std() > 1
    r.close()


def test_video_failure_does_not_lose_the_report(tmp_path, monkeypatch):
    import daedro.video
    from daedro.cli import main
    base = tmp_path / "b.toml"
    base.write_text("[suite]\nn = 4\nseed = 1\n[suite.envelope]\nmass = [0.3, 1.0]\nfriction = [0.5, 1.2]\nik_noise = [0.0, 0.002]\n")
    head = tmp_path / "h.toml"
    head.write_text('[controller]\ngrip_force_n = "stock"\n' + base.read_text())

    def boom(*a, **k):
        raise RuntimeError("no GL here")
    monkeypatch.setattr(daedro.video, "render_previews", boom)
    rc = main(["compare", "--base", str(base), "--head", str(head), "--report", str(tmp_path / "r.md"),
               "--videos", str(tmp_path / "v"), "--fail-on", "0", "--workers", "2"])
    report = (tmp_path / "r.md").read_text()
    assert rc == 1 and "Regression detected" in report or "regressed" in report
    assert "Videos unavailable" in report
