# RPG Boss Phases & Arena Hazards

Status: **validated library pack**
Reusable output: `compound.boss_arena_mastery_loop`
Content gate: `tools/validate_boss_arenas.py`

## Purpose

Complete the reusable build identity → mastery → elite → boss spine without
creating a second boss, spawn, timer, damage, hazard-contact, door, loot, or
persistence owner. The pack adds stable health-, time-, and condition-driven
boss phases, once-only adds, readable boss attacks, boss-driven arena hazards,
enrages, failure, reset, restoration, and exactly-once completion.

The included Foundry Heart and Archive Custodian encounters are original generic
examples. All bosses, attacks, hazards, conditions, writing, items, and balance
remain host supplied; no commercial content or tables are included.

## The loop

```text
Specialization + Skills + Mastery + Ability Loadout
  → the existing build identity and proficiency spine

Elite Encounter Director → elite waves → ordinary defeats
Boss Encounter Script → boss + stable phase adds → ordinary defeats

Boss engagement / phase / enrage
  → Elite Telegraph Scheduler → locked-target windup → one ordinary hit
  → Arena Hazards → warning → armed Hazard Volumes
  → Intent Marks as a removable warning projection

Hazard Volume contact
  → Arena Hazards observes the contact
  → Damage Resolver optionally resolves nonlethal contact damage
  → Character Body independently owns position/respawn policy

Damage Resolver entityDefeated
  → Boss Encounter Script resolution
  → character XP + defeat mastery + Drop Director

Boss completion with stable completionId
  → optional once-only completion mastery
  → Boss Room Seal + arena/telegraph cleanup + Save System

Failure / reset / post-boss cleanup
  → unitRemoved, never entityDefeated
  → no XP, mastery, loot, completion, or room-clear reward
```

The central boundary is that **encounter phase, attack timing, arena scheduling,
contact, final damage, room state, and rewards are different responsibilities**.
A boss director that applies hazard damage becomes a second damage resolver. An
arena script that seals doors becomes a second room owner. A completion listener
that manufactures another defeat duplicates every reward consumer.

## Ownership map

| Decision | Library owner | Boundary |
|---|---|---|
| Build identity and proficiency | `progression.specialization`, `progression.mastery` | Existing build spine; Mastery now accepts stable boss completion sources. |
| Boss engagement and phases | `combat.boss_encounter_script` **extended** | Health/time/condition transitions, enrage, adds, completion, failure, and reset. |
| Boss and add board state | `combat.unit_roster` **extended** | The only unit, position, and health owner; preserves phase metadata. |
| Base spawn level curve | `combat.enemy_tier_scaling` | Existing synchronous spawn-time stat query. |
| Elite and boss attack timing | `combat.elite_telegraph_scheduler` **extended** | Cooldowns, windups, interruption, phase replacement, and one ordinary hit. |
| Targets and time | `combat.aggro_table`, `utility.timer_system` | Existing targeting, tick, and countdown authorities. |
| Arena schedule | `world.arena_hazards` **extended** | Boss-driven hazard phases, warnings, arming, disarming, and restoration. |
| Hazard contact | `world.hazard_volume` **extended** | Stable contact reports only; never health or match rules. |
| Warning presentation | `presentation.intent_marks` **extended** | Removable boss telegraph and arena hazard projections. |
| Final damage and defeats | `combat.damage_resolver` **extended** | Ordinary hits plus opt-in nonlethal hazard-contact resolution. |
| Timed effects | `combat.status_effects` | Existing timed-modifier ledger; enrage does not become a status effect. |
| Room seal and clear fact | `world.boss_room_seal` **extended** | Doors, retry reopening, durable clear state, and restoration. |
| World conditions | `world.world_state_flags` | Existing durable facts that may satisfy a declared boss phase. |
| Character XP and drops | `progression.xp_leveling`, `inventory.drop_director` | Existing consumers of the same ordinary boss defeat. |
| Completion mastery | `progression.mastery` **extended** | Optional stable `completionId` credit, independent of defeat XP and loot. |
| Durable snapshots | `persistence.save_system` **extended** | Completed boss and arena changes, not rejected or cancelled intentions. |

Room Encounters remains the fixed floor-cast owner and is not included in this
scripted boss composition. The boss director announces its own boss and phase
adds; Unit Roster remains the only component that admits them to the board.

## Boss Encounter Script 0.4.0

Legacy `phaseThresholds`, `initialBeaten`, floor outputs, and reset behavior remain
available when `encounters` is empty. A scripted encounter declares:

- `id`, `arenaId`, and `level`;
- a `boss` with `archetype`, `maxHealth`, optional `socket`, and `masteryTags`;
- ordered `phases` with stable ids;
- optional `enrage` with `afterSeconds`, replacement attacks, behavior modifiers,
  and a hazard phase.

The first phase enters on engagement. Every later phase declares exactly one
`enterWhen` kind:

```json
{"healthAtOrBelow": 0.66}
```

```json
{"elapsedSecondsAtLeast": 75}
```

```json
{
  "conditionEvent": "world.worldFlagChanged",
  "conditionMatch": {"flag": "foundry.coolantReleased", "value": true},
  "conditionId": "coolant-released"
}
```

Condition phases may instead use `progression.questStageChanged` or the explicit
`input.bossConditionSatisfied` host input. Matches are scalar payload equality
checks. A condition for another encounter, a repeated condition, or a condition
for a phase that is not next changes nothing.

Health thresholds descend and elapsed-time triggers increase in declaration
order. Only the next phase can enter. The state ledger records entered phases,
satisfied conditions, spawned and defeated units, elapsed time, enrage, and
completion. Restoration accepts that ledger without replaying its events.

### Adds and stable identity

A phase may declare adds with `archetype`, `count`, `baseHealth`, optional
`socket`, and `masteryTags`. Stable spawn ids include encounter, phase,
archetype, and index. Unit Roster preserves `encounterId`, `phaseId`, `spawnId`,
`tier`, `archetype`, and mastery metadata; Damage Resolver propagates it only on
a completed defeat.

A repeated phase entry cannot spawn another copy. Failure, reset, and cleanup of
living adds after boss completion use `unitRemoved`. Those removals cannot
produce XP, mastery, loot, or a room-clear fact.

### Enrage, failure, and completion

Timer System owns the enrage countdown. Enrage enters once, publishes optional
replacement attacks and behavior modifiers, and may select an arena hazard
phase. It does not apply timed effects or final damage.

Player-team elimination emits failure. Reset emits reset. Both cancel attacks
and hazards and may reopen the room for retry. Neither completes the encounter.
Failed and reset encounters may retry; `allowReplay=false` rejects a completed
encounter start.

A matching boss `entityDefeated` emits both the existing `bossDefeated` fact and
one `bossEncounterCompleted` containing a stable `completionId`. The ordinary
defeat remains the single source for character XP, defeat-based mastery, and
Drop Director. Completion-based mastery is an optional separate source deduped
by `completionId`.

## Telegraph Scheduler 0.2.0

Boss attacks use the existing elite scheduler rather than a boss-specific timing
system. Initial phase attacks register on `bossEngaged`; later phases register on
`bossPhaseChanged`; optional enrage attacks register on `bossEnraged`.

A new boss phase replaces that boss's previous attack set. Old windups cancel
without a hit. Elite registrations for other casters remain independent.

At windup the scheduler reads Aggro Table and locks the current target. Commit
emits one `attackCommitted` and one ordinary `combat.hit`. Damage Resolver owns
mitigation, crit, variance, and defeat; Status Effects owns timed effects.
Interrupts, caster or target defeat, phase replacement, failure, reset, and
completion cancel without a hit. Restored timers do not produce catch-up hits.

Single-target locking remains the current contract. Movement-based dodging and
multi-target area resolution are not implied by an attack's warning shape.

## Arena Hazards 0.2.0

Legacy `phaseScript`, `phaseIntervalSeconds`, and automatic escalation are
unchanged by default. `activationMode=bossDriven` instead uses arena definitions:

- stable `hazards` with regions, damage intent, retrigger time, and lethality;
- stable `phases` with `arm`, `disarm`, optional `mutate`, and a positive
  `warningSeconds` for every arming phase.

The boss phase's `hazardPhase` refers to this script. Engagement selects the
initial phase; boss phase changes and enrage select later phases. Completion,
failure, and reset disarm the arena. Unknown or stale phase events are rejected.

Arena Hazards emits `arenaHazardTelegraphed`, waits on Timer System, then emits
`arenaHazardTriggered` and arms the volumes. It never performs collision or
writes health. Hazard Volume emits a stable `contactId` from hazard, body, and
contact ordinal.

Damage Resolver's default `hazardDamageMode=ignore` preserves existing host
policy. The compound opts into `contactDamage`, which resolves nonlethal,
positive-damage contacts through the same final-damage pipeline and deduplicates
contact ids. It does not re-emit `combat.hit`. Instantly lethal contacts remain
host policy rather than an implicit boss-pack rule.

Intent Marks displays pending and armed hazards as a removable projection.
Removing it changes no timer, contact, damage, encounter, or reward behavior.

## Boss Room Seal 0.2.0

Boss Room Seal remains the door and durable clear-fact owner. It can clear from
an ordinary boss defeat or the scripted completion event idempotently. Optional
failure and reset reopening supports retries without setting `bossDefeated`.

`initialSealed` and `initialBossDefeated` restore room state without emitting a
historical seal or clear event. The boss director reports engagement but never
writes door state.

## Rewards and persistence

One real boss defeat can independently advance:

- the owning boss encounter;
- character XP through XP Leveling;
- defeat-based mastery through stable `defeatId` dedupe;
- drop eligibility and roll counts through Drop Director.

One boss completion can separately credit a matching mastery track through its
stable `completionId`. Drop Director retains boss drop chances and roll counts;
Affix Loot Generator, Slotted Bag, and Core Inventory keep their existing item
and capacity responsibilities.

Save System 0.2.4 listens for completed boss engagement, phase, enrage,
completion, failure, reset, and arena warning/arm/reset changes. Restoring each
owner does not replay selections, spawns, attacks, contacts, hazards, room
clears, completion mastery, XP, or drops.

## Content validator

```bash
python3 tools/validate_boss_arenas.py
python3 tools/validate_boss_arenas.py path/to/boss-content --report reports/boss-arenas.json
python3 -m unittest tools/tests/test_validate_boss_arenas.py
```

The default original bundle contains:

- two arenas and four nonlethal hazards;
- two bosses across eight stable phases;
- health, elapsed-time, world-flag, and explicit-condition transitions;
- once-only adds, phase attacks, hazard escalation, and two enrages.

The validator checks duplicate and cross-file arena/encounter ids, arena links,
regions, hazard references, readable arming warnings, arm/disarm conflicts,
phase order, transition kinds and ranges, scalar condition matches, stable
condition ids, add shapes, boss stats, attack timing and shapes, enrage timing,
modifiers, and encounter-wide attack identity. Malformed nested values return
validation errors rather than crashing.

The specialization/elite validator also accepts
`combat.bossEncounterCompleted` mastery sources. The example `elite_hunter`
track includes an optional Glassworks boss-completion source alongside its
existing elite defeat and completion sources.

## Compound and genre adoption

`compound.boss_arena_mastery_loop` contains 44 components and 102 validated
wires. It includes the complete dependency closure for the existing behavior,
pathfinding, room-seal, map, movement, hazard, progression, loot, and save
owners rather than hiding required pieces.

CRPG and Action RPG both name all 44 members. The original
`compound.specialization_elite_loop` remains available for games that want the
smaller build-and-elite slice without bosses.

## Acceptance scenarios

1. Legacy threshold bosses and automatic arena hazards behave as before.
2. Health, time, and condition triggers enter only the next stable phase.
3. Repeated conditions and phase entries cannot duplicate adds or attacks.
4. Boss attacks use readable windups and commit at most one ordinary hit.
5. Interrupts, phase replacement, failure, reset, and completion cancel safely.
6. Hazard phases warn before arming and never own contact or damage.
7. Opt-in hazard damage uses Damage Resolver and stable contact dedupe.
8. Enrage fires once without becoming a timed status or damage pipeline.
9. One boss defeat produces one completion and feeds existing reward owners.
10. Failure, reset, replay rejection, and add cleanup grant no completion rewards.
11. Boss Room Seal alone owns doors and retry/clear state.
12. Restoration cannot replay phases, spawns, hits, hazards, clears, or rewards.
13. Removing Intent Marks leaves combat and encounter behavior unchanged.
14. Removing the boss slice leaves buildcraft, mastery, elites, and loot intact.
15. Broken cross-content links and unreadable encounters fail before runtime.

## Deliberately deferred

- Runtime adapters and concrete engine/UI implementations
- Movement-based dodge and multi-target area-hit resolution for telegraphs
- Instantly lethal hazard policy beyond contact reporting
- Multiplayer boss authority, contested resets, and shared completion policy
- Destructible arena geometry and procedural boss generation
- Cinematics, voice, animation, and specialized boss presentation
- Commercial encounters, writing, item tables, and balance data
- Transactional overflow policy for full item storage

This delivery validates contracts, composition, and original content only. New
runtime targets remain intentionally `unmapped`.
