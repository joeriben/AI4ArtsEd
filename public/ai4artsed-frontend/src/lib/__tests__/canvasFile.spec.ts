import { describe, expect, it } from 'vitest'
import { fileDateParts, fileNamePart, mediaFileName } from '@/lib/downloadMedia'
import {
  CANVAS_FILE_FORMAT_VERSION,
  NotACanvasFile,
  canvasFileName,
  canvasFileStem,
  canvasFileText,
  readCanvasFile,
  toCanvasWorkflow,
} from '@/lib/canvasFile'
import type { CanvasWorkflow } from '@/types/canvas'
import apparatus from '@/views/__tests__/fixtures/apparatus_export.json'

const AT = new Date(2026, 9, 1, 14, 32)

function board(over: Partial<CanvasWorkflow> = {}): CanvasWorkflow {
  return {
    id: 'workflow_1',
    name: '',
    type: 'canvas_workflow',
    nodes: [],
    connections: [],
    ...over,
  } as CanvasWorkflow
}

describe('fileNamePart', () => {
  it('spells the German letters out', () => {
    expect(fileNamePart('Größe über Äpfel')).toBe('Groesse-ueber-Aepfel')
  })
  it('strips the marks of other Latin letters', () => {
    expect(fileNamePart('Café crème à Łódź')).toBe('Cafe-creme-a-Lodz')
    expect(fileNamePart('Çağrı')).toBe('Cagri')
  })
  it('keeps the platform\'s other scripts as written', () => {
    expect(fileNamePart('Привіт світ')).toBe('Привіт-світ')
    expect(fileNamePart('고양이 그림')).toBe('고양이-그림')
    expect(fileNamePart('שָׁלוֹם')).toBe('שָׁלוֹם')
  })
  it('turns everything else into one dash, and none at the ends', () => {
    expect(fileNamePart('  a/b\\c:d*e?"f<g>h|  ')).toBe('a-b-c-d-e-f-g-h')
    expect(fileNamePart('sd3_5_large')).toBe('sd3-5-large')
    expect(fileNamePart('...')).toBe('')
  })
  it('cuts at a word where there is one in the second half', () => {
    expect(fileNamePart('a photograph of a cat sitting on a windowsill')).toBe('a-photograph-of-a-cat-sitting-on')
    expect(fileNamePart('x'.repeat(40))).toBe('x'.repeat(32))
  })
})

describe('mediaFileName', () => {
  it('joins the parts with underscores and drops the empty ones', () => {
    expect(mediaFileName('Mein Bild', ['2026-10-01', '', null, 'sd3.5 large', 2], 'png'))
      .toBe('Mein-Bild_2026-10-01_sd3-5-large_2.png')
    expect(mediaFileName('', [], 'png')).toBe('download.png')
  })
  it('stays within 200 bytes', () => {
    const name = mediaFileName('가'.repeat(32), Array(8).fill('나'.repeat(32)), 'png')
    expect(new TextEncoder().encode(name.replace(/\.png$/, '')).length).toBeLessThanOrEqual(200)
    expect(name.endsWith('.png')).toBe(true)
    expect(/[-_]\.png$/.test(name)).toBe(false)
  })
})

describe('fileDateParts', () => {
  it('names the day and the minute in local time', () => {
    expect(fileDateParts(AT)).toEqual(['2026-10-01', '1432'])
    expect(fileDateParts(AT.getTime())).toEqual(['2026-10-01', '1432'])
  })
})

describe('canvas file name', () => {
  const input = { id: 'n1', type: 'input', x: 0, y: 0, promptText: 'Ein Haus am Meer' }
  const gen = { id: 'n2', type: 'generation', x: 0, y: 0, configId: 'sd3.5_large' }

  it('starts with the name somebody gave the workflow', () => {
    expect(canvasFileName(board({ name: 'Perspektive gegen Rohtext', nodes: [input, gen] as any }), AT))
      .toBe('Perspektive-gegen-Rohtext_2026-10-01_1432.atcanvas')
  })
  it('falls back to the prompt, then the models, then the word canvas', () => {
    expect(canvasFileStem(board({ nodes: [input, gen] as any }))).toBe('Ein Haus am Meer')
    expect(canvasFileStem(board({ nodes: [gen] as any }))).toBe('sd3.5_large')
    expect(canvasFileStem(board())).toBe('canvas')
  })
  it('reads the old default name as no name', () => {
    expect(canvasFileStem(board({ name: 'New Workflow', nodes: [input] as any }))).toBe('Ein Haus am Meer')
  })
})

describe('reading a canvas file', () => {
  it('reads its own file back, without the version marker', () => {
    const saved = board({ name: 'Zwei', nodes: [{ id: 'n1', type: 'input', x: 0, y: 0 }] as any })
    const text = canvasFileText(saved)
    expect(JSON.parse(text).formatVersion).toBe(CANVAS_FILE_FORMAT_VERSION)
    const read = readCanvasFile(text) as unknown as Record<string, unknown>
    expect(read.formatVersion).toBeUndefined()
    expect(read.name).toBe('Zwei')
    expect(read.type).toBe('canvas_workflow')
  })
  it('opens an export from before the extension existed', () => {
    const legacy = JSON.stringify({
      id: 'workflow_9', name: 'New Workflow', type: 'canvas_workflow',
      nodes: [{ id: 'n1', type: 'input', x: 0, y: 0 }], connections: [],
    })
    expect(readCanvasFile(legacy).nodes).toHaveLength(1)
  })
  it('opens a Resona apparatus', () => {
    expect(toCanvasWorkflow(apparatus).nodes.length).toBe(apparatus.nodes.length)
  })
  it('opens a bare graph as a run records it', () => {
    const wf = toCanvasWorkflow({ nodes: [{ id: 'a', type: 'input' }], connections: [] })
    expect(wf.type).toBe('canvas_workflow')
    expect(wf.name).toBe('')
    expect(wf.id).toMatch(/^workflow_/)
  })
  it('refuses what is not a Canvas workflow', () => {
    expect(() => readCanvasFile('not json')).toThrow(NotACanvasFile)
    expect(() => readCanvasFile('{"favorites": []}')).toThrow(NotACanvasFile)
    expect(() => readCanvasFile('[1, 2]')).toThrow(NotACanvasFile)
    expect(() => readCanvasFile('{"nodes": [{"x": 1}]}')).toThrow(NotACanvasFile)
    expect(() => readCanvasFile('{"type": "canvas_workflow", "nodes": [], "connections": 3}'))
      .toThrow(NotACanvasFile)
  })
  it('refuses a graph of nodes the Canvas does not draw', () => {
    // Obsidian's JSON Canvas: `.canvas`, nodes with an id and a type.
    expect(() => readCanvasFile(JSON.stringify({
      nodes: [{ id: 'a', type: 'text', text: 'x', x: 0, y: 0, width: 10, height: 10 }], edges: [],
    }))).toThrow(NotACanvasFile)
    expect(() => readCanvasFile('{"nodes": []}')).toThrow(NotACanvasFile)
    expect(() => readCanvasFile('{"type": "canvas_workflow", "nodes": [1]}')).toThrow(NotACanvasFile)
    expect(() => readCanvasFile(JSON.stringify({
      type: 'canvas_workflow', nodes: [{ id: 'a', type: 'binary_fork' }],
    }))).toThrow(NotACanvasFile)
  })
  it('opens the evaluation nodes of January 2026 as the node that replaced them', () => {
    const wf = readCanvasFile(JSON.stringify({
      type: 'canvas_workflow',
      nodes: [
        { id: 'a', type: 'fairness_evaluation', x: 0, y: 0 },
        { id: 'b', type: 'equity_evaluation', x: 0, y: 0 },
        { id: 'c', type: 'evaluation', evaluationType: 'equity', x: 0, y: 0 },
        { id: 'd', type: 'quality_evaluation', outputType: 'binary', x: 0, y: 0 },
      ],
    }))
    expect(wf.nodes.map(n => [n.type, n.evaluationType])).toEqual([
      ['evaluation', 'fairness'], ['evaluation', 'bias'], ['evaluation', 'bias'], ['evaluation', 'quality'],
    ])
    expect(wf.nodes[3]!.outputType).toBe('all')
  })
  it('opens an empty board it saved itself', () => {
    expect(readCanvasFile(canvasFileText(board())).nodes).toEqual([])
  })
})
