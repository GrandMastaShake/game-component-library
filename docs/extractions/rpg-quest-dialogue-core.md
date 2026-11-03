# RPG Quest & Dialogue Core

Status: **validated library pack**
Reusable output: `compound.quest_dialogue_loop`
Content gate: `tools/validate_narrative_graphs.py`

## Purpose

Add the reusable connective tissue between conversation, encounters, loot,
character progression, and persistence without introducing parallel quest or
dialogue state owners. The pack covers staged quests, required and optional
objectives, conditional dialogue, deterministic attribute checks, once-only
consequences, active/completed/failed quest journals, exactly-once mixed
rewards, restoration, and content validation.

All quests, writing, characters, flags, items, attributes, rewards, and balance
data remain host supplied. The included road-watch content is original generic
example data, not extracted commercial material.

## The loop

```text
Dialogue Box choice
  → Dialogue Tree Engine evaluates conditions and synchronous checks
  → quest / world-flag / journal consequence requests
  → Quest Log accepts work and owns every objective and stage transition

Combat defeat / inventory addition / world-flag change / explicit credit
  → required and optional objective progress
  → ordered branch, completion, or failure
  → Quest Reward Coordinator deduplicates the stable completion id
  → one mixed rewardGranted event
  → XP + Currency + Core Inventory each consume their own grant kinds

Completed quest, dialogue, flag, journal, and reward changes
  → Save System
  → each owner restores its own state without replaying side effects
```

The central boundary is that **quest state, conversation state, world
consequences, reward delivery, and player-facing projections are different
responsibilities**. Combining them makes dialogue a second quest engine and
makes reload especially prone to repeated choices and duplicate rewards.

## Ownership map

| Decision | Library owner | Boundary |
|---|---|---|
| Raw lines and choice buttons | `ui.dialogue_box` | Renders and reports choices; does not interpret extended consequences. |
| Conversation traversal and once-only choices | `ui.dialogue_tree_engine` **extended** | Owns positions and resolved-choice history, not the resulting world state. |
| Attribute checks and roll cursor | `progression.attribute_sheet` **extended** | Synchronous `check` query; caller owns the consequence. |
| World consequences | `world.world_state_flags` **extended** | Owns flag semantics, queries, and restorable values. |
| Quest stages and objectives | `progression.quest_log` **extended** | Sole authority for acceptance, progress, transitions, completion, and failure. |
| Exactly-once mixed quest grants | `progression.quest_reward_coordinator` **new** | Owns grant ids and dedupe ledger, not completion or granted balances. |
| XP, currency, and item balances | `progression.xp_leveling`, `economy.currency`, `inventory.core_inventory` | Existing reward sinks consume only their own grant kinds. |
| Compact objective HUD | `ui.quest_tracker` **extended** | Pinned read model, including staged and failed state. |
| Active/completed/failed quest browser | `ui.quest_journal` **new** | Filtering, selection, ordering, and unread presentation only. |
| Clues and learned lore | `ui.narrative_journal` **extended** | Records dialogue-requested entries, not quest status. |
| Durable snapshots | `persistence.save_system` **extended** | Saves completed changes, not rejected intentions. |

## Quest Log 0.6.0: staged graph mode

Legacy `quests` entries and `inlineLegacy` rewards remain the default. New
`questGraphs` content may declare:

- `prerequisites`: required quest ids and states.
- `start`: the initial stage.
- `stages`: objectives, ordered transitions, and optional completed/failed
  terminals.
- `rewards`: currency, XP, and item grants delivered in coordinated mode.

An objective names a completed gameplay `event`, optional scalar `match`
payload checks, a positive `target`, and optional `amountFrom` and `dedupeBy`
payload fields. Required objectives open transitions; optional objectives do
not block the unconditional default transition. A conditioned transition may
fire before required objectives finish, which allows an explicit failure branch
to interrupt the stage. Transitions are evaluated in declaration order, so that
failure branch can take priority over the ordinary completion branch.

A terminal settles when its required objectives complete. A terminal without
objectives settles on entry. Stage cycles are invalid: repeatability belongs to
a new quest instance rather than a loop through completion logic.

`initialQuestStates` restores current stages, objective counts, seen credit
keys, and completion ids. Restoration is not acceptance or completion and does
not emit rewards. Saved state is not revalidated against edited content; new
credits and transitions use the current definitions.

## Dialogue Tree Engine 0.2.0

Legacy `{label, to, act}` choices remain valid. Extended choices add:

- a stable `id` for restoration and once-only resolution;
- `conditions` against quest state, world flags, or attributes, composed with
  `all`, `any`, and `not`;
- `once`, preventing resolved choices from emitting consequences again;
- `check`, a synchronous Attribute Sheet roll with explicit pass/fail
  destinations;
- `consequences`, plus node-level `onEnter` consequences.

Consequences are requests with three explicit types:

1. `setFlag` → World State Flags.
2. `quest` → Quest Log (`offer`, `accept`, `credit`, `advance`, `fail`, or
   `turnIn`).
3. `journal` → Narrative Journal.

Dialogue Tree Engine never applies those changes itself. `initialDialogueStates`
restores current nodes and resolved-choice ids only; quest, flag, journal, and
attribute-check history restore through their respective owners.

Attribute Sheet 0.3.0 exposes the check query its contract already claimed to
own. `checkSeed` and `initialCheckCount` make the roll stream reproducible and
restorable. An explicit valid roll can be supplied without consuming that
stream.

## Exactly-once coordinated rewards

Staged quests use `rewardMode: coordinated` in the compound:

1. Quest Log completes once and emits `{questId, completionId, rewards}`.
2. It does **not** emit inline `questRewarded` in this mode.
3. Quest Reward Coordinator validates the bundle and stable completion id.
4. A new id enters the restored dedupe ledger before one `rewardGranted`
   emission.
5. Duplicate or restored ids are no-ops; malformed bundles are rejected before
   entering the ledger.
6. XP, Currency, and Core Inventory receive the same mixed event through their
   existing `reward` intent and consume only matching entries.

The coordinator is not a replacement for Reward Schedule. Reward Schedule
decides when ambient achievements pay; this coordinator deduplicates one
specific quest completion. Neither may be wired to pay the same completion.

Runtime adapters must persist the grant ledger and deliver the grant as one
recoverable transaction. A crash recovery replay must consult the ledger rather
than assume that resending the event is harmless.

## Journal boundaries

Quest Journal is intentionally a new read model rather than another progression
system. It projects active, ready, completed, and failed entries with current
stage and objective progress. Quest Tracker remains the compact pinned HUD.
Narrative Journal records clues and lore requested by dialogue. All three can
be removed without changing quest progression or reward delivery.

## Narrative-content validator

```bash
python3 tools/validate_narrative_graphs.py
python3 tools/validate_narrative_graphs.py path/to/content --report reports/narrative-graphs.json
python3 -m unittest tools/tests/test_validate_narrative_graphs.py
```

The default content is `examples/quest-dialogue`:

- `road-watch.quest.json`: two quests, prerequisites, required and optional
  objectives, a failure branch, a completion terminal, and mixed rewards.
- `road-watch.dialogue.json`: one four-node conversation with quest actions, a
  deterministic check, once-only choices, flags, and journal requests.

The validator checks:

- duplicate quest, stage, objective, and choice ids;
- unknown and cyclic quest prerequisites, including cross-file cycles;
- unknown, cyclic, self-referential, and unreachable quest stages;
- nonterminal stages with no exit and quests with no reachable completion;
- malformed objective events, targets, match rules, and rewards;
- malformed nested conditions and attribute checks;
- dangling dialogue pass/fail/ordinary destinations;
- unreachable dialogue nodes as warnings, since conversation hubs may cycle;
- dialogue quest actions against the bundled quest, stage, and objective ids.

## Compound and genre adoption

`compound.quest_dialogue_loop` contains 15 components and 31 validated wires.
Its dependency closure is represented, including Safe Area Layout for the
removable tracker. Combat and inventory objective sources are optional for
quests that do not use them.

CRPG and Action RPG both name every compound member. Existing genre content
remains valid; the two new library components are additive and the extended
owners retain their legacy defaults.

## Acceptance scenarios

1. Legacy flat quests and dialogue choices retain their behavior.
2. Prerequisites, required objectives, optional objectives, and ordered
   transitions produce the intended stage and terminal exactly once.
3. Duplicate gameplay facts cannot advance a deduped objective twice.
4. Conditional choices cannot traverse or emit consequences while unavailable.
5. Seeded checks replay identically with the same restored cursor and choices.
6. Restored once-only choices cannot emit consequences again.
7. Dialogue never directly mutates quest, flag, journal, or reward state.
8. Coordinated completion produces one mixed grant and no inline payout.
9. Duplicate or restored completion ids cannot grant rewards again.
10. XP, currency, and items remain owned by their respective reward sinks.
11. Journal and HUD removal leaves the core loop intact.
12. Restoring narrative state does not replay completed side effects.
13. Rejected intentions do not trigger completed-change saves.
14. Broken content links and impossible quest graphs fail validation before
    runtime.

## Deliberately deferred

- Visual quest/dialogue editors and localization pipelines
- Voice, cinematography, animation, and conversation presentation
- Arbitrary scripting inside conditions or consequences
- Repeatable quests, timed objectives, and procedural quest generation
- Multiplayer quest authority and party-sharing transaction integration
- Transactional inventory-capacity and overflow policy for item rewards
- Runtime adapters, databases, and crash-recovery implementations
- Commercial writing, characters, quests, items, and exact balance data

This delivery validates contracts, composition, and narrative content only.
New runtime targets remain intentionally `unmapped`.
