/**
 * Composable for recording Latent Lab experiment data.
 *
 * Always active (like Canvas recording) — every generation is persisted
 * to exports/json/ for research data export.
 *
 * A SITTING and a RUN are two different things. The sitting is this open
 * instrument: it starts lazily on the first record() and ends when the view
 * goes away, and it is not an address. Each record() writes a RUN of its own,
 * and its id is what the platform's storage addresses — a run card carries it,
 * favouriting stores it, restoring reads it back. Before that split, a whole
 * sitting was one folder, and what the Ablage could store was the pipeline's
 * thin run: the picture, without the parameters and without the sequence.
 *
 * Lifecycle:
 *   onMounted  → mark ready (no backend call)
 *   first record() → startSession() + save
 *   onUnmounted → endSession() (only if a sitting was opened)
 *
 * A surface whose run the SERVER writes (Mean Images since 2026-09-04, the
 * Denoising Archaeology since 2026-09-22) calls startSession() itself before
 * the run and names the sitting in the request; record() is then its way back
 * for a run the server did not write.
 */
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import { useDeviceId } from './useDeviceId'
import { apiBase } from '@/services/labApi'

const BASE = apiBase()

export interface RecordOutput {
  type: 'image' | 'audio' | 'text'
  format: string        // png, jpg, wav, json …
  /** The bytes themselves. One of `dataBase64` and `ref` is required. */
  dataBase64?: string
  /**
   * An ADDRESS inside this platform's storage —
   * `/api/media/<kind>/<run_id>/<index>`. The backend resolves it, reads that
   * file and copies the bytes into the new run, so the run stands complete on
   * its own; what the address saves is the round trip, because a picture that
   * is already a run of its own is then neither held here nor uploaded again.
   */
  ref?: string
  /** The instrument's own word about this output. Carried, never read. */
  meta?: Record<string, unknown>
}

export interface RecordStep {
  format: string        // jpg, png
  dataBase64: string
  /**
   * What this part IS, in the instrument's own terms — the step number and
   * whether it is a corrector, the coordinates of a cell, the concept a frame
   * belongs to. The storage carries it and hands it back on restore; nothing
   * between here and there interprets it.
   */
  meta?: Record<string, unknown>
}

/**
 * What the storage hands an instrument back — the run as an object, not as a
 * picture. Written by devserver/my_app/services/latent_lab_recorder.py
 * (`build_instrument_object`), served by GET /api/latent-lab/run/<run_id> and
 * carried in a favourite's restore data as `instrument`.
 *
 * The storage guarantees the frame: which tool, the parameters, the results,
 * the ordered parts, what came out. What a PART IS stays the instrument's own
 * business and travels in `meta` — nothing between the two ends reads it.
 */
export interface InstrumentPart {
  index: number
  kind: string
  url: string
  meta?: Record<string, unknown>
}

export interface InstrumentOutput {
  type: string
  format?: string
  url: string
  meta?: Record<string, unknown>
}

export interface InstrumentRun {
  run_id: string
  tool: string
  session_id?: string
  generation?: number
  timestamp?: string
  parameters?: Record<string, unknown>
  results?: Record<string, unknown>
  parts?: InstrumentPart[]
  outputs?: InstrumentOutput[]
}

/** One run, read back by its id. Null when there is no Latent Lab run there. */
export async function fetchInstrumentRun(runId: string): Promise<InstrumentRun | null> {
  try {
    const { data } = await axios.get<InstrumentRun>(`${BASE}/api/latent-lab/run/${runId}`)
    return data
  } catch (err) {
    console.warn('[LatentLabRecorder] Failed to read run:', runId, err)
    return null
  }
}

/**
 * The sittings this tab has opened in one instrument, newest last.
 *
 * A sitting ends when the view goes away, so a reload, a step to another
 * instrument and back, or a crash each start a new one — while the person is
 * plainly still working on the same thing. What the surface wants back is
 * therefore not ONE sitting but the sittings of this tab, and that is a fact
 * about this tab: `sessionStorage`, which lives exactly as long as the tab
 * does and is not shared with a second window.
 */
const SITTINGS_KEY = 'ai4artsed:lab-sittings:'
/**
 * A sitting is opened per VISIT, not per afternoon: stepping to another
 * instrument and back opens the next one, and comparing two instruments is the
 * ordinary gesture here. Eight was an hour's worth, after which the strip
 * silently forgot its first runs with no way back.
 */
const SITTINGS_KEPT = 40

const DISMISSED_KEY = 'ai4artsed:lab-dismissed:'

/** The runs this tab has taken off its strip by hand. */
export function dismissed(tool: string): Set<string> {
  try {
    const raw = sessionStorage.getItem(DISMISSED_KEY + tool)
    const ids = raw ? JSON.parse(raw) : []
    return new Set(Array.isArray(ids) ? ids.filter((id) => typeof id === 'string') : [])
  } catch {
    return new Set()
  }
}

/** Note that a run has been taken off, so it does not come back with the sitting. */
export function dismiss(tool: string, runId: string): void {
  try {
    const ids = dismissed(tool)
    ids.add(runId)
    sessionStorage.setItem(DISMISSED_KEY + tool, JSON.stringify([...ids]))
  } catch {
    /* a tab that refuses storage forgets the dismissal after a reload */
  }
}

export function sittingsOf(tool: string): string[] {
  try {
    const raw = sessionStorage.getItem(SITTINGS_KEY + tool)
    const ids = raw ? JSON.parse(raw) : []
    return Array.isArray(ids) ? ids.filter((id) => typeof id === 'string') : []
  } catch {
    return []
  }
}

function rememberSitting(tool: string, sessionId: string): void {
  try {
    const ids = sittingsOf(tool).filter((id) => id !== sessionId)
    ids.push(sessionId)
    sessionStorage.setItem(SITTINGS_KEY + tool, JSON.stringify(ids.slice(-SITTINGS_KEPT)))
  } catch {
    /* a tab that refuses storage simply starts empty after a reload */
  }
}

/** The runs of one sitting, in the order they were made. Empty on any failure. */
export async function fetchSessionRuns(
  sessionId: string,
  deviceId?: string,
): Promise<InstrumentRun[]> {
  try {
    const { data } = await axios.get<{ runs: InstrumentRun[] }>(
      `${BASE}/api/latent-lab/session/${sessionId}/runs`,
      { params: deviceId ? { device_id: deviceId } : undefined },
    )
    return Array.isArray(data?.runs) ? data.runs : []
  } catch (err) {
    console.warn('[LatentLabRecorder] Failed to read sitting:', sessionId, err)
    return []
  }
}

export interface RecordData {
  parameters: Record<string, unknown>
  results?: Record<string, unknown>
  outputs?: RecordOutput[]
  steps?: RecordStep[]
}

export function useLatentLabRecorder(toolType: string) {
  const sessionId = ref<string | null>(null)
  /** The run written last — the address of what is on the surface right now. */
  const lastRunId = ref<string | null>(null)
  const isRecording = ref(false)
  const recordCount = ref(0)
  const deviceId = useDeviceId()
  let mounted = false

  async function startSession(): Promise<void> {
    if (sessionId.value) return // already open
    try {
      const { data } = await axios.post(`${BASE}/api/latent-lab/record/start`, {
        latent_lab_tool: toolType,
        device_id: deviceId,
      })
      sessionId.value = data.session_id
      // So the surface can ask for these runs back after a reload.
      if (data.session_id) rememberSitting(toolType, data.session_id)
      isRecording.value = true
    } catch (err) {
      console.warn('[LatentLabRecorder] Failed to open session:', err)
    }
  }

  /**
   * Write one generation. Returns the run's id, or null when the write failed —
   * a surface that puts it on a card must handle null, because a card without a
   * run id is a card the Ablage cannot store.
   */
  async function save(payload: RecordData): Promise<string | null> {
    const { data } = await axios.post(`${BASE}/api/latent-lab/record/save`, {
      session_id: sessionId.value,
      // The sitting belongs to the device that opened it, and the backend
      // checks that here the way it already does when a plate is set.
      device_id: deviceId,
      parameters: payload.parameters,
      results: payload.results,
      outputs: payload.outputs,
      steps: payload.steps,
    })
    recordCount.value++
    lastRunId.value = data.run_id ?? null
    return lastRunId.value
  }

  async function record(payload: RecordData): Promise<string | null> {
    // Lazy start: open the sitting on the first actual record
    if (!sessionId.value) await startSession()
    if (!sessionId.value) return null // start failed
    try {
      return await save(payload)
    } catch (err) {
      // The backend does not know this sitting: it was restarted, or the tab
      // has been open across a deploy. The sitting is opened again and the run
      // written once more - otherwise this tab would record nothing for the
      // rest of its life, and say nothing about it.
      const gone = axios.isAxiosError(err) && err.response?.status === 404
      if (gone) {
        sessionId.value = null
        await startSession()
        if (sessionId.value) {
          try {
            return await save(payload)
          } catch (retryErr) {
            console.warn('[LatentLabRecorder] Failed to save after reopening:', retryErr)
            return null
          }
        }
      }
      console.warn('[LatentLabRecorder] Failed to save:', err)
      return null
    }
  }

  async function endSession(): Promise<void> {
    if (!sessionId.value) return // nothing to end
    try {
      await axios.post(`${BASE}/api/latent-lab/record/end`, {
        session_id: sessionId.value,
      })
    } catch (err) {
      console.warn('[LatentLabRecorder] Failed to close session:', err)
    } finally {
      isRecording.value = false
      sessionId.value = null
    }
  }

  onMounted(() => {
    mounted = true
    isRecording.value = true
    recordCount.value = 0
  })

  onUnmounted(() => {
    mounted = false
    endSession()
  })

  return { isRecording, recordCount, record, startSession, endSession, sessionId, lastRunId }
}
