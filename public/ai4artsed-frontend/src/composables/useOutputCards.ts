import { ref } from 'vue'
import { getOutputCards, type OutputCard } from '@/services/api'
import { localized } from '@/i18n'
import type { ChipInfo } from '@/components/ChipSelect.vue'

/**
 * What the card beside an output config says: the model's full name, its
 * quality and its speed in five stars each, and the estimated time of the
 * generation (the output chunk's own step, without the steps before it). The t2x
 * page showed exactly these four on its model bubbles until it was removed;
 * the Flow's model choice shows them again.
 *
 * The values are the output chunk's (`GET /api/schema/output-cards`). The
 * scale of the quality rating, and who set which value, stand in
 * docs/QUALITAETSSTUFEN_MODELLE.md. Speed and time are not ratings: both
 * follow from the chunk's estimated duration, reckoned as the t2x page did.
 * Where the chunk gives no duration, 0, or one that does not read as a number,
 * the card shows neither; t2x showed three stars or five and "~1 sec" there.
 *
 * Each config is asked for once and kept for the life of the browser tab: the
 * values stand in files that change with a commit, not while a tab is open. A
 * question that fails is forgotten, so the next one asks again; a config the
 * server leaves out is not asked for again before a reload.
 */

const cards = ref<Record<string, OutputCard>>({})
const asked = new Set<string>()

/** Asks for the cards of those configs that have not been asked for yet. */
function ensure(ids: string[]): void {
  const open = [...new Set(ids.filter((id) => id && !asked.has(id)))]
  if (!open.length) return
  open.forEach((id) => asked.add(id))
  getOutputCards(open)
    .then((got) => {
      cards.value = { ...cards.value, ...got }
    })
    .catch(() => open.forEach((id) => asked.delete(id)))
}

/** The figures of '10-30', '10–30' or '12': the first two numbers in it. */
function figures(d: OutputCard['estimated_duration_seconds']): number[] {
  if (d === null || d === undefined) return []
  return (String(d).match(/\d+(?:\.\d+)?/g) ?? []).slice(0, 2).map(Number)
}

/** The lower bound of a range, or the single figure. None for a lone 0: a
    chunk that runs no model of its own (the two code configs) says 0, and the
    language model that writes the code takes far longer than that. */
function lowerSeconds(d: OutputCard['estimated_duration_seconds']): number | null {
  const f = figures(d)
  const last = f[f.length - 1]
  return last !== undefined && last > 0 ? (f[0] ?? null) : null
}

/** floor((90 - s) / 18) + 1, held to 1..5: five stars up to 18 s, one from
    73 s. The t2x page's line. */
function speedFrom(seconds: number): number {
  return Math.max(1, Math.min(5, Math.floor((90 - seconds) / 18) + 1))
}

/**
 * The estimated time of the generation. A range stands with its two figures
 * as the chunk gives them; a single figure gets the time the weights take to
 * load on top, about a second per GB of the
 * VRAM the chunk names, and shown as a range once that is more than two
 * seconds: the t2x page's reckoning, except that a figure without a VRAM value
 * stands as it is, where t2x showed "~1".
 */
function secondsText(c: OutputCard): string | undefined {
  const d = c.estimated_duration_seconds
  if (lowerSeconds(d) === null) return undefined
  const [first, second] = figures(d)
  if (second !== undefined) return `${first}-${second}`
  const base = Math.round(first ?? 0)
  const load = Math.max(2, Math.round((c.gpu_vram_mb ?? 0) / 1000))
  return load > 2 ? `${base}-${base + load}` : String(base)
}

/** The card of a config, or nothing while it has not come or where there is
    none (a reading frame is no output config). */
function infoFor(id: string, locale: string): ChipInfo | undefined {
  const c = cards.value[id]
  if (!c) return undefined
  const s = lowerSeconds(c.estimated_duration_seconds)
  return {
    name: localized(c.name, locale),
    stars: {
      quality: c.quality_rating ?? undefined,
      speed: s === null ? undefined : speedFrom(s),
    },
    seconds: secondsText(c),
  }
}

export function useOutputCards() {
  return { ensure, infoFor }
}
