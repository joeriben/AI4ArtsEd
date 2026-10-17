/**
 * How a run of the Encoder Fusion names its setting: the three factors, the
 * layout of the T5 block and the pooled vector, in one line, and how a record
 * of such a run is read back into them.
 *
 * The instrument writes that line into the bar of a run's card
 * (views/surrealizer.vue); the favourites strip writes it on the panel beside a
 * kept run (components/FooterGallery.vue). Until 2026-10-03 it stood in the
 * instrument alone. The panel needed the same words for the same record, and a
 * second wording of it is what Rule 13 forbids. The same holds for the reading:
 * the panel shows what the instrument's restore puts back, so both read a
 * record through `recordedFactors`.
 */
import { fusionWeights, isFusionStrategy, parseFusionStrategy } from '@/lib/fusionWeights'

/** Which rows the T5 block holds: all of them, or the tail alone, the head then only inside the CLIP block. */
export type T5Rows = 'full' | 'tail'

/** The pooled vector the model reads beside the table: as CLIP computes it, or zeros in its place. */
export type Pooled = 'clip' | 'zero'

/** A layout as a record or a field names it; anything but the tail is the full block. */
export function recordedRows(v: unknown): T5Rows {
  return v === 'tail' ? 'tail' : 'full'
}

/** The pooled vector as a record or a field names it; anything but zeros is the vector. */
export function recordedPooled(v: unknown): Pooled {
  return v === 'zero' ? 'zero' : 'clip'
}

/** A number as the record wrote it, or nothing: null and a string are not one. */
export function recordedNumber(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

/** Intl writes a hyphen-minus for nearly every language; the minus sign is U+2212. */
export function minus(s: string): string {
  return s.replace('-', '−')
}

/**
 * Two decimals in the reader's language: 1,00 under German, 1.00 under
 * English, and the minus sign (U+2212) before a negative number. `x || 0` folds
 * the negative zero the axis hands out just under 0 into 0, which Intl would
 * print signed.
 */
export function formatFactor(x: number, locale: string): string {
  return minus(new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(x || 0))
}

/** The controls a record of the instrument goes back onto. */
export interface RecordedFactors {
  a: number
  b: number
  c: number
  rows: T5Rows
  pooled: Pooled
  /** Whether these are the run's own numbers, or an older record read back approximately. */
  exact: boolean
}

/**
 * The three factors, layout and pooled vector a record of this instrument
 * (its `current_state`) goes back onto the controls with, or null where it
 * names none the instrument can take.
 *
 * A record made with the three factors carries them, its layout and its
 * pooled vector, and they go back as they are. A record made before them
 * carries an alpha and a strategy, and is read through lib/fusionWeights:
 * what its strategy put on the CLIP block at that alpha becomes a, what it
 * put on T5's rows 0..76 becomes b, c stands at 1, and the layout is the
 * tail, the only one the old node laid, with the pooled vector as that node
 * handed it on. For centered_fade, two_interceptions and legacy that is the
 * run's own arithmetic; dual_alpha scaled the tail by 0.15 · α and normalized
 * rescaled it row by row, which c 1 leaves out (c runs 0..1 here). A record
 * naming a strategy that cannot be read that way (the 2025 `original`, slerp,
 * the sphere) or naming none gives null: taking its number would put a
 * stranger's setting under this instrument's name.
 */
export function recordedFactors(state: Record<string, unknown>): RecordedFactors | null {
  const a = recordedNumber(state.factor_a)
  const b = recordedNumber(state.factor_b)
  const c = recordedNumber(state.factor_c)
  if (a !== null && b !== null && c !== null) {
    // A three-factor record without the key ran before the layout could be
    // chosen, on the full block, which is what the reader returns for it; the
    // same for the pooled vector: a record without the key ran with it.
    return { a, b, c, rows: recordedRows(state.t5_rows), pooled: recordedPooled(state.pooled), exact: true }
  }
  const alpha = recordedNumber(state.alpha_factor)
  const setting = parseFusionStrategy(String(state.fusion_strategy))
  const base = setting.base
  // Every strategy fusionWeights knows: centered_fade and two_interceptions,
  // and legacy, dual_alpha and normalized, for which it returns the concept's
  // identity (1 − α, α). A run on the sphere has no two factors to come back
  // as.
  if (alpha === null || !isFusionStrategy(base) || setting.sphere) return null
  const weights = fusionWeights(alpha, base)
  // Two decimals, as the axis hands them out: 1 − 0.7 is not 0.3 in floating
  // point, and the record would carry the noise.
  const two = (x: number) => Math.round(x * 100) / 100
  // Only legacy and centered_fade are the three factors exactly; the others
  // (model-written encoder prompts, a scaled or rescaled tail, the research
  // options after '#') are read back approximately.
  const exact = (base === 'legacy' || base === 'centered_fade')
    && !String(state.fusion_strategy).includes('#')
  return { a: two(weights.clip), b: two(weights.t5), c: 1, rows: 'tail', pooled: 'clip', exact }
}

/**
 * The three factors of a run, its layout where that is the old one, and its
 * pooled vector where zeros stand in its place; the full block and the vector
 * are the rule and go unsaid.
 */
export function fusionSettingLabel(
  a: number,
  b: number,
  c: number,
  rows: T5Rows,
  pool: Pooled,
  locale: string,
): string {
  const fmt = (x: number) => formatFactor(x, locale)
  const key = [`a ${fmt(a)} · b ${fmt(b)} · c ${fmt(c)}`]
  if (rows === 'tail') key.push('T5 77–511')
  if (pool === 'zero') key.push('pool 0')
  return key.join(' · ')
}
