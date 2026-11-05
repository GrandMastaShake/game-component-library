import {
  applyAssetOperations,
  assetDocumentStats,
  checksumAssetDocument,
  createAssetDocument,
  stableStringify,
  validateAssetDocument,
} from './asset-core.js'
import { bakeAsset } from './asset-baker.js'
import { generate } from './index.js'

export const GEOMETRY_GRAPH_FORMAT = 'polyforge.geometry'
export const GEOMETRY_GRAPH_VERSION = '1.0.0'

const GRAPH_ID = /^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$/
const NODE_ID = /^n[0-9]{6}$/
const LINK_ID = /^l[0-9]{6}$/
const OUTPUT_NAME = /^(asset|stats)$/
const ROOT_KEYS = new Set(['format', 'version', 'id', 'name', 'nodes', 'links', 'outputs', 'nextIds', 'checksum'])

export const GEOMETRY_NODE_TYPES = Object.freeze({
  'source.generate': { inputs: {}, outputs: { asset: 'asset' }, parameters: ['id', 'name', 'settings', 'budgets', 'sockets', 'materials'] },
  'source.asset': { inputs: {}, outputs: { asset: 'asset' }, parameters: ['document'] },
  'edit.move': { inputs: { asset: 'asset' }, outputs: { asset: 'asset' }, parameters: ['vertexIds', 'delta'] },
  'edit.split': { inputs: { asset: 'asset' }, outputs: { asset: 'asset' }, parameters: ['edgeId'] },
  'edit.extrudeFace': { inputs: { asset: 'asset' }, outputs: { asset: 'asset' }, parameters: ['faceId', 'distance'] },
  'edit.deleteFace': { inputs: { asset: 'asset' }, outputs: { asset: 'asset' }, parameters: ['faceId'] },
  'modify.transform': { inputs: { asset: 'asset' }, outputs: { asset: 'asset' }, parameters: ['vertexIds', 'translation', 'scale', 'rotation', 'pivot', 'includeSockets'] },
  'configure.budgets': { inputs: { asset: 'asset' }, outputs: { asset: 'asset' }, parameters: ['levels'] },
  'measure.asset': { inputs: { asset: 'asset' }, outputs: { asset: 'asset', stats: 'stats' }, parameters: [] },
  'output.asset': { inputs: { asset: 'asset' }, outputs: { asset: 'asset' }, parameters: [] },
})

function clone(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value))
}

function nextId(graph, kind) {
  const value = graph.nextIds[kind]
  if (!Number.isInteger(value) || value < 0) throw new Error(`Invalid nextIds.${kind}`)
  graph.nextIds[kind] += 1
  return `${kind === 'node' ? 'n' : 'l'}${String(value).padStart(6, '0')}`
}

export function checksumGeometryGraph(graph) {
  const { checksum, ...content } = graph
  const text = stableStringify(content)
  let hash = 0x811c9dc5
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193)
  }
  return `fnv1a32:${(hash >>> 0).toString(16).padStart(8, '0')}`
}

function validateEndpoint(endpoint, label) {
  if (!endpoint || typeof endpoint !== 'object' || Array.isArray(endpoint)) throw new Error(`${label} must be a node/socket endpoint`)
  if (Object.keys(endpoint).sort().join(',') !== 'node,socket' || typeof endpoint.node !== 'string' || typeof endpoint.socket !== 'string') {
    throw new Error(`${label} must contain only node and socket`)
  }
}

function validateParameters(node) {
  const definition = GEOMETRY_NODE_TYPES[node.type]
  const parameters = node.parameters
  if (!parameters || typeof parameters !== 'object' || Array.isArray(parameters)) throw new Error(`${node.id} parameters must be an object`)
  for (const key of Object.keys(parameters)) {
    if (!definition.parameters.includes(key)) throw new Error(`${node.id} does not accept parameter ${key}`)
  }
  if (node.type === 'source.generate') {
    if (!GRAPH_ID.test(parameters.id || '')) throw new Error(`${node.id} needs a dotted output asset id`)
    if (!parameters.settings || typeof parameters.settings !== 'object' || Array.isArray(parameters.settings)) throw new Error(`${node.id} needs generation settings`)
  } else if (node.type === 'source.asset' && parameters.document !== undefined) {
    validateAssetDocument(parameters.document)
  } else if (node.type === 'edit.move') {
    if (!Array.isArray(parameters.vertexIds) || !parameters.vertexIds.length) throw new Error(`${node.id} needs vertexIds`)
    if (!Array.isArray(parameters.delta) || parameters.delta.length !== 3) throw new Error(`${node.id} needs a three-axis delta`)
  } else if (node.type === 'edit.split') {
    if (typeof parameters.edgeId !== 'string') throw new Error(`${node.id} needs an edgeId`)
  } else if (node.type === 'edit.extrudeFace' || node.type === 'edit.deleteFace') {
    if (typeof parameters.faceId !== 'string') throw new Error(`${node.id} needs a faceId`)
  } else if (node.type === 'configure.budgets') {
    if (!Array.isArray(parameters.levels) || !parameters.levels.length) throw new Error(`${node.id} needs budget levels`)
  }
  if (parameters.includeSockets !== undefined && typeof parameters.includeSockets !== 'boolean') throw new Error(`${node.id} includeSockets must be boolean`)
}

function graphOrder(graph) {
  const nodes = new Map(graph.nodes.map((node) => [node.id, node]))
  const indegree = new Map(graph.nodes.map((node) => [node.id, 0]))
  const outgoing = new Map(graph.nodes.map((node) => [node.id, []]))
  for (const link of graph.links) {
    indegree.set(link.to.node, indegree.get(link.to.node) + 1)
    outgoing.get(link.from.node).push(link.to.node)
  }
  const ready = [...nodes.keys()].filter((id) => indegree.get(id) === 0).sort()
  const order = []
  while (ready.length) {
    const id = ready.shift()
    order.push(id)
    for (const target of [...new Set(outgoing.get(id))].sort()) {
      indegree.set(target, indegree.get(target) - 1)
      if (indegree.get(target) === 0) {
        ready.push(target)
        ready.sort()
      }
    }
  }
  if (order.length !== graph.nodes.length) throw new Error('Geometry graph contains a cycle')
  return order
}

export function validateGeometryGraph(graph, { verifyChecksum = true } = {}) {
  if (!graph || typeof graph !== 'object' || Array.isArray(graph)) throw new Error('Geometry graph must be an object')
  for (const key of Object.keys(graph)) if (!ROOT_KEYS.has(key)) throw new Error(`Unknown graph key: ${key}`)
  if (graph.format !== GEOMETRY_GRAPH_FORMAT || graph.version !== GEOMETRY_GRAPH_VERSION) throw new Error('Unsupported geometry graph format/version')
  if (!GRAPH_ID.test(graph.id || '')) throw new Error('Geometry graph needs a dotted lowercase id')
  if (typeof graph.name !== 'string' || !graph.name) throw new Error('Geometry graph needs a name')
  if (!Array.isArray(graph.nodes) || !graph.nodes.length) throw new Error('Geometry graph needs nodes')
  if (!Array.isArray(graph.links)) throw new Error('Geometry graph links must be an array')
  if (!graph.nextIds || !Number.isInteger(graph.nextIds.node) || !Number.isInteger(graph.nextIds.link) || graph.nextIds.node < 0 || graph.nextIds.link < 0) {
    throw new Error('Geometry graph needs non-negative nextIds counters')
  }
  if (verifyChecksum && graph.checksum !== checksumGeometryGraph(graph)) throw new Error('Geometry graph checksum does not match its contents')

  const nodes = new Map()
  for (const node of graph.nodes) {
    if (!node || typeof node !== 'object' || !NODE_ID.test(node.id || '') || nodes.has(node.id)) throw new Error('Geometry graph contains a missing, malformed, or duplicate node id')
    if (Object.keys(node).some((key) => !['id', 'type', 'parameters', 'position'].includes(key))) throw new Error(`${node.id} contains unknown fields`)
    if (!GEOMETRY_NODE_TYPES[node.type]) throw new Error(`${node.id} uses unknown node type ${node.type}`)
    validateParameters(node)
    if (node.position !== undefined && (!node.position || !Number.isFinite(node.position.x) || !Number.isFinite(node.position.y))) throw new Error(`${node.id} has an invalid editor position`)
    nodes.set(node.id, node)
  }
  const links = new Set()
  const occupiedInputs = new Set()
  for (const link of graph.links) {
    if (!link || !LINK_ID.test(link.id || '') || links.has(link.id)) throw new Error('Geometry graph contains a missing, malformed, or duplicate link id')
    if (Object.keys(link).some((key) => !['id', 'from', 'to'].includes(key))) throw new Error(`${link.id} contains unknown fields`)
    links.add(link.id)
    validateEndpoint(link.from, `${link.id} from`)
    validateEndpoint(link.to, `${link.id} to`)
    const source = nodes.get(link.from.node)
    const target = nodes.get(link.to.node)
    if (!source || !target) throw new Error(`${link.id} references an unknown node`)
    const outputType = GEOMETRY_NODE_TYPES[source.type].outputs[link.from.socket]
    const inputType = GEOMETRY_NODE_TYPES[target.type].inputs[link.to.socket]
    if (!outputType || !inputType) throw new Error(`${link.id} references an unknown socket`)
    if (outputType !== inputType) throw new Error(`${link.id} connects ${outputType} to ${inputType}`)
    const inputKey = `${link.to.node}:${link.to.socket}`
    if (occupiedInputs.has(inputKey)) throw new Error(`${link.to.node}.${link.to.socket} has multiple inbound links`)
    occupiedInputs.add(inputKey)
  }
  if (!graph.outputs || typeof graph.outputs !== 'object' || Array.isArray(graph.outputs) || !graph.outputs.asset) throw new Error('Geometry graph needs an asset output')
  for (const [name, endpoint] of Object.entries(graph.outputs)) {
    if (!OUTPUT_NAME.test(name)) throw new Error(`Unknown graph output: ${name}`)
    validateEndpoint(endpoint, `Output ${name}`)
    const node = nodes.get(endpoint.node)
    if (!node || GEOMETRY_NODE_TYPES[node.type].outputs[endpoint.socket] !== name) throw new Error(`Output ${name} references an incompatible socket`)
  }
  return { nodes: graph.nodes.length, links: graph.links.length, order: graphOrder(graph) }
}

function finalizeGraph(graph) {
  graph.checksum = checksumGeometryGraph(graph)
  validateGeometryGraph(graph)
  return graph
}

export function createGeometryGraph({ id, name, nodes, links = [], outputs }) {
  const graph = {
    format: GEOMETRY_GRAPH_FORMAT,
    version: GEOMETRY_GRAPH_VERSION,
    id,
    name,
    nodes: clone(nodes || []).map((node, index) => ({
      id: node.id || `n${String(index).padStart(6, '0')}`,
      type: node.type,
      parameters: clone(node.parameters || {}),
      ...(node.position ? { position: clone(node.position) } : {}),
    })),
    links: clone(links).map((link, index) => ({ id: link.id || `l${String(index).padStart(6, '0')}`, from: clone(link.from), to: clone(link.to) })),
    outputs: clone(outputs),
    nextIds: { node: nodes?.length || 0, link: links.length },
    checksum: '',
  }
  return finalizeGraph(graph)
}

export function serializeGeometryGraph(graph) {
  validateGeometryGraph(graph)
  return `${stableStringify(graph, 2)}\n`
}

export function parseGeometryGraph(text) {
  const graph = JSON.parse(text)
  validateGeometryGraph(graph)
  return graph
}

/** Non-mutating editor commands. Node and link IDs never depend on later array positions. */
export function applyGeometryGraphOperations(source, operations) {
  validateGeometryGraph(source)
  if (!Array.isArray(operations)) throw new Error('Graph operations must be an array')
  let graph = clone(source)
  for (const operation of operations) {
    if (operation.type === 'addNode') {
      graph.nodes.push({ id: nextId(graph, 'node'), type: operation.nodeType, parameters: clone(operation.parameters || {}), ...(operation.position ? { position: clone(operation.position) } : {}) })
    } else if (operation.type === 'removeNode') {
      if (!graph.nodes.some((node) => node.id === operation.nodeId)) throw new Error(`Unknown graph node: ${operation.nodeId}`)
      if (Object.values(graph.outputs).some((endpoint) => endpoint.node === operation.nodeId)) throw new Error('Cannot remove a node referenced by a graph output')
      graph.nodes = graph.nodes.filter((node) => node.id !== operation.nodeId)
      graph.links = graph.links.filter((link) => link.from.node !== operation.nodeId && link.to.node !== operation.nodeId)
    } else if (operation.type === 'addLink') {
      validateEndpoint(operation.from, 'New link from')
      validateEndpoint(operation.to, 'New link to')
      graph.links.push({ id: nextId(graph, 'link'), from: clone(operation.from), to: clone(operation.to) })
    } else if (operation.type === 'removeLink') {
      const before = graph.links.length
      graph.links = graph.links.filter((link) => link.id !== operation.linkId)
      if (graph.links.length === before) throw new Error(`Unknown graph link: ${operation.linkId}`)
    } else if (operation.type === 'setParameters') {
      const node = graph.nodes.find((candidate) => candidate.id === operation.nodeId)
      if (!node) throw new Error(`Unknown graph node: ${operation.nodeId}`)
      node.parameters = clone(operation.parameters || {})
    } else if (operation.type === 'setOutput') {
      validateEndpoint(operation.endpoint, `Output ${operation.name}`)
      graph.outputs[operation.name] = clone(operation.endpoint)
    } else {
      throw new Error(`Unknown graph operation: ${operation.type}`)
    }
    finalizeGraph(graph)
  }
  return graph
}

function evaluateNode(node, inputs, context) {
  const parameters = node.parameters
  if (node.type === 'source.generate') {
    const generated = generate(clone(parameters.settings))
    try {
      return { asset: createAssetDocument({
        id: parameters.id,
        name: parameters.name,
        result: generated,
        budgets: clone(parameters.budgets),
        sockets: clone(parameters.sockets || []),
        materials: clone(parameters.materials),
      }) }
    } finally {
      generated.geometry.dispose()
    }
  }
  if (node.type === 'source.asset') {
    const document = parameters.document || context.sourceDocument
    if (!document) throw new Error(`${node.id} needs an embedded document or sourceDocument evaluation input`)
    validateAssetDocument(document)
    return { asset: clone(document) }
  }
  const asset = inputs.asset
  if (node.type === 'output.asset') return { asset }
  if (node.type === 'measure.asset') return { asset, stats: assetDocumentStats(asset) }
  if (node.type === 'configure.budgets') {
    const document = clone(asset)
    document.budgets = { levels: clone(parameters.levels) }
    document.checksum = checksumAssetDocument(document)
    validateAssetDocument(document)
    return { asset: document }
  }
  const operation = { type: {
    'edit.move': 'move',
    'edit.split': 'split',
    'edit.extrudeFace': 'extrudeFace',
    'edit.deleteFace': 'deleteFace',
    'modify.transform': 'transform',
  }[node.type], ...clone(parameters) }
  if (!operation.type) throw new Error(`No evaluator for ${node.type}`)
  return { asset: applyAssetOperations(asset, [operation]) }
}

function requiredNodes(graph) {
  const incoming = new Map()
  for (const link of graph.links) {
    if (!incoming.has(link.to.node)) incoming.set(link.to.node, [])
    incoming.get(link.to.node).push(link.from.node)
  }
  const required = new Set()
  const visit = (id) => {
    if (required.has(id)) return
    required.add(id)
    for (const source of incoming.get(id) || []) visit(source)
  }
  Object.values(graph.outputs).forEach((endpoint) => visit(endpoint.node))
  return required
}

function cloneEvaluation(result) {
  return clone(result)
}

export class GeometryGraphEvaluator {
  constructor({ cache = true } = {}) {
    this.cache = cache ? new Map() : null
    this.stats = { hits: 0, misses: 0, evaluations: 0 }
  }

  clear() {
    this.cache?.clear()
  }

  evaluate(source, { sourceDocument, useCache = true } = {}) {
    const validation = validateGeometryGraph(source)
    const key = `${source.checksum}:${sourceDocument?.checksum || 'embedded'}`
    if (this.cache && useCache && this.cache.has(key)) {
      this.stats.hits += 1
      return cloneEvaluation(this.cache.get(key))
    }
    this.stats.misses += 1
    const nodes = new Map(source.nodes.map((node) => [node.id, node]))
    const incoming = new Map(source.links.map((link) => [`${link.to.node}:${link.to.socket}`, link]))
    const required = requiredNodes(source)
    const values = new Map()
    const trace = []
    for (const id of validation.order) {
      if (!required.has(id)) continue
      const node = nodes.get(id)
      const inputs = {}
      for (const socket of Object.keys(GEOMETRY_NODE_TYPES[node.type].inputs).sort()) {
        const link = incoming.get(`${id}:${socket}`)
        if (!link) throw new Error(`${id}.${socket} is not connected`)
        inputs[socket] = values.get(link.from.node)?.[link.from.socket]
      }
      const outputs = evaluateNode(node, inputs, { sourceDocument })
      values.set(id, outputs)
      trace.push({
        nodeId: id,
        type: node.type,
        outputs: Object.fromEntries(Object.entries(outputs).map(([socket, value]) => [socket, socket === 'asset' ? value.checksum : clone(value)])),
      })
      this.stats.evaluations += 1
    }
    const outputs = Object.fromEntries(Object.entries(source.outputs).map(([name, endpoint]) => [name, values.get(endpoint.node)?.[endpoint.socket]]))
    const result = {
      graphId: source.id,
      graphChecksum: source.checksum,
      document: outputs.asset,
      outputs,
      stats: assetDocumentStats(outputs.asset),
      trace,
      skippedNodes: source.nodes.length - trace.length,
    }
    if (this.cache && useCache) this.cache.set(key, cloneEvaluation(result))
    return cloneEvaluation(result)
  }
}

export function evaluateGeometryGraph(graph, options = {}) {
  return new GeometryGraphEvaluator({ cache: false }).evaluate(graph, options)
}

export function bakeGeometryGraph(graph, { strict = true, sourceDocument, evaluator } = {}) {
  const evaluation = (evaluator || new GeometryGraphEvaluator({ cache: false })).evaluate(graph, { sourceDocument })
  return { ...bakeAsset(evaluation.document, { strict }), evaluation }
}
