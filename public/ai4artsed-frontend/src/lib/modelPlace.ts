/**
 * WHICH model ran a step, and WHERE it ran — the platform's one reading of both.
 *
 * The flow drew this first, in three functions private to views/x2x_flow.vue,
 * and the Latent Lab needs the same sentence in its own bar. A second copy is
 * the parallel structure Rule 13 forbids (docs/ELEMENT_STRUCTURE_REGISTRY.md),
 * so the reading moved here and the flow imports it.
 *
 * Two readings, because a model id and a generation's sheet say where they ran
 * in two different ways:
 *
 *  - A LANGUAGE step carries its service in the id itself (`mammouth/glm-5.3`).
 *    The prefix IS the name and is taken verbatim: a prettified spelling would
 *    be one this platform made up, and the name of a service somebody's inputs
 *    are sent to may not be invented here. An id with no prefix keeps the
 *    platform's word for a service it cannot name, because then there is
 *    nothing to name.
 *  - A MODEL THAT RUNS HERE has to be said to run here by whatever hands the
 *    id over, never read out of the id: a repository id
 *    (`stabilityai/stable-diffusion-3.5-medium`) carries its PUBLISHER in
 *    front, which says nothing at all about where the picture was made.
 *
 * `t` is handed in rather than taken from `useI18n()`, the way
 * `generationErrorFor` takes it in useLabRun.ts: these are called from setup
 * and from handlers, and a composable's injection only holds in the first.
 */

export type Translate = (key: string, values?: Record<string, unknown>) => string

/** A model and its place, as two fields: a bar sets them in two tones, a
 *  station band writes them as one line. */
export interface ModelPlace {
  /** What the model is called. */
  name: string
  /** Where it ran. '' where what is known does not say. */
  place: string
  /** The identifier as it arrived, for the hover: unshortened, unprettified. */
  id: string
}

/** The part after the service, which is what the model is called. */
export function modelShort(m: string): string {
  return m.includes('/') ? m.split('/').slice(1).join('/') : m
}

/** WHO is running this step. */
export function providerOf(m: string, t: Translate): string {
  return (m.includes('/') ? m.split('/')[0] : '') || t('x2xFlow.runCloud')
}

/** A language step. Null where no model is named. */
export function llmPlace(m: string, t: Translate): ModelPlace | null {
  if (!m) return null
  return {
    name: modelShort(m),
    place: m.startsWith('local/') ? t('x2xFlow.runLocal') : providerOf(m, t),
    id: m,
  }
}

/** A model that is not running yet, and runs here: the backbone this card
 *  resolves to, before anything has been made with it. */
export function localPlace(m: string, t: Translate): ModelPlace | null {
  if (!m) return null
  return { name: modelShort(m), place: t('x2xFlow.runLocal'), id: m }
}

/** A language step as ONE line — the form the flow's station band writes. */
export function modelLine(m: string, t: Translate): string {
  const p = llmPlace(m, t)
  return p ? `${p.name} · ${p.place}` : ''
}
