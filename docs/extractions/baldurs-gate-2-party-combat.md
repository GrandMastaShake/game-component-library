# Extraction: Baldur’s Gate 2 Party Combat

Status: **validated library pack**  
Reference: classic isometric real-time-with-pause party combat  
Reusable output: `compound.party_rtwp_combat`

## Purpose

Extract the reusable combat decisions behind the reference loop, not its
proprietary implementation or content. This pack contains no character names,
spell names, rule tables, artwork, audio, maps, dialogue, copied code or exact
balance data. Its contracts are original and genre-level so they can support
other tactical party games.

## The loop being extracted

```text
Party explores in continuous time
  → hostile detection creates aggro
  → manual input or configured auto-pause stops simulation time
  → player queues movement and prepared-spell orders per party member
  → resume releases orders in deterministic order
  → Command Bus dispatches player and AI requests through one channel
  → prepared spellbook authorizes eligible casts
  → Hotbar validates execution and emits ordinary hits
  → damage, status, positions and defeat update through existing owners
  → completed rest restores prepared casts; interrupted rest does not
```

The important design insight is that **pausing time, remembering intentions,
and executing actions are three different responsibilities**. A single
“RTwP controller” that owned all three would be difficult to reuse in a
cooldown-based RPG, a party game without prepared spells, or a game with a
different command UI.

## Ownership map

| Reference pattern | Library owner | Why this boundary |
|---|---|---|
| Durable party membership | `social.party_system` | Already owns who belongs to the party. |
| Active character and march arrangement | `social.party_formation` | Already owns control handoff and formation, not combat orders. |
| Live combatants, sides, positions and health | `combat.unit_roster` | One authoritative encounter board. |
| Detection, threat and target memory | `combat.aggro_table` | Already owns noticing and target choice. |
| Continuous-time pause and auto-pause policy | `combat.tactical_pause` **new** | Pause is a clock state, not a turn queue or command list. |
| Per-member orders held across pause | `combat.party_command_queue` **new** | Intentions need a lifetime independent of their executors. |
| Ordered command dispatch | `utility.command_bus` | Player and AI requests share ordering and backpressure. |
| Autonomous behavior intentions | `utility.behavior_fsm` | Already emits command requests without mutating entities. |
| Walkable movement routes | `movement.pathfinding_system` | Now accepts move-kind commands from the common bus. |
| Continuous pursuit and position updates | `movement.pursuit_agent` | Already executes real-time chase orders. |
| Enemy melee cadence | `combat.contact_attack` | Already turns pursuit arrival into ordinary hit events. |
| Known, prepared and remaining spells | `combat.prepared_spellbook` **new** | Preparation and rest recovery are distinct from cast execution. |
| Range, cooldown, resources and cast hits | `combat.hotbar_abilities` | Extended with opt-in authorized-only casting. |
| Final damage and defeat | `combat.damage_resolver` | Spell and melee hits share one damage authority. |
| Timed effects | `combat.status_effects` | Already consumes the ordinary hit stream. |
| Rest completion and interruption | `world.rest_camp` | Already owns the rest transaction and risk roll. |

## Why three new components

### `combat.tactical_pause`

Turn Order Queue owns discrete initiative and emits turn boundaries. Tactical
Pause deliberately does neither. It publishes one continuous-time state and a
reason, with configurable manual and automatic entry conditions. The scheduler
uses its time scale; presentation and input may continue while simulation time
is stopped.

Auto-pause is edge-triggered. A stream of effects while already paused must not
produce repeated pause transitions or repeatedly release player orders.

### `combat.party_command_queue`

Command Bus begins when a request is emitted; it is not a per-member planning
model. Party Command Queue holds short FIFO plans for each member while the
player thinks, cancels invalid plans on defeat, and releases them in a stable
order. It emits the same `utility.commandRequested` event as Behavior FSM, so
execution does not care whether an order came from a player or AI.

Resume and explicit-submit release modes are both supported. The compound uses
resume mode; it never requires a turn manager.

### `combat.prepared_spellbook`

Hotbar Abilities owns whether an ability can execute now. Prepared Spellbook
owns whether this character knows and prepared the spell and whether a cast
remains. Authorization happens before Hotbar execution, but slot spending
happens only after a correlated successful cast. This prevents an exhausted
spell from dealing damage while also preventing a rejected cast from consuming
a slot.

Rest Camp remains the authority on completed versus interrupted rest. Only its
`world.restCompleted` event replenishes prepared casts.

## Backward-compatible extensions

`combat.hotbar_abilities` now has `castAuthorizationMode`:

- `directOrAuthorized` is the default and preserves existing direct input.
- `authorizedOnly` ignores direct ability-slot input and accepts
  `combat.spellCastAuthorized`, preventing this compound from bypassing spell
  preparation.

`movement.pathfinding_system` now listens for `utility.commandDispatched` and
filters for move-kind orders. Existing terrain-driven pathfinding remains
unchanged.

Neither extension adds a runtime implementation or changes an existing default
into the new compound’s behavior.

## Event flow

```text
combat.aggro_table
  --combat.aggroGained----------> tactical pause

combat.tactical_pause
  --combat.tacticalPauseChanged-> party command queue

party command queue + behavior FSM
  --utility.commandRequested----> command bus

command bus
  --utility.commandDispatched---> pathfinding + pursuit + prepared spellbook

prepared spellbook
  --combat.spellCastAuthorized--> hotbar abilities

hotbar abilities
  --combat.abilityCast----------> prepared spellbook spends one cast
  --combat.hit------------------> damage resolver + status effects + unit roster

pursuit agent
  --movement.moveExecuted-------> unit roster
  --movement.pursuitArrived-----> contact attack

contact attack
  --combat.hit------------------> damage resolver + status effects + unit roster

world.rest_camp
  --world.restCompleted---------> prepared spellbook restores casts
```

Target selection and eligibility lookups such as `targetOf` and `canCast` are
synchronous queries. They are not converted into event round trips merely to
make the graph larger.

## Configuration extracted from the reference

| Configuration | Default in this pack | Design meaning |
|---|---|---|
| Manual pause | enabled | The player can stop continuous time to inspect and plan. |
| Enemy-spotted auto-pause | enabled | New hostile contact creates a tactical decision point. |
| Party-member-defeat auto-pause | enabled | A lost member interrupts the plan without ending player agency. |
| Effect-applied auto-pause | disabled | Routine effect refreshes do not cause stop-start combat. |
| Orders per member | 4 | Short plans without unbounded resume bursts. |
| Release edge | resume | Pause and release form one understandable player gesture. |
| Cast authorization | authorized only | Direct input cannot bypass prepared-spell requirements. |
| Rest recovery | completed rest only | Interrupted rest cannot become a free refill. |
| Spell and slot catalogs | host supplied | No commercial content or exact rule table is embedded. |

## Acceptance scenarios

1. **One clock:** every pause reason drives the same simulation state, with no turn events.
2. **No pause storm:** auto-pause fires only on a running-to-paused transition.
3. **Frozen simulation:** movement, cooldowns, status durations, slots and damage do not advance while paused.
4. **Deterministic release:** party order and per-member FIFO order are stable, with exactly-once dispatch.
5. **Defeat cleanup:** invalid actor and target orders disappear before release.
6. **Shared dispatch:** player and AI requests use the same ordered Command Bus.
7. **Preparation gate:** unknown, unprepared and exhausted spells cannot execute or pay costs.
8. **Execution gate:** authorized spells still obey range, cooldown and resource rules.
9. **Exactly-once spending:** only a successful correlated cast spends one prepared cast.
10. **Rest boundary:** completed rest restores casts; interrupted rest and duplicate transaction ids do not.
11. **One damage pipeline:** melee and spell hits share Damage Resolver, Status Effects and Unit Roster.
12. **Optional AI:** removing AI movement and contact attacks leaves a valid player-controlled spell loop.
13. **Replayability:** identical initial state, timed inputs, commands and seed reproduce the same outcome.

## Deliberately deferred

- Scripted encounters, boss phases and dialogue-triggered combat
- Spell learning from items, class progression and detailed slot curves
- Saving throws, resistance schools and exact commercial combat formulas
- Stealth, vision cones, surprise rounds and detection presentation
- Weapon styles, ammunition, attacks per round and detailed initiative variants
- Party AI scripting editors and user-configurable conditional tactics
- Selection outlines, order-line rendering and spellbook user interfaces
- Multiplayer pause arbitration and server-authoritative anti-duplication
- Runtime adapters for Canvas, WebGL, Roblox, Unity or Godot
- Exact commercial spells, characters, content tables and balance data

This delivery validates contracts and composition only. Runtime statuses for
the new components remain intentionally `unmapped`.
