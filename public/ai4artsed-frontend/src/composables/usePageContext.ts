/**
 * usePageContext - Page-level context for Träshy chat assistant
 *
 * Session 133: Provides current page state (form fields, active view, etc.)
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
 * Complete page context structure
 */
export interface PageContext {
  /** View type identifier (e.g., 'text_transformation', 'canvas_workflow') */
  activeViewType: string

  /** Page-specific content */
  pageContent: PageContent

  /** Position hint for Träshy - where should the assistant float to? */
  focusHint?: FocusHint
}

/**
 * Injection key for type-safe provide/inject
 */
export const PAGE_CONTEXT_KEY: InjectionKey<ComputedRef<PageContext>> = Symbol('pageContext')

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
