import { onActivated, onDeactivated, ref, watch, type Ref } from 'vue'
import { getModelAvailability } from '@/services/api'
import { providerName } from '@/data/providers'

/**
 * Which output configs this installation can run right now, as
 * `/api/models/availability` answers it
 * (devserver/my_app/services/model_availability_service.py).
 *
 * The Flow, Mean Images and the model choice of five instruments (Model
 * Comparison, Language Understanding, Stereotype Analysis, Language Model
 * Comparison, Aesthetic Poles) all ask here (docs/ARCHITECTURE PART 08).
 * Gemini 3 Pro Image and Gemini Nano Banana 2.1 run through Mammouth AI
 * whatever the external LLM provider is set to. They are switched off in the
 * Flow and in those choices where that account holds no key, and where it
 * holds no credit
 * (docs/DEVELOPMENT_DECISIONS.md). A second copy of the asking is the
 * parallel structure docs/ELEMENT_STRUCTURE_REGISTRY.md forbids.
 *
 * The answer is shared between the surfaces. A question asked while another
 * one is out waits for that one's answer, and for twenty seconds after an
 * answer every surface reads that answer.
 */

/** config id -> whether it can run. Empty while nothing has been answered. */
const availability = ref<Record<string, boolean>>({})
/** The unavailable cloud configs whose provider holds no key, refuses it, or
    has no credit left (`account_missing` in the answer). */
const accountMissingIds = ref<string[]>([])
/** config id -> the provider it sends to, for each of those
    (`account_provider` in the answer): the sentence names it. */
const accountProviders = ref<Record<string, string>>({})
/** When the last answer came. −Infinity, not 0: `performance.now()` counts
    from the page load, so a zero here would keep the first twenty seconds of
    every visit from asking. */
let answered = Number.NEGATIVE_INFINITY
/** The question that is out, so that a second one waits for it instead of
    racing it and overwriting a newer answer with an older one. */
let pending: Promise<void> | null = null

/**
 * Asks, unless an answer came within the last twenty seconds: a backend can
 * come up or fall over while a page stands there, so a surface asks when it is
 * shown and, where it has one, at the gesture that offers the models. A failed
 * question keeps the last good answer and does not count as one, so the next
 * surface asks again.
 */
function refresh(): Promise<void> {
  if (pending) return pending
  if (performance.now() - answered < 20_000) return Promise.resolve()
  pending = (async () => {
    try {
      const r = await getModelAvailability()
      // Throwing a good answer away would unmark models that really are down,
      // and one restart of the server would do it.
      if (r.status === 'success' && r.availability) {
        availability.value = r.availability
        // Replaced only when it says something else: the choices below look
        // again when it changes, and the same answer is no change.
        const off = r.account_missing ?? []
        if (off.join('|') !== accountMissingIds.value.join('|')) accountMissingIds.value = off
        accountProviders.value = r.account_provider ?? {}
        answered = performance.now()
      }
    } catch {
      /* keep what we had */
    } finally {
      pending = null
    }
  })()
  return pending
}

/**
 * Asks now, and again each time a surface kept alive in the background is
 * shown (the compare instruments stay mounted while another one is in view).
 * Called in a component's setup.
 */
function askWhenShown(): void {
  void refresh()
  onActivated(() => void refresh())
}

/**
 * Unreachable only when the check ran AND said so. An empty map means the
 * question could not be answered — then nothing is marked, because claiming a
 * model is missing when the check itself failed is worse than saying nothing.
 */
function missing(id: string): boolean {
  return Object.keys(availability.value).length > 0 && availability.value[id] === false
}

/** Off because the provider behind it holds no key, refuses it, or has no credit left. */
function accountMissing(id: string): boolean {
  return accountMissingIds.value.includes(id)
}

/** The values of the sentence a surface shows for a config that is off for
    want of an account (`x2xFlow.accountMissing`): the name of the provider
    its chunk sends to, from the answer and not from the code. */
function accountParams(id: string): { provider: string } {
  return { provider: providerName(accountProviders.value[id] ?? '') }
}

/**
 * Whether the component is in view with an answer asked for when it came into
 * view: within twenty seconds of the last answer, that answer. Where that
 * question fails, the component acts on the last answer there is, if any; a
 * question that does not come back holds it at most as long as the client
 * waits for an answer. One kept alive in the background is not in view, and an
 * answer that comes meanwhile changes its choice only when it is shown again.
 * Called in a component's setup.
 */
function whileShown(): Ref<boolean> {
  const shown = ref(false)
  // Counts the showings, so that an answer asked for at an earlier one does
  // not mark the surface as shown after it was hidden again.
  let visit = 0
  const show = () => {
    const mine = ++visit
    void refresh().then(() => { if (mine === visit) shown.value = true })
  }
  show()
  onActivated(show)
  onDeactivated(() => { visit++; shown.value = false })
  return shown
}

/** What a surface tells the two functions below about itself. */
interface ChoiceSurface {
  /** A run is out. */
  busy: () => boolean
}

/**
 * Keeps a multiple choice free of the configs that are off for want of an
 * account. It looks when the list of them in the answer changes, when the
 * choice changes, when the surface is shown (at once where an answer came
 * within the last twenty seconds, else once the question asked then is
 * answered or has failed, in which case by the last answer there is, if any),
 * and when a run ends, each time after the surface's own watchers have run
 * (flush 'post'); never while another instrument is shown, while the question
 * asked at its showing is out, or while a run is out, and never at a config
 * whose pictures stand on the surface (`showsPictures`).
 * An edit of the prompt or of the languages is none of these moments: a model
 * whose pictures it takes out of view stays chosen until the next of them,
 * and its pictures come back when the edit is undone before then. A choice
 * that would keep fewer than `min` goes back to the one the surface opens
 * with, unless one of its configs shows pictures; the config that is off then
 * stays in the choice until one of these moments finds `min` configs beside
 * it or no pictures on the surface, its field lit while no run is out and
 * carrying the sentence on hover, and a run does not send it. Called in a
 * component's setup, below whatever the surface's functions read.
 */
function leaveOutAccountMissing(
  choice: Ref<string[]>,
  opening: readonly string[],
  surface: ChoiceSurface & { min?: number; showsPictures: (id: string) => boolean },
): void {
  const shown = whileShown()
  const min = surface.min ?? 1
  watch([accountMissingIds, shown, surface.busy, choice], () => {
    if (!shown.value || surface.busy()) return
    const off = choice.value.filter(id => accountMissing(id) && !surface.showsPictures(id))
    if (!off.length) return
    const kept = choice.value.filter(id => !off.includes(id))
    if (kept.length >= min) choice.value = kept
    else if (!choice.value.some(surface.showsPictures)) choice.value = opening.filter(id => !accountMissing(id))
  }, { flush: 'post' })
}

/**
 * The same for a single choice: a config that is off for want of an account
 * gives way to the one the surface opens with, at the same moments, after the
 * surface's own watchers, and under the same conditions, unless its pictures
 * stand on the surface. Called in a component's setup, below whatever the
 * surface's functions read.
 */
function replaceAccountMissing(
  choice: Ref<string>,
  opening: string,
  surface: ChoiceSurface & { showsPictures: () => boolean },
): void {
  const shown = whileShown()
  watch([accountMissingIds, shown, surface.busy, choice], () => {
    if (shown.value && !surface.busy() && accountMissing(choice.value) && !surface.showsPictures()) {
      choice.value = opening
    }
  }, { flush: 'post' })
}

export function useModelAvailability() {
  return {
    availability,
    refresh,
    askWhenShown,
    missing,
    accountMissing,
    accountParams,
    leaveOutAccountMissing,
    replaceAccountMissing,
  }
}
