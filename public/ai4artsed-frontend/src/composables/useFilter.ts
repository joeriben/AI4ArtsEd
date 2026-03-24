/**
 * Pure filter composable — no embedded modulators.
 *
 * Signal chain: input → [dry path] ──────────────────→ mixOut → output
 *                     → [wet path] → BiquadFilter ──→ mixOut
 *
 * Mix (0–1): 0 = fully dry, 1 = fully wet (filtered).
 * Both paths are always active — mix controls the balance.
 * This allows adding a resonance peak to a mostly-dry signal.
 *
 * Keyboard tracking shifts cutoff based on MIDI note distance from C3.
 *
 * Cutoff is stored as normalized 0–1 and mapped to 20–20000 Hz (exponential).
 * External modulators (envelopes, LFOs) connect to getFrequencyParam().
 */
import { ref, readonly } from 'vue'

export type FilterType = 'lowpass' | 'highpass' | 'bandpass'

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
  const cutoff = ref(1.0)       // 0–1 normalized
  const resonance = ref(0.7)    // 0–1 mapped to Q
  const mix = ref(1.0)          // 0 = dry, 1 = wet
  const kbdTrack = ref(0)       // 0–1: how much note pitch affects cutoff

  let ctx: AudioContext | null = null
  let filterNode: BiquadFilterNode | null = null
  let inputNode: GainNode | null = null
  let dryGain: GainNode | null = null
  let wetGain: GainNode | null = null
  let outputNode: GainNode | null = null
  let currentNote = 60  // C3 = reference

  /**
   * Create filter nodes. Returns { input, output }.
   * Caller wires: source → input, output → next stage.
   */
  function createNode(ac: AudioContext): { input: GainNode; output: GainNode } {
    ctx = ac

    inputNode = ac.createGain()
    inputNode.gain.value = 1

    filterNode = ac.createBiquadFilter()
    filterNode.type = type.value
    filterNode.frequency.value = normalizedToFreq(cutoff.value)
    filterNode.Q.value = resonanceToQ(resonance.value)

    dryGain = ac.createGain()
    wetGain = ac.createGain()
    outputNode = ac.createGain()
    outputNode.gain.value = 1

    // Dry path: input → dryGain → output
    inputNode.connect(dryGain)
    dryGain.connect(outputNode)

    // Wet path: input → filter → wetGain → output
    inputNode.connect(filterNode)
    filterNode.connect(wetGain)
    wetGain.connect(outputNode)

    applyMix()

    return { input: inputNode, output: outputNode }
  }

  function applyMix(): void {
    if (!dryGain || !wetGain) return
    if (!enabled.value) {
      // Disabled: full dry, no wet
      dryGain.gain.value = 1
      wetGain.gain.value = 0
    } else {
      // Equal-power crossfade
      dryGain.gain.value = Math.cos(mix.value * Math.PI / 2)
      wetGain.gain.value = Math.sin(mix.value * Math.PI / 2)
    }
  }

  function applyParams(): void {
    if (!filterNode) return
    filterNode.type = type.value
    filterNode.Q.value = resonanceToQ(resonance.value)
    applyFrequency()
    applyMix()
  }

  function applyFrequency(): void {
    if (!filterNode) return
    let freq = normalizedToFreq(cutoff.value)
    // Keyboard tracking: shift cutoff by note distance from C3
    if (kbdTrack.value > 0) {
      const semitones = currentNote - 60
      freq *= Math.pow(2, (semitones / 12) * kbdTrack.value)
    }
    freq = Math.max(MIN_FREQ, Math.min(MAX_FREQ, freq))
    filterNode.frequency.value = freq
  }

  /** Get the filter frequency AudioParam for external modulation (envelopes, LFOs). */
  function getFrequencyParam(): AudioParam | null {
    return filterNode?.frequency ?? null
  }

  /** Get the filter Q AudioParam for external modulation. */
  function getQParam(): AudioParam | null {
    return filterNode?.Q ?? null
  }

  /** Notify filter of current MIDI note (for keyboard tracking). */
  function setNote(midiNote: number): void {
    currentNote = midiNote
    if (kbdTrack.value > 0) applyFrequency()
  }

  function setEnabled(on: boolean): void { enabled.value = on; applyMix() }
  function setType(t: FilterType): void { type.value = t; applyParams() }
  function setCutoff(n: number): void { cutoff.value = Math.max(0, Math.min(1, n)); applyParams() }
  function setResonance(r: number): void { resonance.value = Math.max(0, Math.min(1, r)); applyParams() }
  function setMix(m: number): void { mix.value = Math.max(0, Math.min(1, m)); applyMix() }
  function setKbdTrack(k: number): void { kbdTrack.value = Math.max(0, Math.min(1, k)); applyFrequency() }

  function dispose(): void {
    if (filterNode) filterNode.disconnect()
    if (dryGain) dryGain.disconnect()
    if (wetGain) wetGain.disconnect()
    if (inputNode) inputNode.disconnect()
    if (outputNode) outputNode.disconnect()
    filterNode = dryGain = wetGain = inputNode = outputNode = null
    ctx = null
  }

  return {
    enabled: readonly(enabled),
    type: readonly(type),
    cutoff,
    resonance,
    mix,
    kbdTrack,

    createNode,
    getFrequencyParam,
    getQParam,
    setNote,
    setEnabled, setType, setCutoff, setResonance, setMix, setKbdTrack,
    normalizedToFreq,
    dispose,
  }
}
