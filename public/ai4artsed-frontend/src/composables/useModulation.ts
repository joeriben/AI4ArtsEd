/**
 * Modulation bank: 3 ADSR envelopes + 2 LFOs with flexible target routing.
 *
 * Each modulator is independently assignable to a target AudioParam.
 * Targets are registered via setTargets() after audio nodes are created.
 *
 * Envelopes:
 *   - ADSR + amount (depth of modulation)
 *   - Loop toggle: after decay→sustain, restart attack (ADS cycle)
 *   - triggerAttack() / triggerRelease() called from MIDI/sequencer
 *
 * LFOs:
 *   - OscillatorNode → GainNode → target AudioParam (additive)
 *   - Rate, depth, waveform (sine/tri/sq/saw)
 *
 * Targets:
 *   - 'dca'         → amplitude GainNode.gain
 *   - 'dcf_cutoff'  → BiquadFilterNode.frequency
 *   - 'pitch'       → AudioBufferSourceNode.playbackRate (via intermediary)
 *   - 'none'        → unassigned
 */
import { ref, readonly, type Ref } from 'vue'

export type ModTarget = 'dca' | 'dcf_cutoff' | 'pitch' | 'none'
export type LfoWaveform = 'sine' | 'triangle' | 'square' | 'sawtooth'

export const MOD_TARGETS: ModTarget[] = ['none', 'dca', 'dcf_cutoff', 'pitch']

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
    { rate: ref(2.0), depth: ref(0), waveform: ref<LfoWaveform>('sine'), target: ref<ModTarget>('none') },
    { rate: ref(0.5), depth: ref(0), waveform: ref<LfoWaveform>('triangle'), target: ref<ModTarget>('none') },
  ]

  // ─── Audio state ───
  let ctx: AudioContext | null = null
  const targetParams: Record<string, AudioParam | null> = {}
  // Base value getters — read current value at trigger time, not cached from init
  const targetBaseGetters: Record<string, () => number> = {}

  // Envelope GainNodes (one per envelope, used for DCA-type modulation)
  const envGainNodes: (GainNode | null)[] = [null, null, null]
  const envLoopTimers: (ReturnType<typeof setTimeout> | null)[] = [null, null, null]

  // LFO nodes
  const lfoOscs: (OscillatorNode | null)[] = [null, null]
  const lfoGains: (GainNode | null)[] = [null, null]

  /**
   * Initialize with AudioContext. Call once.
   */
  function init(ac: AudioContext): void {
    ctx = ac

    // Create envelope GainNodes (for DCA envelopes — inserted in signal chain)
    for (let i = 0; i < 3; i++) {
      envGainNodes[i] = ac.createGain()
      envGainNodes[i]!.gain.value = 1
    }

    // Create LFO oscillators
    for (let i = 0; i < 2; i++) {
      const osc = ac.createOscillator()
      const gain = ac.createGain()
      osc.type = lfos[i]!.waveform.value
      osc.frequency.value = lfos[i]!.rate.value
      gain.gain.value = 0
      osc.connect(gain)
      osc.start()
      lfoOscs[i] = osc
      lfoGains[i] = gain
    }
  }

  /**
   * Register target AudioParams. Call after all audio nodes are created.
   * For 'dca', pass the GainNode.gain that controls amplitude.
   * Base values are used as the "home" position for envelope release.
   */
  function setTargets(targets: Record<string, { param: AudioParam; baseValue: () => number }>): void {
    for (const [key, { param, baseValue }] of Object.entries(targets)) {
      targetParams[key] = param
      targetBaseGetters[key] = baseValue
    }
    applyLfoRouting()
  }

  /**
   * Get the first DCA envelope's GainNode for signal chain insertion.
   * Chain: source → envGainNodes[0] → ... → destination
   * Only envelope 0 is in the signal path as a GainNode. Envelopes 1/2
   * modulate their targets via AudioParam scheduling (additive), not
   * signal-chain insertion.
   */
  function getDcaGainNode(): GainNode | null {
    return envGainNodes[0] ?? null
  }

  // ─── Envelope scheduling ───

  function triggerAttack(velocity = 1): void {
    if (!ctx) return
    for (let i = 0; i < 3; i++) {
      triggerEnvAttack(i, velocity)
    }
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

    if (target === 'dca') {
      // DCA envelope: modulate the GainNode in the signal chain
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
      // AudioParam modulation (dcf_cutoff, pitch): additive scheduling
      const param = targetParams[target]
      if (!param) return
      const baseVal = targetBaseGetters[target]?.() ?? param.value
      const peakVal = baseVal + amount * baseVal // modulate by `amount` fraction of base
      const susVal = baseVal + (peakVal - baseVal) * sus

      param.cancelScheduledValues(now)
      param.setValueAtTime(baseVal, now)
      if (target === 'dcf_cutoff') {
        // Exponential ramps for frequency
        param.exponentialRampToValueAtTime(Math.max(peakVal, 20), now + Math.max(atk, 0.002))
        param.exponentialRampToValueAtTime(Math.max(susVal, 20), now + Math.max(atk, 0.002) + Math.max(dec, 0.002))
      } else {
        // Linear ramps for pitch/other
        param.linearRampToValueAtTime(peakVal, now + Math.max(atk, 0.002))
        param.linearRampToValueAtTime(susVal, now + Math.max(atk, 0.002) + Math.max(dec, 0.002))
      }

      if (env.loop.value) {
        scheduleEnvLoop(idx, velocity, atk + dec)
      }
    }
  }

  function triggerEnvRelease(idx: number): void {
    if (!ctx) return
    const env = envs[idx]!
    const target = env.target.value
    if (target === 'none') return

    if (envLoopTimers[idx]) { clearTimeout(envLoopTimers[idx]!); envLoopTimers[idx] = null }

    const now = ctx.currentTime
    const rel = env.releaseMs.value / 1000

    if (target === 'dca') {
      const gain = envGainNodes[0]
      if (!gain) return
      const current = gain.gain.value
      gain.gain.cancelScheduledValues(now)
      gain.gain.setValueAtTime(current, now)
      gain.gain.linearRampToValueAtTime(0, now + Math.max(rel, 0.002))
    } else {
      const param = targetParams[target]
      if (!param) return
      const baseVal = targetBaseGetters[target]?.() ?? 1
      const current = param.value
      param.cancelScheduledValues(now)
      param.setValueAtTime(Math.max(current, 0.001), now)
      if (target === 'dcf_cutoff') {
        param.exponentialRampToValueAtTime(Math.max(baseVal, 20), now + Math.max(rel, 0.002))
      } else {
        param.linearRampToValueAtTime(baseVal, now + Math.max(rel, 0.002))
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

  /**
   * Bypass all envelopes: set DCA gain to 1, cancel all scheduling.
   * Used for non-MIDI playback (direct generate+play).
   */
  function bypass(): void {
    if (!ctx) return
    const now = ctx.currentTime
    for (let i = 0; i < 3; i++) {
      if (envLoopTimers[i]) { clearTimeout(envLoopTimers[i]!); envLoopTimers[i] = null }
      const env = envs[i]!
      if (env.target.value === 'dca') {
        const gain = envGainNodes[0]
        if (gain) {
          gain.gain.cancelScheduledValues(now)
          gain.gain.setValueAtTime(1, now)
        }
      } else if (env.target.value !== 'none') {
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

      // Disconnect from previous target
      try { gain.disconnect() } catch { /* noop */ }

      osc.frequency.value = lfo.rate.value
      osc.type = lfo.waveform.value

      if (lfo.target.value === 'none' || lfo.depth.value === 0) {
        gain.gain.value = 0
        continue
      }

      const param = targetParams[lfo.target.value]
      if (!param) { gain.gain.value = 0; continue }

      const baseVal = targetBaseGetters[lfo.target.value]?.() ?? param.value
      // Depth as fraction of base value (e.g., depth=0.5 modulates ±50% of base)
      gain.gain.value = baseVal * lfo.depth.value
      gain.connect(param)
    }
  }

  // ─── Setters ───

  function setEnvParam(idx: number, key: keyof EnvState, value: number | boolean | ModTarget): void {
    const env = envs[idx]
    if (!env) return
    const r = env[key] as Ref<any>
    r.value = value
    if (key === 'target') applyLfoRouting() // targets may share params
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
      if (envGainNodes[i]) envGainNodes[i]!.disconnect()
    }
    for (let i = 0; i < 2; i++) {
      if (lfoOscs[i]) { lfoOscs[i]!.stop(); lfoOscs[i]!.disconnect() }
      if (lfoGains[i]) lfoGains[i]!.disconnect()
    }
    ctx = null
  }

  return {
    envs,
    lfos,
    init,
    setTargets,
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
