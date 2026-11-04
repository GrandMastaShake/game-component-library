# RPG Status Effects & Crowd Control

Status: **validated library pack**
Reusable output: `compound.status_control_loop`
Content gate: `tools/validate_status_effects.py`
Original example: `examples/status-effects/mirelight.status.json`

## Purpose

Extend the existing timed-effect owner into a complete, reusable status and
crowd-control contract without creating another cast, movement, attack, damage,
turn, timer, capture, encounter, or persistence system.

The pack adds stable application identity, authored effect definitions, refresh
and stacking, independent instances, stat-modifier aggregation, tagged
immunities and cleanse, crowd-control facts, timer-generation expiry,
defeat/reset cleanup, and restoration. Existing hit-driven status application
remains available.

The Mirelight effects, targets, abilities, encounters, values, and scenarios are
original generic examples. No commercial names, writing, characters, content
tables, code, or balance data are included.

## The loop

```text
Hotbar / Contact Attack / Elite or Boss Telegraph
  → one ordinary combat.hit
  → Damage Resolver owns final damage and completed defeat
  → Status Effects owns effect and optional effectSeconds
  → Unit Roster retains unit, position, and health state

Explicit host application / legacy hit application
  → Status Effects
  → immunity + capacity + stable-id checks
  → new instance / refresh / stack / independent instance
  → Timer System owns finite countdowns
  → controlState + statModifiers published as facts

controlRestrictionsChanged
  → Hotbar decides cast rejection, cost, cooldown, and hit
  → Basic Walk decides continuous movement
  → Grid Movement Range decides reachable and attackable tiles
  → Contact Attack decides automatic strike cadence
  → Elite Telegraph Scheduler decides windup interruption

application / refresh / stack / removal
  → Capture Mechanic updates its own capture odds
  → Tactical Pause retains its existing edge-triggered pause policy
  → Save System records completed state changes

Defeat / unit removal / encounter failure or reset / restoration
  → scoped status cleanup or silent resume
  → no damage, reward, hit, pause, or capture replay
```

The central boundary is that **Status Effects owns effect state, not the verbs
that state restricts**. It does not reject a cast, move a unit, spend AP,
suppress a cooldown, calculate final damage, or roll capture odds. Each consumer
continues to own its own decision.

## Ownership map

| Decision | Library owner | Boundary |
|---|---|---|
| Effect instances and modifiers | `combat.status_effects` **extended to 0.2.0** | One owner for legacy ad-hoc and authored status state. |
| Countdowns and ticks | `utility.timer_system` | Stable status timer ids and generations; no private status clock. |
| Active casts | `combat.hotbar_abilities` **0.4.0** | Optional `cast` gate; still owns rejection, payment, cooldown, and hits. |
| Continuous movement | `movement.basic_walk` **0.2.0** | Optional `move` gate and speed multiplier; still owns locomotion. |
| Tactical movement and attack ranges | `movement.grid_movement_range` **0.2.0** | Optional range restrictions; pathfinding, AP, turns, and roster remain separate. |
| Automatic basic attacks | `combat.contact_attack` **0.2.0** | Optional `attack` gate; no private damage or status application. |
| Elite and boss windups | `combat.elite_telegraph_scheduler` **0.3.0** | Existing effect interruption plus newly added attack restriction. |
| Capture probability | `pets.capture_mechanic` **0.2.0** | Reads status changes; remains the only capture roll and resolution owner. |
| Real-time-with-pause state | `combat.tactical_pause` | Existing `effectApplied` behavior; refresh and stack events do not auto-pause. |
| Units, positions, and health | `combat.unit_roster` | Status never becomes a roster or health owner. |
| Final damage and completed defeats | `combat.damage_resolver` | Status consumes completed defeat cleanup; it does not resolve hits. |
| Elite and boss encounter scope | Existing directors | Their failure/reset/completion and `unitRemoved` events drive scoped cleanup. |
| Durable snapshots | `persistence.save_system` **0.2.5** | Application, refresh, stack, and removal triggers; rejected requests are not saves. |

An ownership search covered 323 descriptors. `combat.status_effects` was already
the clear timed-effect owner, so this pack extends it rather than introducing a
parallel crowd-control ledger.

## Status Effects 0.2.0

### Definitions

An authored effect declares:

| Field | Meaning |
|---|---|
| `id` | Stable effect id referenced by applications, immunities, and cleanse rules. |
| `durationSeconds` | Positive finite duration, or `null` for a permanent instance. |
| `stackPolicy` | `refresh`, `stack`, or `independent`. |
| `durationPolicy` | On an accepted existing-group application: `reset`, `extend`, `max`, or `ignore`. |
| `maxStacks` | Positive stack cap. Refresh and independent definitions use one. |
| `grouping` | Existing-instance matching by `targetEffect` or `targetEffectSource`. |
| `tags` | Stable content tags used by immunity and cleanse selectors. |
| `dispellable` | Whether any cleanse rule can remove the instance. |
| `cleansePriority` | Deterministic priority for ordered cleanse rules. |
| `removeOnDefeat` | Whether completed defeat clears the instance. |
| `modifiers` | Optional `{stat, operation, value, perStack}` records. |
| `control` | Optional `restrictions` and `moveMultiplier`. |

The supported control restrictions are `move`, `cast`, and `attack`. A `move`
restriction requires `moveMultiplier=0`, removing ambiguity between “blocked”
and “zero speed.” Other status tags remain host-defined content metadata.

Stat modifiers remain in this existing owner. `add` contributions sum and
`multiply` contributions compose in stable application order. `perStack=false`
contributes once per active instance; otherwise it contributes once per stack.
These are modifier facts, not final damage, roster health, or attribute state.

### Stable identity and application

An explicit `input.effectApplicationRequested` supplies at least:

```json
{
  "applicationId": "application.scout.slow.001",
  "effectId": "mire_slick",
  "targetId": "scout",
  "sourceId": "player",
  "encounterId": "mire_1"
}
```

`applicationId` is the replay and restoration identity. A duplicate id is a
silent no-op, whether its original result was acceptance or rejection. Accepted
refreshes record the new request id while retaining the active instance's
original `applicationId`. Events carry `requestedApplicationId` when those ids
differ.

For `refresh` and `stack`, `grouping` finds the existing instance. `independent`
always creates a separate instance and timer. New instances observe the
per-target `maxActiveEffects` cap; updates to an existing group do not. Capacity
never silently evicts an older effect.

### Legacy hit behavior

`unknownEffectPolicy=legacyAdHoc` is the default. A hit carrying `effect` and
optional `effectSeconds` still creates or refreshes an ad-hoc timed effect even
when no authored definition exists. `defaultLegacyEffectSeconds` supplies an
omitted duration. Existing Hotbar Abilities therefore need no new effect event
or second application pipeline.

For new replay-safe content, supply stable `applicationId` values on explicit
requests or hit metadata. A legacy hit with no stable id retains legacy behavior;
it does not gain a fabricated cross-save dedupe guarantee. Authored packs can use
`unknownEffectPolicy=reject` to reject undeclared effect ids.

### Refresh, stacks, and durations

A new instance emits `combat.effectApplied`. An existing-group duration-only
update emits `combat.effectRefreshed`; an increment emits
`combat.effectStacked`. At the stack cap, an accepted application may still
refresh duration but emits `effectRefreshed`, not another stack event.

Every accepted refresh or stack advances the instance's timer `generation`.
Duration policies behave as follows:

- `reset`: use the incoming duration;
- `extend`: add incoming duration to current remaining time;
- `max`: keep the longer of current and incoming;
- `ignore`: retain current remaining time while still invalidating stale timers.

Permanent instances remain permanent under `reset`, `extend`, and `max`.

### Control and modifier queries

`controlFor(unitId)` and `modifiersFor(unitId)` are synchronous reads of the same
state published as `controlState` and `statModifiers`. Consumers can query the
owner rather than maintaining a private status ledger.
`controlRestrictionsChanged` is a change notification for event-driven hosts.

Restrictions union across active instances. Movement multipliers compose
multiplicatively; a stacked multiplier applies once per stack. Removing one
instance recomputes the aggregate from those that remain.

## Cleanse and immunity

An immunity rule has stable `id`, non-empty `targetIds`, and at least one of
`effectIds` or `tags`. A matching target/effect pair is rejected with reason
`immunity` before capacity, timers, modifiers, restrictions, or active state
change.

A cleanse rule has stable `id`, effect/tag selectors, positive `maxEffects`, and
one ordering:

- `highestPriority` or `lowestPriority`, with oldest insertion as the tie-break;
- `oldest` or `newest` by stable insertion order.

Effect-id and tag selectors are unioned. Only dispellable candidates on the
requested target are eligible. `input.effectCleanseRequested` requires a stable
`cleanseId`, target, and rule. Each selected instance emits `effectCleansed` and
the generic `effectRemoved`. Replaying the cleanse cannot remove a later effect.

Explicit manual removal uses a stable `removalId` and emits only the generic
removal with reason `manual`. Expiry and defeat have their own concrete reasons.

## Consumer behavior

All restriction consumers default to `controlRestrictionMode=ignore`. This is
the compatibility switch: a build that does not opt in keeps its prior behavior.

### Hotbar Abilities

With `statusGate`, `cast` on the caster produces the existing
`combat.abilityRejected` with reason `controlRestricted`. Rejection occurs before
resource payment or cooldown and emits neither `abilityCast` nor `combat.hit`.
Clearing control does not cast a queued ability by itself.

### Basic Walk and Grid Movement Range

Basic Walk blocks `moveExecuted` for a move-restricted body and emits its
existing `movement.blocked` with reason `controlRestricted`. Facing and aiming
remain available. A positive multiplier scales walk speed.

Grid Movement Range reduces a move-restricted unit's reachable set to its current
tile. A multiplier scales the movement budget before flood fill. An `attack`
restriction makes `attackableTiles` empty. Neither component spends AP or moves
the roster merely because control changed.

### Contact Attack and telegraphs

Contact Attack suppresses `contactMade` and `hit` while the attacker has
`attack`. It does not spend or restart a ready cooldown, so clearing control does
not require another waiting period.

Elite Telegraph Scheduler retains `interruptEffects`; the example configures
`staggered` and `bound_steps`. A newly added `attack` restriction also cancels an
active windup with reason `interrupt`, no hit, and the existing cooldown policy.
A refresh does not masquerade as a new application, and removing control never
commits an attack.

### Capture and Tactical Pause

Capture Mechanic updates odds on application, refresh, stack, and generic
removal. It still owns probability, attempt state, deterministic shake
presentation, and resolution. Restored or replayed status events do not reroll a
decided attempt.

Tactical Pause continues listening to `effectApplied` only. Its existing
edge-triggered running-to-paused behavior and default-off status auto-pause are
unchanged; refresh and stack events cannot cause pause storms.

## Defeat, encounter cleanup, and restoration

Completed defeat removes instances whose definitions declare `removeOnDefeat`.
Silent `unitRemoved` clears the removed unit's transient status without creating
a completed defeat, XP, mastery, loot, or capture result.

Elite failure/reset and boss completion/failure/reset clear instances carrying
the matching `encounterId`. Events for another encounter are inert. Generic
removal reasons distinguish `defeat`, `encounterReset`, `expired`, `cleansed`,
and `manual` for telemetry and tests.

`initialState` restores active instances, timer ids and generations, processed
application/cleanse/removal ids, and control state. Restoration emits no
historical application, refresh, stack, cleanse, removal, control, pause, hit,
or capture events. A restored old timer completion is checked against the
current generation and cannot remove newer state.

## Original Mirelight content

The example contains eight effects and eight executable scenarios:

- refresh resets duration without a second application;
- three-stack cap and extend behavior;
- independent ember marks with separate identities;
- tagged mind immunity;
- priority cleanse and cleanse replay;
- stacked movement multipliers and full control union;
- defeat and encounter-scoped reset;
- snapshot restoration and historical-event replay.

The validator also rejects malformed durations, policies, duplicate ids,
unknown references, invalid modifiers, unsupported restrictions, empty cleanse
selectors, and bad scenario operations. Its reference model is a content test
oracle, not another runtime component or an implementation claim.

Run:

```bash
python3 tools/validate_status_effects.py --report reports/status-effects.json
python3 -m unittest tools.tests.test_validate_status_effects -v
```

## Compound and adoption

`compound.status_control_loop` contains 28 components, 90 validated connections,
and 18 acceptance criteria. It includes complete hard-dependency closure for
continuous and tactical movement, ordinary damage, elite/boss telegraphs,
capture, timers, and saving. Configs use the original Mirelight content and opt
into `statusGate`; removing that opt-in restores legacy consumer behavior.

Genre adoption updates:

- **CRPG**: refresh-safe RTwP status, cast/movement control, and boss interruption;
- **Action RPG**: real-time cast, movement, contact-attack, and elite control;
- **Turn-Based Tactics**: status-scaled reachable/attackable tiles with existing AP and turns;
- **Monster Taming**: live status application, refresh, stacking, and removal feeding capture odds.

These are reusable system contracts and original examples, not assertions that a
particular commercial game uses this exact stacking or numeric model.

## Deferred systems

This pack does not add charm/faction conversion, forced targeting, confusion
retargeting, terrain creation, damage-over-time final calculations, saving throws,
resistance curves, AI spell selection, aura acquisition, or a new turn sequencer.
Those need their existing owners or separately approved contracts. In particular,
Damage Resolver continues to own final damage and Turn Order Queue continues to
own sequencing.

## Validation

```bash
python3 tools/validate_component_graph.py --report reports/component-graph.json
python3 tools/validate_compounds.py --report reports/compound-validation.json
python3 tools/validate_genres.py --report reports/genre-validation.json
python3 tools/validate_status_effects.py --report reports/status-effects.json
python3 -m unittest discover -s tools/tests -p 'test_*.py'
```

The CI workflow also includes `examples/**/*.status.json` path triggers and the
status-content validator before the complete validator unit-test suite.
