# RPG Consumables, Rest & Recovery

## Purpose

This pack turns quick-use items and resting into explicit, replay-safe game
contracts. It is inspired by the broad recovery decisions in classic and modern
RPGs, not by their protected content. Glimmerfen, its items, its camps, its
units, and every amount in the example are original and generic.

The central rule is ownership:

- **Potion Belt decides whether a use is accepted.** It does not keep a second
  inventory and does not apply the result itself.
- **Rest Camp decides whether a rest starts, completes, or interrupts.** It
  does not heal, refill pools, replenish spells, or spawn the ambush.
- **Resource Pools owns generic per-unit pools** such as focus or resolve. It
  does not duplicate health, action points, card energy, survival meters, team
  RTS stock, or prepared casts.
- Existing inventory, timer, health, status, prepared-spell, damage, encounter,
  and save owners keep their jobs.

The result is a small loop with no hidden second pipeline:

```text
use request
  -> Potion Belt legality + stable useId
  -> exactly one inventory removal when accepted
  -> shared cooldown generation
  -> health / resource / status / cleanse requests
  -> existing owners apply and dedupe those requests

rest request
  -> Rest Camp eligibility + stable restId + persisted ambush roll
  -> timer generation
  -> completed: recovery plan goes to health, pools, and prepared casts
  -> interrupted: no recovery
  -> ambushed: no recovery; existing spawner receives the spawn request
```

## Component changes

| Component | Version | Extension |
|---|---:|---|
| `inventory.potion_belt` | 0.2.0 | Stable uses, authored items, shared cooldown groups, recovery/status/cleanse requests, rejection and restoration |
| `world.rest_camp` | 0.2.0 | Profiles, stable rest ids, pending state, timer generations, safe/combat gates, interruption, ambush requests |
| `combat.resource_pools` | 0.1.0 | New generic per-owner resource balances and once-only recovery |
| `combat.unit_roster` | 0.2.2 | Health recovery requests and completed-rest dedupe through its existing heal path |
| `combat.status_effects` | 0.2.1 | Additional consumable-originated application and cleanse input paths |
| `combat.prepared_spellbook` | 0.2.0 | Completed-rest dedupe for prepared-cast recovery |
| `world.dynamic_encounter_spawner` | 0.2.0 | Rest-ambush requests enter the existing spawn path |
| `persistence.save_system` | 0.2.6 | Save triggers for uses, rejections, cooldowns, rest, health, resources, and prepared-cast recovery |

## Consumable definitions

An authored item has this shape:

```json
{
  "id": "lantern_tonic",
  "targetMode": "self",
  "usePolicy": "always",
  "cooldownGroupId": "tonic",
  "cooldownSeconds": 8,
  "consume": true,
  "recovery": [
    {"resourceId": "focus", "mode": "flat", "amount": 1}
  ],
  "statusApplications": [
    {"effectId": "battle_focus"}
  ],
  "cleanseRequests": []
}
```

`targetMode=self` requires source and target to match. `unit` accepts an
explicit unit target; faction and targeting UI remain host concerns.
`usePolicy=outOfCombat` reads the request's combat fact. Potion Belt does not
become an encounter tracker.

Recovery modes are:

- `flat`: a positive amount;
- `percentMax`: a fraction in `(0,1]` of the target pool's maximum;
- `full`: restore to maximum and take no amount field.

Every item must have at least one recovery, status, or cleanse operation.
`consume=false` is available for a reusable use item; an ordinary consumable
uses `true`.

## Explicit use request and child identities

```json
{
  "useId": "use.scout.lantern.001",
  "itemId": "lantern_tonic",
  "sourceId": "scout",
  "targetId": "scout",
  "inCombat": false
}
```

For this request the first recovery, status, and cleanse operations would use:

```text
use.scout.lantern.001.recovery.0
use.scout.lantern.001.effect.0
use.scout.lantern.001.cleanse.0
```

Only operation kinds present on the item are emitted. These ids are stable
inputs to Unit Roster, Resource Pools, and Status Effects, which maintain their
own ledgers. A bus retry therefore cannot heal twice, refill twice, apply a new
status instance, or cleanse a later effect.

Accepted **and rejected** use ids enter `processedUseIds`. An exact replay is a
silent no-op even when the first decision was a rejection. This prevents a
retry after a state change from turning an earlier cooldown rejection into a
successful use.

## Rejection order and cost

Potion Belt checks:

1. well-formed request and known item;
2. target shape;
3. available stack;
4. combat policy;
5. active source/group cooldown.

A rejection consumes nothing, starts no cooldown, and emits no recovery,
status, or cleanse request. `inventory.useRejected` carries the reason:
`unknownItem`, `empty`, `invalidTarget`, `inCombat`, `cooldown`, or
`invalidRequest`. Empty use also retains `inventory.potionEmpty`.

An accepted use removes one item when `consume=true`, starts the cooldown, and
emits its typed operations. A downstream result does **not** create an automatic
refund. For example, using a healing draught on an already-full target can
produce `combat.healthRestoreRejected` after the item was accepted. That is a
content and targeting decision, not a second use transaction. Games that want
free preflight targeting should query the health or resource owner before
submitting the use.

When an accepted stack reaches zero, `inventory.potionEmpty` reports the empty
slot. Auto-refill remains a view over the same bag, never a duplicate stack.

## Shared cooldowns and timer races

Cooldown identity is `(sourceId, cooldownGroupId)`. Two items in one group
share the lock even if their cooldown durations differ. The accepted item
starts the group's new generation. Timer System still owns countdowns and
`utility.timerCompleted`; Potion Belt owns what that completion means.

```text
redleaf accepted -> draught generation 1
generation 1 completes
redleaf accepted -> draught generation 2
late generation 1 completion -> ignored
```

Restoration includes active cooldowns, generations, and `processedUseIds`.
Restoring emits no historical potion, recovery, status, cleanse, or cooldown
events.

## Generic resource pools

Resource Pools keys a pool by `(ownerId, resourceId)`, allowing both Scout and
Warden to own independent `focus` pools:

```json
{"id": "focus", "ownerId": "scout", "initial": 2, "maximum": 8}
```

A direct recovery request carries `recoveryId`, `targetId`, `resourceId`, and
the operation. Unknown pools and already-full direct requests are rejected
without a balance change. Recovery is capped at maximum. `resourceOf` is a
synchronous query; Potion Belt and Rest Camp do not maintain copies.

Reserved ids are `health`, `action_points`, `card_energy`, `prepared_casts`,
`hunger`, `thirst`, `temperature`, and `stamina`. Their existing owners remain
the only valid destination. A game can name a generic pool `mana`, `focus`,
`resolve`, or another original resource without creating a new descriptor.

## Health, status, cleanse, and prepared casts

Unit Roster handles `resourceId=health` through its existing capped heal path.
It separately remembers direct `recoveryId` values and completed `restId`
values. Unknown, defeated, and full direct targets reject; completed rest
simply emits changes where recovery is possible.

Potion Belt emits `inventory.effectApplicationRequested` and
`inventory.cleanseRequested`. Status Effects listens to these in addition to
its host `input.*` requests. Stacking, immunity, capacity, dispel rules, timer
generations, and cleanup are unchanged. A consumable never edits `activeEffects`
or `controlState` directly.

Prepared Spellbook listens only to `world.restCompleted`. It restores the
current preparation's casts and remembers `restId`. Interrupted rest emits no
completion, and replayed completion cannot replenish a second time. Preparation
lists are not silently replaced.

## Rest profiles

```json
{
  "id": "watchfire_rest",
  "durationSeconds": 8,
  "requiresSafeZone": true,
  "allowInCombat": false,
  "ambushChance": 0.05,
  "recovery": [
    {"resourceId": "health", "mode": "full"},
    {"resourceId": "focus", "mode": "full"},
    {"resourceId": "resolve", "mode": "full"}
  ]
}
```

A request supplies a stable `restId`, profile, unique `memberIds`, safe-zone and
combat facts, and the runtime's risk context. Validation supplies an
`ambushRoll` so the example is deterministic. A runtime rolls once when the
rest starts and stores that roll in `activeRest`; restoring pending rest never
rerolls it.

Rest Camp permits one active transaction. `unsafe`, `inCombat`,
`alreadyResting`, `unknownProfile`, and `invalidRequest` reject before a timer
starts. Accepted and rejected rest ids both enter `processedRestIds`.

`world.restStarted` contains no recovery. On completion, Rest Camp compares the
persisted roll with the profile chance:

- ordinary completion emits `world.restCompleted` with the recovery plan;
- ambush emits `world.restInterrupted` and `world.restAmbushRequested`, never
  `world.restCompleted`.

Manual interruption, a hit against a resting member, or member defeat also
interrupts without recovery. A stale completion after interruption or after a
replacement rest is ignored through the rest generation.

Dynamic Encounter Spawner receives the ambush request and applies its ordinary
biome table, level band, spawn-distance, and out-of-sight rules. Rest Camp does
not place enemies and the spawner does not decide whether rest was interrupted.

## Legacy compatibility

The original `input.potionSlot` and `{itemId:{heal}}` map remain available when
no authored definition replaces that path. Legacy healing still uses Unit
Roster's heal function. The original no-profile `input.restRequested` falls
back to `restDurationSeconds`, `baseAmbushChance`, `requiresSafeZone`, and
`restoresPerRestAbilities`.

An id-less legacy call does not acquire a fabricated durable identity. New
content that needs replay safety must use explicit `useId` and `restId` values.
This is the same compatibility rule used by legacy hit-driven status effects.

## Original Glimmerfen content

`examples/consumables-rest/glimmerfen.recovery.json` contains:

- six consumables: health, focus, cleanse, status-plus-focus, out-of-combat
  percent healing, and a status vial;
- three rest profiles: exposed field break, safe watchfire rest, and a short
  combat-tolerant trail pause;
- three original units and three generic resource-pool records;
- twelve executable scenarios with thirty-eight steps.

The scenarios prove accepted use and replay, rejection before cost, shared
cooldown completion, stale cooldown and rest timers, percent caps, stable child
ids, status cleanse, rest eligibility, once-only completed recovery, damage
interruption, ambush, active-rest exclusion, and snapshot restoration.

## Compound and adoption

`compound.consumable_rest_loop` contains 19 components, 42 validated
connections, and 18 acceptance criteria. It includes the complete dependency
closure for inventory, timers, party, health, generic pools, status, prepared
spells, hotbar, damage, ambush spawning, enemy scaling, physics, XP, and saving.
The member configuration embeds the exact Glimmerfen consumables, rest
profiles, pools, and Mirelight status references validated by the tools.

Action RPG adopts quick use and generic pools. CRPG adds the full rest and
prepared-cast loop. Monster Taming adopts items and completed-rest recovery
without changing capture odds or command rounds. Dungeon Crawler adds
replay-safe supplies and interruptible camps to its run structure.

Removing Resource Pools leaves health, status, cleanse, prepared-cast, and
inventory behavior intact. Removing Dynamic Encounter Spawner leaves rest risk
and interruption intact but places no ambush enemies.

## Deferred systems

This pack deliberately does not add crafting, ingredient conversion, shops,
item prices, equipment durability, AI item selection, survival-meter recovery,
food spoilage, ration logistics, camping construction, world-time simulation,
new turn sequencing, spell learning, forced targeting, charm, damage-over-time
final calculations, or commercial item/spell data. These are separate owner
decisions, not hidden fields in a potion definition.

## Validation

```bash
python3 tools/validate_consumables_rest.py --report reports/consumables-rest.json
python3 -m unittest discover -s tools/tests -p 'test_*.py'
python3 tools/validate_component_graph.py --report reports/component-graph.json
python3 tools/validate_compounds.py --report reports/compound-validation.json
python3 tools/validate_genres.py --report reports/genre-validation.json
```

The semantic validator checks structure, duplicate ownership, reserved pools,
cross-file status references, operation shapes, scenario behavior, and malformed
expectations. Its deterministic model is a test oracle, not another runtime
component. The local workflow also adds `examples/**/*.recovery.json` triggers
and the report-producing validation step.
