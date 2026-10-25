/**
 * Which model this device has running, for the one line in the Latent Lab's bar
 * that says so.
 *
 * The Flow states which provider and which model a run used; the Latent Lab
 * owes the same transparency. The flow can say it because every step of its
 * run reports its model in the stream it is already reading. The Latent Lab's
 * instruments have no such band, and a declaration per instrument would be
 * twenty-five places
 * saying what a run does — each free to drift from what it really does, and the
 * line may be wrong about none of them.
 *
 * WHERE THE ANSWER COMES FROM. From the connection the run is already holding.
 * The DevServer knows what it sends, and it sends it on behalf of the device
 * that is waiting for the answer, so the name travels back the way the picture
 * does: `note_dispatch` in devserver/my_app/services/streaming_response.py
 * writes it into the two-second heartbeat as a `model_place` frame. Nothing is
 * asked for, nothing is held plant-wide, and no run is serialised.
 *
 * That is device-related BECAUSE it is this device's own connection. A register
 * of what runs where, asked by the browser once a second, was tried on this
 * platform and removed (5d7d6688): it could
 * only answer for the whole machine, so in a room where two people work at once
 * it named whichever run began last.
 *
 * WHAT IS HELD is what the last dispatch said, for as long as the run that made
 * it is out. The two transports fill it and empty it — lib/sseStream.ts
 * and composables/useGenerationStream.ts — and no instrument writes here. The
 * frames keep coming for as long as the run is at that model, so the line
 * survives being cleared by mistake; what it does not survive is being cleared
 * by a stream that never wrote it, which is what `RunOwner` below is for.
 */
import { computed, shallowRef, type ComputedRef } from 'vue'

/** One model at work, exactly as the dispatch named it. */
export interface DispatchedModel {
  /** The identifier that went on the wire: the service in front of the model's
   *  name where it is reached through one, the repository id where it is not. */
  model: string
  /** Whether it is running on this machine. The id cannot say — a repository id
   *  carries its publisher in front — so the sender says it. */
  local: boolean
}

/**
 * Whoever wrote the line may take it away, and nobody else.
 *
 * One page runs more than one stream at a time, and the short ones end first: a
 * back-translation in Language Comparison, the check on a dropped picture, the
 * translation behind a media field. Each of them ends while the long run it was
 * fired beside is still going, and an unowned clear let any of them empty the
 * bar for the run that was actually working.
 */
export type RunOwner = object

const at = shallowRef<DispatchedModel | null>(null)
let owner: RunOwner | null = null

/**
 * A `model_place` frame has arrived, from the stream `by`.
 *
 * A `model` of null is that end saying the run is at NO model any more — a
 * dispatch that failed, or one that named none. It takes away the line the way
 * the end of a stream does: only its own.
 *
 * Everything else is read defensively, and a frame with no readable model is
 * IGNORED rather than emptying the line: the null above is how "at nothing" is
 * SAID, so a payload that cannot be read is a frame this client does not
 * understand, and the next beat states the truth again anyway.
 *
 * THE LINE IS TAKEN, NOT SHARED. While one stream holds it, another one's name
 * is dropped. The chat figure is mounted on every page, its turn goes down the
 * same transport as an instrument's run, and a turn is short: it would take the
 * line off a run of several minutes and then, ending first, take it away
 * altogether — the run would go on under an empty bar. Whoever holds the line
 * gives it up by ending or by saying it is at nothing, and the next beat of
 * whatever is still running takes it within the two seconds of a heartbeat.
 */
export function noteRunPlace(payload: unknown, by: RunOwner): void {
  const data = payload as { model?: unknown; local?: unknown } | null | undefined
  if (data && 'model' in data && data.model === null) {
    clearRunPlace(by)
    return
  }
  const model = data && typeof data.model === 'string' ? data.model : ''
  if (!model) return
  if (owner !== null && owner !== by) return
  at.value = { model, local: !!data?.local }
  owner = by
}

/** The stream `by` is over, however it ended. It takes its own line with it and
 *  leaves anybody else's standing. */
export function clearRunPlace(by: RunOwner): void {
  if (owner !== by) return
  at.value = null
  owner = null
}

/** What the bar reads. */
export function useRunPlace(): { place: ComputedRef<DispatchedModel | null> } {
  return { place: computed(() => at.value) }
}

// An edit in development replaces this module and leaves the line standing at
// whatever the instance behind it last held.
if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    at.value = null
    owner = null
  })
}
