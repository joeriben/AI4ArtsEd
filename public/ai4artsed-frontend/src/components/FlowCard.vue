<!--
  FlowCard — the box a flow node throws its output into.

  No parallel structures (docs/ELEMENT_STRUCTURE_REGISTRY.md): static output is
  shown in the flow output boxes, and panel colours and the like are no
  argument for a second box.

  x2x-flow drew this box first: a finished artifact falls out of a node and lands
  on the table as one of these. It is taken out of that page so that a second
  page can put something INTO one, rather than draw a second box that merely
  looks like it. Matching the colours was the wrong answer to the same question —
  what is shared here is the box, not a palette.

  Where the box sits and how big it is stays with the page: x2x-flow places these
  absolutely in world coordinates, the cover band lets them stand in a column and
  grow with their text, the workshop and the contesting surface hang them off
  their own boards. What goes inside is the page's too, through the slot.

  The box comes with sensible backs. A piece of material has two
  faces — what it is, and, by holding it, what made it. That belongs to the box,
  so it comes with it: a page that fills the `back` slot gets the same 450 ms
  hold and the same two faces, instead of printing the provenance under the front
  where it competes with the thing itself. A page that fills no `back` slot has
  no hold at all.

  The flow output model is a template, with no parallel structures in the
  workshop and the contesting surface. So the two parts that had been left
  with the pages came in as well, because leaving them out is what produced
  the copies:

  - the BAR with the grip, and the × in it. Three pages had drawn their own, and
    each drew it differently.
  - the RESIZE CORNER. This one had not merely been copied, it had been written
    per MEDIUM: x2x-flow declared a corner inside its image branch, its text
    branch and its code branch, a fourth one in the video branch with its own
    `bottom: 34px`, and none at all for audio and for a looked-up source — so a
    sound could not be pulled larger anywhere, and on the contesting surface
    nothing could, because that page had never drawn one. A card can be sized
    because it is a card, not because of what happens to lie in it.

  The GESTURES stay with the page — they are the only part that genuinely
  differs, because each surface has its own coordinate system (world coords under
  a pan/zoom board, plain page pixels on the contesting surface). The card emits
  `grip-down`, `resize-down` and `close`; the page decides what they move.

  The bar has TWO slots, and the side decides which one a thing belongs in:
  `bar-lead` stands BEFORE the grip and says what kind of card this is, `bar`
  stands after it and says what is the matter with this one (the surplus mark,
  the failed-upload mark). A type label has to sit where the eye starts, so it
  reads as the card's name rather than as one more state.

  Bar and corner are rendered on BOTH faces on purpose: a card must stay
  movable, sizable and closable while it is showing its back. The frame turns as
  one object either way — that is what makes it read as a card and not as a
  panel whose content was swapped.
-->
<template>
  <div class="asm-item" :class="{ two: !!$slots.back, flipped }">
    <div
      class="face"
      :class="{ 'hold-progress': holdOn }"
      :inert="$slots.back ? flipped : undefined"
      :tabindex="$slots.back ? 0 : undefined"
      :title="holdTitle"
      @pointerdown="startHold"
      @keydown.enter="onFrontKey"
    >
      <div v-if="bar" class="asm-bar" @pointerdown.stop.prevent="emit('grip-down', $event)" @click.stop>
        <slot name="bar-lead" />
        <span class="asm-grip"></span>
        <slot name="bar" />
        <button
          v-if="closable"
          class="asm-del"
          :title="closeTitle"
          @pointerdown.stop
          @click.stop="emit('close')"
        >
          ×
        </button>
      </div>
      <div class="asm-body" :class="{ scrolls: scroll }"><slot /></div>
      <span
        v-if="resizable"
        class="asm-resize"
        :title="resizeTitle"
        @pointerdown.stop.prevent="emit('resize-down', $event)"
        @click.stop
      ></span>
    </div>

    <div
      v-if="$slots.back"
      class="face back"
      :inert="!flipped"
      tabindex="0"
      role="button"
      @click="turnToFront"
      @keydown.enter="onBackKey"
      @keydown.space="onBackKey"
    >
      <div v-if="bar" class="asm-bar" @pointerdown.stop.prevent="emit('grip-down', $event)" @click.stop>
        <span class="asm-grip"></span>
        <button
          v-if="closable"
          class="asm-del"
          :title="closeTitle"
          @pointerdown.stop
          @click.stop="emit('close')"
        >
          ×
        </button>
      </div>
      <!-- The back is told whether it is being looked at: what stands on it may
           have something to fetch (the AI marking, read out of the file), and a
           back that is rendered face down under every card of a grid must not
           ask for it until it is turned up. -->
      <div class="asm-body scrolls"><slot name="back" :flipped="flipped" /></div>
      <span
        v-if="resizable"
        class="asm-resize"
        :title="resizeTitle"
        @pointerdown.stop.prevent="emit('resize-down', $event)"
        @click.stop
      ></span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, useSlots } from 'vue'
import { useHold } from '@/composables/useHold'

defineProps<{
  /** Hover text on the front. The gesture is invisible without one. */
  holdTitle?: string
  /** The head bar with the grip. Off by default — a card in a column has no place to be dragged to. */
  bar?: boolean
  /** The × in the bar. */
  closable?: boolean
  closeTitle?: string
  /** The corner that sizes the card. Independent of what lies in it. */
  resizable?: boolean
  resizeTitle?: string
  /** Let the front scroll when its content is taller than the card. The back always does. */
  scroll?: boolean
}>()

const emit = defineEmits<{
  (e: 'grip-down', ev: PointerEvent): void
  (e: 'resize-down', ev: PointerEvent): void
  (e: 'close'): void
}>()

const slots = useSlots()

/**
 * The back comes by HOLDING — the platform's one hold, `useHold`, at its one
 * duration, since 2026-09-22 (it ran here at 550 ms of its own). A click is
 * left alone: on this face it may be a play button, a link or a word being
 * selected, and none of those may turn the card over. A pointer that travels
 * more than 8px is scrolling or scrubbing, so it cancels — the same threshold,
 * for the same reason.
 *
 * Everything around the timer stays the card's own: which targets keep the
 * finger, the second pointer, the drag that eats pointermove, and the click
 * the release produces. The composable holds the moment and how far it has
 * got; the face draws that as the ring.
 */
const flipped = ref(false)
const hold = useHold(() => {
  release?.()
  flipped.value = true
  swallowNextClick()
})
const { holding: holdOn } = hold
/** The listeners of the hold in progress, so the card can leave during one. */
let release: (() => void) | null = null

/**
 * Where a hold must not begin. Everything in here is something a finger rests
 * on for its own reason: a play button held down, a seek bar dragged slowly, a
 * word being selected. The card turning over under that finger takes the
 * control away from it mid-gesture, because the face it is on stops taking
 * pointers the moment the card is turned. The bar and the corner are in the
 * list for the same reason from the other side: they carry gestures of their
 * own, and a slow drag must not also turn the card.
 */
const KEEPS_THE_FINGER =
  'audio, video, button, a, input, textarea, select, [contenteditable], .asm-bar, .asm-resize'

/**
 * Where a HOLD must not begin, which is nearly the same list and misses the
 * two players. A long press is no transport gesture of sound or film. Play,
 * pause and the seek bar answer to a CLICK, and a scrub travels further than
 * the 8px that call the hold off — so both keep working while a finger resting
 * on the picture of a film still turns the card. Without this split a sound or
 * video card whose player covers its face had no way to the back at all, and
 * the keeping and the saving live there.
 */
const KEEPS_THE_HOLD =
  'button, a, input, textarea, select, [contenteditable], .asm-bar, .asm-resize'

/**
 * The turn is the FACE's key, not its content's. `@keydown.enter.prevent` calls
 * preventDefault before the handler decides anything, so once every card had a
 * face wrapped round it, a line break typed into a card was swallowed by a card
 * that has no back side at all.
 */
function onFrontKey(e: KeyboardEvent) {
  if (e.target !== e.currentTarget || !slots.back) return
  e.preventDefault()
  flipped.value = true
}
function onBackKey(e: KeyboardEvent) {
  if (e.target !== e.currentTarget) return
  e.preventDefault()
  flipped.value = false
}

/**
 * A click anywhere on the back turns it face up again — except when it lands at
 * the end of a selection. The prompt is on this side, and a card that snaps
 * shut the moment the pointer is released is a card the prompt cannot be copied
 * out of.
 */
function turnToFront(e: MouseEvent) {
  if (window.getSelection()?.toString()) return
  // And not when the click had something of its own to do. The model panel on
  // this side opens by its own button, and that button lies on the ground that
  // turns the card: pressing it turned the card over instead of opening it.
  if ((e.target as HTMLElement | null)?.closest(KEEPS_THE_FINGER)) return
  flipped.value = false
}

function startHold(e: PointerEvent) {
  if (!slots.back) return
  // One primary pointer, left button. Two fingers used to arm two holds over a
  // single `timer` slot: whichever ended first cleared the surviving id, the
  // orphan ran, and a pinch-zoom or a resting thumb turned the card over.
  if (e.button !== 0 || !e.isPrimary || hold.holding.value) return
  // A right press opens the context menu, which eats the pointerup that would
  // have called this off — and the card turned over behind the open menu.
  if ((e.target as HTMLElement | null)?.closest(KEEPS_THE_HOLD)) return
  const x0 = e.clientX
  const y0 = e.clientY
  const stop = () => {
    hold.cancel()
    release = null
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', stop)
    window.removeEventListener('pointercancel', stop)
    window.removeEventListener('contextmenu', stop)
    window.removeEventListener('dragstart', stop)
  }
  const onMove = (ev: PointerEvent) => {
    if (Math.hypot(ev.clientX - x0, ev.clientY - y0) > 8) stop()
  }
  release = stop
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', stop)
  window.addEventListener('pointercancel', stop)
  window.addEventListener('contextmenu', stop)
  // A card that can be CARRIED away turns the 8px rule off: once the browser
  // takes the press for a drag, it stops sending pointermove, so the hold runs
  // out behind the drag and the card turns over while it is being carried.
  window.addEventListener('dragstart', stop)
  hold.start()
}

/**
 * The release that ends a hold still produces a click, and the front of a media
 * card is one big click target — x2x-flow kept a `backFired` flag for exactly
 * this. Without it, letting go of a held image opened the full-size overlay on
 * the way to the back side, and the click that landed on the back turned the
 * card straight over again. Capture, so it is over before anything sees it.
 */
let swallow: (() => void) | null = null
function swallowNextClick() {
  swallow?.()
  const drop = () => {
    window.removeEventListener('click', eat, true)
    window.clearTimeout(guard)
    swallow = null
  }
  const eat = (ev: MouseEvent) => {
    ev.stopPropagation()
    ev.preventDefault()
    drop()
  }
  // A pointer that leaves the element before it is released produces no click
  // at all; without this the swallow would sit and wait for an unrelated one.
  const guard = window.setTimeout(drop, 700)
  swallow = drop
  window.addEventListener('click', eat, true)
}

// A card can be taken off the page mid-hold — one finger on it, the other
// pressing the button that clears the column.
onBeforeUnmount(() => {
  release?.()
  swallow?.()
})

defineExpose({ flipped })
</script>

<style scoped>
/* No position and no size: both are the page's. A page that places these
   absolutely says so itself — see .asm-item in x2x_flow. */
.asm-item {
  box-sizing: border-box;
  background: #151320;
  border: 1px solid #2a2540;
  border-radius: 10px;
  overflow: hidden;
}
/* A card with two sides turns as one object, frame included — the border has to
   go round with it or the content merely squashes inside a box that stands
   still. The perspective sits in the transform itself because the element above
   this one belongs to the page and may not be given one. `overflow` has to go:
   on the element that carries preserve-3d it flattens the turn.
   Both faces share one grid cell, so the card is the same size on both sides,
   the way a card is, and nothing has to be measured. */
.asm-item.two {
  display: grid;
  overflow: visible;
  transform-style: preserve-3d;
  transform: perspective(1100px) rotateY(0deg);
  transition: transform 0.34s ease;
}
.asm-item.two.flipped { transform: perspective(1100px) rotateY(180deg); }
.asm-item.two > .face {
  grid-area: 1 / 1;
  min-width: 0;
  outline-offset: -3px;
}
/* Only the BACK suppresses its backface, and only because it stays visible
   through the first half of the turn while still facing away (without this its
   text would show mirrored). The FRONT deliberately does NOT: it is the face
   the generated media lands on, and backface-visibility promoted it to its own
   compositing layer that never got invalidated when the image arrived — the
   card then only revealed its output after a flip forced a repaint. Turned
   away, the front is hidden outright instead, one line below. */
.asm-item.two > .face.back {
  transform: rotateY(180deg);
  cursor: pointer;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
}
/* Halfway through the turn, and not before: `visibility` knows no transition,
   so it switched at the first frame — the card went blank for the whole first
   half of the way over, and on the way back the front stood in it mirrored.
   Delayed by half the 0.34s, each face changes exactly at the edge, where it is
   turned away anyway and nothing can be seen of it either way. */
.asm-item.two > .face { transition: visibility 0s linear 0.17s; }
/* The face turned away, hidden by visibility rather than by its backface:
   absolutely positioned descendants (the action bar over a picture) can get a
   compositing layer of their own and bleed through a suppressed backface in
   some engines. visibility cascades unconditionally, so nothing leaks. `inert`
   next to it takes the same face out of the tab order. */
.asm-item.two.flipped > .face:not(.back),
.asm-item.two:not(.flipped) > .face.back {
  visibility: hidden;
}

/* The face carries the card's three parts in order: the bar it is picked up
   by, the body, and the corner it is sized by. A single-faced card has exactly
   the same three — that is the point of them living here. */
.face {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  position: relative;
  border-radius: inherit;
  overflow: hidden;
}
.asm-body { flex: 1 1 auto; min-height: 0; min-width: 0; }
.asm-body.scrolls { overflow: auto; }

/* The bar, the grip and the × — one drawing of them for the whole platform.
   Values are x2x-flow's, unchanged, because that is the card everything else
   is being brought onto. */
.asm-bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  height: 18px;
  padding: 0 4px 0 8px;
  background: #1c1830;
  cursor: grab;
  touch-action: none;
}
.asm-bar:active { cursor: grabbing; }
.asm-grip {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: repeating-linear-gradient(90deg, #3a3455 0 3px, transparent 3px 6px);
  margin-right: 6px;
}
.asm-del {
  flex: 0 0 auto;
  background: transparent;
  border: none;
  color: #6f6a8a;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  padding: 0 3px;
}
.asm-del:hover { color: #e9e6fb; }

/* The corner. One per card, never per medium — see the note at the top. */
.asm-resize {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 16px;
  height: 16px;
  cursor: nwse-resize;
  touch-action: none;
  background: linear-gradient(135deg, transparent 50%, #4a4270 50%);
}
.asm-resize:hover { background: linear-gradient(135deg, transparent 50%, #7f77dd 50%); }
/* A <video> keeps its controls at the bottom of itself, with the full-size
   button at the right end — exactly where the corner sits, so a card with a
   video in it lifts the corner clear of the bar. x2x-flow did this per medium
   (`.asm-resize.video`); the card now does it by what is inside it. */
.face:has(video) .asm-resize { bottom: 34px; }
</style>
