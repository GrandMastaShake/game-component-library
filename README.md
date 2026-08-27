# Game Component Library

A Lego-style, AI-assemblable library of modular game components ("bricks"). Each brick is a self-contained, schema-described unit that declares its inputs, outputs, events, and dependencies so that both humans and AI agents can snap components together into working game systems without hand-wiring glue code.

## Why This Exists

Most game codebases are monolithic and tightly coupled, which makes it hard for an AI agent (or a human) to safely assemble new features from existing parts. This library takes the opposite approach: every gameplay system is broken into small, independently testable, independently describable bricks that conform to a single shared contract (`component.schema.json`).

Think Lego, not spaghetti: pick a `movement` brick, snap in a `combat` brick, wire up an `inventory` brick, and the schema tells you (or your AI council) exactly how the studs line up.

## Repository Structure

```
game-component-library/
├── README.md                     This file
├── component.schema.json         The Lego connector contract
├── COUNCIL.md                    AI assembly council roles
├── components/
│   ├── movement/                 Walk, jump, dash, swim, fly
│   ├── combat/                   Melee, ranged, magic, AOE
│   ├── inventory/                Slots, stacking, rarities
│   ├── economy/                  Currency, shop, rewards
│   ├── social/                   Trade, party, chat, leaderboard
│   ├── world/                    Terrain, weather, day-night
│   └── ui/                       HUD, menus, notifications
└── roblox-adapters/
    └── README.md                 Bridge to roblox-modular-lib
```

## Component Contract

Every brick is described by a JSON file that follows `component.schema.json`. At minimum a component declares:

- `id` — unique identifier
- `category` — one of the top-level component folders
- `platform` — which runtimes it supports (roblox, godot, unity, web, agnostic)
- `inputs` — parameters the component accepts
- `outputs` — values or state the component exposes
- `events` — signals the component emits or listens for
- `dependencies` — other component ids it requires to function

This contract is what lets an AI "builder" agent discover available bricks and wire them together correctly instead of hallucinating integration code.

## Related Repos

- [`roblox-modular-lib`](https://github.com/GrandMastaShake/roblox-modular-lib) — Luau implementations of many of these bricks for Roblox Studio
- [`bits-and-baubles-blender-kit`](https://github.com/GrandMastaShake/bits-and-baubles-blender-kit) — Blender-side brick/snap geometry pipeline that inspired this schema

## Status

Early scaffold. Seven example bricks are included as reference implementations of the schema; more will be added as they're extracted from existing projects and wrapped with schema descriptors.
