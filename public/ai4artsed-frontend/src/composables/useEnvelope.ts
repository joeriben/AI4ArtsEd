/**
 * ADSR envelope composable for Crossmodal Lab monophonic synth.
 *
 * Wraps a single GainNode driven by Web Audio AudioParam scheduling.
 * Provides triggerAttack / triggerRelease for MIDI note-on/off and
 * bypass() for non-MIDI playback (sets gain=1, no envelope).
 */
import { ref, computed } from 'vue'

export function useEnvelope() {
  const attackMs = ref(0)
  const decayMs = ref(0)
  const sustain = ref(1.0)
  const releaseMs = ref(0)

  /** True when all ADSR values are at neutral defaults (envelope has no effect). */
  const isNeutral = computed(() =>
    attackMs.value === 0 && decayMs.value === 0 && sustain.value >= 1.0 && releaseMs.value === 0,
  )

  let gainNode: GainNode | null = null
  let releaseTimer: ReturnType<typeof setTimeout> | null = null

  /** Create the envelope GainNode. Call once after AudioContext exists. */
  function createNode(ac: AudioContext): GainNode {
    gainNode = ac.createGain()
    gainNode.gain.value = 0
    return gainNode
  }

  /** Note-on: ramp current → peak (velocity) → sustain level. */
  function triggerAttack(velocity = 1): void {
    if (!gainNode) return
    const now = gainNode.context.currentTime
    const atk = attackMs.value / 1000
    const dec = decayMs.value / 1000
    const sus = sustain.value * velocity

    if (releaseTimer) { clearTimeout(releaseTimer); releaseTimer = null }

    // cancelAndHoldAtTime freezes at the current interpolated value —
    // no jump if re-triggering during sustain or release phase.
    gainNode.gain.cancelAndHoldAtTime(now)
    if (atk > 0) {
      gainNode.gain.linearRampToValueAtTime(velocity, now + atk)
    } else {
      gainNode.gain.setValueAtTime(velocity, now)
    }
    if (dec > 0) {
      gainNode.gain.linearRampToValueAtTime(sus, now + atk + dec)
    } else {
      gainNode.gain.setValueAtTime(sus, now + atk)
    }
  }

  /**
   * Note-off: ramp from current interpolated level → 0.
   * Uses cancelAndHoldAtTime to capture the true current value,
   * then ramps to zero. No echo/click from stale .value reads.
   */
  function triggerRelease(onComplete?: () => void): void {
    if (!gainNode) return
    const now = gainNode.context.currentTime
    const rel = releaseMs.value / 1000

    // Freeze at current interpolated value, then ramp to 0
    gainNode.gain.cancelAndHoldAtTime(now)
    if (rel > 0) {
      gainNode.gain.linearRampToValueAtTime(0, now + rel)
    } else {
      gainNode.gain.setValueAtTime(0, now)
    }

    if (onComplete) {
      if (releaseTimer) clearTimeout(releaseTimer)
      releaseTimer = setTimeout(onComplete, releaseMs.value + 50)
    }
  }

  /** Bypass envelope: cancel scheduling, set gain=1 immediately (for non-MIDI playback). */
  function bypass(): void {
    if (!gainNode) return
    const now = gainNode.context.currentTime
    if (releaseTimer) { clearTimeout(releaseTimer); releaseTimer = null }
    gainNode.gain.cancelScheduledValues(now)
    gainNode.gain.setValueAtTime(1, now)
  }

  /**
   * Apply ADSR gain curve to a Float32Array of samples (offline, for export).
   * Mutates the array in-place. Returns immediately if envelope is neutral.
   */
  function applyToSamples(samples: Float32Array, sampleRate: number): void {
    if (isNeutral.value) return
    const a = attackMs.value / 1000
    const d = decayMs.value / 1000
    const s = sustain.value
    const r = releaseMs.value / 1000
    const len = samples.length
    const aSamples = Math.floor(a * sampleRate)
    const dSamples = Math.floor(d * sampleRate)
    const rSamples = Math.floor(r * sampleRate)
    const releaseStart = Math.max(0, len - rSamples)

    for (let i = 0; i < len; i++) {
      let gain: number
      if (i < aSamples) {
        // Attack: 0 → 1
        gain = aSamples > 0 ? i / aSamples : 1
      } else if (i < aSamples + dSamples) {
        // Decay: 1 → sustain
        const t = (i - aSamples) / dSamples
        gain = 1 - t * (1 - s)
      } else if (i < releaseStart) {
        // Sustain
        gain = s
      } else {
        // Release: sustain → 0
        const t = rSamples > 0 ? (i - releaseStart) / rSamples : 1
        gain = s * (1 - t)
      }
      samples[i]! *= gain
    }
  }

  function dispose(): void {
    if (releaseTimer) { clearTimeout(releaseTimer); releaseTimer = null }
    if (gainNode) { gainNode.disconnect(); gainNode = null }
  }

  return {
    attackMs,
    decayMs,
    sustain,
    releaseMs,
    isNeutral,
    createNode,
    triggerAttack,
    triggerRelease,
    bypass,
    applyToSamples,
    dispose,
  }
}
