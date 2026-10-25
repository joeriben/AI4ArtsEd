/**
 * How a card of the runs strip reads its item: the file, its kind, and the record
 * the card's back shows (`MediaBack`, components/mediaBack.ts).
 *
 * In a module of its own, because the record stands in two places and must be
 * one object in both: on the turned card, and beside the picture in the
 * enlarged view (one click, one view, on every surface). The strip opens that
 * view itself for its own cards; a page that shows a run's picture OUTSIDE the
 * strip (Denoising Archaeology, a frame of the sequence) reads the same record
 * here and stands it beside its frame.
 */
import type { DrawerItem } from '@/components/canvas/OutputDrawer.vue'
import type { MediaBack } from '@/components/mediaBack'

/** The file of an item, where it has one. */
export function getOutputUrl(item: DrawerItem): string | null {
  const output = item.output as Record<string, unknown> | null
  if (output && typeof output === 'object' && 'url' in output) return output.url as string
  return null
}

/** The kind of that file; an item without one is text. */
export function getMediaType(item: DrawerItem): string {
  const output = item.output as Record<string, unknown> | null
  if (output && typeof output === 'object' && 'media_type' in output) return output.media_type as string
  return 'text'
}

/**
 * The record of an item, as its card's back shows it. `isFavorited` is the
 * caller's to say: the strip reads the store, and a page reads what it holds.
 * An item that failed has no file, so no kind and no row of things to do with
 * it; its record stands alone.
 */
export function drawerBack(item: DrawerItem, isFavorited: boolean): MediaBack {
  const url = !item.error ? getOutputUrl(item) : null
  return {
    mediaType: url ? getMediaType(item) : undefined,
    runId: item.runId ?? null,
    mediaUrl: url || undefined,
    isFavorited,
    prompt: item.prompt,
    configId: item.configId,
    createdAt: item.createdAt,
    modelMeta: item.modelMeta ?? null,
    facts: item.meta,
  }
}
