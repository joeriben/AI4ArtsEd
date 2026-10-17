import type { MediumId } from './useMediumInference'

/**
 * Deterministic material → pipeline routing (Phase 1, no agent).
 *
 * The assemblage surface collects free material (text objects, images). The
 * Stage-4 config is NOT the medium alone: the i2i / i2v / multi-image chunk
 * lives in a *distinct* output config, and the backend never auto-switches on
 * image presence — it only forwards input_image / input_image1..3. So routing
 * to the right config, and mapping images to the right params, is the caller's
 * job. This resolver encodes that mapping (configs verified in
 * devserver/schemas/configs/output/).
 *
 * The medium is inferred upstream from the (transformed) text. An *inferred*
 * medium may be clamped here: two or more images force `image`, because the sole
 * multi-image pipeline (qwen_2511_multi) is image-out. A medium picked by hand is
 * clamped in one case only — 3d without a picture, which has no path at all —
 * and material the chosen route cannot consume is READ INTO WORDS by the caller
 * (x2x_flow's readIntoWordsIds, marked "Tt") rather than silently dropped: its
 * reading goes into the prompt in front of what was written.
 *
 * A model picked by hand holds AS LONG AS THE MATERIAL CAN FEED IT. Picked with
 * too few pictures — an image editor on an empty board, the fusion with one — it
 * is overridden by automatic routing, because the surface never refuses to
 * generate: it always finds something to make. What it settled
 * on is what the create box names, and the mark that says "your choice holds"
 * is withheld while a pick lies dropped.
 *
 * One route is exempt, and for a reason that is not a preference: 3d has no
 * text path at all. Giving way there would mean giving up the medium, so the
 * run makes the picture first and the mesh from it (`noOtherPath`, see
 * finishRun). Every other image-input route has a text path beside it.
 */

// Image-input configs.
const I2I_IMAGE = 'qwen_img2img' // 1 image → image (Qwen Image Edit Lightning)
const I2V_VIDEO = 'wan22_i2v_video' // 1 image → 5s video (WAN 2.2 i2v)
const MI2X_MULTI = 'qwen_2511_multi' // 1–3 images → image (fusion); backend prunes unused slots
const I2_3D = 'hunyuan3d_text_to_3d' // 1 image → textured GLB mesh (Hunyuan3D-2)

/** How the consumed images are handed to the pipeline. */
export type ImageParam = 'none' | 'single' | 'multi'

/**
 * One image-input route, stated once. Everything the surface needs to know
 * about these four configs — the medium whose list they belong in, the name
 * they are shown under, how many images they take and how those are handed
 * over — is read from here and from nowhere else.
 *
 * Being in this table IS the statement "this config's input is an image", and
 * `minImages` is the count below which a hand-pick gives way to automatic
 * routing — unless `noOtherPath`, where the run makes the picture instead.
 * Either way none of these is ever dispatched empty. Note that hunyuan3d's file
 * name says "text_to_3d" but the chunk reads `input_image`: there is no text→3d
 * path on this platform, which is exactly why it carries `noOtherPath`.
 *
 * Until this table existed the same four configs were described in four
 * separate places, and a fifth one added to some but not all of them failed
 * quietly: no name on screen, or no gate, or a dispatch with no image at all.
 */
export interface RouteSpec {
  id: string
  /** Short name — these configs are not in the page's curated medium lists. */
  label: string
  medium: MediumId
  /** Fewest it can run with. Below this a hand-pick gives way to auto routing. */
  minImages: number
  /** Most it consumes; anything beyond is surplus, never silently dropped. */
  maxImages: number
  imageParam: ImageParam
  /**
   * There is no other way to this medium. Reached with too few pictures, this
   * route does NOT give way to automatic routing — the run makes the picture it
   * needs and then dispatches this: an SD3.5 image is generated as the natural
   * intermediate step, output as well, and the 3D is made from it. True for 3d
   * alone.
   */
  noOtherPath?: boolean
}

export const IMAGE_INPUT_ROUTES: RouteSpec[] = [
  { id: I2I_IMAGE, label: 'Qwen Edit', medium: 'image', minImages: 1, maxImages: 1, imageParam: 'single' },
  // Two, and this is a real condition rather than a preference: the backend
  // does prune the unused encoder slots for a single image, but the config's
  // own adaption instruction is unconditionally multi-image ("Specify how to
  // combine the images"), so a one-image run is handed "merge these pictures"
  // for a board holding one.
  { id: MI2X_MULTI, label: 'Qwen Multi', medium: 'image', minImages: 2, maxImages: 3, imageParam: 'multi' },
  { id: I2V_VIDEO, label: 'Wan i2v', medium: 'video', minImages: 1, maxImages: 1, imageParam: 'single' },
  { id: I2_3D, label: 'Hunyuan3D', medium: '3d', minImages: 1, maxImages: 1, imageParam: 'single', noOtherPath: true },
]

const ROUTE_BY_ID = new Map(IMAGE_INPUT_ROUTES.map((r) => [r.id, r]))

/** The route this config id names, if its input is an image. */
export function imageInputRoute(id: string): RouteSpec | undefined {
  return ROUTE_BY_ID.get(id)
}

/**
 * The one-image route a medium has, if it has one. The fusion route is not one
 * of these: what two or more images reach is a different decision, taken
 * further down, and putting it here would make it the answer for one image too.
 */
const SINGLE_IMAGE_ROUTE = new Map(
  IMAGE_INPUT_ROUTES.filter((r) => r.maxImages === 1).map((r) => [r.medium, r])
)

/** Short display labels for route configs not present in configsByMedium. */
export const ROUTE_LABELS: Record<string, string> = Object.fromEntries(
  IMAGE_INPUT_ROUTES.map((r) => [r.id, r.label])
)

export interface MaterialRoute {
  /** Stage-4 output config id. */
  outputConfigId: string
  /** Medium after clamping (≥2 images ⇒ image). */
  medium: MediumId
  /** How many images this route consumes (0, 1, or up to 3). */
  maxImages: number
  /** How to send the consumed images. */
  imageParam: ImageParam
}

export interface RouteInput {
  imageCount: number
  /** Inferred / hand-set medium, before clamping. */
  medium: MediumId
  /**
   * What to make when no image is consumed (from configsByMedium). For a medium
   * that has no text path at all — 3d, whose only chunk reads a picture — the
   * caller passes the image default: from words alone, a picture is what there
   * is to make.
   */
  t2xConfigId: string
  /** A model the user picked by hand. Honoured wherever the material feeds it. */
  pinnedConfigId?: string | null
  /** True when `medium` was picked by hand, which forbids clamping it. */
  mediumPinned?: boolean
}

export function resolveRoute({
  imageCount,
  medium,
  t2xConfigId,
  pinnedConfigId = null,
  mediumPinned = false,
}: RouteInput): MaterialRoute {
  // A hand-picked model wins over everything the canvas suggests, as far as the
  // material carries it. If it is a text-only config, the images on the board
  // are read into words instead — pick SD3.5 with three images present and you
  // get SD3.5, with all three pictures read into its prompt.
  const pinned = pinnedConfigId ? ROUTE_BY_ID.get(pinnedConfigId) : undefined
  // Too few pictures for what was picked: an image editor on an empty board,
  // the fusion with one. Nothing could come of dispatching it, so the pick
  // gives way and the automatic route below decides. The pick is not forgotten:
  // drag a picture that already lies there into the ring and it takes effect
  // again. (Adding a NEW picture from outside releases every hand-pick — that
  // is the older rule, and it is the one the tooltip states.)
  // `noOtherPath` is the exception: there is nothing to give way TO, so the run
  // makes the picture rather than the medium being dropped.
  const pinServed =
    !!pinnedConfigId && (!pinned || pinned.noOtherPath || imageCount >= pinned.minImages)
  if (pinnedConfigId && pinServed) {
    const consumed = pinned ? Math.min(pinned.maxImages, Math.max(0, imageCount)) : 0
    return {
      outputConfigId: pinnedConfigId,
      medium,
      maxImages: consumed,
      imageParam: consumed > 0 ? pinned!.imageParam : 'none',
    }
  }

  // No images → pure text-to-X, medium as inferred. Except 3d, which has no
  // text path at all: it keeps its config, and the run makes the picture that
  // config reads (finishRun) before dispatching it. The intermediate picture
  // falls on the table like every other artifact.
  if (imageCount <= 0) {
    if (medium === '3d') {
      return { outputConfigId: I2_3D, medium: '3d', maxImages: 0, imageParam: 'none' }
    }
    return { outputConfigId: t2xConfigId, medium, maxImages: 0, imageParam: 'none' }
  }

  // Exactly one image → image-conditioned, if the medium has an i-path.
  if (imageCount === 1) {
    const spec = SINGLE_IMAGE_ROUTE.get(medium)
    if (spec) {
      return { outputConfigId: spec.id, medium, maxImages: 1, imageParam: spec.imageParam }
    }
    // sound and code: no image→x pipeline. Run t2x; the image is read into words.
    return { outputConfigId: t2xConfigId, medium, maxImages: 0, imageParam: 'none' }
  }

  // Two or more images → multi-image fusion (image-out), which is only reachable
  // by clamping the medium to `image`. A hand-picked medium forbids that: it
  // holds, takes what its own path can consume, and the rest becomes surplus.
  if (mediumPinned && medium !== 'image') {
    const spec = SINGLE_IMAGE_ROUTE.get(medium)
    if (spec) {
      return { outputConfigId: spec.id, medium, maxImages: 1, imageParam: spec.imageParam }
    }
    return { outputConfigId: t2xConfigId, medium, maxImages: 0, imageParam: 'none' }
  }

  // Backend consumes input_image1/2/3 and prunes unused slots (≤3).
  return { outputConfigId: MI2X_MULTI, medium: 'image', maxImages: 3, imageParam: 'multi' }
}
