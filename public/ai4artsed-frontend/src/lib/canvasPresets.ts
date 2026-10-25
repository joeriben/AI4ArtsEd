/**
 * The ready-made Canvas workflows: what "New" offers on the ring
 * (components/canvas/CanvasPresetOverlay.vue), and how one of them becomes the
 * board.
 *
 * Two kinds. The BASIC FORMS are the Flow's own paths laid out as nodes —
 * prompt, interception, adaption, translation, generation — so the Canvas begins where the
 * Flow is. The EXPLORATIONS follow instruments of the Latent Lab and of Compare
 * (Language Model Comparison, Interception Scope, Image Understanding, Model
 * Comparison) and the chain game Telephone ("Stille Post"), each an example of
 * what the Canvas can set up that a straight line cannot.
 *
 * A preset is a `.atcanvas` file in devserver/schemas/canvas_presets, served by
 * `GET /api/canvas/presets` and read through the same reader the import uses
 * (`toCanvasWorkflow`). Its `preset` block says where it hangs and what it is
 * called; the names are i18n keys, and the Latent Lab's own names are used
 * where a preset follows one of its instruments.
 *
 * Opening one makes a COPY: the board gets a fresh id, the preset's name in
 * the reader's language, and `presetId`, which every file saved from it
 * carries. What the file names by reference is resolved at that moment against
 * what this installation holds:
 *
 * - `promptPreset` on an input node: a sentence of the platform's example list
 *   (`promptExamples.presets`), in the reader's language.
 * - `interceptionPreset`: the lens's CURRENT wording (lib/lensContext.ts), never
 *   a copy frozen into the file. A lens whose wording does not arrive stops the
 *   opening: its node would pass the prompt on unchanged under the lens's name.
 * - `lineup: [id, place]`: the model at that place among the lineup's models
 *   this installation has (`lineupMembers`), as the Latent Lab lines them up: a
 *   member the installation lacks is left out, the ones after it move up, and
 *   a place past the last stays without a model. The board's own check names
 *   what is missing — a comparison short of a model is better than one with a
 *   stand-in, and every node is titled by the model it actually got. A lineup
 *   that reaches no model at all (or whose register did not answer) stops the
 *   opening: a comparison of nothing would stand as a board with no cause named.
 * - `llmModel` / `visionModel`: kept where the installation offers them, else
 *   left empty for the same reason; a node naming none gets the default.
 * - `titleKey` / `titleArgs`: the node's title in the reader's language; an
 *   argument `{modelOf | visionOf | lensOf: nodeId}` is the name of what that
 *   node resolved to.
 *
 * Those fields are the preset file's own and do not reach the board. That the
 * names in the files exist is tests/test_canvas_presets.py's (devserver) and
 * lib/__tests__/canvasPresets.spec.ts's.
 */
import i18n, { SUPPORTED_LANGUAGES, type SupportedLanguage } from '@/i18n'
import {
  INTERCEPTION_PRESETS,
  generateNodeId,
  type CanvasNode,
  type CanvasWorkflow,
  type InterceptionPreset,
  type LLMModelSummary,
} from '@/types/canvas'
import { toCanvasWorkflow } from '@/lib/canvasFile'
import { nodeDefaults } from '@/lib/canvasNodeDefaults'
import { PROMPT_PRESET_KEY } from '@/lib/promptPresets'

export type PresetKind = 'basic' | 'explore'
/** What a preset's run yields — what its disc shows when it has no picture. */
export type PresetMedium = 'image' | 'video' | 'sound' | 'text'

export interface CanvasPresetInfo {
  id: string
  kind: PresetKind
  order: number
  medium: PresetMedium
  /** i18n key of its name. */
  name: string
  /** i18n key of what it does, shown under a resting pointer. */
  description: string
}

export interface CanvasPreset {
  info: CanvasPresetInfo
  /** The workflow as the file has it, the preset's own node fields included. */
  workflow: CanvasWorkflow
}

/** The fields a preset file may put on a node, resolved when it is opened. */
type TitleArg = number | string | { modelOf?: string; visionOf?: string; lensOf?: string }
interface PresetNodeFields {
  promptPreset?: string
  lineup?: [string, number]
  titleKey?: string
  titleArgs?: Record<string, TitleArg>
}
type PresetNode = CanvasNode & PresetNodeFields

const KINDS: PresetKind[] = ['basic', 'explore']
const MEDIA: PresetMedium[] = ['image', 'video', 'sound', 'text']

/** Where the picture a preset's disc wears is served. */
export function presetPicture(info: CanvasPresetInfo): string {
  return info.medium === 'image' ? `/canvas-presets/${info.id}.webp` : ''
}

function asInfo(raw: unknown): CanvasPresetInfo | null {
  if (!raw || typeof raw !== 'object') return null
  const p = raw as Record<string, unknown>
  if (typeof p.id !== 'string' || !p.id) return null
  if (!KINDS.includes(p.kind as PresetKind) || !MEDIA.includes(p.medium as PresetMedium)) return null
  if (typeof p.name !== 'string' || typeof p.description !== 'string') return null
  return {
    id: p.id,
    kind: p.kind as PresetKind,
    order: typeof p.order === 'number' ? p.order : 0,
    medium: p.medium as PresetMedium,
    name: p.name,
    description: p.description,
  }
}

/**
 * The presets as the server holds them, basic forms first, each kind in its
 * order. One the reader cannot take is left out and named in the console; the
 * others are still worth offering.
 */
export async function fetchCanvasPresets(): Promise<CanvasPreset[]> {
  const response = await fetch('/api/canvas/presets')
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  const data = await response.json()
  const presets: CanvasPreset[] = []
  for (const raw of (data.presets || []) as unknown[]) {
    const info = asInfo((raw as Record<string, unknown> | null)?.preset)
    if (!info) {
      console.error('[Canvas] A preset without a readable preset block was left out:', raw)
      continue
    }
    try {
      presets.push({ info, workflow: toCanvasWorkflow(raw) })
    } catch (err) {
      console.error(`[Canvas] The preset '${info.id}' is not a Canvas workflow and was left out:`, err)
    }
  }
  return presets.sort((a, b) =>
    KINDS.indexOf(a.info.kind) - KINDS.indexOf(b.info.kind) || a.info.order - b.info.order)
}

/** What opening a preset needs to know about this installation and reader. */
export interface PresetContext {
  llmModels: readonly LLMModelSummary[]
  visionModels: readonly LLMModelSummary[]
  /** The model ids a lineup reaches here, in its order (`lineupMembers`). */
  lineupMembers: (lineupId: string) => string[]
  /** A lens's current wording in the reader's language (`lensContext`). */
  lensContext: (lensId: string) => Promise<string>
  t: (key: string, args?: Record<string, unknown>) => string
  locale: string
}

/** The name a model is shown by on a card: the register's name, without its service. */
function modelName(id: string | undefined): string {
  return (id || '').split('/').pop() || ''
}

function offered(id: string | undefined, models: readonly LLMModelSummary[]): string {
  return id && models.some(m => m.id === id) ? id : ''
}

/**
 * The preset as a board of its own. Nothing of the preset is changed: the
 * nodes are copied, and what the file names by reference is resolved here.
 */
export async function openPreset(preset: CanvasPreset, ctx: PresetContext): Promise<CanvasWorkflow> {
  const source = JSON.parse(JSON.stringify(preset.workflow)) as CanvasWorkflow & { preset?: unknown }
  const raw = source.nodes as PresetNode[]
  const defaultVision = (ctx.visionModels.find(m => m.isDefault) || ctx.visionModels[0])?.id || ''

  const nodes: CanvasNode[] = []
  for (const original of raw) {
    const { promptPreset, lineup, titleKey: _titleKey, titleArgs: _titleArgs, ...rest } = original
    const node: CanvasNode = { ...nodeDefaults(rest.type, ctx.llmModels), ...rest }

    if (promptPreset) node.promptText = ctx.t(`${PROMPT_PRESET_KEY}.${promptPreset}`)

    if (lineup) {
      const members = ctx.lineupMembers(lineup[0])
      if (!members.length) throw new Error(`the lineup '${lineup[0]}' reaches no model here`)
      node.llmModel = offered(members[lineup[1]], ctx.llmModels)
    } else if ('llmModel' in rest) {
      node.llmModel = offered(rest.llmModel, ctx.llmModels)
    }

    if (node.type === 'image_evaluation') {
      node.visionModel = 'visionModel' in rest ? offered(rest.visionModel, ctx.visionModels) : defaultVision
    }

    if (node.type === 'interception' && node.interceptionPreset && node.interceptionPreset !== 'user_defined') {
      node.contextPrompt = await ctx.lensContext(node.interceptionPreset)
      if (!node.contextPrompt.trim()) {
        throw new Error(`the perspective '${node.interceptionPreset}' has no wording to load`)
      }
    }
    nodes.push(node)
  }

  // Titles last: an argument names what ANOTHER node resolved to.
  const byId = new Map(nodes.map(n => [n.id, n]))
  for (const original of raw) {
    if (!original.titleKey) continue
    const args: Record<string, unknown> = {}
    let complete = true
    for (const [key, value] of Object.entries(original.titleArgs || {})) {
      if (typeof value !== 'object' || value === null) {
        args[key] = value
        continue
      }
      let word = ''
      if (value.modelOf) word = modelName(byId.get(value.modelOf)?.llmModel)
      else if (value.visionOf) word = modelName(byId.get(value.visionOf)?.visionModel)
      else if (value.lensOf) {
        const lens = byId.get(value.lensOf)?.interceptionPreset as InterceptionPreset | undefined
        word = lens && INTERCEPTION_PRESETS[lens]
          ? i18n.global.t(INTERCEPTION_PRESETS[lens].labelKey, {}, { locale: ctx.locale as SupportedLanguage })
          : ''
      }
      if (!word) complete = false
      args[key] = word
    }
    // A title whose model is missing would name nothing; the node keeps its type.
    const node = byId.get(original.id)
    if (node && complete) node.title = ctx.t(original.titleKey, args)
  }

  // Ids of the board's own kind. The file's ids are readable names
  // ('generation_1'), and every preset uses the same few: the cards of a run
  // stay in the drawer when another board is opened, and are labelled by the
  // node of that id, so a reused id would put the next preset's title on them.
  const ids = new Map(nodes.map(n => [n.id, generateNodeId(n.type)]))
  for (const node of nodes) node.id = ids.get(node.id) ?? node.id
  const connections = (source.connections || []).map(c => ({
    ...c,
    sourceId: ids.get(c.sourceId) ?? c.sourceId,
    targetId: ids.get(c.targetId) ?? c.targetId,
  }))

  const { preset: _preset, updatedAt: _updated, ...workflow } = source
  return {
    ...workflow,
    id: `workflow_${Date.now()}`,
    name: ctx.t(preset.info.name),
    presetId: preset.info.id,
    nodes,
    connections,
    createdAt: new Date().toISOString(),
  }
}

/**
 * The board as far as "does it hold work" is concerned: what the nodes say and
 * how they are joined, and the name. Where a node stands and how large it is
 * are left out — moving the pieces of a preset around is looking at it, not
 * work anybody would lose.
 */
export function presetFingerprint(workflow: Pick<CanvasWorkflow, 'name' | 'nodes' | 'connections'>): string {
  const nodes = workflow.nodes.map(({ x: _x, y: _y, width: _w, height: _h, ...rest }) => rest)
  return JSON.stringify({ name: workflow.name, nodes, connections: workflow.connections })
}

/**
 * Every name a preset carries, in every language the platform speaks, folded
 * for comparison. The star keeps a workflow under its name, and a kept
 * workflow called "Telephone" would stand in the favourites beside the preset
 * of that name, indistinguishable from it — in any language somebody might
 * later read it in. The same rule refuses a kept perspective the name of a
 * given one.
 */
export function presetNames(infos: readonly CanvasPresetInfo[]): Set<string> {
  const names = new Set<string>()
  for (const info of infos) {
    for (const { code } of SUPPORTED_LANGUAGES) {
      const name = i18n.global.t(info.name, {}, { locale: code })
      if (name && name !== info.name) names.add(foldName(name))
    }
  }
  return names
}

/** A name as the comparison reads it: trimmed, case and width folded. */
export function foldName(name: string): string {
  return name.normalize('NFKC').trim().toLocaleLowerCase()
}
