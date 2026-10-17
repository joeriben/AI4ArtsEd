<!--
  FlowRunButton - the trigger inside a band's op node.

  The triangle that starts a run once stood copied by hand FIVE times:
  `.ef-go` (Encoder Fusion), `.da-go` (Denoising Archaeology), `.ba-go` (Bias
  Archaeology 1), `.ct-go` (Bias Archaeology 2) and one in
  `views/x2x_flow.vue`. Four of them were the same character for character - the
  same path, the same six CSS lines, only the class name told them apart. This
  component is those four (docs/ELEMENT_STRUCTURE_REGISTRY.md).

  The fifth stays out, and it is not a parallel structure: in the flow the
  triangle is not the button, the NODE is - it carries hold-to-stop, opens into
  the run panel, and shows the triangle in only one of its phases. What the two
  do share is the drawing of the triangle itself, and that now stands ONCE, in
  `assets/flow-stage.css` (`.play`), where its size step `--flow-play` already
  came from.

  `ready` is ONE state, not two: ready means clickable. The four callers wrote
  it twice (`:class="{ready: canRun}"` and `:disabled="!canRun"`) and always fed
  both from the same condition.

  `number` (2026-09-27) cuts a figure out of the triangle, for a surface that
  starts two runs in order from the bar (components/ShellRun.vue, `steps`). The
  figure is a hole, so it shows whatever the bar stands on in every tone. It sits
  near the triangle's incentre, where a figure at font size 8 (of the 24-unit
  box) keeps about a unit from the two slanted edges.

  `label` is the same trigger where it stands IN the surface rather than in
  the bar: the triangle, and beside it the word for what this press makes. It
  exists because Voices cannot use the bar - three synthesisers, three runs,
  each started for itself - and the quiet bordered button it carried instead
  was not recognisable as a start action. Rather than a fourth trigger shape
  on the platform, the
  canonical one takes a word: same triangle, same run colour, same three
  states, so a press that starts something looks the same wherever it stands.
-->
<template>
  <button
    class="fl-run"
    :class="{ ready, running, labelled: !!label }"
    :disabled="!ready"
    :title="title"
    @click="$emit('click')"
  >
    <svg class="play" viewBox="0 0 24 24" aria-hidden="true">
      <template v-if="number !== undefined">
        <mask :id="maskId">
          <rect width="24" height="24" fill="#fff" />
          <text class="play-number" x="11.5" y="12" dy="0.36em" text-anchor="middle" font-size="8" fill="#000">{{ number }}</text>
        </mask>
        <path d="M8 5.5 19 12 8 18.5Z" fill="currentColor" :mask="`url(#${maskId})`" />
      </template>
      <path v-else d="M8 5.5 19 12 8 18.5Z" fill="currentColor" />
    </svg>
    <span v-if="label" class="fl-run-label">{{ label }}</span>
  </button>
</template>

<script setup lang="ts">
import { useId } from 'vue'

withDefaults(
  defineProps<{
    /** Ready to run: bright, clickable, lifts on hover. */
    ready?: boolean
    /** What the hover text says; without it the button carries none. */
    title?: string
    /**
     * A run is under way. The triangle keeps breathing while it lasts.
     *
     * It is here because the band that used to say this is gone from two
     * surfaces (Denoising Archaeology, Canvas): its middle node pulsed while a
     * run was out, and without a sign the only trigger on the page would sit
     * dimmed and silent for a minute and a half. `ready` is false during a run,
     * so this rides ON TOP of the disabled dimming and must outrank it.
     */
    running?: boolean
    /**
     * The word for what this press makes, beside the triangle. For a trigger
     * that stands IN a surface, where nothing around it says what it starts -
     * in the bar the triangle is alone and needs no word, because there is
     * only one thing to start there.
     */
    label?: string
    /** The figure cut into the triangle: which of several runs this one is. */
    number?: number
  }>(),
  { ready: false, title: undefined, running: false, label: undefined, number: undefined },
)

// One id per button: two numbered triangles in the same document must not
// point at each other's mask.
const maskId = `fl-run-n-${useId()}`

defineEmits<{ (e: 'click'): void }>()
</script>

<style scoped>
.fl-run { background: none; border: 0; padding: 0; display: flex; cursor: pointer; }
.play-number { font-family: inherit; font-weight: 700; }
.fl-run:disabled { cursor: default; }
.fl-run.ready:hover .play { opacity: 1; }
.fl-run:disabled .play { opacity: 0.18; }
/* AFTER the disabled rule on purpose: same specificity, so source order decides
   which opacity the triangle rests at while a run is out. */
.fl-run.running .play { opacity: 0.9; animation: fl-run-pulse 1.2s ease-in-out infinite; }
@keyframes fl-run-pulse { 0%, 100% { opacity: 0.9; } 50% { opacity: 0.28; } }
@media (prefers-reduced-motion: reduce) {
  .fl-run.running .play { animation: none; opacity: 0.6; }
}

/* With a word beside it the trigger needs a body, because it no longer stands
   alone in an empty bar but under a stack of settings. A thin line on an
   almost-transparent ground was what it had first, and at that weight it
   merged with the background - so it is filled and
   drawn round: a ground the eye reads as a surface, and a line at nearly full
   strength around it. The triangle drops to the label's own size: at
   `--flow-play` it is up to 3.25 rem and would be the loudest mark in the
   column.

   `--fl-run-tone-rgb` / `--fl-run-tone-lit` let a surface give the trigger the
   colour of what it starts - Voices gives each machine's column its own, so
   the column, its name and its trigger are one thing to the eye. Unset, the
   RUN colour stands, which nothing else on these surfaces wears: the chips are
   green where chosen and amber where they carry the other side of a
   distinction, so a press that starts something is never read as one more
   thing to tick. */
.fl-run.labelled {
  --flow-play: 1.05rem;
  --fl-run-tone-rgb: 127 178 255;
  --fl-run-tone-lit: #7fb2ff;
  width: 100%;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid rgb(var(--fl-run-tone-rgb) / 0.8);
  border-radius: 6px;
  background: rgb(var(--fl-run-tone-rgb) / 0.18);
}

.fl-run.labelled .fl-run-label {
  font-family: inherit;
  font-size: var(--flow-fs-sub);
  font-weight: 400;
  color: var(--fl-run-tone-lit);
}

.fl-run.labelled .play { opacity: 1; color: var(--fl-run-tone-lit); }
.fl-run.labelled.ready:hover { background: rgb(var(--fl-run-tone-rgb) / 0.32); }

/* Nothing to run: the body goes and the outline stays, so the trigger keeps
   its place in the column without claiming to be pressable. */
.fl-run.labelled:disabled { background: none; border-color: rgba(255, 255, 255, 0.12); }
.fl-run.labelled:disabled .play { opacity: 0.25; }
.fl-run.labelled:disabled .fl-run-label { color: rgba(255, 255, 255, 0.3); }

/* A run IS out, and `ready` is false while it lasts - so this stands after the
   disabled rules and takes the body back. A machine at work should be the
   liveliest thing in its column, not the faintest. */
.fl-run.labelled.running {
  border-color: rgb(var(--fl-run-tone-rgb) / 0.8);
  background: rgb(var(--fl-run-tone-rgb) / 0.18);
}

.fl-run.labelled.running .fl-run-label { color: var(--fl-run-tone-lit); }
</style>
