/**
 * Filter + LFO composable for Crossmodal Lab synth.
 *
 * Signal chain position: amp envelope → **filter** → effects (delay/reverb)
 *
 * Features:
 * - BiquadFilterNode (lowpass / highpass / bandpass)
 * - Filter envelope (ADSR → cutoff modulation)
 * - 2 LFOs (OscillatorNode → GainNode → AudioParam)
 *
 * Cutoff is stored as a normalized 0–1 value and mapped to 20–20000 Hz
 * via exponential scaling (perceptually linear). The filter envelope
 * modulates cutoff upward from the base value by `envAmount` octaves.
 */
import { ref, readonly, computed } from 'vue'

export type FilterType = 'lowpass' | 'highpass' | 'bandpass'
export type LfoWaveform = 'sine' | 'triangle' | 'square' | 'sawtooth'
export type LfoTarget = 'cutoff' | 'resonance' | 'amplitude'

const MIN_FREQ = 20
const MAX_FREQ = 20000

/** Map 0–1 to 20–20000 Hz (exponential). */
function normalizedToFreq(n: number): number {
  return MIN_FREQ * Math.pow(MAX_FREQ / MIN_FREQ, Math.max(0, Math.min(1, n)))
}

/** Map 20–20000 Hz back to 0–1. */
function freqToNormalized(f: number): number {
  return Math.log(f / MIN_FREQ) / Math.log(MAX_FREQ / MIN_FREQ)
}

export function useFilter() {
  // ─── Filter params ───
  const enabled = ref(false)
  const type = ref<FilterType>('lowpass')
  const cutoff = ref(1.0)  // 0–1 normalized, default = wide open
  const resonance = ref(0.7)  // Q factor 0.1–20, display 0–1 mapped

  // ─── Filter envelope ───
  const envAttackMs = ref(0)
  const envDecayMs = ref(0)
  const envSustain = ref(1.0)
  const envReleaseMs = ref(0)
  const envAmount = ref(0)  // 0–1: how many octaves the envelope sweeps upward

  // ─── LFO 1 ───
  const lfo1Enabled = ref(false)
  const lfo1Rate = ref(2.0)       // Hz
  const lfo1Depth = ref(0.3)      // 0–1
  const lfo1Waveform = ref<LfoWaveform>('sine')
  const lfo1Target = ref<LfoTarget>('cutoff')

  // ─── LFO 2 ───
  const lfo2Enabled = ref(false)
  const lfo2Rate = ref(0.5)
  const lfo2Depth = ref(0.2)
  const lfo2Waveform = ref<LfoWaveform>('triangle')
  const lfo2Target = ref<LfoTarget>('amplitude')

  const isNeutral = computed(() => !enabled.value)

  // ─── Audio nodes ───
  let ctx: AudioContext | null = null
  let filterNode: BiquadFilterNode | null = null
  let bypassGain: GainNode | null = null

  // LFO nodes
  let lfo1Osc: OscillatorNode | null = null
  let lfo1Gain: GainNode | null = null
  let lfo2Osc: OscillatorNode | null = null
  let lfo2Gain: GainNode | null = null

  // Envelope release timer
  let envReleaseTimer: ReturnType<typeof setTimeout> | null = null

  /** Resonance: UI 0–1 → Q 0.5–18 (exponential for musical feel) */
  function resonanceToQ(r: number): number {
    return 0.5 * Math.pow(36, r)  // 0→0.5, 0.5→3, 1→18
  }

  /**
   * Create filter node and insert into chain.
   * Returns { input, output } — caller wires: source → input, output → next.
   */
  function createNode(ac: AudioContext): { input: GainNode; output: GainNode } {
    ctx = ac

    // Input gain (always 1, used as connection point)
    const input = ac.createGain()
    input.gain.value = 1

    // Filter
    filterNode = ac.createBiquadFilter()
    filterNode.type = type.value
    filterNode.frequency.value = normalizedToFreq(cutoff.value)
    filterNode.Q.value = resonanceToQ(resonance.value)

    // Bypass gain (output)
    bypassGain = ac.createGain()
    bypassGain.gain.value = 1

    // Wire: input → filter → output (when enabled)
    // Also: input → output (bypass, when disabled)
    input.connect(filterNode)
    filterNode.connect(bypassGain)
    input.connect(bypassGain)  // bypass path always connected

    applyEnabled()

    // Create LFO nodes
    createLfo(ac, 1)
    createLfo(ac, 2)

    return { input, output: bypassGain }
  }

  function applyEnabled(): void {
    if (!filterNode || !bypassGain) return
    if (enabled.value) {
      // Filter active: mute bypass, let filter path through
      filterNode.connect(bypassGain)
    }
    // Both paths always connected; filter type 'allpass' at max freq effectively bypasses.
    // We control via gain: the filter path is always there, we just set freq to max when disabled.
    if (!enabled.value) {
      filterNode.frequency.value = MAX_FREQ
      filterNode.Q.value = 0.5
    } else {
      filterNode.type = type.value
      filterNode.frequency.value = normalizedToFreq(cutoff.value)
      filterNode.Q.value = resonanceToQ(resonance.value)
    }
  }

  function applyParams(): void {
    if (!filterNode || !enabled.value) return
    filterNode.type = type.value
    filterNode.frequency.value = normalizedToFreq(cutoff.value)
    filterNode.Q.value = resonanceToQ(resonance.value)
    applyLfoRouting()
  }

  // ─── Filter Envelope ───

  function triggerEnvAttack(): void {
    if (!filterNode || !enabled.value || !ctx || envAmount.value === 0) return
    const now = ctx.currentTime
    const baseFreq = normalizedToFreq(cutoff.value)
    // Envelope sweeps cutoff upward by envAmount octaves
    const peakFreq = Math.min(MAX_FREQ, baseFreq * Math.pow(2, envAmount.value * 4))
    const susFreq = baseFreq + (peakFreq - baseFreq) * envSustain.value

    const atk = envAttackMs.value / 1000
    const dec = envDecayMs.value / 1000

    if (envReleaseTimer) { clearTimeout(envReleaseTimer); envReleaseTimer = null }

    filterNode.frequency.cancelScheduledValues(now)
    filterNode.frequency.setValueAtTime(baseFreq, now)
    filterNode.frequency.exponentialRampToValueAtTime(
      Math.max(peakFreq, MIN_FREQ), now + Math.max(atk, 0.002),
    )
    filterNode.frequency.exponentialRampToValueAtTime(
      Math.max(susFreq, MIN_FREQ), now + Math.max(atk, 0.002) + Math.max(dec, 0.002),
    )
  }

  function triggerEnvRelease(): void {
    if (!filterNode || !enabled.value || !ctx || envAmount.value === 0) return
    const now = ctx.currentTime
    const baseFreq = normalizedToFreq(cutoff.value)
    const rel = envReleaseMs.value / 1000

    const current = filterNode.frequency.value
    filterNode.frequency.cancelScheduledValues(now)
    filterNode.frequency.setValueAtTime(Math.max(current, MIN_FREQ), now)
    filterNode.frequency.exponentialRampToValueAtTime(
      Math.max(baseFreq, MIN_FREQ), now + Math.max(rel, 0.002),
    )
  }

  function bypassEnvelope(): void {
    if (!filterNode || !ctx) return
    if (envReleaseTimer) { clearTimeout(envReleaseTimer); envReleaseTimer = null }
    filterNode.frequency.cancelScheduledValues(ctx.currentTime)
    if (enabled.value) {
      filterNode.frequency.value = normalizedToFreq(cutoff.value)
    }
  }

  // ─── LFOs ───

  function createLfo(ac: AudioContext, num: 1 | 2): void {
    const osc = ac.createOscillator()
    const gain = ac.createGain()
    const cfg = num === 1
      ? { rate: lfo1Rate, depth: lfo1Depth, waveform: lfo1Waveform, enabled: lfo1Enabled }
      : { rate: lfo2Rate, depth: lfo2Depth, waveform: lfo2Waveform, enabled: lfo2Enabled }

    osc.type = cfg.waveform.value
    osc.frequency.value = cfg.rate.value
    gain.gain.value = 0  // will be set by applyLfoRouting

    osc.connect(gain)
    osc.start()

    if (num === 1) { lfo1Osc = osc; lfo1Gain = gain }
    else { lfo2Osc = osc; lfo2Gain = gain }
  }

  function applyLfoRouting(): void {
    // Disconnect all LFO targets first
    if (lfo1Gain) try { lfo1Gain.disconnect() } catch { /* noop */ }
    if (lfo2Gain) try { lfo2Gain.disconnect() } catch { /* noop */ }

    if (!filterNode || !bypassGain || !enabled.value) return

    // LFO 1
    if (lfo1Osc && lfo1Gain && lfo1Enabled.value) {
      lfo1Osc.frequency.value = lfo1Rate.value
      lfo1Osc.type = lfo1Waveform.value
      connectLfoToTarget(lfo1Gain, lfo1Target.value, lfo1Depth.value)
    }

    // LFO 2
    if (lfo2Osc && lfo2Gain && lfo2Enabled.value) {
      lfo2Osc.frequency.value = lfo2Rate.value
      lfo2Osc.type = lfo2Waveform.value
      connectLfoToTarget(lfo2Gain, lfo2Target.value, lfo2Depth.value)
    }
  }

  function connectLfoToTarget(gain: GainNode, target: LfoTarget, depth: number): void {
    if (!filterNode || !bypassGain) return
    switch (target) {
      case 'cutoff':
        // Modulate frequency: depth maps to Hz range around current cutoff
        gain.gain.value = normalizedToFreq(cutoff.value) * depth
        gain.connect(filterNode.frequency)
        break
      case 'resonance':
        gain.gain.value = resonanceToQ(resonance.value) * depth
        gain.connect(filterNode.Q)
        break
      case 'amplitude':
        gain.gain.value = depth
        gain.connect(bypassGain.gain)
        break
    }
  }

  // ─── Setters (update nodes in real-time) ───

  function setEnabled(on: boolean): void {
    enabled.value = on
    applyEnabled()
    if (on) applyLfoRouting()
  }

  function setType(t: FilterType): void {
    type.value = t
    applyParams()
  }

  function setCutoff(n: number): void {
    cutoff.value = Math.max(0, Math.min(1, n))
    applyParams()
  }

  function setResonance(r: number): void {
    resonance.value = Math.max(0, Math.min(1, r))
    applyParams()
  }

  function setEnvAmount(a: number): void { envAmount.value = Math.max(0, Math.min(1, a)) }

  function setLfo1Enabled(on: boolean): void { lfo1Enabled.value = on; applyLfoRouting() }
  function setLfo1Rate(r: number): void { lfo1Rate.value = r; if (lfo1Osc) lfo1Osc.frequency.value = r }
  function setLfo1Depth(d: number): void { lfo1Depth.value = d; applyLfoRouting() }
  function setLfo1Waveform(w: LfoWaveform): void { lfo1Waveform.value = w; if (lfo1Osc) lfo1Osc.type = w }
  function setLfo1Target(t: LfoTarget): void { lfo1Target.value = t; applyLfoRouting() }

  function setLfo2Enabled(on: boolean): void { lfo2Enabled.value = on; applyLfoRouting() }
  function setLfo2Rate(r: number): void { lfo2Rate.value = r; if (lfo2Osc) lfo2Osc.frequency.value = r }
  function setLfo2Depth(d: number): void { lfo2Depth.value = d; applyLfoRouting() }
  function setLfo2Waveform(w: LfoWaveform): void { lfo2Waveform.value = w; if (lfo2Osc) lfo2Osc.type = w }
  function setLfo2Target(t: LfoTarget): void { lfo2Target.value = t; applyLfoRouting() }

  function dispose(): void {
    if (envReleaseTimer) { clearTimeout(envReleaseTimer); envReleaseTimer = null }
    if (lfo1Osc) { lfo1Osc.stop(); lfo1Osc.disconnect() }
    if (lfo1Gain) lfo1Gain.disconnect()
    if (lfo2Osc) { lfo2Osc.stop(); lfo2Osc.disconnect() }
    if (lfo2Gain) lfo2Gain.disconnect()
    if (filterNode) filterNode.disconnect()
    if (bypassGain) bypassGain.disconnect()
    lfo1Osc = lfo1Gain = lfo2Osc = lfo2Gain = null
    filterNode = bypassGain = null
    ctx = null
  }

  return {
    // Filter
    enabled: readonly(enabled),
    type: readonly(type),
    cutoff,
    resonance,
    isNeutral,
    setEnabled, setType, setCutoff, setResonance,
    createNode,
    applyParams,
    normalizedToFreq,

    // Filter envelope
    envAttackMs,
    envDecayMs,
    envSustain,
    envReleaseMs,
    envAmount,
    setEnvAmount,
    triggerEnvAttack,
    triggerEnvRelease,
    bypassEnvelope,

    // LFO 1
    lfo1Enabled: readonly(lfo1Enabled),
    lfo1Rate, lfo1Depth,
    lfo1Waveform: readonly(lfo1Waveform),
    lfo1Target: readonly(lfo1Target),
    setLfo1Enabled, setLfo1Rate, setLfo1Depth, setLfo1Waveform, setLfo1Target,

    // LFO 2
    lfo2Enabled: readonly(lfo2Enabled),
    lfo2Rate, lfo2Depth,
    lfo2Waveform: readonly(lfo2Waveform),
    lfo2Target: readonly(lfo2Target),
    setLfo2Enabled, setLfo2Rate, setLfo2Depth, setLfo2Waveform, setLfo2Target,

    dispose,
  }
}
