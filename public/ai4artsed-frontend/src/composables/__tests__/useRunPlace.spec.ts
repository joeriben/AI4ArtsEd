import { describe, it, expect, vi, beforeEach } from 'vitest'

/**
 * The line in the bar belongs to ONE stream at a time.
 *
 * A page runs several streams at once and the short ones end first — a
 * back-translation, the check on a dropped picture, a turn of the chat figure
 * that is mounted on every page. Every one of them goes through the same
 * reader as an instrument's run of several minutes, so both halves have to
 * hold: a stranger may not take the line, and a stranger may not take it away.
 *
 * The module keeps its state at module level, so each test takes a fresh copy
 * of it.
 */
async function fresh() {
  vi.resetModules()
  return {
    place: await import('../useRunPlace'),
    stream: await import('@/lib/sseStream'),
  }
}

const A = 'openai/gpt-5'
const B = 'stabilityai/stable-diffusion-3.5-large'

describe('useRunPlace — whoever holds the line', () => {
  let m: Awaited<ReturnType<typeof fresh>>['place']

  beforeEach(async () => {
    m = (await fresh()).place
  })

  it('says what the run was last sent to', () => {
    const run = {}
    m.noteRunPlace({ model: A, local: false }, run)
    expect(m.useRunPlace().place.value).toEqual({ model: A, local: false })
  })

  it('drops a second stream’s name while the first still holds it', () => {
    const long = {}
    const short = {}
    m.noteRunPlace({ model: A, local: true }, long)
    m.noteRunPlace({ model: B, local: false }, short)
    expect(m.useRunPlace().place.value).toEqual({ model: A, local: true })
  })

  it('leaves the line standing when a stranger ends', () => {
    const long = {}
    const short = {}
    m.noteRunPlace({ model: A, local: true }, long)
    m.noteRunPlace({ model: B, local: false }, short)
    m.clearRunPlace(short)
    expect(m.useRunPlace().place.value).toEqual({ model: A, local: true })
  })

  it('frees the line when its own stream ends, and the next one takes it', () => {
    const first = {}
    const second = {}
    m.noteRunPlace({ model: A, local: true }, first)
    m.clearRunPlace(first)
    expect(m.useRunPlace().place.value).toBeNull()
    m.noteRunPlace({ model: B, local: false }, second)
    expect(m.useRunPlace().place.value).toEqual({ model: B, local: false })
  })

  it('reads a model of null as “at nothing”, from the holder only', () => {
    const run = {}
    const other = {}
    m.noteRunPlace({ model: A, local: true }, run)
    m.noteRunPlace({ model: null, local: true }, other)
    expect(m.useRunPlace().place.value).toEqual({ model: A, local: true })
    m.noteRunPlace({ model: null, local: true }, run)
    expect(m.useRunPlace().place.value).toBeNull()
  })

  it('ignores a frame it cannot read rather than emptying the line', () => {
    const run = {}
    m.noteRunPlace({ model: A, local: true }, run)
    m.noteRunPlace(undefined, run)
    m.noteRunPlace({ local: true }, run)
    m.noteRunPlace({ model: 7 }, run)
    expect(m.useRunPlace().place.value).toEqual({ model: A, local: true })
  })
})

/** A body that hands out the given chunks and then ends. */
function body(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  let i = 0
  return {
    getReader: () => ({
      read: () =>
        i < chunks.length
          ? Promise.resolve({ done: false, value: encoder.encode(chunks[i++]) })
          : Promise.resolve({ done: true, value: undefined }),
      cancel: () => Promise.resolve(),
    }),
  } as unknown as ReadableStream<Uint8Array>
}

const framePlace = (model: string | null, local: boolean) =>
  `event: model_place\ndata: ${JSON.stringify({ model, local })}\n\n`

describe('readSseFrames — the model line is taken out of the stream', () => {
  it('swallows the frame, writes the line, and empties it at the end', async () => {
    const { place, stream } = await fresh()
    const seen: unknown[] = []
    for await (const frame of stream.readSseFrames(
      body([framePlace(A, false), 'data: {"n":1}\n\n']),
    )) {
      seen.push(frame)
      expect(place.useRunPlace().place.value).toEqual({ model: A, local: false })
    }
    expect(seen).toEqual([{ data: { n: 1 } }])
    expect(place.useRunPlace().place.value).toBeNull()
  })

  it('lets the run that holds the line keep it when a second stream ends', async () => {
    const { place, stream } = await fresh()
    // The long run announces first and stays open.
    const long = stream.readSseFrames(body([framePlace(A, true), 'data: {"n":1}\n\n']))
    await long.next()
    expect(place.useRunPlace().place.value).toEqual({ model: A, local: true })
    // A short one runs beside it, start to finish.
    for await (const _ of stream.readSseFrames(
      body([framePlace(B, false), 'data: {"n":2}\n\n']),
    )) { /* drained */ }
    expect(place.useRunPlace().place.value).toEqual({ model: A, local: true })
    await long.return(undefined)
    expect(place.useRunPlace().place.value).toBeNull()
  })
})
