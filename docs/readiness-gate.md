# Manifest Readiness Gate

`tools/evaluate_manifest_readiness.py` is the Playtester gate between a graph-valid build plan and a release claim. It reads a manifest produced by `compile_build_manifest.py` and evaluates adapter implementation status by release mode.

## Modes

| Mode | Pass condition | Intended use |
|---|---|---|
| `prototype` | Always passes if the manifest is readable; missing/scaffold adapters become warnings | Architecture review and early planning |
| `demo` | Every critical component must have at least an adapter; scaffold adapters warn but do not fail | Internal playable/demo scope |
| `production` | Every resolved component must be `constructor-verified` | Candidate release scope |

`constructor-verified` means an adapter contains at least one upstream source-verified constructor call. It is deliberately **not** a substitute for runtime, security, or integration testing.

## Run it

```bash
python3 tools/compile_build_manifest.py \
  examples/pet-survival-game.request.json \
  --output reports/pet-survival-game.manifest.json

python3 tools/evaluate_manifest_readiness.py \
  reports/pet-survival-game.manifest.json \
  --mode prototype \
  --report reports/pet-survival-game.prototype-readiness.json
```

## Council usage

1. Architect declares `criticalComponents` in a request.
2. Builder compiles the manifest.
3. Playtester runs the evaluator at the intended release mode.
4. Producer uses the report to approve, reduce scope, or schedule missing adapters.

The Pet Survival Game CI example runs `prototype` mode intentionally. Its purpose is to prove that the manifest compiles and reports gaps honestly; it must not be interpreted as a runnable demo or a production-ready game.
