/**
 * usePageContext - Page-level context for Träshy chat assistant
 *
 * Provides current page state (form fields, active view, etc.)
 * so Träshy can give contextual help even before pipeline execution.
 *
 * Used via Vue provide/inject pattern:
 * - Views provide() their pageContext
 * - ChatOverlay inject() and prepends to messages
 */

import type { ComputedRef, InjectionKey } from 'vue'

/**
 * Content structure varies by view type
 */
export interface PageContent {
  // Text transformation fields
  inputText?: string
  contextPrompt?: string
  interceptionResult?: string
  optimizedPrompt?: string
  selectedCategory?: string | null
  selectedConfig?: string | null

  // Image transformation fields
  uploadedImage?: string | null

  // Image analysis result (persists for ongoing Trashy context)
  imageAnalysisResult?: string

  /**
   * What a measuring instrument on this page has PRODUCED, oldest first.
   *
   * The third kind of material. Without it the page said what it is and what
   * was typed into it, but never what came out, so Help could not answer a
   * question about a result standing right there. Pictures still travel as a
   * directory only (`surface_media`, then
   * `view_run` on request) because looking at one costs a vision call; text
   * costs nothing to read, so it travels whole. The SURFACE decides how many
   * entries it sends - a surface that grows without end would otherwise put its
   * whole history into every message.
   */
  instrumentRuns?: Array<{
    /** What this run was: the settings that distinguish it from its neighbours. */
    label: string
    text: string
  }>

  /**
   * The runs this surface is holding, as a directory: which run, under which
   * name. Help opens one only when it is asked to — same shape the chat sends
   * as `surface_media`. A surface that names its runs here overrides the one
   * run the chat session knows by itself.
   */
  surfaceMedia?: Array<{ runId: string; label: string }>

  // Canvas workflow fields
  workflowName?: string
  workflowNodes?: Array<{
    id: string
    type: string
    configId?: string
    llmModel?: string
  }>
  selectedNodeId?: string | null
  connectionCount?: number
}

/**
 * Position hint for Träshy floating assistant
 * Tells Träshy where to position itself based on current focus
 */
export interface FocusHint {
  /** Horizontal position as percentage of viewport (0-100) */
  x: number
  /** Vertical position as percentage of viewport (0-100) */
  y: number
  /** Which corner of Träshy should anchor to this position */
  anchor: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'
}

/** Default position: bottom-left corner, inside viewport */
export const DEFAULT_FOCUS_HINT: FocusHint = {
  x: 8,
  y: 95,
  anchor: 'bottom-left'
}

/**
 * One thing a page offers, held up by Träshy as a sign.
 *
 * The point is that the explanation does NOT stand in the page taking fixed
 * vertical room. Träshy already receives the interface reference and the page
 * context, so a page hands over at most a question, never an answer — there is
 * no second copy of the text to keep in step with the first.
 */
export interface PageOffer {
  /** What the sign says. Short: it is a sign, not a sentence. */
  label: string
  /**
   * Asked on the page's behalf when someone takes the sign. Optional, and left
   * out where nothing should be put into anybody's mouth: the sign then only
   * opens the conversation and the visitor writes their own.
   */
  question?: string
}

/**
 * Complete page context structure
 */
export interface PageContext {
  /** View type identifier (e.g., 'text_transformation', 'canvas_workflow') */
  activeViewType: string

  /**
   * What the page IS, in plain sentences, written from the view's own code.
   * The view type alone is a name, and a model given only a name fills the
   * rest in from nowhere — measured on /x2x-flow, which came back described
   * as a music page. It is also the only field that carries anything at all
   * before somebody has entered something.
   */
  pageDescription?: string

  /** Page-specific content */
  pageContent: PageContent

  /** Position hint for Träshy - where should the assistant float to? */
  focusHint?: FocusHint

  /** What Träshy holds up on this page, if anything. */
  offer?: PageOffer | null

  /**
   * This page keeps nothing, so nothing said about it may be attached to a run.
   * Träshy stops sending a run id, which is what puts a conversation into
   * exports/<run>/chat_history.json — and the id it would send is a leftover
   * from some earlier page anyway, since this one produces no run at all.
   */
  ephemeral?: boolean
}

/**
 * Format page context as a string for LLM consumption
 *
 * @param context - The page context object
 * @param routePath - Current route path as fallback
 * @returns Formatted context string
 */
export function formatPageContextForLLM(context: PageContext | null, routePath: string): string {
  if (!context) {
    return `[Kontext: Aktive Seite = ${routePath}]`
  }

  const parts: string[] = []
  parts.push(`Aktive Ansicht: ${context.activeViewType}`)
  if (context.pageDescription) {
    parts.push(`Was diese Seite ist: ${context.pageDescription}`)
  }

  const pc = context.pageContent
  if (pc) {
    // Text-related fields
    if (pc.inputText) {
      const truncated = pc.inputText.length > 200 ? pc.inputText.substring(0, 200) + '...' : pc.inputText
      parts.push(`Eingabe: "${truncated}"`)
    }
    if (pc.contextPrompt) {
      const truncated = pc.contextPrompt.length > 150 ? pc.contextPrompt.substring(0, 150) + '...' : pc.contextPrompt
      parts.push(`Kontext-Prompt: "${truncated}"`)
    }
    if (pc.interceptionResult) {
      const truncated = pc.interceptionResult.length > 150 ? pc.interceptionResult.substring(0, 150) + '...' : pc.interceptionResult
      parts.push(`Transformiert: "${truncated}"`)
    }
    if (pc.selectedCategory) {
      parts.push(`Kategorie: ${pc.selectedCategory}`)
    }
    if (pc.selectedConfig) {
      parts.push(`Modell/Config: ${pc.selectedConfig}`)
    }

    // Image analysis result
    if (pc.imageAnalysisResult) {
      const truncated = pc.imageAnalysisResult.length > 300 ? pc.imageAnalysisResult.substring(0, 300) + '...' : pc.imageAnalysisResult
      parts.push(`Bildanalyse: "${truncated}"`)
    }

    if (pc.instrumentRuns && pc.instrumentRuns.length > 0) {
      // Whole, not cut: these are the results being asked about, and a run
      // truncated at 200 characters answers no question about how it ends.
      parts.push('Was auf dieser Fläche entstanden ist:')
      for (const run of pc.instrumentRuns) {
        parts.push(`- ${run.label}: "${run.text}"`)
      }
    }

    // Image-related fields
    if (pc.uploadedImage) {
      parts.push(`Bild: ${pc.uploadedImage}`)
    }

    // Canvas-related fields
    if (pc.workflowName) {
      parts.push(`Workflow: "${pc.workflowName}"`)
    }
    if (pc.workflowNodes && pc.workflowNodes.length > 0) {
      const nodeTypes = pc.workflowNodes.map(n => n.type).join(', ')
      parts.push(`Canvas-Knoten (${pc.workflowNodes.length}): ${nodeTypes}`)
    }
    if (pc.selectedNodeId) {
      const selectedNode = pc.workflowNodes?.find(n => n.id === pc.selectedNodeId)
      if (selectedNode) {
        parts.push(`Ausgewählter Knoten: ${selectedNode.type}`)
      }
    }
    if (pc.connectionCount !== undefined) {
      parts.push(`Verbindungen: ${pc.connectionCount}`)
    }
  }

  return `[AKTUELLER KONTEXT]\n${parts.join('\n')}`
}
