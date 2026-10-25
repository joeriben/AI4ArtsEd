/**
 * Gradient stop: [position (0-1), color]
 */
export type GradientStop = [number, string]

/**
 * Canvas drawing helpers composable
 *
 * Provides common drawing primitives and utilities for Canvas 2D rendering.
 *
 * @example
 * ```typescript
 * const { drawCircle, drawRect, createCachedGradient } = useCanvasDrawing()
 *
 * function render(ctx: CanvasRenderingContext2D) {
 *   drawCircle(ctx, 100, 100, 50, 'red')
 *   drawRect(ctx, 200, 200, 100, 50, 'blue')
 *
 *   const gradient = createCachedGradient(ctx, 0, 0, 0, 400, [
 *     [0, '#87CEEB'],
 *     [1, '#4682B4']
 *   ])
 *   ctx.fillStyle = gradient
 *   ctx.fillRect(0, 0, 800, 400)
 * }
 * ```
 */
export function useCanvasDrawing() {
  // Gradient cache (pattern from IcebergAnimation lines 168-192)
  const gradientCache = new Map<string, CanvasGradient>()

  /**
   * Draw a filled circle
   */
  function drawCircle(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    radius: number,
    fillStyle: string | CanvasGradient
  ) {
    ctx.fillStyle = fillStyle
    ctx.beginPath()
    ctx.arc(x, y, radius, 0, Math.PI * 2)
    ctx.fill()
  }

  /**
   * Draw a filled rectangle
   */
  function drawRect(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    fillStyle: string | CanvasGradient
  ) {
    ctx.fillStyle = fillStyle
    ctx.fillRect(x, y, width, height)
  }

  /**
   * Draw a filled polygon from points
   */
  function drawPolygon(
    ctx: CanvasRenderingContext2D,
    points: Array<{ x: number; y: number }>,
    fillStyle: string | CanvasGradient
  ) {
    if (points.length < 3) return

    ctx.fillStyle = fillStyle
    ctx.beginPath()
    ctx.moveTo(points[0]!.x, points[0]!.y)

    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i]!.x, points[i]!.y)
    }

    ctx.closePath()
    ctx.fill()
  }

  /**
   * Create a cached linear gradient (avoids recreation every frame)
   *
   * Pattern from IcebergAnimation:
   * - Caches gradient by key
   * - Only recreates if stops change
   */
  function createCachedGradient(
    ctx: CanvasRenderingContext2D,
    x0: number,
    y0: number,
    x1: number,
    y1: number,
    stops: GradientStop[],
    cacheKey?: string
  ): CanvasGradient {
    // Generate cache key from stops if not provided
    const key = cacheKey ?? `${x0},${y0},${x1},${y1}:${stops.map(s => `${s[0]}-${s[1]}`).join(',')}`

    // Return cached if exists
    if (gradientCache.has(key)) {
      return gradientCache.get(key)!
    }

    // Create new gradient
    const gradient = ctx.createLinearGradient(x0, y0, x1, y1)
    stops.forEach(([position, color]) => {
      gradient.addColorStop(position, color)
    })

    // Cache and return
    gradientCache.set(key, gradient)
    return gradient
  }

  /**
   * Clear gradient cache (call if canvas size changes)
   */
  function clearGradientCache() {
    gradientCache.clear()
  }

  /**
   * Draw text with alignment
   */
  function drawText(
    ctx: CanvasRenderingContext2D,
    text: string,
    x: number,
    y: number,
    options: {
      fillStyle?: string
      font?: string
      textAlign?: CanvasTextAlign
      textBaseline?: CanvasTextBaseline
    } = {}
  ) {
    const {
      fillStyle = '#000',
      font = '12px sans-serif',
      textAlign = 'left',
      textBaseline = 'alphabetic'
    } = options

    ctx.fillStyle = fillStyle
    ctx.font = font
    ctx.textAlign = textAlign
    ctx.textBaseline = textBaseline
    ctx.fillText(text, x, y)
  }

  /**
   * Draw image/sprite
   */
  function drawSprite(
    ctx: CanvasRenderingContext2D,
    image: CanvasImageSource,
    x: number,
    y: number,
    width?: number,
    height?: number
  ) {
    if (width !== undefined && height !== undefined) {
      ctx.drawImage(image, x, y, width, height)
    } else {
      ctx.drawImage(image, x, y)
    }
  }

  /**
   * Draw shape with shadow (glow effect)
   */
  function drawWithShadow(
    ctx: CanvasRenderingContext2D,
    drawFn: () => void,
    options: {
      blur?: number
      color?: string
      offsetX?: number
      offsetY?: number
    } = {}
  ) {
    const {
      blur = 10,
      color = '#000',
      offsetX = 0,
      offsetY = 0
    } = options

    ctx.save()
    ctx.shadowBlur = blur
    ctx.shadowColor = color
    ctx.shadowOffsetX = offsetX
    ctx.shadowOffsetY = offsetY

    drawFn()

    ctx.restore()
  }

  /**
   * Draw shape with glow effect (shorthand for shadow with no offset)
   */
  function drawWithGlow(
    ctx: CanvasRenderingContext2D,
    drawFn: () => void,
    glowColor: string,
    glowBlur: number = 10
  ) {
    drawWithShadow(ctx, drawFn, {
      blur: glowBlur,
      color: glowColor,
      offsetX: 0,
      offsetY: 0
    })
  }

  /**
   * Interpolate between two colors
   *
   * @param color1 - Start color (hex)
   * @param color2 - End color (hex)
   * @param t - Interpolation factor (0-1)
   * @returns Interpolated color (hex)
   */
  function interpolateColor(color1: string, color2: string, t: number): string {
    // Parse hex colors
    const r1 = parseInt(color1.slice(1, 3), 16)
    const g1 = parseInt(color1.slice(3, 5), 16)
    const b1 = parseInt(color1.slice(5, 7), 16)

    const r2 = parseInt(color2.slice(1, 3), 16)
    const g2 = parseInt(color2.slice(3, 5), 16)
    const b2 = parseInt(color2.slice(5, 7), 16)

    // Interpolate
    const r = Math.round(r1 + (r2 - r1) * t)
    const g = Math.round(g1 + (g2 - g1) * t)
    const b = Math.round(b1 + (b2 - b1) * t)

    // Return hex
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
  }

  return {
    // Shapes
    drawCircle,
    drawRect,
    drawPolygon,

    // Gradients
    createCachedGradient,
    clearGradientCache,

    // Text & Sprites
    drawText,
    drawSprite,

    // Effects
    drawWithShadow,
    drawWithGlow,

    // Utilities
    interpolateColor
  }
}
