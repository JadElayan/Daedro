## Daedro regression report: `main` → `close-gripper-early`

🔴 **Regression detected.** 101 scenarios that passed on `main` fail on `close-gripper-early`.

| | Success rate | 95% CI |
|---|---|---|
| `main` (base) | 120/120 = 100.0% | 96.9%–100.0% |
| `close-gripper-early` (head) | 19/120 = 15.8% | 10.4%–23.4% |

Paired on identical scenarios: **101 regressed**, **0 fixed**, 19 unchanged. Exact McNemar p = 7.89e-31.

**What changed in the controller**

| Parameter | Base | Head |
|---|---|---|
| `params` | {} | {'close_early_s': 0.35} |

**Outcomes**

| Outcome | Base | Head | Δ |
|---|---|---|---|
| success | 120 | 19 | -101 |
| never_lifted | 0 | 101 | +101 |

**Where the regressions cluster** (share of base-passing scenarios that regressed, by quarter of the envelope)

| Parameter | Q1 | Q2 | Q3 | Q4 |
|---|---|---|---|---|
| `half_size` | 0.01–0.0163: **100%** | 0.0163–0.0225: **100%** | 0.0225–0.0288: **97%** | 0.0288–0.035: **40%** |
| `friction` | 0.3–0.424: **87%** | 0.424–0.6: **97%** | 0.6–0.849: **83%** | 0.849–1.2: **70%** |
| `ik_noise` | 0–0.00125: **93%** | 0.00125–0.0025: **90%** | 0.0025–0.00375: **77%** | 0.00375–0.005: **77%** |
| `mass` | 0.05–0.1: **87%** | 0.1–0.2: **90%** | 0.2–0.4: **80%** | 0.4–0.8: **80%** |

**Regressed scenarios** (showing 10 of 101)

| # | Conditions | Head outcome | Reproduce |
|---|---|---|---|
| 32 | μ=0.39 · m=0.79 kg · size=2.1 cm · noise=0.000 rad | never_lifted | `daedro repro --config examples/custom_controller/daedro.toml --scenario 32` |
| 109 | μ=0.69 · m=0.77 kg · size=4.8 cm · noise=0.001 rad | never_lifted | `daedro repro --config examples/custom_controller/daedro.toml --scenario 109` |
| 59 | μ=0.60 · m=0.76 kg · size=2.8 cm · noise=0.001 rad | never_lifted | `daedro repro --config examples/custom_controller/daedro.toml --scenario 59` |
| 83 | μ=0.89 · m=0.74 kg · size=2.4 cm · noise=0.001 rad | never_lifted | `daedro repro --config examples/custom_controller/daedro.toml --scenario 83` |
| 94 | μ=0.95 · m=0.73 kg · size=4.8 cm · noise=0.001 rad | never_lifted | `daedro repro --config examples/custom_controller/daedro.toml --scenario 94` |
| 64 | μ=0.96 · m=0.70 kg · size=4.7 cm · noise=0.004 rad | never_lifted | `daedro repro --config examples/custom_controller/daedro.toml --scenario 64` |
| 62 | μ=0.45 · m=0.69 kg · size=2.0 cm · noise=0.001 rad | never_lifted | `daedro repro --config examples/custom_controller/daedro.toml --scenario 62` |
| 46 | μ=0.32 · m=0.68 kg · size=2.9 cm · noise=0.005 rad | never_lifted | `daedro repro --config examples/custom_controller/daedro.toml --scenario 46` |
| 106 | μ=1.01 · m=0.66 kg · size=2.3 cm · noise=0.002 rad | never_lifted | `daedro repro --config examples/custom_controller/daedro.toml --scenario 106` |
| 45 | μ=1.20 · m=0.64 kg · size=4.2 cm · noise=0.004 rad | never_lifted | `daedro repro --config examples/custom_controller/daedro.toml --scenario 45` |

🎬 **Side-by-side replays** of 2 regressed scenario(s) (#32, #109): attached to this run as `daedro-preview`.

<details markdown="1"><summary>Scenario suite and environment</summary>

- Suite: LHS, n=120, seed=7; both versions ran the identical scenarios.
- Declared operating envelope: `friction` 0.3–1.2; `half_size` 0.01–0.035; `ik_noise` 0–0.005; `mass` 0.05–0.8
- MuJoCo 4.0.1 · Franka Panda (MuJoCo Menagerie eea4c74) · scripted pick-and-place, 3 cm success radius

</details>

> ⚠️ **Simulation only.** These results come from a MuJoCo model, not hardware. A pass here does not guarantee real-world performance or safety; a regression here is a lead to investigate, not proof of a hardware failure.
