import { ref, watch, type Ref } from 'vue'

/** What the platform's own reader found in the delivered file (`read_media_disclosure`). */
export interface MediaDisclosure {
  /** Whether the file was there to be opened at all. */
  present: boolean
  marked: boolean
  description: string
  standard: string
  carrier: string
  digital_source_type: string
}

/**
 * The address the platform answers a file's AI-origin disclosure at, or '' where
 * there is no run to ask about.
 *
 * The medium's own address (`/api/media/<kind>/<run>[/<index>]`) is preferred
 * over a run id and a kind: a run that produced several pictures has one file
 * per index, and only the address says which of them is standing on the card.
 * Where a page hands an address that names no served file — a data: or blob:
 * URL it drew itself — there is nothing to open, and asking the run for "its
 * last file" instead would answer for a different picture than the one on the
 * card (Concept Algebra's result and reference cells share one run). The run
 * id arrives in several shapes on this platform — bare, or a path with the id
 * inside it — and only the id is meant; an upload (`/api/media/uploads/<id>`)
 * is nobody's run and has no marking to read.
 */
export function disclosureAddress(
  runId: string | null | undefined,
  mediaType: string | undefined,
  mediaUrl: string | undefined,
): string {
  let run = runId || ''
  let kind = mediaType || ''
  let index: string | undefined
  if (mediaUrl) {
    let path = ''
    try {
      path = new URL(mediaUrl, 'http://ai4artsed.invalid').pathname
    } catch {
      path = ''
    }
    const own = /^\/api\/media\/([^/?#]+)\/([^/?#]+)(?:\/(\d+))?/.exec(path)
    if (!own) return ''
    kind = own[1] || ''
    run = own[2] || ''
    index = own[3]
  }
  if (run.includes('/')) run = run.match(/(run_[^/]+)/)?.[1] || run
  if (!run.startsWith('run_')) return ''
  const query = kind ? `?type=${encodeURIComponent(kind)}` : ''
  return `/api/media/disclosure/${encodeURIComponent(run)}${index !== undefined ? `/${index}` : ''}${query}`
}

/**
 * The AI-Origin Disclosure (EU AI Act Art. 50), read out of the DELIVERED file
 * of a run. Art. 50 asks for the disclosure to travel WITH the medium, so what
 * is shown is not what the page believes was written: the server opens the
 * file and reports what is in it — including nothing, where the file carries
 * none. Lay in `views/x2x_flow.vue` from 2026-08-15, for the back
 * of the flow's own inspect layer alone; since 2026-09-22 it is read here, for
 * the back of every surface.
 *
 * Read only while `active`: a card back is rendered face down under every
 * card of a grid, and one request per card at mount is what that avoids. A
 * late answer to a question no longer asked is dropped.
 */
export function useMediaDisclosure(
  runId: Ref<string | null | undefined>,
  mediaType: Ref<string | undefined>,
  mediaUrl: Ref<string | undefined>,
  active: Ref<boolean>,
) {
  const disclosure = ref<MediaDisclosure | null>(null)
  /** Which address the current read-out belongs to. */
  let asked = ''

  watch(
    [runId, mediaType, mediaUrl, active],
    async () => {
      if (!active.value) return
      const address = disclosureAddress(runId.value, mediaType.value, mediaUrl.value)
      if (address === asked) return
      asked = address
      disclosure.value = null
      if (!address) return
      try {
        const r = await fetch(address)
        if (!r.ok || asked !== address) return
        const d = await r.json()
        if (asked !== address) return
        disclosure.value = {
          present: !!d.present,
          marked: !!d.marked,
          description: String(d.description || ''),
          standard: String(d.standard || ''),
          carrier: String(d.carrier || ''),
          digital_source_type: String(d.digital_source_type || ''),
        }
      } catch {
        // No read-out. The back stands without the row rather than with a wrong one.
      }
    },
    { immediate: true },
  )

  return { disclosure }
}
