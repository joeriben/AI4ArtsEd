import { ref, computed, onMounted, onUnmounted, type Ref } from 'vue'

/**
 * Canvas rendering context with helpers
 */
export interface RenderContext {
  ctx: CanvasRenderingContext2D
  canvas: HTMLCanvasElement
  width: number
  height: number
  clear: () => void
}

/**
 * Options for Canvas renderer
 */
export interface CanvasRendererOptions {
  width?: Ref<number>
  height?: Ref<number>
  dpr?: number  // Device pixel ratio (default: window.devicePixelRatio)
}

/**
 * Shared Canvas renderer composable
 *
 * Handles:
 * - Canvas element management
 * - Auto-resize with debouncing
 * - Device pixel ratio (retina display support)
 * - Pointer event coordinate conversion
 *
 * Based on patterns from IcebergAnimation.vue
 *
 * @example
 * ```typescript
 * const containerRef = ref<HTMLElement | null>(null)
 * const { canvasRef, getRenderContext, setupPointerEvents } = useCanvasRenderer(containerRef, {
 *   width: ref(800),
 *   height: ref(400)
 * })
 *
 * const renderFrame = () => {
 *   const { ctx, width, height, clear } = getRenderContext()
 *   clear()
 *   ctx.fillStyle = 'blue'
 *   ctx.fillRect(0, 0, width, height)
 * }
 * ```
 */
export function useCanvasRenderer(
  containerRef: Ref<HTMLElement | null>,
  options: CanvasRendererOptions = {}
) {
  const canvasRef = ref<HTMLCanvasElement | null>(null)

  const defaultWidth = ref(800)
  const defaultHeight = ref(320)

  const canvasWidth = options.width ?? defaultWidth
  const canvasHeight = options.height ?? defaultHeight
  const dpr = options.dpr ?? (typeof window !== 'undefined' ? window.devicePixelRatio : 1)

  let resizeTimeout: number | null = null

  /**
   * Get rendering context with current dimensions
   */
  function getRenderContext(): RenderContext {
    const canvas = canvasRef.value
    if (!canvas) {
      throw new Error('[useCanvasRenderer] Canvas ref not initialized')
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) {
      throw new Error('[useCanvasRenderer] Could not get 2D context')
    }

    const width = canvas.width / dpr
    const height = canvas.height / dpr

    return {
      ctx,
      canvas,
      width,
      height,
      clear: () => ctx.clearRect(0, 0, canvas.width, canvas.height)
    }
  }

  /**
   * Resize canvas to match container dimensions with DPR scaling
   * Pattern from IcebergAnimation (lines 131-139)
   */
  function resizeCanvas() {
    const canvas = canvasRef.value
    const container = containerRef.value

    if (!canvas || !container) return

    const rect = container.getBoundingClientRect()
    const width = canvasWidth.value || rect.width
    const height = canvasHeight.value || rect.height

    // Scale for device pixel ratio (retina displays)
    canvas.width = width * dpr
    canvas.height = height * dpr

    // CSS size (actual display size)
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`

    // Scale context to match DPR
    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.scale(dpr, dpr)
    }
  }

  /**
   * Debounced resize handler (300ms)
   */
  function handleResize() {
    if (resizeTimeout !== null) {
      clearTimeout(resizeTimeout)
    }

    resizeTimeout = window.setTimeout(() => {
      resizeCanvas()
      resizeTimeout = null
    }, 300)
  }

  /**
   * Convert pointer event coordinates to canvas coordinates
   * Pattern from IcebergAnimation (lines 351-363)
   */
  function getCanvasCoords(event: PointerEvent): { x: number; y: number } {
    const canvas = canvasRef.value
    if (!canvas) {
      return { x: 0, y: 0 }
    }

    const rect = canvas.getBoundingClientRect()
    return {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top
    }
  }

  /**
   * Setup pointer events with automatic coordinate conversion
   *
   * @param handlers Event handlers
   */
  function setupPointerEvents(handlers: {
    onPointerDown?: (coords: { x: number; y: number }, event: PointerEvent) => void
    onPointerMove?: (coords: { x: number; y: number }, event: PointerEvent) => void
    onPointerUp?: (coords: { x: number; y: number }, event: PointerEvent) => void
    onPointerLeave?: (coords: { x: number; y: number }, event: PointerEvent) => void
  }) {
    const canvas = canvasRef.value
    if (!canvas) return

    if (handlers.onPointerDown) {
      canvas.addEventListener('pointerdown', (e) => {
        handlers.onPointerDown!(getCanvasCoords(e), e)
      })
    }

    if (handlers.onPointerMove) {
      canvas.addEventListener('pointermove', (e) => {
        handlers.onPointerMove!(getCanvasCoords(e), e)
      })
    }

    if (handlers.onPointerUp) {
      canvas.addEventListener('pointerup', (e) => {
        handlers.onPointerUp!(getCanvasCoords(e), e)
      })
    }

    if (handlers.onPointerLeave) {
      canvas.addEventListener('pointerleave', (e) => {
        handlers.onPointerLeave!(getCanvasCoords(e), e)
      })
    }
  }

  /**
   * Lifecycle: Setup canvas and resize listener
   */
  onMounted(() => {
    resizeCanvas()

    // Listen for window resize
    window.addEventListener('resize', handleResize)
  })

  /**
   * Lifecycle: Cleanup resize listener
   */
  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)

    if (resizeTimeout !== null) {
      clearTimeout(resizeTimeout)
    }
  })

  return {
    canvasRef,
    getRenderContext,
    resizeCanvas,
    getCanvasCoords,
    setupPointerEvents,

    // Expose dimensions for reactive access
    width: computed(() => canvasWidth.value),
    height: computed(() => canvasHeight.value)
  }
}
