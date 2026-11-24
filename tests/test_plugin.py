import shutil
import subprocess
from pathlib import Path

from daedro import config as cfgmod
from daedro.cli import main
from daedro.compare import compare

EX = Path(__file__).resolve().parents[1] / "examples" / "custom_controller"


def _small(tmp_path, body_extra=""):
    shutil.copy(EX / "pick.py", tmp_path / "pick.py")
    p = tmp_path / "daedro.toml"
    p.write_text('[controller]\nmodule = "pick.py"\nclass = "WaypointPick"\n' + body_extra +
                 '[suite]\nn = 4\nseed = 1\n[suite.envelope]\nfriction = [0.6, 1.2]\nmass = [0.05, 0.3]\n'
                 'half_size = [0.015, 0.025]\nik_noise = [0.0, 0.002]\n')
    return p


def test_custom_controller_succeeds_on_easy_scenarios(tmp_path):
    ctrl, suite = cfgmod.load(_small(tmp_path))
    rows = compare(ctrl, ctrl, suite, workers=2).head
    assert all(r["success"] for r in rows), [r["outcome"] for r in rows]


def test_crashing_controller_is_reported_not_raised(tmp_path):
    (tmp_path / "bad.py").write_text("class Bad:\n    def reset(self, obs): pass\n    def act(self, obs): raise RuntimeError('boom')\n")
    p = tmp_path / "bad.toml"
    p.write_text('[controller]\nmodule = "bad.py"\nclass = "Bad"\n[suite]\nn = 2\n')
    ctrl, suite = cfgmod.load(p)
    rows = compare(ctrl, ctrl, suite, workers=1).head
    assert {r["outcome"] for r in rows} == {"controller_error"}


def test_ci_catches_a_code_change_on_a_branch(tmp_path, monkeypatch):
    git = lambda *a: subprocess.check_call(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=tmp_path,
                                           stdout=subprocess.DEVNULL)
    _small(tmp_path)
    git("init", "-q", "-b", "main"); git("add", "."); git("commit", "-qm", "base")
    git("checkout", "-qb", "pr")
    code = (tmp_path / "pick.py").read_text().replace("close_early_s=0.0", "close_early_s=0.35")
    (tmp_path / "pick.py").write_text(code)  # toml untouched: only the code changes
    monkeypatch.chdir(tmp_path)
    rc = main(["ci", "--base-ref", "main", "--fail-on", "0", "--workers", "2"])
    report = (tmp_path / "daedro-report.md").read_text()
    assert rc == 1 and "Regression detected" in report or "regressed" in report
    assert "code_sha256" in report  # the report shows the code itself changed
