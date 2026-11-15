/**
 * The line every list of language models in the Latent Lab and on the Canvas
 * offers a model under (useModelRegister.modelLabelOf): name, maker's country
 * and year, size -- 'Qwen 3.8 (China 2026) 27b'.
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { COUNTRY_NAMES, modelLabelOf, useModelRegister } from '../useModelRegister'
import { SUPPORTED_LANGUAGES } from '@/i18n'

const REGISTER = JSON.parse(readFileSync(
  resolve(__dirname, '..', '..', '..', '..', '..', 'devserver', 'config', 'model_register.json'), 'utf-8',
)) as { models: Record<string, { country?: string }>; makers: Record<string, { country?: string }> }

/** The register's answer as the route hands it over (/api/models/register). */
function registerAnswer(models: Record<string, object>) {
  return { ok: true, json: async () => ({ models, lineups: {} }) }
}

describe('modelLabelOf', () => {
  it('writes the name, the country and year in brackets, and the size', () => {
    expect(modelLabelOf(
      { name: 'Qwen 3.8', maker: 'Alibaba', country: 'CN', year: 2026, openness: 'weights', params_b: 27 },
      'Qwen 3.8 27B (FP8) (local)', 'de',
    )).toBe('Qwen 3.8 (China 2026) 27b')
  })

  it('names the country in the reader\'s language, in its short form', () => {
    const f = { name: 'Claude Sonnet 5', country: 'US', year: 2026, openness: 'closed' as const, params_b: null }
    expect(modelLabelOf(f, 'claude-sonnet-5', 'de')).toBe('Claude Sonnet 5 (USA 2026) >1000b')
    expect(modelLabelOf({ ...f, country: 'FR' }, 'x', 'fr')).toBe('Claude Sonnet 5 (France 2026) >1000b')
    expect(modelLabelOf({ ...f, country: '150' }, 'x', 'de')).toBe('Claude Sonnet 5 (Europa 2026) >1000b')
  })

  it('names Europe where the browser hands the code back, as Chrome does for 150', async () => {
    const real = Intl.DisplayNames
    ;(Intl as { DisplayNames: unknown }).DisplayNames = class {
      of(code: string) { return code === 'US' ? 'USA' : code }
    }
    try {
      vi.resetModules()
      const { modelLabelOf: fresh } = await import('../useModelRegister')
      const f = { name: 'EuroLLM', country: '150', year: 2024, openness: 'weights' as const, params_b: 1.7 }
      expect(fresh(f, 'x', 'de')).toBe('EuroLLM (Europa 2024) 1,7b')
      expect(fresh(f, 'x', 'uk')).toBe('EuroLLM (Європа 2024) 1,7b')
      expect(fresh({ ...f, country: 'US' }, 'x', 'de')).toBe('EuroLLM (USA 2024) 1,7b')
      expect(fresh({ ...f, country: 'XK' }, 'x', 'de')).toBe('EuroLLM (XK 2024) 1,7b')
    } finally {
      ;(Intl as { DisplayNames: unknown }).DisplayNames = real
      vi.resetModules()
    }
  })

  it('names a country the same in every browser: Safari\'s "China, Festland" does not reach the line', async () => {
    const real = Intl.DisplayNames
    ;(Intl as { DisplayNames: unknown }).DisplayNames = class {
      of(code: string) { return code === 'CN' ? 'China, Festland' : code === 'XK' ? 'Kosovo' : code }
    }
    try {
      vi.resetModules()
      const { modelLabelOf: fresh } = await import('../useModelRegister')
      const f = { name: 'Qwen 3.8', country: 'CN', year: 2026, openness: 'weights' as const, params_b: 27 }
      expect(fresh(f, 'x', 'de')).toBe('Qwen 3.8 (China 2026) 27b')
      expect(fresh(f, 'x', 'fr')).toBe('Qwen 3.8 (Chine 2026) 27b')
      // A country the table does not hold is still asked of the browser.
      expect(fresh({ ...f, country: 'XK' }, 'x', 'de')).toBe('Qwen 3.8 (Kosovo 2026) 27b')
    } finally {
      ;(Intl as { DisplayNames: unknown }).DisplayNames = real
      vi.resetModules()
    }
  })

  it('holds every country the register names, in every language of the platform', () => {
    const codes = new Set(
      [...Object.values(REGISTER.models), ...Object.values(REGISTER.makers)]
        .map(e => e.country).filter((c): c is string => !!c),
    )
    expect(codes.size).toBeGreaterThan(0)
    for (const code of codes) {
      for (const { code: lang } of SUPPORTED_LANGUAGES) {
        expect(COUNTRY_NAMES[code]?.[lang], `${code} in ${lang}`).toBeTruthy()
      }
    }
  })

  it('an estimate stands with ~, at every size', () => {
    const f = { name: 'GPT-4o', country: 'US', year: 2024, openness: 'closed' as const, params_b: null }
    expect(modelLabelOf({ ...f, params_b_estimate: 200 }, 'x', 'de')).toBe('GPT-4o (USA 2024) ~200b')
    expect(modelLabelOf({ ...f, params_b_estimate: 1000 }, 'x', 'de')).toBe('GPT-4o (USA 2024) ~1000b')
    expect(modelLabelOf({ ...f, params_b_estimate: 1800 }, 'x', 'de')).toBe('GPT-4o (USA 2024) ~1800b')
    expect(modelLabelOf({ ...f, params_b_estimate: 3000 }, 'x', 'en')).toBe('GPT-4o (US 2024) ~3000b')
    // A published count wins over an estimate.
    expect(modelLabelOf({ ...f, params_b: 120, params_b_estimate: 200 }, 'x', 'de')).toBe('GPT-4o (USA 2024) 120b')
  })

  it('a closed model with neither a published count nor an estimate stands as >1000b, any other without a count shows no size', () => {
    expect(modelLabelOf({ name: 'GPT-5', country: 'US', year: 2025, openness: 'closed', params_b: null }, 'x', 'en'))
      .toBe('GPT-5 (US 2025) >1000b')
    expect(modelLabelOf({ name: 'Some Open', country: 'US', year: 2025, openness: 'weights', params_b: null }, 'x', 'en'))
      .toBe('Some Open (US 2025)')
  })

  it('writes the count in the reader\'s digits, without grouping', () => {
    const f = { name: 'Gemma 4', country: 'US', year: 2026, openness: 'weights' as const, params_b: 30.7 }
    expect(modelLabelOf(f, 'x', 'de')).toBe('Gemma 4 (USA 2026) 30,7b')
    expect(modelLabelOf({ ...f, params_b: 2400, openness: 'closed' }, 'x', 'en')).toBe('Gemma 4 (US 2026) 2400b')
  })

  it('leaves out what the register does not say', () => {
    expect(modelLabelOf({ name: 'Kimi K3', year: 2026, params_b: 2800 }, 'x', 'en')).toBe('Kimi K3 (2026) 2800b')
    expect(modelLabelOf({ maker: 'Someone', params_b: 3 }, 'listed-name', 'en')).toBe('listed-name 3b')
  })

  it('without an entry, the list\'s own label', () => {
    expect(modelLabelOf(undefined, 'qwen3:4b', 'en')).toBe('qwen3:4b')
  })
})

describe('useModelRegister().modelLabel', () => {
  afterEach(() => { vi.unstubAllGlobals() })

  it('takes the service off a listed name the register does not know, and only the last brackets', () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))))
    const { modelLabel } = useModelRegister()
    expect(modelLabel('local/unknown:1b', 'Unknown 1B (FP8) (local)', 'en')).toBe('Unknown 1B (FP8)')
    expect(modelLabel('openrouter/x/y-1', 'y-1 (OpenRouter)', 'en')).toBe('y-1')
    expect(modelLabel('local/qwen9:1b', 'qwen9:1b (Lokal)', 'de')).toBe('qwen9:1b')
  })

  it('puts the word for this machine at the end of a local model', () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))))
    const { modelLabel } = useModelRegister()
    expect(modelLabel('local/unknown:1b', 'Unknown 1B (FP8) (local)', 'de', 'lokal')).toBe('Unknown 1B (FP8) lokal')
    expect(modelLabel('openrouter/x/y-1', 'y-1 (OpenRouter)', 'de')).toBe('y-1')
  })

  it('leaves the row that is no model as it is', () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))))
    const { modelLabel } = useModelRegister()
    expect(modelLabel('', 'Default (Settings)', 'en')).toBe('Default (Settings)')
    expect(modelLabel('', 'Standard (Einstellungen)', 'de')).toBe('Standard (Einstellungen)')
  })
})

describe('useModelRegister().ordered', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('this machine first, then from the smallest to the largest, the estimate where no count is published, then A-Z', async () => {
    vi.resetModules()
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(registerAnswer({
      'qwen3.5:9b': { name: 'Qwen 3.5', params_b: 9 },
      'qwen3.5:4b': { name: 'Qwen 3.5', params_b: 4 },
      'qwen3.8:27b': { name: 'Qwen 3.8', params_b: 27 },
      'mistral-nemo': { name: 'Mistral NeMo', params_b: 12 },
      'ministral3:3b': { name: 'Ministral 3', params_b: 3.8 },
      'gemma3:4b': { name: 'Gemma 3', params_b: 4 },
      'kimi-k3': { name: 'Kimi K3', params_b: 2800 },
      'gpt-4o': { name: 'GPT-4o', openness: 'closed', params_b: null, params_b_estimate: 200 },
      'glm-5.3': { name: 'GLM-5.3', params_b: 753 },
      'mystery': { name: 'Mystery', params_b: null },
    }))))
    const mod = await import('../useModelRegister')
    await mod.registerLoaded()
    const { ordered, modelLabel } = mod.useModelRegister()
    const ids = [
      'openrouter/moonshot/kimi-k3', 'openrouter/x/mystery', 'local/qwen3.5:9b', 'openrouter/z/glm-5.3',
      'openrouter/openai/gpt-4o', 'local/qwen3.5:4b', 'local/gemma3:4b', 'local/ministral3:3b',
      'local/oddity:1b', 'openrouter/mistralai/mistral-nemo', 'local/qwen3.8:27b',
    ]
    const read = (id: string) => ({ local: mod.isLocalModel(id), key: id, label: modelLabel(id, id, 'de') })
    expect(ordered(ids, read, 'de')).toEqual([
      'local/ministral3:3b', 'local/gemma3:4b', 'local/qwen3.5:4b', 'local/qwen3.5:9b', 'local/qwen3.8:27b',
      'local/oddity:1b',
      'openrouter/mistralai/mistral-nemo', 'openrouter/openai/gpt-4o', 'openrouter/z/glm-5.3',
      'openrouter/moonshot/kimi-k3', 'openrouter/x/mystery',
    ])
  })
})
