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
  let feedbackFilter: BiquadFilterNode | null = null  // LP in feedback loop — analog warmth
  let delayOut: GainNode | null = null

  // Reverb
  let reverbSend: GainNode | null = null
  let convolver: ConvolverNode | null = null
  let reverbOut: GainNode | null = null

  // Limiter (brick-wall at end of chain)
  let limiter: DynamicsCompressorNode | null = null

  // Reactive state
  const delayEnabled = ref(false)
  const delayTimeMs = ref(250)
  const delayFeedback = ref(0.35)
  const delayDamp = ref(0.5)      // 0 = no damping (20kHz), 1 = max damping (500Hz)
  const delayDampFreq = ref(4000) // Display value in Hz
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

    // Limiter at end of chain (brick-wall, prevents clipping)
    limiter = ac.createDynamicsCompressor()
    limiter.threshold.value = -3   // dB — start limiting 3dB below clipping
    limiter.knee.value = 6         // dB — soft knee for musical response
    limiter.ratio.value = 20       // near brick-wall
    limiter.attack.value = 0.001   // 1ms — fast catch
    limiter.release.value = 0.1    // 100ms — smooth release
    limiter.connect(dest)

    const mixBus = limiter  // everything routes through limiter

    // Input splitter
    inputNode = ac.createGain()
    inputNode.gain.value = 1

    // Dry path
    dryGain = ac.createGain()
    dryGain.gain.value = 1
    inputNode.connect(dryGain)
    dryGain.connect(mixBus)

    // Delay path
    delaySend = ac.createGain()
    delaySend.gain.value = 0
    delayNode = ac.createDelay(5.0)
    delayNode.delayTime.value = delayTimeMs.value / 1000
    feedbackGain = ac.createGain()
    feedbackGain.gain.value = delayFeedback.value
    delayOut = ac.createGain()
    delayOut.gain.value = 1

    // Analog-style feedback damping: LP filter in feedback path
    // Each repeat loses highs, like BBD/tape delay
    feedbackFilter = ac.createBiquadFilter()
    feedbackFilter.type = 'lowpass'
    feedbackFilter.frequency.value = Math.round(20000 * Math.pow(500 / 20000, delayDamp.value))
    feedbackFilter.Q.value = 0.7           // Butterworth, no resonance

    inputNode.connect(delaySend)
    delaySend.connect(delayNode)
    delayNode.connect(feedbackGain)
    feedbackGain.connect(feedbackFilter)
    feedbackFilter.connect(delayNode)  // feedback loop with damping
    delayNode.connect(delayOut)
    delayOut.connect(mixBus)

    // Reverb path
    reverbSend = ac.createGain()
    reverbSend.gain.value = 0
    convolver = ac.createConvolver()
    reverbOut = ac.createGain()
    reverbOut.gain.value = 1

    inputNode.connect(reverbSend)
    reverbSend.connect(convolver)
    convolver.connect(reverbOut)
    reverbOut.connect(mixBus)

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

  /** Damping 0–1: 0 = bright (20kHz), 1 = dark (500Hz). Exponential mapping. */
  function setDelayDamp(d: number): void {
    delayDamp.value = Math.max(0, Math.min(1, d))
    // Exp mapping: 0 → 20000Hz, 1 → 500Hz
    const freq = Math.round(20000 * Math.pow(500 / 20000, delayDamp.value))
    delayDampFreq.value = freq
    if (feedbackFilter) feedbackFilter.frequency.value = freq
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

  function getOutputNode(): DynamicsCompressorNode | null {
    return limiter
  }

  /** Expose AudioParams for modulation routing */
  function getModTargets(): Record<string, { param: AudioParam; baseValue: () => number }> {
    const targets: Record<string, { param: AudioParam; baseValue: () => number }> = {}
    if (delayNode) targets.delay_time = { param: delayNode.delayTime, baseValue: () => delayTimeMs.value / 1000 }
    if (feedbackGain) targets.delay_feedback = { param: feedbackGain.gain, baseValue: () => delayFeedback.value }
    if (delaySend) targets.delay_mix = { param: delaySend.gain, baseValue: () => delayEnabled.value ? delayMix.value : 0 }
    if (reverbSend) targets.reverb_mix = { param: reverbSend.gain, baseValue: () => reverbEnabled.value ? reverbMix.value : 0 }
    return targets
  }

  function dispose(): void {
    if (inputNode) { inputNode.disconnect(); inputNode = null }
    if (dryGain) { dryGain.disconnect(); dryGain = null }
    if (delaySend) { delaySend.disconnect(); delaySend = null }
    if (delayNode) { delayNode.disconnect(); delayNode = null }
    if (feedbackGain) { feedbackGain.disconnect(); feedbackGain = null }
    if (feedbackFilter) { feedbackFilter.disconnect(); feedbackFilter = null }
    if (delayOut) { delayOut.disconnect(); delayOut = null }
    if (reverbSend) { reverbSend.disconnect(); reverbSend = null }
    if (convolver) { convolver.disconnect(); convolver = null }
    if (reverbOut) { reverbOut.disconnect(); reverbOut = null }
    if (limiter) { limiter.disconnect(); limiter = null }
    reverbLoaded.value = false
    loadedVariant = null
    ctx = null
  }

  return {
    // Delay
    delayEnabled: readonly(delayEnabled),
    delayTimeMs: readonly(delayTimeMs),
    delayFeedback: readonly(delayFeedback),
    delayDamp: readonly(delayDamp),
    delayDampFreq: readonly(delayDampFreq),
    delayMix: readonly(delayMix),
    setDelayEnabled,
    setDelayTime,
    setDelayFeedback,
    setDelayDamp,
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
    getOutputNode,
    getModTargets,
    dispose,
  }
}
