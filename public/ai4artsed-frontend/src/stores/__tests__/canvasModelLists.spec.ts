/**
 * The board's lists of models (stores/canvas.ts loadLLMModels): asked again
 * while the board stands, an answer is never laid over one from a later load,
 * a later load that fails leaves the answer before it, a quiet load leaves the
 * board's overlay and error alone, and whoever waits is let go when the newest
 * load has settled and told whether the list lying there is as new as the one
 * it asked for.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { useCanvasStore } from '../canvas'

type Deferred = { promise: Promise<unknown>; resolve: (v: unknown) => void; reject: (e: unknown) => void }

function deferred(): Deferred {
  let resolve!: (v: unknown) => void
  let reject!: (e: unknown) => void
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

const answer = (...ids: string[]) => ({ ok: true, json: async () => ({ models: ids.map(id => ({ id, name: id })) }) })

/** fetch answering each call with the next of `answers`, in the order asked. */
function answering(): Deferred[] {
  const answers: Deferred[] = []
  vi.stubGlobal('fetch', vi.fn(() => {
    const d = deferred()
    answers.push(d)
    return d.promise
  }))
  return answers
}

const ids = (store: ReturnType<typeof useCanvasStore>) => store.llmModels.map(m => m.id)

/** Whether a promise has settled, without waiting for it. */
function tracked<T>(p: Promise<T>): { done: () => boolean; value: Promise<T> } {
  let settled = false
  void p.then(() => { settled = true }, () => { settled = true })
  return { done: () => settled, value: p }
}

beforeEach(() => { setActivePinia(createPinia()) })
afterEach(() => { vi.unstubAllGlobals() })

describe('the board\'s list of language models', () => {
  it('drops an answer that arrives after one from a later load', async () => {
    const answers = answering()
    const store = useCanvasStore()
    const older = store.loadLLMModels(true)
    void store.loadLLMModels(true)
    answers[1]!.resolve(answer('after/b'))
    await flushPromises()
    answers[0]!.resolve(answer('before/a'))
    expect(await older).toBe(true)
    await flushPromises()
    expect(ids(store)).toEqual(['after/b'])
  })

  it('a waiter of the older load does not return before the newer answer', async () => {
    const answers = answering()
    const store = useCanvasStore()
    const older = tracked(store.loadLLMModels(true))
    void store.loadLLMModels(true)
    answers[0]!.resolve(answer('before/a'))
    await flushPromises()
    expect(older.done()).toBe(false)
    answers[1]!.resolve(answer('after/b'))
    await older.value
    expect(ids(store)).toEqual(['after/b'])
  })

  it('a waiter follows every later load to the newest', async () => {
    const answers = answering()
    const store = useCanvasStore()
    const first = tracked(store.loadLLMModels(true))
    void store.loadLLMModels(true)
    void store.loadLLMModels(true)
    answers[0]!.resolve(answer('a'))
    answers[1]!.resolve(answer('b'))
    await flushPromises()
    expect(first.done()).toBe(false)
    answers[2]!.resolve(answer('c'))
    expect(await first.value).toBe(true)
    expect(ids(store)).toEqual(['c'])
  })

  it('a load that never answers holds nobody once a later one has', async () => {
    const answers = answering()
    const store = useCanvasStore()
    const entering = tracked(store.loadLLMModels())
    const hanging = tracked(store.loadLLMModels(true))
    answers[0]!.resolve(answer('a'))
    await flushPromises()
    const last = store.loadLLMModels(true)
    answers[2]!.resolve(answer('c'))
    expect(await last).toBe(true)
    await flushPromises()
    expect(entering.done()).toBe(true)
    expect(hanging.done()).toBe(true)
    expect(await entering.value).toBe(true)
    expect(ids(store)).toEqual(['c'])
    expect(store.isLoading).toBe(false)
  })

  it('a waiter whose own load fails after the newest answered is told the list is there', async () => {
    const answers = answering()
    const store = useCanvasStore()
    const older = store.loadLLMModels(true)
    const newer = store.loadLLMModels(true)
    answers[1]!.resolve(answer('new/b'))
    expect(await newer).toBe(true)
    answers[0]!.reject(new Error('502'))
    expect(await older).toBe(true)
    expect(ids(store)).toEqual(['new/b'])
  })

  it('a later load that fails leaves the answer lying there, and its waiter is told', async () => {
    const answers = answering()
    const store = useCanvasStore()
    const older = store.loadLLMModels(true)
    const newer = store.loadLLMModels(true)
    answers[0]!.resolve(answer('before/a'))
    await flushPromises()
    expect(ids(store)).toEqual(['before/a'])
    answers[1]!.reject(new Error('502'))
    expect(await newer).toBe(false)
    expect(await older).toBe(true)
    expect(ids(store)).toEqual(['before/a'])
  })

  it('a load that fails is let go when only an older load is still out', async () => {
    const answers = answering()
    const store = useCanvasStore()
    void store.loadLLMModels(true)
    const newer = tracked(store.loadLLMModels(true))
    answers[1]!.reject(new Error('502'))
    await flushPromises()
    expect(newer.done()).toBe(true)
    expect(await newer.value).toBe(false)
  })

  it('a quiet load never raises the overlay', async () => {
    const answers = answering()
    const store = useCanvasStore()
    const quiet = store.loadLLMModels(true)
    expect(store.isLoading).toBe(false)
    answers[0]!.resolve(answer('x/a'))
    await quiet
    expect(store.isLoading).toBe(false)
  })

  it('a quiet load that fails while the board is entered leaves its overlay and its list alone', async () => {
    const answers = answering()
    const store = useCanvasStore()
    const first = store.loadLLMModels()
    answers[0]!.resolve(answer('a/x'))
    await first
    expect(ids(store)).toEqual(['a/x'])

    const entering = store.loadLLMModels()
    expect(store.isLoading).toBe(true)
    const quiet = store.loadLLMModels(true)
    answers[2]!.reject(new Error('502'))
    await flushPromises()
    expect(store.isLoading).toBe(true)
    expect(ids(store)).toEqual(['a/x'])

    answers[1]!.resolve(answer('b/glm'))
    expect(await entering).toBe(true)
    expect(await quiet).toBe(false)
    expect(ids(store)).toEqual(['b/glm'])
    expect(store.isLoading).toBe(false)
  })

  it('a quiet load that fails leaves the board\'s error as it was', async () => {
    const answers = answering()
    const store = useCanvasStore()
    const entering = store.loadLLMModels()
    answers[0]!.reject(new Error('502'))
    await entering
    expect(store.error).toBe('502')
    const quiet = store.loadLLMModels(true)
    answers[1]!.reject(new Error('503'))
    await quiet
    expect(store.error).toBe('502')
  })

  it('a quiet load that answers while the board is entered keeps the overlay up, and its answer stands', async () => {
    const answers = answering()
    const store = useCanvasStore()
    const entering = store.loadLLMModels()
    const quiet = store.loadLLMModels(true)
    answers[1]!.resolve(answer('after/b'))
    await flushPromises()
    expect(store.isLoading).toBe(true)
    expect(ids(store)).toEqual(['after/b'])

    answers[0]!.resolve(answer('before/a'))
    await Promise.all([entering, quiet])
    await flushPromises()
    expect(ids(store)).toEqual(['after/b'])
    expect(store.isLoading).toBe(false)
  })

  it('a load on entering that fails after a later answer stands says nothing', async () => {
    const answers = answering()
    const store = useCanvasStore()
    const entering = store.loadLLMModels()
    const quiet = store.loadLLMModels(true)
    answers[1]!.resolve(answer('after/b'))
    await quiet
    answers[0]!.reject(new Error('502'))
    expect(await entering).toBe(true)
    expect(store.error).toBeNull()
    expect(ids(store)).toEqual(['after/b'])
  })

  it('a load on entering that fails while a later load is still out says so', async () => {
    const answers = answering()
    const store = useCanvasStore()
    const entering = store.loadLLMModels()
    const quiet = store.loadLLMModels(true)
    answers[0]!.reject(new Error('502'))
    await flushPromises()
    expect(store.error).toBe('502')
    answers[1]!.reject(new Error('503'))
    expect(await quiet).toBe(false)
    expect(await entering).toBe(false)
    expect(store.error).toBe('502')
  })

  it('a load on entering that fails says so', async () => {
    const answers = answering()
    const store = useCanvasStore()
    const entering = store.loadLLMModels()
    answers[0]!.reject(new Error('502'))
    expect(await entering).toBe(false)
    expect(store.error).toBe('502')
    expect(store.isLoading).toBe(false)
  })
})
