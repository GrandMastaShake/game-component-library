# Build Manifest Compiler

`tools/compile_build_manifest.py` turns a high-level component request into an ordered, platform-aware build manifest for a Builder agent or a human implementation team.

## Input: a request

A request gives the intended platform and the top-level systems desired for a game:

```json
{
  "gameName": "Pet Survival Game",
  "targetPlatform": "roblox",
  "requestedComponents": [
    "pets.pet_companion",
    "world.world_builder",
    "social.trade_window"
  ]
}
```

## Output: a resolved manifest

The compiler recursively resolves every `dependencies` entry, rejects missing components and platform mismatches, then emits a dependency-safe `buildOrder`. Each emitted component includes its schema descriptor path and, for Roblox, an honest adapter status:

- `constructor-verified` — adapter contains a source-verified upstream constructor call
- `scaffold` — adapter exists but source implementation calls remain unverified
- `not-implemented` — descriptor has no Roblox adapter yet

## Run locally

```bash
python3 tools/compile_build_manifest.py \
  examples/pet-survival-game.request.json \
  --output reports/pet-survival-game.manifest.json
```

## Builder workflow

1. Architect writes a request JSON with top-level gameplay intent.
2. The compiler emits the complete dependency closure in safe order.
3. Builder inspects each component descriptor and adapter status.
4. Playtester rejects manifests with unresolved adapters for any required runtime path.
5. Producer decides whether to implement missing adapters, substitute a supported brick, or reduce scope.

The compiler does **not** generate gameplay code. It makes the build plan deterministic and auditable before code generation begins.
