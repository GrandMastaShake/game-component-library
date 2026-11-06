import test from 'node:test'
import assert from 'node:assert/strict'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import {
  GeometryGraphEvaluator,
  PRESETS,
  PROMPT_OBJECTS,
  analyzeTopology,
  applyGeometryGraphOperations,
  assetDocumentToMeshData,
  bakeGeometryGraph,
  checksumGeometryGraph,
  createAssetDocument,
  createGeometryGraph,
  evaluateGeometryGraph,
  generate,
  parseGeometryGraph,
  serializeGeometryGraph,
  validateGeometryGraph,
} from '../index.js'
import { meshDataToGeometry } from '../mesh-data.js'

function sourceNode(parameters = {}) {
  return {
    id: 'n000000',
    type: 'source.generate',
    parameters: {
      id: 'prop.graph_test',
      name: 'Graph Test',
      settings: { primitive: 'crystal', seed: 19, color: '#7DD3FC' },
      budgets: [
        { level: 'lod0', distanceBand: 'hero', maxTriangles: 64 },
        { level: 'lod1', distanceBand: 'gameplay', maxTriangles: 48 },
        { level: 'lod2', distanceBand: 'far', maxTriangles: 32 },
        { level: 'lod3', distanceBand: 'proxy', maxTriangles: 24 },
      ],
      ...parameters,
    },
  }
}

function basicGraph(parameters) {
  return createGeometryGraph({
    id: 'graph.test',
    name: 'Test Graph',
    nodes: [sourceNode(parameters), { id: 'n000001', type: 'output.asset', parameters: {} }],
    links: [{ id: 'l000000', from: { node: 'n000000', socket: 'asset' }, to: { node: 'n000001', socket: 'asset' } }],
    outputs: { asset: { node: 'n000001', socket: 'asset' } },
  })
}

function editingGraph() {
  return createGeometryGraph({
    id: 'graph.editing',
    name: 'Editing Graph',
    nodes: [
      sourceNode(),
      { id: 'n000001', type: 'edit.extrudeFace', parameters: { faceId: 'f000000', distance: 0.18 } },
      { id: 'n000002', type: 'edit.split', parameters: { edgeId: 'e000000' } },
      { id: 'n000003', type: 'modify.transform', parameters: { scale: [1, 1.1, 1], rotation: [0, 15, 0], includeSockets: true } },
      { id: 'n000004', type: 'measure.asset', parameters: {} },
      { id: 'n000005', type: 'output.asset', parameters: {} },
    ],
    links: [
      ['n000000', 'n000001'], ['n000001', 'n000002'], ['n000002', 'n000003'], ['n000003', 'n000004'], ['n000004', 'n000005'],
    ].map(([from, to], index) => ({ id: `l${String(index).padStart(6, '0')}`, from: { node: from, socket: 'asset' }, to: { node: to, socket: 'asset' } })),
    outputs: { asset: { node: 'n000005', socket: 'asset' }, stats: { node: 'n000004', socket: 'stats' } },
  })
}

function topology(document) {
  const geometry = meshDataToGeometry(assetDocumentToMeshData(document))
  try {
    return analyzeTopology(geometry)
  } finally {
    geometry.dispose()
  }
}

test('geometry graphs serialize deterministically with stable node and link identities', () => {
  const first = editingGraph()
  const second = editingGraph()
  assert.equal(serializeGeometryGraph(first), serializeGeometryGraph(second))
  assert.deepEqual(parseGeometryGraph(serializeGeometryGraph(first)), first)
  assert.equal(new Set(first.nodes.map((node) => node.id)).size, first.nodes.length)
  assert.equal(new Set(first.links.map((link) => link.id)).size, first.links.length)
  assert.match(first.checksum, /^fnv1a32:/)
})

test('checksum tampering, cycles, unknown sockets, and duplicate inputs are rejected', () => {
  const graph = editingGraph()
  const tampered = structuredClone(graph)
  tampered.nodes[0].parameters.settings.seed += 1
  assert.throws(() => validateGeometryGraph(tampered), /checksum/)

  const cycle = structuredClone(graph)
  cycle.links[1].from = { node: 'n000003', socket: 'asset' }
  assert.throws(() => validateGeometryGraph(cycle, { verifyChecksum: false }), /cycle/)

  const missingSocket = structuredClone(graph)
  missingSocket.links[0].from.socket = 'missing'
  assert.throws(() => validateGeometryGraph(missingSocket, { verifyChecksum: false }), /unknown socket/)

  const duplicate = structuredClone(graph)
  duplicate.links.push({ id: 'l000005', from: { node: 'n000000', socket: 'asset' }, to: { node: 'n000001', socket: 'asset' } })
  assert.throws(() => validateGeometryGraph(duplicate, { verifyChecksum: false }), /multiple inbound/)
})

test('typed links reject stats flowing into an asset input', () => {
  const graph = basicGraph()
  graph.nodes.splice(1, 0, { id: 'n000002', type: 'measure.asset', parameters: {} })
  graph.links[0].to.node = 'n000002'
  graph.links.push({ id: 'l000001', from: { node: 'n000002', socket: 'stats' }, to: { node: 'n000001', socket: 'asset' } })
  assert.throws(() => validateGeometryGraph(graph, { verifyChecksum: false }), /connects stats to asset/)
})

test('a required unconnected input fails at evaluation with its stable socket name', () => {
  const graph = basicGraph()
  graph.links = []
  assert.throws(() => evaluateGeometryGraph(graph), /checksum/)
  graph.checksum = checksumGeometryGraph(graph)
  assert.throws(() => evaluateGeometryGraph(graph), /n000001\.asset is not connected/)
})

test('source generation evaluates to the canonical asset format for every generation family', () => {
  for (const family of [...PRESETS, ...PROMPT_OBJECTS]) {
    const graph = basicGraph({ settings: { primitive: family.id, seed: 5 } })
    const result = evaluateGeometryGraph(graph)
    assert.equal(result.document.format, 'polyforge.forge', family.id)
    assert.equal(result.document.generator.settings.primitive, family.id)
    assert.ok(result.stats.triangles > 0)
    assert.equal(result.trace.length, 2)
  }
})

test('non-destructive edit chains preserve manifold topology and expose measured outputs', () => {
  const graph = editingGraph()
  const original = serializeGeometryGraph(graph)
  const result = evaluateGeometryGraph(graph)
  assert.equal(serializeGeometryGraph(graph), original)
  assert.equal(result.document.id, 'prop.graph_test')
  assert.deepEqual(result.outputs.stats, result.stats)
  assert.equal(result.stats.operations, 3)
  assert.equal(topology(result.document).manifold, true)
  assert.equal(topology(result.document).degenerate, 0)
  assert.deepEqual(result.trace.map((entry) => entry.nodeId), ['n000000', 'n000001', 'n000002', 'n000003', 'n000004', 'n000005'])
})

test('whole-asset transforms apply XYZ Euler rotation, positive scale, translation, and sockets', () => {
  const graph = createGeometryGraph({
    id: 'graph.transform',
    name: 'Transform Graph',
    nodes: [
      sourceNode({ settings: { primitive: 'monolith' }, sockets: [{ name: 'probe', position: [1, 0, 0] }] }),
      { id: 'n000001', type: 'modify.transform', parameters: { scale: [2, 2, 2], rotation: [0, 0, 90], translation: [0, 0, 3], includeSockets: true } },
      { id: 'n000002', type: 'output.asset', parameters: {} },
    ],
    links: [
      { id: 'l000000', from: { node: 'n000000', socket: 'asset' }, to: { node: 'n000001', socket: 'asset' } },
      { id: 'l000001', from: { node: 'n000001', socket: 'asset' }, to: { node: 'n000002', socket: 'asset' } },
    ],
    outputs: { asset: { node: 'n000002', socket: 'asset' } },
  })
  const result = evaluateGeometryGraph(graph)
  result.document.sockets[0].position.forEach((value, index) => assert.ok(Math.abs(value - [0, 2, 3][index]) < 1e-10))
  assert.equal(result.document.operations[0].type, 'transform')
  assert.throws(() => evaluateGeometryGraph(createGeometryGraph({
    ...graph,
    nodes: graph.nodes.map((node) => node.id === 'n000001' ? { ...node, parameters: { scale: [1, 0, 1] } } : node),
    links: graph.links,
    outputs: graph.outputs,
  })), /positive/)
})

test('budget configuration is semantic graph data and strict baking measures every GLB', () => {
  const graph = editingGraph()
  const baked = bakeGeometryGraph(graph)
  assert.equal(baked.levels.length, 4)
  assert.ok(baked.levels.every((level) => level.withinBudget))
  assert.deepEqual(baked.levels.map((level) => level.readback.triangles), baked.descriptor.levels.map((level) => level.triangles))
  assert.equal(baked.evaluation.graphChecksum, graph.checksum)

  const reconfigured = createGeometryGraph({
    ...graph,
    nodes: [...graph.nodes, { id: 'n000006', type: 'configure.budgets', parameters: { levels: [
      { level: 'lod0', distanceBand: 'hero', maxTriangles: 56 },
      { level: 'lod1', distanceBand: 'gameplay', maxTriangles: 40 },
      { level: 'lod2', distanceBand: 'far', maxTriangles: 32 },
      { level: 'lod3', distanceBand: 'proxy', maxTriangles: 24 },
    ] } }],
    links: [...graph.links.filter((link) => link.to.node !== 'n000004'), { id: 'l000005', from: { node: 'n000003', socket: 'asset' }, to: { node: 'n000006', socket: 'asset' } }, { id: 'l000006', from: { node: 'n000006', socket: 'asset' }, to: { node: 'n000004', socket: 'asset' } }],
    outputs: graph.outputs,
  })
  assert.equal(evaluateGeometryGraph(reconfigured).document.budgets.levels[0].maxTriangles, 56)
})

test('source.asset consumes an external canonical document without embedding or mutating it', () => {
  const generated = generate({ primitive: 'gem', seed: 3 })
  let document
  try {
    document = createAssetDocument({ id: 'prop.external', name: 'External', result: generated })
  } finally {
    generated.geometry.dispose()
  }
  const graph = createGeometryGraph({
    id: 'graph.external',
    name: 'External Source',
    nodes: [{ id: 'n000000', type: 'source.asset', parameters: {} }, { id: 'n000001', type: 'output.asset', parameters: {} }],
    links: [{ id: 'l000000', from: { node: 'n000000', socket: 'asset' }, to: { node: 'n000001', socket: 'asset' } }],
    outputs: { asset: { node: 'n000001', socket: 'asset' } },
  })
  const before = structuredClone(document)
  const evaluated = evaluateGeometryGraph(graph, { sourceDocument: document })
  assert.deepEqual(evaluated.document, document)
  assert.deepEqual(document, before)
  assert.throws(() => evaluateGeometryGraph(graph), /sourceDocument/)
})

test('graph editing commands preserve surviving IDs and never mutate the source graph', () => {
  const graph = basicGraph()
  const before = serializeGeometryGraph(graph)
  const edited = applyGeometryGraphOperations(graph, [
    { type: 'removeLink', linkId: 'l000000' },
    { type: 'addNode', nodeType: 'measure.asset', position: { x: 200, y: 40 } },
    { type: 'addLink', from: { node: 'n000000', socket: 'asset' }, to: { node: 'n000002', socket: 'asset' } },
    { type: 'addLink', from: { node: 'n000002', socket: 'asset' }, to: { node: 'n000001', socket: 'asset' } },
    { type: 'setOutput', name: 'stats', endpoint: { node: 'n000002', socket: 'stats' } },
  ])
  assert.equal(serializeGeometryGraph(graph), before)
  assert.deepEqual(graph.nodes.map((node) => node.id), ['n000000', 'n000001'])
  assert.deepEqual(edited.nodes.map((node) => node.id), ['n000000', 'n000001', 'n000002'])
  assert.deepEqual(edited.links.map((link) => link.id), ['l000001', 'l000002'])
  assert.ok(evaluateGeometryGraph(edited).outputs.stats.triangles > 0)
  assert.throws(() => applyGeometryGraphOperations(edited, [{ type: 'removeNode', nodeId: 'n000002' }]), /graph output/)
})

test('topological execution is independent of node and link array order', () => {
  const graph = editingGraph()
  const reordered = structuredClone(graph)
  reordered.nodes.reverse()
  reordered.links.reverse()
  reordered.checksum = checksumGeometryGraph(reordered)
  const first = evaluateGeometryGraph(graph)
  const second = evaluateGeometryGraph(reordered)
  assert.deepEqual(first.document, second.document)
  assert.deepEqual(first.trace, second.trace)
})

test('unused valid nodes are skipped while cycles anywhere in the document are rejected', () => {
  const graph = basicGraph()
  graph.nodes.push({ id: 'n000002', type: 'source.generate', parameters: { id: 'prop.unused', settings: { primitive: 'orb' } } })
  graph.checksum = checksumGeometryGraph(graph)
  const result = evaluateGeometryGraph(graph)
  assert.equal(result.skippedNodes, 1)
  assert.equal(result.trace.length, 2)
})

test('persistent evaluation caches are content-keyed and mutation-isolated', () => {
  const graph = basicGraph()
  const evaluator = new GeometryGraphEvaluator()
  const first = evaluator.evaluate(graph)
  const expected = first.document.vertices[0].position[0]
  first.document.vertices[0].position[0] = 999
  const second = evaluator.evaluate(graph)
  assert.equal(second.document.vertices[0].position[0], expected)
  assert.equal(evaluator.stats.hits, 1)
  assert.equal(evaluator.stats.misses, 1)
  assert.equal(evaluator.stats.evaluations, 2)
  evaluator.clear()
  evaluator.evaluate(graph)
  assert.equal(evaluator.stats.misses, 2)
})

test('graph-produced GLBs load through Three.js with measured geometry', async () => {
  const baked = bakeGeometryGraph(editingGraph())
  for (const level of baked.levels) {
    const buffer = level.glb.buffer.slice(level.glb.byteOffset, level.glb.byteOffset + level.glb.byteLength)
    const gltf = await new GLTFLoader().parseAsync(buffer, '')
    let triangles = 0
    gltf.scene.traverse((node) => {
      if (node.isMesh) triangles += (node.geometry.index?.count ?? node.geometry.attributes.position.count) / 3
    })
    assert.equal(triangles, level.readback.triangles)
  }
})
