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

export type StepCountOption = 5 | 8 | 10 | 16 | 32
export const STEP_COUNT_OPTIONS: StepCountOption[] = [5, 8, 10, 16, 32]

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
    // Eastcoast: Moog-style bass (Switched-On Bach). 8 steps, C minor pentatonic.
    name: 'eastcoast',
    steps: [
      makeStep(0, 0.94, 0.8),   // C2 root, accent
      makeStep(4, 0.78, 0.5),   // E2, short
      makeStep(7, 0.94, 0.8),   // G2
      makeStep(12, 0.71, 0.5),  // C3, soft+short
      makeStep(4, 0.86, 0.8),   // E2
      makeStep(0, 0.78, 0.5),   // C2, soft
      makeStep(7, 0.94, 0.8),   // G2
      makeStep(4, 0.71, 0.5),   // E2, soft+short
    ],
  },
  {
    // Westcoast: Buchla 245 / Suzanne Ciani. 5 steps, atonal, variable pulses.
    name: 'westcoast',
    steps: [
      makeStep(0, 0.71, 0.4),   // A3
      makeStep(4, 1.0, 1.0),    // C#4, accent+legato
      makeStep(-4, 0.55, 0.2),  // F3, quiet+staccato
      makeStep(7, 0.86, 0.6),   // Eb4
      makeStep(1, 0.78, 0.8),   // Bb3
    ],
  },
  {
    // Synthwave: Perturbator/Kavinsky arpeggios. 16 steps, up-down C major.
    name: 'synthwave',
    steps: [
      makeStep(0, 1.0, 0.6),    // C3
      makeStep(4, 1.0, 0.6),    // E3
      makeStep(7, 1.0, 0.6),    // G3
      makeStep(12, 1.0, 0.6),   // C4
      makeStep(16, 1.0, 0.6),   // E4
      makeStep(19, 1.0, 0.6),   // G4
      makeStep(24, 1.0, 0.6),   // C5
      makeStep(19, 1.0, 0.6),   // G4
      makeStep(16, 1.0, 0.6),   // E4
      makeStep(12, 1.0, 0.6),   // C4
      makeStep(7, 1.0, 0.6),    // G3
      makeStep(4, 1.0, 0.6),    // E3
      makeStep(0, 1.0, 0.6),    // C3
      makeStep(4, 1.0, 0.6),    // E3
      makeStep(7, 1.0, 0.6),    // G3
      makeStep(12, 1.0, 0.6),   // C4
    ],
  },
  {
    // Techno: TB-303-style acid. 16 steps, C1+G1 with rests.
    name: 'techno',
    steps: [
      makeStep(0, 1.0, 0.2),    // C1
      makeStep(0, 0, 0, false),  // rest
      makeStep(0, 1.0, 0.2),    // C1
      makeStep(7, 0.86, 0.2),   // G1
      makeStep(0, 1.0, 0.2),    // C1
      makeStep(0, 0, 0, false),  // rest
      makeStep(0, 1.0, 0.2),    // C1
      makeStep(7, 0.86, 0.2),   // G1
      makeStep(0, 1.0, 0.2),    // C1
      makeStep(0, 0, 0, false),  // rest
      makeStep(0, 1.0, 0.2),    // C1
      makeStep(7, 0.86, 0.2),   // G1
      makeStep(0, 1.0, 0.2),    // C1
      makeStep(0, 0, 0, false),  // rest
      makeStep(0, 1.0, 0.2),    // C1
      makeStep(7, 0.86, 0.2),   // G1
    ],
  },
  {
    // Ambient: Brian Eno evolving pads. 16 steps, C major held notes, rising dynamics.
    name: 'ambient',
    steps: [
      makeStep(0, 0.63, 1.0),   // C4 ×4
      makeStep(0, 0.63, 1.0),
      makeStep(0, 0.63, 1.0),
      makeStep(0, 0.63, 1.0),
      makeStep(4, 0.71, 1.0),   // E4 ×4
      makeStep(4, 0.71, 1.0),
      makeStep(4, 0.71, 1.0),
      makeStep(4, 0.71, 1.0),
      makeStep(7, 0.78, 1.0),   // G4 ×4
      makeStep(7, 0.78, 1.0),
      makeStep(7, 0.78, 1.0),
      makeStep(7, 0.78, 1.0),
      makeStep(12, 0.86, 1.0),  // C5 ×4
      makeStep(12, 0.86, 1.0),
      makeStep(12, 0.86, 1.0),
      makeStep(12, 0.86, 1.0),
    ],
  },
  {
    // IDM/Glitch: Autechre-inspired. 10 steps, irregular, extreme gate variation.
    name: 'idm_glitch',
    steps: [
      makeStep(0, 1.0, 0.1),    // F#4
      makeStep(3, 0.39, 0.9),   // A4, soft+legato
      makeStep(6, 1.0, 0.05),   // C5, staccatissimo
      makeStep(4, 0.63, 0.7),   // Bb4
      makeStep(9, 1.0, 0.15),   // D5, staccato
      makeStep(0, 0, 0, false),  // rest
      makeStep(1, 0.78, 0.4),   // G4
      makeStep(11, 1.0, 0.2),   // E5
      makeStep(0, 0.71, 0.6),   // F#4
      makeStep(6, 1.0, 1.0),    // C5, accent+legato
    ],
  },
  {
    // Solar: precise, mechanical, equal velocity, robotic chromatic movement.
    name: 'solar',
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
    // Arpeggio-Bassline: Daft Punk-style EDM. 32 steps, C-G-C-E ascending pattern.
    // Second half slightly louder for variation.
    name: 'arpeggio_bass',
    steps: [
      makeStep(0, 0.94, 0.5),   // C2
      makeStep(7, 0.78, 0.5),   // G2
      makeStep(12, 0.94, 0.5),  // C3
      makeStep(16, 0.78, 0.5),  // E3
      makeStep(0, 0.94, 0.5),   // C2
      makeStep(7, 0.78, 0.5),   // G2
      makeStep(12, 0.94, 0.5),  // C3
      makeStep(16, 0.78, 0.5),  // E3
      makeStep(0, 0.94, 0.5),
      makeStep(7, 0.78, 0.5),
      makeStep(12, 0.94, 0.5),
      makeStep(16, 0.78, 0.5),
      makeStep(0, 0.94, 0.5),
      makeStep(7, 0.78, 0.5),
      makeStep(12, 0.94, 0.5),
      makeStep(16, 0.78, 0.5),
      // Second half: slightly louder
      makeStep(0, 1.0, 0.5),
      makeStep(7, 0.86, 0.5),
      makeStep(12, 1.0, 0.5),
      makeStep(16, 0.86, 0.5),
      makeStep(0, 1.0, 0.5),
      makeStep(7, 0.86, 0.5),
      makeStep(12, 1.0, 0.5),
      makeStep(16, 0.86, 0.5),
      makeStep(0, 1.0, 0.5),
      makeStep(7, 0.86, 0.5),
      makeStep(12, 1.0, 0.5),
      makeStep(16, 0.86, 0.5),
      makeStep(0, 1.0, 0.5),
      makeStep(7, 0.86, 0.5),
      makeStep(12, 1.0, 0.5),
      makeStep(16, 0.86, 0.5),
    ],
  },
  {
    // Trance gate: same note, rhythmic gating, accent pattern.
    name: 'trance_gate',
    steps: [
      makeStep(0, 1.0, 0.9), makeStep(0, 0.4, 0.3),
      makeStep(0, 1.0, 0.9), makeStep(0, 0.4, 0.3),
      makeStep(0, 1.0, 0.9), makeStep(0, 0.4, 0.3),
      makeStep(0, 1.0, 0.9), makeStep(0, 0.4, 0.3),
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

    // Set step count to match preset length (snap to nearest valid option)
    const presetLen = preset.steps.length
    const bestCount = STEP_COUNT_OPTIONS.reduce((best, opt) =>
      Math.abs(opt - presetLen) < Math.abs(best - presetLen) ? opt : best
    , STEP_COUNT_OPTIONS[0]!)
    stepCount.value = Math.max(bestCount, presetLen) as StepCountOption

    // Load preset steps, pad with defaults if needed
    steps.length = 0
    for (let i = 0; i < stepCount.value; i++) {
      if (i < preset.steps.length) {
        steps.push({ ...preset.steps[i]! })
      } else {
        steps.push(makeStep(0, 0.8, 0.8, false)) // pad with inactive steps
      }
    }

    if (wasPlaying && audioCtx) start(audioCtx)
  }

  /** Reset grid to uniform defaults (all C3, gate 80%, velocity 80%) */
  function resetGrid() {
    const wasPlaying = isPlaying.value
    if (wasPlaying) stop()
    presetIndex.value = -1
    steps.length = 0
    for (let i = 0; i < stepCount.value; i++) {
      steps.push(makeStep(0, 0.8, 0.8, true))
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

  /** Set gate for all steps at once */
  function setAllGates(gate: number) {
    const g = Math.max(0.1, Math.min(1, gate))
    for (const step of steps) step.gate = g
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
    resetGrid,
    setStepActive,
    setStepSemitone,
    setStepVelocity,
    setStepGate,
    setAllGates,
    setCallbacks,
    handleMidiClock,
    dispose,
  }
}
