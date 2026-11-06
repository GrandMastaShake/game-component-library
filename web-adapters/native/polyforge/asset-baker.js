import { assetDocumentStats, assetDocumentToMeshData, validateAssetDocument } from './asset-core.js'
import { decimateMeshData } from './mesh-data.js'

const GLB_MAGIC = 0x46546c67
const JSON_CHUNK = 0x4e4f534a
const BIN_CHUNK = 0x004e4942

function vertexNormals(mesh) {
  const normals = new Array(mesh.positions.length).fill(0)
  for (let index = 0; index < mesh.indices.length; index += 3) {
    const [a, b, c] = mesh.indices.slice(index, index + 3)
    const ai = a * 3
    const bi = b * 3
    const ci = c * 3
    const ab = [0, 1, 2].map((axis) => mesh.positions[bi + axis] - mesh.positions[ai + axis])
    const ac = [0, 1, 2].map((axis) => mesh.positions[ci + axis] - mesh.positions[ai + axis])
    const cross = [ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0]]
    for (const vertex of [a, b, c]) {
      for (let axis = 0; axis < 3; axis += 1) normals[vertex * 3 + axis] += cross[axis]
    }
  }
  for (let index = 0; index < normals.length; index += 3) {
    const length = Math.hypot(normals[index], normals[index + 1], normals[index + 2])
    if (length > 1e-12) {
      normals[index] /= length
      normals[index + 1] /= length
      normals[index + 2] /= length
    } else normals[index + 1] = 1
  }
  return normals
}

function bounds(positions) {
  const minimum = [Infinity, Infinity, Infinity]
  const maximum = [-Infinity, -Infinity, -Infinity]
  for (let index = 0; index < positions.length; index += 3) {
    for (let axis = 0; axis < 3; axis += 1) {
      minimum[axis] = Math.min(minimum[axis], positions[index + axis])
      maximum[axis] = Math.max(maximum[axis], positions[index + axis])
    }
  }
  return { minimum, maximum }
}

function padded(length, alignment = 4) {
  return Math.ceil(length / alignment) * alignment
}

/** Encode one indexed, vertex-colored mesh as a self-contained glTF 2.0 binary. */
export function encodeGLB(document, mesh) {
  const normals = vertexNormals(mesh)
  const material = document.materials[0]
  const json = {
    asset: { version: '2.0', generator: 'POLYFORGE Asset Baker 0.5.0' },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ name: document.id, mesh: 0 }],
    meshes: [{ primitives: [{ attributes: {}, mode: 4, material: 0 }] }],
    materials: [{
      name: material.id,
      pbrMetallicRoughness: {
        baseColorFactor: material.baseColor,
        metallicFactor: material.metallic,
        roughnessFactor: material.roughness,
      },
      doubleSided: false,
    }],
    buffers: [{ byteLength: 0 }],
    bufferViews: [],
    accessors: [],
  }
  if (document.sockets.length) {
    json.scenes[0].nodes.push(...document.sockets.map((_, index) => index + 1))
    document.sockets.forEach((socket, index) => {
      json.nodes.push({ name: `socket_${socket.name}`, translation: socket.position })
    })
  }

  const chunks = []
  let byteOffset = 0
  const addAccessor = (values, type, componentType, target) => {
    const ArrayType = componentType === 5126 ? Float32Array : Uint32Array
    const typed = ArrayType.from(values)
    const offset = padded(byteOffset)
    if (offset > byteOffset) chunks.push({ bytes: new Uint8Array(offset - byteOffset), offset: byteOffset })
    chunks.push({ bytes: new Uint8Array(typed.buffer), offset })
    const components = { SCALAR: 1, VEC2: 2, VEC3: 3 }[type]
    const bufferView = json.bufferViews.length
    json.bufferViews.push({ buffer: 0, byteOffset: offset, byteLength: typed.byteLength, target })
    const accessor = { bufferView, componentType, count: typed.length / components, type }
    if (type === 'VEC3' && target === 34962) {
      const { minimum, maximum } = bounds(values)
      accessor.min = minimum
      accessor.max = maximum
    }
    const index = json.accessors.length
    json.accessors.push(accessor)
    byteOffset = offset + typed.byteLength
    return index
  }

  const primitive = json.meshes[0].primitives[0]
  primitive.attributes.POSITION = addAccessor(mesh.positions, 'VEC3', 5126, 34962)
  primitive.attributes.NORMAL = addAccessor(normals, 'VEC3', 5126, 34962)
  if (mesh.colors) primitive.attributes.COLOR_0 = addAccessor(mesh.colors, 'VEC3', 5126, 34962)
  primitive.indices = addAccessor(mesh.indices, 'SCALAR', 5125, 34963)
  json.buffers[0].byteLength = padded(byteOffset)

  const binary = new Uint8Array(json.buffers[0].byteLength)
  for (const chunk of chunks) binary.set(chunk.bytes, chunk.offset)
  const jsonBytes = new TextEncoder().encode(JSON.stringify(json))
  const jsonLength = padded(jsonBytes.byteLength)
  const totalLength = 12 + 8 + jsonLength + 8 + binary.byteLength
  const output = new Uint8Array(totalLength)
  const view = new DataView(output.buffer)
  view.setUint32(0, GLB_MAGIC, true)
  view.setUint32(4, 2, true)
  view.setUint32(8, totalLength, true)
  view.setUint32(12, jsonLength, true)
  view.setUint32(16, JSON_CHUNK, true)
  output.set(jsonBytes, 20)
  output.fill(0x20, 20 + jsonBytes.byteLength, 20 + jsonLength)
  const binaryHeader = 20 + jsonLength
  view.setUint32(binaryHeader, binary.byteLength, true)
  view.setUint32(binaryHeader + 4, BIN_CHUNK, true)
  output.set(binary, binaryHeader + 8)
  return output
}

function asBytes(value) {
  return value instanceof Uint8Array ? value : new Uint8Array(value)
}

/** Read structural and cost claims back from the exported bytes. */
export function inspectGLB(input) {
  const bytes = asBytes(input)
  if (bytes.byteLength < 28) throw new Error('GLB is too short')
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  if (view.getUint32(0, true) !== GLB_MAGIC) throw new Error('Invalid GLB magic')
  if (view.getUint32(4, true) !== 2) throw new Error('Unsupported GLB version')
  if (view.getUint32(8, true) !== bytes.byteLength) throw new Error('GLB length header does not match the file')
  const jsonLength = view.getUint32(12, true)
  if (view.getUint32(16, true) !== JSON_CHUNK) throw new Error('GLB has no JSON first chunk')
  const jsonStart = 20
  const binaryHeader = jsonStart + jsonLength
  if (binaryHeader + 8 > bytes.byteLength) throw new Error('GLB JSON chunk exceeds the file')
  if (view.getUint32(binaryHeader + 4, true) !== BIN_CHUNK) throw new Error('GLB has no binary chunk')
  const binaryLength = view.getUint32(binaryHeader, true)
  const binaryStart = binaryHeader + 8
  if (binaryStart + binaryLength > bytes.byteLength) throw new Error('GLB binary chunk exceeds the file')
  const document = JSON.parse(new TextDecoder().decode(bytes.subarray(jsonStart, binaryHeader)))
  if (document.asset?.version !== '2.0') throw new Error('GLB does not contain glTF 2.0')

  const accessorBytes = (accessor) => {
    const components = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 }[accessor.type]
    const sizes = { 5121: 1, 5123: 2, 5125: 4, 5126: 4 }
    const bufferView = document.bufferViews?.[accessor.bufferView]
    if (!components || !sizes[accessor.componentType] || !bufferView) throw new Error('Unsupported or missing accessor data')
    const length = accessor.count * components * sizes[accessor.componentType]
    if ((bufferView.byteOffset || 0) + length > binaryLength) throw new Error('Accessor exceeds the binary chunk')
    return length
  }
  document.accessors?.forEach(accessorBytes)

  let triangles = 0
  let vertices = 0
  for (const mesh of document.meshes || []) {
    for (const primitive of mesh.primitives || []) {
      if ((primitive.mode ?? 4) !== 4) throw new Error('Only triangle primitives are supported')
      const indices = document.accessors?.[primitive.indices]
      const position = document.accessors?.[primitive.attributes?.POSITION]
      if (!indices || !position || indices.count % 3) throw new Error('Primitive has invalid triangle accessors')
      triangles += indices.count / 3
      vertices += position.count
    }
  }
  return {
    format: 'gltf-binary',
    bytes: bytes.byteLength,
    triangles,
    vertices,
    sockets: (document.nodes || []).filter((node) => node.name?.startsWith('socket_')).map((node) => node.name.slice(7)),
    generator: document.asset.generator,
  }
}

/** Bake every declared budget and derive the runtime descriptor from GLB readback. */
export function bakeAsset(document, { strict = true } = {}) {
  const sourceStats = validateAssetDocument(document)
  if (document.materials.length !== 1) throw new Error('Asset Baker 0.5 exports one material; multi-material baking belongs to the material pack')
  const source = assetDocumentToMeshData(document)
  const levels = document.budgets.levels.map((budget) => {
    const reduced = decimateMeshData(source, budget.maxTriangles)
    if (strict && !reduced.stats.withinBudget) {
      throw new Error(`${document.id} ${budget.level} cannot meet ${budget.maxTriangles} triangles without violating topology guards (remaining ${reduced.stats.triangles})`)
    }
    const mesh = { positions: reduced.positions, colors: reduced.colors, indices: reduced.indices }
    const glb = encodeGLB(document, mesh)
    const readback = inspectGLB(glb)
    return {
      ...budget,
      mesh,
      glb,
      reduction: reduced.stats,
      readback,
      withinBudget: readback.triangles <= budget.maxTriangles,
    }
  })
  const descriptor = {
    id: document.id,
    name: document.name,
    description: `Deterministic POLYFORGE bake of ${document.id} with ${sourceStats.triangles} editable-source triangles.`,
    format: 'gltf-binary',
    units: document.units,
    forwardAxis: document.forwardAxis,
    sockets: document.sockets.map((socket) => ({ name: socket.name, position: [...socket.position] })),
    levels: levels.map((level) => ({
      level: level.level,
      distanceBand: level.distanceBand,
      file: `assets/${document.id}.${level.level}.glb`,
      triangles: level.readback.triangles,
      bytes: level.readback.bytes,
    })),
    source: {
      tool: 'POLYFORGE Asset Baker 0.5.0',
      repository: 'GrandMastaShake/game-component-library',
      script: 'web-adapters/native/polyforge/asset-baker.js',
      kind: 'generated',
    },
    provenance: 'Original procedural geometry generated and measured by the library-native POLYFORGE asset pipeline; no third-party mesh, texture, or commercial game content is included.',
  }
  return { document, descriptor, levels, stats: { ...sourceStats, bakedLevels: levels.length } }
}
