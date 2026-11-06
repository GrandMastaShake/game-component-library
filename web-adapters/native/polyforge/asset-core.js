import { geometryToMeshData } from './mesh-data.js'

export const FORGE_FORMAT = 'polyforge.forge'
export const FORGE_VERSION = '1.0.0'
export const DISTANCE_BANDS = Object.freeze(['hero', 'gameplay', 'far', 'proxy'])

const ID_PATTERN = /^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$/
const PREFIX = { vertex: 'v', edge: 'e', face: 'f', corner: 'c', operation: 'op' }

function canonicalize(value) {
  if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('Non-finite numbers cannot be serialized')
  if (Array.isArray(value)) return value.map(canonicalize)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]))
  }
  return value
}

export function stableStringify(value, space = 0) {
  return JSON.stringify(canonicalize(value), null, space)
}

export function checksumAssetDocument(document) {
  const { checksum, ...content } = document
  const text = stableStringify(content)
  let hash = 0x811c9dc5
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193)
  }
  return `fnv1a32:${(hash >>> 0).toString(16).padStart(8, '0')}`
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function nextId(document, kind) {
  const value = document.nextIds[kind]
  if (!Number.isInteger(value) || value < 0) throw new Error(`Invalid nextIds.${kind}`)
  document.nextIds[kind] += 1
  return `${PREFIX[kind]}${String(value).padStart(6, '0')}`
}

function finiteVector(value, length, label) {
  if (!Array.isArray(value) || value.length !== length || value.some((entry) => typeof entry !== 'number' || !Number.isFinite(entry))) {
    throw new Error(`${label} must contain ${length} finite numbers`)
  }
}

export function defaultBudgets(sourceTriangles) {
  if (!Number.isInteger(sourceTriangles) || sourceTriangles < 1) throw new Error('A positive source triangle count is required')
  let previous = sourceTriangles
  const minimums = [1, 32, 32, 48]
  return [1, 0.7, 0.4, 0.2].map((ratio, index) => {
    const maximum = index === 0 ? sourceTriangles : Math.min(previous, Math.max(minimums[index], Math.floor(sourceTriangles * ratio)))
    previous = maximum
    return { level: `lod${index}`, distanceBand: DISTANCE_BANDS[index], maxTriangles: maximum }
  })
}

function normalizeBudgets(budgets, sourceTriangles) {
  const levels = budgets === undefined ? defaultBudgets(sourceTriangles) : clone(budgets)
  if (!Array.isArray(levels) || !levels.length) throw new Error('At least one LOD budget is required')
  let previous = Infinity
  levels.forEach((level, index) => {
    if (level.level !== `lod${index}`) throw new Error(`Budget ${index} must be named lod${index}`)
    if (!DISTANCE_BANDS.includes(level.distanceBand)) throw new Error(`Unknown distance band: ${level.distanceBand}`)
    if (!Number.isInteger(level.maxTriangles) || level.maxTriangles < 1) throw new Error(`${level.level} needs a positive integer maxTriangles`)
    if (level.maxTriangles > previous) throw new Error('LOD budgets must be non-increasing')
    previous = level.maxTriangles
  })
  return levels
}

function newCorner(document, vertexId) {
  return { id: nextId(document, 'corner'), vertexId }
}

function rebuildEdges(document) {
  const previous = new Map(document.edges.map((edge) => [[...edge.vertices].sort().join(':'), edge.id]))
  const found = new Map()
  for (const face of document.faces) {
    for (let index = 0; index < face.corners.length; index += 1) {
      const a = face.corners[index].vertexId
      const b = face.corners[(index + 1) % face.corners.length].vertexId
      const key = [a, b].sort().join(':')
      if (!found.has(key)) found.set(key, [a, b].sort())
    }
  }
  document.edges = [...found.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([key, vertices]) => ({
    id: previous.get(key) || nextId(document, 'edge'),
    vertices,
  }))
}

function finalize(document) {
  rebuildEdges(document)
  document.checksum = checksumAssetDocument(document)
  validateAssetDocument(document)
  return document
}

export function createAssetDocument({ id, name, result, budgets, sockets = [], materials }) {
  if (!ID_PATTERN.test(id || '')) throw new Error('Asset id must be a dotted lowercase id such as prop.wayfinder')
  if (!result?.geometry) throw new Error('A POLYFORGE generation result is required')
  const mesh = geometryToMeshData(result.geometry)
  if (mesh.indices.length % 3 || !mesh.indices.length) throw new Error('Generated geometry has no triangles')
  const document = {
    format: FORGE_FORMAT,
    version: FORGE_VERSION,
    id,
    name: name || id.split('.')[1],
    units: 'metres',
    forwardAxis: '+z',
    generator: {
      kind: 'polyforge',
      settings: clone(result.settings || {}),
      operations: clone(result.operations || []),
    },
    vertices: [],
    edges: [],
    faces: [],
    materials: materials ? clone(materials) : [{ id: 'mat_default', baseColor: [1, 1, 1, 1], metallic: 0, roughness: 0.85 }],
    uvSets: [],
    sockets: clone(sockets),
    budgets: { levels: [] },
    operations: [],
    nextIds: { vertex: 0, edge: 0, face: 0, corner: 0, operation: 0 },
    checksum: '',
  }

  const vertexIds = []
  for (let index = 0; index < mesh.positions.length / 3; index += 1) {
    const vertexId = nextId(document, 'vertex')
    vertexIds.push(vertexId)
    document.vertices.push({
      id: vertexId,
      position: mesh.positions.slice(index * 3, index * 3 + 3),
      color: mesh.colors ? mesh.colors.slice(index * 3, index * 3 + 3) : [1, 1, 1],
      skinWeights: [],
    })
  }
  for (let index = 0; index < mesh.indices.length; index += 3) {
    document.faces.push({
      id: nextId(document, 'face'),
      materialId: document.materials[0].id,
      corners: mesh.indices.slice(index, index + 3).map((vertexIndex) => newCorner(document, vertexIds[vertexIndex])),
    })
  }
  document.budgets.levels = normalizeBudgets(budgets, mesh.indices.length / 3)
  return finalize(document)
}

export function assetDocumentStats(document) {
  return {
    vertices: document.vertices.length,
    edges: document.edges.length,
    faces: document.faces.length,
    corners: document.faces.reduce((sum, face) => sum + face.corners.length, 0),
    triangles: document.faces.reduce((sum, face) => sum + Math.max(0, face.corners.length - 2), 0),
    operations: document.operations.length,
    lodLevels: document.budgets.levels.length,
  }
}

export function validateAssetDocument(document, { verifyChecksum = true } = {}) {
  if (!document || typeof document !== 'object') throw new Error('Asset document must be an object')
  if (document.format !== FORGE_FORMAT) throw new Error(`Expected format ${FORGE_FORMAT}`)
  if (document.version !== FORGE_VERSION) throw new Error(`Unsupported asset version: ${document.version}`)
  if (!ID_PATTERN.test(document.id || '')) throw new Error('Invalid asset id')
  if (document.units !== 'metres' || !['+x', '-x', '+z', '-z'].includes(document.forwardAxis)) throw new Error('Invalid asset space declaration')
  if (verifyChecksum && document.checksum !== checksumAssetDocument(document)) throw new Error('Asset checksum does not match its contents')

  const unique = (items, label) => {
    if (!Array.isArray(items)) throw new Error(`${label} must be an array`)
    const ids = items.map((item) => item?.id)
    if (ids.some((id) => typeof id !== 'string' || !id)) throw new Error(`${label} contains a missing id`)
    if (new Set(ids).size !== ids.length) throw new Error(`${label} contains duplicate ids`)
    return new Set(ids)
  }
  const vertexIds = unique(document.vertices, 'vertices')
  unique(document.edges, 'edges')
  const faceIds = unique(document.faces, 'faces')
  const materialIds = unique(document.materials, 'materials')
  const cornerIds = new Set()
  for (const vertex of document.vertices) {
    finiteVector(vertex.position, 3, `Vertex ${vertex.id} position`)
    finiteVector(vertex.color, 3, `Vertex ${vertex.id} color`)
    if (!Array.isArray(vertex.skinWeights)) throw new Error(`Vertex ${vertex.id} skinWeights must be an array`)
  }
  if (!document.faces.length) throw new Error('Asset must contain at least one face')
  for (const face of document.faces) {
    if (!materialIds.has(face.materialId)) throw new Error(`Face ${face.id} references an unknown material`)
    if (!Array.isArray(face.corners) || face.corners.length < 3) throw new Error(`Face ${face.id} needs at least three corners`)
    const polygon = new Set()
    for (const corner of face.corners) {
      if (!corner.id || cornerIds.has(corner.id)) throw new Error(`Duplicate or missing corner id on ${face.id}`)
      cornerIds.add(corner.id)
      if (!vertexIds.has(corner.vertexId)) throw new Error(`Corner ${corner.id} references an unknown vertex`)
      if (polygon.has(corner.vertexId)) throw new Error(`Face ${face.id} repeats vertex ${corner.vertexId}`)
      polygon.add(corner.vertexId)
      if (corner.normal !== undefined) finiteVector(corner.normal, 3, `Corner ${corner.id} normal`)
      if (corner.uv !== undefined) {
        for (const [set, uv] of Object.entries(corner.uv)) finiteVector(uv, 2, `Corner ${corner.id} UV ${set}`)
      }
    }
  }
  for (const edge of document.edges) {
    if (!Array.isArray(edge.vertices) || edge.vertices.length !== 2 || edge.vertices.some((id) => !vertexIds.has(id))) {
      throw new Error(`Edge ${edge.id} must reference two known vertices`)
    }
  }
  if (!Array.isArray(document.uvSets) || !Array.isArray(document.sockets) || !Array.isArray(document.operations)) {
    throw new Error('uvSets, sockets, and operations must be arrays')
  }
  const socketNames = new Set()
  for (const socket of document.sockets) {
    if (!/^[a-z][a-z0-9_]*$/.test(socket.name || '') || socketNames.has(socket.name)) throw new Error('Socket names must be unique lowercase identifiers')
    socketNames.add(socket.name)
    finiteVector(socket.position, 3, `Socket ${socket.name} position`)
  }
  normalizeBudgets(document.budgets?.levels, assetDocumentStats(document).triangles)
  if (!faceIds.size) throw new Error('Asset has no editable faces')
  return assetDocumentStats(document)
}

export function serializeAssetDocument(document) {
  validateAssetDocument(document)
  return `${stableStringify(document, 2)}\n`
}

export function parseAssetDocument(text) {
  const document = JSON.parse(text)
  validateAssetDocument(document)
  return document
}

function faceNormal(face, vertices) {
  const points = face.corners.map((corner) => vertices.get(corner.vertexId).position)
  const normal = [0, 0, 0]
  for (let index = 0; index < points.length; index += 1) {
    const current = points[index]
    const next = points[(index + 1) % points.length]
    normal[0] += (current[1] - next[1]) * (current[2] + next[2])
    normal[1] += (current[2] - next[2]) * (current[0] + next[0])
    normal[2] += (current[0] - next[0]) * (current[1] + next[1])
  }
  const length = Math.hypot(...normal)
  if (length <= 1e-12) throw new Error(`Face ${face.id} has no usable normal`)
  return normal.map((value) => value / length)
}

function transformPoint(point, operation) {
  const translation = operation.translation ?? [0, 0, 0]
  const scale = operation.scale ?? [1, 1, 1]
  const rotation = operation.rotation ?? [0, 0, 0]
  const pivot = operation.pivot ?? [0, 0, 0]
  finiteVector(translation, 3, 'Transform translation')
  finiteVector(scale, 3, 'Transform scale')
  finiteVector(rotation, 3, 'Transform rotation')
  finiteVector(pivot, 3, 'Transform pivot')
  if (scale.some((value) => value <= 0)) throw new Error('Transform scale components must be positive')
  const [rx, ry, rz] = rotation.map((value) => value * Math.PI / 180)
  let [x, y, z] = point.map((value, axis) => (value - pivot[axis]) * scale[axis])
  ;[y, z] = [y * Math.cos(rx) - z * Math.sin(rx), y * Math.sin(rx) + z * Math.cos(rx)]
  ;[x, z] = [x * Math.cos(ry) + z * Math.sin(ry), -x * Math.sin(ry) + z * Math.cos(ry)]
  ;[x, y] = [x * Math.cos(rz) - y * Math.sin(rz), x * Math.sin(rz) + y * Math.cos(rz)]
  return [x + pivot[0] + translation[0], y + pivot[1] + translation[1], z + pivot[2] + translation[2]]
}

/** Apply stable-ID edits without mutating the source document. */
export function applyAssetOperations(source, operations) {
  validateAssetDocument(source)
  if (!Array.isArray(operations)) throw new Error('Asset operations must be an array')
  const document = clone(source)
  for (const operation of operations) {
    const recorded = { ...clone(operation), id: nextId(document, 'operation') }
    const vertices = new Map(document.vertices.map((vertex) => [vertex.id, vertex]))
    if (operation.type === 'move') {
      finiteVector(operation.delta, 3, 'Move delta')
      if (!Array.isArray(operation.vertexIds) || !operation.vertexIds.length) throw new Error('Move needs vertexIds')
      for (const id of operation.vertexIds) {
        const vertex = vertices.get(id)
        if (!vertex) throw new Error(`Selected vertex no longer exists: ${id}`)
        vertex.position = vertex.position.map((value, axis) => value + operation.delta[axis])
      }
    } else if (operation.type === 'split') {
      const edge = document.edges.find((candidate) => candidate.id === operation.edgeId)
      if (!edge) throw new Error(`Selected edge no longer exists: ${operation.edgeId}`)
      const [a, b] = edge.vertices.map((id) => vertices.get(id))
      const midpoint = {
        id: nextId(document, 'vertex'),
        position: a.position.map((value, axis) => (value + b.position[axis]) / 2),
        color: a.color.map((value, axis) => (value + b.color[axis]) / 2),
        skinWeights: [],
      }
      document.vertices.push(midpoint)
      let adjacent = 0
      for (const face of document.faces) {
        const index = face.corners.findIndex((corner, cornerIndex) => {
          const next = face.corners[(cornerIndex + 1) % face.corners.length]
          return (corner.vertexId === a.id && next.vertexId === b.id) || (corner.vertexId === b.id && next.vertexId === a.id)
        })
        if (index < 0) continue
        face.corners.splice(index + 1, 0, newCorner(document, midpoint.id))
        adjacent += 1
      }
      if (!adjacent) throw new Error(`Edge ${edge.id} has no adjacent face`)
    } else if (operation.type === 'transform') {
      const vertexIds = operation.vertexIds ?? document.vertices.map((vertex) => vertex.id)
      if (!Array.isArray(vertexIds) || !vertexIds.length || new Set(vertexIds).size !== vertexIds.length) {
        throw new Error('Transform needs unique vertexIds, or omit them to transform the whole asset')
      }
      const selected = new Set(vertexIds)
      for (const id of selected) {
        if (!vertices.has(id)) throw new Error(`Selected vertex no longer exists: ${id}`)
      }
      for (const vertex of document.vertices) {
        if (selected.has(vertex.id)) vertex.position = transformPoint(vertex.position, operation)
      }
      if (operation.includeSockets) {
        if (selected.size !== document.vertices.length) throw new Error('Socket transforms require the whole asset')
        document.sockets.forEach((socket) => { socket.position = transformPoint(socket.position, operation) })
      }
    } else if (operation.type === 'deleteFace') {
      const before = document.faces.length
      document.faces = document.faces.filter((face) => face.id !== operation.faceId)
      if (document.faces.length === before) throw new Error(`Selected face no longer exists: ${operation.faceId}`)
      if (!document.faces.length) throw new Error('Deleting the final face would leave an empty asset')
    } else if (operation.type === 'extrudeFace') {
      const face = document.faces.find((candidate) => candidate.id === operation.faceId)
      if (!face) throw new Error(`Selected face no longer exists: ${operation.faceId}`)
      const distance = operation.distance ?? 0.25
      if (typeof distance !== 'number' || !Number.isFinite(distance) || distance === 0) throw new Error('Extrusion distance must be finite and non-zero')
      const normal = faceNormal(face, vertices)
      const top = new Map()
      for (const corner of face.corners) {
        const original = vertices.get(corner.vertexId)
        const vertex = {
          id: nextId(document, 'vertex'),
          position: original.position.map((value, axis) => value + normal[axis] * distance),
          color: [...original.color],
          skinWeights: clone(original.skinWeights),
        }
        document.vertices.push(vertex)
        top.set(corner.vertexId, vertex.id)
      }
      const originalIds = face.corners.map((corner) => corner.vertexId)
      face.corners.forEach((corner) => { corner.vertexId = top.get(corner.vertexId) })
      for (let index = 0; index < originalIds.length; index += 1) {
        const a = originalIds[index]
        const b = originalIds[(index + 1) % originalIds.length]
        const side = [a, b, top.get(b), top.get(a)]
        document.faces.push({
          id: nextId(document, 'face'),
          materialId: face.materialId,
          corners: side.map((vertexId) => newCorner(document, vertexId)),
        })
      }
    } else {
      throw new Error(`Unknown asset operation: ${operation.type}`)
    }
    document.operations.push(recorded)
    finalize(document)
  }
  return document
}

export function assetDocumentToMeshData(document) {
  validateAssetDocument(document)
  const vertexIndices = new Map(document.vertices.map((vertex, index) => [vertex.id, index]))
  const indices = []
  const positions = document.vertices.flatMap((vertex) => vertex.position)
  const doubledArea = (a, b, c) => {
    const ab = [0, 1, 2].map((axis) => positions[b * 3 + axis] - positions[a * 3 + axis])
    const ac = [0, 1, 2].map((axis) => positions[c * 3 + axis] - positions[a * 3 + axis])
    return Math.hypot(ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0])
  }
  for (const face of document.faces) {
    const polygon = face.corners.map((corner) => vertexIndices.get(corner.vertexId))
    // A midpoint inserted into a triangle makes a quad with three collinear
    // corners. Pick the fan anchor that avoids a zero-area triangle instead of
    // blindly anchoring on the old corner and destroying the new edge.
    let best = null
    for (let anchor = 0; anchor < polygon.length; anchor += 1) {
      const corners = [...polygon.slice(anchor), ...polygon.slice(0, anchor)]
      const triangles = []
      let minimumArea = Infinity
      for (let index = 1; index < corners.length - 1; index += 1) {
        const triangle = [corners[0], corners[index], corners[index + 1]]
        triangles.push(triangle)
        minimumArea = Math.min(minimumArea, doubledArea(...triangle))
      }
      if (!best || minimumArea > best.minimumArea) best = { triangles, minimumArea }
    }
    best.triangles.forEach((triangle) => indices.push(...triangle))
  }
  return {
    positions,
    colors: document.vertices.flatMap((vertex) => vertex.color),
    indices,
  }
}
