/**
 * The reading and the wording of an Encoder Fusion record, which the
 * instrument's restore and the favourites panel share (lib/fusionSetting).
 * The records are shaped like the stored ones: a three-factor run of
 * 2026-10-03, a three-factor run from before the pooled vector could be
 * chosen, and records from before the three factors.
 */
import { describe, it, expect } from 'vitest'
import { formatFactor, fusionSettingLabel, recordedFactors } from '../fusionSetting'

describe('recordedFactors', () => {
  it('takes a three-factor record as it is', () => {
    expect(
      recordedFactors({ factor_a: -4, factor_b: 5, factor_c: 1, t5_rows: 'tail', pooled: 'clip', alpha_factor: null }),
    ).toEqual({ a: -4, b: 5, c: 1, rows: 'tail', pooled: 'clip', clip: 'both', exact: true })
  })

  it('takes the CLIP encoders a record names, and reads anything else as both', () => {
    expect(recordedFactors({ factor_a: 1, factor_b: 0, factor_c: 1, clip_encoder: 'clip_g' })?.clip).toBe('clip_g')
    expect(recordedFactors({ factor_a: 1, factor_b: 0, factor_c: 1, clip_encoder: 'clip_l' })?.clip).toBe('clip_l')
    expect(recordedFactors({ factor_a: 1, factor_b: 0, factor_c: 1, clip_encoder: 'clip_x' })?.clip).toBe('both')
  })

  it('reads a missing layout as the full block and a missing pooled key as the vector', () => {
    expect(recordedFactors({ factor_a: 1, factor_b: 0, factor_c: 1 })).toEqual({
      a: 1, b: 0, c: 1, rows: 'full', pooled: 'clip', clip: 'both', exact: true,
    })
  })

  it('reads a legacy alpha onto the line a + b = 1, tail layout, exactly', () => {
    expect(recordedFactors({ alpha_factor: 15, fusion_strategy: 'legacy' })).toEqual({
      a: -14, b: 15, c: 1, rows: 'tail', pooled: 'clip', clip: 'both', exact: true,
    })
  })

  it('reads dual_alpha approximately, and centered_fade with options approximately', () => {
    expect(recordedFactors({ alpha_factor: 0.7, fusion_strategy: 'dual_alpha' })).toEqual({
      a: 0.3, b: 0.7, c: 1, rows: 'tail', pooled: 'clip', clip: 'both', exact: false,
    })
    expect(recordedFactors({ alpha_factor: 2, fusion_strategy: 'centered_fade#tail=x' })?.exact).toBe(false)
  })

  it('names nothing for the sphere, an unknown strategy, or no strategy', () => {
    expect(recordedFactors({ alpha_factor: 5, fusion_strategy: 'centered_fade#path=sphere' })).toBeNull()
    expect(recordedFactors({ alpha_factor: 5, fusion_strategy: 'original#path=sphere' })).toBeNull()
    expect(recordedFactors({ alpha_factor: 24.9 })).toBeNull()
    expect(recordedFactors({ factor_a: null, factor_b: 5, factor_c: 1 })).toBeNull()
  })
})

describe('fusionSettingLabel', () => {
  it('writes two decimals and the minus sign in the reader language', () => {
    expect(formatFactor(-4, 'de')).toBe('−4,00')
    expect(formatFactor(-0, 'en')).toBe('0.00')
    expect(fusionSettingLabel(-4, 5, 1, 'tail', 'clip', 'both', 'de')).toBe('a −4,00 · b 5,00 · c 1,00 · T5 77–511')
    expect(fusionSettingLabel(1, 0, 1, 'full', 'zero', 'both', 'en')).toBe('a 1.00 · b 0.00 · c 1.00 · pool 0')
    expect(fusionSettingLabel(1, 0, 1, 'full', 'zero', 'clip_l', 'en')).toBe('a 1.00 · b 0.00 · c 1.00 · clip-l · pool 0')
    expect(fusionSettingLabel(1, 0, 1, 'tail', 'clip', 'clip_g', 'en')).toBe('a 1.00 · b 0.00 · c 1.00 · T5 77–511 · clip-g')
  })
})
