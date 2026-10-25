/**
 * Lazy, queued loading for media that is only ever shown small (list thumbnails).
 *
 * Two mechanisms in one directive:
 *   1. IntersectionObserver - an element only asks for its source once it comes
 *      near the viewport, so a page of 50 rows does not fetch 50 files at once.
 *   2. A module-wide FIFO queue with a small concurrency limit - the elements
 *      that did come into view are served a few at a time, in DOM order, so the
 *      first rows appear immediately instead of everything crawling together.
 *
 * Usage - the directive OWNS the src, so do not also bind `:src`:
 *   <img v-lazy-media="url" class="thumbnail">
 *   <video v-lazy-media="url" muted preload="metadata"></video>
 *
 * The source is read once, at mount. Rows must therefore be keyed by their own
 * identity (`:key="row.id"`), which is what makes Vue create a fresh element per
 * row instead of re-pointing an existing one.
 */

const CONCURRENCY = 3
const ROOT_MARGIN = '300px'
/** Watchdog: a source that never settles must not block the queue forever. */
const SLOT_TIMEOUT_MS = 20000

type LazyEl = (HTMLImageElement | HTMLVideoElement) & { __lazyMediaCleanup?: () => void }

let active = 0
const pending: Array<() => void> = []

function pump(): void {
  while (active < CONCURRENCY && pending.length > 0) {
    const job = pending.shift() as () => void
    active += 1
    job()
  }
}

function releaseSlot(): void {
  active = Math.max(0, active - 1)
  pump()
}

export const vLazyMedia = {
  mounted(el: LazyEl, binding: { value?: string | null }): void {
    const src = binding.value
    if (!src) return

    // A video with preload="metadata" may never reach 'loadeddata', so the
    // slot is also freed on 'loadedmetadata'; settle() is idempotent.
    const settleEvents =
      el.tagName === 'VIDEO' ? ['loadedmetadata', 'loadeddata', 'error'] : ['load', 'error']

    let cancelled = false
    let holdsSlot = false
    let observer: IntersectionObserver | null = null
    let timer: ReturnType<typeof setTimeout> | null = null

    function settle(): void {
      if (!holdsSlot) return
      holdsSlot = false
      stopListening()
      releaseSlot()
    }

    function stopListening(): void {
      if (timer !== null) {
        clearTimeout(timer)
        timer = null
      }
      settleEvents.forEach((name) => el.removeEventListener(name, settle))
    }

    const start = () => {
      // pump() has already taken a slot on this job's behalf.
      if (cancelled) {
        releaseSlot()
        return
      }
      holdsSlot = true
      settleEvents.forEach((name) => el.addEventListener(name, settle))
      timer = setTimeout(settle, SLOT_TIMEOUT_MS)
      el.src = src
    }

    observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return
        observer?.disconnect()
        observer = null
        pending.push(start)
        pump()
      },
      { rootMargin: ROOT_MARGIN },
    )
    observer.observe(el)

    el.__lazyMediaCleanup = () => {
      cancelled = true
      observer?.disconnect()
      observer = null
      stopListening()
      if (holdsSlot) {
        holdsSlot = false
        releaseSlot()
      }
    }
  },

  unmounted(el: LazyEl): void {
    el.__lazyMediaCleanup?.()
    delete el.__lazyMediaCleanup
  },
}
