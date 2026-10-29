import * as THREE from 'three'

export function readMeshEdits(value) {
  try {
    const operations = JSON.parse(value || '[]')
    return Array.isArray(operations) ? operations : []
  } catch {
    return []
  }
}

function triangleIndices(geometry) {
  const index = geometry.index
  const count = index ? index.count : geometry.attributes.position.count
  const triangles = []
  for (let i = 0; i < count; i += 3) {
    triangles.push(index ? [index.getX(i), index.getX(i + 1), index.getX(i + 2)] : [i, i + 1, i + 2])
  }
  return triangles
}

export function applyMeshEdits(baseGeometry, operations) {
  const geometry = baseGeometry.clone()
  const positions = Array.from(geometry.attributes.position.array)
  const colors = geometry.attributes.color ? Array.from(geometry.attributes.color.array) : null
  let triangles = triangleIndices(geometry)

  const addVertex = (point, color) => {
    const index = positions.length / 3
    positions.push(point.x, point.y, point.z)
    if (colors) colors.push(color.r, color.g, color.b)
    return index
  }
  const pointAt = (index) => new THREE.Vector3().fromArray(positions, index * 3)
  const colorAt = (index) => colors
    ? new THREE.Color().fromArray(colors, index * 3)
    : new THREE.Color(1, 1, 1)
  const moveVertex = (index, delta) => {
    if (index < 0 || index >= positions.length / 3) throw new Error('Selected vertex no longer exists')
    positions[index * 3] += delta[0]
    positions[index * 3 + 1] += delta[1]
    positions[index * 3 + 2] += delta[2]
  }

  for (const operation of operations) {
    if (operation.type === 'move') {
      for (const index of operation.indices) moveVertex(index, operation.delta)
    } else if (operation.type === 'split') {
      const [a, b] = operation.indices
      const adjacent = triangles.filter((triangle) => triangle.includes(a) && triangle.includes(b))
      if (!adjacent.length) throw new Error('Selected edge no longer exists')
      const middle = pointAt(a).add(pointAt(b)).multiplyScalar(0.5)
      const color = colorAt(a).add(colorAt(b)).multiplyScalar(0.5)
      const midpoint = addVertex(middle, color)
      const next = []
      for (const triangle of triangles) {
        const edgeIndex = triangle.findIndex((value, i) => value === a && triangle[(i + 1) % 3] === b)
        const reverseIndex = triangle.findIndex((value, i) => value === b && triangle[(i + 1) % 3] === a)
        if (edgeIndex >= 0) {
          const c = triangle[(edgeIndex + 2) % 3]
          next.push([a, midpoint, c], [midpoint, b, c])
        } else if (reverseIndex >= 0) {
          const c = triangle[(reverseIndex + 2) % 3]
          next.push([b, midpoint, c], [midpoint, a, c])
        } else next.push(triangle)
      }
      triangles = next
    } else if (operation.type === 'deleteFace') {
      if (operation.face < 0 || operation.face >= triangles.length) throw new Error('Selected face no longer exists')
      triangles.splice(operation.face, 1)
    } else if (operation.type === 'extrudeFace') {
      const triangle = triangles[operation.face]
      if (!triangle) throw new Error('Selected face no longer exists')
      const [a, b, c] = triangle
      const normal = new THREE.Vector3().subVectors(pointAt(b), pointAt(a))
        .cross(new THREE.Vector3().subVectors(pointAt(c), pointAt(a))).normalize()
      const distance = Number(operation.distance) || 0.25
      const top = triangle.map((index) => addVertex(pointAt(index).addScaledVector(normal, distance), colorAt(index)))
      triangles.splice(operation.face, 1)
      for (let i = 0; i < 3; i++) {
        const next = (i + 1) % 3
        triangles.push([triangle[i], triangle[next], top[next]], [triangle[i], top[next], top[i]])
      }
      triangles.push(top)
    }
  }

  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  if (colors) geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
  geometry.setIndex(triangles.flat())
  geometry.computeVertexNormals()
  geometry.computeBoundingBox()
  geometry.computeBoundingSphere()
  geometry.userData.meshEditCount = operations.length
  return geometry
}
