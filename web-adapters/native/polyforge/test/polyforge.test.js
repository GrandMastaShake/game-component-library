import test from 'node:test'
import assert from 'node:assert/strict'
import {
  LowPolyGenerator,
  PRESETS,
  PROMPT_OBJECTS,
  generate,
  generateFromPrompt,
  interpretPrompt,
  toMeshData,
} from '../index.js'

for (const preset of PRESETS) {
  test(`${preset.id}: default parametric mesh is closed and non-degenerate`, () => {
    const result = generate({ primitive: preset.id })
    assert.equal(result.stats.manifold, true)
    assert.equal(result.stats.degenerate, 0)
    result.geometry.dispose()
  })
}

for (const object of PROMPT_OBJECTS) {
  test(`${object.id}: default prompt mesh is closed and quad-dominant`, () => {
    const result = generate({ primitive: object.id })
    assert.equal(result.stats.manifold, true)
    assert.equal(result.stats.degenerate, 0)
    assert.ok(result.stats.quads > 0)
    assert.ok(result.stats.quadRatio > 0.5)
    assert.equal(result.stats.unifiedFaces, result.faces.length)
    assert.equal(result.stats.vertices, result.geometry.attributes.position.count)
    result.geometry.dispose()
  })
}

test('generation is deterministic and returns serializable mesh data', () => {
  const first = generateFromPrompt('a tall broad rocket', { seed: 42 })
  const second = generateFromPrompt('a tall broad rocket', { seed: 42 })
  return Promise.all([first, second]).then(([a, b]) => {
    assert.deepEqual(toMeshData(a), toMeshData(b))
    assert.doesNotThrow(() => JSON.stringify(toMeshData(a)))
    assert.equal(a.settings.primitive, 'rocket')
    assert.equal(a.settings.height, 3.8)
    assert.equal(a.settings.radius, 1.45)
    a.geometry.dispose()
    b.geometry.dispose()
  })
})

test('local prompt interpretation rejects an unknown object clearly', () => {
  assert.throws(() => interpretPrompt('a low-poly helicopter'), /Try house, rocket/)
})

test('an optional prompt adapter can extend the local settings patch', async () => {
  const result = await generateFromPrompt('a tiny house', {
    adapter: async () => ({ color: '#123456', twist: 0.4 }),
  })
  assert.equal(result.settings.color, '#123456')
  assert.equal(result.settings.twist, 0.4)
  assert.equal(result.settings.primitive, 'house')
  result.geometry.dispose()
})

test('vertex move is replayable without mutating the base geometry', () => {
  const base = generate({ primitive: 'rocket' })
  const original = base.geometry.attributes.position.getY(0)
  const edited = new LowPolyGenerator().edit(base.geometry, [{ type: 'move', indices: [0], delta: [0, 0.5, 0] }])
  assert.equal(base.geometry.attributes.position.getY(0), original)
  assert.equal(edited.attributes.position.getY(0), original + 0.5)
  base.geometry.dispose()
  edited.dispose()
})

test('edge split adds one midpoint and preserves a closed mesh', () => {
  const base = generate({ primitive: 'rocket' })
  const [a, b] = base.geometry.index.array.slice(0, 2)
  const result = generate({ primitive: 'rocket', meshEdits: [{ type: 'split', indices: [a, b] }] })
  assert.equal(result.stats.vertices, base.stats.vertices + 1)
  assert.equal(result.stats.manifold, true)
  assert.ok(result.geometry.index.count > base.geometry.index.count)
  base.geometry.dispose()
  result.geometry.dispose()
})

test('face extrusion adds geometry and face deletion opens three boundaries', () => {
  const base = generate({ primitive: 'rocket' })
  const editor = new LowPolyGenerator()
  const extruded = editor.edit(base.geometry, [{ type: 'extrudeFace', face: 0, distance: 0.25 }])
  assert.ok(extruded.index.count > base.geometry.index.count)
  const deleted = editor.edit(base.geometry, [{ type: 'deleteFace', face: 0 }])
  const deletedResult = generate({ primitive: 'rocket', meshEdits: [{ type: 'deleteFace', face: 0 }] })
  assert.equal(deletedResult.stats.boundary, 3)
  base.geometry.dispose()
  extruded.dispose()
  deleted.dispose()
  deletedResult.geometry.dispose()
})

test('the stateful brick preserves defaults while allowing per-call overrides', () => {
  const brick = new LowPolyGenerator({ primitive: 'tree', seed: 7 })
  const tree = brick.generate()
  const rock = brick.generate({ primitive: 'rock' })
  assert.equal(tree.settings.primitive, 'tree')
  assert.equal(tree.settings.seed, 7)
  assert.equal(rock.settings.primitive, 'rock')
  assert.equal(rock.settings.seed, 7)
  tree.geometry.dispose()
  rock.geometry.dispose()
})

test('the stateful prompt API preserves defaults without masking prompt settings', async () => {
  const brick = new LowPolyGenerator({ primitive: 'tree', seed: 7 })
  const result = await brick.generateFromPrompt('a tall broad rocket')
  assert.equal(result.settings.primitive, 'rocket')
  assert.equal(result.settings.height, 3.8)
  assert.equal(result.settings.radius, 1.45)
  assert.equal(result.settings.detail, 1)
  assert.equal(result.settings.seed, 7)
  result.geometry.dispose()
})
