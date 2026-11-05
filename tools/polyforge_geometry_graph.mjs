#!/usr/bin/env node
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import {
  bakeGeometryGraph,
  createGeometryGraph,
  evaluateGeometryGraph,
  parseGeometryGraph,
  serializeAssetDocument,
  serializeGeometryGraph,
  stableStringify,
} from '../web-adapters/native/polyforge/index.js'

function argumentsFrom(argv) {
  const [command, ...rest] = argv
  const options = { command }
  for (let index = 0; index < rest.length; index += 2) options[rest[index].replace(/^--/, '')] = rest[index + 1]
  return options
}

const source = () => ({
  id: 'n000000',
  type: 'source.generate',
  parameters: {
    id: 'prop.wayfinder_relay',
    name: 'Wayfinder Relay',
    settings: { primitive: 'crystal', seed: 20261106, color: '#7DD3FC' },
    sockets: [{ name: 'attachment', position: [0, 3.9, 0] }],
  },
  position: { x: 0, y: 120 },
})
const output = () => ({ id: 'n000003', type: 'output.asset', parameters: {}, position: { x: 660, y: 120 } })
const assetLink = (id, from, to) => ({ id, from: { node: from, socket: 'asset' }, to: { node: to, socket: 'asset' } })

async function createExample(outputPath) {
  const partial = createGeometryGraph({
    id: 'graph.wayfinder_relay',
    name: 'Wayfinder Relay Geometry',
    nodes: [
      source(),
      { id: 'n000001', type: 'edit.extrudeFace', parameters: { faceId: 'f000000', distance: 0.18 }, position: { x: 220, y: 0 } },
      { id: 'n000002', type: 'edit.split', parameters: { edgeId: 'e000000' }, position: { x: 440, y: 0 } },
      output(),
    ],
    links: [assetLink('l000000', 'n000000', 'n000001'), assetLink('l000001', 'n000001', 'n000002'), assetLink('l000002', 'n000002', 'n000003')],
    outputs: { asset: { node: 'n000003', socket: 'asset' } },
  })
  const midpoint = evaluateGeometryGraph(partial).document.vertices.at(-1)
  const graph = createGeometryGraph({
    id: 'graph.wayfinder_relay',
    name: 'Wayfinder Relay Geometry',
    nodes: [
      source(),
      { id: 'n000001', type: 'edit.extrudeFace', parameters: { faceId: 'f000000', distance: 0.18 }, position: { x: 180, y: 0 } },
      { id: 'n000002', type: 'edit.split', parameters: { edgeId: 'e000000' }, position: { x: 360, y: 0 } },
      { id: 'n000003', type: 'edit.move', parameters: { vertexIds: [midpoint.id], delta: [0.03, -0.02, 0.04] }, position: { x: 540, y: 0 } },
      { id: 'n000004', type: 'modify.transform', parameters: { scale: [0.95, 1.15, 0.95], rotation: [0, 30, 0], translation: [0, 0.1, 0], includeSockets: true }, position: { x: 720, y: 0 } },
      { id: 'n000005', type: 'configure.budgets', parameters: { levels: [
        { level: 'lod0', distanceBand: 'hero', maxTriangles: 64 },
        { level: 'lod1', distanceBand: 'gameplay', maxTriangles: 48 },
        { level: 'lod2', distanceBand: 'far', maxTriangles: 32 },
        { level: 'lod3', distanceBand: 'proxy', maxTriangles: 24 },
      ] }, position: { x: 900, y: 0 } },
      { id: 'n000006', type: 'measure.asset', parameters: {}, position: { x: 1080, y: 0 } },
      { id: 'n000007', type: 'output.asset', parameters: {}, position: { x: 1260, y: 0 } },
    ],
    links: Array.from({ length: 7 }, (_, index) => assetLink(`l${String(index).padStart(6, '0')}`, `n${String(index).padStart(6, '0')}`, `n${String(index + 1).padStart(6, '0')}`)),
    outputs: { asset: { node: 'n000007', socket: 'asset' }, stats: { node: 'n000006', socket: 'stats' } },
  })
  await mkdir(path.dirname(outputPath), { recursive: true })
  await writeFile(outputPath, serializeGeometryGraph(graph))
  const evaluated = evaluateGeometryGraph(graph)
  console.log(JSON.stringify({ command: 'create', id: graph.id, output: outputPath, checksum: graph.checksum, nodes: graph.nodes.length, links: graph.links.length, triangles: evaluated.stats.triangles }))
}

async function build(graphPath, sourceOutput, outputDirectory, descriptorOption) {
  const graph = parseGeometryGraph(await readFile(graphPath, 'utf8'))
  const baked = bakeGeometryGraph(graph)
  if (sourceOutput) {
    await mkdir(path.dirname(sourceOutput), { recursive: true })
    await writeFile(sourceOutput, serializeAssetDocument(baked.document))
  }
  await mkdir(path.join(outputDirectory, 'assets'), { recursive: true })
  for (const level of baked.levels) await writeFile(path.join(outputDirectory, `assets/${baked.document.id}.${level.level}.glb`), level.glb)
  const descriptorPath = descriptorOption || path.join(outputDirectory, `${baked.document.id}.asset.json`)
  await mkdir(path.dirname(descriptorPath), { recursive: true })
  await writeFile(descriptorPath, `${stableStringify(baked.descriptor, 2)}\n`)
  console.log(JSON.stringify({
    command: 'build',
    graph: graph.id,
    asset: baked.document.id,
    source: sourceOutput || null,
    descriptor: descriptorPath,
    trace: baked.evaluation.trace.map((entry) => entry.nodeId),
    levels: baked.descriptor.levels.map((level) => ({ level: level.level, triangles: level.triangles, bytes: level.bytes })),
  }))
}

const options = argumentsFrom(process.argv.slice(2))
if (options.command === 'create' && options.output) await createExample(options.output)
else if (options.command === 'build' && options.graph && options['output-dir']) await build(options.graph, options['source-output'], options['output-dir'], options.descriptor)
else if (options.command === 'evaluate' && options.graph) {
  const graph = parseGeometryGraph(await readFile(options.graph, 'utf8'))
  const result = evaluateGeometryGraph(graph)
  console.log(JSON.stringify({ graph: result.graphId, checksum: result.graphChecksum, stats: result.stats, trace: result.trace }, null, 2))
} else {
  console.error('Use: create --output <file.graph.json> | evaluate --graph <file.graph.json> | build --graph <file.graph.json> --output-dir <directory> [--source-output <file.forge.json>] [--descriptor <file.asset.json>]')
  process.exitCode = 2
}
