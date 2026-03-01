/**
 * Arpeggiator composable — a note transformer that sits between note sources
 * (sequencer steps, MIDI keys) and the synthesis engine.
 *
 * When disabled: passes notes straight through (transparent).
 * When enabled: takes a base note, builds a chord pattern, and fires rapid
 * noteOn callbacks at an arp rate derived from BPM.
 *
 * 4 patterns (intervals relative to input note):
 *   up:     +0, +4, +7, +12     (major triad + octave, ascending)
 *   down:   +12, +7, +4, +0     (descending)
 *   updown: +0, +4, +7, +12, +7, +4  (bounce)
 *   random: shuffled {+0, +4, +7, +12}
 */
import { ref, readonly, type Ref } from 'vue'

export type ArpPattern = 'up' | 'down' | 'updown' | 'random'

const ARP_INTERVALS: Record<ArpPattern, number[]> = {
  up: [0, 4, 7, 12],
  down: [12, 7, 4, 0],
  updown: [0, 4, 7, 12, 7, 4],
  random: [0, 4, 7, 12], // shuffled at runtime
}

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

  let arpTimer: ReturnType<typeof setTimeout> | null = null
  let arpStepIndex = 0
  let currentIntervals: number[] = []
  let currentBaseNote = 0
  let currentNoteOn: ((n: number, v: number) => void) | null = null
  let currentNoteOff: (() => void) | null = null
  let currentVelocity = 0.8

  function getArpRateMs(): number {
    // One arp step = one 16th note at current BPM
    const bpm = bpmRef.value || 120
    return (60 / bpm) / 4 * 1000
  }

  function buildIntervals(): number[] {
    const p = pattern.value
    if (p === 'random') return shuffle(ARP_INTERVALS.random)
    return ARP_INTERVALS[p]
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
      currentIntervals = shuffle(ARP_INTERVALS.random)
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
    // If arp is running, rebuild intervals for next cycle
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
    setEnabled,
    setPattern,
    processNote,
    stop,
    dispose,
  }
}
