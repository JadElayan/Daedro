## Release record: pick-cycle v2.4 → v2.5 (faster cycle, softer grip)

1 of 4 setups approved.

| Setup | Verdict | Evidence (simulation) |
|---|---|---|
| Site A · light parts (≤ 300 g) | **Ready** | 0 regressed / 120 · success 120→120 |
| Site B · heavy parts (up to 1 kg) | **Blocked** | 9 regressed / 120 · success 115→106 |
| Site B · suction cell | **Needs hardware test** | No simulation model |
| Lab · SO-101 (experimental) | **Blocked** | 32 regressed / 60 · success 45→16 |

**Site B · heavy parts (up to 1 kg): replay the failures**

- #72 slip_on_lift (μ=0.23, 0.97 kg, 5.9 cm): `daedro repro --config v2.5.toml --scenario 72`
- #2 slip_on_lift (μ=0.21, 0.94 kg, 3.6 cm): `daedro repro --config v2.5.toml --scenario 2`
- #14 drop_in_transit (μ=0.27, 0.93 kg, 5.6 cm): `daedro repro --config v2.5.toml --scenario 14`
- #49 slip_on_lift (μ=0.25, 0.84 kg, 4.3 cm): `daedro repro --config v2.5.toml --scenario 49`
- #32 slip_on_lift (μ=0.23, 0.79 kg, 3.3 cm): `daedro repro --config v2.5.toml --scenario 32`

**Lab · SO-101 (experimental): replay the failures**

- #6 slip_on_lift (μ=1.02, 0.15 kg, 2.0 cm): `daedro repro --config so101_v2.toml --scenario 6`
- #33 slip_on_lift (μ=0.65, 0.14 kg, 1.9 cm): `daedro repro --config so101_v2.toml --scenario 33`
- #3 misplaced (μ=0.87, 0.13 kg, 2.4 cm): `daedro repro --config so101_v2.toml --scenario 3`
- #10 drop_in_transit (μ=0.74, 0.12 kg, 2.1 cm): `daedro repro --config so101_v2.toml --scenario 10`
- #52 slip_on_lift (μ=0.88, 0.11 kg, 2.1 cm): `daedro repro --config so101_v2.toml --scenario 52`

**Approvals**

- 2026-11-25T00:07:45+00:00: Release lead (example) approved Site A · light parts (≤ 300 g) (Sim clean; rolling out to packaging line first)

**Hand-offs**

- 2026-11-25T00:07:45+00:00: Site A · light parts (≤ 300 g) → existing fleet deploy tool (example) (by Release lead (example))

> Simulation evidence only. A Ready verdict means no regressions were found in simulation for the declared conditions; it does not guarantee real-world performance or safety.