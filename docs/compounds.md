# Compounds: Reusable System Recipes

Components are elemental bricks. Compounds are validated recipes that combine
bricks into recognizable game-system behaviours, including member roles, event
wires, critical pieces, and acceptance criteria.

A compound is not documentation. `validate_compounds.py` checks every
connection against the members' declared `emits` and `listensTo`, so a wire
written here that nobody sends is a build failure rather than a stale
paragraph. That is the difference between a kit and a list of suggestions,
and it is why the answer to "can I drop these into another game" is a
compound rather than a section in a README.

## Included compounds

| Compound | Pieces | Wires | What it makes |
|---|---|---|---|
| `compound.crafting_loop` | 5 | 3 | Ingredients, a crafted result, feedback, and saving |
| `compound.first_person_voxel_world` | 17 | 11 | A voxel world you stand inside |
| `compound.home_showcase_loop` | 4 | 3 | Home displays, layout saving, visitation |
| `compound.isometric_tile_world` | 10 | 7 | A stepped isometric board with elevation |
| `compound.party_quest_sharing_loop` | 4 | 3 | Quest credit shared across a party |
| `compound.pet_hatching_loop` | 6 | 4 | Eggs, hatching, and what comes out |
| `compound.pet_persistence_loop` | 6 | 2 | Persistent pet ownership state |
| `compound.pet_progression_loop` | 6 | 4 | Companion XP, feedback, skills, saving |
| `compound.procedural_world_bootstrap` | 14 | 10 | Seeded terrain, biomes, caves, water, props |
| `compound.quest_reward_loop` | 5 | 5 | Completion, reward state, feedback, saving |
| **`compound.real_time_encounter`** | 6 | 7 | **A place with hostiles in it, no turn structure** |
| `compound.server_authoritative_trade_flow` | 5 | 6 | Server-authoritative trade topology |
| `compound.stepped_grid_movement` | 8 | 8 | Tile-to-tile movement with elevation rules |

Run `python3 tools/validate_compounds.py --report reports/compound-validation.json`
to verify component references, platform support, event emitters and listeners,
and critical membership.

---

## Picking a kit: what goes where

The catalogue is organised by **what a component owns**, not by what genre it
came from. That is the whole reason a piece written for one game drops into
another, and it is worth stating as a rule, because the failure mode is
specific and recurring: a component that owns two things is a component that
can only ever be used by a game that wants both.

Every kit below is the same shape — a small number of pieces, each of which
owns exactly one question, wired through events so no piece reaches into
another.

### The real-time encounter kit

Six pieces, and the split is the point:

| Piece | Owns | Explicitly does not own |
|---|---|---|
| `combat.unit_roster` | who is on the board, which side, which tile, how much is left | movement, damage, or noticing |
| `combat.aggro_table` | noticing, threat, forgetting | the notice *range* (that is `utility.behavior_fsm`'s `detectionRange`), moving, striking |
| `movement.patrol_route` | roaming near where something spawned | the decision to chase, or the pace of one |
| `movement.pursuit_agent` | carrying out a chase | who to chase, or how far you notice |
| `combat.contact_attack` | the cadence of a strike — reach, cooldown, which sides swing | the damage number, or the positions |
| `combat.damage_resolver` | the one place a damage number is computed | what happens to the unit afterwards |

Add `combat.spawn_director` when the region should refill, and
`combat.enemy_tier_scaling` with it — the director is the caller that
component was written for.

**Each was written after finding the seam that appears when one component owns
two of those.** The aggro table exists because three separate components were
each privately deciding who was being hunted. The contact attack exists
because the pursuer stopped at melee range and nothing turned arrival into a
swing. The patrol route exists because a world where enemies stand still until
they see you is a world of statues.

### Measured, not asserted

Each piece was resolved **alone** and run for two simulated seconds with every
optional partner absent:

| Piece | Hard deps | Closure when asked for alone | Runs with optional partners absent |
|---|---|---|---|
| `combat.aggro_table` | 1 | 2 | yes |
| `movement.patrol_route` | 1 | 2 | yes |
| `combat.contact_attack` | 2 | 3 | yes |
| `combat.spawn_director` | 2 | 4 | yes |
| `movement.pursuit_agent` | 2 | 5 | yes |

Small closures and clean degradation are what "modular" has to mean here, and
they are checked rather than claimed. Removing `combat.aggro_table` leaves a
build that still runs — pursuit falls back to the nearest target and patrol
becomes unconditional — which is an acceptance criterion of the compound and
not a happy accident.

### The finding worth acting on

**`combat.unit_roster` is the hinge, and only 2 of 35 genres name it**
(`genre.action_rpg`, `genre.turn_based_tactics`). Every real-time combat piece
above depends on it, so in practice this kit is droppable into exactly those
two packs today — not because the pieces are entangled, but because almost no
genre pack declares a board for units to stand on.

That is a gap in the **packs**, not in the components. Dungeon Crawler, CRPG,
Roguelike, Survival Horror, Monster Taming, Open World and Battle Royale all
describe loops with hostiles in them and none of them names a roster. Adding
`combat.unit_roster` to a pack is what makes the whole kit available to it.

Do not resolve this by loosening the components' dependencies. A pursuer that
works without a roster is a pursuer that has invented a second place positions
live, which is the exact defect the roster was created to remove.

See **[building.md](building.md)** for the order to ask things in — whether a
concept is already owned, whether the owner can be extended rather than joined,
and what a new component has to record about having looked.

## Before building the next genre: ask what it already costs

```
python3 tools/compound_fit.py compound.real_time_encounter
python3 tools/compound_fit.py compound.real_time_encounter genre.dungeon_crawler
python3 tools/compound_fit.py --report reports/compound-fit.json
```

It **changes nothing**. Wiring a kit into a pack is a decision about that genre,
made when that genre is being built; a tool that quietly did it would be making
thirty-four such decisions on nobody's behalf. This reports the delta and stops.

It answers two questions about every compound against every genre, because a
cost with nothing to compare it to is just a number:

- **What is the relation?** How many of the kit's members the pack already
  names, out of how many. Five of six is a kit a pack nearly has; one of six is
  a kit it barely touches. Both are "5 to add" without the denominator.
- **Compared to what?** How the addition measures against the pack's own size.
  Four members is cheap against a pack of thirty and is a rewrite against a
  pack of eight.

It also reports, separately, how many of a kit's members have no reviewed
canvas2d implementation — because **adoptable and playable are different
questions**, and a pack that names three unimplemented components has adopted a
promise rather than a system.

Two readings from the first run worth keeping:

- `genre.crpg` is **one component** from `compound.party_quest_sharing_loop`
  (9% of its pack) — the cheapest grab in the catalogue.
- `genre.dungeon_crawler` names **none** of the real-time encounter kit, and
  adopting it would grow that pack by 67%. That is a signal about the pack, not
  the kit: a nine-component Dungeon Crawler is thin for a genre whose loop is
  entirely about fighting things in corridors.

## Adding a compound

1. Write the recipe in `compounds/`, naming a `role` for every member — the
   role is the reason that piece is in the kit, and a member without one is a
   member somebody added by association.
2. Write `acceptanceCriteria` as things a person could go and check. "A pack
   converges on distinct tiles rather than queueing" is checkable; "AI feels
   good" is not.
3. Include at least one criterion about what happens when an optional piece is
   REMOVED. A kit that only works assembled is not a kit.
4. Run `validate_compounds.py`. A connection whose event nobody emits, or
   nobody listens for, fails there — which is the point.
