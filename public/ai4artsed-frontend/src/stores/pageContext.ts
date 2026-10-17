import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { PageContext, PageContent, FocusHint, PageOffer } from '@/composables/usePageContext'
import { DEFAULT_FOCUS_HINT, formatPageContextForLLM } from '@/composables/usePageContext'

/**
 * Pinia Store for Page Context
 *
 * Provides current page state for Träshy chat assistant
 * Replaces provide/inject pattern to work across component tree siblings
 *
 * Views call setPageContext() to update their state
 * ChatOverlay reads the store to get positioning and context info
 */
export const usePageContextStore = defineStore('pageContext', () => {
  // ============================================================================
  // STATE
  // ============================================================================

  /** Current view type (e.g., 'text_transformation', 'canvas_workflow') */
  const activeViewType = ref<string>('')

  /** What the current page is (see PageContext.pageDescription). */
  const pageDescription = ref<string>('')

  /** Page-specific content */
  const pageContent = ref<PageContent>({})

  /** Position hint for Träshy floating assistant */
  const focusHint = ref<FocusHint>(DEFAULT_FOCUS_HINT)

  /** What Träshy holds up on this page. Null on pages that offer nothing. */
  const offer = ref<PageOffer | null>(null)

  /** True on a page that keeps nothing; see PageContext.ephemeral. */
  const ephemeral = ref(false)

  // ============================================================================
  // COMPUTED
  // ============================================================================

  /** Full page context object */
  const context = computed<PageContext | null>(() => {
    if (!activeViewType.value) return null
    return {
      activeViewType: activeViewType.value,
      pageDescription: pageDescription.value,
      pageContent: pageContent.value,
      focusHint: focusHint.value,
      offer: offer.value,
      ephemeral: ephemeral.value
    }
  })

  /** Current focus hint (with default fallback) */
  const currentFocusHint = computed(() => focusHint.value || DEFAULT_FOCUS_HINT)

  // ============================================================================
  // ACTIONS
  // ============================================================================

  /**
   * Set the complete page context (called by views)
   */
  function setPageContext(ctx: PageContext) {
    activeViewType.value = ctx.activeViewType
    pageDescription.value = ctx.pageDescription || ''
    pageContent.value = ctx.pageContent
    focusHint.value = ctx.focusHint || DEFAULT_FOCUS_HINT
    // Explicitly reset when absent: a page that offers nothing must not inherit
    // the previous page's sign.
    offer.value = ctx.offer ?? null
    ephemeral.value = ctx.ephemeral === true
  }

  /**
   * Update only the focus hint (for dynamic positioning)
   */
  function setFocusHint(hint: FocusHint) {
    focusHint.value = hint
  }

  /**
   * Clear context (when leaving a view)
   */
  function clearContext() {
    activeViewType.value = ''
    pageDescription.value = ''
    pageContent.value = {}
    focusHint.value = DEFAULT_FOCUS_HINT
    offer.value = null
    ephemeral.value = false
  }

  /**
   * Format context for LLM consumption
   */
  function formatForLLM(routePath: string): string {
    return formatPageContextForLLM(context.value, routePath)
  }

  // ============================================================================
  // RETURN
  // ============================================================================

  return {
    // State
    activeViewType,
    pageDescription,
    pageContent,
    focusHint,
    offer,
    ephemeral,

    // Computed
    context,
    currentFocusHint,

    // Actions
    setPageContext,
    setFocusHint,
    clearContext,
    formatForLLM
  }
})
