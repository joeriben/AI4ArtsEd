/**
 * 3 Drift LFOs — ultra-slow parameter modulation for generative drift.
 *
 * Targets: alpha (hallucinator blend), semantic axes 1–3, wavetable scan.
 * Rate range: 0.001 Hz (16min cycle) – 2 Hz, exponential slider mapping.
 *
 * Pure rAF-driven (no AudioContext dependency).
 * Phase-accumulating: each LFO tracks its own phase, waveform computed per frame.
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
  depth: Ref<number>     // 0 – 1
  waveform: Ref<DriftWaveform>
  target: Ref<DriftTarget>
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

  // Callback registry: target → setter function
  const callbacks: Record<string, (value: number) => void> = {}
  // Base value getters: target → current base value
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
    const dt = (now - lastTime) / 1000 // seconds
    lastTime = now

    let anyActive = false

    for (let i = 0; i < 3; i++) {
      const lfo = lfos[i]!
      const target = lfo.target.value
      if (target === 'none' || lfo.depth.value === 0) continue

      const cb = callbacks[target]
      const baseGet = baseGetters[target]
      if (!cb || !baseGet) continue

      anyActive = true

      // Advance phase
      phases[i] = (phases[i]! + lfo.rate.value * dt) % 1

      // Compute waveform output (-1..+1), scale by depth
      const raw = waveformValue(phases[i]!, lfo.waveform.value)
      const base = baseGet()
      // Bipolar modulation: base ± (depth * range)
      // Depth of 1.0 = full range sweep of the target
      cb(base + raw * lfo.depth.value)
    }

    if (anyActive) {
      rafId = requestAnimationFrame(tick)
    } else {
      rafId = null
    }
  }

  function setParam(idx: number, key: keyof DriftLfoState, value: number | string): void {
    const lfo = lfos[idx]
    if (!lfo) return
    const r = lfo[key] as Ref<any>
    r.value = value

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
    setCallbacks,
    setParam,
    start,
    stop,
    resetPhases,
    dispose,
  }
}
