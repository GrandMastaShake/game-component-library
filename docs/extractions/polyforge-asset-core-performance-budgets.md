# POLYFORGE Asset Core & Performance Budgets

## Scope

Build the first visual-authoring foundation around the existing native POLYFORGE brick:

- A canonical editable `.forge.json` document.
- Stable vertex, edge, face, corner, and operation identities.
- Deterministic, replayable stable-ID editing.
- Measured triangle-budget enforcement for existing generation.
- Deterministic LOD generation and self-contained GLB export.
- Runtime descriptors derived from exported-file readback.
- Original example content and independent semantic regression validation.

This is original library technology. No commercial game code, assets, writing, characters, quests, item names, exact content tables, or balance data are included.

## Ownership

- `presentation.low_poly_generator`: parametric/prompt synthesis, legacy numeric edits, and measured `targetFaceCount` enforcement.
- `presentation.asset_core`: canonical source, stable identities, checksums, serialization, and stable-ID edit replay.
- `presentation.asset_baker`: offline simplification, triangle ceilings, LOD generation, GLB encoding, and readback statistics.
- `presentation.lod_system`: runtime distance selection only.

UV unwrapping/packing, texture painting, multi-material export, geometry nodes, rigging, animation, and studio UI remain later packs. The core reserves per-corner UV/normal data, per-vertex skin-weight slots, per-face material assignments, named sockets, and named UV-set declarations without claiming those systems are implemented.

## Why array indices cannot be the source format

The legacy `mesh-edit.js` API addresses vertices and faces by numeric array position. That remains valid for a short-lived geometry operation, but it is fragile as an editor document: splits, extrusions, deletions, and LOD compaction all change those positions.

`.forge.json` therefore uses durable IDs:

```text
v000000  vertex
e000000  edge
f000000  face
c000000  face corner
op000000 edit operation
```

Array order is serialization, not identity. Operations address `vertexIds`, `edgeId`, or `faceId`. Unchanged faces and corners retain their identities through splits and extrusion. New topology receives deterministic IDs from `nextIds`.

## Canonical document

The schema is `art/forge.schema.json`. The document contains:

- Asset identity, metre units, forward axis, format, and version.
- Generator settings and legacy operation provenance.
- Vertex positions, colors, and empty skin-weight slots.
- Edges and polygon faces with stable corners.
- Per-face material assignments and a portable initial PBR material.
- Named UV-set declarations and sockets.
- Ordered `lodN` budgets using `hero`, `gameplay`, `far`, and `proxy` bands.
- Stable-ID operation history and deterministic ID counters.
- An FNV-1a checksum over canonical, key-sorted content.

`stableStringify` provides deterministic serialization. `parseAssetDocument` rejects checksum drift, duplicate IDs, dangling references, malformed vectors, repeated face vertices, invalid sockets, and rising LOD budgets.

## Stable-ID edit behavior

- **Move:** changes positions only; all topology identities survive.
- **Split:** inserts a midpoint into every polygon adjacent to the selected edge. Existing face IDs survive; triangles can become quads. Baking selects a non-degenerate triangulation anchor so a collinear midpoint does not disappear into a zero-area triangle.
- **Extrude face:** duplicates the polygon boundary along its Newell normal, preserves the selected face/corner identities on the top, and creates one quad side per boundary edge.
- **Delete face:** removes the selected face while preventing deletion of the final face.

Every operation returns a new document, rebuilds edge references while preserving surviving edge IDs, appends an operation ID, updates the checksum, and revalidates.

## Performance budgets

`targetFaceCount` now means a measured triangle ceiling. Existing callers that omit it retain their original geometry. When supplied, reduction happens after legacy edits and before topology statistics are returned.

The deterministic reducer evaluates edges by squared length with index tie-breaking. A collapse is accepted only when:

1. The manifold link condition holds.
2. No remaining triangle becomes degenerate.
3. No affected normal folds through the old surface.
4. No duplicate face is produced.
5. A closed mesh does not collapse below four triangles.

If no legal candidate remains, `withinBudget` is false. `generate({targetFaceCount})` and strict `bakeAsset` throw with the remaining count. Non-strict baking can return the measured failure for diagnostics; it never relabels it as within budget.

Default LOD budgets are conservative. Custom aggressive budgets can be geometrically unreachable for a particular composed mesh; that is a content/budget error, not permission to emit broken topology.

## GLB baking and readback

The baker writes glTF 2.0 binary directly, with:

- POSITION, NORMAL, COLOR_0, and uint32 index accessors.
- One initial PBR material.
- A root mesh node and `socket_<name>` nodes.
- Correct chunk alignment, declared lengths, accessor bounds, position min/max, and buffer views.

`inspectGLB` opens the actual bytes and measures triangle count, vertex count, byte length, and socket names. `bakeAsset` uses those measurements—not source estimates—to populate `asset.schema.json` descriptors.

The repository-level Python validator performs a second, independent readback. It also requires the committed descriptor to deeply equal a fresh bake, preventing source, exporter, and descriptor drift.

## Original example

`examples/polyforge-asset-core/wayfinder.forge.json` is a seeded original crystal-family asset named **Wayfinder Beacon**. It applies one stable-ID edge split and midpoint move and declares one attachment socket.

Fresh bake:

| Level | Band | Budget | Measured GLB triangles | GLB bytes |
|---|---|---:|---:|---:|
| lod0 | hero | 50 | 50 | 3340 |
| lod1 | gameplay | 40 | 40 | 3056 |
| lod2 | far | 32 | 32 | 2816 |
| lod3 | proxy | 24 | 24 | 2612 |

The descriptor is `assets/prop.wayfinder.asset.json`. GLBs are generated into the consuming repository or a temporary validation directory rather than committed as opaque binaries here.

## API map

- `mesh-data.js`: portable indexed mesh conversion and guarded deterministic reduction.
- `asset-core.js`: canonical source, schema semantics, stable-ID operations, checksums, and polygon triangulation.
- `asset-baker.js`: LOD baking, GLB encoding, binary readback, and runtime descriptors.
- `index.js`: public generation, asset, baking, serialization, and stateful brick APIs.
- `tools/polyforge_asset_pipeline.mjs`: original example creation and reproducible baking.
- `tools/validate_polyforge_assets.py`: fresh-bake and independent GLB validation.

## Acceptance evidence

Native Node tests cover:

- Every primitive and prompt family at `targetFaceCount: 200`.
- Manifold and non-degenerate output after reduction.
- Explicit failure of an impossible closed-mesh budget.
- Stable identity uniqueness and deterministic serialization.
- Non-mutating moves, manifold edge splits, quad-sided extrusion, and face deletion boundaries.
- Checksum tampering and dangling-ID rejection.
- Four-level GLB triangle/byte/socket readback.
- Byte-for-byte deterministic baking and corrupt-GLB rejection.
- All pre-existing POLYFORGE behavior.

Python regression tests cover duplicate topology IDs, rising budgets, independent GLB measurements, and corrupt-file rejection.

## Deferred

- Geometry-node DAG and compiler.
- UV seams, unwrap, island packing, and texel-density workflows.
- Material graphs, shading variants, texture painting, and multi-material export.
- Skeletons, weights editing, animation clips, and runtime controllers.
- Full visual workbench, undo UI, raycast selection, autosave, and world-model integration.
