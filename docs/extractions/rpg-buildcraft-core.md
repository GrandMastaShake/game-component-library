# RPG Buildcraft Core

Status: **validated library pack**  
Reusable output: `compound.rpg_buildcraft_loop`  
Content gate: `tools/validate_skill_trees.py`

## Purpose

Add the reusable decisions around RPG skill trees without creating another
generic node graph or embedding a particular game's classes and content. The
pack covers ranked purchases, prerequisites, exclusive branches, active-ability
loadouts, dependency-safe respecs, and persistence triggers. All tree, ability,
attribute, price, and balance data remains host supplied.

## The loop

```text
Experience and quests
  → level-up grants skill and attribute growth
  → ranked skill purchases publish passive bonuses
  → unlocked active abilities become loadout candidates
  → Ability Loadout binds the selected kit to Hotbar
  → Hotbar executes casts through existing combat owners
  → completed build changes trigger persistence

Optional rebuild:
  plan respec → confirm exact changes and price → pay currency
  → skill tree and attribute sheet reset their own state
  → Ability Loadout prunes newly ineligible actives
  → both owners acknowledge → respec completes → save
```

The central boundary is that **unlocking, selecting, executing, and rebuilding
are different responsibilities**. Combining them makes a skill tree into a
second combat system and makes respec especially prone to stale abilities and
duplicate refunds.

## Ownership map

| Decision | Library owner | Boundary |
|---|---|---|
| Experience and level growth | `progression.xp_leveling` | Already owns thresholds and level-up events. |
| Skill ranks and point spending | `progression.skills_tree` **extended** | Owns purchases, prerequisites, exclusive branches, and passive totals. |
| Attribute allocations and checks | `progression.attribute_sheet` **extended** | Owns attribute points, derived stats, and its own respec plan. |
| Active abilities in limited slots | `progression.ability_loadout` **new** | Owns selection and presets, not casting or cooldowns. |
| Cross-system rebuild transaction | `progression.build_respec` **new** | Owns confirmation, price, transaction id, and completion—not rank or attribute storage. |
| Respec affordability and payment | `economy.currency` | Synchronous `spend` call; no artificial payment event round trip. |
| Executable ability kit | `combat.hotbar_abilities` **extended** | Accepts complete loadout snapshots while retaining execution and cooldowns. |
| Damage and status outcomes | `combat.damage_resolver`, `combat.status_effects` | Existing combat owners remain unchanged. |
| Completed-change persistence | `persistence.save_system` **extended** | Saves successful changes, not rejected intentions. |

## Skills Tree 0.2.0

Legacy definitions remain valid. A node without the new fields is still a
one-rank, one-point unlock. New content may declare:

- `maxRank`: maximum purchasable rank, default 1.
- `costByRank`: exact point price for each rank, default 1 per rank.
- `prerequisites`: required node ids with optional minimum ranks.
- `exclusiveGroup`: nodes in which only one may hold ranks.
- `effect`: named modifiers applied per current rank.

The tree now publishes `ranks`, `available`, `lockedBy`, `spentPoints`, and a
pure `planRespec` query. Restored ranks are not revalidated against edited
content; new purchases always are. `initialUnlocked` remains supported, while
`initialRanks` restores ranked builds.

## Ability Loadout

Each active catalog entry names a `sourceNodeId` and optional `minRank`. The
loadout asks the tree whether that source is currently unlocked; it does not
copy the prerequisite engine. Slot restrictions and duplicate policy are
selection rules. Named presets apply all at once or not at all.

A rank loss or completed skill respec prunes newly ineligible entries. The
component then emits a complete `boundAbilities` snapshot, preventing Hotbar
from combining the new loadout with stale manual abilities.

## Build Respec

Respec is a transaction rather than a reset button:

1. Skills Tree and Attribute Sheet each produce a pure plan.
2. Partial skill plans either reject orphaned dependents or explicitly cascade
   them, according to configuration.
3. Build Respec calculates the currency price and stable plan hash.
4. The player confirms that exact plan when confirmation is enabled.
5. Currency spends synchronously; insufficient funds reject before mutation.
6. One `buildRespecRequested` transaction reaches the selected owners.
7. Each owner resets its own state, returns its own point type, and acknowledges
   the transaction id.
8. Build Respec completes once all expected acknowledgements arrive exactly
   once. Ability Loadout prunes and Save System records the completed result.

Skill points and attribute points remain separate even when a full respec
returns both. Runtime adapters must execute the paid request and expected
owner updates as one recoverable transaction; a partial acknowledgement set
must never become a second refund.

## Backward-compatible extensions

- **Skills Tree 0.2.0:** ranked content and respec support; legacy one-rank
  definitions retain their behavior.
- **Attribute Sheet 0.2.0:** explicit allocation, restored state, unspent
  points, and respec acknowledgement.
- **Hotbar Abilities 0.3.0:** `manualOrLoadout` remains the default;
  `loadoutOnly` requires complete loadout binding.
- **Save System 0.2.1:** additional completed build-change triggers; existing
  triggers and autosave behavior remain.

## Tree-content validator

```bash
python3 tools/validate_skill_trees.py
python3 tools/validate_skill_trees.py path/to/custom.tree.json --report reports/skill-trees.json
python3 -m unittest tools/tests/test_validate_skill_trees.py
```

The validator checks duplicate ids, unknown and cyclic prerequisites,
prerequisite rank bounds, rank-cost lengths and values, exclusive branches that
depend on their own excluded ancestors, and malformed named effects. Effectless
nodes remain legal because they can be titles, prerequisites, or active-ability
sources.

`examples/skill-trees/buildcraft-example.tree.json` is original generic content
used to demonstrate the format, not a class or balance recommendation.

## Acceptance scenarios

1. Legacy one-rank trees retain their purchase and restore behavior.
2. Rank purchases enforce level, prerequisite, exclusivity, cap, and cost rules.
3. Passive totals follow current ranks exactly without double application.
4. Restores tolerate edited content; new purchases do not bypass current rules.
5. Loadouts and presets reject locked, misplaced, or duplicate actives atomically.
6. Respec and rank loss prune stale actives and rebind Hotbar completely.
7. Partial respecs never silently orphan dependent nodes.
8. Insufficient currency rejects before any build mutation.
9. Transaction ids and acknowledgements cannot produce duplicate refunds.
10. Full respecs return skill and attribute points to their respective owners.
11. Rejected intentions do not trigger completed-change saves.
12. Respec and combat execution remain removable without breaking build planning.

## Deliberately deferred

- Class and subclass systems, specializations, and mastery capstones
- Triggered passive and synergy engines
- Skill augments, mutations, and behavior replacement
- Attribute-gated abilities and equipment requirements
- Loadout sharing, import/export strings, and build comparison UI
- Respec confirmation screens and price presentation
- Account-wide builds, multiplayer trading, and server migration
- Runtime adapters and transactional database implementations
- Commercial classes, skill names, content tables, and exact balance data

This delivery validates contracts, composition, and tree content only. New
runtime targets remain intentionally `unmapped`.
