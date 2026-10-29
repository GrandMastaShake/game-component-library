import { DEFAULTS, PRESETS, analyzeTopology, generateGeometry } from './mesh.js'
import { PROMPT_OBJECTS, interpretPrompt, isPromptObject, resolvePrompt } from './prompt-mesh.js'
import { applyMeshEdits, readMeshEdits } from './mesh-edit.js'
import { buildQuadDominant } from './quad-mesh.js'

export { DEFAULTS, PRESETS, PROMPT_OBJECTS, analyzeTopology, applyMeshEdits, buildQuadDominant, interpretPrompt, readMeshEdits, resolvePrompt }

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
  const geometry = operations.length ? applyMeshEdits(base, operations) : base
  if (geometry !== base) base.dispose()

  const quadMesh = buildQuadDominant(geometry)
  const topology = analyzeTopology(geometry)
  const stats = {
    ...topology,
    unifiedFaces: quadMesh.faces.length,
    quads: quadMesh.stats.quads,
    quadRatio: quadMesh.stats.quadRatio,
    faceReduction: quadMesh.stats.faceReduction,
    faceReductionRatio: quadMesh.stats.faceReductionRatio,
  }
  return { geometry, settings, operations, faces: quadMesh.faces, stats }
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
}
