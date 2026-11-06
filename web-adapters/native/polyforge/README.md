# POLYFORGE native WebGL brick

Library-native implementation of `presentation.low_poly_generator`, `presentation.asset_core`, `presentation.geometry_graph`, and `presentation.asset_baker`. The package is UI-independent and requires no hosted provider.

## Included

- Six parametric primitives: monolith, gem, orb, vessel, spire, and torus.
- Nine deterministic prompt families: house, rocket, mushroom, tree, cactus, crystal, rock, robot, and sword.
- Local prompt interpretation with an optional async AI-adapter boundary.
- Three.js `BufferGeometry` output with vertex colors, quad-dominant topology inspection, and legacy numeric mesh edits.
- **Measured `targetFaceCount` enforcement.** Reduction uses deterministic edge collapse with manifold-link, normal-fold, degenerate, and duplicate-face guards. An unreachable budget throws instead of silently returning an over-budget mesh.
- **Canonical `.forge.json` assets.** Stable vertex, edge, face, corner, and operation IDs replace array positions as the editing API. Documents carry generator provenance, positions/colors/skin-weight slots, face materials, UV-set declarations, sockets, LOD budgets, and deterministic checksums.
- **Stable-ID editing.** Move vertices, split edges, extrude polygons into quad sides, transform vertices and sockets, and delete faces without mutating the source document.
- **Typed geometry graphs.** Canonical `.graph.json` DAGs use stable node/link IDs, typed sockets, checksum validation, deterministic topological execution, dependency pruning, and non-mutating graph editing commands. Ten nodes cover sources, geometry edits, transforms, budget configuration, measurement, and output.
- **Content-keyed evaluation caches.** `GeometryGraphEvaluator` reuses unchanged results while returning isolated clones so callers cannot corrupt cached assets.
- **Deterministic LOD baking.** Ordered hero/gameplay/far/proxy budgets produce self-contained glTF 2.0 binaries.
- **Exported-file readback.** Runtime descriptors take triangle counts, byte counts, and socket presence from the actual GLB. The repository validator independently rebakes and checks the binary again.

The studio, raycast selection, undo UI, autosave, UV unwrapping/packing, texture painting, multi-material baking, rigging, animation, and runtime LOD selection remain separate concerns. Asset Baker 0.5 exports one material; the canonical document already reserves the material/corner structure needed by later packs.

## Generate and enforce a budget

```js
import * as THREE from 'three'
import { generateFromPrompt } from '@game-component-library/polyforge'

const result = await generateFromPrompt('a tall broad rocket', {
  seed: 42,
  targetFaceCount: 200,
})
scene.add(new THREE.Mesh(result.geometry, material))
console.log(result.stats.triangles, result.stats.budget.withinBudget)
```

Consumers own and must dispose returned geometries. Legacy `meshEdits` remains supported for compatibility; new editor state should use stable-ID asset operations.

## Create, edit, serialize, and bake

```js
import {
  applyAssetOperations,
  bakeAsset,
  createAssetDocument,
  generate,
  serializeAssetDocument,
} from '@game-component-library/polyforge'

const generated = generate({ primitive: 'rocket', seed: 42 })
const source = createAssetDocument({
  id: 'prop.wayfinder',
  name: 'Wayfinder Beacon',
  result: generated,
  sockets: [{ name: 'attachment', position: [0, 3.9, 0] }],
})
generated.geometry.dispose()

const split = applyAssetOperations(source, [
  { type: 'split', edgeId: source.edges[0].id },
])
const midpoint = split.vertices.at(-1)
const edited = applyAssetOperations(split, [
  { type: 'move', vertexIds: [midpoint.id], delta: [0.02, 0.04, -0.03] },
])

const serialized = serializeAssetDocument(edited)
const baked = bakeAsset(edited) // strict budgets by default
for (const level of baked.levels) {
  console.log(level.level, level.readback.triangles, level.readback.bytes)
  // level.glb is a Uint8Array ready to write or upload.
}
console.log(baked.descriptor)
```

`applyAssetOperations` returns a new document and updates its checksum. Supported operations:

- `{type:'move', vertexIds:[...], delta:[x,y,z]}`
- `{type:'split', edgeId:'e000000'}`
- `{type:'extrudeFace', faceId:'f000000', distance:0.25}`
- `{type:'transform', vertexIds:[...], translation:[x,y,z], scale:[x,y,z], rotation:[x,y,z], pivot:[x,y,z], includeSockets:true}` (all fields are optional; omitting `vertexIds` selects the whole asset, rotation is XYZ degrees, and scale components must be positive)
- `{type:'deleteFace', faceId:'f000000'}`

## Evaluate and bake a geometry graph

```js
import {
  GeometryGraphEvaluator,
  bakeGeometryGraph,
  parseGeometryGraph,
} from '@game-component-library/polyforge'
import { readFile } from 'node:fs/promises'

const graph = parseGeometryGraph(await readFile('wayfinder-relay.graph.json', 'utf8'))
const evaluator = new GeometryGraphEvaluator()
const first = evaluator.evaluate(graph)
console.log(first.stats, first.trace, evaluator.stats)

const second = evaluator.evaluate(graph) // cache hit; returned documents remain mutation-isolated
const baked = bakeGeometryGraph(graph, { evaluator })
console.log(baked.descriptor.levels)
```

A graph declares `nodes`, `links`, and typed `outputs.asset` / optional `outputs.stats`. `source.generate` creates an original asset locally; `source.asset` accepts either an embedded document or the `sourceDocument` evaluation input. Edit nodes use the same durable topology IDs as Asset Core. `configure.budgets` declares final LOD ceilings, and `measure.asset` exposes canonical topology statistics.

`applyGeometryGraphOperations` supports `addNode`, `removeNode`, `addLink`, `removeLink`, `setParameters`, and `setOutput`. Every command returns a new checksummed graph and preserves surviving node/link IDs. Cycles, unknown node types or sockets, type mismatches, checksum drift, and multiple inbound links fail validation.

## Repository example

`examples/polyforge-asset-core/wayfinder.forge.json` is original editable source. `assets/prop.wayfinder.asset.json` is its measured runtime descriptor. Binary GLBs are intentionally generated into a temporary/consuming repository rather than committed here.

```bash
node tools/polyforge_asset_pipeline.mjs bake \
  --source examples/polyforge-asset-core/wayfinder.forge.json \
  --output-dir /tmp/wayfinder-bake
```

The example currently measures 50/40/32/24 triangles across its four LODs.

`examples/polyforge-geometry-graph/wayfinder-relay.graph.json` is the original **Wayfinder Relay** eight-node DAG. Its freshly evaluated `wayfinder-relay.forge.json` contains 56 triangles; measured GLB LODs are 56/48/32/24 triangles. The runtime descriptor is `assets/prop.wayfinder_relay.asset.json`.

```bash
node tools/polyforge_geometry_graph.mjs evaluate \
  --graph examples/polyforge-geometry-graph/wayfinder-relay.graph.json

node tools/polyforge_geometry_graph.mjs build \
  --graph examples/polyforge-geometry-graph/wayfinder-relay.graph.json \
  --source-output /tmp/wayfinder-relay.forge.json \
  --output-dir /tmp/wayfinder-relay-bake
```

## Verify

```bash
npm ci
npm test
```

From the repository root:

```bash
python3 tools/validate_polyforge_assets.py
python3 tools/validate_polyforge_geometry_graphs.py
python3 -m unittest \
  tools.tests.test_validate_polyforge_assets \
  tools.tests.test_validate_polyforge_geometry_graphs
```

Native tests cover all generation families, closed/manifold defaults, deterministic generation, legacy and stable-ID edits, transform math, graph identity and checksum rejection, typed DAG validation, topological order, dependency pruning, cache isolation, measured triangle ceilings, deterministic LODs, real Three.js GLB loading, and descriptor readback. Independent Python validators check source and graph semantics, fresh evaluation/bake equality, GLB chunks/accessors, triangle counts, bytes, budgets, and sockets.
