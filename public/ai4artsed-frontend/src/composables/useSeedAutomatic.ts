import { getCurrentScope, onScopeDispose, type Ref } from 'vue'

/**
 * The seed automatic of an instrument that has a seed field of its own
 * (`components/SeedControl.vue`, or a plain number field where the surface has
 * no tick; such a surface passes a constant false as `random`).
 *
 * The platform's rule for the seed (ARCHITECTURE PART 01, section 3), for the
 * instruments of the Latent Lab, which go the direct way and so meet no seed
 * logic on the server:
 *
 *   - something changed since the picture on the surface was made: the SAME
 *     seed, so that the new picture shows the change and not another noise;
 *   - nothing changed: a NEW seed, because pressing again unchanged asks for a
 *     variation;
 *   - a seed typed into the field: THAT seed, and the automatic goes on from it;
 *   - the tick „Random variation“: a new seed on EVERY run.
 *
 * A first run takes the number in the field (STANDARD_SEED, 123456789, unless
 * typed; Mean Images opens on a number of its own, 424242). The seed
 * that goes out is written into the field, so the field names the seed of the
 * picture on the surface and a seed worth coming back to can be read off it. A
 * number counts as typed when it is not the one the automatic last put there.
 *
 * Compared is the run whose picture stands on the surface: one that arrived, or
 * one laid back from the run strip or the favourites. A run that failed or was
 * blocked made no picture and is not the yardstick: pressing again with nothing
 * changed sends its seed again, and a change takes the picture's seed. An
 * instrument that keeps its fields in sessionStorage names a key, and the
 * yardstick is kept under it, because the instrument is mounted afresh on every
 * change of tab and on a reload and its fields come back from there. An
 * instrument whose fields open at their defaults again passes null and starts
 * afresh with them: a yardstick kept without its field would take a number
 * typed back into the field for the one the automatic wrote. An instance that
 * has been taken down writes nothing more: a run still going when the tab
 * changed lands in the old instance and must not overwrite what the new one
 * stands on.
 *
 * Until 2026-10-03 Encoder Fusion sent the field's number unless the tick was
 * set, and under the tick it kept the seed whenever an input changed. The other
 * instruments with a seed field sent the field's number, or -1 under the tick
 * for the server to draw, and Mean Images drew under its tick; the three sound
 * instruments of the Crossmodal Lab sent the field, which opened at -1 in two of
 * them. Instruments whose seeds are set by design keep them: a comparison held
 * on the platform's number, a seed drawn per row, a seed swept as a parameter,
 * the frames of the synth's wavetable. The Flow keeps its own automatic in
 * `views/x2x_flow.vue`, with no seed field.
 *
 * What counts as a change is the instrument's to say: it hands everything the
 * run goes out with except the seed over as one key.
 */

/** The seed of a first run whose field holds no number (PART 01, 3.2). */
export const STANDARD_SEED = 123456789

/** A drawn seed, below 2^31. */
export function drawSeed(): number {
  return Math.floor(Math.random() * 2147483647)
}

/**
 * A seed is a whole number from 0 up; anything else names none. Exported for
 * the favourites panel, which shows the seed a restore lays back
 * (components/FooterGallery.vue) and reads it by the same rule.
 */
export function asSeed(n: unknown): number | null {
  return typeof n === 'number' && Number.isInteger(n) && n >= 0 ? n : null
}

export function useSeedAutomatic(seed: Ref<number>, random: Ref<boolean>, storageKey: string | null) {
  // The run whose picture stands on the surface: what it went out with (null
  // when that is not known) and its seed (null when the record names none).
  let lastInputs: string | null = null
  let lastSeed: number | null = null
  // The number the automatic last put into the field.
  let shown: number | null = null
  // The run that went out and has not arrived: what it went out with, its seed.
  let pendingInputs: string | null = null
  let pendingSeed: number | null = null
  let disposed = false

  try {
    const kept = storageKey ? JSON.parse(sessionStorage.getItem(storageKey) || 'null') : null
    if (kept && typeof kept === 'object') {
      lastInputs = typeof kept.inputs === 'string' ? kept.inputs : null
      lastSeed = asSeed(kept.seed)
      shown = asSeed(kept.shown)
    }
  } catch {
    /* nothing kept */
  }
  if (getCurrentScope()) onScopeDispose(() => { disposed = true })

  function keep(): void {
    if (!storageKey) return
    try {
      sessionStorage.setItem(storageKey, JSON.stringify({ inputs: lastInputs, seed: lastSeed, shown }))
    } catch {
      /* quota: the yardstick holds until the next reload */
    }
  }

  function show(n: number): void {
    seed.value = n
    shown = n
  }

  /**
   * The seed for the run that is about to go out, given its inputs as one key.
   * Writes it into the field. The run becomes the yardstick only once its
   * picture arrives (`arrived`).
   */
  function seedForRun(inputs: string): number {
    const field = asSeed(seed.value)
    let next: number
    if (random.value) {
      next = drawSeed()
    } else if (field !== null && field !== shown) {
      // Typed by hand, or the field's number on a first run.
      next = field
    } else if (pendingSeed !== null && inputs === pendingInputs) {
      // The run that made no picture, asked for again.
      next = pendingSeed
    } else if (inputs !== lastInputs) {
      next = lastSeed ?? field ?? STANDARD_SEED
    } else {
      next = drawSeed()
    }
    show(next)
    pendingInputs = inputs
    pendingSeed = next
    keep()
    return next
  }

  function settle(inputs: string | null, madeWith: number | null): void {
    lastInputs = inputs
    lastSeed = madeWith
    pendingInputs = null
    pendingSeed = null
    keep()
  }

  /**
   * The picture of the run that went out has arrived and stands on the
   * surface. The field takes its seed unless a number was typed into it while
   * the run was going.
   */
  function arrived(inputs: string, runSeed: unknown): void {
    if (disposed) return
    const madeWith = asSeed(runSeed)
    const field = asSeed(seed.value)
    if (madeWith !== null && (field === null || field === shown)) show(madeWith)
    settle(inputs, madeWith)
  }

  /**
   * A run laid back from the run strip or the favourites: its picture stands on
   * the surface and its seed goes into the field. `inputs` is null when the
   * instrument could not read back everything the run went out with; the next
   * press then counts as a change and keeps the picture's seed. `runSeed` is
   * null when the record names none; the field then keeps its number, and the
   * next press takes it as typed.
   */
  function laidBack(inputs: string | null, runSeed: unknown): void {
    if (disposed) return
    const madeWith = asSeed(runSeed)
    if (madeWith !== null) show(madeWith)
    else shown = null
    settle(inputs, madeWith)
  }

  return { seedForRun, arrived, laidBack }
}
