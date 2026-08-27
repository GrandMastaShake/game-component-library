# Roblox Adapters

This folder is the bridge between the platform-agnostic component definitions in `components/` and the concrete Luau implementations that already exist in [`roblox-modular-lib`](https://github.com/GrandMastaShake/roblox-modular-lib).

## Plan

1. For each `*.component.json` in `components/`, add a matching adapter here (e.g. `movement.basic_walk.adapter.lua`) that maps the schema's `inputs`/`outputs`/`events` onto the actual Luau module API in `roblox-modular-lib`.
2. Adapters should be thin — no gameplay logic lives here, only translation between the universal schema contract and the Roblox-specific module signature.
3. As `roblox-modular-lib` modules are wrapped, cross-link them back into their `component.json` via a `platformImplementations` field (to be added to `component.schema.json` in a future version).

## Status

Not yet started — this is the next concrete step after the schema and example bricks are in place.
