# Tool record: RoboGate

*Track 1, existing-tool investigation. Written 2026-11-24. One page by design.*

**Versions inspected:** arXiv 2603.22126 **v4** (20 Apr 2026; PDF sha256 prefix `f03c6522`) · `liveplex-cpu/robogate-failure-dictionary` @ `da3cfea` (2026-04-15, MIT) · `liveplex-cpu/robogate-leaderboard` @ `f9f8331` (2026-07-04, CC BY 4.0). The paper's code link, `github.com/liveplex-cpu/robogate`, **could not be cloned anonymously** (git asks for credentials, which is GitHub's response for a private or missing repo).

## What we actually ran
- **Not** the RoboGate simulation. No public code exists to run, and our machine has no GPU (4 CPUs, 15 GB RAM).
- A re-analysis of the public 50k-row dataset against the paper's headline claims: `scripts/check_robogate_claims.py` (numpy only, deterministic).
- As a learning exercise, a MuJoCo equivalent of the smallest workflow (see `docs/mujoco_loop.md`).

## Hardware and dependencies (as documented, not verified)
RTX 4090 (24 GB), i9-13900K, 64 GB RAM, Ubuntu 22.04, Isaac Sim 5.1 + Newton physics, Python 3.12. The VLA path adds a separate Python 3.11 Isaac process, a per-model conda env and a ZMQ bridge. The reproducibility commands in the appendix point to `scripts/*.py` that aren't public, and include a Windows `python.bat` path. Reported cost is about 14 GPU-hours for 30k episodes.

## Documented vs. demonstrated

| Claim (source) | What the public data shows |
|---|---|
| "Open-source" (abstract, README) | The data and leaderboard are open. The simulator harness, controller, sampler and risk model are **not public**. The leaderboard says `pip install robogate` is "on the roadmap". |
| Franka SR 33.3% / 63.9%, UR5e 74.3% (paper Table 3) | **Reproduced** exactly from the files. |
| friction r=+0.36, mass r=−0.20, ik_noise r=−0.11 (README) | **Reproduced** (+0.356, −0.196, −0.110). |
| Risk-model AUC 0.754 → 0.780 from boundary sampling (paper §10) | We get similar raw numbers (5-fold CV 0.743 uniform, 0.790 combined), but the two figures are scored on **different datasets**. At an **equal 8k budget, scored on the same held-out uniform data**, uniform-only gives 0.740 ± 0.010 and half-uniform + half-boundary gives 0.738 ± 0.010 (20 repeats). **The improvement did not reproduce** under a like-for-like test. (Our model is a close approximation of theirs, not their code.) |
| Stage 2 puts 30% of its budget in the emphasis region μ<0.3 ∧ m≥0.5 (paper §5.2; file metadata says the same) | The Stage 2 file samples μ ∈ [0.355, 1.2] and m ∈ [0.05, 0.869]. **0 of 10,000** rows fall in the emphasis region. |
| "Danger zones: 7,808" (README) | `zone` is assigned per row from a pre-computed `fail_prob`, built from hand-set lookup penalties (box 0.00, cylinder 0.15, … irregular 0.45; 0.12 per obstacle). It is a heuristic label, not a measured failure region. As a predictor that heuristic scores AUC 0.63. |
| Timeout means "episode exceeds 15 s" (paper §4.3) | Every `timeout` row has `cycle_time` between 1.50 and 2.03 s. Either the field means something else or the definition doesn't match the data. |
| UR10e SR 61.6% (paper v4 Table + conclusion) | The data file shows **0.1%** (10/10,000) and the README says 0.0%. The paper's UR10e figure has **no public data behind it**. |
| UR3e/UR10e use finger grippers (README table) | File metadata says `SurfaceGripper (Short_Suction)`, and so does the paper. The UR5e file's metadata says `robot: "ur10"`. |
| Scripted baseline 100% (68/68) (paper §7) | The leaderboard (Jul 2026) says **83.8% (57/68)**. |
| "eight VLA policies" (arXiv abstract) | The PDF body says seven. The leaderboard now lists 15, all 0/68. |

## Where it broke for us
1. **Can't run it.** There's no public harness, and even with code, Isaac Sim needs an RTX-class GPU that we don't have.
2. **Can't trace provenance.** Rows carry `mode: "isaac_sim"`, but the per-row heuristic fields (`fail_prob`, `*_penalty`) and the unreleased generator mean we can't tell which values the physics measured and which were computed.
3. **Cross-robot comparisons aren't like-for-like.** UR5e varies 5 parameters, UR3e/UR10e vary 9 different ones (some, such as `gravity_scale` and `approach_speed`, don't exist for Franka), and Franka varies 8. The paper acknowledges part of this.

## Which limitation a real user would also hit
- **The VLA 0/68 result can't be acted on by a policy team.** The paper converts each model's delta-EE output with a fixed 0.02 m / 0.05 rad scale and its own IK, and attributes the GR00T fine-tune collisions to "likely an action-scale mismatch". The harness itself is a plausible cause of the gap, and a team can't rerun it to rule that out. The leaderboard's "manual queue" makes this worse.
- **The boundary equation is simulator-specific and unvalidated on hardware.** The paper says so (§9.8) and plans a 500-episode real-robot study.

## What this means for Daedro (hypotheses, not conclusions)
- RoboGate's public value today is a **dataset and a leaderboard**, not a tool a team can run on its own policy. "Can I reproduce this on *my* policy in a simulator I trust?" is unmet *by RoboGate*. It's still unknown whether teams actually want that (Track 2 should test it).
- The two-stage sampler's advantage is **not established** by the public evidence. Search sophistication is not where the gap is, which matches our CLAUDE.md caution.
- Question for interviews: would a team trust a third-party harness's 0% result, or only results from their own eval stack?

*Reproduce the numbers above:* `python -I scripts/check_robogate_claims.py ../external/robogate-failure-dictionary`
