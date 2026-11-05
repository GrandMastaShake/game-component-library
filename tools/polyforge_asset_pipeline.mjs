#!/usr/bin/env node
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import {
  applyAssetOperations,
  bakeAsset,
  createAssetDocument,
  generate,
  parseAssetDocument,
  serializeAssetDocument,
  stableStringify,
} from '../web-adapters/native/polyforge/index.js'

function argumentsFrom(argv) {
  const [command, ...rest] = argv
  const options = { command }
  for (let index = 0; index < rest.length; index += 2) {
    options[rest[index].replace(/^--/, '')] = rest[index + 1]
  }
  return options
}

async function createExample(output) {
  const generated = generate({ primitive: 'crystal', seed: 20261105, color: '#6EE7B7' })
  let document
  try {
    document = createAssetDocument({
      id: 'prop.wayfinder',
      name: 'Wayfinder Beacon',
      result: generated,
      budgets: [
        { level: 'lod0', distanceBand: 'hero', maxTriangles: 50 },
        { level: 'lod1', distanceBand: 'gameplay', maxTriangles: 40 },
        { level: 'lod2', distanceBand: 'far', maxTriangles: 32 },
        { level: 'lod3', distanceBand: 'proxy', maxTriangles: 24 },
      ],
      sockets: [{ name: 'attachment', position: [0, 3.9, 0] }],
    })
  } finally {
    generated.geometry.dispose()
  }
  document = applyAssetOperations(document, [{ type: 'split', edgeId: document.edges[0].id }])
  const midpoint = document.vertices.at(-1)
  document = applyAssetOperations(document, [{ type: 'move', vertexIds: [midpoint.id], delta: [0.02, 0.04, -0.03] }])
  await mkdir(path.dirname(output), { recursive: true })
  await writeFile(output, serializeAssetDocument(document))
  console.log(JSON.stringify({ command: 'create', id: document.id, output, checksum: document.checksum }))
}

async function bake(source, outputDirectory) {
  const document = parseAssetDocument(await readFile(source, 'utf8'))
  const baked = bakeAsset(document)
  const assets = path.join(outputDirectory, 'assets')
  await mkdir(assets, { recursive: true })
  for (const level of baked.levels) {
    await writeFile(path.join(outputDirectory, `assets/${document.id}.${level.level}.glb`), level.glb)
  }
  const descriptorPath = path.join(outputDirectory, `${document.id}.asset.json`)
  await writeFile(descriptorPath, `${stableStringify(baked.descriptor, 2)}\n`)
  console.log(JSON.stringify({
    command: 'bake',
    id: document.id,
    descriptor: descriptorPath,
    levels: baked.descriptor.levels.map((level) => ({ level: level.level, triangles: level.triangles, bytes: level.bytes })),
  }))
}

const options = argumentsFrom(process.argv.slice(2))
if (options.command === 'create' && options.output) await createExample(options.output)
else if (options.command === 'bake' && options.source && options['output-dir']) await bake(options.source, options['output-dir'])
else {
  console.error('Use: create --output <file.forge.json> | bake --source <file.forge.json> --output-dir <directory>')
  process.exitCode = 2
}
