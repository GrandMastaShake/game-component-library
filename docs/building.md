# Building: improve what is here, or strap on a new part

The catalogue's whole value is that a piece written for one genre is grabbable
for the next. The thing that destroys it is a second component quietly owning
half of what an existing one owns — and that does not happen through
carelessness. It happens because **the question "does this already exist?" was
expensive to ask**, so it did not get asked.

This is the order to ask things in, and the tool for each step.

---

## 1 · Does something already own this?

```
python3 tools/who_owns.py elevation --runtime ../game-architect-studio/generator
```

It searches every descriptor's id, name, tags, inputs, outputs, events and
prose — and, with `--runtime`, the consuming app's source for concepts
implemented where **no descriptor covers them**.

That second half is the one that earns its keep. The near-miss that caused this
document was stepped isometric terrain about to be written a *third* time:
`world.tile_grid` already declared `elevationAt`, and `generator/iso/IsoWorld`
already implemented it — and `IsoWorld` is not a component, so it appears
nowhere in the catalogue. A descriptor search alone would have found one of the
two and missed the other.

**A hit in an id, output, input, event or tag is a claim.** A hit in prose is a
component that happens to mention the word. The tool ranks them accordingly,
because otherwise thirty descriptions bury the one declaration that matters.

## 2 · If it exists, can it be extended?

This is the balance, and it does not have a rule that decides itself. The
question to ask is not "is this related?" but:

> **Would the existing component end up owning two things?**

If no, extend it. A declared input or output on a component that already owns
the concept is almost always better than a second component owning half of it:

- `utility.behavior_fsm` already knew `detectionRange` and kept it private. It
  became an **output**. Nothing new was written, and `combat.aggro_table` and
  `movement.pursuit_agent` both read the one number.
- `progression.skills_tree` published four names nothing read. It gained
  `bonuses`. The tree still does not touch combat — `combat.melee_basic` reads
  its own numbers — so nothing gained a second owner.
- `world.tile_grid` generated a skirmish board unconditionally. It now derives
  elevation and surface **from the terrain when the build has terrain**. One
  component, one more thing it can be; the alternative was a third stepped-terrain
  implementation.

If yes — if the extension would make one component answer two different
questions — that is when a new part is the right answer:

- `combat.aggro_table` exists because *three* components were each privately
  deciding who was being hunted. No single one of them could own it without
  owning something else too.
- `movement.pursuit_agent` exists because the only executor was turn-based and
  dragged an action-point economy in behind it.

## 3 · If you are adopting a kit, price it first

```
python3 tools/compound_fit.py compound.real_time_encounter genre.dungeon_crawler
```

Answers **what is the relation** (how many of the kit's members the pack already
names, out of how many) and **compared to what** (how the addition measures
against the pack's own size). A cost with nothing beside it is just a number.

## 4 · If it really is new, say what you looked for

`provenance` is not paperwork. It is the field that turns *"I could not find
anything like this"* from a private belief into a reviewable claim, and it is
the first thing a reader reaches for when two components look similar and they
need to know which came second and why.

Say what you searched for, what you found, and **which existing component this
is NOT**. `movement.patrol_route` names `world.mob_patrol` and explains that one
is a platformer package that owns its mobs while the other owns only a verb.

`validate_provenance.py` gates this. 261 components predate the rule and are
baselined — that is a line that must not move outward, not a backlog with a
schedule. A baselined component that gains a real provenance is reported so the
baseline can shrink; a baseline that only grows is a permission slip.

## 5 · Then the checks that were already there

| | catches |
|---|---|
| `validate_component_graph` | dangling dependencies, cycles |
| `validate_compounds` | a kit's wire that nobody emits or nobody hears |
| `validate_genres` | a pack naming a component that does not exist |
| `validate_topology` / `platforms` / `assembly` | claims art and adapters cannot back |
| `declare_implementations --check` | an implementation claimed and never reviewed |
| `validate_provenance` | a new component that skipped step 1 |

And in the consuming app: `check-implementations` (a brick registered twice),
`check-payloads` (two emitters of one event disagreeing about its shape),
`check-iso` (a brick that paints on the map without asking the painter),
`check-mash`, `check-tweak`, `check-select`, `check-mcp`.

---

## The shape of the balance

Every one of these was found by **playing the build**, not by reading it:

| symptom | what it actually was |
|---|---|
| "I don't see aiming or mobs" | the pack named no movement and nothing to fight |
| "the mobs should only attack within a certain distance" | a declared input that was never published |
| "do the skills actually do anything?" | two of three declared outputs did not exist |
| "they look like they might be in the lower cell" | a tile's centre is not where a thing stands |
| "you move SE when you hit down" | an arrow key handed through as a tile delta |

The tools in steps 1–3 are for the moment **before** writing. The checks in
step 5 are for the moment after. Neither replaces putting the thing on a screen
and using it — that is where every entry in that table came from, and no
validator in this repository would have produced a single one of them.
