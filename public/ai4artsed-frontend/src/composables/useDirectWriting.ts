import { onMounted, onUnmounted, type Ref } from 'vue'

/**
 * DIRECT WRITING — the keyboard is a talking surface's default way in.
 *
 * WHAT THIS IS
 *   Type anywhere on the surface and the letters land in the open line. No
 *   click first, no field to go and find, and no field to look at: writing is
 *   what these surfaces are for, so it needs no gesture and no furniture of its
 *   own. Where the line STANDS is not decided here — the open line is the
 *   human's line of the exchange and stands in the exchange (see
 *   components/ResonaVoice.vue).
 *
 * WHO USES IT
 *   Every surface that talks — the workshop (views/resona.vue) and contesting
 *   (views/ai_persona.vue). One behaviour, one place, so the two surfaces do not
 *   drift apart in how they take a keystroke.
 */
/**
 * The open line WRAPS. It is a text area with no frame, no scrollbar and no
 * resize grip, which means it has no height of its own — this gives it one,
 * the height of what stands in it. Called after every change to the line, not
 * only after a keystroke: a line cleared on send has to come back to one row.
 */
export function growWriteLine(el: HTMLTextAreaElement | null | undefined): void {
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

export interface DirectWritingOptions {
  /** The open line's own model. Typed characters are appended to it. */
  text: Ref<string>
  /** Put the caret in the open line. */
  focus: () => void
  /** True while the surface is not writing — a camera, a fullscreen image. */
  paused?: () => boolean
}

/** A field, a text area or anything contenteditable already has the caret. */
export function isWritingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || !!el.isContentEditable
}

export function useDirectWriting(opts: DirectWritingOptions) {
  function onKeydown(e: KeyboardEvent) {
    // Shortcuts stay shortcuts, a field that already has the caret keeps it,
    // and a surface with a camera or a fullscreen image up is not writing.
    if (e.metaKey || e.ctrlKey || e.altKey) return
    if (isWritingTarget(e.target)) return
    if (opts.paused?.()) return
    // One printable character. Arrows, Escape, F-keys and the like are not text.
    if (e.key.length !== 1) return
    e.preventDefault()
    opts.text.value += e.key
    opts.focus()
  }

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onUnmounted(() => window.removeEventListener('keydown', onKeydown))
}
