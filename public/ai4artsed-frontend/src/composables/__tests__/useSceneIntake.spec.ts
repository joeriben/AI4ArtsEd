import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  uploadSceneDocument,
  sceneRejectionKey,
  fetchSceneJob,
  fetchSceneDocument,
  listSceneDocuments,
} from '../useSceneIntake'

/**
 * UCD-133 — the document intake's own contract.
 *
 * What is asserted is the LAYER LINE, not the backend's wording: a rejection
 * arrives as a CATEGORY KEY (the surface speaks it in the reader's language;
 * the gate's German sentence never crosses this line), a duplicate arrives
 * as a duplicate (not an error), and an acceptance carries the job and
 * document ids the follow path needs.
 */

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
})

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return { ok, status, statusText: 'status ' + status, json: () => Promise.resolve(body) } as Response
}

const GATE_TEXTS: Array<[string, string]> = [
  ['Datei nicht angenommen: kein lesbares PDF.', 'notPdf'],
  ['Datei nicht angenommen: verschlüsselte Dokumente werden nicht akzeptiert.', 'encrypted'],
  ['Datei nicht angenommen: das Dokument überschreitet das Seitenlimit von 1000 Seiten.', 'tooManyPages'],
  ['Datei nicht angenommen: das Dokument enthält eingebettete Dateien. Solche Dokumente werden nicht angenommen.', 'embeddedFile'],
  ['Datei nicht angenommen: das Dokument enthält Aktionen, die Programme starten. Solche Dokumente werden nicht angenommen.', 'launchAction'],
  ['Datei nicht angenommen: dieses Dokument ist gesperrt.', 'blocked'],
  ['Dokument nicht angenommen: Kennzeichen verfassungswidriger Organisationen.', 'para86a'],
  ['Dokument nicht angenommen: Inhalte verfassungswidriger Organisationen.', 'para86'],
  ['Dokument nicht angenommen: Inhalt entspricht nicht den Aufnahmekriterien.', 'further'],
  ['irgend etwas anderes', 'generic'],
]

describe('sceneRejectionKey', () => {
  it.each(GATE_TEXTS)('maps %s -> %s', (text, key) => {
    expect(sceneRejectionKey(text)).toBe(key)
  })

  it('maps every category key to an existing resonaScene.rej.* string', async () => {
    // The mapping is only worth its layer line if the hand-maintained source
    // actually has a sentence for every category the gate can hand over.
    const { en } = await import('../../i18n/en')
    const table: Record<string, string> = (en as unknown as { resonaScene: { rej: Record<string, string> } }).resonaScene.rej
    for (const [, key] of GATE_TEXTS) expect(table[key]).toBeTruthy()
  })
})

describe('uploadSceneDocument', () => {
  it('returns accepted with job and doc ids', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ success: true, job_id: 'j1', doc_id: 'd1' }))
    const out = await uploadSceneDocument(new File([], 'a.pdf', { type: 'application/pdf' }), 'sess')
    expect(out).toEqual({ status: 'accepted', jobId: 'j1', docId: 'd1' })
    const call = fetchMock.mock.calls[0]
    expect(String(call?.[0])).toBe('/api/scene/upload')
    const init = call?.[1] as RequestInit | undefined
    expect(init?.method).toBe('POST')
    const form = init?.body as FormData
    expect(form.get('journal_id')).toBe('sess')
    expect((form.get('document') as File).name).toBe('a.pdf')
  })

  it('returns a duplicate (409), not an error — the capsules that exist are the answer', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ success: false, duplicate: true, doc_id: 'd1', error: 'bereits analysiert' }, false, 409))
    const out = await uploadSceneDocument(new File([], 'a.pdf'), 'sess')
    expect(out).toEqual({ status: 'duplicate', docId: 'd1' })
  })

  it('maps a gate rejection (400) to its category, never carrying the sentence', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ error: 'Dokument nicht angenommen: Kennzeichen verfassungswidriger Organisationen.' }, false, 400))
    const out = await uploadSceneDocument(new File([], 'a.pdf'), 'sess')
    expect(out).toEqual({ status: 'rejected', reasonKey: 'para86a' })
    expect(JSON.stringify(out)).not.toContain('Kennzeichen')
  })

  it('throws on a non-JSON failure body (uploadImageFile order rule)', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false, status: 502, statusText: 'Bad Gateway',
      json: () => Promise.reject(new SyntaxError('Unexpected token <')),
    } as Response)
    await expect(uploadSceneDocument(new File([], 'a.pdf'), 'sess')).rejects.toThrow()
  })
})

describe('fetchSceneJob / fetchSceneDocument / listSceneDocuments', () => {
  it('reduces the job view to state and ids', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ state: 'running', doc_id: 'd1', message: 'queued' }))
    expect(await fetchSceneJob('j1')).toEqual({ state: 'running', docId: 'd1', message: 'queued' })
  })

  it('turns a document into capsules, counts and provenance', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({
      doc_id: 'd1',
      meta: {
        title: 'Probe', analyzed_at: '2026-09-27T16:00:00+00:00',
        analysis_model: 'mammouth/glm-5.3', analysis_lang: 'de',
        n_flagged_segments: 2, n_discarded_capsules: 1,
      },
      n_capsules: 1,
      n_flagged_segments: 2,
      n_discarded_capsules: 1,
      capsules: [{
        anchor: { chapter: 'Kapitel 1', probe: '…' },
        scene: 'Eine Werkstatt.',
        prompt: 'Ein Bild, das zeigt: Eine Werkstatt..',
        safety: { verdict: 'pass', categories: [] },
      }],
    }))
    const doc = await fetchSceneDocument('sess', 'd1')
    expect(doc?.docId).toBe('d1')
    expect(doc?.title).toBe('Probe')
    expect(doc?.flagged).toBe(2)
    expect(doc?.discarded).toBe(1)
    expect(doc?.capsules[0]!.prompt).toContain('Ein Bild')
    expect(doc?.meta.analysisModel).toBe('mammouth/glm-5.3')
  })

  it('returns null for a document the session no longer knows (space died with it)', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ error: 'unknown document' }, false, 404))
    expect(await fetchSceneDocument('sess', 'gone')).toBeNull()
  })

  it('lists the session documents as ids', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ documents: [{ doc_id: 'd1' }, { doc_id: 'd2' }] }))
    const ids = await listSceneDocuments('sess')
    expect(ids).toEqual([{ docId: 'd1' }, { docId: 'd2' }])
    expect(String(fetchMock.mock.calls[0]![0])).toContain('journal_id=sess')
  })
})
