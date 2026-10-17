/**
 * Web MIDI API composable for Crossmodal Lab Synth tab.
 *
 * Provides MIDI input device selection, CC-to-callback mapping,
 * note-to-callback mapping, and MIDI realtime clock forwarding
 * for external hardware control.
 *
 * Gracefully degrades: if Web MIDI is unsupported, `isSupported`
 * is false and no errors are thrown.
 */
import { ref, readonly, onUnmounted, type Ref } from 'vue'

export type MidiClockType = 'clock' | 'start' | 'stop'

export interface MidiInputInfo {
  id: string
  name: string
}

export function useWebMidi() {
  const isSupported = ref(false)
  const inputs = ref<MidiInputInfo[]>([])
  const selectedInputId = ref<string | null>(null)

  let midiAccess: MIDIAccess | null = null
  let activeInput: MIDIInput | null = null

  // Callback registries
  const ccCallbacks = new Map<number, (value01: number) => void>()
  let noteCallback: ((note: number, velocity: number, on: boolean) => void) | null = null
  let clockCallback: ((type: MidiClockType) => void) | null = null

  function handleMidiMessage(event: MIDIMessageEvent) {
    const data = event.data
    if (!data || data.length === 0) return

    // Handle single-byte MIDI realtime messages before the 3-byte guard
    const byte0 = data[0]!
    if (byte0 === 0xf8) { clockCallback?.('clock'); return }
    if (byte0 === 0xfa) { clockCallback?.('start'); return }
    if (byte0 === 0xfc) { clockCallback?.('stop'); return }

    if (data.length < 3) return

    const status = byte0 & 0xf0
    const d1 = data[1]!
    const d2 = data[2]!

    // CC (0xB0)
    if (status === 0xb0) {
      const cb = ccCallbacks.get(d1)
      if (cb) cb(d2 / 127)
    }

    // Note On (0x90)
    if (status === 0x90 && d2 > 0) {
      noteCallback?.(d1, d2 / 127, true)
    }

    // Note Off (0x80) or Note On with velocity 0
    if (status === 0x80 || (status === 0x90 && d2 === 0)) {
      noteCallback?.(d1, 0, false)
    }
  }

  function selectInput(id: string | null) {
    // Disconnect old
    if (activeInput) {
      activeInput.onmidimessage = null
      activeInput = null
    }

    selectedInputId.value = id
    if (!id || !midiAccess) return

    const input = midiAccess.inputs.get(id)
    if (input) {
      activeInput = input
      input.onmidimessage = handleMidiMessage
    }
  }

  function refreshInputs() {
    if (!midiAccess) return
    const list: MidiInputInfo[] = []
    midiAccess.inputs.forEach((input) => {
      list.push({ id: input.id, name: input.name || input.id })
    })
    inputs.value = list

    // Auto-select first input if none selected
    if (!selectedInputId.value && list.length > 0 && list[0]) {
      selectInput(list[0].id)
    }

    // Reconnect if previously selected input reappeared
    if (selectedInputId.value && list.some(i => i.id === selectedInputId.value)) {
      selectInput(selectedInputId.value)
    }
  }

  async function init() {
    if (!navigator.requestMIDIAccess) {
      isSupported.value = false
      return
    }

    try {
      midiAccess = await navigator.requestMIDIAccess()
      isSupported.value = true

      midiAccess.onstatechange = () => refreshInputs()
      refreshInputs()
    } catch {
      isSupported.value = false
    }
  }

  function mapCC(ccNumber: number, callback: (value01: number) => void) {
    ccCallbacks.set(ccNumber, callback)
  }

  function unmapCC(ccNumber: number) {
    ccCallbacks.delete(ccNumber)
  }

  function onNote(callback: (note: number, velocity: number, on: boolean) => void) {
    noteCallback = callback
  }

  function onClock(callback: (type: MidiClockType) => void) {
    clockCallback = callback
  }

  function dispose() {
    if (activeInput) {
      activeInput.onmidimessage = null
      activeInput = null
    }
    ccCallbacks.clear()
    noteCallback = null
    clockCallback = null
    midiAccess = null
  }

  onUnmounted(dispose)

  return {
    init,
    selectInput,
    mapCC,
    unmapCC,
    onNote,
    onClock,
    dispose,
    isSupported: readonly(isSupported),
    inputs: inputs as Readonly<Ref<MidiInputInfo[]>>,
    selectedInputId: readonly(selectedInputId),
  }
}
