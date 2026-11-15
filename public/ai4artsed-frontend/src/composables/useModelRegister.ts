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
  /** The model's own name, without its size (see `modelLabelOf`). */
  name?: string
  maker?: string
  /** The maker's seat: an ISO 3166 code, or '150' (Europe) for a consortium
   *  across European countries. Never a word -- `modelLabelOf` names it. */
  country?: string
  year?: number
  openness?: Openness
  /** Billions. For an image model the image network alone. */
  params_b?: number | null
  /** Where the maker publishes no count: an estimate in billions that others
   *  published, where independent ones agree, its grounds under
   *  `size_estimates` in the register file. It orders the
   *  lists, stands in the line with '~' (`modelLabelOf`) and gives the size
   *  class; it is never a published figure. */
  params_b_estimate?: number | null
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

/**
 * The lineup a surface opens on: the one it names where this installation
 * reaches any of it, else the first of `among` that it does reach, '' where
 * none. Which models a lineup reaches follows the provider the settings
 * choose (useChatModels.chosenModels), and one that reaches nothing of the
 * named lineup would open the surface on no model at all. Interception across
 * Models opens on it, and so does its ready-made workflow on the Canvas.
 */
export function fillableLineup(
  preferred: string,
  models: readonly { id: string; register: string; available: boolean }[],
  among: readonly string[] = Object.keys(lineups.value),
): string {
  return [preferred, ...among.filter(id => id !== preferred)]
    .find(id => lineupMembers(id, models).length) || ''
}

/** The three steps of openness as the card marks them: full, partial, none. */
const MARK_LEVEL: Record<Openness, 'full' | 'partial' | 'none'> = {
  open: 'full',
  weights: 'partial',
  closed: 'none',
}

/**
 * The trailing brackets a list puts after a model's name to say which service
 * it reaches -- '(local)', '(OpenRouter)', '(Lokal)'. That is not a fact about
 * the model, and the lists no longer show it (`modelLabelOf`).
 */
const SERVICE_SUFFIX = / \([^()]*\)$/

const regionNames = new Map<string, Intl.DisplayNames | null>()

/**
 * The countries the register names, in the platform's ten languages
 * (i18n/index.ts): CLDR's short form, read off Node's full ICU (CLDR 47 and 48
 * agree). Fixed here rather than asked of the browser, because each browser
 * ships its own copy of that data and changes it: Safari names China
 * 'China, Festland', and Chrome has no name for Europe -- the UN region code
 * 150, for a maker that is a consortium across countries -- and hands the code
 * back. A country the register gains is asked of the browser until it stands
 * here (modelLabel.spec.ts checks the register against this table).
 */
export const COUNTRY_NAMES: Record<string, Record<string, string>> = {
  CH: { ar: 'سويسرا', bg: 'Швейцария', de: 'Schweiz', en: 'Switzerland', es: 'Suiza', fr: 'Suisse', he: 'שווייץ', ko: '스위스', tr: 'İsviçre', uk: 'Швейцарія', 'zh-hant': '瑞士' },
  CN: { ar: 'الصين', bg: 'Китай', de: 'China', en: 'China', es: 'China', fr: 'Chine', he: 'סין', ko: '중국', tr: 'Çin', uk: 'Китай', 'zh-hant': '中國' },
  FR: { ar: 'فرنسا', bg: 'Франция', de: 'Frankreich', en: 'France', es: 'Francia', fr: 'France', he: 'צרפת', ko: '프랑스', tr: 'Fransa', uk: 'Франція', 'zh-hant': '法國' },
  US: { ar: 'الولايات المتحدة', bg: 'САЩ', de: 'USA', en: 'US', es: 'EE. UU.', fr: 'É.-U.', he: 'ארה״ב', ko: '미국', tr: 'ABD', uk: 'США', 'zh-hant': '美國' },
  '150': { ar: 'أوروبا', bg: 'Европа', de: 'Europa', en: 'Europe', es: 'Europa', fr: 'Europe', he: 'אירופה', ko: '유럽', tr: 'Avrupa', uk: 'Європа', 'zh-hant': '歐洲' },
}

/** The country in the reader's language, in its short form ('USA', 'China'). */
function countryName(code: string, locale: string): string {
  const fixed = COUNTRY_NAMES[code]?.[locale] ?? COUNTRY_NAMES[code]?.[locale.split('-')[0]!]
  if (fixed) return fixed
  let names = regionNames.get(locale)
  if (names === undefined) {
    try {
      names = new Intl.DisplayNames([locale], { type: 'region', style: 'short' })
    } catch {
      names = null
    }
    regionNames.set(locale, names)
  }
  let named = ''
  try {
    named = names?.of(code) || ''
  } catch {
    named = ''
  }
  return named || code
}

/**
 * Whether a model runs on this platform's own machines: the platform routes an
 * id that begins 'local/' there and every other to a provider
 * (devserver chat_routes).
 */
export function isLocalModel(id: string): boolean {
  return id.startsWith('local/')
}

/** The size a list orders by: the published count, else the estimate. */
function orderSize(f: ModelFacts | undefined): number | null {
  if (f?.params_b && f.params_b > 0) return f.params_b
  if (f?.params_b_estimate && f.params_b_estimate > 0) return f.params_b_estimate
  return null
}

/**
 * The line a list of language models offers a model under, the same in every
 * instrument of the Latent Lab and every Canvas module (2026-10-27): its name,
 * its maker's country and its year, its size -- 'Qwen 3.8 (China 2026) 27b',
 * 'GPT-4o (USA 2024) ~200b', 'Claude Sonnet 5.5 (USA 2026) >1000b'. Where the
 * maker publishes no count, an estimate the register records stands, marked
 * with a '~' (2026-10-29); a closed model with neither stands as '>1000b', as the
 * scheme was given; any other model without a count shows no size. The provider is not in it, and neither is what is
 * recorded about its data path: the lists offer the models of the one provider
 * the settings choose, and the settings show that provider and its record.
 *
 * `label` stands where the register holds no entry or no name.
 */
export function modelLabelOf(f: ModelFacts | undefined, label: string, locale: string): string {
  if (!f) return label
  const origin = [f.country ? countryName(f.country, locale) : '', f.year ? String(f.year) : '']
    .filter(Boolean).join(' ')
  const n = f.params_b
  const guess = f.params_b_estimate
  const digits = (x: number) =>
    new Intl.NumberFormat(locale, { maximumFractionDigits: 1, useGrouping: false }).format(x)
  let size = ''
  if (n !== null && n !== undefined && n > 0) {
    size = `${digits(n)}b`
  } else if (guess !== null && guess !== undefined && guess > 0) {
    // An estimate is marked as one.
    size = `~${digits(guess)}b`
  } else if (f.openness === 'closed') {
    size = '>1000b'
  }
  return [f.name || label, origin ? `(${origin})` : '', size].filter(Boolean).join(' ')
}

/**
 * The size class, read off the parameter count at four bits per weight: half
 * a byte each, so gigabytes = billions / 2. The thresholds are set so that
 * the reference examples of each class fall where its name puts them: under
 * 4 GB is micro; up to 16 GB (32 B) is small; up to 64 GB is large, where a
 * 100 B dense model and gpt-oss-120b (120 B, mixture-of-experts) both land;
 * above that is very large (Mistral Large 3 at 675 B). Where no count is
 * published, the register's estimate is read (`params_b_estimate`), as the
 * line and the order of a list read it. A closed model with neither is very
 * large by rule, not by a reading of a figure. Any other model with neither
 * has no class, because a guess would read as a fact.
 *
 * The thresholds are a language-model scale: every reference example is a
 * language model, and small reaches to 32 B. An image network is a
 * different field, where 8 B is the top of it, and read on this scale the
 * platform's largest open image model stood there as „SD 3.5 Large ·
 * small“. So an image network carries its count alone, no class; the rule
 * for a closed model without a published count holds for it as for any
 * other.
 */
export function sizeClass(
  f: Pick<ModelFacts, 'params_b' | 'params_b_estimate' | 'openness' | 'medium'> | undefined,
): SizeClass | undefined {
  if (!f) return undefined
  const paramsB = f.params_b ?? f.params_b_estimate
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
   * The line a list of language models offers this model under
   * (`modelLabelOf`). `label` is the name the list itself gives; it stands
   * where the register holds no entry, without the service the list names in
   * brackets at its end. `local` is the word a model of this platform's own
   * machines (`isLocalModel`) carries at the end ('lokal'), '' for any other.
   */
  function modelLabel(modelId: string, label: string, locale: string, local = ''): string {
    // No id is no model: the row „Default (Settings)" keeps its brackets.
    if (!modelId) return label
    return [modelLabelOf(factsFor(modelId), label.replace(SERVICE_SUFFIX, ''), locale), local]
      .filter(Boolean).join(' ')
  }

  /**
   * The order every list of language models offers its models in
   * (2026-10-27): the models of this platform's own machines first, then the
   * provider's; within each from the smallest to the largest -- the published
   * count, else the register's estimate -- and where two are the same size,
   * alphabetically by the line the list shows. A model of no known size stands
   * at the end of its half.
   */
  function ordered<T>(
    models: readonly T[],
    read: (m: T) => { local: boolean; key: string; label: string },
    locale: string,
  ): T[] {
    const collator = new Intl.Collator(locale, { numeric: true, sensitivity: 'base' })
    const bySize = (a: number | null, b: number | null) =>
      a === b ? 0 : a === null ? 1 : b === null ? -1 : a - b
    return models
      .map(m => {
        const r = read(m)
        return { m, local: r.local, size: orderSize(factsFor(r.key)), label: r.label }
      })
      .sort((a, b) =>
        Number(b.local) - Number(a.local)
        || bySize(a.size, b.size)
        || collator.compare(a.label, b.label))
      .map(e => e.m)
  }

  /** The models a lineup stands for, as bare names. Empty while the register
   *  has not arrived, and empty for a lineup it does not name. */
  function lineup(id: string): string[] {
    return lineups.value[id] || []
  }

  return { factsFor, sizeLabel, sizeWords, sizeText, infoFor, modelLabel, ordered, lineup, lineups }
}
