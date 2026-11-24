# MuJoCo learning loop: what it showed

*2026-11-24. A learning exercise, not differentiated technology (see CLAUDE.md). All results are simulation-only.*

**Setup:** Menagerie Franka Panda (commit `eea4c74`), MuJoCo 4.0.1, CPU only. Scripted 6-phase pick-and-place, with 4 swept parameters: object friction μ [0.05–1.2, log], mass [0.05–2 kg, log], cube half-size [1–3.5 cm], and joint-target noise [0–0.04 rad]. Success means the cube rests within 3 cm of the target. About 0.3 s per episode per core.

## Findings
1. **The stock gripper can't do the task.** Menagerie's gripper is a 100 N/m position servo. We measured about 0.1–2 N of squeeze per finger, and it fails to lift 0.2 kg even at μ=1. We replaced it with a stiff servo clipped at 70 N tendon force (the Panda's spec continuous force), which measures 35 N per finger. Default MuJoCo contact softness (solref 0.02) then let the pads sink about 8 mm and pop the cube out, so we use 0.005.
2. **The first version gave results we couldn't trust.** Grasping 20% below the cube's centre tilted it onto the small pad boxes, where it was *carried on a ledge*. Slippery 2 kg cubes "succeeded" with only 70 N of normal force, where Coulomb friction needs 196 N. A sampler run on that sim would have "found" a boundary created by finger geometry. We found this by checking the sim against the closed-form bound 2μN ≥ mg *before* running any search.
3. **After the fix, the sim agrees with physics.** In a noise-free 9×9 friction × mass grid, 80/81 cells (flat pad) and 78/81 (as-shipped fingers) agree with Coulomb (`results/coulomb_check.json`). In the 2,000-episode reference campaign, rows with noise < 0.005 rad agree 94% of the time (n=250).
4. **The reference landscape** (LHS, n=2,000, seed 1): SR 43.7%. Outcomes: success 874, slip_on_lift 679, drop_in_transit 244, misplaced 163, grasp_miss 40. Correlation with success: mass −0.44, friction +0.37, noise −0.37, size +0.14. Success rate by noise level: 73% (<0.01 rad), 44%, 33%, 24% (0.03–0.04 rad).
5. **Random vs. LHS** (10 campaigns of n=100 each, scored against the reference):

   | | SR error (RMSE) | AUC of fitted risk model on the reference |
   |---|---|---|
   | Random | 0.048 | 0.944 ± 0.005 |
   | LHS | 0.035 | 0.945 ± 0.004 |

   LHS gives a somewhat tighter success-rate estimate, as theory predicts (10 repeats is weak evidence). It makes **no difference** to the risk model. This matches the RoboGate re-analysis: the sampler is not where the value is.
6. **Reproducible.** The same seed gives an identical `rows_sha256` (tested). Every campaign is in `results/` with version metadata.

## Lessons for Daedro (hypotheses)
- Most of the work, and nearly all of the risk, sat in **making the sim trustworthy**, not in search. A customer will ask the same thing: "why should I believe this failure?"
- Physical-fidelity choices (gripper force, contact softness, collision geometry) changed outcomes more than the choice of sampler did. Any comparison report has to state them.
