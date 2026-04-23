/**
 * Model install composable — triggers HF GGUF download via SSE stream.
 * Module-level singleton: one install at a time across the whole app.
 *
 * Consumers: dropdown click handlers open install; ModelInstallToast displays.
 */
import { ref, computed, readonly } from 'vue'

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

function getBaseUrl(): string {
  return import.meta.env.DEV ? 'http://localhost:17802' : ''
}

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
    const resp = await fetch(`${getBaseUrl()}/api/chat/install`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alias }),
      signal: controller.signal,
    })
    if (!resp.ok || !resp.body) {
      throw new Error(`HTTP ${resp.status}`)
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE events are separated by \n\n; each "data: <json>"
      let sep = buffer.indexOf('\n\n')
      while (sep !== -1) {
        const raw = buffer.slice(0, sep).trim()
        buffer = buffer.slice(sep + 2)
        sep = buffer.indexOf('\n\n')
        if (!raw.startsWith('data:')) continue
        const json = raw.slice(5).trim()
        if (!json) continue
        try {
          const ev = JSON.parse(json)
          _applyEvent(ev, alias)
        } catch (err) {
          console.warn('[useModelInstall] bad SSE chunk:', json, err)
        }
      }
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
