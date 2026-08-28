# Compounds: Reusable System Recipes

A **component** is an elemental brick: movement, inventory, weather, pets, trade transport, or persistence.

A **compound** is a validated recipe that combines several bricks into a recognizable game-system behavior. A compound adds no hidden runtime implementation; it records the members, the event wires, critical pieces, and acceptance criteria needed to assemble and test that composition repeatedly.

## Included compounds

| Compound | Purpose |
|---|---|
| `compound.pet_persistence_loop` | Acquire/own a pet, dirty player state, save it safely, and retain it through a profile session |
| `compound.server_authoritative_trade_flow` | Open a client trade, validate and commit through server authority, and return committed/rejected events to transport and UI |

## Validation

```bash
python3 tools/validate_compounds.py --report reports/compound-validation.json
```

The validator checks:

- Each compound member exists in `components/`
- Each member supports the compound platform (or is platform-agnostic)
- Each event wire has a real emitter on the source component
- Each event wire has a real listener on the target component
- Every declared critical component belongs to the compound

## Why compounds matter

Components make reuse possible. Compounds make reuse practical: a Builder does not need to rediscover the same safe arrangement every time it wants persistent pets or a server-authoritative trade flow. A Playtester gets explicit acceptance criteria, and a Producer can scope work around a meaningful behavior rather than an arbitrary pile of modules.
