import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  uploadSceneDocument,
  sceneRejectionKey,
  sceneBlockKey,
  fetchSceneJob,
  fetchSceneDocument,
  documentText,
  emptySceneDocument,
} from '../useSceneIntake'

/**
 * The document intake's own contract.
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

describe('sceneBlockKey', () => {
  it.each([
    ['personal_data', 'resonaScene.rej.personalData'],
    ['content', 'resonaScene.rej.further'],
    ['unavailable', 'resonaScene.unavailable'],
    ['symbol', 'resonaScene.rej.generic'],
  ])('says a block for %s as %s, a sentence that exists', async (reasonKey, key) => {
    expect(sceneBlockKey({ checkpoint: 'intake', field: 'document', reason_key: reasonKey, reason: '' }))
      .toBe(key)
    const { en } = await import('../../i18n/en')
    const sentence = key.split('.').reduce<unknown>(
      (node, part) => (node as Record<string, unknown> | undefined)?.[part], en)
    expect(typeof sentence).toBe('string')
  })
})

describe('uploadSceneDocument', () => {
  it('returns accepted with job and doc ids', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ success: true, job_id: 'j1', doc_id: 'd1' }))
    const out = await uploadSceneDocument(new File([], 'a.pdf', { type: 'application/pdf' }), 'sess', 'de')
    expect(out).toEqual({ status: 'accepted', jobId: 'j1', docId: 'd1' })
    const call = fetchMock.mock.calls[0]
    expect(String(call?.[0])).toBe('/api/scene/upload')
    const init = call?.[1] as RequestInit | undefined
    expect(init?.method).toBe('POST')
    const form = init?.body as FormData
    expect(form.get('journal_id')).toBe('sess')
    expect(form.get('lang')).toBe('de')
    expect((form.get('document') as File).name).toBe('a.pdf')
  })

  it('returns a duplicate (409), not an error — the summary that exists is the answer', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ success: false, duplicate: true, doc_id: 'd1', error: 'bereits analysiert' }, false, 409))
    const out = await uploadSceneDocument(new File([], 'a.pdf'), 'sess', 'de')
    expect(out).toEqual({ status: 'duplicate', docId: 'd1' })
  })

  it('carries the job of a summary this session is still running', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ success: false, duplicate: true, doc_id: 'd1', job_id: 'j1', error: 'läuft' }, false, 409))
    const out = await uploadSceneDocument(new File([], 'a.pdf'), 'sess', 'de')
    expect(out).toEqual({ status: 'duplicate', docId: 'd1', jobId: 'j1' })
  })

  it('maps a gate rejection (400) to its category, never carrying the sentence', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ error: 'Dokument nicht angenommen: Kennzeichen verfassungswidriger Organisationen.' }, false, 400))
    const out = await uploadSceneDocument(new File([], 'a.pdf'), 'sess', 'de')
    expect(out).toEqual({ status: 'rejected', reasonKey: 'para86a' })
    expect(JSON.stringify(out)).not.toContain('Kennzeichen')
  })

  it('returns a refused name (403) with its block message', async () => {
    const block = { checkpoint: 'intake', field: 'title', reason_key: 'personal_data', reason: '' }
    fetchMock.mockResolvedValueOnce(jsonResponse({ error: 'safety_blocked', safety_block: block }, false, 403))
    const out = await uploadSceneDocument(new File([], 'a.pdf'), 'sess', 'de')
    expect(out).toEqual({ status: 'refused', block })
  })

  it('throws on a non-JSON failure body (uploadImageFile order rule)', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false, status: 502, statusText: 'Bad Gateway',
      json: () => Promise.reject(new SyntaxError('Unexpected token <')),
    } as Response)
    await expect(uploadSceneDocument(new File([], 'a.pdf'), 'sess', 'de')).rejects.toThrow()
  })
})

describe('fetchSceneJob / fetchSceneDocument', () => {
  it('reduces the job view to state and ids', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ state: 'running', doc_id: 'd1', message: 'queued' }))
    expect(await fetchSceneJob('j1')).toEqual({ state: 'running', docId: 'd1', message: 'queued' })
  })

  it('carries how far the analysis is, once the pipeline reports it', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({
      state: 'running', doc_id: 'd1', message: 'summary',
      progress: { units_done: 7, units_total: 35 },
    }))
    expect((await fetchSceneJob('j1')).progress).toEqual({ unitsDone: 7, unitsTotal: 35 })
  })

  it('carries the block message of a document the intake refused', async () => {
    const block = { checkpoint: 'intake', field: 'document[2]', reason_key: 'content', reason: '' }
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ state: 'blocked', doc_id: 'd1', message: 'blocked', safety_block: block }))
    expect(await fetchSceneJob('j1')).toEqual({ state: 'blocked', docId: 'd1', message: 'blocked', block })
  })

  it('says a job the server no longer knows is gone, and does not throw', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ error: 'unknown job' }, false, 404))
    expect(await fetchSceneJob('j1')).toEqual({ state: 'gone' })
  })

  it('reads the summary the route answers with: profile, sections, glossary, count, provenance', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({
      doc_id: 'd1',
      meta: {
        title: 'Probe', analyzed_at: '2026-09-27T16:00:00+00:00',
        analysis_model: 'mammouth/glm-5.3', analysis_lang: 'de', n_withheld: 2,
      },
      summary: {
        profile: 'Ein Schulatelier.',
        sections: [{ heading: 'Das Atelier', body: 'Jeden Dienstag.' }],
        glossary: [{ term: 'Atelier', definition: 'Werkraum' }],
      },
      n_withheld: 2,
    }))
    const doc = await fetchSceneDocument('sess', 'd1')
    expect(doc?.docId).toBe('d1')
    expect(doc?.title).toBe('Probe')
    expect(doc?.profile).toBe('Ein Schulatelier.')
    expect(doc?.sections).toEqual([{ heading: 'Das Atelier', body: 'Jeden Dienstag.' }])
    expect(doc?.glossary).toEqual([{ term: 'Atelier', definition: 'Werkraum' }])
    expect(doc?.withheld).toBe(2)
    expect(doc?.meta.analysisModel).toBe('mammouth/glm-5.3')
  })

  it('returns null for a document the session does not hold', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ error: 'unknown document' }, false, 404))
    expect(await fetchSceneDocument('sess', 'gone')).toBeNull()
  })
})

describe('documentText', () => {
  const doc = (over: object) => ({ ...emptySceneDocument('t'), ...over })

  it('is the profile', () => {
    expect(documentText(doc({ profile: ' Profil ', sections: [{ heading: 'H', body: 'B' }] }))).toBe('Profil')
  })

  it('is the first section where the check withheld the profile', () => {
    expect(documentText(doc({ sections: [{ heading: 'H', body: ' B ' }, { heading: 'I', body: 'C' }] }))).toBe('B')
  })

  it('is empty while the card stands for a summary that runs', () => {
    expect(documentText(emptySceneDocument('a.pdf'))).toBe('')
  })
})
