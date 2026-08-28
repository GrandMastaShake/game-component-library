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

## Initial vocabulary

| Intent | Appropriate sink |
|---|---|
| `persist` | Durable state/snapshot systems |
| `notify` | Player feedback systems |

The compound validator reports each accepted wire as `exact` or `intent:<labels>` in `validatedWires.acceptedBy`.
