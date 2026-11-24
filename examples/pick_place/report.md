## Daedro regression report: `main` → `faster-softer-grip`

🔴 **Regression detected.** 7 scenarios that passed on `main` fail on `faster-softer-grip`.

| | Success rate | 95% CI |
|---|---|---|
| `main` (base) | 194/200 = 97.0% | 93.6%–98.6% |
| `faster-softer-grip` (head) | 187/200 = 93.5% | 89.2%–96.2% |

Paired on identical scenarios: **7 regressed**, **0 fixed**, 193 unchanged. Exact McNemar p = 0.0156.

**What changed in the controller**

| Parameter | Base | Head |
|---|---|---|
| `speed` | 1.0 | 1.4 |
| `grip_force_n` | 70 | 40 |

**Outcomes**

| Outcome | Base | Head | Δ |
|---|---|---|---|
| success | 194 | 187 | -7 |
| slip_on_lift | 0 | 6 | +6 |
| drop_in_transit | 5 | 5 | +0 |
| misplaced | 1 | 2 | +1 |

**Where the regressions cluster** (share of base-passing scenarios that regressed, by quarter of the envelope)

| Parameter | Q1 | Q2 | Q3 | Q4 |
|---|---|---|---|---|
| `mass` | 0.05–0.106: 0% | 0.106–0.224: 0% | 0.224–0.473: 2% | 0.473–1: 14% |
| `friction` | 0.2–0.313: 11% | 0.313–0.49: 4% | 0.49–0.767: 0% | 0.767–1.2: 0% |
| `ik_noise` | 0–0.0025: 0% | 0.0025–0.005: 4% | 0.005–0.0075: 4% | 0.0075–0.01: 7% |
| `half_size` | 0.015–0.02: 6% | 0.02–0.025: 2% | 0.025–0.03: 4% | 0.03–0.035: 2% |

**Regressed scenarios** (showing 7 of 7)

| # | Conditions | Head outcome | Reproduce |
|---|---|---|---|
| 137 | μ=0.30 · m=0.94 kg · size=4.0 cm · noise=0.006 rad | drop_in_transit | `daedro repro --config examples/pick_place/daedro.toml --scenario 137` |
| 2 | μ=0.34 · m=0.84 kg · size=5.5 cm · noise=0.006 rad | misplaced | `daedro repro --config examples/pick_place/daedro.toml --scenario 2` |
| 87 | μ=0.26 · m=0.82 kg · size=3.1 cm · noise=0.004 rad | drop_in_transit | `daedro repro --config examples/pick_place/daedro.toml --scenario 87` |
| 58 | μ=0.32 · m=0.74 kg · size=5.2 cm · noise=0.008 rad | drop_in_transit | `daedro repro --config examples/pick_place/daedro.toml --scenario 58` |
| 196 | μ=0.22 · m=0.70 kg · size=3.5 cm · noise=0.004 rad | drop_in_transit | `daedro repro --config examples/pick_place/daedro.toml --scenario 196` |
| 156 | μ=0.22 · m=0.52 kg · size=6.5 cm · noise=0.008 rad | drop_in_transit | `daedro repro --config examples/pick_place/daedro.toml --scenario 156` |
| 22 | μ=0.21 · m=0.28 kg · size=3.5 cm · noise=0.010 rad | misplaced | `daedro repro --config examples/pick_place/daedro.toml --scenario 22` |

<details markdown="1"><summary>Scenario suite and environment</summary>

- Suite: LHS, n=200, seed=2026; both versions ran the identical scenarios.
- Declared operating envelope: `friction` 0.2–1.2; `half_size` 0.015–0.035; `ik_noise` 0–0.01; `mass` 0.05–1
- MuJoCo 4.0.1 · Franka Panda (MuJoCo Menagerie eea4c74) · scripted pick-and-place, 3 cm success radius

</details>

> ⚠️ **Simulation only.** These results come from a MuJoCo model, not hardware. A pass here does not guarantee real-world performance or safety; a regression here is a lead to investigate, not proof of a hardware failure.
