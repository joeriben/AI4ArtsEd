/**
 * Arpeggiator composable — note transformer between note sources
 * (sequencer steps, MIDI keys, on-screen keyboard) and synthesis engine.
 *
 * When disabled: passes notes straight through (transparent).
 * When enabled: builds a chord pattern across octaves, fires noteOn
 * callbacks at a musically-quantized rate derived from BPM.
 *
 * Rate divisions relative to quarter note (MIDI-clock aware via bpmRef):
 *   1/4, 1/8, 1/16, 1/32, 1/4T, 1/8T, 1/16T (T = triplet)
 *
 * Octave range: 1–4 octaves. Chord intervals repeat per octave.
 *
 * 4 patterns: up, down, updown, random
 */
import { ref, readonly, type Ref } from 'vue'

export type ArpPattern = 'up' | 'down' | 'updown' | 'random'
export type ArpRate = '1/4' | '1/8' | '1/16' | '1/32' | '1/4T' | '1/8T' | '1/16T'

/** Factor relative to a quarter note duration */
const RATE_FACTORS: Record<ArpRate, number> = {
  '1/4':  1,
  '1/8':  0.5,
  '1/16': 0.25,
  '1/32': 0.125,
  '1/4T': 2 / 3,
  '1/8T': 1 / 3,
  '1/16T': 1 / 6,
}

/** Base chord intervals (major triad — no octave duplicate) */
const CHORD_INTERVALS = [0, 4, 7]

function shuffle(arr: number[]): number[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j]!, a[i]!]
  }
  return a
}

export function useArpeggiator(bpmRef: Readonly<Ref<number>>) {
  const enabled = ref(false)
  const pattern = ref<ArpPattern>('up')
  const rate = ref<ArpRate>('1/16')
  const octaveRange = ref(1)

  let arpTimer: ReturnType<typeof setTimeout> | null = null
  let arpStepIndex = 0
  let currentIntervals: number[] = []
  let currentBaseNote = 0
  let currentNoteOn: ((n: number, v: number) => void) | null = null
  let currentNoteOff: (() => void) | null = null
  let currentVelocity = 0.8

  function getArpRateMs(): number {
    const bpm = bpmRef.value || 120
    const quarterNoteMs = (60 / bpm) * 1000
    return quarterNoteMs * RATE_FACTORS[rate.value]
  }

  /** Build interval sequence across octaves, then apply pattern ordering */
  function buildIntervals(): number[] {
    // Expand chord across octave range
    const expanded: number[] = []
    for (let oct = 0; oct < octaveRange.value; oct++) {
      for (const interval of CHORD_INTERVALS) {
        expanded.push(interval + oct * 12)
      }
    }

    const p = pattern.value
    if (p === 'up') return expanded
    if (p === 'down') return [...expanded].reverse()
    if (p === 'updown') {
      if (expanded.length <= 1) return expanded
      // Up then down, omitting duplicates at peaks
      return [...expanded, ...expanded.slice(1, -1).reverse()]
    }
    // random
    return shuffle(expanded)
  }

  function scheduleNextArpStep() {
    if (!enabled.value || !currentNoteOn) return

    const intervals = currentIntervals
    if (intervals.length === 0) return

    const idx = arpStepIndex % intervals.length
    const note = currentBaseNote + intervals[idx]!
    currentNoteOn(note, currentVelocity)
    arpStepIndex++

    // Rebuild intervals on each cycle for random pattern freshness
    if (arpStepIndex % intervals.length === 0 && pattern.value === 'random') {
      currentIntervals = shuffle(buildIntervals())
    }

    arpTimer = setTimeout(scheduleNextArpStep, getArpRateMs())
  }

  /**
   * Process an incoming note. If arpeggiator is disabled, passes straight
   * through to noteOn. If enabled, starts the arp pattern from this base note.
   */
  function processNote(
    note: number,
    velocity: number,
    noteOn: (n: number, v: number) => void,
    noteOff: () => void,
  ): void {
    if (!enabled.value) {
      noteOn(note, velocity)
      return
    }

    // Stop any running arp first
    clearArp()

    currentBaseNote = note
    currentVelocity = velocity
    currentNoteOn = noteOn
    currentNoteOff = noteOff
    currentIntervals = buildIntervals()
    arpStepIndex = 0

    // Fire first note immediately, then schedule subsequent
    scheduleNextArpStep()
  }

  function clearArp() {
    if (arpTimer != null) {
      clearTimeout(arpTimer)
      arpTimer = null
    }
    arpStepIndex = 0
  }

  function stop(noteOff?: () => void): void {
    clearArp()
    const off = noteOff ?? currentNoteOff
    off?.()
    currentNoteOn = null
    currentNoteOff = null
  }

  function setEnabled(on: boolean): void {
    enabled.value = on
    if (!on) clearArp()
  }

  function setPattern(p: ArpPattern): void {
    pattern.value = p
    if (enabled.value) {
      currentIntervals = buildIntervals()
    }
  }

  function setRate(r: ArpRate): void {
    rate.value = r
  }

  function setOctaveRange(oct: number): void {
    octaveRange.value = Math.max(1, Math.min(4, oct))
    if (enabled.value) {
      currentIntervals = buildIntervals()
    }
  }

  function dispose(): void {
    clearArp()
    currentNoteOn = null
    currentNoteOff = null
  }

  return {
    enabled: readonly(enabled),
    pattern: readonly(pattern),
    rate: readonly(rate),
    octaveRange: readonly(octaveRange),
    setEnabled,
    setPattern,
    setRate,
    setOctaveRange,
    processNote,
    stop,
    dispose,
  }
}
