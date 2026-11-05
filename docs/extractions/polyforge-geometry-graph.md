# POLYFORGE Geometry Graph

## Scope

Build the second visual-authoring pack as a real, executable non-destructive geometry system:

- Canonical `.graph.json` documents with stable node and link identities.
- Typed input/output sockets and explicit graph outputs.
- Deterministic topological evaluation and dependency pruning.
- Non-mutating graph editing commands and checksum validation.
- Canonical asset generation or external `.forge.json` input.
- Stable-ID geometry edits, whole-asset transforms, LOD budget configuration, and topology measurement.
- Content-keyed, mutation-isolated evaluation caching.
- Direct Asset Baker integration, an original graph-built asset, semantic validation, and binary GLB readback.

This is original library technology. No commercial game code, assets, writing, characters, quests, item names, exact content tables, or balance data are included.

## Ownership

- `presentation.low_poly_generator`: original parametric and prompt-family geometry.
- `presentation.asset_core`: canonical polygon source, durable topology IDs, stable-ID operations, and asset checksums.
- `presentation.geometry_graph`: non-destructive typed DAG authoring and deterministic compilation to canonical source.
- `presentation.asset_baker`: topology-guarded simplification, strict budgets, GLB encoding, and runtime descriptor readback.
- `presentation.lod_system`: runtime distance selection only.

The graph does not replace `.forge.json`, become a runtime scene format, perform LOD selection, or export materials. Every successful evaluation produces the existing canonical asset contract, so downstream baking and independent validation remain unchanged.

## Canonical graph document

`art/geometry-graph.schema.json` defines `polyforge.geometry` version `1.0.0`.

```text
n000000  stable node identity
l000000  stable link identity
```

Each node has a registered `type`, a `parameters` object, and optional editor-only `position`. Each link names exact endpoints:

```json
{
  "id": "l000000",
  "from": {"node": "n000000", "socket": "asset"},
  "to": {"node": "n000001", "socket": "asset"}
}
```

The graph requires an `asset` output and may expose a `stats` output. `nextIds` allocates future stable IDs; array positions are not editor identity. An FNV-1a checksum covers canonical key-sorted graph content.

`applyGeometryGraphOperations` provides non-mutating editor commands:

- `addNode` and `removeNode`.
- `addLink` and `removeLink`.
- `setParameters`.
- `setOutput`.

Removing a node also removes its connected links, but refuses to remove a node referenced by a graph output. Every command revalidates and re-checksums the new graph. Surviving IDs never change.

## Node contract

| Node | Inputs | Outputs | Purpose |
|---|---|---|---|
| `source.generate` | — | `asset` | Generate original POLYFORGE geometry and canonicalize it |
| `source.asset` | — | `asset` | Use an embedded document or `sourceDocument` evaluation input |
| `edit.move` | `asset` | `asset` | Move durable vertex IDs |
| `edit.split` | `asset` | `asset` | Split a durable edge ID |
| `edit.extrudeFace` | `asset` | `asset` | Extrude a durable face ID into quad sides |
| `edit.deleteFace` | `asset` | `asset` | Delete a durable face ID while preserving a non-empty asset |
| `modify.transform` | `asset` | `asset` | Positive scale, XYZ degree rotation, pivot, and translation |
| `configure.budgets` | `asset` | `asset` | Replace ordered LOD budget declarations |
| `measure.asset` | `asset` | `asset`, `stats` | Pass source through and expose canonical topology statistics |
| `output.asset` | `asset` | `asset` | Explicit graph terminal |

Unknown parameter keys are rejected. Required source/edit parameters are checked before execution. Geometry edit nodes delegate to Asset Core, so graph evaluation and direct stable-ID editing share topology behavior rather than drifting into separate implementations.

## Transform semantics

Asset Core now supports a `transform` operation. It applies, in order:

1. Pivot subtraction.
2. Component-wise positive scale.
3. X, then Y, then Z rotation in degrees.
4. Pivot restoration and translation.

`vertexIds` may select a subset; omitting the field selects the whole asset. Socket transformation requires whole-asset selection so geometry and attachment points cannot silently diverge. Zero or negative scale is rejected instead of creating collapsed or winding-inverted topology. Transform operations receive ordinary stable operation IDs and appear in canonical asset history.

## Validation and deterministic execution

Validation rejects:

- Missing or duplicate node/link IDs.
- Unknown node types, parameter keys, endpoints, or sockets.
- Incompatible socket types.
- Multiple inbound links on one input.
- Missing or incompatible graph outputs.
- Cycles anywhere in the document, including unused branches.
- Checksum drift and invalid editor positions.

Execution uses a stable topological order with node-ID tie-breaking. Only ancestors of declared outputs execute; valid unused nodes are reported as skipped. Reordering serialized node/link arrays therefore does not change the evaluated asset or execution trace.

Each trace entry records the stable node ID, type, and output checksums or statistics. `GeometryGraphEvaluator` caches complete evaluations by graph checksum plus external source checksum. Cached and uncached calls return deep-isolated results: caller mutation cannot poison a later cache hit.

## Original example

`examples/polyforge-geometry-graph/wayfinder-relay.graph.json` builds the original **Wayfinder Relay** through eight nodes:

```text
crystal source
  → face extrusion
  → edge split
  → stable midpoint move
  → whole-asset transform
  → four-level budget configuration
  → topology measurement
  → asset output
```

The graph contains editor-ready positions and exposes both `asset` and `stats`. Fresh evaluation produces `wayfinder-relay.forge.json` with 56 triangles, 40 vertices, 51 polygon faces, and four recorded geometry operations. `assets/prop.wayfinder_relay.asset.json` is derived from actual GLB readback:

| Level | Band | Budget | Measured GLB triangles | GLB bytes |
|---|---|---:|---:|---:|
| lod0 | hero | 64 | 56 | 3560 |
| lod1 | gameplay | 48 | 48 | 3332 |
| lod2 | far | 32 | 32 | 2852 |
| lod3 | proxy | 24 | 24 | 2612 |

GLBs remain reproducible generated artifacts rather than opaque committed binaries.

## Commands

Recreate the original graph:

```bash
node tools/polyforge_geometry_graph.mjs create \
  --output examples/polyforge-geometry-graph/wayfinder-relay.graph.json
```

Evaluate or bake it:

```bash
node tools/polyforge_geometry_graph.mjs evaluate \
  --graph examples/polyforge-geometry-graph/wayfinder-relay.graph.json

node tools/polyforge_geometry_graph.mjs build \
  --graph examples/polyforge-geometry-graph/wayfinder-relay.graph.json \
  --source-output /tmp/wayfinder-relay.forge.json \
  --output-dir /tmp/wayfinder-relay-bake
```

Run semantic and independent binary validation:

```bash
python3 tools/validate_polyforge_geometry_graphs.py
python3 -m unittest tools.tests.test_validate_polyforge_geometry_graphs
```

The Python validator performs its own DAG checks, invokes the native compiler, requires the committed descriptor to deeply equal a fresh graph bake, and reuses the independent GLB parser to verify actual indices, byte lengths, and triangle budgets. Canonical forge source is generated into the temporary build directory rather than duplicated in Git.

## Acceptance evidence

Validation passes with **62 native Node tests** and **48 Python repository tests**. The complete catalog gate passes with 326 components, 24 compounds / 405 wires, 35 genres / 767 component references, and 15 asset descriptors / 18 sockets. Both POLYFORGE validators pass: one original Asset Core source plus one eight-node graph, each with four independently checked GLB levels.

Native regression coverage includes:

- Every primitive and prompt family through `source.generate`.
- Stable graph serialization and checksum rejection.
- Cycles, unknown sockets, duplicate inputs, and socket-type mismatches.
- Stable-ID non-mutating graph commands.
- Manifold, non-degenerate edit chains and measured outputs.
- Exact socket transform math and invalid-scale rejection.
- External canonical sources and missing-source errors.
- Topological order independent of array order and unused-node pruning.
- Cache hits, invalidation by content, and mutation isolation.
- Strict four-level baking and real Three.js `GLTFLoader` loading.

The repository integration adds `presentation.geometry_graph`, inserts it into the POLYFORGE Asset Pipeline compound, and adopts it in Exploration / Collectathon without conflating authoring, baking, and runtime selection.

## Deferred

- Visual node-editor UI, drag/drop, box selection, minimaps, and undo-stack presentation.
- UV seams, unwrap, island packing, and texel-density nodes.
- Material graphs, shading variants, texture painting, and multi-material export.
- Skeletons, weight editing, animation clips, and deformation nodes.
- Geometry intersection/CSG, scattering, simulation, and world-generation nodes.
- Full visual workbench and world-model implementation.
