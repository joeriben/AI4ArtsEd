/**
 * Scene document intake — the canonical, view-independent way a PDF reaches
 * the scene capsule pipeline (UCD-133 on the UCD-132 backend).
 *
 * THE CONTRACT (what a surface may assume, all of it UCD-132's own routes):
 *
 *   POST /api/scene/upload (multipart: `document` + `journal_id`) runs the
 *   Stage-A admission gate synchronously BEFORE any storage or enqueue — a
 *   rejected file costs nothing and comes back as HTTP 400 with a German
 *   plain-language reason. A re-upload of a document the session already
 *   analysed comes back as HTTP 409 `duplicate` (the session's hash index;
 *   a document known to the library is also refused — no second analysis
 *   anywhere). An admitted file returns `job_id` + `doc_id` and is analysed
 *   by the FIFO worker; GET /api/scene/jobs/<job_id> reports its state. The
 *   analysed document lives in the SESSION's document space and is read back
 *   through GET /api/scene/documents/<doc_id>?journal_id=<id> with its
 *   capsules (anchor/scene/prompt/safety), its counts, and provenance.
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

export interface SceneCapsule {
  /** Textanker: chapter/unit heading + in-vivo probe of the digest. */
  anchor: { chapter: string; probe: string }
  /** The visual scene in one line (place, figures, action, mood). */
  scene: string
  /** The finished image prompt, deterministically built from the capsule. */
  prompt: string
  /** The capsule gate's verdict — only `pass` capsules are ever stored. */
  safety: { verdict: string; categories: string[] }
}

export interface SceneDocument {
  docId: string
  title: string
  capsules: SceneCapsule[]
  /** Flagged segments — reported as a COUNT, never as content. */
  flagged: number
  /** Capsules the capsule gate discarded — a count, same rule. */
  discarded: number
  meta: {
    analyzedAt?: string
    analysisModel?: string
    analysisLang?: string
  }
}

export type SceneUploadOutcome =
  | { status: 'accepted'; jobId: string; docId: string }
  | { status: 'duplicate'; docId: string }
  | { status: 'rejected'; reasonKey: string }

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
 * POST /api/scene/upload. Throws on network and parse failures (the caller
 * reports an operational notice); 400 and 409 are mapped outcomes, not
 * throws. The json()-before-ok order is uploadImageFile's own rule: an HTTP
 * failure with a non-JSON body surfaces the parse error, not a silent null.
 */
export async function uploadSceneDocument(file: File, journalId: string): Promise<SceneUploadOutcome> {
  const form = new FormData()
  form.append('document', file)
  form.append('journal_id', journalId)
  const res = await fetch('/api/scene/upload', { method: 'POST', body: form })
  // json() BEFORE the ok check, uploadImageFile's own rule: an HTTP failure
  // with a non-JSON body (proxy 413/502 HTML page) throws the parse error
  // instead of silently becoming a null the outcome logic would misread.
  const data = await res.json()
  if (res.status === 409 || (data && data.duplicate)) {
    return { status: 'duplicate', docId: (data?.doc_id as string) || '' }
  }
  if (!res.ok) {
    return { status: 'rejected', reasonKey: sceneRejectionKey(String(data?.error || '')) }
  }
  if (data && data.success) {
    return { status: 'accepted', jobId: String(data.job_id), docId: String(data.doc_id) }
  }
  throw new Error(data?.error || 'scene upload failed')
}

/** The worker's public job view, reduced to what a surface waits on. */
export interface SceneJobState {
  state: 'queued' | 'running' | 'done' | 'error' | 'cancelled' | string
  docId?: string
  message?: string
}

export async function fetchSceneJob(jobId: string): Promise<SceneJobState> {
  const res = await fetch(`/api/scene/jobs/${jobId}`)
  const data = await res.json()
  if (!res.ok || !data) throw new Error('scene job fetch failed')
  return { state: String(data.state), docId: data.doc_id, message: data.message }
}

/**
 * The wire records the reader routes answer with (their own shapes, not
 * this module's — see UCD-132's scene_routes/scene_document_space).
 */
interface WireCapsule {
  anchor?: { chapter?: string; probe?: string }
  scene?: string
  prompt?: string
  safety?: { verdict?: string; categories?: string[] }
}

interface WireDocument {
  doc_id?: string
  meta?: {
    title?: string
    analyzed_at?: string
    analysis_model?: string
    analysis_lang?: string
    n_flagged_segments?: number
    n_discarded_capsules?: number
  }
  n_flagged_segments?: number
  n_discarded_capsules?: number
  capsules?: WireCapsule[]
}

/**
 * One analysed document of the session, capsules and all — null when the
 * session no longer knows it (journal dropped): the space dies with the
 * session, and a stale card goes with the document it asked for.
 */
export async function fetchSceneDocument(journalId: string, docId: string): Promise<SceneDocument | null> {
  const res = await fetch(`/api/scene/documents/${docId}?journal_id=${encodeURIComponent(journalId)}`)
  // A document the session no longer knows (404, or the journal's space is
  // gone) is null, not a throw — the caller takes the stale card down with
  // the document it asked for. A parse error on a 2xx body still throws.
  if (!res.ok) return null
  const data: WireDocument = await res.json()
  if (!data) return null
  return {
    docId: String(data.doc_id || docId),
    title: String(data.meta?.title || ''),
    capsules: Array.isArray(data.capsules)
      ? data.capsules.map((c: WireCapsule) => ({
          anchor: { chapter: String(c.anchor?.chapter || ''), probe: String(c.anchor?.probe || '') },
          scene: String(c.scene || ''),
          prompt: String(c.prompt || ''),
          safety: {
            verdict: String(c.safety?.verdict || ''),
            categories: Array.isArray(c.safety?.categories) ? c.safety.categories.map(String) : [],
          },
        }))
      : [],
    flagged: Number(data.n_flagged_segments || 0),
    discarded: Number(data.n_discarded_capsules || 0),
    meta: {
      analyzedAt: data.meta?.analyzed_at,
      analysisModel: data.meta?.analysis_model,
      analysisLang: data.meta?.analysis_lang,
    },
  }
}

/** All analysed documents of the session (counts only — the surface lists). */
export async function listSceneDocuments(journalId: string): Promise<Array<{ docId: string }>> {
  const res = await fetch(`/api/scene/documents?journal_id=${encodeURIComponent(journalId)}`)
  const data: { documents?: Array<{ doc_id?: string }> } = await res.json()
  if (!res.ok || !data || !Array.isArray(data.documents)) throw new Error('scene document list failed')
  return data.documents.map((d: { doc_id?: string }) => ({ docId: String(d.doc_id) }))
}
