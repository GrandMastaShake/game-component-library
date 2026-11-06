# POLYFORGE native WebGL brick

Library-native implementation of `presentation.low_poly_generator`, `presentation.asset_core`, and `presentation.asset_baker`. The package is UI-independent and requires no hosted provider.

## Included

- Six parametric primitives: monolith, gem, orb, vessel, spire, and torus.
- Nine deterministic prompt families: house, rocket, mushroom, tree, cactus, crystal, rock, robot, and sword.
- Local prompt interpretation with an optional async AI-adapter boundary.
- Three.js `BufferGeometry` output with vertex colors, quad-dominant topology inspection, and legacy numeric mesh edits.
- **Measured `targetFaceCount` enforcement.** Reduction uses deterministic edge collapse with manifold-link, normal-fold, degenerate, and duplicate-face guards. An unreachable budget throws instead of silently returning an over-budget mesh.
- **Canonical `.forge.json` assets.** Stable vertex, edge, face, corner, and operation IDs replace array positions as the editing API. Documents carry generator provenance, positions/colors/skin-weight slots, face materials, UV-set declarations, sockets, LOD budgets, and deterministic checksums.
- **Stable-ID editing.** Move vertices, split edges, extrude polygons into quad sides, and delete faces without mutating the source document.
- **Deterministic LOD baking.** Ordered hero/gameplay/far/proxy budgets produce self-contained glTF 2.0 binaries.
- **Exported-file readback.** Runtime descriptors take triangle counts, byte counts, and socket presence from the actual GLB. The repository validator independently rebakes and checks the binary again.

The studio, raycast selection, undo UI, autosave, UV unwrapping/packing, texture painting, multi-material baking, rigging, animation, and runtime LOD selection remain separate concerns. Asset Baker 0.4 exports one material; the canonical document already reserves the material/corner structure needed by later packs.

## Generate and enforce a budget

```js
import * as THREE from 'three'
import { generateFromPrompt } from '@game-component-library/polyforge'

const result = await generateFromPrompt('a tall broad rocket', {
  seed: 42,
  targetFaceCount: 200,
})
scene.add(new THREE.Mesh(result.geometry, material))
console.log(result.stats.triangles, result.performanceBudget.withinBudget)
// performanceBudget is the contract's output (also at stats.budget); absent without targetFaceCount.
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
- `{type:'deleteFace', faceId:'f000000'}`

## Repository example

`examples/polyforge-asset-core/wayfinder.forge.json` is original editable source. `assets/prop.wayfinder.asset.json` is its measured runtime descriptor. Binary GLBs are intentionally generated into a temporary/consuming repository rather than committed here.

A descriptor is a claim about files in the consuming repository, so each level's `file` names the path that repository keeps it at, relative to its root: `public/assets/generated/<id>.<level>.glb` by default, the same folder every other generated prop's descriptor uses. Pass `bakeAsset(document, { fileRoot })` to choose another. The pipeline writes each GLB at its descriptor path under `--output-dir`, so baking with `--output-dir` set to the consumer's root puts the files exactly where the descriptor says.

```bash
node tools/polyforge_asset_pipeline.mjs bake \
  --source examples/polyforge-asset-core/wayfinder.forge.json \
  --output-dir /tmp/wayfinder-bake
```

The example currently measures 50/40/32/24 triangles across its four LODs.

## Verify

```bash
npm ci
npm test
```

From the repository root:

```bash
python3 tools/validate_polyforge_assets.py
python3 -m unittest tools.tests.test_validate_polyforge_assets
```

Native tests cover all generation families, closed/manifold defaults, deterministic generation, legacy edits, stable-ID edits, checksum rejection, measured triangle ceilings, impossible-budget failure, deterministic LODs, GLB corruption, byte-for-byte baking, and descriptor readback. The Python validator independently checks source structure, fresh-bake descriptor equality, GLB chunks/accessors, triangle counts, bytes, budgets, and sockets.
