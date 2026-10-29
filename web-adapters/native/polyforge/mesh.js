import * as THREE from 'three'
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js'
import { generatePromptGeometry, isPromptObject } from './prompt-mesh.js'

export const DEFAULTS = Object.freeze({
  primitive: 'monolith',
  detail: 2,
  radius: 1.15,
  height: 2.9,
  asymmetry: 0.18,
  distortion: 0.16,
  taper: 0.22,
  twist: 0.28,
  seed: 1847,
  color: '#C7F36B',
  viewMode: 'topology',
  prompt: '',
  meshEdits: '[]',
  componentMode: 'object',
})

export const PRESETS = [
  { id: 'monolith', name: 'Monolith', code: '01', description: 'Balanced ring topology' },
  { id: 'gem', name: 'Gem', code: '02', description: 'Crisp crowned facets' },
  { id: 'orb', name: 'Orb', code: '03', description: 'Icosahedral hull' },
  { id: 'vessel', name: 'Vessel', code: '04', description: 'Closed lathed volume' },
  { id: 'spire', name: 'Spire', code: '05', description: 'Tapered twisting rings' },
  { id: 'torus', name: 'Torus', code: '06', description: 'Continuous quad source' },
]

function hash(x, y, z, seed) {
  const value = Math.sin(x * 127.1 + y * 311.7 + z * 74.7 + seed * 0.013) * 43758.5453123
  return (value - Math.floor(value)) * 2 - 1
}

function ringGeometry(settings, profile) {
  const segments = 6 + settings.detail * 3
  const positions = []
  const indices = []
  const rings = profile.length

  for (let j = 0; j < rings; j++) {
    const [y, radius] = profile[j]
    for (let i = 0; i < segments; i++) {
      const angle = (i / segments) * Math.PI * 2
      positions.push(Math.cos(angle) * radius, y, Math.sin(angle) * radius)
    }
  }
  for (let j = 0; j < rings - 1; j++) {
    for (let i = 0; i < segments; i++) {
      const next = (i + 1) % segments
      const a = j * segments + i
      const b = j * segments + next
      const c = (j + 1) * segments + next
      const d = (j + 1) * segments + i
      indices.push(a, b, d, b, c, d)
    }
  }

  const bottom = positions.length / 3
  positions.push(0, profile[0][0], 0)
  const top = positions.length / 3
  positions.push(0, profile[rings - 1][0], 0)
  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments
    indices.push(bottom, next, i)
    const a = (rings - 1) * segments + i
    const b = (rings - 1) * segments + next
    indices.push(top, a, b)
  }

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setIndex(indices)
  return geometry
}

function createBaseGeometry(settings) {
  const r = settings.radius
  const h = settings.height
  const d = settings.detail

  switch (settings.primitive) {
    case 'gem':
      return ringGeometry(settings, [
        [-h * 0.5, r * 0.54],
        [-h * 0.12, r],
        [h * 0.18, r * 0.82],
        [h * 0.34, r * 0.46],
      ])
    case 'orb': {
      const geometry = new THREE.IcosahedronGeometry(r, d)
      geometry.deleteAttribute('normal')
      geometry.deleteAttribute('uv')
      return mergeVertices(geometry, 1e-5)
    }
    case 'vessel':
      return ringGeometry(settings, [
        [-h * 0.5, r * 0.52],
        [-h * 0.32, r * 0.82],
        [0, r],
        [h * 0.28, r * 0.83],
        [h * 0.5, r * 0.58],
      ])
    case 'spire':
      return ringGeometry(settings, [
        [-h * 0.5, r],
        [-h * 0.18, r * 0.84],
        [h * 0.14, r * 0.55],
        [h * 0.38, r * 0.28],
        [h * 0.5, r * 0.08],
      ])
    case 'torus': {
      let geometry = new THREE.TorusGeometry(r * 0.72, r * 0.3, 5 + d * 2, 10 + d * 5)
      geometry.deleteAttribute('normal')
      geometry.deleteAttribute('uv')
      geometry = mergeVertices(geometry, 1e-5)
      geometry.rotateX(Math.PI / 2)
      geometry.scale(1, Math.max(0.55, h / (r * 2.4)), 1)
      return geometry
    }
    case 'monolith':
    default:
      return ringGeometry(settings, [
        [-h * 0.5, r * 0.76],
        [-h * 0.27, r],
        [h * 0.08, r * 0.93],
        [h * 0.34, r * 0.72],
        [h * 0.5, r * 0.44],
      ])
  }
}

function deform(geometry, settings) {
  const position = geometry.attributes.position
  const h = settings.height
  const seedPhase = settings.seed * 0.017
  const point = new THREE.Vector3()

  for (let i = 0; i < position.count; i++) {
    point.fromBufferAttribute(position, i)
    const originalY = point.y
    const normalizedY = THREE.MathUtils.clamp(originalY / Math.max(h, 0.01) + 0.5, 0, 1)
    const radial = Math.hypot(point.x, point.z)
    const angle = Math.atan2(point.z, point.x)
    const coherent = Math.sin(angle * 3 + normalizedY * 2.4 + seedPhase) * 0.58
      + Math.cos(angle * 5 - normalizedY * 3.1 + seedPhase * 0.7) * 0.28
    const jitter = hash(point.x, point.y, point.z, settings.seed)
    const noise = coherent + jitter * 0.14
    const radialScale = Math.max(0.18, 1 + noise * settings.distortion)
    const taperScale = Math.max(0.2, 1 - settings.taper * normalizedY)

    point.x *= radialScale * taperScale
    point.z *= radialScale * taperScale
    point.x += settings.asymmetry * settings.radius * (normalizedY - 0.35) * 0.65
    point.z += settings.asymmetry * settings.radius * Math.sin(normalizedY * Math.PI) * 0.18

    const twist = settings.twist * (normalizedY - 0.5) * Math.PI
    const cos = Math.cos(twist)
    const sin = Math.sin(twist)
    const x = point.x * cos - point.z * sin
    const z = point.x * sin + point.z * cos
    point.x = x
    point.z = z
    point.y = originalY + radial * jitter * settings.distortion * 0.12
    position.setXYZ(i, point.x, point.y, point.z)
  }

  geometry.computeBoundingBox()
  const minY = geometry.boundingBox.min.y
  const centerX = (geometry.boundingBox.min.x + geometry.boundingBox.max.x) * 0.5
  const centerZ = (geometry.boundingBox.min.z + geometry.boundingBox.max.z) * 0.5
  geometry.translate(-centerX, -minY, -centerZ)
  position.needsUpdate = true
  geometry.computeVertexNormals()
  geometry.computeBoundingSphere()
  return geometry
}

export function analyzeTopology(geometry) {
  const positions = geometry.attributes.position
  const index = geometry.index
  const edges = new Map()
  let degenerate = 0
  const a = new THREE.Vector3()
  const b = new THREE.Vector3()
  const c = new THREE.Vector3()
  const ab = new THREE.Vector3()
  const ac = new THREE.Vector3()
  const triangles = index ? index.count / 3 : positions.count / 3

  for (let i = 0; i < triangles; i++) {
    const ia = index ? index.getX(i * 3) : i * 3
    const ib = index ? index.getX(i * 3 + 1) : i * 3 + 1
    const ic = index ? index.getX(i * 3 + 2) : i * 3 + 2
    a.fromBufferAttribute(positions, ia)
    b.fromBufferAttribute(positions, ib)
    c.fromBufferAttribute(positions, ic)
    ab.subVectors(b, a)
    ac.subVectors(c, a)
    if (ab.cross(ac).lengthSq() < 1e-12) degenerate++
    for (const [from, to] of [[ia, ib], [ib, ic], [ic, ia]]) {
      const low = Math.min(from, to)
      const high = Math.max(from, to)
      const key = `${low}:${high}`
      const edge = edges.get(key) || { count: 0, direction: 0 }
      edge.count++
      edge.direction += from === low ? 1 : -1
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

  return {
    vertices: positions.count,
    edges: edges.size,
    triangles,
    boundary,
    nonManifold,
    inconsistent,
    degenerate,
    manifold: boundary === 0 && nonManifold === 0 && inconsistent === 0 && degenerate === 0,
  }
}

export function generateGeometry(settings) {
  const geometry = isPromptObject(settings.primitive)
    ? generatePromptGeometry(settings)
    : deform(createBaseGeometry(settings), settings)
  geometry.name = `POLYFORGE_${settings.primitive}_${settings.seed}`
  geometry.userData.topology = analyzeTopology(geometry)
  geometry.userData.generator = { ...settings }
  return geometry
}
