/**
 * Pure filter composable — no embedded modulators.
 *
 * Signal chain: input → [dry path] ──────────────────→ mixOut → output
 *                     → [wet path] → Filter(s) ─────→ mixOut
 *
 * Mix (0–1): 0 = fully dry, 1 = fully wet (filtered).
 * Both paths are always active — mix controls the balance.
 *
 * Slopes: 12dB/oct (1 BiquadFilter), 24dB/oct (2 cascaded BiquadFilters).
 * Keyboard tracking shifts cutoff based on MIDI note distance from C3.
 *
 * Cutoff is stored as normalized 0–1 and mapped to 20–20000 Hz (exponential).
 * External modulators (envelopes, LFOs) connect to getFrequencyParam().
 */
import { ref, readonly } from 'vue'

export type FilterType = 'lowpass' | 'highpass' | 'bandpass'
export type FilterSlope = '12' | '24'

const MIN_FREQ = 20
const MAX_FREQ = 20000

/** Map 0–1 to 20–20000 Hz (exponential). */
export function normalizedToFreq(n: number): number {
  return MIN_FREQ * Math.pow(MAX_FREQ / MIN_FREQ, Math.max(0, Math.min(1, n)))
}

/** Resonance: UI 0–1 → Q 0.5–18 (exponential for musical feel) */
function resonanceToQ(r: number): number {
  return 0.5 * Math.pow(36, r)
}

export function useFilter() {
  const enabled = ref(false)
  const type = ref<FilterType>('lowpass')
  const slope = ref<FilterSlope>('12')
  const cutoff = ref(1.0)       // 0–1 normalized
  const resonance = ref(0)      // 0–1 mapped to Q (0 = minimal Q, flat passband)
  const mix = ref(1.0)          // 0 = dry, 1 = wet
  const kbdTrack = ref(0)       // 0–1: how much note pitch affects cutoff

  let ctx: AudioContext | null = null
  // Two filter nodes: filterNodes[0] always used, filterNodes[1] for 24dB cascade
  let filterNodes: BiquadFilterNode[] = []
  let inputNode: GainNode | null = null
  let dryGain: GainNode | null = null
  let wetGain: GainNode | null = null
  let outputNode: GainNode | null = null
  let currentNote = 60

  /**
   * Create filter nodes. Returns { input, output }.
   */
  function createNode(ac: AudioContext): { input: GainNode; output: GainNode } {
    ctx = ac

    inputNode = ac.createGain()
    inputNode.gain.value = 1

    // Create two BiquadFilterNodes (second used only for 24dB)
    filterNodes = [ac.createBiquadFilter(), ac.createBiquadFilter()]
    for (const fn of filterNodes) {
      fn.type = type.value
      fn.frequency.value = normalizedToFreq(cutoff.value)
      fn.Q.value = resonanceToQ(resonance.value)
    }

    dryGain = ac.createGain()
    wetGain = ac.createGain()
    outputNode = ac.createGain()
    outputNode.gain.value = 1

    // Dry path
    inputNode.connect(dryGain)
    dryGain.connect(outputNode)

    // Wet output → mix bus
    wetGain.connect(outputNode)

    // Wet path (filter chain) — rewired by applySlope()
    applySlope()
    applyMix()

    return { input: inputNode, output: outputNode }
  }

  /** Wire wet path based on slope setting */
  function applySlope(): void {
    if (!inputNode || !wetGain || filterNodes.length < 2) return

    // Disconnect existing wet path
    try { inputNode.disconnect(filterNodes[0]!) } catch { /* noop */ }
    try { filterNodes[0]!.disconnect() } catch { /* noop */ }
    try { filterNodes[1]!.disconnect() } catch { /* noop */ }

    if (slope.value === '24') {
      // 24dB: input → filter1 → filter2 → wetGain
      inputNode.connect(filterNodes[0]!)
      filterNodes[0]!.connect(filterNodes[1]!)
      filterNodes[1]!.connect(wetGain)
    } else {
      // 12dB: input → filter1 → wetGain
      inputNode.connect(filterNodes[0]!)
      filterNodes[0]!.connect(wetGain)
    }
  }

  function applyMix(): void {
    if (!dryGain || !wetGain) return
    if (!enabled.value || cutoff.value > 0.95) {
      // Disabled or cutoff wide open: bypass filter entirely
      dryGain.gain.value = 1
      wetGain.gain.value = 0
    } else {
      dryGain.gain.value = Math.cos(mix.value * Math.PI / 2)
      wetGain.gain.value = Math.sin(mix.value * Math.PI / 2)
    }
  }

  function applyParams(): void {
    for (const fn of filterNodes) {
      fn.type = type.value
      fn.Q.value = resonanceToQ(resonance.value)
    }
    applyFrequency()
    applyMix()
  }

  function applyFrequency(): void {
    let freq = normalizedToFreq(cutoff.value)
    if (kbdTrack.value > 0) {
      const semitones = currentNote - 60
      freq *= Math.pow(2, (semitones / 12) * kbdTrack.value)
    }
    freq = Math.max(MIN_FREQ, Math.min(MAX_FREQ, freq))
    for (const fn of filterNodes) {
      fn.frequency.value = freq
    }
  }

  /** Get the primary filter frequency AudioParam for external modulation. */
  function getFrequencyParam(): AudioParam | null {
    return filterNodes[0]?.frequency ?? null
  }

  /** Get the primary filter Q AudioParam for external modulation. */
  function getQParam(): AudioParam | null {
    return filterNodes[0]?.Q ?? null
  }

  function setNote(midiNote: number): void {
    currentNote = midiNote
    if (kbdTrack.value > 0) applyFrequency()
  }

  function setEnabled(on: boolean): void { enabled.value = on; applyMix() }
  function setType(t: FilterType): void { type.value = t; applyParams() }
  function setSlope(s: FilterSlope): void { slope.value = s; applySlope() }
  function setCutoff(n: number): void { cutoff.value = Math.max(0, Math.min(1, n)); applyParams() }
  function setResonance(r: number): void { resonance.value = Math.max(0, Math.min(1, r)); applyParams() }
  function setMix(m: number): void { mix.value = Math.max(0, Math.min(1, m)); applyMix() }
  function setKbdTrack(k: number): void { kbdTrack.value = Math.max(0, Math.min(1, k)); applyFrequency() }

  function dispose(): void {
    for (const fn of filterNodes) fn.disconnect()
    filterNodes = []
    if (dryGain) dryGain.disconnect()
    if (wetGain) wetGain.disconnect()
    if (inputNode) inputNode.disconnect()
    if (outputNode) outputNode.disconnect()
    dryGain = wetGain = inputNode = outputNode = null
    ctx = null
  }

  return {
    enabled: readonly(enabled),
    type: readonly(type),
    slope,
    cutoff,
    resonance,
    mix,
    kbdTrack,

    createNode,
    getFrequencyParam,
    getQParam,
    setNote,
    setEnabled, setType, setSlope, setCutoff, setResonance, setMix, setKbdTrack,
    normalizedToFreq,
    dispose,
  }
}
