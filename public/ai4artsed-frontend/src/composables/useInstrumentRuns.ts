/**
 * The runs an instrument has made, as the cards of its own strip.
 *
 * The strip itself is `components/canvas/OutputDrawer.vue` — the platform's one
 * surface for laying runs side by side. What was missing under it was memory:
 * the cards lived in a local array, so a reload emptied the strip while every
 * run of it lay complete on disk, each one carrying the sitting it was made in.
 *
 * This composable is that memory, and it is ONE implementation rather than one
 * per instrument (Rule #13): it holds the cards, it takes one away, and on
 * mount it asks the server for the runs of this tab's sittings and lets the
 * instrument turn each one into its own card. What a card SAYS stays the
 * instrument's business — only the instrument knows which two of its parameters
 * tell two of its runs apart.
 */
import { computed, inject, onActivated, onDeactivated, onMounted, onUnmounted, ref } from 'vue'
import type { InjectionKey, Ref } from 'vue'
import { useDeviceId } from './useDeviceId'
import { dismiss, dismissed, fetchSessionRuns, sittingsOf, type InstrumentRun } from './useLatentLabRecorder'
import type { DrawerItem } from '@/components/canvas/OutputDrawer.vue'

/**
 * Where the strip STANDS.
 *
 * An instrument that fills the work area lays its own strip along its bottom
 * edge (Encoder Fusion, Denoising Archaeology, Attention Cartography are built
 * that way). An instrument that is still a page in the lab's narrow measure has
 * no bottom edge of its own - it scrolls inside the frame - so its strip stands
 * in the FRAME, under the work area, and the instrument hands its cards up.
 * One strip, one place; the frame shows whichever instrument is open.
 */
export interface LabRunsPublication {
  runs: Ref<DrawerItem[]>
  /**
   * Where a favourite made from one of these cards says it came from. A ref
   * where one instrument serves several addresses (the crossmodal lab has a
   * tab per address).
   */
  sourceView: string | Ref<string>
  onSelect?: (id: string) => void
  onRemove?: (index: number) => void
}

export interface LabRunsHost {
  publish: (publication: LabRunsPublication) => void
  withdraw: (publication: LabRunsPublication) => void
}

export const LAB_RUNS_HOST: InjectionKey<LabRunsHost> = Symbol('labRunsHost')

export interface InstrumentRunsOptions {
  /**
   * Where a card goes when it arrives. `false` (the default) appends, as most
   * of the strips do; `true` puts the newest first, as Attention Cartography
   * lays them.
   */
  newestFirst?: boolean
  /**
   * Hand the cards to the lab's frame instead of drawing a strip in the page.
   * See LabRunsPublication.
   */
  shell?: { sourceView: string | Ref<string>; onSelect?: (id: string) => void }
  /**
   * Which of the cards the strip SHOWS. Several instruments may record into ONE
   * tool - the three of the Crossmodal Lab do, under the sitting key their
   * shared history is filed by - and runs of two different tools laid side by
   * side are not a comparison, they are two strips in one. The cards themselves
   * are all held either way.
   */
  shownWhen?: (card: DrawerItem) => boolean
}

export interface InstrumentRuns {
  /**
   * Every card this instrument holds, in order. The FILTERED view goes to the
   * frame's strip and stays there: this one is the instrument's own list, and
   * the instruments that lay a card themselves write into it.
   */
  runs: Ref<DrawerItem[]>
  /** Lay one card - a run just made. */
  addRun: (card: DrawerItem | null) => void
  /** Take one card away (the strip's ×). */
  removeRun: (index: number) => void
  /** Ask for the runs of this tab's sittings and lay the ones not already here. */
  restoreSitting: () => Promise<void>
}

export function useInstrumentRuns(
  tool: string,
  cardFor: (run: InstrumentRun) => DrawerItem | null,
  options: InstrumentRunsOptions = {},
): InstrumentRuns {
  const runs = ref<DrawerItem[]>([])
  const deviceId = useDeviceId()

  function addRun(card: DrawerItem | null): void {
    if (!card) return
    if (runs.value.some((existing) => existing.id === card.id)) return
    // The strip's order is its argument, and it is the order the runs were
    // MADE in - not the order they happen to arrive. A restored sitting reaches
    // the surface after a run that has just finished, and appending would put
    // the older cards after the newer one.
    const at = runs.value.findIndex((existing) =>
      options.newestFirst
        ? (existing.createdAt ?? 0) < (card.createdAt ?? 0)
        : (existing.createdAt ?? 0) > (card.createdAt ?? 0)
    )
    if (at < 0) runs.value.push(card)
    else runs.value.splice(at, 0, card)
  }

  function removeRun(index: number): void {
    // A position that is not there must take nothing away: `splice(-1, 1)` would
    // quietly remove the LAST card instead.
    if (index < 0 || index >= runs.value.length) return
    const gone = runs.value[index]
    runs.value.splice(index, 1)
    // The x is the only way to clear the strip, and without a note of it the
    // card came straight back on the next visit and on every reload - the user
    // paid for an action that undid itself.
    if (gone?.runId) dismiss(tool, gone.runId)
  }

  async function restoreSitting(): Promise<void> {
    const sittings = sittingsOf(tool)
    if (!sittings.length) return
    const gone = dismissed(tool)

    const lists = await Promise.all(sittings.map((id) => fetchSessionRuns(id, deviceId)))
    const past = lists
      .flat()
      .sort((a, b) => Date.parse(a.timestamp || '') - Date.parse(b.timestamp || ''))

    for (const run of past) {
      if (gone.has(run.run_id)) continue
      let card: DrawerItem | null = null
      try {
        card = cardFor(run)
      } catch (err) {
        // One run the instrument cannot read leaves the rest of the sitting
        // standing.
        console.warn('[InstrumentRuns] Run not readable as a card:', run.run_id, err)
      }
      if (!card) continue
      // A card may name itself by something other than the record's own id -
      // Encoder Fusion names its cards by the PIPELINE run, because that is
      // where its picture lies. The × notes down whichever name the card
      // carried, so both are asked here; otherwise the next reload undid it.
      if (gone.has(card.id)) continue
      // A run that is already on the surface keeps its place: the strip may have
      // been filled from elsewhere first (a favourite that came back).
      addRun(card)
    }
  }

  /**
   * The cards the strip lays out — all of them, or the ones this surface stands
   * for right now. The × comes back as a position in what is SHOWN, so it is
   * read as the card at that position and taken away by identity; a position
   * counted in a filtered list would otherwise remove a different run.
   */
  const shown = options.shownWhen
    ? computed(() => runs.value.filter(options.shownWhen as (card: DrawerItem) => boolean))
    : runs

  function removeShown(index: number): void {
    const card = shown.value[index]
    if (!card) return
    removeRun(runs.value.indexOf(card))
  }

  // The frame's strip, for an instrument that has no bottom edge of its own.
  const host = options.shell ? inject(LAB_RUNS_HOST, null) : null
  const publication: LabRunsPublication | null = options.shell
    ? { runs: shown, sourceView: options.shell.sourceView, onSelect: options.shell.onSelect, onRemove: removeShown }
    : null

  const hand = () => { if (host && publication) host.publish(publication) }
  const takeBack = () => { if (host && publication) host.withdraw(publication) }

  onMounted(() => {
    hand()
    void restoreSitting()
  })

  /**
   * An instrument inside `KeepAlive` is DEACTIVATED rather than unmounted when
   * it is left, and activated rather than mounted when it comes back — the
   * Crossmodal Lab holds its three that way, so that leaving one does not throw
   * its work away. Without these two the frame's strip went on showing the runs
   * of the instrument the visitor had left.
   *
   * `restoreSitting` stays on the mount alone: the cards are still here, so
   * switching back shows them again without asking the server a second time.
   * Handing over twice on a first mount inside `KeepAlive` costs nothing — the
   * frame holds ONE publication and an activation writes the same one again
   * (views/latent_lab.vue) — and the order of the two calls at a switch does
   * not matter either, because taking back only clears a slot that is still
   * ours.
   */
  onActivated(hand)
  onDeactivated(takeBack)
  onUnmounted(takeBack)

  return { runs, addRun, removeRun, restoreSitting }
}
