import numpy as np
import pytest

from daedro.episode import run_episode
from daedro.sampling import NAMES, PARAM_SPACE, lhs_unit, sample
from daedro.scene import SceneParams


def test_lhs_one_point_per_stratum():
    n = 50
    u = lhs_unit(n, np.random.default_rng(0))
    for j in range(len(NAMES)):
        assert sorted(np.floor(u[:, j] * n).astype(int)) == list(range(n))


def test_samples_within_declared_ranges():
    for method in ("random", "lhs"):
        for _, p in sample(method, 200, 1):
            for name in NAMES:
                lo, hi, _ = PARAM_SPACE[name]
                assert lo <= getattr(p, name) <= hi


def test_sampling_is_seeded():
    assert sample("lhs", 20, 5) == sample("lhs", 20, 5)
    assert sample("lhs", 20, 5) != sample("lhs", 20, 6)


def test_episode_is_reproducible():
    p = SceneParams(friction=0.4, mass=0.6, half_size=0.02, ik_noise=0.02)
    assert run_episode(p, 123).to_dict() == run_episode(p, 123).to_dict()


def test_nominal_case_succeeds():
    r = run_episode(SceneParams(friction=1.0, mass=0.2, half_size=0.02, ik_noise=0.0), 0)
    assert r.outcome == "success", r


@pytest.mark.parametrize("mass", [1.5, 2.0])
def test_slippery_heavy_object_is_not_carried(mass):
    # Coulomb check: 2 * mu * N = 2 * 0.05 * 35 N = 3.5 N < m * g (14.7 N at 1.5 kg)
    r = run_episode(SceneParams(friction=0.05, mass=mass, half_size=0.02, ik_noise=0.0), 0)
    assert r.outcome in ("slip_on_lift", "drop_in_transit"), r


def test_campaign_is_bit_reproducible():
    from daedro.campaign import run_campaign
    a = run_campaign("lhs", 8, 11, workers=2)["metadata"]["rows_sha256"]
    b = run_campaign("lhs", 8, 11, workers=2)["metadata"]["rows_sha256"]
    assert a == b
