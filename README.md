# Game Component Library

A schema-driven, AI-assemblable library of modular game systems—**elements** and **compounds**—plus tools that validate connections, compile safe build plans, and assess prototype, demo, or production readiness.

> Build games from validated pieces rather than one-off glue code.

## What exists

- **75 component descriptors** spanning movement, combat, inventory, economy, social, world, UI, pets, progression, persistence, presentation, housing, and utility.
- **10 validated compounds** for reusable multi-system gameplay loops.
- Component-graph and compound validators for malformed descriptors, missing members/dependencies, bad event wires, duplicates, and cycles.
- A platform-aware build-manifest compiler, readiness evaluator, and coverage-roadmap generator.
- A dependency-injection adapter runtime for integrating `roblox-modular-lib` without hard-coded cross-repository paths.
- Two library-native strict-Luau runtime modules with deterministic TestEZ-style tests: `EggHatchery.lua` and `PetHatchPresenter.lua`.

## Mental model

An **element** is a component contract: inputs, outputs, events, dependencies, platform scope, provenance, and—when available—an implementation path.

A **compound** is a validator-checked gameplay composition: member components, event wires, critical path, configuration, and acceptance criteria.

```text
Component descriptors → declare contracts and dependencies
Compound recipes      → declare reusable behavior and event topology
Validators            → reject incoherent graphs and wiring
Manifest compiler     → creates a dependency-safe platform build plan
Readiness + roadmap   → shows risk and prioritizes adapter work
Adapters/native code  → executes those contracts in a game runtime
```

## Provenance

| Value | Meaning |
|---|---|
| `upstream-mapped` | Maps an existing `roblox-modular-lib` implementation |
| `library-native` | Designed and implemented in this repository |
| `hybrid` | Maps upstream behavior while adding contract extensions that still need adapter work |

A valid descriptor or compound is not, by itself, a claim that its runtime adapter is complete or production tested.

## Quick start

Validate the catalog and compound recipes:

```bash
python3 tools/validate_component_graph.py --report reports/component-graph.json
python3 tools/validate_compounds.py --report reports/compound-validation.json
```

Compile the included Pet Survival Game request:

```bash
python3 tools/compile_build_manifest.py \
  examples/pet-survival-game.request.json \
  --output reports/pet-survival-game.manifest.json
```

Evaluate prototype readiness and generate the prioritized implementation roadmap:

```bash
python3 tools/evaluate_manifest_readiness.py \
  reports/pet-survival-game.manifest.json \
  --mode prototype \
  --report reports/pet-survival-game.prototype-readiness.json

python3 tools/generate_coverage_roadmap.py \
  reports/pet-survival-game.manifest.json \
  --output reports/pet-survival-game.coverage-roadmap.json
```

## Compounds

| Compound | Gameplay loop |
|---|---|
| Pet Persistence Loop | Ownership → state save → session restore |
| Pet Progression Loop | Activity → XP → level/skills → feedback → save |
| Pet Hatching Loop | Egg → weighted outcome → reveal request → persistence trigger |
| Home Trade Stand Loop | Home listing → visitor discovery → trade entry |
| Server-Authoritative Trade Flow | Client transport → server validation → commit/reject UI state |
| Party Quest Sharing Loop | Quest completion → party policy → deduplicated shared credit |
| Procedural World Bootstrap | Noise → terrain/biomes/caves/water → props/environment |

## Runnable hatch slice

The first native vertical slice is a server-authoritative pet hatching flow:

```text
Authoritative Inventory
  → pets.egg_hatchery (server-side weighted outcome)
  → pets.hatched
  → ui.pet_hatch_presenter
  → ui.notificationRequested
  → notification UI adapter

pets.hatched → save-system adapter
```

`EggHatchery` receives authoritative Inventory, Currency, EventBus, and RNG dependencies. The client does not select outcomes; egg ownership and optional cost are checked before the result is granted. Explicit failure events cover missing eggs, insufficient funds, and inventory/charge/grant failures; compensating restores/refunds are attempted where applicable.

`PetHatchPresenter` receives an already-trusted hatch payload and emits normalized presentation intent. It does not render UI, keeping gameplay authority, presentation decisions, and platform-specific rendering modular.

## Roblox integration

`roblox-adapters/AdapterRuntime.lua` uses dependency injection. The consuming Roblox project supplies its own upstream module references and EventBus according to its Rojo, Wally, or Studio arrangement.

Two upstream constructor shapes have been source-verified:

```lua
Inventory.new(eventBus, maxSlots)
TradeCoordinator.new(eventBus, deps, config)
```

See `roblox-adapters/INTEGRATION.md` and `roblox-adapters/ADAPTER_STATUS.md` for integration boundaries and evidence status.

## Quality boundary

GitHub Actions runs the graph validator, compound validator, Pet Survival Game manifest compiler, prototype readiness evaluator, and coverage-roadmap generator when relevant files change.

Passing validation proves contract coherence—not that all adapters are playtested or production-ready.

## Immediate roadmap

1. Connect `PetHatchPresenter` to a Roblox notification/toast adapter.
2. Add a persistence integration test for the full hatching loop.
3. Implement native Home Trade Stand and Party Credit Guard runtimes.
4. Complete the critical Pet Survival Game adapter path using the coverage roadmap.
5. Add native components only when a real vertical slice exposes a missing contract.

## Related repositories

- [`roblox-modular-lib`](https://github.com/GrandMastaShake/roblox-modular-lib) — upstream strict-Luau systems mapped into the initial catalog
- [`bits-and-baubles-blender-kit`](https://github.com/GrandMastaShake/bits-and-baubles-blender-kit) — modular Blender/3D work that inspired the validated-building-block approach
