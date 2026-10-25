/**
 * What each reading actually weighs, at a given alpha, under a given strategy.
 *
 * The surface here is showing what `_fuse_prompt` will do
 * (gpu_service/services/diffusers_backend.py). The arithmetic therefore belongs
 * in one place, and every reader of it — the coefficient line beside the slider,
 * the field map's numbers, the field map's vectors — takes the same numbers from
 * it.
 *
 * It was written twice before, and the two copies had drifted from the backend
 * in two different directions:
 *
 *   - Both capped the growing weight at 1 (`Math.min(1, ...)`), which
 *     centered_fade explicitly does not do ("KEIN min-Deckel auf die wachsende
 *     Seite"). Past an anchor the surface said 1.00 CLIP where the run used 2.00.
 *   - The field map's vectors ignored the strategy altogether and always drew
 *     the legacy LERP, so at alpha -0.5 under centered_fade it drew 1.50 CLIP
 *     and -0.50 T5 beneath a readout that correctly said 1.00 and 0.50.
 */

/**
 * The strategy names this file answers for: the two the Surrealizer sends
 * (centered_fade, two_interceptions) and the three that can arrive with a
 * restored run or from the canvas (legacy, dual_alpha, normalized). What each
 * of them does to the core positions stands in fusionWeights() below, read off
 * `_fuse_prompt` as the head of this file says.
 *
 * `two_interceptions` is not a name the backend knows. It is centered_fade's
 * arithmetic on prompts adapted per model: the route has a language model
 * write a keyword list for the CLIP encoders and a prose paragraph for T5
 * (my_app/services/surrealizer_original), hands both down, and sends the
 * backend `centered_fade` with the same options (schema_pipeline_routes,
 * "ENCODER FUSION, ADAPTED PROMPTS"). On the surface it is „Adapted prompts",
 * the second position of the switch „Same prompt" / „Adapted prompts".
 * Everything here that reads a strategy therefore treats the two names alike;
 * what tells them apart is the prompts, and the prompts are not this file's
 * business.
 *
 * `original`, the 2025 ComfyUI workflow reproduced in the backend (CLIP-L
 * alone, T5 at the length of its own text), has no chip on the surface. Next
 * to centered_fade it changed three things at once and could not say which of
 * them did what, so it is out of the picker. It stays in the backend for the
 * research that cites it and is reached by hand.
 * A stored run naming it is a run this page has no chip for, and is handled as
 * one (see the restore in views/surrealizer.vue).
 *
 * It is not every name the backend knows. `_fuse_prompt` dispatches twenty-one,
 * and the three pickers between them offer six; the rest are the fusion
 * research and reachable only by hand. The canvas keeps a fourth list, narrower
 * again (`_FUSION_STRATEGIES` in
 * devserver/my_app/services/canvas_graph_authoring.py: legacy, dual_alpha,
 * centered_fade). Holding four lists in step is not something a type can do.
 * What it does do is smaller and worth having: an unrecognised name used to be
 * answered here with the LERP below, so a strategy added to a picker and not
 * added here would have drawn legacy's numbers under its run — the drift this
 * file was written to end, arriving from the other side. That name is now a
 * compile error at the call.
 *
 * `slerp` is left out because its core is no pair of factors on the two
 * readings. Both are normalised to unit length first; the turned direction is
 * (sin((1-a)t)·u_CLIP + sin(at)·u_T5)/sin t with t the angle between them,
 * which differs from token to token; and that unit result is then scaled by
 * (1-a)·‖CLIP‖ + a·‖T5‖. The Encoder Fusion Workbench, where slerp is offered,
 * prints that whole formula and never asks this file.
 */
/*
 * Written out rather than derived from the array below, so that the five names
 * are readable where the type is.
 *
 * One thing it does not buy back: SayableFieldMap's `strategy` prop compiled to
 * `type: String` while it was declared `string`, and compiles to `type: null`
 * now that it names this type through the `@` alias — the SFC compiler emits no
 * runtime check for a type it cannot read at the prop. Nothing is lost that was
 * worth having. That check only ever asked whether the value was a string; the
 * type asks which of the five it is, at both call sites, before the build runs.
 */
export type FusionStrategy =
  | 'centered_fade'
  | 'two_interceptions'
  | 'legacy'
  | 'dual_alpha'
  | 'normalized'

export const FUSION_STRATEGIES = [
  'centered_fade',
  'two_interceptions',
  'legacy',
  'dual_alpha',
  'normalized',
] as const satisfies readonly FusionStrategy[]

/** Narrows a name that arrives as text — a restored record, a stored session. */
export function isFusionStrategy(value: string): value is FusionStrategy {
  return (FUSION_STRATEGIES as readonly string[]).includes(value)
}

export interface FusionWeights {
  /** What the CLIP reading (CLIP-L + CLIP-G) is multiplied by on the core positions. */
  clip: number
  /** What the T5 reading is multiplied by on the core positions. */
  t5: number
}

/**
 * centered_fade's normal band, as a half-width: the anchors sit at +/- this.
 * The backend's NORMAL_BAND_H; the slider spans twice it, so that both the
 * inverted continuations are reachable.
 */
const NORMAL_BAND_H = 1.0

export function fusionWeights(alpha: number, strategy?: FusionStrategy): FusionWeights {
  // The plain LERP over the core positions. It is what legacy, dual_alpha and
  // normalized do there, and what an unnamed strategy has always been answered
  // with. (dual_alpha's 0.15x on the extended tail is not a core weight and
  // does not belong on this line; normalized's rescaling lands on the tail as
  // well.)
  const lerp = (): FusionWeights => ({ clip: 1 - alpha, t5: alpha })
  if (strategy === undefined) return lerp()
  // A switch with no `default`, under an annotated return type: a sixth name in
  // FusionStrategy that nobody handles here is a compile error, rather than a
  // run quietly drawn with legacy's numbers.
  switch (strategy) {
  // The same arithmetic on prompts adapted per model; see the head of this file.
  case 'two_interceptions':
  case 'centered_fade': {
    // An axis with a genuine middle: at 0 BOTH readings act fully — that is the
    // point of it — and the control fades toward one or the other. Past an
    // anchor the fading side inverts while the standing side keeps growing.
    const t = alpha / NORMAL_BAND_H
    return t <= 0
      ? { clip: Math.max(1, -t), t5: 1 + t }
      : { clip: 1 - t, t5: Math.max(1, t) }
  }
  // These three read alpha as "how far past T5": the LERP passes 1 and keeps
  // going. They are not on the centred axis and keep the unshifted reading.
  case 'legacy':
  case 'dual_alpha':
  case 'normalized':
    return lerp()
  }
}

/*
 * Two settings stood beside the switch and are gone.
 *
 * The path of the core, „Chord" / „Sphere": the sphere turned the direction
 * from CLIP toward T5 and ran the length between the two readings' lengths,
 * and the backend took it as "<base>#path=sphere". The sphere is the
 * interpolation between the embeddings of two DIFFERENT prompts; between the
 * two readings of one prompt it has no object. The backend keeps the name for
 * the stored runs and for the research that cites it; no surface sends it.
 *
 * A settable law over the T5 tail, gone from the surface and from the backend
 * with it. It had two forms, 0.15 * alpha and (alpha / anchor) ** F, and the
 * anchor was derived from the 0.15 it replaced, so the smoother function
 * carried the arbitrariness of the constant it was meant to improve on. A
 * variable that no hypothesis can be formed about has no business on the
 * surface. A tail law comes back through a predicted effect, grounded and
 * then empirically redeemed, and an aesthetic or didactic gain that pays for
 * the apparatus.
 *
 * The tail carries its own length. dual_alpha keeps its 0.15, which is what
 * distinguishes that strategy and is not a setting of any surface.
 */

/** What a stored strategy string says, taken apart again. */
export interface ParsedFusionStrategy {
  /** The bare fusion name. NOT narrowed: a stored run may name any of the
   *  twenty-one the backend dispatches, and the caller decides what to do with
   *  one this file does not answer for. */
  base: string
  /** Whether the run walked the sphere ("#path=sphere"), which no surface
   *  offers. Such a run is one the page cannot reproduce. */
  sphere: boolean
}

/**
 * Backend -> axis: a strategy string that may carry options, taken apart.
 *
 * Every place that reads a STORED strategy goes through this — a restored run,
 * a card in the series, the session picked up again — because what was sent
 * between 2026-09-10 and 2026-09-12 is a composed string, "<base>#k=v#...",
 * and what those places need is the fusion's name and whether the run is one
 * the page still offers. Strings recorded on 2026-09-10 may also carry
 * "tail=" and "tf=", from a law that stood for one day; they are read past.
 */
export function parseFusionStrategy(text: string): ParsedFusionStrategy {
  const parts = String(text || '').split('#')
  const opts: Record<string, string> = {}
  for (const p of parts.slice(1)) {
    const i = p.indexOf('=')
    if (i > 0) opts[p.slice(0, i)] = p.slice(i + 1)
  }
  return {
    base: parts[0] ?? '',
    sphere: opts.path === 'sphere',
  }
}

/** The reachable range of alpha, and how finely it is divided. */
export interface AlphaScale {
  min: number
  max: number
  step: number
  /**
   * The stretch of the axis the instrument exists for, and the setting that
   * stands at the middle of the track. Everything between `lo` and `hi` is
   * drawn linearly and takes the middle 60 % of the track; past it the track
   * runs logarithmically to the ends.
   */
  band: { lo: number; mid: number; hi: number }
}

/**
 * The axis a fusion is read on.
 *
 * The two the Surrealizer offers share one axis, -75..+75 (the fp16 edge) with
 * CLIP alone at -1, both readings full at 0 and T5 alone at +1, because they
 * are one arithmetic on different texts. A run is asked for the alpha the axis
 * shows, in these units, on both.
 *
 * The second chip used to be the 2025 workflow, whose own alpha ran 0..1 with
 * the mix at 0.5; it stood on this track shifted by that half (AXIS_OFFSET),
 * with anchors at -0.5 and +0.5. The shift and the second band went with the
 * chip. `mid` stays in the band, and the track
 * arithmetic below stays written from it, so an axis that is not centred on
 * zero can come back without the track being rewritten.
 */
const CENTERED_SCALE: AlphaScale = {
  min: -75,
  max: 75,
  step: 0.05,
  band: { lo: -1, mid: 0, hi: 1 },
}
const ALPHA_SCALES: Record<string, AlphaScale> = {
  centered_fade: CENTERED_SCALE,
  two_interceptions: CENTERED_SCALE,
}
const DEFAULT_ALPHA_SCALE: AlphaScale = {
  min: -75,
  max: 75,
  step: 0.1,
  band: { lo: -1, mid: 0, hi: 1 },
}

export function alphaScaleFor(strategy?: FusionStrategy): AlphaScale {
  return (strategy && ALPHA_SCALES[strategy]) || DEFAULT_ALPHA_SCALE
}

/**
 * Where a setting SITS on the track, which is not the same as what it is.
 *
 * The slider runs on positions and alpha is read off them, because on a linear
 * -75..+75 track the part of the axis this instrument exists for is 1.3 % wide.
 * Those places came out two pixels apart, so the one reading the axis is good
 * for could not be set. A linear alpha scale is too tight around 0; the scale
 * is non-linear so that the CLIP/T5 points remain discernible, and the band
 * can also serve to explore CLIP vs. T5 shares.
 *
 * Inside the band the track is linear and takes BAND_SHARE of each half; past
 * the band it is logarithmic and runs to the end of the scale. The two meet at
 * the band edge without a step, and the mapping is invertible - a stored alpha
 * finds its position again, which is what the marks and the restore need.
 *
 * The band need not be centred on zero: the arithmetic below is written from
 * `mid` outwards in both directions and reduces exactly to the symmetric case
 * when `mid` is 0, which it is on every axis this page has.
 */
export const BAND_SHARE = 0.3
const POS_MAX = 1000
export const ALPHA_POSITIONS = { min: -POS_MAX, max: POS_MAX, step: 1 }

/**
 * How close to a whole number the handle has to come for the axis to take it,
 * in POSITIONS. Ten of a thousand is about four pixels on the track this axis
 * is drawn at — the handle catches, and everything between two whole numbers
 * stays reachable. The magnet never takes more than SNAP_SHARE of the gap it
 * sits in, so on the crowded end of the log stretch, where whole numbers stand
 * three positions apart, it shrinks with them instead of swallowing the axis.
 *
 * Snap means latching at the position, not reduction to integers: a build that
 * rounded everything past the band took the values in between away with it.
 */
const SNAP_POS = 10
const SNAP_SHARE = 0.3

/** Reach of one side, never shorter than the band: log(span/band) must stay > 0. */
function sideSpan(scale: AlphaScale, up: boolean): number {
  const { lo, mid, hi } = scale.band
  return up
    ? Math.max(scale.max - mid, 2 * (hi - mid))
    : Math.max(mid - scale.min, 2 * (mid - lo))
}

export function alphaToPos(alpha: number, scale: AlphaScale = DEFAULT_ALPHA_SCALE): number {
  const { lo, mid, hi } = scale.band
  const up = alpha >= mid
  const bandReach = up ? hi - mid : mid - lo
  const span = sideSpan(scale, up)
  const d = Math.min(up ? alpha - mid : mid - alpha, span)
  const q =
    d <= bandReach
      ? BAND_SHARE * (d / bandReach)
      : BAND_SHARE + (1 - BAND_SHARE) * (Math.log(d / bandReach) / Math.log(span / bandReach))
  return Math.round((up ? 1 : -1) * q * POS_MAX)
}

export function posToAlpha(pos: number, scale: AlphaScale = DEFAULT_ALPHA_SCALE): number {
  const { lo, mid, hi } = scale.band
  const up = pos >= 0
  const bandReach = up ? hi - mid : mid - lo
  const span = sideSpan(scale, up)
  const u = Math.min(Math.abs(pos) / POS_MAX, 1)
  const d =
    u <= BAND_SHARE
      ? bandReach * (u / BAND_SHARE)
      : bandReach * Math.pow(span / bandReach, (u - BAND_SHARE) / (1 - BAND_SHARE))
  const a = up ? mid + d : mid - d
  return snapToWhole(a, pos, scale)
}

/**
 * The whole numbers hold the handle.
 *
 * They are where this axis is read and written — the anchors at 0 and +/-1,
 * and out on the log stretch the settings the legacy workflow itself ran (15 to
 * 35). On a track that hands out 4,87 and 5,31 they could not be asked for at
 * all. So each whole number takes the positions right around it, and only those:
 * a value between two of them is set by standing between them.
 *
 * The magnet is measured on the track, not in alpha, because that is where the
 * hand is: the same few pixels everywhere, and never more than SNAP_SHARE of
 * the gap the handle is in. In the band, where one unit is 300 positions wide,
 * that leaves the axis its two decimals and only catches at the anchors.
 */
function snapToWhole(alpha: number, pos: number, scale: AlphaScale): number {
  const free = Math.round(alpha * 100) / 100
  const lo = Math.floor(free)
  const hi = Math.ceil(free)
  if (lo === hi) return free
  const posLo = alphaToPos(lo, scale)
  const posHi = alphaToPos(hi, scale)
  const radius = Math.min(SNAP_POS, SNAP_SHARE * (posHi - posLo))
  if (pos - posLo <= radius) return lo
  if (posHi - pos <= radius) return hi
  return free
}
