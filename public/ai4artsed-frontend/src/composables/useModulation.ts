/**
 * Modulation bank: 3 ADSR envelopes + 2 LFOs with flexible target routing.
 *
 * Targets come in two flavors:
 *   - AudioParam targets (dca, dcf_cutoff, pitch, delay_*, reverb_*, lfo rates)
 *     → modulated via Web Audio scheduling / LFO connection
 *   - Callback targets (wt_scan)
 *     → modulated via requestAnimationFrame polling
 *
 * LFO modes:
 *   - 'free': runs continuously, phase never resets
 *   - 'trigger': phase resets to 0 on each note-on
 */
import { ref, readonly, type Ref } from 'vue'

export type ModTarget =
  | 'dca' | 'dcf_cutoff' | 'pitch'
  | 'delay_time' | 'delay_feedback' | 'delay_mix' | 'reverb_mix'
  | 'lfo1_rate' | 'lfo2_rate' | 'lfo1_depth' | 'lfo2_depth'
  | 'wt_scan'
  | 'none'

export type LfoWaveform = 'sine' | 'triangle' | 'square' | 'sawtooth'
export type LfoMode = 'free' | 'trigger'

export const MOD_TARGETS: ModTarget[] = [
  'none', 'dca', 'dcf_cutoff', 'pitch',
  'delay_time', 'delay_feedback', 'delay_mix', 'reverb_mix',
  'lfo1_rate', 'lfo2_rate', 'lfo1_depth', 'lfo2_depth', 'wt_scan',
]

export interface EnvState {
  attackMs: Ref<number>
  decayMs: Ref<number>
  sustain: Ref<number>
  releaseMs: Ref<number>
  amount: Ref<number>
  target: Ref<ModTarget>
  loop: Ref<boolean>
}

export interface LfoState {
  rate: Ref<number>
  depth: Ref<number>
  waveform: Ref<LfoWaveform>
  target: Ref<ModTarget>
  mode: Ref<LfoMode>
}

export function useModulation() {
  // ─── 3 Envelopes ───
  const envs: EnvState[] = [
    {
      attackMs: ref(0), decayMs: ref(0), sustain: ref(1), releaseMs: ref(0),
      amount: ref(1), target: ref<ModTarget>('dca'), loop: ref(false),
    },
    {
      attackMs: ref(0), decayMs: ref(0), sustain: ref(1), releaseMs: ref(0),
      amount: ref(0.5), target: ref<ModTarget>('none'), loop: ref(false),
    },
    {
      attackMs: ref(0), decayMs: ref(0), sustain: ref(1), releaseMs: ref(0),
      amount: ref(0.5), target: ref<ModTarget>('none'), loop: ref(false),
    },
  ]

  // ─── 2 LFOs ───
  const lfos: LfoState[] = [
    { rate: ref(2.0), depth: ref(0), waveform: ref<LfoWaveform>('sine'), target: ref<ModTarget>('none'), mode: ref<LfoMode>('free') },
    { rate: ref(0.5), depth: ref(0), waveform: ref<LfoWaveform>('triangle'), target: ref<ModTarget>('none'), mode: ref<LfoMode>('free') },
  ]

  // ─── Audio state ───
  let ctx: AudioContext | null = null
  const targetParams: Record<string, AudioParam | null> = {}
  const targetBaseGetters: Record<string, () => number> = {}

  // Callback targets (non-AudioParam, e.g. wt_scan)
  const callbackTargets: Record<string, (value: number) => void> = {}
  const callbackBaseGetters: Record<string, () => number> = {}

  // Envelope GainNodes (for DCA)
  const envGainNodes: (GainNode | null)[] = [null, null, null]
  const envLoopTimers: (ReturnType<typeof setTimeout> | null)[] = [null, null, null]

  // Callback envelope state (for rAF-driven ADSR on non-AudioParam targets)
  const cbEnvState: Array<{
    active: boolean; releasing: boolean
    startTime: number; releaseTime: number
    velocity: number
    rafId: number | null
  }> = [
    { active: false, releasing: false, startTime: 0, releaseTime: 0, velocity: 1, rafId: null },
    { active: false, releasing: false, startTime: 0, releaseTime: 0, velocity: 1, rafId: null },
    { active: false, releasing: false, startTime: 0, releaseTime: 0, velocity: 1, rafId: null },
  ]

  // LFO nodes
  const lfoOscs: (OscillatorNode | null)[] = [null, null]
  const lfoGains: (GainNode | null)[] = [null, null]

  // Track current LFO connection targets to avoid disconnect/reconnect glitches
  const lfoCurrentParams: (AudioParam | null)[] = [null, null]

  // LFO callback polling
  let lfoRafId: number | null = null
  const lfoAnalysers: (AnalyserNode | null)[] = [null, null]
  const lfoSampleBuf = new Float32Array(1)

  function init(ac: AudioContext): void {
    ctx = ac

    for (let i = 0; i < 3; i++) {
      envGainNodes[i] = ac.createGain()
      envGainNodes[i]!.gain.value = 0  // Closed gate — envelope opens it
    }

    for (let i = 0; i < 2; i++) {
      createLfoNodes(ac, i)
    }
  }

  function createLfoNodes(ac: AudioContext, idx: number): void {
    // Clean up old — disconnect from tracked param first to avoid orphaned connections
    if (lfoCurrentParams[idx]) {
      try { lfoGains[idx]?.disconnect(lfoCurrentParams[idx]!) } catch { /* noop */ }
      lfoCurrentParams[idx] = null
    }
    if (lfoOscs[idx]) { try { lfoOscs[idx]!.stop() } catch { /* noop */ }; lfoOscs[idx]!.disconnect() }
    if (lfoGains[idx]) lfoGains[idx]!.disconnect()
    if (lfoAnalysers[idx]) lfoAnalysers[idx]!.disconnect()

    const osc = ac.createOscillator()
    const gain = ac.createGain()
    const analyser = ac.createAnalyser()
    analyser.fftSize = 32

    osc.type = lfos[idx]!.waveform.value
    osc.frequency.value = lfos[idx]!.rate.value
    gain.gain.value = 0

    osc.connect(gain)
    gain.connect(analyser) // for callback target value readback

    osc.start()
    lfoOscs[idx] = osc
    lfoGains[idx] = gain
    lfoAnalysers[idx] = analyser
  }

  /**
   * Register AudioParam-based targets.
   */
  function setTargets(targets: Record<string, { param: AudioParam; baseValue: () => number }>): void {
    for (const [key, { param, baseValue }] of Object.entries(targets)) {
      targetParams[key] = param
      targetBaseGetters[key] = baseValue
    }

    // Also register LFO rate params as targets
    if (lfoOscs[0]) {
      targetParams['lfo1_rate'] = lfoOscs[0]!.frequency
      targetBaseGetters['lfo1_rate'] = () => lfos[0]!.rate.value
    }
    if (lfoGains[0]) {
      targetParams['lfo1_depth'] = lfoGains[0]!.gain
      targetBaseGetters['lfo1_depth'] = () => lfoGains[0]!.gain.value
    }
    if (lfoOscs[1]) {
      targetParams['lfo2_rate'] = lfoOscs[1]!.frequency
      targetBaseGetters['lfo2_rate'] = () => lfos[1]!.rate.value
    }
    if (lfoGains[1]) {
      targetParams['lfo2_depth'] = lfoGains[1]!.gain
      targetBaseGetters['lfo2_depth'] = () => lfoGains[1]!.gain.value
    }

    applyLfoRouting()
  }

  /**
   * Register callback-based targets (non-AudioParam, e.g. wt_scan).
   */
  function setCallbackTargets(targets: Record<string, { callback: (v: number) => void; baseValue: () => number }>): void {
    for (const [key, { callback, baseValue }] of Object.entries(targets)) {
      callbackTargets[key] = callback
      callbackBaseGetters[key] = baseValue
    }
  }

  function getDcaGainNode(): GainNode | null {
    return envGainNodes[0] ?? null
  }

  function isCallbackTarget(target: ModTarget): boolean {
    return target in callbackTargets
  }

  // ─── Envelope scheduling ───

  function triggerAttack(velocity = 1): void {
    if (!ctx) return
    for (let i = 0; i < 3; i++) {
      triggerEnvAttack(i, velocity)
    }
    // Retrigger LFOs in trigger mode
    for (let i = 0; i < 2; i++) {
      if (lfos[i]!.mode.value === 'trigger' && ctx) {
        createLfoNodes(ctx, i)
        applyLfoRouting()
      }
    }
    startLfoCallbackPolling()
  }

  function triggerRelease(): void {
    if (!ctx) return
    for (let i = 0; i < 3; i++) {
      triggerEnvRelease(i)
    }
  }

  function triggerEnvAttack(idx: number, velocity = 1): void {
    if (!ctx) return
    const env = envs[idx]!
    const target = env.target.value
    if (target === 'none') return

    if (envLoopTimers[idx]) { clearTimeout(envLoopTimers[idx]!); envLoopTimers[idx] = null }

    const now = ctx.currentTime
    const atk = env.attackMs.value / 1000
    const dec = env.decayMs.value / 1000
    const sus = env.sustain.value
    const amount = env.amount.value

    if (isCallbackTarget(target)) {
      // Callback target: drive via rAF
      const st = cbEnvState[idx]!
      st.active = true
      st.releasing = false
      st.startTime = performance.now()
      st.velocity = velocity
      if (!st.rafId) startCbEnvLoop(idx)
      return
    }

    if (target === 'dca') {
      const gain = envGainNodes[0]
      if (!gain) return
      const peak = velocity * amount
      const susLevel = sus * peak
      gain.gain.cancelScheduledValues(now)
      gain.gain.setValueAtTime(0, now)
      gain.gain.linearRampToValueAtTime(peak, now + Math.max(atk, 0.002))
      gain.gain.linearRampToValueAtTime(susLevel, now + Math.max(atk, 0.002) + Math.max(dec, 0.002))

      if (env.loop.value) {
        scheduleEnvLoop(idx, velocity, atk + dec)
      }
    } else {
      // AudioParam modulation
      const param = targetParams[target]
      if (!param) return
      const baseVal = targetBaseGetters[target]?.() ?? param.value

      let startVal: number
      let peakVal: number
      let susVal: number

      if (target === 'dcf_cutoff') {
        // Subtractive model: amount controls sweep range around cutoff slider.
        // amount=0: no sweep (stays at baseVal). amount=1: 20Hz→20kHz full sweep.
        // Start drops below base, peak rises above base — proportional to amount.
        const minFreq = 20
        startVal = Math.max(minFreq, baseVal * (1 - amount))
        peakVal = Math.min(20000, baseVal * (1 + amount * 8))
        susVal = Math.max(minFreq, startVal + (peakVal - startVal) * sus)
      } else {
        startVal = baseVal
        peakVal = baseVal + amount * baseVal
        susVal = baseVal + (peakVal - baseVal) * sus
      }

      param.cancelScheduledValues(now)
      if (target === 'dcf_cutoff') {
        param.setValueAtTime(Math.max(startVal, 20), now)
        param.exponentialRampToValueAtTime(Math.max(peakVal, 20), now + Math.max(atk, 0.002))
        param.exponentialRampToValueAtTime(Math.max(susVal, 20), now + Math.max(atk, 0.002) + Math.max(dec, 0.002))
      } else {
        param.setValueAtTime(Math.max(startVal, 0.001), now)
        param.linearRampToValueAtTime(peakVal, now + Math.max(atk, 0.002))
        param.linearRampToValueAtTime(susVal, now + Math.max(atk, 0.002) + Math.max(dec, 0.002))
      }

      if (env.loop.value) {
        scheduleEnvLoop(idx, velocity, atk + dec)
      }
    }
  }

  /**
   * Freeze current automation value, then ramp to target.
   * Uses cancelAndHoldAtTime where available (Chrome), falls back to
   * cancelScheduledValues + setValueAtTime for Firefox/Safari.
   */
  function holdAndRamp(param: AudioParam, target: number, now: number, duration: number): void {
    if (typeof param.cancelAndHoldAtTime === 'function') {
      param.cancelAndHoldAtTime(now)
    } else {
      // Fallback: cancel all automation, anchor at last known sustain value.
      // During sustain phase this is the susLevel. During attack/decay ramps
      // .value returns the intrinsic (not computed) value, so we compute it
      // from the envelope state. In practice, release during sustain is the
      // common case — the sustain value was the last ramp target.
      const current = param.value  // Best effort — correct during sustain
      param.cancelScheduledValues(now)
      param.setValueAtTime(current || 0.001, now)
    }
    param.linearRampToValueAtTime(target, now + Math.max(duration, 0.002))
  }

  function triggerEnvRelease(idx: number): void {
    if (!ctx) return
    const env = envs[idx]!
    const target = env.target.value
    if (target === 'none') return

    if (envLoopTimers[idx]) { clearTimeout(envLoopTimers[idx]!); envLoopTimers[idx] = null }

    if (isCallbackTarget(target)) {
      const st = cbEnvState[idx]!
      st.releasing = true
      st.releaseTime = performance.now()
      return
    }

    const now = ctx.currentTime
    const rel = env.releaseMs.value / 1000

    if (target === 'dca') {
      const gain = envGainNodes[0]
      if (!gain) return
      holdAndRamp(gain.gain, 0, now, rel)
    } else {
      const param = targetParams[target]
      if (!param) return
      if (target === 'dcf_cutoff') {
        const baseVal = targetBaseGetters[target]?.() ?? 1000
        const releaseTarget = Math.max(20, baseVal * (1 - env.amount.value))
        holdAndRamp(param, releaseTarget, now, rel)
      } else {
        const baseVal = targetBaseGetters[target]?.() ?? 1
        holdAndRamp(param, baseVal, now, rel)
      }
    }
  }

  function scheduleEnvLoop(idx: number, velocity: number, cycleTime: number): void {
    envLoopTimers[idx] = setTimeout(() => {
      if (envs[idx]!.loop.value && envs[idx]!.target.value !== 'none') {
        triggerEnvAttack(idx, velocity)
      }
    }, cycleTime * 1000)
  }

  // ─── Callback envelope (rAF-driven ADSR for non-AudioParam targets) ───

  function computeEnvValue(idx: number, now: number): number {
    const env = envs[idx]!
    const st = cbEnvState[idx]!
    const atk = env.attackMs.value
    const dec = env.decayMs.value
    const sus = env.sustain.value
    const rel = env.releaseMs.value
    const amount = env.amount.value

    if (st.releasing) {
      const elapsed = now - st.releaseTime
      if (elapsed >= rel) { st.active = false; return 0 }
      // Compute level at release start, then ramp to 0
      const preRelLevel = computeSustainLevel(idx, st.releaseTime - st.startTime)
      return preRelLevel * (1 - elapsed / Math.max(rel, 1)) * amount
    }

    const elapsed = now - st.startTime
    let level: number
    if (elapsed < atk) {
      level = atk > 0 ? elapsed / atk : 1
    } else if (elapsed < atk + dec) {
      const t = (elapsed - atk) / Math.max(dec, 1)
      level = 1 - t * (1 - sus)
    } else {
      level = sus
      // Loop: restart cycle
      if (env.loop.value && !st.releasing) {
        st.startTime = now - 0 // restart
        level = 0
      }
    }
    return level * amount * st.velocity
  }

  function computeSustainLevel(idx: number, elapsed: number): number {
    const env = envs[idx]!
    const atk = env.attackMs.value
    const dec = env.decayMs.value
    const sus = env.sustain.value
    if (elapsed < atk) return atk > 0 ? elapsed / atk : 1
    if (elapsed < atk + dec) return 1 - ((elapsed - atk) / Math.max(dec, 1)) * (1 - sus)
    return sus
  }

  function startCbEnvLoop(idx: number): void {
    const st = cbEnvState[idx]!
    const env = envs[idx]!

    function tick() {
      if (!st.active) { st.rafId = null; return }
      const target = env.target.value
      const cb = callbackTargets[target]
      const baseGet = callbackBaseGetters[target]
      if (cb && baseGet) {
        const envVal = computeEnvValue(idx, performance.now())
        const base = baseGet()
        // Additive: envelope sweeps value away from base position
        cb(base + envVal)
      }
      st.rafId = requestAnimationFrame(tick)
    }
    st.rafId = requestAnimationFrame(tick)
  }

  // ─── LFO callback polling (for non-AudioParam targets like wt_scan) ───

  function startLfoCallbackPolling(): void {
    if (lfoRafId !== null) return
    function poll() {
      let anyActive = false
      for (let i = 0; i < 2; i++) {
        const lfo = lfos[i]!
        const target = lfo.target.value
        if (target === 'none' || lfo.depth.value === 0) continue
        const cb = callbackTargets[target]
        if (!cb) continue
        const analyser = lfoAnalysers[i]
        if (!analyser) continue

        anyActive = true
        analyser.getFloatTimeDomainData(lfoSampleBuf)
        const lfoVal = lfoSampleBuf[0]! // -1..+1
        const baseGet = callbackBaseGetters[target]
        const base = baseGet?.() ?? 0.5
        // Additive bipolar: base ± depth (depth controls absolute sweep range 0-1)
        cb(base + lfoVal * lfo.depth.value)
      }
      if (anyActive) {
        lfoRafId = requestAnimationFrame(poll)
      } else {
        lfoRafId = null
      }
    }
    lfoRafId = requestAnimationFrame(poll)
  }

  function bypass(): void {
    if (!ctx) return
    const now = ctx.currentTime
    for (let i = 0; i < 3; i++) {
      if (envLoopTimers[i]) { clearTimeout(envLoopTimers[i]!); envLoopTimers[i] = null }
      cbEnvState[i]!.active = false
      const env = envs[i]!
      if (env.target.value === 'dca') {
        const gain = envGainNodes[0]
        if (gain) {
          gain.gain.cancelScheduledValues(now)
          gain.gain.setValueAtTime(1, now)
        }
      } else if (env.target.value !== 'none' && !isCallbackTarget(env.target.value)) {
        const param = targetParams[env.target.value]
        if (param) {
          param.cancelScheduledValues(now)
          param.setValueAtTime(targetBaseGetters[env.target.value]?.() ?? param.value, now)
        }
      }
    }
  }

  // ─── LFO routing ───

  function applyLfoRouting(): void {
    for (let i = 0; i < 2; i++) {
      const gain = lfoGains[i]
      const osc = lfoOscs[i]
      const lfo = lfos[i]!
      if (!gain || !osc) continue

      osc.frequency.value = lfo.rate.value
      osc.type = lfo.waveform.value

      const newTarget = lfo.target.value
      const inactive = newTarget === 'none' || lfo.depth.value === 0
      const isCallback = !inactive && isCallbackTarget(newTarget)
      const newParam = (!inactive && !isCallback) ? (targetParams[newTarget] ?? null) : null

      const prevParam = lfoCurrentParams[i]

      // Only reconnect if target changed — avoids disconnect/reconnect glitch
      if (newParam !== prevParam) {
        // Connect to new target BEFORE disconnecting old (atomic swap)
        if (newParam) gain.connect(newParam)
        if (prevParam) { try { gain.disconnect(prevParam) } catch { /* noop */ } }
        lfoCurrentParams[i] = newParam
      }

      // Ensure analyser is always connected (for callback target readback)
      const analyser = lfoAnalysers[i]
      if (analyser) { try { gain.connect(analyser) } catch { /* already connected */ } }

      if (inactive) {
        gain.gain.value = 0
        continue
      }

      if (isCallback) {
        gain.gain.value = 1
        startLfoCallbackPolling()
        continue
      }

      if (newParam) {
        const baseVal = targetBaseGetters[newTarget]?.() ?? newParam.value
        gain.gain.value = baseVal * lfo.depth.value
      } else {
        gain.gain.value = 0
      }
    }
  }

  // ─── Setters ───

  function setEnvParam(idx: number, key: keyof EnvState, value: number | boolean | ModTarget): void {
    const env = envs[idx]
    if (!env) return
    const r = env[key] as Ref<any>
    r.value = value
    if (key === 'target') applyLfoRouting()
  }

  function setLfoParam(idx: number, key: keyof LfoState, value: number | string): void {
    const lfo = lfos[idx]
    if (!lfo) return
    const r = lfo[key] as Ref<any>
    r.value = value

    const osc = lfoOscs[idx]
    if (osc && key === 'rate') osc.frequency.value = value as number
    if (osc && key === 'waveform') osc.type = value as OscillatorType

    if (key === 'target' || key === 'depth') applyLfoRouting()
  }

  function dispose(): void {
    for (let i = 0; i < 3; i++) {
      if (envLoopTimers[i]) clearTimeout(envLoopTimers[i]!)
      cbEnvState[i]!.active = false
      if (cbEnvState[i]!.rafId) cancelAnimationFrame(cbEnvState[i]!.rafId!)
      if (envGainNodes[i]) envGainNodes[i]!.disconnect()
    }
    if (lfoRafId !== null) cancelAnimationFrame(lfoRafId)
    for (let i = 0; i < 2; i++) {
      lfoCurrentParams[i] = null
      if (lfoOscs[i]) { try { lfoOscs[i]!.stop() } catch { /* noop */ }; lfoOscs[i]!.disconnect() }
      if (lfoGains[i]) lfoGains[i]!.disconnect()
      if (lfoAnalysers[i]) lfoAnalysers[i]!.disconnect()
    }
    ctx = null
  }

  return {
    envs,
    lfos,
    init,
    setTargets,
    setCallbackTargets,
    getDcaGainNode,
    triggerAttack,
    triggerRelease,
    bypass,
    setEnvParam,
    setLfoParam,
    applyLfoRouting,
    dispose,
  }
}
