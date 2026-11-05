import * as THREE from 'three'

export function cloneMeshData(mesh) {
  return {
    positions: [...mesh.positions],
    indices: [...mesh.indices],
    colors: mesh.colors ? [...mesh.colors] : null,
  }
}

export function geometryToMeshData(geometry) {
  const position = geometry.getAttribute('position')
  const color = geometry.getAttribute('color')
  if (!position) throw new Error('A position attribute is required')
  return {
    positions: Array.from(position.array),
    indices: geometry.index
      ? Array.from(geometry.index.array)
      : Array.from({ length: position.count }, (_, index) => index),
    colors: color ? Array.from(color.array) : null,
  }
}

export function meshDataToGeometry(mesh) {
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(mesh.positions, 3))
  if (mesh.colors) geometry.setAttribute('color', new THREE.Float32BufferAttribute(mesh.colors, 3))
  geometry.setIndex(mesh.indices)
  geometry.computeVertexNormals()
  geometry.computeBoundingBox()
  geometry.computeBoundingSphere()
  return geometry
}

function normal(a, b, c, positions) {
  const ai = a * 3
  const bi = b * 3
  const ci = c * 3
  const abx = positions[bi] - positions[ai]
  const aby = positions[bi + 1] - positions[ai + 1]
  const abz = positions[bi + 2] - positions[ai + 2]
  const acx = positions[ci] - positions[ai]
  const acy = positions[ci + 1] - positions[ai + 1]
  const acz = positions[ci + 2] - positions[ai + 2]
  const x = aby * acz - abz * acy
  const y = abz * acx - abx * acz
  const z = abx * acy - aby * acx
  const length = Math.hypot(x, y, z)
  return length > 1e-12 ? [x / length, y / length, z / length] : null
}

function compactMesh(positions, colors, triangles) {
  const used = [...new Set(triangles.flat())].sort((a, b) => a - b)
  const remap = new Map(used.map((oldIndex, newIndex) => [oldIndex, newIndex]))
  const nextPositions = []
  const nextColors = colors ? [] : null
  for (const oldIndex of used) {
    nextPositions.push(...positions.slice(oldIndex * 3, oldIndex * 3 + 3))
    if (colors) nextColors.push(...colors.slice(oldIndex * 3, oldIndex * 3 + 3))
  }
  return {
    positions: nextPositions,
    colors: nextColors,
    indices: triangles.flat().map((index) => remap.get(index)),
  }
}

/**
 * Deterministic, topology-guarded edge-collapse reduction.
 *
 * The link condition rejects non-manifold collapses, and the normal test rejects
 * folded or degenerate triangles. If a budget is geometrically unreachable the
 * function reports withinBudget=false; callers decide whether that is an error.
 */
export function decimateMeshData(mesh, maximumTriangles) {
  if (!Number.isInteger(maximumTriangles) || maximumTriangles < 1) {
    throw new Error('Triangle budget must be a positive integer')
  }
  const source = cloneMeshData(mesh)
  if (source.indices.length % 3 !== 0) throw new Error('Mesh indices must contain triangles')
  const positions = [...source.positions]
  const colors = source.colors ? [...source.colors] : null
  let triangles = []
  for (let index = 0; index < source.indices.length; index += 3) {
    triangles.push(source.indices.slice(index, index + 3))
  }
  const originalTriangles = triangles.length
  const edgeUse = new Map()
  for (const triangle of triangles) {
    for (let corner = 0; corner < 3; corner += 1) {
      const key = [triangle[corner], triangle[(corner + 1) % 3]].sort((a, b) => a - b).join(':')
      edgeUse.set(key, (edgeUse.get(key) || 0) + 1)
    }
  }
  const closed = [...edgeUse.values()].every((count) => count === 2)
  let collapses = 0

  while (triangles.length > maximumTriangles) {
    // A closed triangle mesh cannot drop below a tetrahedron. In particular,
    // never report two coincident faces or an empty mesh as a successful LOD.
    if (closed && triangles.length <= 4) break
    const neighbors = Array.from({ length: positions.length / 3 }, () => new Set())
    const edges = new Map()
    for (const triangle of triangles) {
      for (let corner = 0; corner < 3; corner += 1) {
        const a = triangle[corner]
        const b = triangle[(corner + 1) % 3]
        const c = triangle[(corner + 2) % 3]
        neighbors[a].add(b)
        neighbors[a].add(c)
        neighbors[b].add(a)
        neighbors[b].add(c)
        const low = Math.min(a, b)
        const high = Math.max(a, b)
        const key = `${low}:${high}`
        if (!edges.has(key)) edges.set(key, { a: low, b: high, opposite: new Set() })
        edges.get(key).opposite.add(c)
      }
    }

    const candidates = [...edges.values()].map((edge) => {
      const ai = edge.a * 3
      const bi = edge.b * 3
      const dx = positions[ai] - positions[bi]
      const dy = positions[ai + 1] - positions[bi + 1]
      const dz = positions[ai + 2] - positions[bi + 2]
      return { ...edge, cost: dx * dx + dy * dy + dz * dz }
    }).sort((left, right) => left.cost - right.cost || left.a - right.a || left.b - right.b)

    let selected = null
    for (const edge of candidates) {
      const shared = [...neighbors[edge.a]].filter((vertex) => neighbors[edge.b].has(vertex))
      if (shared.length !== edge.opposite.size) continue

      const midpoint = [0, 1, 2].map((axis) => (positions[edge.a * 3 + axis] + positions[edge.b * 3 + axis]) / 2)
      let valid = true
      for (const triangle of triangles) {
        if (!triangle.includes(edge.a) && !triangle.includes(edge.b)) continue
        if (triangle.includes(edge.a) && triangle.includes(edge.b)) continue
        const replaced = triangle.map((vertex) => vertex === edge.b ? edge.a : vertex)
        if (new Set(replaced).size !== 3) { valid = false; break }
        const before = normal(...triangle, positions)
        const saved = positions.slice(edge.a * 3, edge.a * 3 + 3)
        positions.splice(edge.a * 3, 3, ...midpoint)
        const after = normal(...replaced, positions)
        positions.splice(edge.a * 3, 3, ...saved)
        if (!before || !after || before[0] * after[0] + before[1] * after[1] + before[2] * after[2] <= 1e-8) {
          valid = false
          break
        }
      }
      if (valid) {
        const signatures = new Set()
        for (const triangle of triangles) {
          if (triangle.includes(edge.a) && triangle.includes(edge.b)) continue
          const replaced = triangle.map((vertex) => vertex === edge.b ? edge.a : vertex)
          const signature = [...replaced].sort((a, b) => a - b).join(':')
          if (signatures.has(signature)) { valid = false; break }
          signatures.add(signature)
        }
      }
      if (valid) { selected = { ...edge, midpoint }; break }
    }

    if (!selected) break
    positions.splice(selected.a * 3, 3, ...selected.midpoint)
    if (colors) {
      const mixed = [0, 1, 2].map((axis) => (colors[selected.a * 3 + axis] + colors[selected.b * 3 + axis]) / 2)
      colors.splice(selected.a * 3, 3, ...mixed)
    }
    triangles = triangles.flatMap((triangle) => {
      if (triangle.includes(selected.a) && triangle.includes(selected.b)) return []
      return [triangle.map((vertex) => vertex === selected.b ? selected.a : vertex)]
    })
    collapses += 1
  }

  const reduced = compactMesh(positions, colors, triangles)
  return {
    ...reduced,
    stats: {
      originalTriangles,
      triangles: triangles.length,
      targetTriangles: maximumTriangles,
      collapses,
      withinBudget: triangles.length <= maximumTriangles,
    },
  }
}
