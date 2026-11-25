# Daedro — Project Context

Read this before doing any work in this project. It records what has been decided so far, so each session starts from the current state instead of the original 1,600-line brief.

## Who
- Jad Elayan, UC Irvine student. Strong in software, product and design; new to robotics.
- Goal: build Daedro into a company strong enough to be accepted by Y Combinator.
- The second founder (robotics/ML) is **not yet recruited**. Treat robotics expertise as a gap, not a resource.

## What Daedro is (working hypothesis, not a validated product)
> **Direction set 2026-11-25:** Daedro helps robotics teams use what happens on their factory floor to make their robots better.

Every team generates evidence daily (failed picks, bad shifts, new grippers, cells that differ). Daedro turns real incidents into reusable **cases** (recording + robot state + hardware config + software version + outcome) that engineers investigate, test fixes against, and verify across machines; outcomes after rollout feed the next iteration. Regression testing (what's built) is one piece. Analogy: Applied Compute's AC2 feeds production traces into the next training run (appliedcompute.com/platform/introducing-ac2): an analogy, not a competitor.
- **First product:** the shortest path from one real robot incident to a case an engineer can reuse, built with one team on recordings it already collects (likely via Foxglove/MCAP). Simulate when the case reproduces; otherwise store physical test evidence in the same case.
- **Signal:** the team brings a second and third case unprompted.
- **Caution:** recordings support investigating what happened, not proving what a changed controller would have done (see Key technical cautions).
- Adjacent: Foxglove (recording/replay), InOrbit (fleet monitoring), Formant, Roboto, Rerun, Viam. Integrate, don't replace. Gap to test: manual work between seeing a problem and proving an improvement.
- Earlier framing (kept as history): catch and reproduce regressions when updating a robot policy or controller, and turn confirmed failures into repeatable tests.

- Long-term vision (infrastructure for testing, adapting and deploying robot skills) stays a vision. Every later phase needs its own evidence.
- **Name: Daedro** (chosen 2026-11-24), after Daedalus, the mythic craftsman who built moving statues and told Icarus to fly the middle course. Brand line candidate: "Fly the middle course." Renamed from "Synapse", which was crowded (Synapse Robotics, SYNAPSE ML/automation software marks, Synapse Semiconductor YC S26, Synapse fintech collapse).
- Daedro checks done: daedro.ai, daedro.dev and getdaedro.com were unregistered on 2026-11-24 (daedro.com taken); web search found no conflicting company. **Not** a legal trademark clearance. Run a USPTO search before paying for domains or brand work. Nothing registered yet.

## Current phase: investigation + a minimal real product (Nov 2026 →)
On 2026-11-24 Jad unfroze branding and product work: he works better when something real exists. Scope agreed:
1. Name + logo.
2. A real CI tool: `daedro compare` runs the same seeded sim scenarios on two controller versions and writes a regression report; a GitHub Action posts it on pull requests.
3. A demo run producing a real report.
4. An honest landing page built around that real report, plus a waitlist. Public deployment only with Jad's explicit approval.
Still frozen: pricing tiers, dashboards, and features the tool doesn't actually have. The evidence tracks below still decide whether this becomes a company; the product does not replace them.
Hardware: don't buy a robot arm yet. If needed later, a low-cost SO-101 kit (LeRobot) fits; not a Franka.

### Three parallel tracks
1. **Existing-tool investigation.** Run RoboGate, and try Bifrost Manifold if access allows. For each, write one page covering: what we actually ran, hardware and dependencies, documented vs. demonstrated, where it broke, and which limitation a real user also hit.
2. **8–10 workflow interviews** with UCI robotics researchers and grad students. Ask them to show:
   - their latest eval script
   - two versions they compared
   - a failure they couldn't reproduce
   - what evidence made them run (or not run) on hardware
   - the most recent eval task that ate a lot of time
   Opening question: *"Which evaluation result do you trust enough to change your engineering decisions?"*
3. **One collaboration case.** Work through one real, nonconfidential case with a robotics collaborator: a comparison report for two behavior versions, using an eval procedure they already trust.

### Six-week execution gate
By ~6 weeks in, work through one real evaluation case with a robotics collaborator. If it doesn't happen, figure out which of these is the reason:
- no responses → outreach problem, not evidence about the market
- conversations but no shared case → access, trust or relevance problem
- shared cases but no repeated pain → rethink the wedge
- clear pain but we can't execute → narrow the scope or rethink the founding team

### Proceed-to-build test
Only commit to building when we can fill this in with evidence:
"These specific teams repeatedly struggle with ___, existing tools leave ___ gap, and at least one team has committed time, data, integration effort or money to testing our solution."

## Competitive facts (verify before relying on them)
- **RoboGate** (arXiv 2603.22126, AgentAI Co., Seoul, robogate.io). Uses LHS + boundary-focused sampling on scripted pick-and-place in Isaac Sim, is open source, and runs on a single GPU. v1/v2 (Mar 2026) report 2 robots (Panda, UR5e) and 30k experiments; a later version reports 4 robots and 50k+. Always cite the version. Its VLA results have acknowledged action-space-mismatch caveats.
  → **The original Synapse MVP (Panda + MuJoCo + 4 physical params + adaptive sampler) is a learning and reproduction exercise, not differentiated technology.**
- **Bifrost Manifold** markets policy evaluation across simulators (Isaac Lab, MuJoCo, ManiSkill, Genesis) with failure clustering and leaderboards. Its site *claims* to be open source; no public repo or license has been found yet. Currently early access.
- Active research field: NVIDIA RoboLab, XPolicyLab, RobotArena∞, SIMPLER, AutoEval (real-world automated eval), RoboArena, world-model evaluators, SO-101 Bench, LeRobot.
- Robotics observability tools (Foxglove, Roboto, Rerun, Formant) overlap with any "real failure logs" direction.

## Key technical cautions
- Simulator trust comes before search sophistication. A failure found in a sim the customer doesn't trust is worthless.
- Recorded logs support *investigating* a failure, not claiming what a changed policy *would* have done.
- Don't assume learned-policy (VLA) teams are the best first customers. Choose by reachability, whether we can run their behavior, trustworthy success criteria, recurrence, and a gap they can't fill today.
- A "meaningful failure" must be valid (inside declared operating conditions), reproducible, distinct, and actionable.

## Non-negotiable rules
- Never fabricate traction, metrics, customers, partnerships, testimonials or benchmark results, including in YC applications, decks or the website.
- Never present simulated results as hardware validation, or claim that passing tests guarantees safety.
- Distinguish hypotheses from proven capabilities in everything we write.
- Use existing open-source tools. Don't rebuild what exists without a documented reason.

## First engineering task
Reproduce RoboGate's smallest workflow:
1. Inspect the repo: license, dependencies, GPU and hardware needs.
2. If Isaac Sim is too heavy for our machines, record that, then build the equivalent minimal loop in MuJoCo (Franka Panda from MuJoCo Menagerie, scripted pick-and-place, 4 params, random vs. LHS sampling, seeded reproducibility) purely as a learning exercise.
3. Write the one-page tool record (Track 1).

## When working in code
- Inspect the existing repo before changing anything. Work in small, testable increments. Don't silently replace working code.
- Explain significant architectural decisions.
- Python first for the tool. The landing page is a static site; no dashboard or cloud backend yet.

## Log
- 2026-11-23: Brief written. Three AI critiques converged on the investigation plan above. Brief frozen. Next action: send outreach emails to 3 UCI robotics researchers/grad students.
- 2026-11-24: Track 1 step done for RoboGate (docs/tool_record_robogate.md): harness code not public, no GPU here; public dataset re-analysed — boundary-sampling AUC gain did not reproduce at equal budget; Stage 2 never sampled its stated emphasis region; UR10e 61.6% in paper has no public data. MuJoCo loop built (docs/mujoco_loop.md): stock Menagerie gripper too weak; first sim version produced a geometry artifact, caught by a Coulomb check; LHS ≈ random for the risk model. Name check: "Synapse" is crowded (Synapse Robotics in A3 directory, SYNAPSE software marks for ML/automation, Synapse Semiconductor YC S26 physical AI, Synapse fintech collapse) — rename recommended. Jad asked to unfreeze: name, logo, website, deployment, working product.
- 2026-11-24 (later): Name chosen: **Daedro**. Project renamed (package `daedro`). Building logo, `daedro compare` CI tool, demo report, landing page.
- 2026-11-24 (later): Built: logo (brand/), `daedro compare/repro/run/ci` CLI (14 tests pass), GitHub Action (untested on GitHub), demo report (examples/pick_place: faster+softer grip -> 7 regressions, McNemar p=0.016), static landing page (site/). Not deployed. Waitlist backend undecided.
- 2026-11-24 (later): Landing page deployed to https://daedro.vercel.app (Vercel project 'daedro'). Waitlist: Google Form link pending. Code committed locally; GitHub repo pending.
- 2026-11-24 (later): Landing page live at https://daedro.vercel.app (Vercel project `daedro`). Code pushed to github.com/JadElayan/daedro. Added bring-your-own-controller plug-in (daedro/plugin.py): a from-scratch team controller scores 120/120; a "close gripper early" PR breaks 101/120, clustered on small parts. CI compares base-branch *code* via git worktree. 17 tests pass. Live Action demo set up in demo/ (needs a PR to run). Waitlist Google Form link pending; site not yet updated for the plug-in.
- 2026-11-24 (later): GitHub Action verified live on JadElayan/Daedro#1 (demo PR, not for merging): commented a report (68/80 regressed, code_sha256 change detected, clustered on small parts) and failed the check as intended via fail-on 0. Run took 53 s on ubuntu-latest.
- 2026-11-24 (later): Jad asked to build the full 'Vercel for robotics' path now. Built: side-by-side video previews (compare/ci --videos, daedro preview; Action uploads artifact), failure library (daedro pin, incl. --field; pinned failures re-run every comparison and gate CI), camera observations for vision policies (front + wrist). Staged rollouts: design doc only (docs/design_staged_rollouts.md), no fake fleet code. Not built: custom robot models, Isaac/ManiSkill (no GPU), hosted runs, dashboard. 23 tests pass.
- 2026-11-25: Jad: build both (builders + manufacturers) as one engine. Built: experimental SO-101 support (docs/so101_preview.md: fragile tip-contact grasp, noise-free envelope, ~25% release flakiness), robot setups + release records (daedro release / approve; verdicts Ready/Review/Blocked/Needs hardware test), website updated on Codex's design (release section, features, who it's for) and redeployed from GitHub to daedro.vercel.app. Game plan in docs/game_plan.md; Jad runs builder outreach. 28 tests pass.
- 2026-11-25 (later): Jad set the direction: robot-improvement platform (incident → case → investigate → try fix → verify across machines → outcomes feed back), Applied Compute as the model. Founding-team Google Doc rewritten around it (Drive: "Daedro: Company Overview and Plan"; older versions marked [Superseded]). Website still uses the regression-testing framing. Next build, only with a real team: import a real recording into a case.
