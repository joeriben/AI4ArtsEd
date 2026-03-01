/**
 * Step Sequencer composable for Crossmodal Lab Synth tab.
 *
 * Chris Wilson "Tale of Two Clocks" scheduler: setInterval (25ms) polls
 * + AudioContext lookahead (100ms) for sample-accurate timing.
 *
 * Drives the looper with rhythmic melodic patterns — each step retriggers
 * audio at a new pitch with its own velocity and gate length, so the ADSR
 * envelope actually shapes every note.
 *
 * Supports internal BPM clock and external MIDI clock (24ppqn).
 */
import { ref, readonly, type Ref } from 'vue'
import type { MidiClockType } from './useWebMidi'

export interface Step {
  note: number    // MIDI note number
  velocity: number // 0-1
  gate: number    // 0-1 fraction of step duration
}

export interface Pattern {
  name: string   // i18n key suffix
  steps: Step[]
}

// 8 preset patterns
const PATTERNS: Pattern[] = [
  {
    name: 'arpeggio_up',
    steps: [
      { note: 48, velocity: 1.0, gate: 0.8 },
      { note: 52, velocity: 0.8, gate: 0.8 },
      { note: 55, velocity: 0.8, gate: 0.8 },
      { note: 60, velocity: 1.0, gate: 0.8 },
    ],
  },
  {
    name: 'arpeggio_down',
    steps: [
      { note: 60, velocity: 1.0, gate: 0.8 },
      { note: 55, velocity: 0.8, gate: 0.8 },
      { note: 52, velocity: 0.8, gate: 0.8 },
      { note: 48, velocity: 1.0, gate: 0.8 },
    ],
  },
  {
    name: 'arpeggio_updown',
    steps: [
      { note: 48, velocity: 1.0, gate: 0.8 },
      { note: 52, velocity: 0.8, gate: 0.8 },
      { note: 55, velocity: 0.8, gate: 0.8 },
      { note: 60, velocity: 1.0, gate: 0.8 },
      { note: 55, velocity: 0.8, gate: 0.8 },
      { note: 52, velocity: 0.8, gate: 0.8 },
    ],
  },
  {
    name: 'octaves',
    steps: [
      { note: 48, velocity: 1.0, gate: 0.7 },
      { note: 60, velocity: 0.9, gate: 0.7 },
      { note: 48, velocity: 0.9, gate: 0.7 },
      { note: 60, velocity: 1.0, gate: 0.7 },
    ],
  },
  {
    name: 'power_chord',
    steps: [
      { note: 48, velocity: 1.0, gate: 0.9 },
      { note: 55, velocity: 0.9, gate: 0.9 },
      { note: 48, velocity: 0.9, gate: 0.9 },
      { note: 55, velocity: 1.0, gate: 0.9 },
    ],
  },
  {
    name: 'minor_pentatonic',
    steps: [
      { note: 48, velocity: 1.0, gate: 0.8 },
      { note: 51, velocity: 0.8, gate: 0.8 },
      { note: 53, velocity: 0.9, gate: 0.8 },
      { note: 55, velocity: 0.8, gate: 0.8 },
      { note: 58, velocity: 1.0, gate: 0.8 },
    ],
  },
  {
    name: 'bass_groove',
    steps: [
      { note: 36, velocity: 1.0, gate: 0.9 },
      { note: 36, velocity: 0.5, gate: 0.4 },
      { note: 43, velocity: 1.0, gate: 0.9 },
      { note: 43, velocity: 0.5, gate: 0.4 },
      { note: 46, velocity: 1.0, gate: 0.9 },
      { note: 46, velocity: 0.5, gate: 0.4 },
      { note: 41, velocity: 1.0, gate: 0.9 },
      { note: 41, velocity: 0.5, gate: 0.4 },
    ],
  },
  {
    name: 'trance_gate',
    steps: [
      { note: 48, velocity: 1.0, gate: 0.9 },
      { note: 48, velocity: 0.4, gate: 0.3 },
      { note: 48, velocity: 1.0, gate: 0.9 },
      { note: 48, velocity: 0.4, gate: 0.3 },
      { note: 48, velocity: 1.0, gate: 0.9 },
      { note: 48, velocity: 0.4, gate: 0.3 },
      { note: 48, velocity: 1.0, gate: 0.9 },
      { note: 48, velocity: 0.4, gate: 0.3 },
    ],
  },
]

export function useStepSequencer() {
  const isPlaying = ref(false)
  const currentStep = ref(0)
  const bpm = ref(120)
  const patternIndex = ref(0)
  const pattern = ref<Pattern>(PATTERNS[0]!)
  const midiClockActive = ref(false)
  const midiClockBpm = ref(0)
  const stepCount = ref(PATTERNS[0]!.steps.length)

  let audioCtx: AudioContext | null = null
  let schedulerInterval: ReturnType<typeof setInterval> | null = null
  let nextStepTime = 0 // AudioContext time of the next step
  let scheduledStep = 0 // Next step index to schedule

  // Gate-off timers: step index -> timer ID
  const gateTimers = new Map<number, ReturnType<typeof setTimeout>>()

  // Callbacks
  let noteOnCb: ((note: number, velocity: number) => void) | null = null
  let noteOffCb: (() => void) | null = null

  // MIDI clock EMA state
  let lastClockTime = 0
  let emaInterval = 0
  let clockPulseCount = 0

  const SCHEDULER_INTERVAL_MS = 25
  const LOOKAHEAD_SEC = 0.1

  function setCallbacks(
    onNoteOn: (note: number, velocity: number) => void,
    onNoteOff: () => void,
  ) {
    noteOnCb = onNoteOn
    noteOffCb = onNoteOff
  }

  function getEffectiveBpm(): number {
    return midiClockActive.value ? midiClockBpm.value : bpm.value
  }

  function stepDurationSec(): number {
    // 16th notes: quarter note / 4
    return (60 / getEffectiveBpm()) / 4
  }

  function scheduleStep(stepIdx: number, time: number) {
    const step = pattern.value.steps[stepIdx]
    if (!step) return

    const now = audioCtx?.currentTime ?? 0
    const delayMs = Math.max(0, (time - now) * 1000)
    const gateDurMs = step.gate * stepDurationSec() * 1000

    // Schedule noteOn
    setTimeout(() => {
      if (!isPlaying.value) return
      currentStep.value = stepIdx
      noteOnCb?.(step.note, step.velocity)
    }, delayMs)

    // Cancel any pending gate-off for this step index
    const existingTimer = gateTimers.get(stepIdx)
    if (existingTimer != null) clearTimeout(existingTimer)

    // Schedule noteOff at end of gate
    const offTimer = setTimeout(() => {
      if (!isPlaying.value) return
      gateTimers.delete(stepIdx)
      noteOffCb?.()
    }, delayMs + gateDurMs)
    gateTimers.set(stepIdx, offTimer)
  }

  function schedulerTick() {
    if (!audioCtx || !isPlaying.value) return
    const endWindow = audioCtx.currentTime + LOOKAHEAD_SEC

    while (nextStepTime < endWindow) {
      const stepIdx = scheduledStep % pattern.value.steps.length
      scheduleStep(stepIdx, nextStepTime)
      nextStepTime += stepDurationSec()
      scheduledStep++
    }
  }

  function start(ac: AudioContext) {
    if (isPlaying.value) return
    audioCtx = ac
    isPlaying.value = true
    scheduledStep = 0
    currentStep.value = 0
    nextStepTime = ac.currentTime + 0.05 // Small offset to avoid scheduling in the past

    schedulerInterval = setInterval(schedulerTick, SCHEDULER_INTERVAL_MS)
    schedulerTick() // Fire immediately
  }

  function stop() {
    isPlaying.value = false
    if (schedulerInterval != null) {
      clearInterval(schedulerInterval)
      schedulerInterval = null
    }
    // Cancel all pending gate timers
    for (const timer of gateTimers.values()) clearTimeout(timer)
    gateTimers.clear()
    currentStep.value = 0
    scheduledStep = 0
  }

  function setBpm(newBpm: number) {
    bpm.value = Math.max(60, Math.min(200, newBpm))
  }

  function setPattern(idx: number) {
    if (idx < 0 || idx >= PATTERNS.length) return
    patternIndex.value = idx
    pattern.value = PATTERNS[idx]!
    stepCount.value = pattern.value.steps.length
    // Reset to step 0 on pattern change
    if (isPlaying.value) {
      // Cancel pending gates and restart scheduling from step 0
      for (const timer of gateTimers.values()) clearTimeout(timer)
      gateTimers.clear()
      scheduledStep = 0
      currentStep.value = 0
      if (audioCtx) {
        nextStepTime = audioCtx.currentTime + 0.05
      }
    }
  }

  function handleMidiClock(type: MidiClockType) {
    const now = performance.now()
    if (type === 'start') {
      midiClockActive.value = true
      clockPulseCount = 0
      lastClockTime = now
      if (!isPlaying.value && audioCtx) start(audioCtx)
      return
    }
    if (type === 'stop') {
      midiClockActive.value = false
      midiClockBpm.value = 0
      clockPulseCount = 0
      stop()
      return
    }
    // type === 'clock' (0xF8): 24 pulses per quarter note
    if (!midiClockActive.value) {
      midiClockActive.value = true
      lastClockTime = now
      clockPulseCount = 1
      return
    }
    clockPulseCount++
    const interval = now - lastClockTime
    lastClockTime = now

    if (interval > 0 && interval < 1000) {
      // EMA smoothing (alpha = 0.2)
      if (emaInterval === 0) {
        emaInterval = interval
      } else {
        emaInterval = 0.2 * interval + 0.8 * emaInterval
      }
      // BPM from 24ppqn: quarter note = 24 pulses
      const quarterNoteMs = emaInterval * 24
      if (quarterNoteMs > 0) {
        midiClockBpm.value = Math.round(60000 / quarterNoteMs)
      }
    }
  }

  function dispose() {
    stop()
    noteOnCb = null
    noteOffCb = null
    midiClockActive.value = false
    midiClockBpm.value = 0
    clockPulseCount = 0
    emaInterval = 0
    audioCtx = null
  }

  return {
    isPlaying: readonly(isPlaying),
    currentStep: readonly(currentStep),
    bpm: readonly(bpm) as Readonly<Ref<number>>,
    patternIndex: readonly(patternIndex),
    pattern: readonly(pattern) as Readonly<Ref<Pattern>>,
    stepCount: readonly(stepCount),
    midiClockActive: readonly(midiClockActive),
    midiClockBpm: readonly(midiClockBpm),
    patterns: PATTERNS,
    start,
    stop,
    setBpm,
    setPattern,
    setCallbacks,
    handleMidiClock,
    dispose,
  }
}
