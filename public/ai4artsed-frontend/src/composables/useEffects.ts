/**
 * Send-bus effects chain: Delay + Convolution Reverb (plate).
 *
 * Architecture (all native Web Audio nodes — no AudioWorklet):
 *
 *   source → dryGain ──────────────────────────────→ destination
 *          → delaySend → DelayNode → feedbackGain ─┐
 *          │             ↑──────────────────────────┘
 *          │           → delayOut ──────────────────→ destination
 *          → reverbSend → ConvolverNode → reverbOut → destination
 *
 * EMT-140 plate reverb impulse responses (CC-BY, Greg Hopkins).
 */
import { ref, readonly } from 'vue'

export type PlateVariant = 'bright' | 'medium' | 'dark'

/** Resolve IR paths via import.meta.url — works in both Vite dev and built dist */
const IR_URLS: Record<PlateVariant, string> = {
  bright: new URL('../audio/ir/emt_140_plate_bright.wav', import.meta.url).href,
  medium: new URL('../audio/ir/emt_140_plate_medium.wav', import.meta.url).href,
  dark:   new URL('../audio/ir/emt_140_plate_dark.wav', import.meta.url).href,
}

export function useEffects() {
  let ctx: AudioContext | null = null
  let inputNode: GainNode | null = null

  // Dry
  let dryGain: GainNode | null = null

  // Delay
  let delaySend: GainNode | null = null
  let delayNode: DelayNode | null = null
  let feedbackGain: GainNode | null = null
  let delayOut: GainNode | null = null

  // Reverb
  let reverbSend: GainNode | null = null
  let convolver: ConvolverNode | null = null
  let reverbOut: GainNode | null = null

  // Reactive state
  const delayEnabled = ref(false)
  const delayTimeMs = ref(250)
  const delayFeedback = ref(0.35)
  const delayMix = ref(0.3)

  const reverbEnabled = ref(false)
  const reverbMix = ref(0.25)
  const reverbVariant = ref<PlateVariant>('medium')
  const reverbLoaded = ref(false)

  let loadedVariant: PlateVariant | null = null
  let destinationNode: AudioNode | null = null

  /**
   * Build the effects graph. Call once after AudioContext exists.
   * Returns the input GainNode — connect your source to this.
   */
  function createChain(ac: AudioContext, dest: AudioNode): GainNode {
    ctx = ac
    destinationNode = dest

    // Input splitter
    inputNode = ac.createGain()
    inputNode.gain.value = 1

    // Dry path
    dryGain = ac.createGain()
    dryGain.gain.value = 1
    inputNode.connect(dryGain)
    dryGain.connect(dest)

    // Delay path
    delaySend = ac.createGain()
    delaySend.gain.value = 0
    delayNode = ac.createDelay(5.0)
    delayNode.delayTime.value = delayTimeMs.value / 1000
    feedbackGain = ac.createGain()
    feedbackGain.gain.value = delayFeedback.value
    delayOut = ac.createGain()
    delayOut.gain.value = 1

    inputNode.connect(delaySend)
    delaySend.connect(delayNode)
    delayNode.connect(feedbackGain)
    feedbackGain.connect(delayNode)  // feedback loop
    delayNode.connect(delayOut)
    delayOut.connect(dest)

    // Reverb path
    reverbSend = ac.createGain()
    reverbSend.gain.value = 0
    convolver = ac.createConvolver()
    reverbOut = ac.createGain()
    reverbOut.gain.value = 1

    inputNode.connect(reverbSend)
    reverbSend.connect(convolver)
    convolver.connect(reverbOut)
    reverbOut.connect(dest)

    // Apply initial state
    applyDelayParams()
    applyReverbParams()

    // Load IR if reverb was enabled before chain existed
    if (reverbEnabled.value && !reverbLoaded.value) {
      loadIR(reverbVariant.value)
    }

    return inputNode
  }

  // ─── Delay ───

  function applyDelayParams(): void {
    if (!delaySend || !delayNode || !feedbackGain || !dryGain) return
    delaySend.gain.value = delayEnabled.value ? delayMix.value : 0
    delayNode.delayTime.value = delayTimeMs.value / 1000
    feedbackGain.gain.value = Math.min(delayFeedback.value, 0.95) // safety clamp
    // Adjust dry to compensate
    dryGain.gain.value = delayEnabled.value ? 1 - delayMix.value * 0.3 : 1
  }

  function setDelayEnabled(on: boolean): void {
    delayEnabled.value = on
    applyDelayParams()
  }

  function setDelayTime(ms: number): void {
    delayTimeMs.value = Math.max(1, Math.min(5000, ms))
    if (delayNode) delayNode.delayTime.value = delayTimeMs.value / 1000
  }

  function setDelayFeedback(fb: number): void {
    delayFeedback.value = Math.max(0, Math.min(0.95, fb))
    if (feedbackGain) feedbackGain.gain.value = delayFeedback.value
  }

  function setDelayMix(mix: number): void {
    delayMix.value = Math.max(0, Math.min(1, mix))
    applyDelayParams()
  }

  /** Sync delay time to BPM: set delay to a musical division */
  function syncDelayToBpm(bpm: number, division: '1/4' | '1/8' | '1/16' | '1/8T' | '1/4T'): void {
    const quarterMs = (60 / bpm) * 1000
    const factors: Record<string, number> = {
      '1/4': 1, '1/8': 0.5, '1/16': 0.25, '1/8T': 1/3, '1/4T': 2/3,
    }
    setDelayTime(quarterMs * (factors[division] ?? 0.5))
  }

  // ─── Reverb ───

  function applyReverbParams(): void {
    if (!reverbSend || !dryGain) return
    reverbSend.gain.value = reverbEnabled.value ? reverbMix.value : 0
  }

  async function loadIR(variant: PlateVariant): Promise<void> {
    if (!ctx || !convolver) return
    if (loadedVariant === variant && reverbLoaded.value) return

    const url = IR_URLS[variant]
    try {
      const resp = await fetch(url)
      const arrayBuf = await resp.arrayBuffer()
      const audioBuf = await ctx.decodeAudioData(arrayBuf)
      convolver.buffer = audioBuf
      loadedVariant = variant
      reverbLoaded.value = true
    } catch (e) {
      console.warn(`Failed to load IR ${url}:`, e)
      reverbLoaded.value = false
    }
  }

  async function setReverbEnabled(on: boolean): Promise<void> {
    reverbEnabled.value = on
    if (on && !reverbLoaded.value) {
      await loadIR(reverbVariant.value)
    }
    applyReverbParams()
  }

  function setReverbMix(mix: number): void {
    reverbMix.value = Math.max(0, Math.min(1, mix))
    applyReverbParams()
  }

  async function setReverbVariant(variant: PlateVariant): Promise<void> {
    reverbVariant.value = variant
    if (reverbEnabled.value) {
      await loadIR(variant)
    }
  }

  function getInputNode(): GainNode | null {
    return inputNode
  }

  function dispose(): void {
    if (inputNode) { inputNode.disconnect(); inputNode = null }
    if (dryGain) { dryGain.disconnect(); dryGain = null }
    if (delaySend) { delaySend.disconnect(); delaySend = null }
    if (delayNode) { delayNode.disconnect(); delayNode = null }
    if (feedbackGain) { feedbackGain.disconnect(); feedbackGain = null }
    if (delayOut) { delayOut.disconnect(); delayOut = null }
    if (reverbSend) { reverbSend.disconnect(); reverbSend = null }
    if (convolver) { convolver.disconnect(); convolver = null }
    if (reverbOut) { reverbOut.disconnect(); reverbOut = null }
    reverbLoaded.value = false
    loadedVariant = null
    ctx = null
  }

  return {
    // Delay
    delayEnabled: readonly(delayEnabled),
    delayTimeMs: readonly(delayTimeMs),
    delayFeedback: readonly(delayFeedback),
    delayMix: readonly(delayMix),
    setDelayEnabled,
    setDelayTime,
    setDelayFeedback,
    setDelayMix,
    syncDelayToBpm,

    // Reverb
    reverbEnabled: readonly(reverbEnabled),
    reverbMix: readonly(reverbMix),
    reverbVariant: readonly(reverbVariant),
    reverbLoaded: readonly(reverbLoaded),
    setReverbEnabled,
    setReverbMix,
    setReverbVariant,

    // Chain
    createChain,
    getInputNode,
    dispose,
  }
}
