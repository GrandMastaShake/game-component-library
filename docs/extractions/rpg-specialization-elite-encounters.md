# RPG Specialization, Masteries & Elite Encounters

Status: **validated library pack**
Reusable output: `compound.specialization_elite_loop`
Content gate: `tools/validate_specialization_elites.py`

## Purpose

Connect durable build identity and gameplay-earned proficiency to readable,
deterministic elite challenges without creating second skill, spawn, damage,
loot, or timer authorities. The pack covers specialization selection, ranked
mastery tracks, gated actives, enemy affixes, finite waves, interruptible
telegraphs, stable defeat metadata, existing XP and loot outcomes, restoration,
and cross-content validation.

All identities, skills, abilities, affixes, attacks, encounters, items, writing,
and balance data remain host supplied. The included disciplines and crossing
encounters are original generic examples, not commercial content or tables.

## The loop

```text
XP Leveling → level and skill growth
Skills Tree + Specialization → gated build identity and passive modifiers
Mastery sources → deduplicated proficiency XP → derived ranks and modifiers
Ability Loadout → source-rank + specialization + mastery gates → Hotbar

Elite Encounter Director
  → Enemy Tier Scaling for base spawn stats
  → Elite Affixes for deterministic enemy modifiers and special attacks
  → Unit Roster for the only board-state write

Elite Telegraph Scheduler + Aggro Table + Timer System
  → locked-target windup → Intent Marks projection
  → interrupt / defeat / reset cancellation, or one commit
  → ordinary combat.hit → Damage Resolver + Status Effects

Damage Resolver entityDefeated
  → owning encounter wave + character XP + mastery + Drop Director

Drop Director → Affix Loot Generator → Slotted Bag / Core Inventory
Completed changes → Save System → each owner restores without replaying effects
```

The central boundary is that **identity, proficiency, encounter composition,
attack timing, combat resolution, and rewards are different responsibilities**.
A specialization that buys ranks becomes a second skill tree. An affix roller
that spawns units becomes a second encounter director. A telegraph that computes
mitigation becomes a second damage resolver.

## Ownership map

| Decision | Library owner | Boundary |
|---|---|---|
| Character XP and levels | `progression.xp_leveling` | Existing growth events and character thresholds. |
| Skill ranks and point refunds | `progression.skills_tree` **extended** | Optional specialization gates for new purchases; legacy nodes unchanged. |
| Durable build identity | `progression.specialization` **new** | Selection, prerequisites, exclusivity, and named modifiers; no rank purchases. |
| Gameplay-earned proficiency | `progression.mastery` **new** | Track XP, dedupe ledger, derived ranks, and modifiers; no character XP or loot. |
| Active-slot assignment | `progression.ability_loadout` **extended** | Combined skill, specialization, mastery, slot, and duplicate gates. |
| Ordinary rebuilds | `progression.build_respec` | Existing skill/attribute transaction; specialization and mastery survive. |
| Base enemy level curve | `combat.enemy_tier_scaling` | Existing synchronous spawn-time stat query. |
| Enemy affix selection | `combat.elite_affixes` **new** | Deterministic legal enemy modifiers and attack definitions; no item affixes. |
| Finite elite waves | `combat.elite_encounter_director` **new** | Stable unit ledgers, wave progression, completion, failure, and reset. |
| Board state | `combat.unit_roster` **extended** | Preserves spawn metadata and remains the only unit/health/position owner. |
| Elite attack timing | `combat.elite_telegraph_scheduler` **new** | Cooldown, locked-target windup, interruption, and commit; no final damage. |
| Targets and time | `combat.aggro_table`, `utility.timer_system` | Existing targeting and countdown owners. |
| Warning presentation | `presentation.intent_marks` **extended** | Removable projection of active telegraphs; no timing or hit rules. |
| Final damage and defeats | `combat.damage_resolver` **extended** | Existing damage pipeline plus stable encounter metadata on defeat. |
| Drops and item quality | `inventory.drop_director`, `inventory.affix_loot_generator` | Existing eligibility and item-affix rolls. |
| Storage | `inventory.slotted_bag`, `inventory.core_inventory` | Existing capacity and carried-item authority. |
| Durable snapshots | `persistence.save_system` **extended** | Saves completed changes, not rejected intentions or cancelled hits. |

## Specialization 0.1.0

A specialization definition declares:

- `id` and `name`;
- optional `requiredLevel` and `requiredSkills`;
- optional `requiresSpecializations` and `exclusiveGroup`;
- optional named `effect` modifiers granted while selected.

Selection is additive up to `maxActive`. With the default `selectionLocked`, a
full selection cannot be replaced through the ordinary input. If replacement is
enabled, the complete resulting selection is validated atomically. A rejected
request changes nothing.

`initialSelected` restores identity without revalidating edited content or
emitting another selection. New selections still validate current rules.
Specialization publishes `isActive`, `available`, `lockedBy`, and summed
`bonuses`; it never reaches into combat calculations.

Skills Tree 0.3.0 adds optional node-level `specialization` gating. The default
`whenDeclared` mode checks only nodes that declare the field. Restore never
deletes ranks because a gate changed. Build Respec rebuilds ranks and attributes
while preserving the selected identity and all mastery XP.

Ability Loadout 0.2.0 adds optional `specialization`, `masteryTrack`, and
`minMasteryRank` gates to its existing source-node rule. An active must satisfy
every declared gate before assignment. `lockedAbilities` explains why one is
unavailable.

## Mastery 0.1.0

Each track declares strictly increasing XP `thresholds`, one optional modifier
object per rank, and one or more completed-event sources. A source contains:

- a supported `event`;
- optional scalar `match` payload checks;
- fixed `amount` or payload `amountFrom`;
- required `dedupeBy`, naming a stable id such as `castId`, `defeatId`, or
  `completionId`.

A track may also require an active `specialization`. Inactive tracks do not
accept new credit. One completed fact can credit multiple matching tracks, but
the same stable id can credit a given track only once.

Ranks derive from XP and thresholds. `initialXp` restores the authoritative XP;
`initialCreditIds` restores the dedupe ledger. Restoration emits no historical
XP or rank-up events. Ordinary Build Respec does not reset mastery.

Mastery modifiers remain named data for the owners of the affected stats.
Mastery does not grant character XP, purchase a skill, choose an item, or fire
an achievement.

## Elite Affixes 0.1.0

Affixes are enemy modifiers, not item affixes. Each definition may declare:

- weighted random selection and a threat band;
- required and excluded affix ids;
- spawn-time `statMultipliers` and AI/attack `behaviorModifiers`;
- special `attacks` with windup, cooldown, base damage, and warning shape.

`assign({encounterId, waveId, unitId, threat, affixCount?, affixIds?})` returns a
complete record. Explicit ids support curated elites; omitted ids use the seed
and stable unit identity. Prerequisite closure must fit the requested count and
`maxAffixes`; exclusions and threat bands are mandatory.

`initialAssignments` restores the complete record by `eliteInstanceId`, so a
reload cannot reroll a more favorable enemy. Elite Encounter Director composes
the multipliers with level scaling once at spawn. Damage Resolver never applies
them again per hit.

## Elite Encounter Director 0.1.0

An encounter declares an arena, level, threat, and ordered waves. Wave units may
be normal support or elite. Elite entries use `affixCount` for a deterministic
roll or `affixIds` for a curated set.

Stable unit ids include encounter, wave, archetype, and index. Unit Roster 0.2.0
preserves `spawnId`, `encounterId`, `waveId`, `tier`, `affixIds`, and
`masteryTags`. Damage Resolver 0.2.1 propagates those fields and a stable
`defeatId` through `entityDefeated`.

The director advances only for defeats belonging to the active wave. A later
wave cannot start while any spawned unit from the current wave remains. Final
wave completion emits one stable `completionId`; `allowReplay=false` rejects a
second start. Player-team elimination emits failure, not completion.

Reset removes living encounter units through `unitRemoved`. That path cannot
grant XP, mastery, loot, or a false defeat. Restoring director state does not
spawn units or emit completion; Unit Roster restores corresponding units and
health independently.

## Elite Telegraph Scheduler 0.1.0

Assigned special attacks register with the scheduler. Cooldowns and windups use
Timer System. At windup the scheduler reads the caster's current Aggro Table
target and locks it for that attack. Intent Marks displays the shape, target,
and remaining time.

A commit emits:

1. `combat.attackCommitted` for presentation and persistence;
2. one ordinary `combat.hit` containing the declared base payload.

Damage Resolver computes final damage and Status Effects owns timed effects.
Declared interrupt effects, caster defeat, target defeat, missing targets, and
encounter reset cancel without a hit. Restored timers never produce a catch-up
hit storm.

This contract currently locks a single target. Movement-based dodging,
multi-target area resolution, and destructible warning geometry are deliberately
outside this pack rather than implied by the warning shape.

## Rewards and persistence

One elite defeat may independently advance:

- its owning encounter wave;
- character XP through XP Leveling;
- matching mastery tracks through stable `defeatId` dedupe;
- drop eligibility through Drop Director.

Elite encounter completion may separately credit mastery through its stable
`completionId`. Drop Director retains elite drop chances and roll counts.
Affix Loot Generator remains in `onRequest` mode, and Slotted Bag/Core Inventory
retain item-capacity authority.

Save System 0.2.3 listens for completed specialization, mastery, affix
assignment, encounter, telegraph, and existing build/inventory changes. Rejected
selections, duplicate mastery facts, invalid assignments, stale defeats, and
cancelled attacks do not masquerade as completed rewards.

## Content validator

```bash
python3 tools/validate_specialization_elites.py
python3 tools/validate_specialization_elites.py path/to/content path/to/trees --report reports/specialization-elites.json
python3 -m unittest tools/tests/test_validate_specialization_elites.py
```

The default bundle includes `examples/specialization-elite` and
`examples/skill-trees`:

- `disciplines.specialization.json`: three identities, three mastery tracks,
  and four gated actives linked to the existing eight-node example tree.
- `crossing.elite.json`: five affixes and two encounters across three waves,
  including curated and deterministic affix assignments.

The validator checks:

- duplicate specialization, mastery, ability, affix, encounter, and wave ids;
- unknown, self-referential, cyclic, and exclusive-conflicting prerequisites;
- required skill and active source-node references and their rank bounds;
- mastery thresholds, rank effects, source events, scalar matches, amounts, and
  stable dedupe fields;
- active specialization and mastery references and rank bounds;
- affix threat bands, requirement closure, exclusions, slot caps, modifiers,
  attacks, and warning shapes;
- encounter wave and unit shapes, elite presence, affix counts, explicit curated
  combinations, and cross-file consistency.

When custom validation paths contain no tree files, skill references are checked
for shape only and the report warns about that reduced check.

## Compound and genre adoption

`compound.specialization_elite_loop` contains 25 components and 58 validated
wires. Its dependency closure is represented, including Core Inventory under
Slotted Bag and Unit Roster under Aggro Table and the encounter director.

CRPG and Action RPG both name every member. Existing genre content remains
valid: specialization and mastery gates are opt-in, enemy affixes are separate
from item affixes, and legacy spawn, boss, damage, and loot paths remain intact.

## Acceptance scenarios

1. Legacy skill and loadout content behaves identically without the new gates.
2. Invalid specialization selections and replacements change nothing.
3. Ordinary respecs preserve specialization and mastery.
4. Duplicate or restored gameplay facts cannot grant mastery twice.
5. Every active satisfies all declared skill, identity, and proficiency gates.
6. Identical seeds and stable ids reproduce legal affix assignments.
7. Current-wave defeats alone advance an encounter, and completion is once-only.
8. Failure and reset cannot synthesize XP, mastery, loot, or completion.
9. Every elite special has readable windup and commits at most one ordinary hit.
10. Interrupts, defeats, missing targets, and reset cancel without damage.
11. Removing Intent Marks leaves combat behavior unchanged.
12. Existing damage, status, drop, item-generation, and capacity owners retain
    their authority.
13. Restoration cannot reroll elites or replay selections, ranks, waves, hits,
    or encounter rewards.
14. Broken cross-content links and impossible affix sets fail before runtime.

## Deliberately deferred

- Runtime adapters and concrete engine/UI implementations
- Movement-based dodge and multi-target area-hit resolution for telegraphs
- Specialization-changing respec transactions and mastery-reset policy
- Multiplayer encounter authority and contested target ownership
- Procedural quest generation, timed encounters, and commercial balance tables
- Voice, cinematics, animation, and specialized enemy presentation
- Transactional overflow policy for full item storage

This delivery validates contracts, composition, and original content only. New
runtime targets remain intentionally `unmapped`.
