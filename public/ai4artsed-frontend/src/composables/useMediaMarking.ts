/**
 * Downloading a file the browser itself assembled.
 *
 * Most downloads on this platform hand out a file the server wrote, and that
 * file carries the AI-origin disclosure the EU AI Act asks for. A few do not:
 * the cross-modal bench decodes a generated sound, lets someone loop and shape
 * it, and writes a completely new WAV out of the samples — 44 fresh header
 * bytes, and nothing of what the platform had written into the sound.
 *
 * Such a file can only be marked where the writers live, so it goes to the
 * server once on its way to the person saving it. If that fails, the download
 * still happens: a download that does not happen is worse than one that
 * carries nothing.
 */

import { downloadBlob } from '@/lib/downloadMedia'

/** Hand bytes to the server for marking. Returns the original blob on failure. */
export async function markBlob(blob: Blob): Promise<Blob> {
  try {
    const form = new FormData()
    form.append('file', blob)
    const response = await fetch('/api/media/mark', { method: 'POST', body: form })
    if (!response.ok) return blob
    const marked = await response.blob()
    return marked.size > 0 ? marked : blob
  } catch {
    return blob
  }
}

/** Save a blob the browser made, marked: the cause, or '' (lib/downloadMedia.ts). */
export async function downloadMarkedBlob(blob: Blob, filename: string): Promise<string> {
  return downloadBlob(await markBlob(blob), filename)
}
