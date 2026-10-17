/**
 * Model install composable — triggers HF GGUF download via SSE stream.
 * Module-level singleton: one install at a time across the whole app.
 *
 * Consumers: dropdown click handlers open install; ModelInstallToast displays.
 */
import { ref, computed, readonly } from 'vue'
import { sseEvents } from '@/lib/sseStream'
import { apiBase } from '@/services/labApi'

export interface InstallProgress {
  alias: string           // e.g. "local/gemma-2-2b"
  displayLabel: string    // "Gemma 2 2B (local)"
  currentFile: string     // "gemma-2-2b-it-Q8_0.gguf" or "mmproj-F16.gguf"
  doneMb: number
  totalMb: number
  speedMbS: number
  state: 'starting' | 'downloading' | 'done' | 'error'
  errorMessage: string
}

const _active = ref<InstallProgress | null>(null)
let _activeController: AbortController | null = null
const _onDoneCallbacks: Array<(alias: string) => void> = []

/** Register a callback to run when ANY install finishes successfully. */
export function onInstallDone(cb: (alias: string) => void): () => void {
  _onDoneCallbacks.push(cb)
  return () => {
    const idx = _onDoneCallbacks.indexOf(cb)
    if (idx >= 0) _onDoneCallbacks.splice(idx, 1)
  }
}

/**
 * Start an install. Returns immediately; progress is in `active`.
 * If another install is already running, rejects with a descriptive error.
 */
async function install(alias: string, displayLabel: string): Promise<void> {
  if (_active.value && _active.value.state !== 'done' && _active.value.state !== 'error') {
    throw new Error(`Another install is already running (${_active.value.displayLabel})`)
  }

  _active.value = {
    alias,
    displayLabel,
    currentFile: '',
    doneMb: 0,
    totalMb: 0,
    speedMbS: 0,
    state: 'starting',
    errorMessage: '',
  }

  const controller = new AbortController()
  _activeController = controller

  try {
    // The platform's own reader, not a second one written out here. This
    // composable kept a hand-written loop for one reason — the warning below,
    // which the shared reader had no way to give — and that reason is now a
    // parameter. `SseHttpError` carries the message `HTTP <status>`, which is
    // the string this catch block already showed.
    for await (const ev of sseEvents<any>(
      `${apiBase()}/api/chat/install`,
      { alias },
      {
        signal: controller.signal,
        // A download whose progress frames stop arriving looks, on the bar,
        // exactly like a download that died. This is the line that tells the
        // two apart, and this composable is the only caller that asks for it.
        onSkipped: (payload, err) =>
          console.warn('[useModelInstall] bad SSE chunk:', payload, err),
      },
    )) {
      _applyEvent(ev, alias)
    }

    // Stream ended. If state never became done/error, mark as error.
    if (_active.value && _active.value.state !== 'done' && _active.value.state !== 'error') {
      _active.value = { ..._active.value, state: 'error', errorMessage: 'Stream ended unexpectedly' }
    }
  } catch (e: any) {
    if (_active.value) {
      _active.value = { ..._active.value, state: 'error', errorMessage: e?.message || 'Unknown error' }
    }
  } finally {
    _activeController = null
  }
}

function _applyEvent(ev: any, alias: string): void {
  if (!_active.value) return
  if (ev.type === 'start') {
    _active.value = {
      ..._active.value,
      state: 'downloading',
      currentFile: ev.file || _active.value.currentFile,
      totalMb: ev.total_mb || _active.value.totalMb,
      doneMb: 0,
      speedMbS: 0,
    }
  } else if (ev.type === 'progress') {
    _active.value = {
      ..._active.value,
      state: 'downloading',
      currentFile: ev.file || _active.value.currentFile,
      doneMb: ev.done_mb ?? _active.value.doneMb,
      totalMb: ev.total_mb || _active.value.totalMb,
      speedMbS: ev.speed_mb_s ?? 0,
    }
  } else if (ev.type === 'done') {
    _active.value = { ..._active.value, state: 'done' }
    for (const cb of _onDoneCallbacks) {
      try { cb(alias) } catch (err) { console.warn('[useModelInstall] onDone cb threw:', err) }
    }
  } else if (ev.type === 'error') {
    _active.value = { ..._active.value, state: 'error', errorMessage: ev.message || 'Install failed' }
  }
}

function dismiss(): void {
  // Only allow dismissing after done/error
  if (_active.value && (_active.value.state === 'done' || _active.value.state === 'error')) {
    _active.value = null
  }
}

export function useModelInstall() {
  return {
    active: readonly(_active),
    isActive: computed(() => _active.value !== null),
    install,
    dismiss,
  }
}
