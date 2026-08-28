# Compounds: Reusable System Recipes

Components are elemental bricks. Compounds are validated recipes that combine bricks into recognizable game-system behaviors, including member roles, event wires, critical pieces, and acceptance criteria.

## Included compounds

| Compound | Purpose |
|---|---|
| `compound.pet_persistence_loop` | Persistent pet ownership state |
| `compound.server_authoritative_trade_flow` | Server-authoritative trade topology |
| `compound.pet_progression_loop` | Companion XP, level feedback, skill evaluation, and saving |
| `compound.quest_reward_loop` | Quest completion, reward state, feedback, and saving |
| `compound.crafting_loop` | Ingredient inventory, crafted result, feedback, and saving |
| `compound.home_showcase_loop` | Home displays, layout saving, and future social visitation |
| `compound.procedural_world_bootstrap` | Seeded terrain, biomes, caves, erosion, water, props, and environment |

Run `python3 tools/validate_compounds.py --report reports/compound-validation.json` to verify component references, platform support, event emitters/listeners, and critical membership.
