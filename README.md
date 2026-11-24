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
