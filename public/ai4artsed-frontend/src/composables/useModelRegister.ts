/**
 * What a model IS -- who made it, in what year, how open its weights are, how
 * big it is -- for the card that shows beside a model chip or a model row, and
 * for the one line a native select can carry.
 *
 * ONE register for the whole platform (devserver/config/model_register.json,
 * served at /api/models/register), so the same model says the same thing
 * wherever it is offered. Fetched once per session and kept: it is a file that
 * changes when someone edits it, not while a page is open.
 *
 * A model the register says nothing about gets no card and no placeholder. An
 * unknown fact stays unstated -- it is never filled in from what a model name
 * sounds like.
 */
import { ref } from 'vue'
import type { ChipInfo } from '@/components/ChipSelect.vue'
import { apiBase } from '@/services/labApi'

/** How open a model is, in three steps rather than two. What a step means is
 *  the register's (`_note` of devserver/config/model_register.json): 'open' is
 *  weights AND training data published, 'weights' is weights downloadable under
 *  a licence, 'closed' is no weights. The words for the steps are Open Source,
 *  Open Weights, Closed Weights (`modelInfo.openness`). */
export type Openness = 'open' | 'weights' | 'closed'

export interface ModelFacts {
  maker?: string
  year?: number
  openness?: Openness
  /** Billions. For an image model the image network alone. */
  params_b?: number | null
  /** 'image' marks an image network, which carries no size class (see `sizeClass`). */
  medium?: 'image'
  source?: string
}

/**
 * The four sizes of a model: Mikro below four gigabytes; Klein up to 32b;
 * Gross up to 90 or 100b, gpt-oss-120b included because it is a mixture of
 * experts; Sehr gross from Mistral Medium or Large upward, which would no
 * longer run on a gaming PC. The words stand in `modelInfo.size`; the
 * thresholds are `sizeClass` below.
 */
export type SizeClass = 'micro' | 'small' | 'large' | 'veryLarge'

/** A translation function, as `useI18n().t` is. The register holds no word of
 *  its own; the caller's `t` turns its steps into the reader's language. */
export type Translate = (key: string, values?: Record<string, unknown>) => string

const facts = ref<Record<string, ModelFacts>>({})
const lineups = ref<Record<string, string[]>>({})
let asked: Promise<void> | null = null

const baseUrl = apiBase()

/** Everything after the last slash -- the key the register is written in.
 *  A cloud id carries its provider, a local one carries none, and a config id
 *  is already bare; taking the last segment answers all three without a list of
 *  providers to keep current. */
export function bareName(modelId: string): string {
  return (modelId || '').split('/').pop() || ''
}

async function load(): Promise<void> {
  try {
    const res = await fetch(`${baseUrl}/api/models/register`)
    if (!res.ok) throw new Error(`${res.status}`)
    const data = await res.json()
    facts.value = data.models || {}
    lineups.value = data.lineups || {}
  } catch {
    // Then there are no cards. The chips stand as they did. A failed answer
    // is not kept: the next one to ask asks again, or a ready-made workflow
    // opened after one bad moment would find its lineup empty for the rest of
    // the session.
    asked = null
  }
}

/**
 * The register's answer, for a caller that has to wait for it rather than
 * redraw when it arrives: a ready-made Canvas workflow fills its lineup's
 * places once, when it is opened (lib/canvasPresets.ts).
 */
export function registerLoaded(): Promise<void> {
  if (!asked) asked = load()
  return asked
}

/**
 * The models a lineup reaches on THIS installation, as ids of the list it is
 * given, in the order the register names them — that order is the lineup's
 * argument, so it is kept. A member the list does not hold, or holds as
 * unavailable, is left out rather than replaced.
 *
 * It was `membersOf` in views/latent_lab/interception_models.vue until the
 * Canvas's Language Model Comparison had to fill the same places from the
 * same lineup (docs/ELEMENT_STRUCTURE_REGISTRY.md).
 */
export function lineupMembers(
  id: string,
  models: readonly { id: string; register: string; available: boolean }[],
): string[] {
  return (lineups.value[id] || [])
    .map(bare => models.find(m => m.available && m.register === bare))
    .filter((m): m is { id: string; register: string; available: boolean } => !!m)
    .map(m => m.id)
}

/** The three steps of openness as the card marks them: full, partial, none. */
const MARK_LEVEL: Record<Openness, 'full' | 'partial' | 'none'> = {
  open: 'full',
  weights: 'partial',
  closed: 'none',
}

/**
 * The size class, read off the parameter count at four bits per weight: half
 * a byte each, so gigabytes = billions / 2. The thresholds are set so that
 * the reference examples of each class fall where its name puts them: under
 * 4 GB is micro; up to 16 GB (32 B) is small; up to 64 GB is large, where a
 * 100 B dense model and gpt-oss-120b (120 B, mixture-of-experts) both land;
 * above that is very large (Mistral Large 3 at 675 B). A closed model without
 * a published count is very large by rule, not by a reading of a figure. Any
 * other model without a published count has no class, because a guess would
 * read as a fact.
 *
 * The thresholds are a language-model scale: every reference example is a
 * language model, and small reaches to 32 B. An image network is a
 * different field, where 8 B is the top of it, and read on this scale the
 * platform's largest open image model stood there as „SD 3.5 Large ·
 * small“. So an image network carries its count alone, no class; the rule
 * for a closed model without a published count holds for it as for any
 * other.
 */
export function sizeClass(f: Pick<ModelFacts, 'params_b' | 'openness' | 'medium'> | undefined): SizeClass | undefined {
  if (!f) return undefined
  const paramsB = f.params_b
  if (paramsB === null || paramsB === undefined || !(paramsB >= 0)) {
    return f.openness === 'closed' ? 'veryLarge' : undefined
  }
  if (f.medium === 'image') return undefined
  const gb = paramsB / 2
  if (gb < 4) return 'micro'
  if (gb <= 16) return 'small'
  if (gb <= 64) return 'large'
  return 'veryLarge'
}

export function useModelRegister() {
  if (!asked) asked = load()

  function factsFor(modelId: string): ModelFacts | undefined {
    return facts.value[bareName(modelId)]
  }

  /**
   * How big, for the place beside the name on the chip. Billions up to a
   * thousand, trillions above -- and a dash where the maker publishes no
   * figure, because an empty place reads as a small model.
   */
  function sizeLabel(modelId: string, locale: string): string {
    const f = factsFor(modelId)
    if (!f) return ''
    const n = f.params_b
    if (n === null || n === undefined) return '–'
    const fmt = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 })
    return n >= 1000 ? `${fmt.format(n / 1000)}T` : `${fmt.format(n)}B`
  }

  /**
   * What is known of the size, as one text: the figure and the class
   * ('27B · small'), the class alone for a closed model ('very large'), or
   * nothing. For the line of the card at a row head, which has no `aside`.
   */
  function sizeWords(modelId: string, t: Translate, locale: string): string {
    const f = factsFor(modelId)
    if (!f) return ''
    const size = sizeClass(f)
    return [
      f.params_b === null || f.params_b === undefined ? '' : sizeLabel(modelId, locale),
      size ? t(`modelInfo.size.${size}`) : '',
    ].filter(Boolean).join(' · ')
  }

  /**
   * The same for the `aside` of a model chip, where the registry puts the size
   * (a list is read for which models are big without touching each one) -- so
   * for a model the register holds without a figure or a class, the dash of
   * `sizeLabel` stands: an empty place reads as a small model. A model the
   * register does not hold gets nothing, as before.
   */
  function sizeText(modelId: string, t: Translate, locale: string): string {
    return sizeWords(modelId, t, locale) || sizeLabel(modelId, locale)
  }

  /**
   * The card. `name` is what the model is called here; `t` turns the register's
   * step of openness into the reader's word. The register holds the step,
   * never a word, so the same entry serves every language. The size is not on
   * this card: it stands in the chip's `aside` (`sizeText`), where a list is
   * read for it. Where the model is reached through a service, the caller
   * adds the route (`ChipInfo.route`); the register knows models, not this
   * installation's keys.
   */
  function infoFor(
    modelId: string,
    name: string,
    t: Translate,
  ): ChipInfo | undefined {
    const f = factsFor(modelId)
    if (!f) return undefined
    const parts = [
      f.maker,
      f.year ? String(f.year) : '',
    ].filter(Boolean)
    const info: ChipInfo = { name }
    if (parts.length) info.line = parts.join(' · ')
    if (f.openness) {
      info.mark = { level: MARK_LEVEL[f.openness], text: t(`modelInfo.openness.${f.openness}`) }
    }
    // A card with nothing but the name repeats the chip.
    return info.line || info.mark ? info : undefined
  }

  /**
   * The two words a line of text can carry about a model: how open it is and
   * how big -- 'Open Weights · very large' -- for a place that holds no card,
   * the option text of a native select. Empty where the register says
   * neither.
   */
  function qualification(modelId: string, t: Translate): string {
    const f = factsFor(modelId)
    if (!f) return ''
    const size = sizeClass(f)
    return [
      f.openness ? t(`modelInfo.openness.${f.openness}`) : '',
      size ? t(`modelInfo.size.${size}`) : '',
    ].filter(Boolean).join(' · ')
  }

  /** The models a lineup stands for, as bare names. Empty while the register
   *  has not arrived, and empty for a lineup it does not name. */
  function lineup(id: string): string[] {
    return lineups.value[id] || []
  }

  return { factsFor, sizeLabel, sizeWords, sizeText, infoFor, qualification, lineup, lineups }
}
