# Topology contracts

## Why this exists

Topology quality is invisible in the artifact. A mesh renders identically whether it is
clean quad loops or triangle soup — the difference only appears once the thing is
**deformed or subdivided**. Static geometry carries the shape but not the consequence,
which is why the craft knowledge lives in prose ("never use a UV sphere for a game
asset") and why it is never enforced.

So the knowledge sits in artists' heads and in review comments, and every new asset
rediscovers it. This turns the checkable half into rules that run in CI.

## What it does and does not claim

The validator does **not** judge art. It has no opinion on whether a silhouette is good.

It asserts one thing: **a descriptor must not contradict itself.** A shape cannot be
declared as deforming with a rig *and* described with topology that is known to pinch
under deformation. One of those two statements is wrong, and the author is the one who
knows which.

That framing matters, because it means every finding has an honest resolution either
way:

- the shape really does deform → the topology spec needs quad loops
- the topology is really that simple → `deformsWithRig` should be `false`

Both are legitimate. Silently shipping both claims at once is not.

## The rules

Prose is never parsed. `poleNote` is for humans; `hasPoles` is the boolean rules act on,
derived once at authoring time.

### Blocking — the descriptor contradicts itself

All three are conditioned on `deformsWithRig`. A triangle-dominant *static prop* is
completely fine; props do not bend. The same topology on a skinned limb is a defect.

| Code | Rule |
|---|---|
| `TOPO001` | `deformsWithRig` with `quadPct` below the 60% floor. A triangle-dominant surface pinches at joints regardless of skin weights. |
| `TOPO002` | `deformsWithRig` with a `fan_tri` cap. A triangle fan concentrates a pole at the cap centre, which collapses when the joint bends. |
| `TOPO003` | `deformsWithRig` while carrying a pole. Poles must sit in flat, non-deforming regions. |

### Data integrity — the numbers must be self-consistent

| Code | Rule |
|---|---|
| `TOPO010` | LOD triangle counts must be non-increasing. A coarser tier cannot add detail. |
| `TOPO011` | LOD levels must start at 0 and increment by 1. |
| `TOPO012` | Vertices cannot exceed 3 × triangles. Every triangle contributes at most three corners, so more is arithmetically impossible. |

### Advisory — worth a look, never blocking

| Code | Rule |
|---|---|
| `TOPO020` | Over 100 triangles at LOD0 with no reduction by the coarsest tier: the LOD chain is not doing work. |
| `TOPO021` | Hazardous topology on a deforming shape with no `pitfall` documented. |

## A rule that was tried and rejected

An earlier draft checked the Euler characteristic directly: for a closed triangle mesh
`E = 3F/2`, so `V − F/2` should equal `2 − 2g`.

It fired on 28 of 35 closed shapes — and the data was right, the rule was wrong. These
vertex counts are **render vertices**, split at UV seams and hard normals, not
topological ones. A sealed icosphere at 1280 triangles has 642 vertices; the catalogue
records 718, and those 76 extra are seam duplicates rather than an error.

The identity is still useful, so it is reported as `seamVertexOverhead` — a measure of
how much duplication the seams cost — and never enforced. Worth remembering as the
shape of mistake this kind of validator invites: an invariant that is true of ideal
geometry and false of shipped geometry.

## The baseline

Introducing a linter to an existing library with a red build helps nobody, and blanket
suppression comments scattered through descriptors would hide the debt.

`art/topology-baseline.json` records the findings accepted when validation was
introduced. Anything in it is reported as *known* and does not fail; **anything new
fails immediately.** So the rules block new debt from day one without demanding an art
rewrite first, and the baseline file doubles as a visible ledger of what is outstanding.

Removing an entry is a fix landing. Adding one should be a deliberate, reviewed
decision.

```bash
# check (what CI runs)
python3 tools/validate_topology.py --baseline art/topology-baseline.json

# after fixing shapes, re-record what remains
python3 tools/validate_topology.py --baseline art/topology-baseline.json --write-baseline

# ignore the baseline entirely and see everything
python3 tools/validate_topology.py
```

## Current state

47 shapes, 13 of them deforming. All 13 trip at least one blocking rule, which is the
finding rather than an embarrassment: the contradiction was always there, and nothing
had ever asked the question.

`art.limb_arm` is the clearest case. Its pitfall already says *"Needs 2+ edge loops per
joint for clean skin-weight deformation"* — and its topology records `quadPct: 0` with a
`fan_tri` cap, which is precisely the absence of those loops. The documentation and the
geometry disagreed, in the same file, and only a validator was ever going to notice.

## Where this goes

The natural next contract is the one nobody builds: **does a rig's joint range exceed
what a topology supports?** A 140° elbow on a zero-quad fan-capped limb is a predictable
pinch, and both halves of that sentence are already declared data. That is the
topology ↔ animation bridge, and it wants `art/rigs/*.rig.json` with joint limits before
it can be written.
