/**
 * Document intake — the canonical, view-independent way a PDF reaches the
 * flow's summary job.
 *
 * THE CONTRACT (what a surface may assume, all of it scene_routes.py):
 *
 *   POST /api/scene/upload (multipart: `document`, `journal_id`, `lang`) runs
 *   the file check synchronously BEFORE any storage or enqueue — a rejected
 *   file costs nothing and comes back as HTTP 400 with a German plain-language
 *   reason. The document's name passes the platform's intake there too; a
 *   refused name comes back as HTTP 403 with the block message
 *   (`safety_block`). A file the platform has summarised in this language, in
 *   any session, comes back as HTTP 409 `duplicate` with its `doc_id`: the
 *   summary went through the check of this session's level, stands in this
 *   session's space, and no second analysis runs. A file this session is
 *   summarising right now comes back the same way, with the `job_id` of that
 *   job. A document known only to the library comes back as 409 with no
 *   `doc_id`. An admitted file returns `job_id` + `doc_id` and is summarised by
 *   the FIFO worker; GET /api/scene/jobs/<job_id> reports its state. The
 *   worker takes the document's text in at the intake before anything else
 *   reads it; a refused document ends its job as `blocked`, with the block
 *   message. The summary lives in the SESSION's document space and is read
 *   back through GET /api/scene/documents/<doc_id>?journal_id=<id>: its
 *   profile, sections, glossary, the count of parts the check withheld, and
 *   provenance. That read answers 404 for a document checked at a looser level
 *   than the session's. When the check gives no answer on a stored summary, the
 *   upload answers with the session's own copy if one stands at this level, and
 *   otherwise admits the file: the job asks again, and ends as a technical
 *   fault.
 *
 * WHY THE REJECTION TEXT IS NEVER SHOWN: the backend's reason sentences are
 * German wire text. They carry no forbidden term (the gate's own rule), but
 * they are one language's sentences shown to every reader. The intake maps
 * them to a CATEGORY (sceneRejectionKey); the surface says the category in
 * the reader's own words (i18n `resonaScene.rej.*`). The raw sentence never
 * crosses this line, so no re-worded backend text can ever repeat a term
 * the gate found.
 *
 * Sibling of uploadImageFile in useMaterialIntake.ts — one canonical
 * implementation, no second view recipe.
 */

import { safetyBlockOf, type SafetyBlock } from '@/composables/useGenerationStream'

/** One condensed section of the document. */
export interface SceneSection {
  heading: string
  body: string
}

/** One entry of the document's glossary. */
export interface SceneGlossaryEntry {
  term: string
  definition: string
}

export interface SceneDocument {
  docId: string
  title: string
  /** The library's profile: what the document claims and how it stands. */
  profile: string
  sections: SceneSection[]
  glossary: SceneGlossaryEntry[]
  /** Parts the check withheld — reported as a COUNT, never as content. */
  withheld: number
  meta: {
    analyzedAt?: string
    analysisModel?: string
    analysisLang?: string
  }
}

/** A document card with nothing read yet: only the name it stands under. */
export function emptySceneDocument(title: string): SceneDocument {
  return { docId: '', title, profile: '', sections: [], glossary: [], withheld: 0, meta: {} }
}

/**
 * What a run reads of a document: the profile, the one part that speaks for
 * the whole. A summary grows with its document, up to a thousand pages, and
 * the URL of a generation carries the run's text two or three times, which the
 * tunnel refuses somewhere between 60 and 120 KB (measured 2026-11-06). So the
 * sections stay on the card, and the carry button takes one further as a text
 * card. Where the check withheld the profile, the first section stands in for it.
 */
export function documentText(doc: SceneDocument): string {
  return doc.profile.trim() || doc.sections[0]?.body.trim() || ''
}

export type SceneUploadOutcome =
  | { status: 'accepted'; jobId: string; docId: string }
  | { status: 'duplicate'; docId: string; jobId?: string }
  | { status: 'rejected'; reasonKey: string }
  | { status: 'refused'; block: SafetyBlock }

/** The reason categories, in the order the gate's own texts are matched. */
const REJECTION_MATCHERS: Array<[string, RegExp]> = [
  ['notPdf', /kein lesbares PDF/],
  ['encrypted', /verschlüsselte Dokumente/],
  ['tooManyPages', /Seitenlimit/],
  ['embeddedFile', /eingebettete Dateien/],
  ['launchAction', /Aktionen, die Programme starten/],
  ['blocked', /gesperrt/],
  ['para86a', /Kennzeichen verfassungswidriger/],
  ['para86', /Inhalte verfassungswidriger/],
  ['further', /Aufnahmekriterien/],
]

/**
 * Which rejection category a backend reason sentence is. The sentences are
 * the gate's own (_REJECT_MESSAGES in upload_gate.py); a sentence nobody
 * mapped is `generic` — still a category, still never the sentence itself.
 */
export function sceneRejectionKey(errorText: string): string {
  for (const [key, re] of REJECTION_MATCHERS) {
    if (re.test(errorText)) return key
  }
  return 'generic'
}

/**
 * Which sentence a block message of the document intake is. A document is
 * said as a document, never as a prompt, and by the kind of refusal, never
 * by what was found.
 */
export function sceneBlockKey(block: SafetyBlock): string {
  switch (block.reason_key) {
    case 'unavailable': return 'resonaScene.unavailable'
    case 'personal_data': return 'resonaScene.rej.personalData'
    case 'content': return 'resonaScene.rej.further'
    default: return 'resonaScene.rej.generic'
  }
}

/**
 * POST /api/scene/upload. `lang` is the language of the surface, which the
 * summary is written in. Throws on network and parse failures (the caller
 * reports an operational notice); 400 and 409 are mapped outcomes, not
 * throws. The json()-before-ok order is uploadImageFile's own rule: an HTTP
 * failure with a non-JSON body surfaces the parse error, not a silent null.
 */
export async function uploadSceneDocument(
  file: File,
  journalId: string,
  lang: string
): Promise<SceneUploadOutcome> {
  const form = new FormData()
  form.append('document', file)
  form.append('journal_id', journalId)
  form.append('lang', lang)
  const res = await fetch('/api/scene/upload', { method: 'POST', body: form })
  // json() BEFORE the ok check, uploadImageFile's own rule: an HTTP failure
  // with a non-JSON body (proxy 413/502 HTML page) throws the parse error
  // instead of silently becoming a null the outcome logic would misread.
  const data = await res.json()
  // A name the intake refused: the block message, said by its kind.
  const block = res.status === 403 ? safetyBlockOf(data) : null
  if (block) return { status: 'refused', block }
  if (res.status === 409 || (data && data.duplicate)) {
    const docId = (data?.doc_id as string) || ''
    return data?.job_id
      ? { status: 'duplicate', docId, jobId: String(data.job_id) }
      : { status: 'duplicate', docId }
  }
  if (!res.ok) {
    return { status: 'rejected', reasonKey: sceneRejectionKey(String(data?.error || '')) }
  }
  if (data && data.success) {
    return { status: 'accepted', jobId: String(data.job_id), docId: String(data.doc_id) }
  }
  throw new Error(data?.error || 'scene upload failed')
}

/** How far a running summary is: the sections of the document condensed. */
export interface SceneJobProgress {
  unitsDone: number
  unitsTotal: number
}

/**
 * The worker's public job view, reduced to what a surface waits on. `gone`
 * is a job the server does not know (404): the worker keeps its jobs in
 * memory, so a backend restart ends every one that was running, and none
 * of them comes back.
 */
export interface SceneJobState {
  state: 'queued' | 'running' | 'done' | 'error' | 'cancelled' | 'blocked' | 'gone' | string
  docId?: string
  message?: string
  /** The block message of a document the intake refused (`blocked`). */
  block?: SafetyBlock
  /** Present once the pipeline knows its units; absent while the job waits or reads. */
  /** Present once the condensation knows its sections; absent while the job waits or reads. */
  progress?: SceneJobProgress
}

export async function fetchSceneJob(jobId: string): Promise<SceneJobState> {
  const res = await fetch(`/api/scene/jobs/${jobId}`)
  if (res.status === 404) return { state: 'gone' }
  const data = await res.json()
  if (!res.ok || !data) throw new Error('scene job fetch failed')
  const p = data.progress
  return {
    state: String(data.state),
    docId: data.doc_id,
    message: data.message,
    block: safetyBlockOf(data) ?? undefined,
    progress: p
      ? {
          unitsDone: Number(p.units_done) || 0,
          unitsTotal: Number(p.units_total) || 0,
        }
      : undefined,
  }
}

/** The wire record the reader route answers with (scene_document_space.get_document). */
interface WireDocument {
  doc_id?: string
  meta?: {
    title?: string
    analyzed_at?: string
    analysis_model?: string
    analysis_lang?: string
  }
  summary?: {
    profile?: string
    sections?: Array<{ heading?: string; body?: string }>
    glossary?: Array<{ term?: string; definition?: string }>
  }
  n_withheld?: number
}

/**
 * One summarised document of the session — null when the session does not hold
 * it or may not read it at its level: a stale card goes with the document it
 * asked for.
 */
export async function fetchSceneDocument(journalId: string, docId: string): Promise<SceneDocument | null> {
  const res = await fetch(`/api/scene/documents/${docId}?journal_id=${encodeURIComponent(journalId)}`)
  // A document the session does not hold (404, or the journal's space is
  // gone) is null, not a throw — the caller takes the stale card down with
  // the document it asked for. A parse error on a 2xx body still throws.
  if (!res.ok) return null
  const data: WireDocument = await res.json()
  if (!data) return null
  const s = data.summary
  return {
    docId: String(data.doc_id || docId),
    title: String(data.meta?.title || ''),
    profile: String(s?.profile || ''),
    sections: Array.isArray(s?.sections)
      ? s.sections.map((x) => ({ heading: String(x.heading || ''), body: String(x.body || '') }))
      : [],
    glossary: Array.isArray(s?.glossary)
      ? s.glossary.map((g) => ({ term: String(g.term || ''), definition: String(g.definition || '') }))
      : [],
    withheld: Number(data.n_withheld || 0),
    meta: {
      analyzedAt: data.meta?.analyzed_at,
      analysisModel: data.meta?.analysis_model,
      analysisLang: data.meta?.analysis_lang,
    },
  }
}
