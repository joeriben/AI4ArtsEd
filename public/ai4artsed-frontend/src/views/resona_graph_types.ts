// Shared types for Resona's apparatus cards (graph runs).
//
// Resona (the workshop companion chat persona) now authors Canvas workflow
// graphs. Each is executed via /api/canvas/execute-stream and rendered as an
// "apparatus card". This box is the reactive state one card owns; it lives in
// resona.vue and is passed to ResonaGraphCard.vue. Kept in its own module so
// both can import the type without a circular view↔component import.

/** Executor-ready workflow graph as authored by Resona. */
export interface GraphWorkflow {
  nodes: Array<Record<string, unknown>>
  connections: Array<Record<string, unknown>>
}

/** One node's line in the live progress list while the apparatus runs. */
export interface GraphProgressRow {
  nodeId: string
  nodeType: string
  message?: string
  /** node_complete image preview (thumbnail shown inline). */
  previewUrl?: string
  /** node_complete text preview. */
  previewText?: string
}

/** Metadata carried by a completed generation node's result. */
export interface GraphResultMeta {
  config_id?: string
  display_name?: string
  seed?: number | null
  steps?: number | null
  cfg?: number | null
}

/**
 * One pedagogically relevant output extracted from complete.results:
 * generation → image/media (url + meta); evaluation/comparison/interception →
 * text. seed/resolution/quality/input/collector/display are ignored.
 */
export interface GraphResultItem {
  nodeId: string
  nodeType: string
  kind: 'image' | 'text' | 'media'
  url?: string
  text?: string
  meta?: GraphResultMeta
}

/** One finished output recovered from a torn run's persisted final/ folder
 * (GET /api/canvas/partial/<run_id>). Only images are recovered today. */
export interface GraphRecoveredItem {
  kind: 'image'
  url: string
  index: number
  nodeLabel?: string
}

/** Reactive state for a single apparatus card. */
export interface GraphRunBox {
  id: string
  intentId: string | null
  title: string
  motivation: string | null
  summary: string
  workflow: GraphWorkflow
  // running  → live; complete → finished cleanly; error → hard failure;
  // partial  → the live stream tore (server restart) but some finished pieces
  //            were recovered from disk via the partial endpoint.
  status: 'running' | 'complete' | 'error' | 'partial'
  progress: GraphProgressRow[]
  results: GraphResultItem[]
  error?: string
  /** Canvas run id. Set EARLY from the run_started event (before any node), so
   * a torn stream can reconnect / recover by run_id; also confirmed by complete. */
  runId?: string
  /** Highest SSE event index seen, for lossless reconnect (?after=<n>). */
  lastEventIndex: number
  /** Images recovered from disk after a tear (partial state). */
  recovered?: GraphRecoveredItem[]
  /** Count of generations that never landed (partial state). */
  recoveredPending?: number
  startedAt: number
  finishedAt?: number
}
