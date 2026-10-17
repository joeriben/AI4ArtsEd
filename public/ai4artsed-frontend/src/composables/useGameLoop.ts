import { ref, watch, onUnmounted, type Ref } from 'vue'

/**
 * Game loop modes
 */
export type GameLoopMode = 'raf' | 'interval'

/**
 * Options for game loop
 */
export interface GameLoopOptions {
  /**
   * Loop mode:
   * - 'raf': requestAnimationFrame (60fps, smooth animations)
   * - 'interval': setInterval (lower fps, game logic)
   */
  mode: GameLoopMode

  /**
   * Frames per second (only for 'interval' mode)
   * Default: 10 (100ms, matches ForestMiniGame/RareEarthMiniGame)
   */
  fps?: number

  /**
   * Callback called each tick
   * @param dt - Delta time in seconds since last tick
   */
  onTick: (dt: number) => void

  /**
   * Whether the loop is active (auto start/stop)
   */
  isActive: Ref<boolean>
}

/**
 * Unified game loop composable
 *
 * Supports two modes:
 * - **RAF mode**: 60fps smooth animations (IcebergAnimation pattern)
 * - **Interval mode**: Lower fps for game logic (ForestMiniGame/RareEarthMiniGame pattern)
 *
 * Automatically starts/stops based on `isActive` ref.
 *
 * @example RAF mode (smooth 60fps)
 * ```typescript
 * const { start, stop } = useGameLoop({
 *   mode: 'raf',
 *   onTick: (dt) => {
 *     updatePhysics(dt)
 *     render()
 *   },
 *   isActive: computed(() => progress.value > 0)
 * })
 * ```
 *
 * @example Interval mode (10fps game logic)
 * ```typescript
 * const { start, stop } = useGameLoop({
 *   mode: 'interval',
 *   fps: 10,  // 100ms ticks
 *   onTick: (dt) => {
 *     updateGameLogic(dt)
 *   },
 *   isActive: computed(() => !gameOver.value)
 * })
 * ```
 */
export function useGameLoop(options: GameLoopOptions) {
  const { mode, fps = 10, onTick, isActive } = options

  const tickCount = ref(0)
  const isRunning = ref(false)

  let rafId: number | null = null
  let intervalId: number | null = null
  let lastFrameTime = 0

  /**
   * RAF loop implementation (pattern from IcebergAnimation lines 367-424)
   */
  function rafLoop(timestamp: number) {
    if (!isRunning.value) return

    // Calculate delta time (in seconds)
    const dt = lastFrameTime === 0 ? 0 : (timestamp - lastFrameTime) / 1000
    lastFrameTime = timestamp

    // Skip first frame (dt = 0)
    if (dt > 0) {
      onTick(dt)
      tickCount.value++
    }

    // Schedule next frame
    rafId = requestAnimationFrame(rafLoop)
  }

  /**
   * Interval loop implementation (pattern from ForestMiniGame/RareEarthMiniGame)
   */
  function intervalLoop() {
    if (!isRunning.value) return

    const dt = 1 / fps  // Delta time in seconds

    onTick(dt)
    tickCount.value++
  }

  /**
   * Start the game loop
   */
  function start() {
    if (isRunning.value) return

    isRunning.value = true
    tickCount.value = 0

    if (mode === 'raf') {
      lastFrameTime = 0
      rafId = requestAnimationFrame(rafLoop)
    } else {
      const intervalMs = 1000 / fps
      intervalId = window.setInterval(intervalLoop, intervalMs)
    }
  }

  /**
   * Stop the game loop
   */
  function stop() {
    if (!isRunning.value) return

    isRunning.value = false

    if (mode === 'raf' && rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
      lastFrameTime = 0
    } else if (mode === 'interval' && intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  /**
   * Auto start/stop based on isActive ref
   */
  watch(
    isActive,
    (active) => {
      if (active) {
        start()
      } else {
        stop()
      }
    },
    { immediate: true }
  )

  /**
   * Cleanup on unmount
   */
  onUnmounted(() => {
    stop()
  })

  return {
    start,
    stop,
    tickCount,
    isRunning
  }
}
