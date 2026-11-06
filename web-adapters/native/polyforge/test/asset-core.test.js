import test from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_FILE_ROOT,
  PRESETS,
  PROMPT_OBJECTS,
  analyzeTopology,
  applyAssetOperations,
  assetDocumentStats,
  assetDocumentToMeshData,
  bakeAsset,
  bakeGeneratedAsset,
  createAssetDocument,
  generate,
  inspectGLB,
  parseAssetDocument,
  serializeAssetDocument,
} from '../index.js'
import { meshDataToGeometry } from '../mesh-data.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

function asset(input = { primitive: 'rocket', seed: 42 }, extras = {}) {
  const result = generate(input)
  try {
    return createAssetDocument({ id: 'prop.wayfinder', name: 'Wayfinder', result, ...extras })
  } finally {
    result.geometry.dispose()
  }
}

function topology(document) {
  const geometry = meshDataToGeometry(assetDocumentToMeshData(document))
  try {
    return analyzeTopology(geometry)
  } finally {
    geometry.dispose()
  }
}

test('asset documents expose stable topology identities and deterministic canonical serialization', () => {
  const first = asset()
  const second = asset()
  const stats = assetDocumentStats(first)
  assert.ok(stats.vertices > 0)
  assert.equal(stats.triangles, 176)
  assert.equal(stats.corners, stats.triangles * 3)
  assert.equal(new Set(first.vertices.map((item) => item.id)).size, stats.vertices)
  assert.equal(new Set(first.edges.map((item) => item.id)).size, stats.edges)
  assert.equal(new Set(first.faces.map((item) => item.id)).size, stats.faces)
  assert.equal(new Set(first.faces.flatMap((face) => face.corners.map((corner) => corner.id))).size, stats.corners)
  assert.equal(serializeAssetDocument(first), serializeAssetDocument(second))
  assert.deepEqual(parseAssetDocument(serializeAssetDocument(first)), first)
})

test('ID-based moves are replayable and never mutate the source asset', () => {
  const source = asset()
  const vertex = source.vertices[0]
  const moved = applyAssetOperations(source, [{ type: 'move', vertexIds: [vertex.id], delta: [0, 0.5, 0] }])
  assert.notDeepEqual(moved.vertices[0].position, vertex.position)
  assert.equal(source.vertices[0].position[1], vertex.position[1])
  assert.equal(moved.vertices[0].id, vertex.id)
  assert.equal(moved.faces[0].id, source.faces[0].id)
  assert.equal(moved.operations[0].id, 'op000000')
  assert.notEqual(moved.checksum, source.checksum)
})

test('ID-based edge splits preserve face identities and closed topology', () => {
  const source = asset()
  const originalFaceIds = source.faces.map((face) => face.id)
  const split = applyAssetOperations(source, [{ type: 'split', edgeId: source.edges[0].id }])
  assert.equal(split.vertices.length, source.vertices.length + 1)
  assert.equal(split.faces.length, source.faces.length)
  assert.deepEqual(split.faces.map((face) => face.id), originalFaceIds)
  assert.ok(split.faces.some((face) => face.corners.length === 4))
  assert.equal(topology(split).manifold, true)
  assert.equal(topology(split).triangles, topology(source).triangles + 2)
})

test('ID-based polygon extrusion creates quad sides and preserves a closed mesh', () => {
  const source = asset()
  const result = applyAssetOperations(source, [{ type: 'extrudeFace', faceId: source.faces[0].id, distance: 0.3 }])
  assert.equal(result.vertices.length, source.vertices.length + 3)
  assert.equal(result.faces.length, source.faces.length + 3)
  assert.equal(result.faces.filter((face) => face.corners.length === 4).length, 3)
  assert.equal(result.faces[0].id, source.faces[0].id)
  assert.equal(topology(result).manifold, true)
})

test('ID-based face deletion opens a boundary and checksum tampering is rejected', () => {
  const source = asset()
  const result = applyAssetOperations(source, [{ type: 'deleteFace', faceId: source.faces[0].id }])
  assert.equal(topology(result).boundary, 3)
  const tampered = JSON.parse(serializeAssetDocument(result))
  tampered.vertices[0].position[0] += 1
  assert.throws(() => parseAssetDocument(JSON.stringify(tampered)), /checksum/)
  assert.throws(() => applyAssetOperations(result, [{ type: 'move', vertexIds: ['v999999'], delta: [0, 0, 0] }]), /no longer exists/)
})

for (const family of [...PRESETS, ...PROMPT_OBJECTS]) {
  test(`${family.id}: targetFaceCount is a measured hard ceiling`, () => {
    const result = generate({ primitive: family.id, targetFaceCount: 200 })
    assert.ok(result.stats.triangles <= 200)
    assert.equal(result.stats.budget.withinBudget, true)
    assert.equal(result.stats.manifold, true)
    assert.equal(result.stats.degenerate, 0)
    result.geometry.dispose()
  })
}

test('every family bakes a complete default LOD chain within budget and without broken topology', () => {
  for (const family of [...PRESETS, ...PROMPT_OBJECTS]) {
    const baked = bakeGeneratedAsset({ id: 'prop.probe', input: { primitive: family.id } })
    assert.equal(baked.levels.length, 4, family.id)
    for (const level of baked.levels) {
      assert.ok(level.withinBudget, `${family.id} ${level.level}`)
      const geometry = meshDataToGeometry(level.mesh)
      const stats = analyzeTopology(geometry)
      assert.equal(stats.manifold, true, `${family.id} ${level.level}`)
      assert.equal(stats.degenerate, 0, `${family.id} ${level.level}`)
      geometry.dispose()
    }
  }
})

test('an impossible closed-mesh budget fails explicitly', () => {
  assert.throws(() => generate({ primitive: 'monolith', targetFaceCount: 2 }), /unreachable/)
})

test('GLB baking measures every LOD from exported bytes and preserves sockets', () => {
  const source = asset({ primitive: 'rocket', seed: 42 }, {
    budgets: [
      { level: 'lod0', distanceBand: 'hero', maxTriangles: 176 },
      { level: 'lod1', distanceBand: 'gameplay', maxTriangles: 112 },
      { level: 'lod2', distanceBand: 'far', maxTriangles: 64 },
      { level: 'lod3', distanceBand: 'proxy', maxTriangles: 32 },
    ],
    sockets: [{ name: 'hand_right', position: [1, 2, 0] }],
  })
  const baked = bakeAsset(source)
  assert.equal(baked.levels.length, 4)
  assert.deepEqual(baked.levels.map((level) => level.readback.triangles), baked.descriptor.levels.map((level) => level.triangles))
  assert.deepEqual(baked.levels.map((level) => level.readback.bytes), baked.descriptor.levels.map((level) => level.bytes))
  assert.ok(baked.levels.every((level) => level.withinBudget))
  assert.ok(baked.descriptor.levels.every((level, index, levels) => index === 0 || level.triangles <= levels[index - 1].triangles))
  assert.deepEqual(baked.levels[0].readback.sockets, ['hand_right'])
  assert.equal(baked.levels[0].readback.format, 'gltf-binary')
  assert.ok(baked.levels[0].readback.bytes > 1000)
})

test('exported GLBs load through Three.js with the measured triangle count and sockets', async () => {
  const source = asset({ primitive: 'rocket', seed: 42 }, {
    sockets: [{ name: 'attachment', position: [0, 3.9, 0] }],
  })
  const baked = bakeAsset(source)
  for (const level of baked.levels) {
    const buffer = level.glb.buffer.slice(level.glb.byteOffset, level.glb.byteOffset + level.glb.byteLength)
    const gltf = await new GLTFLoader().parseAsync(buffer, '')
    let triangles = 0
    const names = []
    gltf.scene.traverse((node) => {
      if (node.isMesh) triangles += (node.geometry.index?.count ?? node.geometry.attributes.position.count) / 3
      if (node.name.startsWith('socket_')) names.push(node.name)
    })
    assert.equal(triangles, level.readback.triangles)
    assert.deepEqual(names, ['socket_attachment'])
  }
})

test('bakes are byte-for-byte deterministic and corrupt GLBs fail readback', () => {
  const options = { id: 'prop.wayfinder', input: { primitive: 'tree', seed: 7 }, budgets: [
    { level: 'lod0', distanceBand: 'hero', maxTriangles: 70 },
    { level: 'lod1', distanceBand: 'gameplay', maxTriangles: 40 },
    { level: 'lod2', distanceBand: 'far', maxTriangles: 24 },
    { level: 'lod3', distanceBand: 'proxy', maxTriangles: 16 },
  ] }
  const first = bakeGeneratedAsset(options)
  const second = bakeGeneratedAsset(options)
  assert.deepEqual(first.levels[2].glb, second.levels[2].glb)
  assert.deepEqual(first.descriptor, second.descriptor)
  const corrupt = first.levels[0].glb.slice()
  corrupt[0] = 0
  assert.throws(() => inspectGLB(corrupt), /magic/)
})

test('generate publishes the performanceBudget output its contract declares, only when a budget was asked for', () => {
  const budgeted = generate({ primitive: 'crystal', seed: 7, targetFaceCount: 40 })
  assert.deepEqual(budgeted.performanceBudget, budgeted.stats.budget)
  assert.equal(budgeted.performanceBudget.targetTriangles, 40)
  assert.equal(budgeted.performanceBudget.withinBudget, true)
  assert.equal(budgeted.performanceBudget.triangles, budgeted.stats.triangles)
  for (const key of ['originalTriangles', 'triangles', 'targetTriangles', 'collapses', 'withinBudget']) {
    assert.ok(key in budgeted.performanceBudget, key)
  }
  budgeted.geometry.dispose()
  const free = generate({ primitive: 'crystal', seed: 7 })
  assert.equal('performanceBudget' in free, false)
  free.geometry.dispose()
})

test('descriptor files name where the consumer keeps them, and fileRoot moves them', () => {
  const source = asset({ primitive: 'crystal', seed: 7 })
  const baked = bakeAsset(source)
  assert.equal(DEFAULT_FILE_ROOT, 'public/assets/generated')
  for (const level of baked.descriptor.levels) {
    assert.equal(level.file, `public/assets/generated/${source.id}.${level.level}.glb`)
  }
  const moved = bakeAsset(source, { fileRoot: 'static/models' })
  assert.deepEqual(moved.descriptor.levels.map((level) => level.file), baked.descriptor.levels.map((level) => level.file.replace('public/assets/generated/', 'static/models/')))
  // Only the path moves: the bytes are the same bake.
  assert.deepEqual(moved.levels.map((level) => level.readback.bytes), baked.levels.map((level) => level.readback.bytes))
  for (const bad of ['', '/abs/path', '../outside', 'a/../b', 'a\b', 'a//b', 5]) {
    assert.throws(() => bakeAsset(source, { fileRoot: bad }), /fileRoot/, JSON.stringify(bad))
  }
  const viaWrapper = bakeGeneratedAsset({ id: 'prop.probe', input: { primitive: 'crystal' }, fileRoot: 'x' })
  assert.ok(viaWrapper.descriptor.levels.every((level) => level.file.startsWith('x/prop.probe.')))
})
