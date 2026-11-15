/**
 * The lineup a surface opens on (useModelRegister.fillableLineup): the one it
 * names where the provider the settings choose reaches any of it, else the
 * first that it does reach.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'

const LINEUPS = { openWeights: ['glm-5.3', 'kimi-k3'], closedWeights: ['claude-sonnet-5'], family: ['qwen3.5:4b'] }

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
    ok: true, json: async () => ({ models: {}, lineups: LINEUPS }),
  })))
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.resetModules()
})

const reach = (...names: string[]) => names.map(n => ({ id: `p/${n}`, register: n, available: true }))

describe('fillableLineup', () => {
  it('keeps the lineup it names where any of it is reached', async () => {
    const { fillableLineup, registerLoaded } = await import('../useModelRegister')
    await registerLoaded()
    expect(fillableLineup('openWeights', reach('kimi-k3', 'claude-sonnet-5'))).toBe('openWeights')
  })

  it('gives way to the first lineup that is reached, in the register\'s order', async () => {
    const { fillableLineup, registerLoaded } = await import('../useModelRegister')
    await registerLoaded()
    expect(fillableLineup('openWeights', reach('claude-sonnet-5', 'qwen3.5:4b'))).toBe('closedWeights')
    expect(fillableLineup('openWeights', reach('qwen3.5:4b'))).toBe('family')
    expect(fillableLineup('openWeights', reach('qwen3.5:4b'), ['openWeights', 'closedWeights'])).toBe('')
  })

  it('counts no model that is listed and not available, and answers nothing where none is reached', async () => {
    const { fillableLineup, registerLoaded } = await import('../useModelRegister')
    await registerLoaded()
    expect(fillableLineup('openWeights', [{ id: 'local/glm-5.3', register: 'glm-5.3', available: false }])).toBe('')
    expect(fillableLineup('openWeights', [])).toBe('')
  })
})
