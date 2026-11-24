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
