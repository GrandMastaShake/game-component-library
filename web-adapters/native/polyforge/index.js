import { DEFAULTS, PRESETS, analyzeTopology, generateGeometry } from './mesh.js'
import { PROMPT_OBJECTS, interpretPrompt, isPromptObject, resolvePrompt } from './prompt-mesh.js'
import { applyMeshEdits, readMeshEdits } from './mesh-edit.js'
import { buildQuadDominant } from './quad-mesh.js'
import { decimateMeshData, geometryToMeshData, meshDataToGeometry } from './mesh-data.js'
import { applyAssetOperations, assetDocumentStats, assetDocumentToMeshData, checksumAssetDocument, createAssetDocument, defaultBudgets, parseAssetDocument, serializeAssetDocument, stableStringify, validateAssetDocument } from './asset-core.js'
import { DEFAULT_FILE_ROOT, bakeAsset, encodeGLB, inspectGLB } from './asset-baker.js'

export { DEFAULTS, PRESETS, PROMPT_OBJECTS, analyzeTopology, applyMeshEdits, buildQuadDominant, interpretPrompt, readMeshEdits, resolvePrompt }
export { DEFAULT_FILE_ROOT, applyAssetOperations, assetDocumentStats, assetDocumentToMeshData, bakeAsset, checksumAssetDocument, createAssetDocument, decimateMeshData, defaultBudgets, encodeGLB, inspectGLB, parseAssetDocument, serializeAssetDocument, stableStringify, validateAssetDocument }

export function normalizeSettings(input = {}) {
  const settings = { ...DEFAULTS, ...input }
  if (!input.primitive && input.shapeType) {
    settings.primitive = isPromptObject(input.shapeType) ? input.shapeType : 'rock'
  }
  return settings
}

function operationsFrom(value) {
  if (Array.isArray(value)) return value
  return readMeshEdits(value)
}

/** Generate a render-ready BufferGeometry plus inspectable quad-dominant topology. */
export function generate(input = {}) {
  const settings = normalizeSettings(input)
  const base = generateGeometry(settings)
  const operations = operationsFrom(input.meshEdits)
  let geometry = operations.length ? applyMeshEdits(base, operations) : base
  if (geometry !== base) base.dispose()

  let budget = null
  if (input.targetFaceCount !== undefined) {
    const reduced = decimateMeshData(geometryToMeshData(geometry), input.targetFaceCount)
    if (!reduced.stats.withinBudget) {
      geometry.dispose()
      throw new Error(`targetFaceCount ${input.targetFaceCount} is unreachable without violating topology guards (remaining ${reduced.stats.triangles})`)
    }
    geometry.dispose()
    geometry = meshDataToGeometry(reduced)
    budget = { ...reduced.stats }
  }

  const quadMesh = buildQuadDominant(geometry)
  const topology = analyzeTopology(geometry)
  const stats = {
    ...topology,
    unifiedFaces: quadMesh.faces.length,
    quads: quadMesh.stats.quads,
    quadRatio: quadMesh.stats.quadRatio,
    faceReduction: quadMesh.stats.faceReduction,
    faceReductionRatio: quadMesh.stats.faceReductionRatio,
    ...(budget ? { budget } : {}),
  }
  // The contract's `performanceBudget` output: present only when a budget was
  // asked for. Also kept at stats.budget, where 0.4.0 put it.
  return { geometry, settings, operations, faces: quadMesh.faces, stats, ...(budget ? { performanceBudget: { ...budget } } : {}) }
}

/** Resolve a natural-language prompt locally, or through an optional async adapter. */
export async function generateFromPrompt(prompt, options = {}) {
  const { adapter, ...overrides } = options
  const settings = await resolvePrompt(prompt, adapter)
  return generate({ ...settings, ...overrides })
}

/** Convert a result to plain data for serialization or a non-Three.js renderer. */
export function toMeshData(result) {
  const { geometry, faces, stats, settings, operations } = result
  const position = geometry.getAttribute('position')
  const color = geometry.getAttribute('color')
  return {
    positions: Array.from(position.array),
    indices: geometry.index ? Array.from(geometry.index.array) : Array.from({ length: position.count }, (_, index) => index),
    colors: color ? Array.from(color.array) : null,
    faces: faces.map((face) => [...face]),
    stats: { ...stats },
    settings: { ...settings },
    operations: operations.map((operation) => ({ ...operation })),
  }
}

/** Generate, canonicalize, budget, export, and read back an original asset. */
export function bakeGeneratedAsset({ id, name, input = {}, budgets, sockets, materials, strict = true, fileRoot }) {
  const result = generate(input)
  try {
    const document = createAssetDocument({ id, name, result, budgets, sockets, materials })
    return bakeAsset(document, { strict, ...(fileRoot !== undefined ? { fileRoot } : {}) })
  } finally {
    result.geometry.dispose()
  }
}

/** Stateful convenience wrapper; all generation and edits remain deterministic. */
export class LowPolyGenerator {
  constructor(defaults = {}) {
    this.defaults = { ...defaults }
  }

  generate(overrides = {}) {
    return generate({ ...this.defaults, ...overrides })
  }

  generateFromPrompt(prompt, options = {}) {
    const { adapter, ...overrides } = options
    const defaults = { ...this.defaults }
    // A constructor's parametric shape must not mask the object named by a prompt.
    delete defaults.primitive
    delete defaults.shapeType
    return generateFromPrompt(prompt, { ...defaults, ...overrides, adapter })
  }

  edit(geometry, operations) {
    return applyMeshEdits(geometry, operationsFrom(operations))
  }

  createAsset({ id, name, budgets, sockets, materials, ...overrides } = {}) {
    const result = this.generate(overrides)
    try {
      return createAssetDocument({ id, name, result, budgets, sockets, materials })
    } finally {
      result.geometry.dispose()
    }
  }

  bakeAsset({ id, name, budgets, sockets, materials, strict = true, fileRoot, ...overrides } = {}) {
    return bakeGeneratedAsset({ id, name, input: { ...this.defaults, ...overrides }, budgets, sockets, materials, strict, fileRoot })
  }
}
