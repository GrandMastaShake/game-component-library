# POLYFORGE native WebGL brick

Library-native implementation of `presentation.low_poly_generator`, packaged from the POLYFORGE v0.3 mesh studio as a reusable, UI-independent module.

## Included

- Six parametric primitives: monolith, gem, orb, vessel, spire, and torus.
- Nine deterministic prompt families: house, rocket, mushroom, tree, cactus, crystal, rock, robot, and sword.
- Local prompt interpretation with an optional async AI-adapter boundary; no credentials or hosted provider required.
- Three.js `BufferGeometry` output with vertex colors.
- Quad-dominant triangle-pair unification and topology statistics.
- Replayable vertex moves, edge splits, triangular-face extrusion, and face deletion.
- Plain-object serialization through `toMeshData` for non-Three.js consumers.

The studio, raycast selection, undo UI, autosave, and GLB export remain in POLYFORGE. This package is the generation/editing brick a game or editor can embed.

## Use

```js
import * as THREE from 'three'
import { LowPolyGenerator, generateFromPrompt, toMeshData } from '@game-component-library/polyforge'

const result = await generateFromPrompt('a tall broad rocket', { seed: 42 })
scene.add(new THREE.Mesh(result.geometry, material))
console.log(result.stats.quadRatio, result.stats.manifold)

const brick = new LowPolyGenerator({ primitive: 'tree', seed: 7 })
const moved = brick.generate({
  meshEdits: [{ type: 'move', indices: [0], delta: [0, 0.2, 0] }],
})
const portable = toMeshData(moved)
```

`generate()` and `generateFromPrompt()` return a new geometry. Consumers own and must dispose returned geometries when replacing or removing them. Editing never mutates the input geometry.

## Verify

```bash
npm ci
npm test
```

The tests cover all nine prompt families, closed/manifold defaults, quad dominance, deterministic generation, prompt adapters, vertex moves, edge splits, face extrusion/deletion, serialization, and the stateful brick API.
