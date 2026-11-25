"""Video previews: film base and head on the same scenario and put them side by side.

Rendering is off-screen (MuJoCo Renderer). On a machine with no GPU set MUJOCO_GL=egl
and install Mesa's EGL (apt: libegl1 libgl1); it renders in software at ~0.1 s/frame.
Videos are written with the system ffmpeg (H.264 MP4, plays in browsers and GitHub).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")

import mujoco
import numpy as np

FPS = 15
W, H = 480, 320


class Recorder:
    """Pass to run_episode / run_plugin_episode; collects frames at FPS."""

    def __init__(self, width: int = W, height: int = H):
        self.w, self.h = width, height
        self.frames: list[np.ndarray] = []
        self._r = None
        self._every = None
        self._k = 0
        self.cam = mujoco.MjvCamera()
        self.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        self.cam.lookat[:] = [0.5, 0.0, 0.12]  # front view: part, target and arm path all visible
        self.cam.distance, self.cam.azimuth, self.cam.elevation = 1.05, 180.0, -30.0

    def step(self, m: mujoco.MjModel, d: mujoco.MjData) -> None:
        if self._r is None:
            self._r = mujoco.Renderer(m, self.h, self.w)
            self._every = max(1, int(round(1.0 / (FPS * m.opt.timestep))))
        if self._k % self._every == 0:
            self._r.update_scene(d, camera=self.cam)
            self.frames.append(self._r.render().copy())
        self._k += 1

    def close(self):
        if self._r is not None:
            self._r.close()
            self._r = None


def _label(frame: np.ndarray, title: str, sub: str, ok: bool) -> np.ndarray:
    from PIL import Image, ImageDraw, ImageFont
    im = Image.fromarray(frame)
    dr = ImageDraw.Draw(im)
    try:
        f1, f2 = ImageFont.load_default(size=18), ImageFont.load_default(size=14)
    except TypeError:  # very old Pillow
        f1 = f2 = ImageFont.load_default()
    bar = (46, 125, 79) if ok else (180, 35, 24)
    dr.rectangle([0, 0, im.width, 44], fill=(20, 18, 15))
    dr.rectangle([0, 44, im.width, 47], fill=bar)
    dr.text((12, 4), title, fill=(242, 239, 234), font=f1)
    dr.text((12, 25), sub, fill=(200, 194, 186), font=f2)
    return np.asarray(im)


def side_by_side(left: Recorder, right: Recorder, left_title: str, right_title: str,
                 left_outcome: str, right_outcome: str, caption: str, out: Path) -> Path:
    """Write an MP4 with the two runs next to each other, padded to the same length."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found; install it to write videos")
    n = max(len(left.frames), len(right.frames))
    pad = lambda fr: fr + [fr[-1]] * (n - len(fr))
    L, R = pad(left.frames), pad(right.frames)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h = L[0].shape[1] * 2 + 8, L[0].shape[0]
    proc = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         "-crf", "26", str(out)], stdin=subprocess.PIPE)
    gap = np.full((h, 8, 3), 20, np.uint8)
    for i in range(n):
        a = _label(L[i], left_title, f"{left_outcome} · {caption}", left_outcome == "success")
        b = _label(R[i], right_title, f"{right_outcome} · {caption}", right_outcome == "success")
        proc.stdin.write(np.hstack([a, gap, b]).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    return out


def _replay(params, seed, ctrl, rec):
    from .compare import run_any
    from .so101 import So101Config
    if isinstance(ctrl, So101Config):  # small arm: frame it closer
        rec.cam.lookat[:] = [0.18, 0.0, 0.05]
        rec.cam.distance, rec.cam.azimuth, rec.cam.elevation = 0.55, 180.0, -32.0
    return run_any(params, seed, ctrl, rec)


def render_scenario(base_ctrl, head_ctrl, params, seed, idx, base_label, head_label, out: Path) -> dict:
    lb, lh = Recorder(), Recorder()
    rb, rh = _replay(params, seed, base_ctrl, lb), _replay(params, seed, head_ctrl, lh)
    cap = (f"#{idx}  mu={params.friction:.2f}  m={params.mass:.2f} kg  "
           f"size={2 * params.half_size * 100:.1f} cm")
    side_by_side(lb, lh, base_label, head_label, rb["outcome"], rh["outcome"], cap, out)
    lb.close(); lh.close()
    return {"scenario": idx, "file": Path(out).name, "base": rb["outcome"], "head": rh["outcome"]}


def render_previews(cmp, base_label: str, head_label: str, out_dir: Path, max_videos: int = 3) -> list[dict]:
    """Film the worst regressions (heaviest-mass first, matching the report order)."""
    from .sampling import sample
    scen = sample(cmp.suite.method, cmp.suite.n, cmp.suite.seed, cmp.suite.space())
    regs = sorted(cmp.regressions, key=lambda t: -t[1]["mass"])[:max_videos]
    out = []
    for b, h in regs:
        i = h["scenario"]
        seed, params = scen[i]
        v = render_scenario(cmp.base_cfg, cmp.head_cfg, params, seed, i, base_label, head_label,
                            Path(out_dir) / f"scenario-{i}.mp4")
        if (v["base"], v["head"]) != (b["outcome"], h["outcome"]):
            raise RuntimeError(f"replay of scenario {i} was not deterministic: {v} vs {b['outcome']}/{h['outcome']}")
        out.append(v)
    _write_index(out, base_label, head_label, Path(out_dir))
    return out


def _write_index(videos, base_label, head_label, out_dir: Path):
    rows = "\n".join(
        f'<figure><video src="{v["file"]}" controls loop muted playsinline></video>'
        f'<figcaption>Scenario #{v["scenario"]}: <b>{base_label}</b> {v["base"]} → <b>{head_label}</b> {v["head"]}'
        f'</figcaption></figure>' for v in videos)
    (out_dir / "index.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Daedro preview</title>
<style>body{{margin:0;background:#0E0D0C;color:#F2EFEA;font:16px/1.5 system-ui,sans-serif;padding:24px}}
h1{{font-size:22px;margin:0 0 4px}}p{{color:#A39C92;margin:0 0 24px}}figure{{margin:0 0 28px}}
video{{width:100%;max-width:980px;border-radius:10px;display:block}}figcaption{{color:#A39C92;margin-top:8px}}</style>
</head><body><h1>Daedro preview: {base_label} → {head_label}</h1>
<p>Side-by-side replays of the regressed scenarios. Simulation only (MuJoCo), not hardware.</p>
{rows}</body></html>""")
