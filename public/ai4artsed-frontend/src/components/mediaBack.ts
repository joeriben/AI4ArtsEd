/**
 * What stands on the back of a medium: the record of the run that made it.
 *
 * One shape for the two places the back is drawn — on the turned card
 * (`MediaCardBack` in `FlowCard`'s `back` slot) and beside the medium in the
 * enlarged view (`MediaFullscreen`'s `back` prop). A page fills in what it
 * knows; every field is optional, and a block whose field is left out stays
 * away. The rows from `perspective` to `source` came over from the x2x flow's
 * own inspect layer when that layer was replaced by the platform's one (one
 * click, one view, on every surface); `mediaUrl` and `active` came with it,
 * for reading the file's marking only while the back is looked at.
 */
export interface MediaSource {
  /** What was searched for. */
  term: string
  /** The article that was found, or the term again when nothing was. */
  title: string
  /** Empty when the lookup found nothing. */
  url: string
  /** The opening summary that was retrieved. */
  extract: string
  /** Which Wikipedia was read. */
  lang: string
  /** The perspective that went looking. Empty for a run with no perspective. */
  perspective: string
  /** Why the model looked this up, in its own words. */
  why: string
}

export interface MediaBack {
  /** Left out where the page has no notion of one. Null = there was one and it stayed empty. */
  motivation?: string | null
  /**
   * Optional since 2026-08-19: a canvas run that predates the collector
   * carrying its prompt still has a config, a seed and a time, and those are
   * the facts that tell two of its outputs apart. A back with them and no
   * prompt is worth more than no back at all.
   */
  prompt?: string
  configId?: string
  createdAt?: number
  modelMeta?: Record<string, any> | null
  /**
   * Further facts of the run, already worded by the page, standing beside the
   * config and the time. The runs of an instrument differ by their SETTING —
   * a seed, an alpha, a strategy — and that is what tells two of them apart;
   * it is a record, so it belongs on this side rather than in the card's bar.
   */
  facts?: string[]
  /**
   * What kind of medium the card holds. It is what brings the row of actions —
   * left out, this side stays a record and nothing else, which is what a card
   * without a medium (a graph, a composition, a looked-up source) needs.
   */
  mediaType?: string
  runId?: string | null
  isFavorited?: boolean
  /**
   * It IS kept, and not by the person looking at it: the favourites strip in
   * „All" shows everyone's, and the server refuses a foreign delete. Without
   * this the star stands lit and does nothing.
   */
  keepDisabled?: boolean
  /** What handing it on is called here; the platform's wording otherwise. */
  forwardTitle?: string
  /**
   * Whether the medium can be handed on to the flow at all. On the flow itself
   * it already lies on the table, and a button that would carry it there does
   * nothing — so the flow turns it off.
   */
  canForward?: boolean
  /**
   * Whether the row offers to open the run again in the instrument that made
   * it, with its setting. Only the favourites strip says so, for a run whose
   * instrument reads one back; everywhere else the row has no such button.
   */
  canRestore?: boolean
  /**
   * The setting the run went out with, in one line, already worded by the
   * page: what the instrument puts back when the run is opened there. It
   * stands under the prompt, with its own label, and stays away where the page
   * has none.
   */
  setting?: string
  /**
   * The text Prompt Interception wrote, where the page has one. It stands OVER
   * `prompt`, which is what the image model was given after the adaption — two
   * different texts, and on a surface that compares interceptions the first one
   * is the one being read.
   */
  intercepted?: string
  /** How the page names that text. Without it the block stays away. */
  interceptedLabel?: string
  /** The perspective the run read under, by its name. */
  perspective?: string
  /** The LoRAs the run loaded, named with their strength where it was not the trained one. */
  loras?: string
  /** The checks THIS run passed, by name. */
  safety?: string[]
  /**
   * A source a perspective looked up while it was reading — evidence, not a
   * medium. A card that carries one carries nothing else.
   */
  source?: MediaSource | null
  /**
   * The medium's own address where the page has one (`/api/media/<kind>/<run>[/<index>]`).
   * It names the exact file of a run that produced several, which the run id
   * and the kind alone cannot; the AI marking is read out of that file.
   */
  mediaUrl?: string
  /**
   * Whether this back is being looked at. A card back is rendered face down
   * under every card of a grid; the file is asked about only while the back
   * is turned up, and in the enlarged view it always is.
   */
  active?: boolean
}
