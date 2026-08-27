# Assembly Council

This library is designed to be consumed by a small council of AI agents, each with a distinct role, rather than a single monolithic code generator. This mirrors the council pattern already used in the `ink-and-spindle` writing app and the `ember-data-foundry` pipeline.

## Roles

### Architect
Reads the player/designer's request and decomposes it into a target set of component categories and rough wiring (e.g. "a survival game needs movement, inventory, world/weather, and a day-night cycle"). Produces a manifest of required component ids, proposing new ones if nothing in the library fits.

### Builder
Consumes the Architect's manifest, pulls matching `component.schema.json`-conformant bricks from `components/`, and generates the glue/wiring code for the target platform (Roblox/Luau first, others as adapters are added). Never invents a component that isn't in the manifest — if something is missing, it must ask the Architect for a new brick spec.

### Playtester
Runs or simulates the assembled system against the `inputs`/`outputs`/`events` contracts declared in each component. Flags mismatched types, unhandled events, or missing dependencies before anything ships.

### Producer
Arbitrates disagreements between Architect and Playtester, approves new components for inclusion in the library, and maintains version bumps on `component.schema.json` itself.

## Workflow

1. Architect proposes a manifest.
2. Builder assembles from `components/` using the schema as the contract.
3. Playtester validates against declared inputs/outputs/events.
4. Producer signs off, or sends it back with notes.

This is intentionally the same council shape used elsewhere in the org's projects — the goal is a reusable orchestration pattern, not a one-off.
