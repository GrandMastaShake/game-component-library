# Adapter Coverage Roadmap

`tools/generate_coverage_roadmap.py` converts a compiled manifest into the Producer's implementation backlog. It identifies every component whose Roblox adapter is not yet `constructor-verified`, ranks the work by critical-path membership and downstream impact, and supplies a source-honest next action.

## Run it

```bash
python3 tools/compile_build_manifest.py \
  examples/pet-survival-game.request.json \
  --output reports/pet-survival-game.manifest.json

python3 tools/generate_coverage_roadmap.py \
  reports/pet-survival-game.manifest.json \
  --output reports/pet-survival-game.coverage-roadmap.json
```

## Ranking method

The roadmap does not claim to estimate engineering effort. It ranks **unblocking value**:

1. A component named in `criticalComponents` receives the highest weight.
2. A component that unlocks many downstream bricks is ranked above an isolated leaf component.
3. A missing adapter is ranked above a scaffold, and a scaffold above a constructor-verified adapter.
4. Ties are deterministic, using component ID.

The output includes the exact descriptor path, status, number of transitively unlocked downstream components, and a next action appropriate to the evidence level.

## How to use it

- **Architect:** adjusts `criticalComponents` when the minimum player loop changes.
- **Builder:** takes the queue top-to-bottom but stops to verify upstream APIs before implementing source calls.
- **Playtester:** recompiles and re-evaluates readiness after each adapter milestone.
- **Producer:** uses the critical-gap count to make scope and release decisions.

The roadmap is an implementation-order tool, not a substitute for engineering estimation, security review, or playtesting.
