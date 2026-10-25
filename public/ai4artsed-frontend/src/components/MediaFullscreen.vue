<!--
  MediaFullscreen — one medium, large, on a ground of its own.

  Twelve pages had written this layer out by hand, and they had drifted apart
  while doing it: five on 95 % black at 95 % of the window edge, four of the lab
  pages with an 8px blur at 90 %, three more somewhere between, and the fusion
  workbench under a name of its own with a caption under the picture. Every one
  of them could show a PICTURE and nothing else — an `<img>` was written into
  the layer itself, so a sound or a film had no way in even where the page had
  one to give.

  The layer takes the values the majority and the newer pages carry: 95 % black,
  no blur, 95 % of the window edge, a click beside it closes, and now Escape
  too, which only one of the twelve had. What it shows follows `kind`, and the
  three that are not a picture keep their own clicks: a play button that closes
  the layer under the finger is not a play button.

  The medium can have its BACK beside it (`back`): the record of the run that
  made it, drawn by the platform's one card back (`MediaCardBack`), the same
  one a turned card shows. One click, one view, the medium and what made it
  together, on every surface. The
  x2x flow had held its material at full size on a click and shown the back
  only after a 550 ms hold, in a layer of its own; no other surface showed the
  back in the enlarged view at all. With a back the medium steps aside for it;
  under 900 px of window the back stands below the medium instead. Without one
  the layer is the one it always was.
-->
<template>
  <Teleport to="body">
    <Transition name="mfs-fade">
      <!-- A layer that covers the window has to say so: without `dialog` and a
           held focus the Tab key walks through the page UNDER it, where a press
           of Enter sets off something nobody can see. -->
      <div
        v-if="open"
        ref="root"
        class="mfs"
        role="dialog"
        aria-modal="true"
        :aria-label="label || t('mediaOutput.fullscreen')"
        tabindex="-1"
        @mousedown="onDown"
        @mouseup="onUp"
        @keydown.tab="keepFocus"
      >
        <!-- The medium and, beside it, its back. Both boxes are ground: a click
             in the room next to the picture is a click beside it. -->
        <div
          ref="stage"
          class="mfs-stage mfs-ground"
          :class="{ backed: !!back, code: kind === 'code' }"
          :style="back && stageHeight ? { '--mfs-stage-h': stageHeight + 'px' } : undefined"
        >
          <div
            class="mfs-figure mfs-ground"
            :class="{ fill: kind !== 'image' && kind !== 'video', sound: kind === 'audio' }"
          >
            <!-- The picture closes on click, like it always did: there is nothing on
                 it to press, and the whole ground is the way out.

                 `width`/`height` are the picture's own measurements, and where a
                 page knows them the place the picture will take is held before it
                 is there. `poster` is a copy small enough to be already in hand
                 (the strip's plate), painted INTO that place meanwhile. Neither is
                 required: without them this is the element it always was. -->
            <img
              v-if="kind === 'image'"
              :src="src || undefined"
              :alt="alt ?? t('mediaOutput.fullscreen')"
              :style="standIn"
              class="mfs-media mfs-ground"
              @load="arrived = true"
            />
            <video
              v-else-if="kind === 'video'"
              :src="src || undefined"
              class="mfs-media"
              controls
              playsinline
            ></video>
            <!-- A sound does not get bigger. It gets a ground to itself and a player
                 wide enough to seek in, which is what the small one in the box is
                 not. -->
            <audio v-else-if="kind === 'audio'" :src="src || undefined" class="mfs-audio" controls></audio>
            <!-- A sketch is read and run, so the layer hands it to the platform's
                 one sandbox rather than to a picture element. Until its source has
                 arrived nothing is shown: an empty sandbox would offer a run
                 button over nothing. -->
            <div v-else-if="kind === 'code'" class="mfs-code">
              <CodeSandbox v-if="code" :code="code" :kind="codeKind" />
            </div>
            <model-viewer
              v-else
              :src="src || undefined"
              auto-rotate
              camera-controls
              shadow-intensity="1"
              environment-image="neutral"
              interaction-prompt="auto"
              touch-action="pan-y"
              class="mfs-model"
            ></model-viewer>
          </div>

          <aside v-if="back" ref="panel" class="mfs-panel">
            <MediaCardBack
              v-bind="back"
              @toggle-favorite="emit('toggle-favorite')"
              @restore="emit('restore')"
              @forward="emit('forward')"
              @download="emit('download')"
              @print="emit('print')"
            />
          </aside>
        </div>

        <!-- Only where a page has something to say about what is standing there.
             The workbench names its picture and offers it for download; the bar
             is that page's, through the slot, not a second thing to maintain. -->
        <div v-if="label || paints(slots.bar?.())" ref="bar" class="mfs-bar">
          <span v-if="label" class="mfs-label">{{ label }}</span>
          <slot name="bar" />
        </div>

        <button class="mfs-close" :aria-label="t('mediaOutput.close')" @click="close">
          &times;
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<script lang="ts">
/**
 * One key, and the layer on top gets it. Every instance used to hang its own
 * listener on the window without asking whether it was the one being looked at,
 * so a second layer over the first was left by one press of Escape and a click
 * had to be spent on each. The stack is shared by all of them and runs only
 * while at least one layer is open, which is also the whole listener bookkeeping
 * in one place instead of twelve.
 */
const stack: Array<() => void> = []

function onKey(e: KeyboardEvent) {
  const top = stack[stack.length - 1]
  if (e.key === 'Escape' && top) top()
}

function push(fn: () => void) {
  if (stack.includes(fn)) return
  if (!stack.length) window.addEventListener('keydown', onKey)
  stack.push(fn)
}

function pop(fn: () => void) {
  const i = stack.lastIndexOf(fn)
  if (i < 0) return
  stack.splice(i, 1)
  if (!stack.length) window.removeEventListener('keydown', onKey)
}
</script>

<script setup lang="ts">
import {
  Comment,
  Fragment,
  Text,
  computed,
  nextTick,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  ref,
  useSlots,
  watch,
  type VNode,
} from 'vue'
import { useI18n } from 'vue-i18n'
import CodeSandbox from '@/components/CodeSandbox.vue'
import MediaCardBack from '@/components/MediaCardBack.vue'
import type { MediaBack } from '@/components/mediaBack'
import { useAnalysisEventStore } from '@/stores/analysisEvent'

const props = withDefaults(
  defineProps<{
    /**
     * The file to show. Null or empty means the layer is not there at all —
     * except for a sketch, which has no file: its source (`code`) opens the
     * layer instead.
     */
    src?: string | null
    /** What it is. Anything other than the named kinds is shown as a 3D object. */
    kind?: 'image' | 'video' | 'audio' | '3d' | 'code'
    /** The source of a sketch, for `kind: 'code'`. Read from the run by the page. */
    code?: string
    /** Which runtime that source belongs to. */
    codeKind?: 'p5js' | 'tonejs'
    /** A word about what is standing there. Draws the bar under it when set. */
    label?: string
    /** Alternative text for a picture. Defaults to the platform's own word. */
    alt?: string
    /**
     * The picture's own measurements, where the page knows them. Both or
     * neither: the ratio the browser holds the place by comes from the pair.
     */
    width?: number
    height?: number
    /**
     * A small copy of the same picture that the page ALREADY has - the plate of
     * a strip, not something fetched for this. It is painted into the reserved
     * box while the picture travels, and dropped the moment the picture is
     * there, because a picture with transparent parts would otherwise be looked
     * at through its own copy.
     */
    poster?: string
    /**
     * The back of the medium, standing beside it: what the page knows about the
     * run that made it, in the one shape the card back takes (`MediaBack`). The
     * row of actions on it answers through this layer's events. Left out, the
     * medium stands alone.
     */
    back?: MediaBack | null
  }>(),
  {
    src: null,
    kind: 'image',
    label: '',
    alt: undefined,
    code: '',
    codeKind: 'p5js',
    width: 0,
    height: 0,
    poster: '',
    back: null,
  },
)

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'toggle-favorite'): void
  (e: 'restore'): void
  (e: 'forward'): void
  (e: 'download'): void
  (e: 'print'): void
}>()

const { t } = useI18n()
const slots = useSlots()
const root = ref<HTMLElement | null>(null)

const close = () => emit('close')

/** Whether there is anything to stand on the ground. */
const open = computed(() => !!props.src || (props.kind === 'code' && !!props.code))

/**
 * The eye on an action row — on a page's bar (the favourites strip) or on the
 * back beside the medium — hands the picture to the chat figure, and that
 * figure lives UNDER this layer: `#app` is a stacking context of its own (see
 * the z-index note in the styles), so the conversation opened behind the black
 * ground and nothing seemed to happen. The layer steps aside the moment a look
 * is asked for. Synchronous, because the figure consumes the request in its
 * own watcher, and a queued one here would only ever see the emptied slot.
 */
const analysis = useAnalysisEventStore()
watch(
  () => analysis.pendingReflection,
  (pending) => {
    if (pending && open.value) close()
  },
  { flush: 'sync' },
)

/**
 * Whether the picture on screen is the one `src` names. It is not while a new
 * src is travelling, and a layer that stays open through a change of picture
 * (the strip closes and reopens, but a page need not) would otherwise hold the
 * old picture's copy under the new one.
 */
const arrived = ref(false)

/** Measurements are only usable as a PAIR - one alone says nothing about shape. */
const held = computed(() => props.width > 0 && props.height > 0)

/**
 * The room the picture may use: the stage, less the back standing beside it
 * (or, on a narrow window, below it). The stage is what the layer has left
 * after its own padding and its bar, so this is exact rather than an estimate,
 * and it is read once when the layer opens, which is well before any file can
 * have travelled.
 */
const stage = ref<HTMLElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const bar = ref<HTMLElement | null>(null)
const room = ref<{ w: number; h: number } | null>(null)
/**
 * The stage's height in pixels, for the picture beside a back. A percentage
 * would do for a picture standing alone, but beside the back the figure is
 * shrink-wrapped so the pair stands together, and a shrink-wrapped box takes
 * its width from the picture's OWN width before any percentage height has
 * been resolved — a tall picture then claimed the width it would have had at
 * full height and left that room empty between itself and the back. A pixel
 * height is known before the picture is measured, so the width it claims is
 * the width it will have.
 */
const stageHeight = ref(0)

function measure() {
  const el = stage.value
  if (!el) {
    room.value = null
    stageHeight.value = 0
    return
  }
  stageHeight.value = el.clientHeight
  // The held place only where a page hands over measurements. Without them
  // there is no place to hold.
  if (!held.value) {
    room.value = null
    return
  }
  const style = getComputedStyle(el)
  const gap = parseFloat(style.columnGap || '0') || 0
  const aside = panel.value
  const stacked = style.flexDirection === 'column'
  room.value = {
    w: Math.max(0, el.clientWidth - (aside && !stacked ? aside.offsetWidth + gap : 0)),
    h: Math.max(0, el.clientHeight - (aside && stacked ? aside.offsetHeight + gap : 0)),
  }
}

watch(() => props.src, () => {
  arrived.value = false
})

/**
 * Measured again whenever the layer, its bar or its back changes size - the
 * window is turned, the bar takes a second line, the back's rows arrive.
 * Watched rather than read once, because a held place is a promise about a box
 * that anything may still change. Watched only where something is measured
 * at all: a layer showing a film or a sketch on its own would be reading the
 * window and watching it for nothing.
 */
let watching: ResizeObserver | null = null

watch(
  [open, held, () => !!props.back],
  async () => {
    watching?.disconnect()
    watching = null
    await nextTick()
    measure()
    if ((held.value || props.back) && root.value && typeof ResizeObserver !== 'undefined') {
      watching = new ResizeObserver(() => measure())
      watching.observe(root.value)
      if (stage.value) watching.observe(stage.value)
      if (bar.value) watching.observe(bar.value)
      if (panel.value) watching.observe(panel.value)
    }
  },
  { immediate: true },
)

/**
 * The place the picture will take, held before it is there, and the small copy
 * painted into it.
 *
 * The picture takes as much of the room as it fits into and NEVER more than its
 * own size - which is why both measurements are needed and a ratio alone would
 * not do: a picture smaller than the room is not enlarged. The copy is laid in
 * with `contain` into a box that already has the picture's shape, so it fills
 * it exactly; when the picture LANDS, both go and the element sizes itself the
 * way it always did, at the same place. The copy goes then because a picture
 * with transparent parts would otherwise be looked at through it - and only
 * then: a picture that fails to arrive leaves the copy standing, which says
 * more than the browser's broken-image mark on black.
 */
const standIn = computed(() => {
  const style: Record<string, string> = {}
  if (arrived.value) return style
  if (held.value && room.value) {
    const scale = Math.min(1, room.value.w / props.width, room.value.h / props.height)
    style.width = `${props.width * scale}px`
    style.height = `${props.height * scale}px`
  }
  if (props.poster) {
    // The address goes into a CSS value, so the characters that could end that
    // value early are spelled out. Nothing user-written reaches here today -
    // the address is a run id and a moment - and a quoting that rests on that
    // staying true is not a quoting.
    const quoted = props.poster.replace(/["\\\n\r]/g, (c) => encodeURIComponent(c))
    style.backgroundImage = `url("${quoted}")`
    style.backgroundSize = 'contain'
    style.backgroundRepeat = 'no-repeat'
    style.backgroundPosition = 'center'
  }
  return style
})

/**
 * A slot that was handed over but renders nothing still counts as a slot, so
 * `$slots.bar` alone would draw an empty bar with its gap under a page whose
 * bar is conditional. What is asked here is whether anything would be painted.
 */
function paints(nodes: VNode[] | undefined): boolean {
  return !!nodes?.some((n) => {
    if (n.type === Comment) return false
    if (n.type === Fragment) return paints(n.children as VNode[])
    if (n.type === Text) return String(n.children).trim() !== ''
    return true
  })
}

/**
 * The ground closes, the medium does not — except a picture, which has nothing
 * to hold and has closed on click since the first of the twelve layers. It is
 * press AND release that have to land on the ground: a seek bar taken hold of
 * and dragged out over the black releases there, and on a plain click handler
 * that release closed the film somebody was scrubbing through.
 */
let armed = false

function isGround(target: EventTarget | null) {
  const el = target as HTMLElement | null
  return !!el && (el === root.value || el.classList.contains('mfs-ground'))
}
function onDown(e: MouseEvent) {
  armed = e.button === 0 && isGround(e.target)
}
function onUp(e: MouseEvent) {
  const go = armed && isGround(e.target)
  armed = false
  if (go) close()
}

/**
 * Tab stays inside. The close button is the last thing in the body, so without
 * this it sits behind the whole page it is covering.
 */
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), audio[controls], video[controls], model-viewer, iframe, [tabindex]:not([tabindex="-1"])'

function keepFocus(e: KeyboardEvent) {
  const el = root.value
  if (!el) return
  const items = Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE))
  if (!items.length) {
    e.preventDefault()
    el.focus()
    return
  }
  const first = items[0]
  const last = items[items.length - 1]
  if (!first || !last) return
  const active = document.activeElement
  if (e.shiftKey && (active === first || active === el)) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && active === last) {
    e.preventDefault()
    first.focus()
  }
}

/**
 * The 3D branch brings its own element, which two of the twelve pages happened
 * to have loaded from elsewhere and ten did not — there it would have rendered
 * as an empty unknown tag. It weighs a megabyte, so it is fetched when a 3D
 * object is actually asked for and not on every page that shows a picture. The
 * element upgrades itself once the definition arrives, so it may render first.
 */
watch(
  () => props.kind,
  (k) => {
    if (k !== 'image' && k !== 'video' && k !== 'audio' && k !== 'code')
      import('@google/model-viewer')
  },
  { immediate: true },
)

/** Where the focus came from, so it can be put back where the hand left it. */
let returnTo: HTMLElement | null = null

watch(
  open,
  async (isOpen) => {
    if (isOpen) {
      push(close)
      returnTo = document.activeElement as HTMLElement | null
      await nextTick()
      root.value?.focus()
    } else {
      pop(close)
      returnTo?.focus?.()
      returnTo = null
    }
  },
  { immediate: true },
)

// Kept alive, not unmounted: the compare hub holds its two pages in a
// <KeepAlive>, so switching tabs over an open layer neither unmounts this nor
// clears the page's own state — the black ground stayed lying over the other
// tab and answered its Escape.
onDeactivated(() => {
  pop(close)
  if (open.value) close()
})
onActivated(() => {
  if (open.value) push(close)
})
onBeforeUnmount(() => {
  watching?.disconnect()
  pop(close)
})
</script>

<style scoped>
/* Deliberate black, not a surface tone: this is the ground a single thing is
   looked at on, and every one of the twelve layers this replaces used it.
   9999 is what eleven of the twelve carried, and it is not free to raise: the
   platform's own teleported pieces at 10000 — the voice's question, the model
   toast — have to stay above a picture being looked at. The chat figure is not
   a case: #app is position: fixed, so it is a stacking context of its own and
   everything in it stays below anything teleported beside it, whatever number
   it carries. */
.mfs {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.95);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  /* The 95 % is the padding, so the medium can simply take what is left. With a
     bar under it the flex box shortens the medium instead of pushing the bar
     off the screen. */
  padding: 2.5vh 2.5vw;
  box-sizing: border-box;
  cursor: zoom-out;
}
.mfs:focus {
  outline: none;
}
/* The stage is what is left for the medium and its back: the layer less its
   padding and its bar. A row — the medium, then the back — centred as a pair.
   The figure is STRETCHED to the stage's height rather than centred in it,
   because only a stretched flex item has a definite height for the picture's
   percentage to resolve against; the picture is centred inside the figure. */
.mfs-stage {
  flex: 1 1 auto;
  min-height: 0;
  align-self: stretch;
  display: flex;
  align-items: stretch;
  justify-content: center;
  gap: 22px;
  min-width: 0;
}
.mfs-figure {
  /* Shrink-wrapped to the picture, so the back stands right beside it and the
     pair sits centred; what does not have a size of its own (a sound's player,
     a sketch, an object) takes the room instead, see `.fill`. */
  flex: 0 1 auto;
  min-width: 0;
  min-height: 0;
  max-width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.mfs-figure.fill {
  flex: 1 1 0;
}
.mfs-media {
  max-width: 100%;
  max-height: 100%;
  min-height: 0;
  object-fit: contain;
}
/* Beside a back the picture's height is given in pixels (see `stageHeight`),
   so that the shrink-wrapped figure claims no more width than the picture
   will have. Only beside: below a back the figure's height is what the column
   leaves, and a stage-high picture would run over the back. */
@media (min-width: 900px) {
  .mfs-stage.backed:not(.code) .mfs-media {
    max-height: var(--mfs-stage-h, 100%);
  }
  /* Room for the cross: a record as tall as the stage, beside a medium that
     fills the stage's width, stood with its first line under the cross. Only
     a record that long loses the 6rem; the cross box is 3rem from the top. */
  .mfs-stage.backed:not(.code) > .mfs-panel {
    max-height: calc(100% - 6rem);
  }
}
.mfs-media:not(.mfs-ground),
.mfs-audio,
.mfs-model,
.mfs-code,
.mfs-panel,
.mfs-bar {
  cursor: default;
}
/* The back: the platform's card back on its own panel, mid-height beside the
   medium, scrolling where its record is longer than the window. The width is
   the one the x2x flow's inspect layer gave its provenance panel. */
.mfs-panel {
  flex: 0 0 min(360px, 34vw);
  align-self: center;
  max-height: 100%;
  overflow: auto;
  box-sizing: border-box;
  background: rgb(var(--surface-1-rgb) / 0.92);
  border: 1px solid var(--surface-3);
  border-radius: 10px;
}
/* Under 900 px of window there is no room beside the medium; the back stands
   below it instead, and the medium keeps what is left above. The same for a
   sketch at every width (`.code`): its sandbox reads and runs in two columns
   and wants the stage's width for them — beside the back it had 236 px a
   column at 900 px of window, and the sandbox's own breakpoint measures the
   window, not itself. The two blocks say the same thing, because a media
   query cannot stand in a selector list. */
@media (max-width: 899.98px) {
  .mfs-stage.backed {
    flex-direction: column;
    align-items: center;
  }
  .mfs-stage.backed > .mfs-figure {
    flex: 1 1 0;
    align-self: stretch;
  }
  .mfs-stage.backed > .mfs-panel {
    flex: 0 0 auto;
    width: min(100%, 560px);
    max-height: 45%;
  }
  /* A sound's player is one line high; the back takes what is left. */
  .mfs-stage.backed > .mfs-figure.sound {
    flex: 0 0 auto;
  }
  .mfs-stage.backed > .mfs-figure.sound + .mfs-panel {
    flex: 0 1 auto;
    min-height: 0;
    max-height: none;
  }
}
.mfs-stage.backed.code {
  flex-direction: column;
  align-items: center;
}
.mfs-stage.backed.code > .mfs-figure {
  flex: 1 1 0;
  align-self: stretch;
}
.mfs-stage.backed.code > .mfs-panel {
  flex: 0 0 auto;
  width: min(100%, 560px);
  max-height: 30%;
}
/* The sandbox reads and runs side by side and wants the room for it, unlike a
   picture, which takes only what it needs. Because it fills the width, its own
   run button ends up under the layer's cross; the top edge keeps clear of it. */
.mfs-code {
  /* Not the full width: a sandbox that reaches both edges leaves only the
     layer's own padding as ground, and clicking beside it is one of the two
     ways out of here. The other, Escape, cannot be relied on once the hand is
     INSIDE the frame — a sandbox without `allow-same-origin` is an opaque
     document and keeps its keys — so the ground and the cross carry it. */
  width: min(1500px, 92%);
  height: 100%;
  min-height: 0;
  display: flex;
  /* The sandbox's own run button would otherwise sit under the layer's cross. */
  padding-top: 2.6rem;
  box-sizing: border-box;
}
.mfs-code > * {
  flex: 1;
  min-width: 0;
  min-height: 0;
}
.mfs-audio {
  /* What MediaOutputBox gives the player in the page, so the big one is never
     the narrower of the two. */
  width: min(800px, 100%);
  flex: 0 0 auto;
}
.mfs-model {
  width: min(900px, 100%);
  height: min(700px, 100%);
  min-height: 0;
  background-color: transparent;
}
.mfs-bar {
  flex: 0 0 auto;
  /* Stretched, not shrink-wrapped: what a page writes here belongs to the whole
     picture — a name at the left edge, the way to take it home at the right. */
  align-self: stretch;
  display: flex;
  align-items: center;
  gap: 1rem;
  max-width: 100%;
  /* A very long name used to push the medium out of the window entirely. */
  max-height: 40%;
  overflow-y: auto;
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.82rem;
}
.mfs-label {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}
.mfs-close {
  position: absolute;
  /* Outside the medium: the padding of this layer is a percentage, so on a
     narrow window a fixed rem would have put the cross on the picture. */
  top: max(1rem, 2.5vh);
  right: max(1.5rem, 2.5vw);
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  /* Something a finger can hit. */
  padding: 0.5rem;
}
.mfs-close:hover,
.mfs-close:focus-visible {
  color: #fff;
}
.mfs-fade-enter-active,
.mfs-fade-leave-active {
  transition: opacity 0.2s ease;
}
.mfs-fade-enter-from,
.mfs-fade-leave-to {
  opacity: 0;
}
</style>
