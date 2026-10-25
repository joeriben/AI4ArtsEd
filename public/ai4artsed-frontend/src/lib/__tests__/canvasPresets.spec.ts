/**
 * The ready-made Canvas workflows (lib/canvasPresets.ts): every name a preset
 * file carries has its words in en.ts, and opening one makes a board of its
 * own — names resolved for this reader and this installation, the file's own
 * fields gone, nothing of the preset changed.
 *
 * What the files name on the server side (lenses, output configs, lineups,
 * frames, the cap on executions) is devserver/tests/test_canvas_presets.py's.
 */
import { beforeAll, describe, expect, it } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import i18n from '@/i18n'
import { toCanvasWorkflow } from '@/lib/canvasFile'
import {
  foldName,
  openPreset,
  presetFingerprint,
  presetNames,
  presetPicture,
  type CanvasPreset,
  type CanvasPresetInfo,
  type PresetContext,
} from '@/lib/canvasPresets'
import { PROMPT_PRESETS, PROMPT_PRESET_KEY } from '@/lib/promptPresets'
import { INTERCEPTION_PRESETS, type CanvasWorkflow } from '@/types/canvas'

const HERE = dirname(fileURLToPath(import.meta.url))
const DIR = resolve(HERE, '../../../../../devserver/schemas/canvas_presets')

type Raw = CanvasWorkflow & { preset: CanvasPresetInfo }
const FILES: Raw[] = readdirSync(DIR)
  .filter(f => f.endsWith('.atcanvas'))
  .map(f => JSON.parse(readFileSync(resolve(DIR, f), 'utf8')))

const te = (key: string) => i18n.global.te(key, 'en')

// The words below are read in English: a translation of a preset's name
// arriving in de.ts must not change what these tests assert.
beforeAll(() => {
  i18n.global.locale.value = 'en'
})

function asPreset(raw: Raw): CanvasPreset {
  return { info: raw.preset, workflow: toCanvasWorkflow(raw) }
}

function ctx(over: Partial<PresetContext> = {}): PresetContext {
  return {
    llmModels: [
      { id: 'mammouth/glm-5.3', name: 'glm-5.3', provider: 'mammouth', isDefault: true },
      { id: 'mammouth/mistral-large-3', name: 'mistral-large-3', provider: 'mammouth' },
      { id: 'mammouth/deepseek-v4-pro', name: 'deepseek-v4-pro', provider: 'mammouth' },
      { id: 'mammouth/kimi-k3', name: 'kimi-k3', provider: 'mammouth' },
    ],
    visionModels: [
      { id: 'local/qwen3-vl:32b', name: 'qwen3-vl:32b', provider: 'local', isDefault: true },
      { id: 'local/qwen3-vl:8b', name: 'qwen3-vl:8b', provider: 'local' },
      { id: 'local/qwen3-vl:4b', name: 'qwen3-vl:4b', provider: 'local' },
    ],
    lineupMembers: (id) => (id === 'openWeights'
      ? ['mammouth/mistral-large-3', 'mammouth/deepseek-v4-pro', 'mammouth/glm-5.3', 'mammouth/kimi-k3']
      : []),
    lensContext: async (id) => `LENS[${id}]`,
    t: (key, args) => (args ? i18n.global.t(key, args) : i18n.global.t(key)),
    locale: 'en',
    ...over,
  }
}

function byFile(id: string): CanvasPreset {
  const raw = FILES.find(f => f.preset.id === id)
  if (!raw) throw new Error(`no preset ${id}`)
  return asPreset(raw)
}

describe('the preset files', () => {
  it('are there, basic forms and explorations', () => {
    expect(FILES.some(f => f.preset.kind === 'basic')).toBe(true)
    expect(FILES.some(f => f.preset.kind === 'explore')).toBe(true)
  })

  for (const raw of FILES) {
    describe(raw.preset.id, () => {
      it('has its name and description in en.ts', () => {
        expect(te(raw.preset.name), raw.preset.name).toBe(true)
        expect(te(raw.preset.description), raw.preset.description).toBe(true)
      })
      it('names titles, prompts and lenses that exist', () => {
        for (const node of raw.nodes as Array<Record<string, any>>) {
          if (node.titleKey) expect(te(node.titleKey), node.titleKey).toBe(true)
          if (node.promptPreset) {
            expect(PROMPT_PRESETS as readonly string[]).toContain(node.promptPreset)
            expect(te(`${PROMPT_PRESET_KEY}.${node.promptPreset}`)).toBe(true)
          }
          if (node.interceptionPreset) expect(Object.keys(INTERCEPTION_PRESETS)).toContain(node.interceptionPreset)
        }
      })
      it('is read by the import reader', () => {
        expect(() => toCanvasWorkflow(raw)).not.toThrow()
      })
    })
  }

  it('the kinds and the ring have their words', () => {
    for (const key of ['kinds.basic', 'kinds.explore', 'empty', 'emptyDescription', 'loading', 'unavailable', 'openError']) {
      expect(te(`canvas.presets.${key}`), key).toBe(true)
    }
    expect(te('canvas.keepPresetName')).toBe(true)
  })
})

describe('openPreset', () => {
  it("makes a copy named by the preset, with fresh ids and nothing of the file's own fields", async () => {
    const preset = byFile('telephone')
    const before = JSON.stringify(preset.workflow)
    const board = await openPreset(preset, ctx())
    expect(JSON.stringify(preset.workflow)).toBe(before)
    expect(board.name).toBe('Telephone')
    expect(board.presetId).toBe('telephone')
    expect(board.id).not.toBe(preset.workflow.id)
    expect((board as unknown as Record<string, unknown>).preset).toBeUndefined()
    const ids = new Set(board.nodes.map(n => n.id))
    expect(ids.size).toBe(board.nodes.length)
    for (const n of board.nodes) {
      expect(preset.workflow.nodes.some(o => o.id === n.id)).toBe(false)
      for (const field of ['promptPreset', 'lineup', 'titleKey', 'titleArgs']) {
        expect(n as unknown as Record<string, unknown>).not.toHaveProperty(field)
      }
    }
    for (const c of board.connections) {
      expect(ids.has(c.sourceId) && ids.has(c.targetId)).toBe(true)
    }
    expect(board.connections.length).toBe(preset.workflow.connections.length)
  })

  it('fills the prompt, the titles and the default reader', async () => {
    const board = await openPreset(byFile('telephone'), ctx())
    const input = board.nodes.find(n => n.type === 'input')!
    expect(input.promptText).toBe(i18n.global.t(`${PROMPT_PRESET_KEY}.house`))
    expect(input.title).toBe('Prompt')
    const titles = board.nodes.map(n => n.title)
    expect(titles).toContain('Link 1 · Image')
    expect(titles).toContain('Link 6 · Reading')
    for (const n of board.nodes.filter(n => n.type === 'image_evaluation')) {
      expect(n.visionModel).toBe('local/qwen3-vl:32b')
      expect(n.imageEvaluationPreset).toBe('descriptive')
    }
  })

  it('takes the lineup in its order and the lens text as it is now', async () => {
    const board = await openPreset(byFile('language_models'), ctx())
    const writers = board.nodes.filter(n => n.type === 'interception')
    expect(writers.map(n => n.llmModel)).toEqual([
      'mammouth/mistral-large-3', 'mammouth/deepseek-v4-pro', 'mammouth/glm-5.3', 'mammouth/kimi-k3',
    ])
    expect(writers.map(n => n.title)).toEqual(['mistral-large-3', 'deepseek-v4-pro', 'glm-5.3', 'kimi-k3'])
    for (const n of writers) expect(n.contextPrompt).toBe('LENS[theopposite]')
    const reference = board.nodes.find(n => n.type === 'generation' && n.title === i18n.global.t('latentLab.interception.models.asWritten'))
    expect(reference).toBeDefined()
  })

  it('leaves a model the installation lacks empty, and its title off', async () => {
    const board = await openPreset(byFile('language_models'), ctx({
      lineupMembers: () => ['mammouth/mistral-large-3'],
    }))
    const writers = board.nodes.filter(n => n.type === 'interception')
    expect(writers[0]!.llmModel).toBe('mammouth/mistral-large-3')
    expect(writers.slice(1).every(n => n.llmModel === '' && !n.title)).toBe(true)
  })

  it('keeps a named reader only where it is offered', async () => {
    const board = await openPreset(byFile('image_understanding'), ctx())
    const readers = board.nodes.filter(n => n.type === 'image_evaluation')
    expect(readers.map(n => n.visionModel)).toEqual(['local/qwen3-vl:8b', 'local/qwen3-vl:4b', ''])
    expect(readers.map(n => n.title)).toEqual(['qwen3-vl:8b', 'qwen3-vl:4b', undefined])
  })

  it('names the perspectives of Interception Scope by the Canvas list', async () => {
    const board = await openPreset(byFile('perspectives'), ctx())
    const lenses = board.nodes.filter(n => n.type === 'interception')
    expect(lenses.map(n => n.title)).toEqual(
      lenses.map(n => i18n.global.t(INTERCEPTION_PRESETS[n.interceptionPreset!].labelKey, {}, { locale: 'en' })),
    )
  })

  it('gives a basic form the default writer and no perspective', async () => {
    const board = await openPreset(byFile('text_to_image'), ctx())
    const writer = board.nodes.find(n => n.type === 'interception')!
    expect(writer.llmModel).toBe('mammouth/glm-5.3')
    expect(writer.interceptionPreset).toBeUndefined()
    expect(writer.contextPrompt).toBeUndefined()
  })

  it('translates before every generation, as the Flow does in Stage 3', async () => {
    for (const raw of FILES) {
      const board = await openPreset(asPreset(raw), ctx())
      const types = new Map(board.nodes.map(n => [n.id, n.type]))
      for (const c of board.connections) {
        if (types.get(c.targetId) !== 'generation' || c.label === 'params') continue
        expect(types.get(c.sourceId), `${raw.preset.id}: ${c.sourceId} -> ${c.targetId}`).toBe('translation')
      }
      for (const n of board.nodes.filter(n => n.type === 'translation')) {
        expect(n.llmModel).toBe('mammouth/glm-5.3')
      }
    }
  })

  it('does not open on a lineup that reaches no model', async () => {
    await expect(openPreset(byFile('language_models'), ctx({ lineupMembers: () => [] })))
      .rejects.toThrow(/reaches no model/)
  })

  it('does not open on a perspective whose wording did not arrive', async () => {
    await expect(openPreset(byFile('perspectives'), ctx({ lensContext: async () => '' })))
      .rejects.toThrow(/has no wording/)
  })
})

describe('presetFingerprint', () => {
  it('ignores where the pieces stand, not what they say', async () => {
    const board = await openPreset(byFile('text_to_image'), ctx())
    const moved = { ...board, nodes: board.nodes.map(n => ({ ...n, x: n.x + 40, y: n.y - 7, width: 300 })) }
    expect(presetFingerprint(moved)).toBe(presetFingerprint(board))
    const changed = { ...board, nodes: board.nodes.map(n => (n.type === 'input' ? { ...n, promptText: 'x' } : n)) }
    expect(presetFingerprint(changed)).not.toBe(presetFingerprint(board))
  })
})

describe('presetNames', () => {
  it('holds every preset name, folded', () => {
    const names = presetNames(FILES.map(f => f.preset))
    expect(names.has(foldName('Telephone'))).toBe(true)
    expect(names.has(foldName(' TELEPHONE '))).toBe(true)
    expect(names.has(foldName('My own chain'))).toBe(false)
  })
})

describe('presetPicture', () => {
  it('is the served picture for a picture preset and nothing otherwise', () => {
    expect(presetPicture(byFile('telephone').info)).toBe('/canvas-presets/telephone.webp')
    expect(presetPicture(byFile('text_to_video').info)).toBe('')
  })
})
