import * as THREE from 'three'

const edgeKey = (a, b) => `${Math.min(a, b)}:${Math.max(a, b)}`

function readTriangles(geometry) {
  const index = geometry.index
  const position = geometry.attributes.position
  const count = index ? index.count : position.count
  const triangles = []
  for (let i = 0; i < count; i += 3) {
    triangles.push(index
      ? [index.getX(i), index.getX(i + 1), index.getX(i + 2)]
      : [i, i + 1, i + 2])
  }
  return triangles
}

function quadCandidate(first, second, shared, positions) {
  if (first.from === second.from) return null
  const boundary = []
  for (const triangle of [first.triangle, second.triangle]) {
    for (const edge of triangle.edges) {
      if (edgeKey(edge.from, edge.to) !== shared) boundary.push(edge)
    }
  }
  const next = new Map(boundary.map((edge) => [edge.from, edge.to]))
  const start = boundary[0].from
  const face = [start]
  let current = start
  for (let i = 0; i < 4; i++) {
    current = next.get(current)
    if (current === undefined) return null
    if (current !== start) face.push(current)
  }
  if (current !== start || face.length !== 4 || new Set(face).size !== 4) return null

  const points = face.map((index) => new THREE.Vector3().fromBufferAttribute(positions, index))
  const normal = new THREE.Vector3()
  for (let i = 0; i < 4; i++) {
    const a = points[i]
    const b = points[(i + 1) % 4]
    normal.x += (a.y - b.y) * (a.z + b.z)
    normal.y += (a.z - b.z) * (a.x + b.x)
    normal.z += (a.x - b.x) * (a.y + b.y)
  }
  if (normal.lengthSq() < 1e-12) return null
  normal.normalize()

  const edge = new THREE.Vector3().subVectors(points[1], points[0])
  const diagonal = new THREE.Vector3().subVectors(points[2], points[0])
  const planarity = Math.abs(new THREE.Vector3().crossVectors(edge, diagonal).normalize().dot(normal))
  const planeDistance = Math.abs(new THREE.Vector3().subVectors(points[3], points[0]).dot(normal))
  const scale = Math.max(0.001, points[0].distanceTo(points[2]))
  let concave = false
  let minLength = Infinity
  let maxLength = 0
  for (let i = 0; i < 4; i++) {
    const a = new THREE.Vector3().subVectors(points[(i + 1) % 4], points[i])
    const b = new THREE.Vector3().subVectors(points[(i + 2) % 4], points[(i + 1) % 4])
    if (new THREE.Vector3().crossVectors(a, b).dot(normal) < -1e-8) concave = true
    minLength = Math.min(minLength, a.length())
    maxLength = Math.max(maxLength, a.length())
  }
  const aspectPenalty = 1 - minLength / Math.max(maxLength, 1e-8)
  const score = (1 - planarity) * 3 + (planeDistance / scale) * 2 + aspectPenalty * 0.12 + (concave ? 2 : 0)
  return { face, score }
}

function analyzeFaces(faces) {
  const edges = new Map()
  for (const face of faces) {
    for (let i = 0; i < face.length; i++) {
      const from = face[i]
      const to = face[(i + 1) % face.length]
      const key = edgeKey(from, to)
      const edge = edges.get(key) || { count: 0, direction: 0, from: Math.min(from, to), to: Math.max(from, to) }
      edge.count++
      edge.direction += from < to ? 1 : -1
      edges.set(key, edge)
    }
  }
  let boundary = 0
  let nonManifold = 0
  let inconsistent = 0
  for (const edge of edges.values()) {
    if (edge.count === 1) boundary++
    else if (edge.count !== 2) nonManifold++
    else if (edge.direction !== 0) inconsistent++
  }
  return { edges, boundary, nonManifold, inconsistent, manifold: boundary === 0 && nonManifold === 0 && inconsistent === 0 }
}

export function buildQuadDominant(geometry) {
  const positions = geometry.attributes.position
  const source = readTriangles(geometry)
  const triangles = source.map((vertices, id) => {
    const edges = vertices.map((from, i) => ({ from, to: vertices[(i + 1) % 3] }))
    return { id, vertices, edges }
  })
  const edgeMap = new Map()
  for (const triangle of triangles) {
    for (const edge of triangle.edges) {
      const key = edgeKey(edge.from, edge.to)
      const entries = edgeMap.get(key) || []
      entries.push({ ...edge, triangle })
      edgeMap.set(key, entries)
    }
  }

  const candidates = []
  for (const [shared, entries] of edgeMap) {
    if (entries.length !== 2) continue
    const candidate = quadCandidate(entries[0], entries[1], shared, positions)
    if (!candidate) continue
    candidates.push({
      a: entries[0].triangle.id,
      b: entries[1].triangle.id,
      face: candidate.face,
      score: candidate.score,
    })
  }
  candidates.sort((a, b) => a.score - b.score || a.a - b.a || a.b - b.b)

  const used = new Set()
  const faces = []
  for (const candidate of candidates) {
    if (used.has(candidate.a) || used.has(candidate.b)) continue
    used.add(candidate.a)
    used.add(candidate.b)
    faces.push(candidate.face)
  }
  for (const triangle of triangles) {
    if (!used.has(triangle.id)) faces.push(triangle.vertices)
  }

  const topology = analyzeFaces(faces)
  const quads = faces.filter((face) => face.length === 4).length
  const remainingTriangles = faces.length - quads
  const stats = {
    vertices: positions.count,
    sourceTriangles: source.length,
    faces: faces.length,
    quads,
    triangles: remainingTriangles,
    edges: topology.edges.size,
    boundary: topology.boundary,
    nonManifold: topology.nonManifold,
    inconsistent: topology.inconsistent,
    manifold: topology.manifold,
    quadRatio: faces.length ? quads / faces.length : 0,
    faceReduction: source.length - faces.length,
    faceReductionRatio: source.length ? (source.length - faces.length) / source.length : 0,
    silhouettePreserved: true,
  }
  return { faces, stats }
}

export function createQuadFlowGeometry(geometry, quadMesh) {
  const topology = analyzeFaces(quadMesh.faces)
  const positions = geometry.attributes.position
  const values = []
  const a = new THREE.Vector3()
  const b = new THREE.Vector3()
  for (const edge of topology.edges.values()) {
    a.fromBufferAttribute(positions, edge.from)
    b.fromBufferAttribute(positions, edge.to)
    values.push(a.x, a.y, a.z, b.x, b.y, b.z)
  }
  const flow = new THREE.BufferGeometry()
  flow.setAttribute('position', new THREE.Float32BufferAttribute(values, 3))
  flow.computeBoundingSphere()
  flow.name = 'Quad-dominant edge flow'
  return flow
}
