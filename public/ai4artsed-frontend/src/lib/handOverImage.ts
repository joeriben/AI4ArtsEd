/**
 * A picture handed from one surface to the Flow: the "send onward" controls
 * put it here and route to /x2x-flow, which takes it on arrival. One key, one
 * shape, one freshness limit — until 2026-10-10 four writers and the one
 * reader each spelled them out for themselves.
 */
const KEY = 'i2i_transfer_data'

/** Older than this on arrival, and it is a leftover nobody meant to see again. */
const FRESH_MS = 300_000

export interface HandedImage {
  imageUrl: string
  runId: string | null
}

/** Hand a picture over; the Flow takes it on its next arrival. */
export function handOverImage(imageUrl: string, runId: string | null | undefined): void {
  localStorage.setItem(KEY, JSON.stringify({ imageUrl, runId: runId ?? null, timestamp: Date.now() }))
}

/**
 * What was handed over, read once and cleared at once — localStorage outlives
 * the browser. Null where nothing fresh lies there, or storage is refused.
 */
export function takeHandedImage(): HandedImage | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    localStorage.removeItem(KEY)
    const handed = JSON.parse(raw) as { imageUrl?: string; runId?: string | null; timestamp?: number }
    const fresh = typeof handed?.timestamp === 'number' && Date.now() - handed.timestamp < FRESH_MS
    return handed?.imageUrl && fresh ? { imageUrl: handed.imageUrl, runId: handed.runId ?? null } : null
  } catch {
    return null
  }
}
