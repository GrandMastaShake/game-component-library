# Event Contracts and Cross-Cutting Fan-In

## The problem

Persistence and player feedback are cross-cutting sinks. Treating their contracts as a closed list of every gameplay event makes each new compound fragile.

## Two subscription forms

A compound wire is valid if the target either lists the event exactly in `events.listensTo`, or the source event's `eventIntents` intersects the target's `sinkFor`.

```json
{"events":{"emits":["pets.hatched"]},"eventIntents":{"pets.hatched":["persist","notify"]}}
```

```json
{"id":"persistence.save_system","sinkFor":["persist"]}
```

The compound must still declare its actual wire explicitly.

## Rules

- `eventIntents` keys must be emitted events.
- Intent arrays and `sinkFor` must contain non-empty strings.
- Exact listeners remain preferred for narrow domain behavior.
- Intent fan-in is for durable cross-cutting capabilities only.
- Do not use broad intents for ownership, authorization, or security-sensitive flows.

## Vocabulary

The full list. It is open — `validate_compounds.py` checks the SHAPE of `eventIntents` and
`sinkFor` and not the class names — so this table is the only place the vocabulary is
written down, and a class not on it is a typo until it is added here with its sinks.

| Intent | Means | Sinks today |
|---|---|---|
| `persist` | something durable happened | `persistence.save_system` |
| `notify` | the player should be told | `ui.notification_toast` |
| `impact` | something hit something | `presentation.audio_system`, `presentation.particle_system`, `presentation.screen_shake` |
| `achievement` | the player accomplished something worth rewarding | `progression.reward_schedule` |
| `reward` | the player is being GIVEN something | `economy.currency`, `inventory.core_inventory`, `progression.xp_leveling` |

### `reward` carries a payload contract, and it is the only class that does

The other four classes are pure notifications: a sink reacts to the fact of the event and
reads whatever fields it recognises. `reward` is different, because three unrelated sinks
receive the same event and each has to decide whether any of it is theirs.

**Every event tagged `reward` carries `grants`: an array of `{kind, amount, itemId?}`,
where `kind` is `currency`, `item` or `xp`.** A sink takes the entries whose kind is its
own and ignores the rest; an event granting coins and experience together is one event
with two entries, not two events.

```json
{"grants": [{"kind": "currency", "amount": 10}, {"kind": "xp", "amount": 5}]}
```

Without this rule the sinks would have to branch on the event NAME to know which shape to
read, which is exact coupling wearing an intent's clothes — and it would undo the reason
the class exists, that a genre added later is paid without anybody editing a sink.

An event may carry its own fields alongside `grants`; `economy.collectibleCollected` still
reports the pickup it was, and `grants` is how the wallet understands it.

The compound validator reports each accepted wire as `exact` or `intent:<labels>` in `validatedWires.acceptedBy`.

## Which form to use when authoring

The two forms are not interchangeable. The test is *why* the listener cares.

**Exact `listensTo` is for functional coupling** — the listener reacts to what the event
*means*. `progression.skills_tree` listens to `progression.leveledUp` because levelling is
specifically the thing that unlocks skills.

**`sinkFor` is for side-effect classes** — the listener reacts to what *kind of consequence*
the event has, not what it means. `persistence.save_system` does not care that a pet hatched;
it cares that something durable happened.

> **New components declare `eventIntents` on the events they emit. Cross-cutting sinks do not
> enumerate.**

This is what keeps the catalog from degrading. A sink that enumerates every event it might ever
persist grows without bound, and each new gameplay loop breaks CI until someone remembers to
append to it. That is not hypothetical: four consecutive compound waves failed validation this
way before intent fan-in was introduced, each fixed by appending to the same two arrays.

When a sink accepts an event purely because of its consequence class, the entry belongs in
`eventIntents` on the emitter, and the sink's `listensTo` should not grow at all.

## Event naming

`<category>.<lowerCamelEvent>`, where the prefix matches the category of the emitting component
(`combat.damageResolved`, `world.visionUpdated`).

Past tense for things that happened (`inventory.itemAdded`, `pets.hatched`). Present tense only
for requests that something *should* happen (`ui.notificationRequested`,
`utility.commandRequested`) — a request event implies some component services it and emits the
corresponding past-tense result.

## Gotcha: unknown keys pass silently

`component.schema.json` is draft-07 without `additionalProperties: false`, so a misspelled
`sinkfor` or `eventIntent` is accepted by the schema and then ignored by the wire resolver. The
failure surfaces later as a wire error naming the *compound*, not the typo. When a wire fails to
resolve and the intent looks correct, check the spelling of these two keys on both ends first.
