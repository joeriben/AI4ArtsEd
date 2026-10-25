/**
 * A Canvas workflow as a file on somebody's disk.
 *
 * Until 2026-10-01 every export left as `New_Workflow.json` — the workflow had
 * no name anyone could give it, and `.json` is the extension of a thousand other
 * files in the same Downloads folder. A file nobody can tell apart from its
 * neighbours is a file nobody finds again.
 *
 * So the file has an extension of its own, `.atcanvas` (ATELIER Canvas; `.canvas`
 * is taken by the open JSON Canvas format that Obsidian opens), and a name made
 * of the workflow's name and the minute it was saved:
 *
 *   Perspektive-gegen-Rohtext_2026-10-01_1432.atcanvas
 *
 * The contents stay indented JSON, readable in any editor. What makes a file a
 * Canvas workflow is its `type: 'canvas_workflow'`, never its name: exports from
 * before 2026-10-01 are `.json`, and so are the apparatus Resona writes on the
 * server (services/canvas_graph_export.py); both open as they always did.
 */
import { getNodeTypeDefinition, type CanvasNode, type CanvasWorkflow, type StageType } from '@/types/canvas'
import { downloadBlob, fileDateParts, mediaFileName } from '@/lib/downloadMedia'

export const CANVAS_FILE_EXTENSION = 'atcanvas'
/** What the import dialog offers: the file of its own, and the exports before it. */
export const CANVAS_FILE_ACCEPT = `.${CANVAS_FILE_EXTENSION},.json`
/** Written into every file, so a later change of the format can be told apart. */
export const CANVAS_FILE_FORMAT_VERSION = 1

/**
 * The name the empty workflow carried until 2026-10-01. Nobody gave it, so it
 * is no name: a file saved with it still reads as unnamed.
 */
const LEGACY_DEFAULT_NAME = 'New Workflow'

/** The name somebody gave the workflow, or an empty string. */
export function givenName(workflow: Pick<CanvasWorkflow, 'name'> | null | undefined): string {
  const name = (workflow?.name || '').trim()
  return name === LEGACY_DEFAULT_NAME ? '' : name
}

/** The prompt typed into the workflow's first input node that has one. */
export function canvasPrompt(workflow: Pick<CanvasWorkflow, 'nodes'> | null | undefined): string {
  const input = (workflow?.nodes || []).find(
    (n: CanvasNode) => n.type === 'input' && (n.promptText || '').trim(),
  )
  return (input?.promptText || '').trim()
}

/** The output configs the workflow's generation nodes run, each once. */
export function canvasModels(workflow: Pick<CanvasWorkflow, 'nodes'> | null | undefined): string[] {
  const ids = (workflow?.nodes || [])
    .filter((n: CanvasNode) => n.type === 'generation' && n.configId)
    .map((n: CanvasNode) => n.configId as string)
  return [...new Set(ids)]
}

/**
 * The words a file of this workflow starts with: its name; where it has none,
 * the prompt it begins with; where it has none of that either, the models it
 * generates with. `canvas` only for a board with nothing on it.
 */
export function canvasFileStem(workflow: CanvasWorkflow | null | undefined): string {
  return givenName(workflow) || canvasPrompt(workflow) || canvasModels(workflow).join(' ') || 'canvas'
}

export function canvasFileName(workflow: CanvasWorkflow, when: Date | number = new Date()): string {
  return mediaFileName(canvasFileStem(workflow), fileDateParts(when), CANVAS_FILE_EXTENSION)
}

/** The file's contents. */
export function canvasFileText(workflow: CanvasWorkflow): string {
  return JSON.stringify({ ...workflow, formatVersion: CANVAS_FILE_FORMAT_VERSION }, null, 2)
}

/**
 * Save the workflow to the disk. Handed over as raw bytes rather than as JSON:
 * Safari adds the extension it associates with a MIME type to a name whose own
 * extension it does not know, and the file would arrive as `….atcanvas.json`.
 *
 * @returns the cause where it failed, an empty string where it reached the disk.
 */
export function saveCanvasFile(workflow: CanvasWorkflow, when: Date | number = new Date()): string {
  const blob = new Blob([canvasFileText(workflow)], { type: 'application/octet-stream' })
  return downloadBlob(blob, canvasFileName(workflow, when))
}

/** A file that does not hold a Canvas workflow. */
export class NotACanvasFile extends Error {}

/**
 * The evaluation nodes of January 2026, under the node that replaced them. On
 * 2026-01-25 five evaluation types became one `evaluation` node with an
 * `evaluationType` (7e649d5c), and on 2026-01-28 the type `equity` was renamed
 * `bias` (27f04f7d). The forks and the loop controller of those days have no
 * node any more; a file that holds one is refused.
 */
const LEGACY_EVALUATIONS: Record<string, string> = {
  fairness_evaluation: 'fairness',
  creativity_evaluation: 'creativity',
  equity_evaluation: 'bias',
  quality_evaluation: 'quality',
  custom_evaluation: 'custom',
}

function migratedNode(node: unknown): unknown {
  if (!node || typeof node !== 'object') return node
  let n = node as Record<string, unknown>
  const kind = typeof n.type === 'string' ? LEGACY_EVALUATIONS[n.type] : undefined
  if (kind) n = { ...n, type: 'evaluation', evaluationType: kind }
  if (n.type !== 'evaluation') return n
  if (n.evaluationType === 'equity') n = { ...n, evaluationType: 'bias' }
  // The yes/no output of those days. The node decides pass or fail by a score
  // now (services/canvas_executor.py), and asks for one only under `score` or
  // `all`; under the old value it never asked, and every run took `fail`.
  if (n.outputType === 'binary') n = { ...n, outputType: 'all' }
  return n
}

/**
 * A workflow out of what a file or the server holds.
 *
 * Accepted: a node list in which every node has an id and a type the Canvas
 * draws (`NODE_TYPE_DEFINITIONS`), with a connection list or none. That is a
 * saved workflow, an export from before 2026-10-01, a Resona apparatus, and the
 * bare graph a run records in its `workflow.json`. An empty node list only where
 * the file says it is a Canvas workflow. Everything else is refused here, before
 * it reaches the board: `loadWorkflow` takes what it is given, and a JSON file of
 * another kind (an Obsidian `.canvas`, a React Flow export) left a Canvas that
 * could not draw itself.
 */
export function toCanvasWorkflow(data: unknown): CanvasWorkflow {
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new NotACanvasFile()
  const raw = data as Record<string, unknown>
  if (!Array.isArray(raw.nodes)) throw new NotACanvasFile()
  const nodes = raw.nodes.map(migratedNode)
  const isNode = (n: unknown) => {
    if (!n || typeof n !== 'object') return false
    const { id, type } = n as Record<string, unknown>
    return typeof id === 'string' && !!id && typeof type === 'string' &&
      !!getNodeTypeDefinition(type as StageType)
  }
  if (!nodes.every(isNode)) throw new NotACanvasFile()
  if (!nodes.length && raw.type !== 'canvas_workflow') throw new NotACanvasFile()
  if (raw.connections !== undefined && !Array.isArray(raw.connections)) throw new NotACanvasFile()
  // The file's own version marker stays behind: the board holds the workflow,
  // and the marker is written afresh with every save.
  const { formatVersion: _version, ...rest } = raw
  return {
    ...rest,
    id: typeof raw.id === 'string' && raw.id ? raw.id : `workflow_${Date.now()}`,
    name: typeof raw.name === 'string' ? raw.name : '',
    type: 'canvas_workflow',
    nodes: nodes as CanvasNode[],
    connections: (raw.connections as CanvasWorkflow['connections']) || [],
  } as CanvasWorkflow
}

/** The text of a file, read as a workflow. */
export function readCanvasFile(text: string): CanvasWorkflow {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch {
    throw new NotACanvasFile()
  }
  return toCanvasWorkflow(data)
}
