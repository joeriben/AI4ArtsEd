<!--
  FigureMask — the one sign for an agent presence on this platform.

  Theatre masks (Material Symbols `theater_comedy`, 24dp): comedy and tragedy in
  a single glyph. Wherever the platform shows that something is present, waiting,
  speaking or holding back, it shows THIS shape — the places differ, the sign
  does not.

  Colour is not a prop. The root sets `color: var(--figure-tint, …)` and the
  glyph takes it through `currentColor`, so a page can tint its own figure by
  setting `--figure-tint` on its root (see assets/base.css, where the pigment
  is named). Blueprint is the default, because a page that names no situation
  of its own is one where the figure is help.

  The tint stops here: it carries on the mask and the mask's own outline, and on
  nothing else. No surface, panel, background or page border takes it.

  The states are told apart by the KIND of motion they show, not by motion
  against stillness. `idle` carries a micro-movement of its own — the drift the
  Träshy figure had, taken over unchanged. The two working states each move
  differently: a size pulse while something is being computed, brackets running
  outward while something is sounding. `held` is the one that stands still, and
  it is brighter instead — a pulse would say "wait", and that state says the
  opposite: it is made, and nothing more comes until a human touches it.

  The centre never wanders, with the one exception the idle state names: every
  transform here is centre-preserving — scale about the middle — except the idle
  micro-movement, which is allowed its couple of pixels of drift. PlatformVoice
  draws its threads from the centre of the origin element's bounding rect
  (drawThread), so a transform that moved the centre would move where every
  thread starts.
-->
<template>
  <component
    :is="interactive ? 'button' : 'span'"
    class="figure-mask"
    :class="[`is-${state}`, { 'is-interactive': interactive }]"
    :type="interactive ? 'button' : undefined"
    :role="!interactive && label ? 'img' : undefined"
    :aria-label="label || undefined"
    :aria-hidden="!label && !interactive ? 'true' : undefined"
    :style="{ width: `${size}px`, height: `${size}px` }"
    @click="emit('click', $event)"
  >
    <!--
      The viewport is SQUARE (size x size) and the mask fills it exactly, as it
      would under the plain Material Symbols viewBox: `slice` scales the viewBox
      to COVER the square, and because the viewBox is wider than it is tall that
      scale is size/960 — the vertical fit. `xMidYMid` puts the viewBox centre
      (480, -480), which is the mask's centre, at the centre of the square.

      The viewBox is extended horizontally to hold the speaker brackets. What
      lets them PAINT outside the square is `overflow: visible` in the stylesheet
      below; the extension gives them coordinates, not visibility. Keeping the
      layout box square is what keeps the centre exact and stops the box from
      changing width when the figure starts speaking.

      These two numbers — 1900 wide, 960 tall — are what
      FIGURE_MASK_OVERHANG_RATIO is computed from. Change the viewBox and the
      exported overhang follows; change it in only one of the two places and
      every consumer placing a figure near an edge is silently wrong.
    -->
    <svg
      :width="size"
      :height="size"
      :style="{ width: `${size}px`, height: `${size}px` }"
      viewBox="-470 -960 1900 960"
      preserveAspectRatio="xMidYMid slice"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <!--
        Speaker brackets: three each side, rising in size outward, so the whole
        reads ((( MASK ))). Arcs of circles around the mask's own centre, drawn
        in `currentColor` like the glyph. Ranks are paired left/right so both
        sides light together.
      -->
      <g
        class="figure-arcs"
        fill="none"
        stroke="currentColor"
        stroke-width="60"
        stroke-linecap="round"
      >
        <path class="figure-arc figure-arc-1" d="M -91.6 -810 A 660 660 0 0 0 -91.6 -150" />
        <path class="figure-arc figure-arc-1" d="M 1051.6 -810 A 660 660 0 0 1 1051.6 -150" />
        <path class="figure-arc figure-arc-2" d="M -204.2 -875 A 790 790 0 0 0 -204.2 -85" />
        <path class="figure-arc figure-arc-2" d="M 1164.2 -875 A 790 790 0 0 1 1164.2 -85" />
        <path class="figure-arc figure-arc-3" d="M -316.7 -940 A 920 920 0 0 0 -316.7 -20" />
        <path class="figure-arc figure-arc-3" d="M 1276.7 -940 A 920 920 0 0 1 1276.7 -20" />
      </g>

      <!-- Material Symbols `theater_comedy`, 24dp, unchanged. -->
      <path
        d="M760-660q17 0 28.5-11.5T800-700q0-17-11.5-28.5T760-740q-17 0-28.5 11.5T720-700q0 17 11.5 28.5T760-660Zm-160 0q17 0 28.5-11.5T640-700q0-17-11.5-28.5T600-740q-17 0-28.5 11.5T560-700q0 17 11.5 28.5T600-660Zm-20 136h200q0-35-30.5-55.5T680-600q-39 0-69.5 20.5T580-524ZM110-150q-70-70-70-170v-280h480v280q0 100-70 170T280-80q-100 0-170-70Zm283-57q47-47 47-113v-200H120v200q0 66 47 113t113 47q66 0 113-47Zm287-153q-26 0-51.5-5.5T580-382v-94q22 17 47.5 26.5T680-440q66 0 113-47t47-113v-200H520v140h-80v-220h480v280q0 100-70 170t-170 70Zm-480-20q17 0 28.5-11.5T240-420q0-17-11.5-28.5T200-460q-17 0-28.5 11.5T160-420q0 17 11.5 28.5T200-380Zm188.5-11.5Q400-403 400-420t-11.5-28.5Q377-460 360-460t-28.5 11.5Q320-437 320-420t11.5 28.5Q343-380 360-380t28.5-11.5Zm-39 127Q380-285 380-320H180q0 35 30.5 55.5T280-244q39 0 69.5-20.5ZM280-340Zm400-280Z"
      />
    </svg>
  </component>
</template>

<script lang="ts">
/**
 * How far the WIDEST state paints beyond the square layout box, per side, as a
 * fraction of `size`. The box is always `size × size`, but an uttering figure's
 * outermost bracket reaches the edge of the extended viewBox, so its painted
 * width is `size × 1.979` — centred, hence this much sticking out each side.
 *
 * Derived from the viewBox, not measured: the box is 960 units tall and 1900
 * wide around the same centre, so (1900 − 960) / 2 / 960 of a side is overhang.
 * Anyone placing a figure near a screen edge has to add this, or the brackets
 * are cut off the moment it speaks — the layout box gives no warning, because
 * the box itself is never clipped.
 */
export const FIGURE_MASK_OVERHANG_RATIO = (1900 - 960) / 2 / 960
</script>

<script setup lang="ts">
/**
 * What the figure is doing, as the platform already names it elsewhere
 * (SpeakButton uses the same four distinctions for the same act).
 *
 * - `idle`     nothing is running; the figure is simply present
 * - `waiting`  inference is running
 * - `uttering` speech is sounding
 * - `held`     speech is synthesized and waits for a tap before it can sound
 */
export type FigureState = 'idle' | 'waiting' | 'uttering' | 'held'

withDefaults(
  defineProps<{
    /** Edge length of the square layout box, in px. The mask fills it. */
    size?: number
    state?: FigureState
    /** Accessible name. An interactive figure needs one. Left empty on a
     *  non-interactive figure, it is decoration and is hidden from assistive
     *  technology, the way the image it replaces was. */
    label?: string
    /** Whether the figure takes the pointer itself. False where a consumer
     *  already wraps it in its own button. */
    interactive?: boolean
  }>(),
  {
    size: 48,
    state: 'idle',
    label: '',
    interactive: true,
  },
)

const emit = defineEmits<{ click: [event: MouseEvent] }>()
</script>

<style scoped>
.figure-mask {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  padding: 0;
  border: none;
  background: none;
  line-height: 0;
  /* The one place the colour is decided. The glyph, the brackets and the focus
     outline follow through currentColor; nothing here paints a surface with it.
     A page tints its figure by setting --figure-tint on its own root; without
     one the figure is help, and takes help's pigment. The literal is the last
     resort for a document that somehow never loaded assets/base.css. */
  color: var(--figure-tint, var(--figure-tint-blueprint, #5c8cb0));
}

.figure-mask.is-interactive {
  cursor: pointer;
}

.figure-mask:not(.is-interactive) {
  pointer-events: none;
}

.figure-mask:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: 3px;
  border-radius: 4px;
}

.figure-mask svg {
  display: block;
  /* Lets the speaker brackets paint outside the square layout box. Without it
     the arcs are clipped to the box and only their innermost sliver shows. */
  overflow: visible;
}

/* ---------- idle ----------
   Micro-movement, taken over from the Träshy figure this replaces: the same 4s
   ease-in-out drift of a couple of pixels and a degree of tilt, keyframe for
   keyframe. This is the ONE transform here that moves the centre, and it is
   meant to. */
.figure-mask.is-idle {
  opacity: 0.82;
  animation: figure-idle 4s ease-in-out infinite;
}

@keyframes figure-idle {
  0%,
  100% {
    transform: translate(0, 0) rotate(0deg);
  }
  25% {
    transform: translate(2px, -3px) rotate(1deg);
  }
  50% {
    transform: translate(-1px, -5px) rotate(-0.5deg);
  }
  75% {
    transform: translate(-2px, -2px) rotate(0.5deg);
  }
}

/* ---------- waiting ----------
   Inference is running: a slow breath, and size is the whole of it. Scale about
   the centre, the same 0.94–1.06 magnitude the platform's other figures breathe
   at. Nothing else changes — not the brightness, not the position. */
.figure-mask.is-waiting {
  animation: figure-waiting 2.4s ease-in-out infinite;
}

@keyframes figure-waiting {
  0%,
  100% {
    transform: scale(0.94);
  }
  50% {
    transform: scale(1.06);
  }
}

/* ---------- uttering ----------
   Speech is sounding. The mask itself stands still and full — what moves are
   the brackets, dark to bright and travelling OUTWARD: the innermost lights
   first, then the middle, then the outermost, over and over. The motion sits
   where the sounding is, not on the face. */
.figure-mask.is-uttering {
  opacity: 1;
}

.figure-arc {
  opacity: 0;
}

.figure-mask.is-uttering .figure-arc {
  animation: figure-arc-run 1.5s ease-in-out infinite;
}

.figure-mask.is-uttering .figure-arc-2 {
  animation-delay: 0.17s;
}

.figure-mask.is-uttering .figure-arc-3 {
  animation-delay: 0.34s;
}

@keyframes figure-arc-run {
  0% {
    opacity: 0.1;
  }
  18% {
    opacity: 1;
  }
  55%,
  100% {
    opacity: 0.1;
  }
}

/* ---------- held ----------
   Synthesized speech that cannot sound until somebody taps it. Still like idle
   and told apart from it by brightness alone: a pulse would mean "wait", and
   this state means the opposite — it is made, and nothing more comes until a
   human touches it. The same distinction SpeakButton makes between its waiting
   and blocked states, for the same reason. */
.figure-mask.is-held {
  opacity: 1;
  filter: brightness(1.25);
}

@media (prefers-reduced-motion: reduce) {
  /* All motion goes, the idle drift included. Brightness alone then carries the
     four states apart, which is why they sit at four clearly different levels
     here. `held` is already still and needs nothing switched off. */
  .figure-mask.is-idle,
  .figure-mask.is-waiting,
  .figure-mask.is-uttering .figure-arc {
    animation: none;
  }

  .figure-mask.is-idle {
    opacity: 0.75;
  }

  .figure-mask.is-waiting {
    opacity: 0.92;
  }

  .figure-mask.is-uttering .figure-arc {
    opacity: 0.55;
  }
}
</style>
