## Daedro regression report: `main` → `gentle-grip`

🔴 **Regression detected.** 45 scenarios that passed on `main` fail on `gentle-grip`.

| | Success rate | 95% CI |
|---|---|---|
| `main` (base) | 70/100 = 70.0% | 60.4%–78.1% |
| `gentle-grip` (head) | 28/100 = 28.0% | 20.1%–37.5% |

Paired on identical scenarios: **45 regressed**, **3 fixed**, 52 unchanged. Exact McNemar p = 1.31e-10.

**What changed in the controller**

| Parameter | Base | Head |
|---|---|---|
| `jaw_close` | -0.17 | 0.1 |

**Outcomes**

| Outcome | Base | Head | Δ |
|---|---|---|---|
| success | 70 | 28 | -42 |
| slip_on_lift | 4 | 53 | +49 |
| drop_in_transit | 1 | 3 | +2 |
| misplaced | 25 | 16 | -9 |

**Where the regressions cluster** (share of base-passing scenarios that regressed, by quarter of the envelope)

| Parameter | Q1 | Q2 | Q3 | Q4 |
|---|---|---|---|---|
| `half_size` | 0.009–0.01: **100%** | 0.01–0.011: **94%** | 0.011–0.012: **44%** | 0.012–0.013: 12% |
| `ik_noise` | 0–2.5e-05: **63%** | 2.5e-05–5e-05: **55%** | 5e-05–7.5e-05: **59%** | 7.5e-05–0.0001: **86%** |
| `friction` | 0.25–0.37: **67%** | 0.37–0.548: **60%** | 0.548–0.811: **67%** | 0.811–1.2: **64%** |
| `mass` | 0.01–0.0197: **67%** | 0.0197–0.0387: **65%** | 0.0387–0.0762: **59%** | 0.0762–0.15: **67%** |

**Regressed scenarios** (showing 10 of 45)

| # | Conditions | Head outcome | Reproduce |
|---|---|---|---|
| 13 | μ=0.48 · m=0.14 kg · size=1.9 cm · noise=0.000 rad | slip_on_lift | `daedro repro --config examples/so101/daedro.toml --scenario 13` |
| 24 | μ=0.26 · m=0.13 kg · size=2.3 cm · noise=0.000 rad | drop_in_transit | `daedro repro --config examples/so101/daedro.toml --scenario 24` |
| 99 | μ=0.36 · m=0.12 kg · size=2.0 cm · noise=0.000 rad | slip_on_lift | `daedro repro --config examples/so101/daedro.toml --scenario 99` |
| 46 | μ=0.80 · m=0.12 kg · size=2.4 cm · noise=0.000 rad | misplaced | `daedro repro --config examples/so101/daedro.toml --scenario 46` |
| 0 | μ=0.78 · m=0.11 kg · size=2.0 cm · noise=0.000 rad | slip_on_lift | `daedro repro --config examples/so101/daedro.toml --scenario 0` |
| 69 | μ=1.00 · m=0.11 kg · size=2.0 cm · noise=0.000 rad | slip_on_lift | `daedro repro --config examples/so101/daedro.toml --scenario 69` |
| 53 | μ=0.65 · m=0.11 kg · size=2.2 cm · noise=0.000 rad | slip_on_lift | `daedro repro --config examples/so101/daedro.toml --scenario 53` |
| 44 | μ=0.98 · m=0.10 kg · size=1.9 cm · noise=0.000 rad | slip_on_lift | `daedro repro --config examples/so101/daedro.toml --scenario 44` |
| 29 | μ=0.25 · m=0.09 kg · size=2.1 cm · noise=0.000 rad | slip_on_lift | `daedro repro --config examples/so101/daedro.toml --scenario 29` |
| 98 | μ=0.31 · m=0.08 kg · size=2.2 cm · noise=0.000 rad | slip_on_lift | `daedro repro --config examples/so101/daedro.toml --scenario 98` |

🎬 **Side-by-side replays** of 2 regressed scenario(s) (#13, #24): saved to the preview folder for this run.

<details markdown="1"><summary>Scenario suite and environment</summary>

- Suite: LHS, n=100, seed=5; both versions ran the identical scenarios.
- Declared operating envelope: `friction` 0.25–1.2; `half_size` 0.009–0.013; `ik_noise` 0–0.0001; `mass` 0.01–0.15
- MuJoCo 4.0.1 · SO-101 (MuJoCo Menagerie eea4c74), preview support · scripted pick-and-place, 2 cm success radius

</details>

> ⚠️ **Simulation only.** These results come from a MuJoCo model, not hardware. A pass here does not guarantee real-world performance or safety; a regression here is a lead to investigate, not proof of a hardware failure.
