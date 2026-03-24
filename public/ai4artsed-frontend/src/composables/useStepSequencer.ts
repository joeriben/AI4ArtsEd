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
    // Eastcoast (Berlin School): 16 steps, ratchet-style low-high alternation.
    // Low tones on odd steps, octave staccato fills between. Melodic contour
    // via Bb2, Eb2, F2. Last step = ghost note. Gemini V2.
    name: 'eastcoast',
    steps: [
      makeStep(0, 0.79, 0.5),    // C2
      makeStep(12, 0.63, 0.25),  // C3, staccato
      makeStep(7, 0.63, 0.5),    // G2
      makeStep(12, 0.63, 0.25),  // C3, staccato
      makeStep(0, 0.87, 0.5),    // C2, accent
      makeStep(12, 0.63, 0.25),  // C3, staccato
      makeStep(10, 0.63, 0.5),   // Bb2
      makeStep(12, 0.63, 0.25),  // C3, staccato
      makeStep(0, 0.79, 0.5),    // C2
      makeStep(12, 0.63, 0.25),  // C3, staccato
      makeStep(3, 0.63, 0.5),    // Eb2
      makeStep(12, 0.63, 0.25),  // C3, staccato
      makeStep(0, 0.87, 0.5),    // C2, accent
      makeStep(12, 0.63, 0.25),  // C3, staccato
      makeStep(5, 0.71, 0.8),    // F2, legato
      makeStep(7, 0.47, 0.25),   // G2, ghost
    ],
  },
  {
    // Westcoast: 5-step polyrhythm against 4/4 — takes 5 bars to realign.
    // Wide leaps, rest as rhythmic element, extreme timbre contrast. Gemini V2.
    name: 'westcoast',
    steps: [
      makeStep(0, 1.0, 0.8),     // C1, deep, accent
      makeStep(19, 0.47, 1.0),   // G3, glide (long gate)
      makeStep(0, 0, 0, false),  // REST — rhythmically essential
      makeStep(24, 0.79, 0.1),   // C4, staccatissimo
      makeStep(3, 0.31, 0.4),    // Eb2, whisper
    ],
  },
  {
    // Synthwave (Outrun): sidechain bass pump. 16 steps.
    // Mutes on downbeats (kick space), Eb/G variations in second half. Gemini V2.
    name: 'synthwave',
    steps: [
      makeStep(0, 0, 0, false),  // mute (kick)
      makeStep(0, 0.79, 0.4),    // C2
      makeStep(0, 0.79, 0.4),    // C2
      makeStep(3, 0.87, 0.4),    // Eb2
      makeStep(0, 0, 0, false),  // mute
      makeStep(0, 0.79, 0.4),    // C2
      makeStep(0, 0.79, 0.4),    // C2
      makeStep(3, 0.87, 0.4),    // Eb2
      makeStep(0, 0, 0, false),  // mute
      makeStep(0, 0.79, 0.4),    // C2
      makeStep(0, 0.79, 0.4),    // C2
      makeStep(7, 0.87, 0.4),    // G2 — opens up
      makeStep(0, 0, 0, false),  // mute
      makeStep(0, 0.79, 0.4),    // C2
      makeStep(0, 0.79, 0.4),    // C2
      makeStep(7, 0.87, 0.4),    // G2
    ],
  },
  {
    // Acid: 16 steps. Rests for air, ties (gate=1.0), accents,
    // the classic 2-octave belly-drop Eb→G1 at steps 10-12. Gemini V2.
    name: 'techno',
    steps: [
      makeStep(0, 0, 0, false),  // REST — acid needs air
      makeStep(0, 0.79, 0.5),    // C2
      makeStep(0, 0.63, 1.0),    // C2, TIE (legato into next)
      makeStep(12, 1.0, 0.5),    // C3, ACCENT + slide up
      makeStep(0, 0, 0, false),  // REST
      makeStep(0, 0.79, 0.5),    // C2
      makeStep(0, 0, 0, false),  // REST
      makeStep(0, 0.79, 0.5),    // C2
      makeStep(0, 0.63, 1.0),    // C2, TIE
      makeStep(3, 1.0, 1.0),     // Eb2, ACCENT + TIE — belly ache starts
      makeStep(3, 0.63, 1.0),    // Eb2, TIE (sustaining)
      makeStep(-5, 0.63, 0.5),   // G1, 2-octave DROP (the 303 moment)
      makeStep(0, 1.0, 0.5),     // C2, ACCENT — landing
      makeStep(0, 0, 0, false),  // REST
      makeStep(12, 0.63, 0.5),   // C3
      makeStep(0, 0, 0, false),  // REST
    ],
  },
  {
    // Dub Techno: sparse chord stabs with long silences. 16 steps.
    name: 'dub_techno',
    steps: [
      makeStep(0, 0.71, 0.1),    // stab
      makeStep(0, 0, 0, false),  // silence
      makeStep(0, 0, 0, false),
      makeStep(0, 0, 0, false),
      makeStep(0, 0, 0, false),
      makeStep(0, 0.86, 0.1),    // stab, louder
      makeStep(0, 0, 0, false),
      makeStep(0, 0, 0, false),
      makeStep(0, 0, 0, false),
      makeStep(0, 0, 0, false),
      makeStep(0, 0.55, 0.1),    // stab, softer
      makeStep(0, 0, 0, false),
      makeStep(0, 0, 0, false),
      makeStep(0, 0, 0, false),
      makeStep(0, 0, 0, false),
      makeStep(0, 0, 0, false),
    ],
  },
  {
    // Ambient: 16 steps. Slow evolving, non-obvious voicings, gradual swell.
    name: 'ambient',
    steps: [
      makeStep(0, 0.45, 1.0),    // root, pp
      makeStep(0, 0.48, 1.0),
      makeStep(2, 0.5, 1.0),     // add9
      makeStep(2, 0.53, 1.0),
      makeStep(7, 0.55, 1.0),    // 5th
      makeStep(7, 0.6, 1.0),
      makeStep(5, 0.63, 1.0),    // sus4
      makeStep(5, 0.65, 1.0),
      makeStep(11, 0.7, 1.0),    // maj7
      makeStep(11, 0.73, 1.0),
      makeStep(14, 0.75, 1.0),   // 9th
      makeStep(14, 0.78, 1.0),
      makeStep(12, 0.8, 1.0),    // octave
      makeStep(7, 0.7, 1.0),     // 5th, pulling back
      makeStep(2, 0.55, 1.0),    // add9, fading
      makeStep(0, 0.4, 1.0),     // root, ppp
    ],
  },
  {
    // IDM/Glitch: 10 steps. Genuinely unpredictable, no tonal logic.
    name: 'idm_glitch',
    steps: [
      makeStep(6, 1.0, 0.04),    // tritone, click
      makeStep(-8, 0.3, 1.0),    // low, whisper legato
      makeStep(17, 0.95, 0.12),  // high, stab
      makeStep(0, 0, 0, false),  // rest
      makeStep(-1, 0.7, 0.7),    // semitone below
      makeStep(23, 0.4, 0.03),   // extreme high, tick
      makeStep(-11, 1.0, 0.5),   // low, accent
      makeStep(8, 0.55, 0.85),   // aug5, lingering
      makeStep(0, 0, 0, false),  // rest
      makeStep(-4, 0.9, 1.0),    // M3 below, full
    ],
  },
  {
    // Solar: 16 steps. Mechanical, chromatic upper neighbors on each degree.
    name: 'solar',
    steps: [
      makeStep(0, 0.9, 0.5), makeStep(1, 0.9, 0.5),
      makeStep(0, 0.9, 0.5), makeStep(0, 0.9, 0.5),
      makeStep(5, 0.9, 0.5), makeStep(6, 0.9, 0.5),
      makeStep(5, 0.9, 0.5), makeStep(5, 0.9, 0.5),
      makeStep(7, 0.9, 0.5), makeStep(8, 0.9, 0.5),
      makeStep(7, 0.9, 0.5), makeStep(7, 0.9, 0.5),
      makeStep(11, 0.9, 0.5), makeStep(12, 0.9, 0.5),
      makeStep(11, 0.9, 0.5), makeStep(10, 0.9, 0.5),
    ],
  },
  {
    // Arpeggio bass: 32 steps. Alternating 5ths/tritones, building intensity.
    name: 'arpeggio_bass',
    steps: [
      makeStep(0, 0.8, 0.5), makeStep(7, 0.65, 0.45),
      makeStep(0, 0.8, 0.5), makeStep(6, 0.65, 0.45),
      makeStep(0, 0.8, 0.5), makeStep(7, 0.65, 0.45),
      makeStep(0, 0.8, 0.5), makeStep(10, 0.7, 0.5),
      makeStep(0, 0.85, 0.5), makeStep(7, 0.7, 0.45),
      makeStep(0, 0.85, 0.5), makeStep(6, 0.7, 0.45),
      makeStep(0, 0.85, 0.5), makeStep(7, 0.7, 0.45),
      makeStep(0, 0.85, 0.5), makeStep(11, 0.75, 0.55),
      makeStep(0, 0.9, 0.55), makeStep(7, 0.75, 0.5),
      makeStep(12, 0.9, 0.55), makeStep(6, 0.75, 0.5),
      makeStep(0, 0.9, 0.55), makeStep(7, 0.75, 0.5),
      makeStep(12, 0.9, 0.55), makeStep(10, 0.8, 0.55),
      makeStep(0, 0.95, 0.6), makeStep(7, 0.8, 0.5),
      makeStep(12, 0.95, 0.6), makeStep(6, 0.8, 0.5),
      makeStep(0, 1.0, 0.6), makeStep(11, 0.85, 0.55),
      makeStep(7, 1.0, 0.6), makeStep(0, 0, 0, false),
    ],
  },
  {
    // Trance gate: 8 steps. Rhythmic gating with syncopation.
    name: 'trance_gate',
    steps: [
      makeStep(0, 1.0, 0.9),
      makeStep(0, 0.3, 0.15),
      makeStep(0, 0.85, 0.7),
      makeStep(0, 0.5, 0.3),
      makeStep(0, 1.0, 0.9),
      makeStep(0, 0, 0, false),
      makeStep(0, 0.9, 0.6),
      makeStep(0, 0.4, 0.2),
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
