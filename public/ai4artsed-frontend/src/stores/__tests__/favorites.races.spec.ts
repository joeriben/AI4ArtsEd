/**
 * The favourites list while adds, removes and loads overlap
 * (stores/favorites.ts, 2026-11-15). A load answered from the store as it was
 * before an add or a remove was stored took a new star off again or put back
 * the one just taken away, and a rollback put an entry back into a list that
 * had been replaced since.
 */
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    isAxiosError: (e: unknown) => !!(e as { isAxiosError?: boolean } | null)?.isAxiosError,
  },
}))

import axios from 'axios'
import { useFavoritesStore, type FavoriteItem } from '../favorites'
import { useLabAuthStore } from '../labAuth'

const get = axios.get as unknown as Mock
const post = axios.post as unknown as Mock
const del = axios.delete as unknown as Mock

const DEVICE = 'browser-1_2026-11-15'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((r, j) => { resolve = r; reject = j })
  return { promise, resolve, reject }
}

const entry = (runId: string, mayChange = true): FavoriteItem => ({
  run_id: runId,
  added_at: '2026-11-15T10:00:00',
  thumbnail_url: `/api/media/audio/${runId}`,
  media_type: 'audio',
  user_id: 'anonymous',
  user_note: '',
  may_change: mayChange,
})
const listing = (...items: FavoriteItem[]) =>
  ({ data: { favorites: items, total: items.length, mode: 'global' } })
const kept = (runId: string) => ({ data: { success: true, favorite: entry(runId), total: 1 } })
const refused = (status: number, error: string) =>
  Object.assign(new Error(error), { isAxiosError: true, response: { status, data: { error } } })

beforeEach(() => {
  setActivePinia(createPinia())
  get.mockReset()
  post.mockReset()
  del.mockReset()
})

describe('a load and an add or a remove at once', () => {
  it('lays an add still out over a load answered before it was stored', async () => {
    const store = useFavoritesStore()
    const answer = deferred<unknown>()
    post.mockReturnValueOnce(answer.promise)
    const adding = store.addFavorite('run_b', 'audio', DEVICE)
    get.mockResolvedValueOnce(listing(entry('run_x')))
    await store.loadFavorites(DEVICE)
    expect(store.favorites.map((f) => f.run_id)).toEqual(['run_b', 'run_x'])
    expect(store.isLoading).toBe(false)

    answer.resolve(kept('run_b'))
    expect(await adding).toBe(true)
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(1)
    expect(store.favorites.map((f) => f.run_id)).toEqual(['run_b', 'run_x'])
    expect(store.isFavorited('run_b')).toBe(true)
  })

  it('leaves out a run whose removal is out from a load answered before it was stored', async () => {
    const store = useFavoritesStore()
    get.mockResolvedValueOnce(listing(entry('run_x'), entry('run_y')))
    await store.loadFavorites(DEVICE)
    const answer = deferred<unknown>()
    del.mockReturnValueOnce(answer.promise)
    const removing = store.removeFavorite('run_x', DEVICE)

    get.mockResolvedValueOnce(listing(entry('run_x'), entry('run_y')))
    await store.loadFavorites(DEVICE)
    expect(store.favorites.map((f) => f.run_id)).toEqual(['run_y'])

    answer.resolve({ data: { success: true, run_id: 'run_x', total: 1 } })
    expect(await removing).toBe(true)
    expect(store.favorites.map((f) => f.run_id)).toEqual(['run_y'])
  })

  it('does not let an add that never answers hold the list', async () => {
    const store = useFavoritesStore()
    post.mockReturnValueOnce(new Promise(() => {}))
    void store.addFavorite('run_b', 'audio', DEVICE)
    get.mockResolvedValueOnce(listing(entry('run_x')))
    await store.loadFavorites(DEVICE)
    expect(store.isLoading).toBe(false)
    expect(store.favorites.map((f) => f.run_id)).toEqual(['run_b', 'run_x'])

    get.mockResolvedValueOnce(listing(entry('run_x'), entry('run_y')))
    await store.loadFavorites(DEVICE)
    expect(store.isLoading).toBe(false)
    expect(store.favorites.map((f) => f.run_id)).toEqual(['run_b', 'run_x', 'run_y'])
  })

  it('lights a star the account keeps already while another add is out', async () => {
    const store = useFavoritesStore()
    post.mockReturnValueOnce(new Promise(() => {}))
    void store.addFavorite('run_b', 'audio', DEVICE)
    // Kept on another machine of the same account, so not yet in this list.
    post.mockRejectedValueOnce(refused(409, 'Favorite already exists'))
    get.mockResolvedValueOnce(listing(entry('run_a')))
    expect(await store.addFavorite('run_a', 'audio', DEVICE)).toBe(true)
    expect(store.isFavorited('run_a')).toBe(true)
    expect(store.error).toBeNull()
  })

  it('keeps a star whose add was out while another add was refused', async () => {
    const store = useFavoritesStore()
    const first = deferred<unknown>()
    post.mockReturnValueOnce(first.promise)
    post.mockRejectedValueOnce(refused(409, 'Run holds no audio to keep'))
    // Read before the add of run_b was stored.
    get.mockResolvedValueOnce(listing())

    const addingB = store.addFavorite('run_b', 'audio', DEVICE)
    expect(await store.addFavorite('run_a', 'audio', DEVICE)).toBe(false)
    expect(store.favorites.map((f) => f.run_id)).toEqual(['run_b'])

    first.resolve(kept('run_b'))
    expect(await addingB).toBe(true)
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(1)
    expect(store.isFavorited('run_b')).toBe(true)
    expect(store.isFavorited('run_a')).toBe(false)
    expect(store.favorites.map((f) => f.run_id)).toEqual(['run_b'])
  })

  it('asks again where an add started while the load was out', async () => {
    const store = useFavoritesStore()
    const stale = deferred<unknown>()
    get.mockReturnValueOnce(stale.promise)
    const loading = store.loadFavorites(DEVICE)
    await flushPromises()

    post.mockResolvedValueOnce(kept('run_b'))
    expect(await store.addFavorite('run_b', 'audio', DEVICE)).toBe(true)

    get.mockResolvedValueOnce(listing(entry('run_b')))
    stale.resolve(listing())
    await loading
    expect(get).toHaveBeenCalledTimes(2)
    expect(store.isFavorited('run_b')).toBe(true)
  })

  it('does not put back a removed entry from a load asked before the removal', async () => {
    const store = useFavoritesStore()
    get.mockResolvedValueOnce(listing(entry('run_x')))
    await store.loadFavorites(DEVICE)

    const stale = deferred<unknown>()
    get.mockReturnValueOnce(stale.promise)
    const loading = store.loadFavorites(DEVICE)
    await flushPromises()
    del.mockResolvedValueOnce({ data: { success: true, run_id: 'run_x', total: 0 } })
    expect(await store.removeFavorite('run_x', DEVICE)).toBe(true)

    get.mockResolvedValueOnce(listing())
    stale.resolve(listing(entry('run_x')))
    await loading
    expect(store.isFavorited('run_x')).toBe(false)
  })
})

describe('a second press, and whose the list is', () => {
  it('does not count a second press as the answer to the first', async () => {
    const store = useFavoritesStore()
    post.mockRejectedValueOnce(refused(409, 'This run is kept by another account or device'))
    const reload = deferred<unknown>()
    get.mockReturnValueOnce(reload.promise)
    const first = store.addFavorite('run_b', 'audio', DEVICE)
    await flushPromises()

    post.mockReturnValueOnce(new Promise(() => {}))
    void store.addFavorite('run_b', 'audio', DEVICE)
    get.mockResolvedValueOnce(listing())
    reload.resolve(listing())
    expect(await first).toBe(false)
  })

  it('keeps the adds still out newest first over a load', async () => {
    const store = useFavoritesStore()
    post.mockReturnValueOnce(new Promise(() => {}))
    post.mockReturnValueOnce(new Promise(() => {}))
    void store.addFavorite('run_1', 'audio', DEVICE)
    void store.addFavorite('run_2', 'audio', DEVICE)
    expect(store.favorites.map((f) => f.run_id)).toEqual(['run_2', 'run_1'])
    get.mockResolvedValueOnce(listing(entry('run_x')))
    await store.loadFavorites(DEVICE)
    expect(store.favorites.map((f) => f.run_id)).toEqual(['run_2', 'run_1', 'run_x'])
  })

  it('refuses a second press on a run whose first is out', async () => {
    const store = useFavoritesStore()
    const answer = deferred<unknown>()
    post.mockReturnValueOnce(answer.promise)
    const adding = store.toggleFavorite('run_b', 'audio', DEVICE)
    expect(await store.toggleFavorite('run_b', 'audio', DEVICE)).toBe(false)
    expect(del).not.toHaveBeenCalled()

    answer.resolve(kept('run_b'))
    expect(await adding).toBe(true)
    expect(store.isFavorited('run_b')).toBe(true)
  })

  it('puts nothing of the one before into the list of the one signed in now', async () => {
    const store = useFavoritesStore()
    const answer = deferred<unknown>()
    post.mockReturnValueOnce(answer.promise)
    const adding = store.addFavorite('run_b', 'audio', DEVICE)

    get.mockResolvedValueOnce(listing())
    const loading = store.loadFavorites(DEVICE, true)
    expect(store.favorites).toEqual([])
    await loading

    get.mockResolvedValueOnce(listing())
    answer.resolve(kept('run_b'))
    expect(await adding).toBe(true)
    await flushPromises()
    expect(store.isFavorited('run_b')).toBe(false)
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('puts back no entry of the one before after a sign-in', async () => {
    const store = useFavoritesStore()
    get.mockResolvedValueOnce(listing(entry('run_x')))
    await store.loadFavorites(DEVICE)
    const answer = deferred<unknown>()
    del.mockReturnValueOnce(answer.promise)
    const removing = store.removeFavorite('run_x', DEVICE)

    get.mockResolvedValueOnce(listing())
    await store.loadFavorites(DEVICE, true)
    // The load the removal asks for once answered stays out, so that what the
    // list holds now is the rollback's doing alone.
    get.mockReturnValueOnce(new Promise(() => {}))
    answer.reject(refused(500, 'Failed to save favorites'))
    expect(await removing).toBe(false)
    expect(store.favorites).toEqual([])
  })

  it('takes a press under the one signed in now on a run whose add hung before', async () => {
    const store = useFavoritesStore()
    post.mockReturnValueOnce(new Promise(() => {}))
    void store.addFavorite('run_b', 'audio', DEVICE)
    get.mockResolvedValueOnce(listing())
    await store.loadFavorites(DEVICE, true)

    post.mockResolvedValueOnce(kept('run_b'))
    expect(await store.addFavorite('run_b', 'audio', DEVICE)).toBe(true)
    expect(post).toHaveBeenCalledTimes(2)
    expect(store.isFavorited('run_b')).toBe(true)
  })
})

describe('a removal the server answers otherwise', () => {
  it('leaves a favourite out that is gone already', async () => {
    const store = useFavoritesStore()
    get.mockResolvedValueOnce(listing(entry('run_x')))
    await store.loadFavorites(DEVICE)
    del.mockRejectedValueOnce(refused(404, 'Favorite not found'))
    expect(await store.removeFavorite('run_x', DEVICE)).toBe(true)
    expect(store.isFavorited('run_x')).toBe(false)
  })

  it('reads whose a favourite is anew where it is not theirs to take back', async () => {
    const store = useFavoritesStore()
    get.mockResolvedValueOnce(listing(entry('run_x')))
    await store.loadFavorites(DEVICE)
    del.mockRejectedValueOnce(refused(403, 'This favorite belongs to another account or device'))
    get.mockResolvedValueOnce(listing(entry('run_x', false)))
    expect(await store.removeFavorite('run_x', DEVICE)).toBe(false)
    expect(store.isFavorited('run_x')).toBe(false)
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(2)
    expect(store.isFavorited('run_x')).toBe(false)
    expect(store.favorites.map((f) => f.run_id)).toEqual(['run_x'])
  })

  it('asks who is signed in where a removal is refused as not theirs', async () => {
    const store = useFavoritesStore()
    const auth = useLabAuthStore()
    const place = vi.spyOn(auth, 'checkPlaceSession').mockResolvedValue()
    const leader = vi.spyOn(auth, 'checkLeaderSession').mockResolvedValue()
    get.mockResolvedValueOnce(listing(entry('run_x')))
    await store.loadFavorites(DEVICE)
    del.mockRejectedValueOnce(refused(403, 'This favorite belongs to another account or device'))
    get.mockResolvedValueOnce(listing())
    expect(await store.removeFavorite('run_x', DEVICE)).toBe(false)
    expect(place).toHaveBeenCalledWith(true)
    expect(leader).toHaveBeenCalledWith(true)
  })

  it('puts a favourite back where the removal failed', async () => {
    const store = useFavoritesStore()
    get.mockResolvedValueOnce(listing(entry('run_w'), entry('run_x'), entry('run_y')))
    await store.loadFavorites(DEVICE)
    del.mockRejectedValueOnce(refused(500, 'Failed to save favorites'))
    expect(await store.removeFavorite('run_x', DEVICE)).toBe(false)
    expect(store.favorites.map((f) => f.run_id)).toEqual(['run_w', 'run_x', 'run_y'])
    expect(store.isFavorited('run_x')).toBe(true)
  })
})
