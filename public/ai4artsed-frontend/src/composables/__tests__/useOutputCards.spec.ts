import { describe, it, expect, vi, beforeEach } from 'vitest'

/**
 * What the card beside a model says, reckoned from the output chunk's values
 * as the t2x page reckoned them (see composables/useOutputCards.ts and
 * docs/QUALITAETSSTUFEN_MODELLE.md).
 *
 * The module keeps its cache at module level, so each test takes a fresh copy
 * of it and of the mocked question.
 */
const getOutputCards = vi.fn()
vi.mock('@/services/api', () => ({ getOutputCards: (ids: string[]) => getOutputCards(ids) }))

async function fresh() {
  vi.resetModules()
  return (await import('../useOutputCards')).useOutputCards()
}

function card(d: string | number | null, vram: number | null = null, q: number | null = null) {
  return { name: { en: 'Name', de: 'Name' }, quality_rating: q, estimated_duration_seconds: d, gpu_vram_mb: vram }
}

async function infoOf(d: string | number | null, vram: number | null = null, q: number | null = null) {
  getOutputCards.mockResolvedValueOnce({ x: card(d, vram, q) })
  const m = await fresh()
  m.ensure(['x'])
  await vi.waitFor(() => expect(m.infoFor('x', 'en')).toBeDefined())
  return m.infoFor('x', 'en')!
}

describe('useOutputCards — the card beside a model', () => {
  beforeEach(() => getOutputCards.mockReset())

  it('keeps a range as it stands and takes the speed from its lower bound', async () => {
    const i = await infoOf('12-40', 28000, 3)
    expect(i).toEqual({ name: 'Name', stars: { quality: 3, speed: 5 }, seconds: '12-40' })
  })

  it('reads a range written with an en dash', async () => {
    expect((await infoOf('10–30')).seconds).toBe('10-30')
  })

  it('adds the load time to a single figure once it is three seconds or more', async () => {
    expect((await infoOf('12', 28000)).seconds).toBe('12-40')
    expect((await infoOf('12', 2000)).seconds).toBe('12')
    expect((await infoOf('12', null)).seconds).toBe('12')
  })

  it('draws the t2x line: five stars up to 18 s, one from 73 s', async () => {
    expect((await infoOf('18')).stars?.speed).toBe(5)
    expect((await infoOf('19')).stars?.speed).toBe(4)
    expect((await infoOf('30-240')).stars?.speed).toBe(4)
    expect((await infoOf('72')).stars?.speed).toBe(2)
    expect((await infoOf('73')).stars?.speed).toBe(1)
    expect((await infoOf('180-240')).stars?.speed).toBe(1)
  })

  it('shows neither speed nor time for 0, nothing, or no number', async () => {
    for (const d of ['0', 0, null, 'n/a']) {
      const i = await infoOf(d)
      expect(i.stars?.speed).toBeUndefined()
      expect(i.seconds).toBeUndefined()
    }
  })

  it('leaves the quality out where the chunk sets none', async () => {
    expect((await infoOf('12')).stars?.quality).toBeUndefined()
  })

  it('asks for a config once, and again after a failed question', async () => {
    const m = await fresh()
    getOutputCards.mockRejectedValueOnce(new Error('down'))
    m.ensure(['x'])
    await vi.waitFor(() => expect(getOutputCards).toHaveBeenCalledTimes(1))
    await new Promise((r) => setTimeout(r, 0))
    getOutputCards.mockResolvedValueOnce({ x: card('12') })
    m.ensure(['x'])
    await vi.waitFor(() => expect(m.infoFor('x', 'en')).toBeDefined())
    m.ensure(['x'])
    expect(getOutputCards).toHaveBeenCalledTimes(2)
  })
})
