/**
 * Step Sequencer composable for Crossmodal Lab Synth tab.
 *
 * A proper step sequencer with user-editable grid:
 * - Selectable step count: 5 (Eastcoast!), 8, 16
 * - Each step: active toggle, semitone offset, velocity, gate
 * - Preset patterns as grid initializers (not fixed arpeggiator)
 *
 * Chris Wilson "Tale of Two Clocks" scheduler: setInterval (25ms) polls
 * + AudioContext lookahead (100ms) for sample-accurate timing.
 *
 * Supports internal BPM clock and external MIDI clock (24ppqn).
 */
import { ref, reactive, readonly, computed, type Ref } from 'vue'
import type { MidiClockType } from './useWebMidi'

export interface Step {
  active: boolean    // toggle on/off
  semitone: number   // -24 to +24 offset from base note (C3 = 0)
  velocity: number   // 0-1
  gate: number       // 0-1 fraction of step duration
}

export interface Preset {
  name: string   // i18n key suffix
  steps: Step[]
}

export type StepCountOption = 5 | 8 | 16 | 32
export const STEP_COUNT_OPTIONS: StepCountOption[] = [5, 8, 16, 32]

/** Note division: how long each step lasts relative to a beat */
export type NoteDivision = '1/1' | '1/2' | '1/4' | '1/8' | '1/16'
export const NOTE_DIVISIONS: NoteDivision[] = ['1/1', '1/2', '1/4', '1/8', '1/16']
const DIVISION_FACTORS: Record<NoteDivision, number> = {
  '1/1': 4, '1/2': 2, '1/4': 1, '1/8': 0.5, '1/16': 0.25,
}

function makeStep(semitone = 0, velocity = 0.8, gate = 0.8, active = true): Step {
  return { active, semitone, velocity, gate }
}

// Preset patterns — used as grid initializers, user can modify after loading.
// Named after sequencer traditions, not arpeggios.
const PRESETS: Preset[] = [
  {
    // Eastcoast classic: minor pentatonic, 5 steps, accented root
    // Moog/Buchla-era East Coast modular — melodic, tonal center
    name: 'eastcoast',
    steps: [
      makeStep(0, 1.0, 0.9),   // root, accent
      makeStep(3, 0.7, 0.8),   // minor 3rd
      makeStep(5, 0.8, 0.8),   // 4th
      makeStep(7, 0.7, 0.8),   // 5th
      makeStep(10, 0.9, 0.7),  // minor 7th
    ],
  },
  {
    // Westcoast: non-standard intervals, varied gates, exploratory
    // Buchla-inspired — less tonal, more timbral
    name: 'westcoast',
    steps: [
      makeStep(0, 1.0, 0.6),   // root, short gate
      makeStep(6, 0.6, 1.0),   // tritone, long gate
      makeStep(2, 0.8, 0.4),   // major 2nd, staccato
      makeStep(9, 0.5, 0.9),   // major 6th, soft
      makeStep(5, 0.9, 0.5),   // 4th
      makeStep(11, 0.4, 1.0),  // major 7th, quiet + legato
      makeStep(1, 0.7, 0.3),   // minor 2nd, staccato
      makeStep(8, 0.8, 0.7),   // augmented 5th
    ],
  },
  {
    // British: New Order / Depeche Mode — 16th note bass sequences
    // Driving octave-root patterns with syncopation
    name: 'british',
    steps: [
      makeStep(0, 1.0, 0.9),   // root accent
      makeStep(0, 0.5, 0.3),   // ghost note
      makeStep(0, 0.7, 0.6),
      makeStep(12, 0.9, 0.4),  // octave, short
      makeStep(0, 0.8, 0.9),
      makeStep(0, 0.3, 0.2, false), // rest
      makeStep(7, 0.8, 0.6),   // 5th
      makeStep(5, 0.7, 0.5),   // 4th
    ],
  },
  {
    // Kraftwerk: precise, mechanical, equal velocity, strict gate
    // Robotic feel, chromatic movement, 16 steps
    name: 'kraftwerk',
    steps: [
      makeStep(0, 0.9, 0.5), makeStep(0, 0.9, 0.5),
      makeStep(0, 0.9, 0.5), makeStep(0, 0.9, 0.5),
      makeStep(3, 0.9, 0.5), makeStep(3, 0.9, 0.5),
      makeStep(5, 0.9, 0.5), makeStep(5, 0.9, 0.5),
      makeStep(7, 0.9, 0.5), makeStep(7, 0.9, 0.5),
      makeStep(5, 0.9, 0.5), makeStep(5, 0.9, 0.5),
      makeStep(3, 0.9, 0.5), makeStep(3, 0.9, 0.5),
      makeStep(0, 0.9, 0.5), makeStep(0, 0.9, 0.5),
    ],
  },
  {
    // Synthwave: retro 80s arpeggiated chords, wide intervals, pumping gates
    name: 'synthwave',
    steps: [
      makeStep(0, 1.0, 0.9),   // root
      makeStep(7, 0.7, 0.7),   // 5th
      makeStep(12, 0.8, 0.7),  // octave
      makeStep(16, 0.6, 0.6),  // major 3rd + octave
      makeStep(19, 0.9, 0.8),  // 5th + octave
      makeStep(16, 0.6, 0.6),
      makeStep(12, 0.8, 0.7),
      makeStep(7, 0.7, 0.7),
    ],
  },
  {
    // Trance gate: same note, rhythmic gating creates pattern from texture
    name: 'trance_gate',
    steps: [
      makeStep(0, 1.0, 0.9), makeStep(0, 0.4, 0.3),
      makeStep(0, 1.0, 0.9), makeStep(0, 0.4, 0.3),
      makeStep(0, 1.0, 0.9), makeStep(0, 0.4, 0.3),
      makeStep(0, 1.0, 0.9), makeStep(0, 0.4, 0.3),
    ],
  },
  {
    // Bass groove: sub-octave movement with ghost notes
    name: 'bass_groove',
    steps: [
      makeStep(-12, 1.0, 0.9), makeStep(-12, 0.4, 0.3),
      makeStep(-5, 1.0, 0.9), makeStep(-5, 0.4, 0.3),
      makeStep(-2, 1.0, 0.9), makeStep(-2, 0.4, 0.3),
      makeStep(-7, 1.0, 0.9), makeStep(-7, 0.4, 0.3),
    ],
  },
]

export function useStepSequencer() {
  const isPlaying = ref(false)
  const currentStep = ref(-1)
  const bpm = ref(120)
  const stepCount = ref<StepCountOption>(5)
  const division = ref<NoteDivision>('1/8')
  const presetIndex = ref(-1) // -1 = custom / no preset
  const midiClockActive = ref(false)
  const midiClockBpm = ref(0)

  // User-editable step grid (reactive array) — default 5 steps (Eastcoast)
  const steps = reactive<Step[]>(createDefaultSteps(5))

  let audioCtx: AudioContext | null = null
  let schedulerInterval: ReturnType<typeof setInterval> | null = null
  let nextStepTime = 0
  let scheduledStep = 0

  // Gate-off timers: scheduled step counter -> timer ID
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
  const BASE_NOTE = 60 // C3

  // Active steps count (for display)
  const activeStepCount = computed(() => steps.filter(s => s.active).length)

  function createDefaultSteps(count: number): Step[] {
    return Array.from({ length: count }, () => makeStep(0, 0.8, 0.8, true))
  }

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
    const quarterNote = 60 / getEffectiveBpm()
    return quarterNote * DIVISION_FACTORS[division.value]
  }

  function scheduleStep(stepIdx: number, time: number, schedId: number) {
    const step = steps[stepIdx]
    if (!step || !step.active) return

    const now = audioCtx?.currentTime ?? 0
    const delayMs = Math.max(0, (time - now) * 1000)
    const gateDurMs = step.gate * stepDurationSec() * 1000
    const midiNote = BASE_NOTE + step.semitone

    // Schedule noteOn
    setTimeout(() => {
      if (!isPlaying.value) return
      currentStep.value = stepIdx
      noteOnCb?.(midiNote, step.velocity)
    }, delayMs)

    // Cancel any pending gate-off for this schedule ID
    const existingTimer = gateTimers.get(schedId)
    if (existingTimer != null) clearTimeout(existingTimer)

    // Schedule noteOff at end of gate
    const offTimer = setTimeout(() => {
      if (!isPlaying.value) return
      gateTimers.delete(schedId)
      noteOffCb?.()
    }, delayMs + gateDurMs)
    gateTimers.set(schedId, offTimer)
  }

  function schedulerTick() {
    if (!audioCtx || !isPlaying.value) return
    const endWindow = audioCtx.currentTime + LOOKAHEAD_SEC
    const count = steps.length

    while (nextStepTime < endWindow) {
      const stepIdx = scheduledStep % count
      scheduleStep(stepIdx, nextStepTime, scheduledStep)
      nextStepTime += stepDurationSec()
      scheduledStep++
    }
  }

  function start(ac: AudioContext) {
    if (isPlaying.value) return
    audioCtx = ac
    isPlaying.value = true
    scheduledStep = 0
    currentStep.value = -1
    nextStepTime = ac.currentTime + 0.05

    schedulerInterval = setInterval(schedulerTick, SCHEDULER_INTERVAL_MS)
    schedulerTick()
  }

  function stop() {
    isPlaying.value = false
    if (schedulerInterval != null) {
      clearInterval(schedulerInterval)
      schedulerInterval = null
    }
    for (const timer of gateTimers.values()) clearTimeout(timer)
    gateTimers.clear()
    currentStep.value = -1
    scheduledStep = 0
  }

  function setBpm(newBpm: number) {
    bpm.value = Math.max(60, Math.min(200, newBpm))
  }

  function setDivision(div: NoteDivision) {
    division.value = div
  }

  function setStepCount(count: StepCountOption) {
    const wasPlaying = isPlaying.value
    if (wasPlaying) stop()

    stepCount.value = count
    // Resize the steps array
    while (steps.length < count) {
      steps.push(makeStep(0, 0.8, 0.8, true))
    }
    while (steps.length > count) {
      steps.pop()
    }
    presetIndex.value = -1 // custom after resize

    if (wasPlaying && audioCtx) start(audioCtx)
  }

  function loadPreset(idx: number) {
    if (idx < 0 || idx >= PRESETS.length) return
    const preset = PRESETS[idx]!
    presetIndex.value = idx

    const wasPlaying = isPlaying.value
    if (wasPlaying) stop()

    // Adapt preset to current step count:
    // fill grid by wrapping or truncating
    const count = stepCount.value
    steps.length = 0
    for (let i = 0; i < count; i++) {
      const src = preset.steps[i % preset.steps.length]!
      steps.push({ ...src })
    }

    if (wasPlaying && audioCtx) start(audioCtx)
  }

  // Edit individual step properties
  function setStepActive(idx: number, active: boolean) {
    if (steps[idx]) { steps[idx].active = active; presetIndex.value = -1 }
  }

  function setStepSemitone(idx: number, semitone: number) {
    if (steps[idx]) { steps[idx].semitone = Math.max(-24, Math.min(24, semitone)); presetIndex.value = -1 }
  }

  function setStepVelocity(idx: number, velocity: number) {
    if (steps[idx]) { steps[idx].velocity = Math.max(0, Math.min(1, velocity)); presetIndex.value = -1 }
  }

  function setStepGate(idx: number, gate: number) {
    if (steps[idx]) { steps[idx].gate = Math.max(0.1, Math.min(1, gate)); presetIndex.value = -1 }
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
      if (emaInterval === 0) {
        emaInterval = interval
      } else {
        emaInterval = 0.2 * interval + 0.8 * emaInterval
      }
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
    // Reactive state
    isPlaying: readonly(isPlaying),
    currentStep: readonly(currentStep),
    bpm: readonly(bpm) as Readonly<Ref<number>>,
    stepCount: readonly(stepCount) as Readonly<Ref<StepCountOption>>,
    division: readonly(division) as Readonly<Ref<NoteDivision>>,
    presetIndex: readonly(presetIndex),
    steps,
    activeStepCount,
    midiClockActive: readonly(midiClockActive),
    midiClockBpm: readonly(midiClockBpm),

    // Constants
    presets: PRESETS,
    stepCountOptions: STEP_COUNT_OPTIONS,
    noteDivisions: NOTE_DIVISIONS,

    // Methods
    start,
    stop,
    setBpm,
    setDivision,
    setStepCount,
    loadPreset,
    setStepActive,
    setStepSemitone,
    setStepVelocity,
    setStepGate,
    setCallbacks,
    handleMidiClock,
    dispose,
  }
}
