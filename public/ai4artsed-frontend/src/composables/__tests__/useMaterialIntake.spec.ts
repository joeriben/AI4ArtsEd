import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
import {
  ARTIFACT_DT,
  FAVORITE_DT,
  PROMPT_DT,
  uploadImageFile,
  uploadCheckedImage,
  uploadCheckedImageFromUrl,
  uploadRefusal,
  UploadRefused,
  quickImageSafetyCheck,
  quickTextSafetyCheck,
  useMaterialIntake,
  type MaterialIntakeAdapter,
} from '../useMaterialIntake'
import type { AsmItem } from '../useAssemblageBoard'

// ---------------------------------------------------------------------------
// Fetch + response fakes
// ---------------------------------------------------------------------------

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

/** HTTP failure whose body is not JSON (proxy 413/502 HTML page). */
function htmlErrorResponse(): Response {
  return {
    ok: false,
    status: 502,
    statusText: 'Bad Gateway',
    json: () => Promise.reject(new SyntaxError('Unexpected token <')),
  } as Response
}

/** A response whose body is the given SSE frames, read the way fetch hands them over. */
function sseResponse(frames: string[]): Response {
  const encoder = new TextEncoder()
  let i = 0
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: () => Promise.resolve(null),
    body: {
      getReader: () => ({
        read: () =>
          i < frames.length
            ? Promise.resolve({ done: false, value: encoder.encode(frames[i++]!) })
            : Promise.resolve({ done: true, value: undefined }),
        cancel: () => Promise.resolve(),
      }),
    },
  } as unknown as Response
}

/**
 * How the quick check answers since it was moved onto the platform's streamed
 * transport: a heartbeat while the vision model works, then one `complete`
 * frame carrying the body and the status a plain POST would have returned.
 */
function streamedResponse(body: unknown, httpStatus = 200): Response {
  return sseResponse([
    ': heartbeat\n\n',
    'event: complete\ndata: ' + JSON.stringify({ http_status: httpStatus, body }) + '\n\n',
  ])
}

/**
 * What a server WITHOUT the streaming branch answers on the same route: one
 * plain JSON body, and a content type that says so. This is a deploy state
 * here, not a fault — the bundle is built on a machine and the backend comes
 * from git, so the two can differ by minutes.
 */
function plainJson(body: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    headers: {
      get: (name: string) =>
        name.toLowerCase() === 'content-type' ? 'application/json' : null,
    },
    json: () => Promise.resolve(body),
    body: {
      getReader: () => ({
        read: () => Promise.resolve({ done: true, value: undefined }),
        cancel: () => Promise.resolve(),
      }),
    },
  } as unknown as Response
}

/** A stream that breathed and then tore: no verdict ever arrives. */
function tornStreamResponse(): Response {
  return sseResponse([': heartbeat\n\n'])
}

function pngFile(name = 'a.png'): File {
  return new File(['x'], name, { type: 'image/png' })
}

function textFile(name = 'notes.txt'): File {
  return new File(['x'], name, { type: 'text/plain' })
}

function fileList(files: File[]): FileList {
  return Object.assign([...files], {
    item: (i: number) => files[i] ?? null,
  }) as unknown as FileList
}

/** Route the two intake endpoints; anything else is unexpected. */
function routeUploadAndSafety(safety: unknown = { safe: true }) {
  fetchMock.mockImplementation((input) => {
    const url = String(input)
    if (url === '/api/media/upload/image') {
      return Promise.resolve(
        jsonResponse({ success: true, image_id: 'img-9', image_path: '/srv/uploads/img-9.png' })
      )
    }
    if (url === '/api/schema/pipeline/safety/quick') {
      return Promise.resolve(streamedResponse(safety))
    }
    return Promise.reject(new Error('unexpected fetch: ' + url))
  })
}

// ---------------------------------------------------------------------------
// Adapter fake — minimal board world; returns real item objects so the
// composable's in-place mutations (position, upload state) stay observable.
// ---------------------------------------------------------------------------

function makeAdapter() {
  let seq = 0
  const item = (kind: AsmItem['kind'], x: number, y: number, w: number, h: number): AsmItem => {
    seq += 1
    return { id: 'it' + seq, kind, x, y, w, h }
  }
  return {
    toWorldPoint: vi.fn(
      (_e: { clientX: number; clientY: number }): { x: number; y: number } | null => ({ x: 200, y: 100 })
    ),
    addText: vi.fn((x = 70, y = 60) => item('text', x, y, 250, 120)),
    addImage: vi.fn((src: string, x = 90, y = 90): AsmItem => ({ ...item('image', x, y, 190, 150), src })),
    addMedia: vi.fn(
      (kind: 'audio' | 'video', src: string, runId: string, x = 120, y = 120): AsmItem => ({
        ...item(kind, x, y, 260, 80),
        src,
        runId,
      })
    ),
    removeItem: vi.fn(),
    placeArtifactImage: vi.fn(),
    placeArtifactMedia: vi.fn(),
    artifactDragSource: vi.fn((): { runId: string; src: string } | null => null),
    onUserImageIntake: vi.fn(),
    reportSafetyBlocked: vi.fn(),
    reportSafetyAnalysis: vi.fn(),
  } satisfies MaterialIntakeAdapter
}

function makeIntake() {
  const adapter = makeAdapter()
  const intake = useMaterialIntake({ adapter, fileInput: ref<HTMLInputElement | null>(null) })
  return { adapter, intake }
}

function dragEvent(data: Partial<Record<string, string>>, files: File[] = []): DragEvent {
  return {
    clientX: 10,
    clientY: 20,
    dataTransfer: {
      getData: (type: string) => data[type] ?? '',
      files: fileList(files),
    },
  } as unknown as DragEvent
}

// ---------------------------------------------------------------------------
// MIME constants
// ---------------------------------------------------------------------------

describe('material MIME constants', () => {
  it('are exported and distinct', () => {
    const all = [ARTIFACT_DT, FAVORITE_DT, PROMPT_DT]
    expect(new Set(all).size).toBe(3)
    for (const dt of all) expect(dt).toMatch(/^application\/x-ai4artsed-/)
  })
})

// ---------------------------------------------------------------------------
// uploadImageFile
// ---------------------------------------------------------------------------

describe('uploadImageFile', () => {
  it('POSTs the file as form data and returns the upload shape', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        image_id: 'img-1',
        image_path: '/srv/uploads/img-1.png',
        filename: 'cat.png',
      })
    )
    const up = await uploadImageFile(pngFile('cat.png'))
    expect(up.imageId).toBe('img-1')
    expect(up.path).toBe('/srv/uploads/img-1.png')
    expect(up.servedUrl).toBe('/api/media/uploads/img-1')
    expect(up.filename).toBe('cat.png')
    expect(up.raw).toMatchObject({ success: true, image_id: 'img-1' })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('/api/media/upload/image')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBeInstanceOf(FormData)
  })

  it('surfaces the res.json() parse error on a non-JSON error body (json runs before the ok-check)', async () => {
    fetchMock.mockResolvedValueOnce(htmlErrorResponse())
    // NOT the generic 'upload failed' — res.json() runs BEFORE the !res.ok
    // check, and that order is load-bearing (see the module docstring).
    await expect(uploadImageFile(pngFile())).rejects.toThrow('Unexpected token <')
  })

  it('throws Error(data.error) on a JSON body with success:false', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ success: false, error: 'no space left' }))
    await expect(uploadImageFile(pngFile())).rejects.toThrow('no space left')
  })

  it('falls back to the generic message when the JSON error body names none', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ success: false }))
    await expect(uploadImageFile(pngFile())).rejects.toThrow('upload failed')
  })

  it('names the recorded picture it was fetched from, and nothing where there is none', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ success: true, image_id: 'img-1', image_path: '/srv/uploads/img-1.png' })
    )
    await uploadImageFile(pngFile(), '/api/media/image/run_x/0')
    await uploadImageFile(pngFile())
    const sent = fetchMock.mock.calls.map(([, init]) => (init?.body as FormData).get('source'))
    expect(sent).toEqual(['/api/media/image/run_x/0', null])
  })

  it('a picture refused where it came in throws the refusal, not a transfer failure', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ error: 'safety_blocked', safety_block: REFUSED_AT_UPLOAD }, false, 403)
    )
    const err = await uploadImageFile(pngFile()).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(UploadRefused)
    expect(uploadRefusal(err)).toEqual({ safe: false, block: REFUSED_AT_UPLOAD })
    expect((err as { said?: string }).said).toBeUndefined()
  })

  it('an intake check that could not run reads as a fault of the platform', async () => {
    const unavailable = { ...REFUSED_AT_UPLOAD, reason_key: 'unavailable' }
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ error: 'safety_blocked', safety_block: unavailable }, false, 403)
    )
    const err = await uploadImageFile(pngFile()).catch((e: unknown) => e)
    expect(uploadRefusal(err)).toEqual({ safe: false, block: unavailable, operational: true })
  })

  it('any other failure is no refusal', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ success: false, error: 'no space left' }))
    const err = await uploadImageFile(pngFile()).catch((e: unknown) => e)
    expect(uploadRefusal(err)).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// uploadCheckedImage — the upload and the verdict, as one step
// ---------------------------------------------------------------------------

/** The block message the upload sends where its intake check refused the picture. */
const REFUSED_AT_UPLOAD = { checkpoint: 'intake', field: 'file', reason_key: 'image_content', reason: 'refused' }

describe('uploadCheckedImage', () => {
  it('a refusal at the upload is the answer, and the quick check is not asked', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ error: 'safety_blocked', safety_block: REFUSED_AT_UPLOAD }, false, 403)
    )
    const { up, safety } = await uploadCheckedImage(pngFile())
    expect(up).toBeNull()
    expect(safety).toEqual({ safe: false, block: REFUSED_AT_UPLOAD })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('a picture that went up is read by the quick check', async () => {
    routeUploadAndSafety({ safe: true })
    const { up, safety } = await uploadCheckedImage(pngFile())
    expect(up?.path).toBe('/srv/uploads/img-9.png')
    expect(safety.safe).toBe(true)
    const [, init] = fetchMock.mock.calls[1]!
    expect(JSON.parse(String(init?.body)).image_path).toBe('/srv/uploads/img-9.png')
  })

  it('any other failure of the upload throws as before', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ success: false, error: 'no space left' }))
    await expect(uploadCheckedImage(pngFile())).rejects.toThrow('no space left')
  })

  it('a picture fetched by its address names that address to the upload', async () => {
    fetchMock.mockImplementation((input, init) => {
      const url = String(input)
      if (url === '/api/media/image/run_x/0') {
        return Promise.resolve({
          ok: true, status: 200,
          blob: () => Promise.resolve(new Blob(['png'], { type: 'image/png' })),
        } as unknown as Response)
      }
      if (url === '/api/media/upload/image') {
        expect((init?.body as FormData).get('source')).toBe('/api/media/image/run_x/0')
        return Promise.resolve(
          jsonResponse({ success: true, image_id: 'img-9', image_path: '/srv/uploads/img-9.png' })
        )
      }
      if (url === '/api/schema/pipeline/safety/quick') {
        return Promise.resolve(streamedResponse({ safe: true }))
      }
      return Promise.reject(new Error('unexpected fetch: ' + url))
    })
    const { up, safety } = await uploadCheckedImageFromUrl('/api/media/image/run_x/0', 'run_x.png')
    expect(up?.imageId).toBe('img-9')
    expect(safety.safe).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// quickImageSafetyCheck
// ---------------------------------------------------------------------------

/** The block messages the quick route sends with a refusal (`safety_block`). */
const IMAGE_REFUSED = { checkpoint: 'intake', field: 'image', reason_key: 'image_content', reason: 'refused' }
const UNAVAILABLE = (reason: string) => ({ checkpoint: 'intake', field: 'image', reason_key: 'unavailable', reason })

describe('quickImageSafetyCheck', () => {
  it('asks for the stream and passes a safe verdict through with the VLM description', async () => {
    fetchMock.mockResolvedValueOnce(streamedResponse({ safe: true, vlm_description: 'a drawing of a fox' }))
    const r = await quickImageSafetyCheck('/srv/uploads/img-1.png')
    expect(r).toEqual({ safe: true, errorMessage: undefined, vlmDescription: 'a drawing of a fox' })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('/api/schema/pipeline/safety/quick')
    expect(init?.method).toBe('POST')
    // enable_streaming is what opts this route into the stream; without it the
    // request is the silent POST the edge was cutting at ~100 s.
    expect(JSON.parse(String(init?.body))).toEqual({
      image_path: '/srv/uploads/img-1.png',
      enable_streaming: true,
      // The second name of the same transport. /pipeline/interception reads
      // `enable_streaming` as an older protocol of its own, so this client says
      // which one it means rather than leaving a route to guess.
      enable_answer_streaming: true,
    })
  })

  it('maps an unsafe body to safe:false with message and description', async () => {
    fetchMock.mockResolvedValueOnce(
      streamedResponse({
        safe: false, error_message: 'blocked for this room', vlm_description: 'a weapon',
        safety_block: IMAGE_REFUSED,
      })
    )
    expect(await quickImageSafetyCheck('/p')).toEqual({
      safe: false,
      errorMessage: 'blocked for this room',
      vlmDescription: 'a weapon',
      block: IMAGE_REFUSED,
    })
  })

  it('blocks on a refusal that arrives as a plain JSON body rather than a stream', async () => {
    // The deploy window: this bundle asks for the stream and reaches a backend
    // that has not been restarted, which answers the route with one JSON
    // object. That object is the verdict, and it has to be read as one: taken
    // for a torn connection it would land in the catch, where the picture is
    // held back as a fault of the platform — and a refusal would then reach the
    // child as „the check could not run" instead of as the answer it is.
    fetchMock.mockResolvedValueOnce(
      plainJson({ safe: false, error_message: 'blocked for this room' })
    )
    expect(await quickImageSafetyCheck('/p')).toEqual({
      safe: false,
      errorMessage: 'blocked for this room',
      vlmDescription: undefined,
    })
  })

  it('blocks on a parseable body without safe:true', async () => {
    fetchMock.mockResolvedValueOnce(streamedResponse({}))
    expect((await quickImageSafetyCheck('/p')).safe).toBe(false)
  })

  it('refuses a request it has no picture for', async () => {
    // An upload whose answer carried no `image_path` used to send the field
    // undefined, which JSON.stringify drops — and the route answers a body with
    // no path at all `{"checks_passed": [], "safe": true}`, measured through the
    // tunnel on 2026-09-04. Nothing here is a verdict, and it never reaches the
    // route now.
    expect(await quickImageSafetyCheck('')).toEqual({ safe: false, operational: true })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('reads the DSGVO branch\'s unavailable model as operational, not as a name', async () => {
    // The quick route says this one under a DSGVO prefix when the model that
    // verifies a name cannot be reached. Read by the prefix it told the writer
    // their text held a person's name, while in truth nothing had read it. The
    // block message says which it is, whatever prefix the wording wears.
    fetchMock.mockResolvedValueOnce(
      streamedResponse({
        safe: false,
        error_message: 'DSGVO: Sicherheitsprüfung nicht verfügbar. Bitte GPU Service neustarten.',
        safety_block: UNAVAILABLE('DSGVO: Sicherheitsprüfung nicht verfügbar. Bitte GPU Service neustarten.'),
      })
    )
    expect((await quickImageSafetyCheck('/p')).operational).toBe(true)
  })

  it('calls a body that carries no verdict operational, not a rating', async () => {
    // The transport hands a gateway page or an error body back as a BODY rather
    // than throwing, so this — and not the catch — is where most operational
    // failures arrive. Without `operational` the surfaces would tell the child
    // an image AI had rated their picture unsuitable.
    fetchMock.mockResolvedValueOnce(streamedResponse({ status: 'error', error: 'upstream gone' }))
    expect(await quickImageSafetyCheck('/p')).toEqual({ safe: false, operational: true })
  })

  it('reads the server\'s own operational refusal as operational', async () => {
    fetchMock.mockResolvedValueOnce(
      streamedResponse({
        safe: false, error_message: '⚠️ Technische Störung bei der Bildprüfung',
        safety_block: UNAVAILABLE('⚠️ Technische Störung bei der Bildprüfung'),
      })
    )
    const r = await quickImageSafetyCheck('/p')
    expect(r.safe).toBe(false)
    expect(r.operational).toBe(true)
  })

  it('leaves a content refusal unmarked, so it keeps its own sentence', async () => {
    fetchMock.mockResolvedValueOnce(
      streamedResponse({ safe: false, error_message: 'refused', safety_block: IMAGE_REFUSED })
    )
    const r = await quickImageSafetyCheck('/p')
    expect(r.operational).toBeUndefined()
    expect(r.block).toEqual(IMAGE_REFUSED)
  })

  it('reads the refusal out of a terminal frame that carries a failure status', async () => {
    // The route answers 200 in every branch today, so this is the guarantee and
    // not the observed case: a status inside the envelope must never turn the
    // refusal it travels with into a thrown error — the catch holds the picture
    // back too, but it would say the check had not run when in truth it had.
    fetchMock.mockResolvedValueOnce(
      streamedResponse({ safe: false, error_message: 'blocked for this room' }, 500)
    )
    expect((await quickImageSafetyCheck('/p')).safe).toBe(false)
  })

  it('blocks on a refusal that arrived without the stream ever opening', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 502,
      statusText: 'Bad Gateway',
      json: () => Promise.resolve({ safe: false, error_message: 'blocked for this room' }),
    } as unknown as Response)
    expect(await quickImageSafetyCheck('/p')).toEqual({
      safe: false,
      errorMessage: 'blocked for this room',
      vlmDescription: undefined,
    })
  })

  it('holds the picture back when the stream never opened and left nothing readable', async () => {
    fetchMock.mockResolvedValueOnce(htmlErrorResponse())
    expect(await quickImageSafetyCheck('/p')).toEqual({ safe: false, operational: true })
  })

  it('holds the picture back on a stream that tore before its verdict', async () => {
    fetchMock.mockResolvedValueOnce(tornStreamResponse())
    expect(await quickImageSafetyCheck('/p')).toEqual({ safe: false, operational: true })
  })

  it('holds the picture back on a network error', async () => {
    // These three answered `{ safe: true }` until 2026-09-04 — a verdict that
    // never arrived became a permission, which is the first of the four
    // patterns this platform's check chain has been broken by since 2025.
    // `operational` is what lets the surface say the fault was the platform's
    // rather than rate the picture.
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    expect(await quickImageSafetyCheck('/p')).toEqual({ safe: false, operational: true })
  })
})

// ---------------------------------------------------------------------------
// onDrop dispatch order: artifact -> favorite -> held prompt -> OS files
// ---------------------------------------------------------------------------

describe('onDrop dispatch order', () => {
  it('an artifact payload wins over favorite, held prompt and files', () => {
    const { adapter, intake } = makeIntake()
    intake.onDrop(
      dragEvent(
        {
          [ARTIFACT_DT]: JSON.stringify({ kind: 'audio', runId: 'run-a', src: 'blob:audio' }),
          [FAVORITE_DT]: JSON.stringify({ run_id: 'run-f', media_type: 'image' }),
          [PROMPT_DT]: 'a held prompt',
        },
        [pngFile()]
      )
    )
    expect(adapter.addMedia).toHaveBeenCalledWith('audio', 'blob:audio', 'run-a')
    const placed = adapter.addMedia.mock.results[0]!.value as AsmItem
    expect(placed.x).toBe(70) // Math.round(200 - 260 / 2): centered on the drop point
    expect(placed.y).toBe(60) // Math.round(100 - 80 / 2)
    expect(fetchMock).not.toHaveBeenCalled() // no favorite restore, no upload
    expect(adapter.addText).not.toHaveBeenCalled()
    expect(adapter.addImage).not.toHaveBeenCalled()
  })

  it('a favorite payload wins over held prompt and files', async () => {
    const { adapter, intake } = makeIntake()
    fetchMock.mockResolvedValueOnce(jsonResponse({ transformed_text: 'the favorite words' }))
    intake.onDrop(
      dragEvent(
        {
          [FAVORITE_DT]: JSON.stringify({ run_id: 'run-f', media_type: 'text' }),
          [PROMPT_DT]: 'a held prompt',
        },
        [pngFile()]
      )
    )
    await vi.waitFor(() => expect(adapter.addText).toHaveBeenCalledTimes(1))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('/api/favorites/run-f/restore')
    expect((adapter.addText.mock.results[0]!.value as AsmItem).text).toBe('the favorite words')
    expect(adapter.addImage).not.toHaveBeenCalled() // files ignored
  })

  it('a held prompt wins over files and lands as text at the drop point', () => {
    const { adapter, intake } = makeIntake()
    intake.onDrop(dragEvent({ [PROMPT_DT]: 'a held prompt' }, [pngFile()]))
    expect(adapter.addText).toHaveBeenCalledWith(75, 40) // Math.round(200-125), Math.round(100-60)
    expect((adapter.addText.mock.results[0]!.value as AsmItem).text).toBe('a held prompt')
    expect(adapter.addImage).not.toHaveBeenCalled()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('with no payloads, OS files route into image intake', async () => {
    const { adapter, intake } = makeIntake()
    routeUploadAndSafety()
    intake.onDrop(dragEvent({}, [pngFile()]))
    expect(adapter.onUserImageIntake).toHaveBeenCalledTimes(1)
    await vi.waitFor(() => expect(adapter.addImage).toHaveBeenCalledTimes(1))
    // let the upload settle before the fetch stub is torn down
    await vi.waitFor(() =>
      expect((adapter.addImage.mock.results[0]!.value as AsmItem).uploading).toBe(false)
    )
  })

  it('a malformed artifact payload consumes the drop without falling through', () => {
    const { adapter, intake } = makeIntake()
    intake.onDrop(dragEvent({ [ARTIFACT_DT]: 'not json', [PROMPT_DT]: 'a held prompt' }))
    expect(adapter.addMedia).not.toHaveBeenCalled()
    expect(adapter.addText).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// dropFavorite — the moment returns with its provenance
// ---------------------------------------------------------------------------

describe('dropFavorite', () => {
  const at = { x: 300, y: 200 }

  it('text: becomes board text, the words the run was MADE FROM', async () => {
    const { adapter, intake } = makeIntake()
    fetchMock.mockResolvedValueOnce(jsonResponse({ transformed_text: 'transformed', input_text: 'original' }))
    await intake.dropFavorite('run-1', 'text', at)
    expect(adapter.addText).toHaveBeenCalledWith(300, 200)
    // What the plate and the large view of that run show, which is what
    // `resolveRunAs` hands to a field: one gesture, one answer.
    expect((adapter.addText.mock.results[0]!.value as AsmItem).text).toBe('original')

    fetchMock.mockResolvedValueOnce(jsonResponse({ input_text: 'original' }))
    await intake.dropFavorite('run-1', 'text', null)
    expect(adapter.addText).toHaveBeenLastCalledWith(80, 80)
    expect((adapter.addText.mock.results[1]!.value as AsmItem).text).toBe('original')
  })

  it('provenance keeps the GENERATION prompt, unlike the material a text drop hands over', async () => {
    const { adapter, intake } = makeIntake()
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        transformed_text: 'transformed',
        input_text: 'original',
        media_outputs: [{ type: 'image', url: '/api/media/img.png' }],
      })
    )
    await intake.dropFavorite('run-9', 'image', at)
    const meta = adapter.placeArtifactImage.mock.calls[0]![2] as AsmItem['meta']
    // The back of a card says what made the piece, as it does for a card that
    // fell out of a run (x2x_flow `finalPrompt` = transformed || prompt).
    expect(meta?.prompt).toBe('transformed')
  })

  it('image: re-places via placeArtifactImage with runId and provenance meta', async () => {
    const { adapter, intake } = makeIntake()
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        input_text: 'ein Fuchs aus Licht',
        schema: 'sd35_large',
        media_outputs: [{ url: '/api/media/run-2/out.png' }],
      })
    )
    await intake.dropFavorite('run-2', 'image', at)
    expect(adapter.placeArtifactImage).toHaveBeenCalledWith(
      'run-2',
      '/api/media/run-2/out.png',
      { prompt: 'ein Fuchs aus Licht', config: 'sd35_large', mediaType: 'image' },
      at
    )
    expect(adapter.placeArtifactMedia).not.toHaveBeenCalled()
  })

  it("music: places audio material carrying meta.mediaType 'music'", async () => {
    const { adapter, intake } = makeIntake()
    fetchMock.mockResolvedValueOnce(jsonResponse({ media_outputs: [{ url: '/api/media/run-3/out.mp3' }] }))
    await intake.dropFavorite('run-3', 'music', at)
    expect(adapter.placeArtifactMedia).toHaveBeenCalledWith(
      'audio',
      '/api/media/run-3/out.mp3',
      'run-3',
      { prompt: undefined, config: undefined, mediaType: 'music' },
      at
    )
  })

  it('types nothing on this table can hold yet are ignored', async () => {
    const { adapter, intake } = makeIntake()
    fetchMock.mockResolvedValue(jsonResponse({ media_outputs: [{ url: '/api/media/run-4/out.glb' }] }))
    await intake.dropFavorite('run-4', '3d', at)
    expect(adapter.placeArtifactImage).not.toHaveBeenCalled()
    expect(adapter.placeArtifactMedia).not.toHaveBeenCalled()
    expect(adapter.addText).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// ingestImage / readImages
// ---------------------------------------------------------------------------

describe('quickTextSafetyCheck', () => {
  it('passes a judged text through', async () => {
    fetchMock.mockResolvedValueOnce(streamedResponse({ safe: true, checks_passed: ['dsgvo_ner'] }))
    expect(await quickTextSafetyCheck('ein haus', 'de')).toEqual({
      safe: true,
      errorMessage: undefined,
      checks: ['dsgvo_ner'],
    })
  })

  it('holds a text nothing judged', async () => {
    // Same three shapes as the picture check, and the same answer: a body with
    // no verdict, a torn stream, a network error. Text carries a level too — a
    // memo brought onto a board reaches the chat model the way a typed line
    // does.
    fetchMock.mockResolvedValueOnce(streamedResponse({ status: 'error' }))
    expect(await quickTextSafetyCheck('ein haus', 'de')).toEqual({ safe: false, operational: true })
    fetchMock.mockResolvedValueOnce(tornStreamResponse())
    expect(await quickTextSafetyCheck('ein haus', 'de')).toEqual({ safe: false, operational: true })
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    expect(await quickTextSafetyCheck('ein haus', 'de')).toEqual({ safe: false, operational: true })
  })

  it('refuses to call the route for a text that is not there', async () => {
    expect(await quickTextSafetyCheck('   ', 'de')).toEqual({ safe: false, operational: true })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('marks the server\'s own operational refusal', async () => {
    fetchMock.mockResolvedValueOnce(
      streamedResponse({
        safe: false, error_message: 'Sicherheitssystem-Fehler',
        safety_block: { ...UNAVAILABLE('Sicherheitssystem-Fehler'), field: 'text' },
      })
    )
    expect((await quickTextSafetyCheck('ein haus', 'de')).operational).toBe(true)
  })
})

describe('ingestImage', () => {
  it('previews, uploads, safety-checks and switches to the served URL (fan-out by index)', async () => {
    const { adapter, intake } = makeIntake()
    routeUploadAndSafety({ safe: true, vlm_description: 'a sketch' })
    await intake.ingestImage(pngFile(), 1, { x: 200, y: 100 })
    const [src, x, y] = adapter.addImage.mock.calls[0]!
    expect(String(src).startsWith('data:')).toBe(true) // the preview is a data URL
    expect(x).toBe(124) // 100 + 1 * 24
    expect(y).toBe(114) // 90 + 1 * 24
    const placed = adapter.addImage.mock.results[0]!.value as AsmItem
    expect(placed.x).toBe(Math.round(200 - placed.w / 2) + 24) // centered under the pointer + fan-out
    expect(placed.y).toBe(Math.round(100 - placed.h / 2) + 24)
    expect(placed.imageId).toBe('img-9')
    expect(placed.path).toBe('/srv/uploads/img-9.png')
    expect(placed.src).toBe('/api/media/uploads/img-9') // no base64 kept
    expect(placed.uploading).toBe(false)
    expect(placed.failed).toBeUndefined()
    expect(adapter.reportSafetyAnalysis).toHaveBeenCalledWith('a sketch')
  })

  it('a safety block removes the item and reports it', async () => {
    const { adapter, intake } = makeIntake()
    routeUploadAndSafety({
      safe: false, error_message: 'not for this room', vlm_description: 'something',
      safety_block: IMAGE_REFUSED,
    })
    await intake.ingestImage(pngFile(), 0)
    const placed = adapter.addImage.mock.results[0]!.value as AsmItem
    expect(adapter.removeItem).toHaveBeenCalledWith(placed.id)
    expect(adapter.reportSafetyBlocked).toHaveBeenCalledWith({
      safe: false,
      errorMessage: 'not for this room',
      vlmDescription: 'something',
      block: IMAGE_REFUSED,
    })
    expect(placed.imageId).toBeUndefined() // never switched to the upload
  })

  it('takes the picture off the board when the safety endpoint is unreachable', async () => {
    const { adapter, intake } = makeIntake()
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url === '/api/media/upload/image') {
        return Promise.resolve(
          jsonResponse({ success: true, image_id: 'img-9', image_path: '/srv/uploads/img-9.png' })
        )
      }
      return Promise.reject(new TypeError('Failed to fetch'))
    })
    await intake.ingestImage(pngFile(), 0)
    const placed = adapter.addImage.mock.results[0]!.value as AsmItem
    expect(adapter.removeItem).toHaveBeenCalledWith(placed.id)
    expect(adapter.reportSafetyBlocked).toHaveBeenCalledWith({
      safe: false,
      operational: true,
    })
    expect(placed.imageId).toBeUndefined() // never switched to the upload
  })

  it('a picture refused at the upload comes off the board and is reported', async () => {
    const { adapter, intake } = makeIntake()
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ error: 'safety_blocked', safety_block: REFUSED_AT_UPLOAD }, false, 403)
    )
    await intake.ingestImage(pngFile(), 0)
    const placed = adapter.addImage.mock.results[0]!.value as AsmItem
    expect(adapter.removeItem).toHaveBeenCalledWith(placed.id)
    expect(adapter.reportSafetyBlocked).toHaveBeenCalledWith({ safe: false, block: REFUSED_AT_UPLOAD })
    expect(placed.failed).toBeUndefined()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('a failed upload marks the item instead of removing it', async () => {
    const { adapter, intake } = makeIntake()
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    await intake.ingestImage(pngFile(), 0)
    const placed = adapter.addImage.mock.results[0]!.value as AsmItem
    expect(placed.failed).toBe(true)
    expect(placed.uploading).toBe(false)
    expect(adapter.removeItem).not.toHaveBeenCalled()
  })
})

describe('readImages', () => {
  it('filters to images, hands routing back once, fans positions out by +i*24', async () => {
    const { adapter, intake } = makeIntake()
    routeUploadAndSafety()
    intake.readImages(fileList([pngFile('a.png'), textFile(), pngFile('b.png')]))
    expect(adapter.onUserImageIntake).toHaveBeenCalledTimes(1)
    await vi.waitFor(() => expect(adapter.addImage).toHaveBeenCalledTimes(2))
    const coords = adapter.addImage.mock.calls
      .map((c) => [c[1], c[2]])
      .sort((a, b) => Number(a[0]) - Number(b[0]))
    expect(coords).toEqual([
      [100, 90], // i = 0
      [124, 114], // i = 1 — the +i*24 fan-out
    ])
    // let both uploads settle before the fetch stub is torn down
    await vi.waitFor(() => {
      for (const r of adapter.addImage.mock.results) {
        expect((r.value as AsmItem).uploading).toBe(false)
      }
    })
  })

  it('does nothing (not even the routing handback) without an image file', () => {
    const { adapter, intake } = makeIntake()
    intake.readImages(fileList([textFile()]))
    expect(adapter.onUserImageIntake).not.toHaveBeenCalled()
    expect(adapter.addImage).not.toHaveBeenCalled()
  })
})
