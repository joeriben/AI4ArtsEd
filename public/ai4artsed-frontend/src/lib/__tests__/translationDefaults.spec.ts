/**
 * The defaults a Canvas translation node shows (lib/translationDefaults): a
 * failed request names its cause and is asked again; an answer clears it.
 */
import { describe, it, expect, vi, afterEach } from 'vitest'

async function freshModule() {
  vi.resetModules()
  return await import('../translationDefaults')
}

const settle = () => new Promise(resolve => setTimeout(resolve, 0))

const answer = { ok: true, json: async () => ({ instruction: 'Translate.', language: 'en' }) }

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('loadTranslationDefaults', () => {
  it('names the cause of a failed request and asks again on the next call', async () => {
    const m = await freshModule()
    const fetchMock = vi.fn().mockResolvedValueOnce({ ok: false, status: 502 }).mockResolvedValueOnce(answer)
    vi.stubGlobal('fetch', fetchMock)

    m.loadTranslationDefaults()
    await settle()
    expect(m.translationDefaultsError.value).toBe('HTTP 502')
    expect(m.translationDefaults.value.instruction).toBe('')

    m.loadTranslationDefaults()
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(m.translationDefaultsError.value).toBe('')
    expect(m.translationDefaults.value).toEqual({ instruction: 'Translate.', language: 'en' })
  })

  it('names a network error by its message', async () => {
    const m = await freshModule()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    m.loadTranslationDefaults()
    await settle()
    expect(m.translationDefaultsError.value).toBe('Failed to fetch')
  })

  it('asks once while an answer stands', async () => {
    const m = await freshModule()
    const fetchMock = vi.fn().mockResolvedValue(answer)
    vi.stubGlobal('fetch', fetchMock)
    m.loadTranslationDefaults()
    await settle()
    m.loadTranslationDefaults()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
