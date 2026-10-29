import * as THREE from 'three'
import { mergeGeometries, mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js'

export const PROMPT_OBJECTS = [
  { id: 'house', name: 'House', keywords: ['house', 'cottage', 'cabin', 'home'], color: '#D68462' },
  { id: 'rocket', name: 'Rocket', keywords: ['rocket', 'spaceship', 'spacecraft'], color: '#82B8C7' },
  { id: 'mushroom', name: 'Mushroom', keywords: ['mushroom', 'toadstool'], color: '#D68462' },
  { id: 'tree', name: 'Pine tree', keywords: ['tree', 'pine', 'fir'], color: '#C7F36B' },
  { id: 'cactus', name: 'Cactus', keywords: ['cactus', 'succulent'], color: '#C7F36B' },
  { id: 'crystal', name: 'Crystal cluster', keywords: ['crystal', 'crystals', 'mineral'], color: '#9B8AC4' },
  { id: 'rock', name: 'Rock', keywords: ['rock', 'stone', 'boulder'], color: '#DCD8CD' },
  { id: 'robot', name: 'Robot', keywords: ['robot', 'bot', 'android'], color: '#82B8C7' },
  { id: 'sword', name: 'Sword', keywords: ['sword', 'blade', 'dagger'], color: '#DCD8CD' },
]

function hashPrompt(text) {
  let hash = 2166136261
  for (let i = 0; i < text.length; i++) {
    hash ^= text.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return Math.abs(hash) || 1
}

export function interpretPrompt(prompt) {
  const text = prompt.trim().toLowerCase()
  if (!text) throw new Error('Describe an object first')
  const object = PROMPT_OBJECTS.find((item) => item.keywords.some((word) => text.includes(word)))
  if (!object) throw new Error('Try house, rocket, mushroom, tree, cactus, crystal, rock, robot, or sword')
  const detail = /ultra|dense|high detail/.test(text) ? 3 : /tiny|simple|low poly|low-poly|coarse/.test(text) ? 0 : 1
  const height = /tall|towering/.test(text) ? 3.8 : /small|tiny|short/.test(text) ? 2.0 : 2.8
  return {
    primitive: object.id,
    prompt: prompt.trim(),
    detail,
    height,
    radius: /wide|broad|chunky/.test(text) ? 1.45 : 1.05,
    asymmetry: 0.08,
    distortion: object.id === 'rock' ? 0.28 : 0.04,
    taper: 0,
    twist: 0,
    seed: (hashPrompt(text) % 98999) + 1000,
    color: object.color,
    viewMode: 'topology',
    meshEdits: '[]',
    componentMode: 'object',
  }
}

// Optional hosted-AI boundary: an adapter can return the same plain settings patch.
// The local interpreter remains the default, so generation never requires credentials.
export async function resolvePrompt(prompt, adapter) {
  if (!adapter) return interpretPrompt(prompt)
  const patch = await adapter(prompt)
  return { ...interpretPrompt(prompt), ...patch, meshEdits: '[]' }
}

function coloredPart(geometry, color, position, scale, rotation) {
  geometry.deleteAttribute('normal')
  geometry.deleteAttribute('uv')
  if (scale) geometry.scale(...scale)
  if (rotation) geometry.rotateX(rotation[0]), geometry.rotateY(rotation[1]), geometry.rotateZ(rotation[2])
  if (position) geometry.translate(...position)
  if (!geometry.index) geometry = mergeVertices(geometry, 1e-6)
  const rgb = new THREE.Color(color)
  const values = new Float32Array(geometry.attributes.position.count * 3)
  for (let i = 0; i < geometry.attributes.position.count; i++) rgb.toArray(values, i * 3)
  geometry.setAttribute('color', new THREE.BufferAttribute(values, 3))
  return geometry
}

function buildParts(id, seed) {
  const parts = []
  const add = (geometry, shade = 0, position, scale, rotation) => {
    const color = new THREE.Color('#FFFFFF').offsetHSL(0, 0, shade)
    parts.push(coloredPart(geometry, color, position, scale, rotation))
  }
  const box = (size, shade, position, rotation) => add(new THREE.BoxGeometry(...size), shade, position, null, rotation)
  const cylinder = (top, bottom, height, segments, shade, position, rotation) => add(new THREE.CylinderGeometry(top, bottom, height, segments), shade, position, null, rotation)
  const cone = (radius, height, segments, shade, position, rotation) => add(new THREE.ConeGeometry(radius, height, segments), shade, position, null, rotation)
  const ico = (radius, detail, shade, position, scale) => add(new THREE.IcosahedronGeometry(radius, detail), shade, position, scale)

  if (id === 'house') {
    box([1.8, 1.25, 1.5], 0, [0, 0.63, 0])
    cone(1.45, 1.0, 4, -0.25, [0, 1.72, 0], [0, Math.PI / 4, 0])
    box([0.4, 0.75, 0.08], -0.38, [0, 0.38, 0.79])
    for (const x of [-0.58, 0.58]) box([0.38, 0.38, 0.07], 0.25, [x, 0.77, 0.79])
    box([0.28, 0.7, 0.28], -0.3, [0.52, 1.85, -0.25])
  } else if (id === 'rocket') {
    cylinder(0.46, 0.58, 1.8, 10, 0.08, [0, 1.2, 0])
    cone(0.47, 0.9, 10, -0.18, [0, 2.55, 0])
    cylinder(0.36, 0.42, 0.4, 10, -0.4, [0, 0.12, 0])
    cylinder(0.19, 0.19, 0.08, 10, 0.3, [0, 1.55, 0.52], [Math.PI / 2, 0, 0])
    for (let i = 0; i < 3; i++) {
      const a = i * Math.PI * 2 / 3
      box([0.12, 0.75, 0.65], -0.22, [Math.sin(a) * 0.55, 0.55, Math.cos(a) * 0.55], [0, a, -0.12])
    }
  } else if (id === 'mushroom') {
    cylinder(0.28, 0.42, 1.25, 8, 0.16, [0, 0.63, 0])
    ico(1.12, 1, -0.18, [0, 1.45, 0], [1, 0.48, 1])
    for (let i = 0; i < 7; i++) {
      const a = i * 2.4 + seed * 0.001
      ico(0.11, 0, 0.3, [Math.cos(a) * 0.65, 1.85 - (i % 2) * 0.14, Math.sin(a) * 0.65], [1, 0.35, 1])
    }
  } else if (id === 'tree') {
    cylinder(0.18, 0.27, 1.1, 7, -0.35, [0, 0.55, 0])
    cone(1.0, 1.65, 7, -0.18, [0, 1.35, 0])
    cone(0.82, 1.5, 7, -0.05, [0, 2.0, 0])
    cone(0.58, 1.25, 7, 0.08, [0, 2.65, 0])
  } else if (id === 'cactus') {
    cylinder(0.34, 0.4, 2.25, 8, -0.08, [0, 1.13, 0])
    ico(0.34, 1, 0.04, [0, 2.23, 0], [1, 0.8, 1])
    for (const side of [-1, 1]) {
      cylinder(0.18, 0.2, 0.85, 7, -0.15, [side * 0.55, 1.0 + (side + 1) * 0.25, 0], [0, 0, Math.PI / 2])
      cylinder(0.17, 0.2, 0.9, 7, 0, [side * 0.92, 1.4 + (side + 1) * 0.25, 0])
      ico(0.18, 0, 0.05, [side * 0.92, 1.85 + (side + 1) * 0.25, 0])
    }
  } else if (id === 'crystal') {
    for (let i = 0; i < 6; i++) {
      const a = i * 2.4
      const radius = i === 0 ? 0 : 0.55
      const height = i === 0 ? 1.65 : 0.65 + (i % 3) * 0.25
      add(new THREE.OctahedronGeometry(0.5, 0), (i - 2) * 0.055, [Math.cos(a) * radius, height * 0.55, Math.sin(a) * radius], [0.55, height, 0.55], [0, a * 0.2, i ? 0.18 : 0])
    }
  } else if (id === 'robot') {
    box([1.05, 1.1, 0.7], -0.08, [0, 1.25, 0])
    box([0.8, 0.65, 0.68], 0.12, [0, 2.15, 0])
    box([0.5, 0.16, 0.05], -0.35, [0, 2.16, 0.36])
    for (const side of [-1, 1]) {
      cylinder(0.12, 0.14, 1.05, 6, -0.2, [side * 0.72, 1.25, 0], [0, 0, side * 0.12])
      cylinder(0.15, 0.18, 0.85, 6, -0.18, [side * 0.3, 0.35, 0])
      box([0.42, 0.18, 0.65], -0.32, [side * 0.3, 0.06, 0.12])
    }
    cylinder(0.04, 0.04, 0.35, 5, -0.25, [0, 2.65, 0])
    ico(0.12, 0, 0.25, [0, 2.86, 0])
  } else if (id === 'sword') {
    box([0.22, 1.9, 0.09], 0.2, [0, 1.65, 0])
    cone(0.16, 0.5, 4, 0.25, [0, 2.85, 0], [0, Math.PI / 4, 0])
    box([1.1, 0.16, 0.2], -0.28, [0, 0.68, 0])
    cylinder(0.11, 0.13, 0.62, 7, -0.38, [0, 0.3, 0])
    ico(0.18, 0, -0.15, [0, -0.03, 0])
  } else {
    ico(1.25, 1, -0.08, [0, 0.9, 0], [1.15, 0.82, 0.95])
    ico(0.65, 0, 0.08, [0.72, 0.45, 0.15], [1, 0.75, 1])
  }
  return parts
}

export function isPromptObject(id) {
  return PROMPT_OBJECTS.some((item) => item.id === id)
}

export function generatePromptGeometry(settings) {
  const parts = buildParts(settings.primitive, settings.seed)
  let geometry = mergeGeometries(parts, false)
  for (const part of parts) part.dispose()
  geometry = mergeVertices(geometry, 1e-5)
  const position = geometry.attributes.position
  const color = geometry.attributes.color
  const accent = new THREE.Color(settings.color)
  const tint = new THREE.Color()
  for (let i = 0; i < position.count; i++) {
    const shade = color.getX(i)
    tint.copy(accent).multiplyScalar(0.45 + shade * 0.75)
    color.setXYZ(i, tint.r, tint.g, tint.b)
  }
  if (settings.primitive === 'rock') {
    const point = new THREE.Vector3()
    for (let i = 0; i < position.count; i++) {
      point.fromBufferAttribute(position, i)
      const noise = 1 + Math.sin(point.x * 4.1 + point.y * 2.7 + settings.seed) * 0.09
      point.multiplyScalar(noise)
      position.setXYZ(i, point.x, point.y, point.z)
    }
  }
  const scale = settings.height / 3
  geometry.scale(scale * settings.radius, scale, scale * settings.radius)
  geometry.computeBoundingBox()
  const box = geometry.boundingBox
  geometry.translate(-(box.min.x + box.max.x) / 2, -box.min.y, -(box.min.z + box.max.z) / 2)
  geometry.computeVertexNormals()
  geometry.computeBoundingSphere()
  geometry.userData.promptObject = settings.primitive
  return geometry
}
