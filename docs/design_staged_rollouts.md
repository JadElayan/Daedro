# Design: staged rollouts (test → deploy → monitor)

*Status: design only, 2026-11-24. Nothing here is built except the pieces marked **exists**. We build the rest with the first team that ships behaviour updates to real robots, because the integration (how their robots receive code, what they log) decides most of the details.*

## Goal
A controller or policy change reaches a fleet only after passing gates that get closer to reality, and rolls back on its own when real-world success drops. This turns Daedro from "a test you run" into "the path every behaviour change takes to production", which is where infrastructure stickiness comes from.

## The pipeline

```
PR opened ──► Gate 0: simulation (exists)
               paired regression run + failure library, --fail-on
                        │ merge
                        ▼
              Gate 1: release candidate
               the --json verdict from Gate 0 is attached to the build (exists: daedro ci --json)
                        │
                        ▼
              Stage 1: canary, 1 robot          ◄── field metrics
              Stage 2: 10% of the fleet          ◄── field metrics
              Stage 3: 100%                      ◄── field metrics
                        │ success drops below the baseline band
                        ▼
              Automatic rollback + new field failure pinned (exists: daedro pin --field)
```

## Pieces and their status

| Piece | Status | Notes |
|---|---|---|
| Simulation gate with paired stats, clustering, replay | **exists** | `daedro ci --fail-on N` |
| Failure library re-run on every change | **exists** | `daedro-failures.toml`, `daedro pin` |
| Machine-readable verdict per build | **exists** | `daedro ci --json`: versions, success rates, regressions, pinned regressions, environment |
| Field-failure intake | **exists (manual)** | `daedro pin --field` with measured conditions. Automatic intake needs the team's logs. |
| Robot agent (receives a version, reports outcomes) | design | Small daemon on each robot. Likely a ROS 2 node or a LeRobot hook; to choose with the first team. |
| Rollout controller (stages, holds, rollback) | design | Server-side state machine: `stage → hold until N picks observed → compare to baseline band → promote or roll back`. |
| Field metrics | design | Per-version pick success, cycle time, safety stops. The rollback rule uses a one-sided test against the previous version's rate, the same idea as the paired sim test, adapted to unpaired field data. |
| Dashboard | design | Version history across sim gate → canary → fleet. Frozen until a team needs it. |

## Rollback rule (first version)
Promote from a stage when at least `n_min` tasks have run (default 200) and the field success rate is not significantly below the previous version's (one-sided exact test, α = 0.01). Roll back immediately on any safety stop attributed to the new version, or when the test rejects. Every rollback automatically opens a field-failure pin for engineers to review. **A pin is a lead, not proof:** the simulator recreates the reported conditions, not the event itself.

## What we will not claim
- Passing the gates does not make a change safe. It reduces the chance of shipping a known class of regression.
- Simulation results are not hardware validation. The canary stage exists because the simulator can be wrong.

## Open questions for the first customer
1. How do robots receive new behaviour today (container image, ROS package, model weights over the air)?
2. What do they already log per task, and where (Foxglove, Roboto, Formant, their own)? Integrate before building our own collection.
3. Who approves a promotion: an engineer, or the rule?
4. What counts as a "task" and as "success" in their cell?
