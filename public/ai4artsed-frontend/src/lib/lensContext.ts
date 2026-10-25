/**
 * The wording of a Canvas lens in the reader's language: what an interception
 * node carries as its `contextPrompt` once a perspective is chosen on it.
 *
 * Asked for in two places since 2026-10-02 — the node's own select
 * (components/canvas/StageModule.vue) and a ready-made workflow being opened
 * (lib/canvasPresets.ts), which names its perspectives by id and takes their
 * CURRENT text when it opens rather than a copy frozen into the file. One
 * request, so the two cannot drift apart (Rule 13).
 *
 * `user_defined` is the blank perspective and has no wording to fetch. Where the
 * request fails the answer is empty, as it was on the node: the node then stands
 * with no perspective and hands its input on verbatim (services/canvas_executor.py);
 * a ready-made workflow refuses to open on it (lib/canvasPresets.ts).
 */
import { localized } from '@/i18n'

export async function lensContext(lensId: string, locale: string): Promise<string> {
  if (!lensId || lensId === 'user_defined') return ''
  try {
    const response = await fetch(`/api/interception/${encodeURIComponent(lensId)}`)
    if (!response.ok) return ''
    const data = await response.json()
    return localized(data.context || {}, locale) || ''
  } catch {
    return ''
  }
}
