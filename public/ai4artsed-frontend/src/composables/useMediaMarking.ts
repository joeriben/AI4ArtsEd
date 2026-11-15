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

import { carriesDisclosure, downloadBlob, unmarkedName } from '@/lib/downloadMedia'

/**
 * Hand bytes to the server for marking. Returns the original blob on failure.
 * `unmarked` where the disclosure is not in what comes back, read off the bytes.
 * Only for a medium: anything else (a preset, a workflow) is saved as it is.
 */
export async function markBlob(blob: Blob): Promise<{ blob: Blob; unmarked: boolean }> {
  let result = blob
  try {
    const form = new FormData()
    form.append('file', blob)
    const response = await fetch('/api/media/mark', { method: 'POST', body: form })
    if (response.ok) {
      const marked = await response.blob()
      if (marked.size > 0) result = marked
    }
  } catch {
    // The original goes out; its bytes say whether it carries the disclosure.
  }
  return { blob: result, unmarked: !(await carriesDisclosure(result)) }
}

/**
 * Save a blob the browser made, marked: the cause, or '' (lib/downloadMedia.ts).
 * A file the disclosure did not get into is saved with `_ai_generated` in its name.
 */
export async function downloadMarkedBlob(blob: Blob, filename: string): Promise<string> {
  const marked = await markBlob(blob)
  return downloadBlob(marked.blob, marked.unmarked ? unmarkedName(filename) : filename)
}
