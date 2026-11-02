# Extraction: Pokémon Battle and Capture

Status: **validated library pack**  
Reference: classic single-creature, turn-based Pokémon encounters  
Reusable output: `compound.monster_battle_capture`

## Purpose

Extract the reusable decisions and state transitions behind the reference loop,
not its proprietary content. This pack contains no species, move names, art,
audio, dialogue, maps, trademarked component ids, copied code or exact game
data. The reusable recipe uses original, genre-level contracts that can also
serve other creature-collection and turn-based games.

## The loop being extracted

```text
Encounter starts
  → both sides choose a command
  → commands resolve in a deterministic order
  → moves spend PP and produce hits or misses
  → type, damage and status systems change battle state
  → the player weakens the wild creature or attempts capture
  → success: party/box ownership + dex registration + encounter end
  → failure: round flow continues
  → knockout: replacement, party defeat or victory
```

The key design insight is that **capture is not a separate minigame**. It is a
command inside the same round structure as fighting and switching, and its
probability reads the state those other commands produced.

## Ownership map

| Reference pattern | Library owner | Why this boundary |
|---|---|---|
| Known moves, accuracy, priority and PP | `combat.move_set` **new** | Move definitions and per-creature PP are separate from turn sequencing and damage. |
| Choose first, then resolve by priority and speed | `combat.command_round` **new** | `combat.turn_order_queue` gives one unit a turn at a time; this reference collects both sides' commands before resolution. |
| Active creature, switching and knockout replacement | `pets.battle_party` **new** | Party membership survives the encounter; active battle slots do not. |
| Party cap and overflow storage | `pets.team_composition` | Already owns durable party order and boxes. |
| Elemental strengths, resistance and same-type bonus | `combat.type_chart` | Already provides a synchronous lookup, which damage resolution needs immediately. |
| Final damage and knockout | `combat.damage_resolver` | Keeps one damage authority and one defeat event source. |
| Health, sides and encounter unit state | `combat.unit_roster` | Keeps current health and unit identity out of the command sequencer. |
| Status conditions | `combat.status_effects` | Already owns effect application; capture reads its resulting state. |
| Capture devices | `inventory.slotted_bag` | Inventory owns possession and consumption, not capture probability. |
| Health/status/rarity-sensitive capture | `pets.capture_mechanic` | Already owns a deterministic weaken-then-capture decision. |
| Seen/caught collection registry | `pets.monster_dex` | Already owns permanent registration and milestones. |
| Experience after combat | `progression.xp_leveling` | Optional observer; removing it cannot break the battle. |

## Why three new components

### `combat.move_set`

The existing hotbar and tactical-attack contracts assume direct actions or an
action-point budget. The reference instead has a small known-move set, move
priority and PP that must be spent exactly once when the command executes.
Putting that state in the round would make the round a second move database.

### `combat.command_round`

`combat.turn_order_queue` remains the right brick for initiative-based tactics.
It is not replaced. Command Round covers a different topology: both sides lock
choices, then command class, priority, speed and deterministic ties produce an
execution order. This also gives capture and switching first-class command
slots instead of treating them as out-of-band UI actions.

### `pets.battle_party`

`pets.team_composition` correctly owns party membership and storage, but not
who is active in this encounter or what happens after a knockout. Battle Party
keeps that ephemeral state separate, so a switch cannot accidentally reorder
or duplicate the stored party.

## Event flow

```text
combat.move_set
  --combat.moveSelected--> combat.command_round
  --combat.moveCommitted (return wire)--> spends PP

combat.command_round
  --combat.hit--> damage resolver + status effects + unit roster
  --combat.captureCommanded--> capture mechanic
  --combat.switchCommanded--> battle party

combat.damage_resolver
  --combat.damageResolved--> capture odds refresh
  --combat.entityDefeated--> roster + battle party + XP + command round

pets.capture_mechanic
  --pets.captureSucceeded--> team composition + monster dex + command round
  --pets.captureFailed-----> command round

pets.battle_party
  --combat.activeCreatureChanged--> command round
  --pets.partyDefeated------------> command round
```

`combat.type_chart` is intentionally not event-wired. Its descriptor defines a
synchronous query; an event round trip would arrive after the damage pipeline
had already resolved.

## Configuration extracted from the reference

| Configuration | Default | Design meaning |
|---|---:|---|
| `maxMovesPerCreature` | 4 | A compact set makes move selection and PP management readable. |
| `activeSlotsPerSide` | 1 | Starts with the single-encounter ruleset; higher values are a later pack. |
| `commandPrecedence` | switch → capture → move | Makes non-damage commands explicit rather than hidden special cases. |
| `tieBreak` | seeded | Equal stats remain replayable without a permanent side advantage. |
| `partySize` | 6 | Preserves the reference genre's party pressure and overflow decision. |
| `endOnCapture` | true | A successful wild capture concludes this encounter recipe. |
| `automaticReplacement` | false | A knockout replacement remains a player decision. |

These are configurable genre conventions, not claims that every Pokémon game
or generation uses identical rules.

## Acceptance scenarios

The compound carries executable wiring validation and human-checkable
acceptance criteria. The most important scenarios are:

1. **Two-sided command lock:** no early resolution and no duplicate command.
2. **Deterministic order:** class, priority, speed and tie-break are inspectable.
3. **PP correctness:** rejection costs zero; execution costs one even on a miss.
4. **Single damage authority:** type is queried, damage comes only from the resolver.
5. **Capture determinism:** one device and one decision per attempt; presentation does not reroll.
6. **Exactly-once ownership:** one capture produces one party/box creature and one dex update.
7. **No capture-as-knockout reward:** capturing a target does not emit a defeat.
8. **Replacement and loss:** knockout waits for a healthy replacement or ends on party defeat.
9. **Optional observers:** dex and XP can be removed without breaking the core loop.
10. **Replayability:** identical state, commands and seed reproduce the result.

## Deliberately deferred

- Trainer battles and reward payout rules
- Double or multi-creature battle targeting
- Held items, abilities and detailed stat-stage rules
- Move learning, evolution and breeding
- Capture-device crafting and shop economy
- Persistence of newly caught creatures and dex state
- Runtime adapters and presentation/animation implementations
- Exact formulas, charts or content from any commercial game

These should be added only when a concrete vertical slice exposes the missing
contract. The present delivery is a schema and composition pack; `unmapped`
runtime statuses are intentional.
