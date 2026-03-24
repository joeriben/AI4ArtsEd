/**
 * 3 Drift LFOs — rAF-driven, ultra-slow parameter modulation.
 *
 * Offset-based: reads base (slider value) every tick, applies offset on top.
 * Slider stays at user's setting; drift indicator shows modulated position.
 *
 * output = base() + waveform(phase) * depth * halfRange
 */
import { ref, type Ref } from 'vue'

export type DriftTarget =
  | 'alpha'
  | 'sem_axis_1' | 'sem_axis_2' | 'sem_axis_3'
  | 'wt_scan'
  | 'none'

export const DRIFT_TARGETS: DriftTarget[] = [
  'none', 'alpha', 'sem_axis_1', 'sem_axis_2', 'sem_axis_3', 'wt_scan',
]

export type DriftWaveform = 'sine' | 'triangle' | 'square' | 'sawtooth'

export interface DriftLfoState {
  rate: Ref<number>      // Hz (0.001 – 2)
  depth: Ref<number>     // 0 – 1 (exponential mapped)
  waveform: Ref<DriftWaveform>
  target: Ref<DriftTarget>
}

// ─── Target ranges: min/max bounds, halfRange derived ───

export const TARGET_RANGES: Record<string, { min: number; max: number }> = {
  alpha:      { min: -2, max: 2 },
  sem_axis_1: { min: -2, max: 2 },
  sem_axis_2: { min: -2, max: 2 },
  sem_axis_3: { min: -2, max: 2 },
  wt_scan:    { min: 0, max: 1 },
}

// ─── Rate mapping: exponential 0.001 – 2 Hz ───

const DRIFT_RATE_MIN = 0.001
const DRIFT_RATE_MAX = 2

export function sliderToDriftRate(v: number): number {
  return DRIFT_RATE_MIN * Math.pow(DRIFT_RATE_MAX / DRIFT_RATE_MIN, v)
}

export function driftRateToSlider(hz: number): number {
  return Math.log(Math.max(DRIFT_RATE_MIN, hz) / DRIFT_RATE_MIN) / Math.log(DRIFT_RATE_MAX / DRIFT_RATE_MIN)
}

export function formatDriftRate(hz: number): string {
  if (hz >= 1) return `${hz.toFixed(2)} Hz`
  if (hz >= 0.01) return `${hz.toFixed(3)} Hz`
  return `${hz.toFixed(4)} Hz`
}

// ─── Depth mapping: exponential 0.001 – 1 (micro-drift at low end) ───

const DRIFT_DEPTH_MIN = 0.001
const DRIFT_DEPTH_MAX = 1

export function sliderToDriftDepth(v: number): number {
  if (v === 0) return 0
  return DRIFT_DEPTH_MIN * Math.pow(DRIFT_DEPTH_MAX / DRIFT_DEPTH_MIN, v)
}

export function driftDepthToSlider(d: number): number {
  if (d <= 0) return 0
  return Math.log(Math.max(DRIFT_DEPTH_MIN, d) / DRIFT_DEPTH_MIN) / Math.log(DRIFT_DEPTH_MAX / DRIFT_DEPTH_MIN)
}

export function formatDriftDepth(d: number): string {
  if (d === 0) return '0'
  if (d >= 0.1) return d.toFixed(2)
  if (d >= 0.01) return d.toFixed(3)
  return d.toFixed(4)
}

// ─── Waveform computation (phase 0–1 → output -1..+1) ───

function waveformValue(phase: number, type: DriftWaveform): number {
  const p = phase - Math.floor(phase) // normalize to 0–1
  switch (type) {
    case 'sine':
      return Math.sin(p * Math.PI * 2)
    case 'triangle':
      return p < 0.25 ? p * 4
        : p < 0.75 ? 2 - p * 4
        : p * 4 - 4
    case 'square':
      return p < 0.5 ? 1 : -1
    case 'sawtooth':
      return p < 0.5 ? p * 2 : p * 2 - 2
  }
}

// ─── Composable ───

export function useDriftLfo() {
  const lfos: DriftLfoState[] = [
    { rate: ref(0.01), depth: ref(0), waveform: ref<DriftWaveform>('sine'), target: ref<DriftTarget>('none') },
    { rate: ref(0.005), depth: ref(0), waveform: ref<DriftWaveform>('triangle'), target: ref<DriftTarget>('none') },
    { rate: ref(0.002), depth: ref(0), waveform: ref<DriftWaveform>('sine'), target: ref<DriftTarget>('none') },
  ]

  // Phase accumulators (0–1 wrapping)
  const phases = [0, 0, 0]
  let lastTime = 0
  let rafId: number | null = null

  // Current offsets (reactive) — for visual indicators on sliders
  const offsets: Ref<number>[] = [ref(0), ref(0), ref(0)]

  // Callback registry: target → setter function
  const callbacks: Record<string, (value: number) => void> = {}
  // Base value getters: target → current user base value (read every tick)
  const baseGetters: Record<string, () => number> = {}

  function setCallbacks(targets: Record<string, { callback: (v: number) => void; baseValue: () => number }>): void {
    for (const [key, { callback, baseValue }] of Object.entries(targets)) {
      callbacks[key] = callback
      baseGetters[key] = baseValue
    }
  }

  function start(): void {
    if (rafId !== null) return
    lastTime = performance.now()
    tick()
  }

  function stop(): void {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  }

  function resetPhases(): void {
    phases[0] = 0
    phases[1] = 0
    phases[2] = 0
    lastTime = performance.now()
  }

  function tick(): void {
    const now = performance.now()
    const dt = (now - lastTime) / 1000
    lastTime = now

    let anyActive = false

    for (let i = 0; i < 3; i++) {
      const lfo = lfos[i]!
      const target = lfo.target.value
      if (target === 'none' || lfo.depth.value === 0) {
        if (offsets[i]!.value !== 0) offsets[i]!.value = 0
        continue
      }

      const cb = callbacks[target]
      const getter = baseGetters[target]
      if (!cb || !getter) continue

      const range = TARGET_RANGES[target]
      if (!range) continue

      anyActive = true

      // Advance phase
      phases[i] = (phases[i]! + lfo.rate.value * dt) % 1

      const raw = waveformValue(phases[i]!, lfo.waveform.value)
      const base = getter() // Read current slider value EVERY tick
      const halfRange = (range.max - range.min) / 2
      const offset = raw * lfo.depth.value * halfRange
      offsets[i]!.value = offset
      const modulated = Math.max(range.min, Math.min(range.max, base + offset))
      cb(modulated)
    }

    if (anyActive) {
      rafId = requestAnimationFrame(tick)
    } else {
      rafId = null
    }
  }

  /** Sum of all LFO offsets currently targeting a given parameter. */
  function getOffsetForTarget(target: DriftTarget): number {
    let total = 0
    for (let i = 0; i < 3; i++) {
      if (lfos[i]!.target.value === target) {
        total += offsets[i]!.value
      }
    }
    return total
  }

  function setParam(idx: number, key: keyof DriftLfoState, value: number | string): void {
    const lfo = lfos[idx]
    if (!lfo) return

    if (key === 'target') {
      // Restore old target: zero offset, call cb with current base (undo modulation)
      const oldTarget = lfo.target.value
      if (oldTarget !== 'none') {
        offsets[idx]!.value = 0
        const cb = callbacks[oldTarget]
        const getter = baseGetters[oldTarget]
        if (cb && getter) cb(getter())
      }
    }

    const r = lfo[key] as Ref<any>
    r.value = value

    if (key === 'target') {
      phases[idx] = 0
    }

    // Auto-start/stop the rAF loop based on active targets
    const anyActive = lfos.some(l => l.target.value !== 'none' && l.depth.value > 0)
    if (anyActive && rafId === null) {
      lastTime = performance.now()
      tick()
    }
  }

  function dispose(): void {
    stop()
  }

  return {
    lfos,
    offsets,
    setCallbacks,
    setParam,
    getOffsetForTarget,
    start,
    stop,
    resetPhases,
    dispose,
  }
}
