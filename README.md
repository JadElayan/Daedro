# Daedro

Learning and investigation code only — not a product. See `CLAUDE.md` for project context.

| Path | What |
|---|---|
| `docs/tool_record_robogate.md` | Track 1 one-page record for RoboGate |
| `docs/mujoco_loop.md` | What the MuJoCo learning loop showed |
| `scripts/check_robogate_claims.py` | Re-derives RoboGate's headline numbers from its public dataset |
| `scripts/coulomb_check.py` | Simulator-trust check: does grasp success follow 2·μ·N ≥ m·g? |
| `scripts/random_vs_lhs.py` | Random vs. LHS comparison campaign |
| `daedro/` | Panda (MuJoCo Menagerie) scripted pick-and-place, 4 params, seeded |
| `results/` | Every campaign as JSONL with a metadata header (versions, seed, sha256) |

## Setup
```bash
pip install -r requirements.txt
git clone https://github.com/google-deepmind/mujoco_menagerie ../external/mujoco_menagerie   # or set MENAGERIE_PATH
git clone https://github.com/liveplex-cpu/robogate-failure-dictionary ../external/robogate-failure-dictionary
python -m pytest -q
```

## Run
```bash
python -m daedro.campaign --method lhs --n 500 --seed 2026 --out results/lhs_2026.jsonl
PYTHONPATH=. python scripts/coulomb_check.py results/coulomb_check.json
python -I scripts/check_robogate_claims.py ../external/robogate-failure-dictionary
```
Same `--seed` → identical `rows_sha256` on the same machine/MuJoCo build (tested). CPU only; ~0.35 s per episode per core.

## The product (prototype)
```bash
pip install -e .
daedro compare --base examples/pick_place/base.toml --head examples/pick_place/daedro.toml --report report.md
daedro repro --config examples/pick_place/daedro.toml --scenario 137
daedro ci --base-ref origin/main --fail-on 0      # what the GitHub Action runs
python site/build.py                             # landing page -> site/dist/
```
- `action.yml`: composite GitHub Action (pins the Menagerie commit, posts one sticky PR comment). Not yet run on GitHub.
- `examples/workflow/daedro.yml`: workflow to copy into a team's repo.
- `brand/`: logo mark and favicon.

## Bring your own controller
Point `daedro.toml` at a Python class in your repo (`reset(obs)` and `act(obs)` returning a TCP or joint target plus a gripper command); see `daedro/plugin.py` for the interface and `examples/custom_controller/` for a working example. In CI, `daedro ci` checks out the base branch in a temporary worktree, so a change to the controller *code* is compared, not just the config.

Live demo: `demo/` + `.github/workflows/daedro.yml`. Open a PR that edits `demo/pick.py` and the Action comments a report.

## Video previews
`daedro compare ... --videos preview/` (or `daedro preview --scenario N`) films each regressed scenario for base and head side by side (MP4 + `index.html`). The Action uploads them as the `daedro-preview` artifact and links it from the PR comment. Needs `ffmpeg`; on headless Linux, Mesa EGL (`apt install libegl1 libgl1`).

## Failure library
`daedro pin --config daedro.toml --scenario N` (a sim failure) or `--field "where/when" --friction .. --mass .. --half-size ..` (a real-robot failure) appends to `daedro-failures.toml`. Every comparison re-runs all pinned failures and flags any that come back.

## Vision policies
Add `cameras = ["front", "wrist"]` (optional `camera_hz`, `image_size`) to `[controller]`; the policy receives `obs["images"]`.

## Roadmap
`docs/design_staged_rollouts.md`: how the simulation gate extends to canary → fleet rollouts with automatic rollback (design only, built with the first team that ships to real robots).

## Release records (robot setups)
`daedro release --file daedro-release.toml --out release/` runs base vs head on each hardware setup and writes a release record (JSON, Markdown, HTML) with a verdict per setup: Ready, Review, Blocked, or Needs hardware test. `daedro approve --record release/ --by NAME --setup "..." [--handoff "..."]` records approvals and hand-offs. Example: `examples/release/`.

## SO-101 (experimental)
`robot = "so101"` under `[controller]`. See `docs/so101_preview.md` for what works and its limits. Example: `examples/so101/`.

## Plan
`docs/game_plan.md`: the next six weeks.

## Cases: from a real incident to a proven fix
```bash
daedro case new --recording cell2.mcap --cases-dir cases          # find the incident, clip, timeline, context
daedro case reproduce --case cases/<id> --config current.toml     # does simulation recreate it?
daedro case test --case cases/<id> --base current.toml --head fix.toml --pin daedro-failures.toml
daedro case evidence --case cases/<id> --kind hardware --result pass --note "supervised trial"
daedro case evidence --case cases/<id> --kind outcome --result improved --note "first week after rollout"
```
Recordings are MCAP (the Foxglove / ROS 2 format) with JSON channels; see `daedro/recording.py` for the channels Daedro reads. `daedro record` writes example recordings from simulation, clearly marked as such. A recording supports investigation only; a fix counts as "verified in simulation" only when simulation reproduced the incident. Example: `examples/cases/` (an example incident, not customer data).
