import type { MediumId } from './useMediumInference'

/**
 * Composition routing — "media as operand", the second operation class.
 *
 * Stage-4 generation is prompt -> artifact, and the artifact is a terminal leaf.
 * Post-production is artifact(s) -> artifact (devserver post_production_service).
 * The board makes that reachable: a sound dragged off the output box is no longer
 * a result, it is material.
 *
 * The service resolves inputs by run_id (or an /api/media/<type>/<run_id> URL), so
 * only *artifacts* can be composed — an uploaded file has no run. An image on this
 * board is usually an upload with a server path, which is what the i2i and
 * multi-image pipelines read; but a picture the platform made and let fall keeps
 * its run, and that one composes like any other artifact — either already lying
 * there (`imageRef`) or generated first by this very run (`generate: 'image'`).
 */

export type ComposeOp = 'still_plus_audio' | 'video_plus_audio'

export type ComposeRole = 'image' | 'video' | 'audio'

export interface CompositionPlan {
  op: ComposeOp
  /** Refs that already exist (run_id or media URL), keyed by the service's roles. */
  ready: Partial<Record<ComposeRole, string>>
  /** The role the flow must generate first, or null when nothing has to be made. */
  generate: 'image' | 'video' | null
}

export interface CompositionInput {
  /** There is text material to generate from. */
  hasText: boolean
  /** Medium as inferred or asserted, before any clamping. */
  medium: MediumId
  /** Ref of the first sound on the board, if any. */
  audioRef?: string | null
  /** Ref of the first video on the board, if any. */
  videoRef?: string | null
  /**
   * Ref of the first picture on the board that carries a run — one the platform
   * made and let fall, not an upload. The caller passes null while a perspective
   * lies in the reading: a perspective is there to be applied, and composing
   * would drop it silently.
   */
  imageRef?: string | null
}

/**
 * Decide whether the board describes a composition, and what has to happen first.
 *
 * Returns null when there is nothing to compose. A sound that no plan consumes is
 * not dropped — the caller reads it into words and marks it "Tt", like every
 * other piece of material the chosen route cannot take.
 */
export function planComposition({
  hasText,
  medium,
  audioRef = null,
  videoRef = null,
  imageRef = null,
}: CompositionInput): CompositionPlan | null {
  // A composition is a sound plus a picture. Without sound there is nothing here.
  if (!audioRef) return null

  // Video + sound: both already exist. Nothing is generated; ffmpeg lays one
  // under the other. This runs even without text.
  if (videoRef) {
    return { op: 'video_plus_audio', ready: { video: videoRef, audio: audioRef }, generate: null }
  }

  // Picture + sound, both already made: the same case one medium down. ffmpeg
  // holds the still under the sound and nothing is generated. Words outrank
  // this: with text present the text is still an instruction to make something,
  // so the branches below keep their precedence.
  if (imageRef && !hasText) {
    return { op: 'still_plus_audio', ready: { image: imageRef, audio: audioRef }, generate: null }
  }

  // Text + sound: the text becomes the picture, the sound stays what it is.
  if (hasText) {
    if (medium === 'image') {
      return { op: 'still_plus_audio', ready: { audio: audioRef }, generate: 'image' }
    }
    if (medium === 'video') {
      return { op: 'video_plus_audio', ready: { audio: audioRef }, generate: 'video' }
    }
  }

  // sound + sound, 3d + sound, or a lone sound: no operation exists. Say nothing,
  // and let the caller read the sound into words rather than invent a route.
  return null
}
