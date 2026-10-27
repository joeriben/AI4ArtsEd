/**
 * The run behind a picture raster: what is in the cells, what still has to be
 * computed, and the loop that computes it one cell at a time.
 *
 * Built inside Cultural (Un)Known, copied comment for comment into LoRA Explorer
 * on 2026-08-29, and gathered here the same day — the raster's CSS had already
 * gone to `assets/flow-stage.css` (`.lab-grid`) and its measurement to
 * `useGridCellWidth.ts`, and the loop around them was the third copy of the same
 * behaviour. Rule 13.
 *
 * What a surface keeps for itself: what its rows and columns ARE, what a cell is
 * keyed by, and how one cell is computed. What is here is everything that was
 * word for word the same on both.
 */
import { onBeforeUnmount, ref, type Ref } from 'vue'
import { refusalKeyOf } from '@/composables/useLabRun'

/**
 * A cell is in exactly one of four states, and a surface has to be able to show
 * which: not run yet (nothing set), a picture, refused (`blockedKey` — the KEY,
 * so a surface switched to another language after the run does not keep this one
 * cell in the old one), or nothing came back (`failed`). Without the last of
 * these a hole in a raster reads as a cell that has not run, and the counting a
 * surface invites is quietly wrong.
 */
export interface RasterCell {
  key: string
  /** The seed the run ACTUALLY worked with, not the one it was asked for. */
  seed: number
  url: string
  blockedKey: string
  failed: boolean
  /**
   * WHY nothing came back, as a key. `failed` alone says only that a hole is a
   * hole; a surface that can name the cause (the card is taken, the model is not
   * installed, the queue is full) says it here, in the same key-not-sentence
   * form as `blockedKey`. Absent where the caller did not work one out.
   */
  failedKey?: string
  /** The values the sentence of `failedKey` names (a provider, say). */
  failedParams?: Record<string, string>
  /**
   * WHY nothing came back, as the sentence the platform answered with (the
   * `error` of the run's reply: a ComfyUI node that failed, a model file that
   * is missing). Read where `failedKey` is absent, so the cause stands where the
   * picture would instead of the house sentence; it is the route's wording and
   * does not follow a language switch, which is why a keyed cause comes first.
   * Absent where the reply carried no sentence.
   */
  failedText?: string
  /** What the back of the card is made of — the run this picture came from. */
  runId?: string
  modelMeta?: Record<string, any> | null
  durationMs?: number
  createdAt?: number
}

export interface RasterRun {
  /** Every cell that has a result, by its key. */
  cells: Ref<Record<string, RasterCell>>
  running: Ref<boolean>
  /** How many cells have come back in this run. */
  done: Ref<number>
  /**
   * What the counter counts, fixed when the run starts: what is still to do
   * shrinks as the pictures arrive, and a denominator walking down with the
   * numerator would read 1/1 all the way through. A plan handed over as a
   * stream of steps has no length to read it from; the surface that writes the
   * stream keeps this number itself.
   */
  expected: Ref<number>
  /**
   * Run a plan, one step at a time and in the order given. Returns when the
   * plan is through or when the run was dropped.
   *
   * The plan is a list, or a stream of steps the surface is still writing while
   * the first of them run: Mean Images makes the pictures of the prompt as
   * entered while a language model writes the variants the other column needs,
   * and the steps for those join the run when the variants are back. A stream
   * notices a drop when it hands over its next step, so one that is waiting
   * returns only then. Steps are plain values: a step that is a promise would
   * be awaited.
   */
  start: <S>(plan: S[] | AsyncIterable<S>, runOne: (step: S) => Promise<void>) => Promise<void>
  /**
   * Whether the run a step belongs to is still the current one — the same
   * question the loop asks between two steps. A step that itself makes more
   * than one call asks it in the middle, or a surface the reader has left
   * starts one more of them after they are gone.
   */
  live: () => boolean
  /** A picture came back. False where the answer carried none. */
  recordImage: (key: string, seed: number, data: any) => boolean
  /** A refusal, at the cell it refused. False where the error is not one. */
  recordBlocked: (key: string, seed: number, err: unknown) => boolean
  /**
   * Nothing came back at all. `failedKey` is the cause as a key, from
   * `failureKey()`; `failedText` the sentence the reply carried, for the cause
   * that classifier has no key for; `failedParams` the values the sentence of
   * `failedKey` names. All optional, because a surface that has no cause to
   * hand still has to be able to mark the hole.
   */
  recordFailed: (key: string, seed: number, failedKey?: string, failedText?: string,
    failedParams?: Record<string, string>) => void
  /**
   * Give up the run that is going. The loop notices between two steps and
   * returns; a picture already out still comes back and is dropped, exactly as
   * when the instrument is left. For a surface whose ground is pulled out from
   * under a run — a stored raster brought in from the gallery, say — where
   * going on would generate into somebody else's cells.
   */
  stop: () => void
}

export function useRasterRun(): RasterRun {
  const cells = ref<Record<string, RasterCell>>({})
  const running = ref(false)
  const done = ref(0)
  const expected = ref(0)

  /**
   * Which run is the current one. A raster is up to several dozen pictures and
   * runs for minutes; leaving the instrument in the middle of it used to leave
   * the loop generating into a component nobody was looking at any more, while a
   * fresh instance let a second run start beside it and both queued for the same
   * card. The pattern is Bias Archaeology's.
   */
  let runToken = 0
  let activeToken = 0

  onBeforeUnmount(() => {
    runToken++
  })

  function put(cell: RasterCell): void {
    cells.value = { ...cells.value, [cell.key]: cell }
  }

  async function start<S>(plan: S[] | AsyncIterable<S>, runOne: (step: S) => Promise<void>): Promise<void> {
    if (running.value) return
    const mine = ++runToken
    activeToken = mine
    running.value = true
    done.value = 0
    if (Array.isArray(plan)) expected.value = plan.length
    try {
      for await (const step of plan) {
        if (mine !== runToken) return
        await runOne(step)
        if (mine !== runToken) return
        done.value++
      }
    } finally {
      if (mine === runToken) running.value = false
    }
  }

  function live(): boolean {
    return activeToken === runToken
  }

  function stop(): void {
    if (!running.value) return
    runToken++
    running.value = false
  }

  function recordImage(key: string, seed: number, data: any): boolean {
    const url = data?.media_output?.url || ''
    if (!url) return false
    // The seed the run actually worked with. A raster rests on its cells sharing
    // their seed, so the record has to read what came back instead of repeating
    // what was sent.
    const got = data?.media_output?.seed
    put({
      key,
      seed: typeof got === 'number' ? got : seed,
      url,
      blockedKey: '',
      failed: false,
      runId: data?.media_output?.run_id || data?.run_id || undefined,
      modelMeta: data?.model_meta ?? null,
      durationMs: typeof data?.duration_ms === 'number' ? data.duration_ms : 0,
      createdAt: Date.now(),
    })
    return true
  }

  function recordBlocked(key: string, seed: number, err: unknown): boolean {
    // A refusal belongs at the cell it refused, not as a line over the whole
    // surface: the other cells of the run are unaffected and stay readable. The
    // reasons are German developer strings and are never shown raw, so the
    // reading is the platform's one (composables/useLabRun.ts).
    const blockedKey = refusalKeyOf(err)
    if (!blockedKey) return false
    put({ key, seed, url: '', blockedKey, failed: false })
    return true
  }

  function recordFailed(key: string, seed: number, failedKey?: string, failedText?: string,
    failedParams?: Record<string, string>): void {
    put({ key, seed, url: '', blockedKey: '', failed: true, failedKey, failedText, failedParams })
  }

  return { cells, running, done, expected, start, live, stop,
           recordImage, recordBlocked, recordFailed }
}

/**
 * The lines of a written field, trimmed, in the order they stand, empty and
 * repeated ones dropped. A line twice would be the same column twice, and a
 * cell is keyed by the prompt it was made from — the two would collide.
 */
export function uniqueLines(text: string): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (line && !seen.has(line)) {
      seen.add(line)
      out.push(line)
    }
  }
  return out
}
