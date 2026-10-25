<!--
  MediaGridCell — ONE generated medium standing as a cell of a grid or a row.

  The tiles once were not media output boxes: no functions, no back, no header
  line with meta-information. The binding template for such uses is
  MediaOutputBox in sparse form, taken over from Flow with all functions but no
  mini-window handle; a long click inherits from the Flow MediaOutputBox a back
  with information and functions.

  So this is the flow's card, not a likeness of it. Nothing here is a second
  implementation of anything:

  - the two faces and the 550 ms hold that turns them are `FlowCard`'s, and they
    already come apart from the window chrome there: `bar`, `closable` and
    `resizable` are its own opt-ins and stay off here. A cell is a cell — it is
    not picked up, not closed, not dragged bigger, and it has no place on a
    board to be moved to.
  - the front is `MediaCardFront`, which is `MediaOutputBox frame="card"`: no
    frame of its own (the cell is the frame), no header line of metadata, and
    no row of buttons either — the medium alone.
  - the back is `MediaCardBack`: every function the box carries in the flow —
    keep, hand on, save, print, have it looked at, not a selection of them — and
    under them prompt, the facts of the surface (a seed, a setting), the model's
    sheet, config and time. The functions stand on the back, in the flow too.

  What it takes over from `.lab-shot`, the cell it replaces (registry, 2026-08-23
  — superseded by this): the SQUARE, the picture shown WHOLE rather than cropped
  and standing in the MIDDLE of it, and a refusal standing IN the cell rather
  than as a line over the surface, so the other cells of a run are unaffected and
  stay readable.

  The SIZE stays the page's, as it was there, and a page with a RASTER says it by
  standing the cell in the platform's square surface (`.instr-frame` /
  `.instr-stack`, assets/instrument-surface.css): the frame measures its own area
  and the stack takes the SMALLER of its two sides, so the cell is a square in a
  narrow column just as it is in a wide one. A surface that grows a ROW per press
  lets the column give the width instead — its height is not bounded, so there is
  no smaller side to take.

  What does NOT work on a raster that must show a fixed number of rows at once —
  and once stood here — is letting the row give the height and deriving the
  width from `aspect-ratio` with a `max-width` back to the column. That holds
  only while every column is wider than a row is tall. At seven columns on
  1900x1100 the cells stood 250 x 355 and the picture hung at the top of a tall
  plate.

  A cell can also show a run WHILE it happens (`isExecuting`, for the
  comparison surfaces): the card stands with the bar, the model's name
  and the picture as it forms — `MediaOutputBox frame="card"` has drawn that
  since it was built. A surface that only fills its cells afterwards passes
  nothing and keeps its plate until the medium is there.

  The four states a cell can be in stay apart: nothing run yet (empty plate), a
  medium, refused, and nothing came back. The last two arrive as `note` — the
  caller has translated the key by then, because a refusal is a German developer
  string until `safetyBlockKey()` has been over it.

  A click on the picture opens it LARGE from here, on the platform's one layer
  (`MediaFullscreen`), with the card's back standing beside it: one click, one
  view, on every surface. The record beside the picture and the record on the
  turned card are ONE object (`back`), and what is pressed on the layer's row
  is what is pressed on the card's back: the same four events, re-emitted.
  Before that every page that laid these cells opened a layer of its own with
  the picture alone — twelve pages, nine of them with a caption composed from
  the record. What a page still says under the
  enlarged picture is `label`: the cell's PLACE in its raster (the model, the
  perspective, „Reference"), which the record does not carry.
-->
<template>
  <div class="media-grid-cell" :class="{ filled: !!url }">
    <FlowCard v-if="url || isExecuting" class="mgc-card" :hold-title="t('resonaMediaCard.flipToBack')">
      <MediaCardFront
        :output-url="url"
        :media-type="mediaType"
        :run-id="runId"
        :is-executing="isExecuting"
        :progress="progress"
        :preview-image="previewImage"
        :model-meta="modelMeta"
        :stage4-duration-ms="durationMs"
        :is-favorited="isFavorited"
        @image-click="shown = $event"
      />
      <template #back="{ flipped }">
        <MediaCardBack
          v-bind="back"
          :active="flipped"
          @toggle-favorite="emit('toggle-favorite')"
          @forward="emit('forward')"
          @download="emit('download')"
          @print="emit('print')"
        />
      </template>
    </FlowCard>

    <div v-else-if="note" class="mgc-note"><span>{{ note }}</span></div>

    <!-- The picture large, its back beside it; see components/MediaFullscreen.vue. -->
    <MediaFullscreen
      :src="shown"
      :alt="label || t('mediaOutput.generatedImage')"
      :label="label ?? ''"
      :back="back"
      @close="shown = null"
      @toggle-favorite="emit('toggle-favorite')"
      @forward="emit('forward')"
      @download="emit('download')"
      @print="emit('print')"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import FlowCard from '@/components/FlowCard.vue'
import MediaCardFront from '@/components/MediaCardFront.vue'
import MediaCardBack from '@/components/MediaCardBack.vue'
import MediaFullscreen from '@/components/MediaFullscreen.vue'
import type { MediaBack } from '@/components/mediaBack'

const props = withDefaults(
  defineProps<{
    /** The medium. Empty: the cell has nothing in it and shows its plate. */
    url: string
    /** A run is out for THIS cell: the card stands and shows it forming. */
    isExecuting?: boolean
    /** How far that run has come, 0..100. */
    progress?: number
    /** The picture as it forms, where the run sends one. */
    previewImage?: string | null
    mediaType?: string
    runId?: string | null
    /** What made it — the composed prompt, on the back. */
    prompt?: string
    /** What Prompt Interception wrote, on the back over `prompt`. */
    intercepted?: string
    /** How the page names that text; without it the block stays away. */
    interceptedLabel?: string
    configId?: string
    createdAt?: number
    modelMeta?: Record<string, any> | null
    durationMs?: number
    /** Further facts of the run, worded by the page: a seed, a setting. */
    facts?: string[]
    isFavorited?: boolean
    /**
     * The cell's place in its raster — the model, the perspective, „Reference" —
     * as the line under the picture when it stands large. The record beside it
     * says what made the picture; this says which of the pictures it is.
     */
    label?: string
    /**
     * A refusal or a failure, in the reader's language already. Shown in place
     * of the medium; a cell holds one or the other, never both.
     */
    note?: string
  }>(),
  {
    isExecuting: false,
    progress: 0,
    previewImage: null,
    mediaType: 'image',
    runId: null,
    prompt: undefined,
    configId: undefined,
    createdAt: undefined,
    modelMeta: null,
    durationMs: 0,
    facts: undefined,
    isFavorited: false,
    label: undefined,
    note: '',
  }
)

const emit = defineEmits<{
  (e: 'download'): void
  (e: 'toggle-favorite'): void
  (e: 'forward'): void
  (e: 'print'): void
}>()

const { t } = useI18n()

/** The picture standing large, or nothing. */
const shown = ref<string | null>(null)

/**
 * The record of this medium, as the back of the card shows it and as the layer
 * shows it beside the picture: one object, so the two can never differ. The
 * AI marking is read by the back itself, from `mediaUrl` (see MediaCardBack).
 */
const back = computed<MediaBack>(() => ({
  mediaType: props.mediaType,
  runId: props.runId,
  mediaUrl: props.url || undefined,
  isFavorited: props.isFavorited,
  prompt: props.prompt,
  intercepted: props.intercepted,
  interceptedLabel: props.interceptedLabel,
  configId: props.configId,
  createdAt: props.createdAt,
  modelMeta: props.modelMeta,
  facts: props.facts,
}))
</script>

<style scoped>
.media-grid-cell {
  position: relative;
  aspect-ratio: 1;
  min-width: 0;
  border-radius: 6px;
  background: var(--surface-2);
  border: 1px solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* A cell with a card in it shows the card, not a plate behind it. */
.media-grid-cell.filled {
  background: transparent;
  border-color: transparent;
}

/* The card is exactly its MEDIUM, and the cell centres it — which is what it
   looked like all along and was not, because a two-sided card takes the height of
   whichever side is TALLER: front and back share one grid cell. The back carries
   the prompt, the model's sheet, a seed and a time, and in a narrow column that
   text wraps into more lines than the picture is high. The card then grew past
   the picture, and the front puts its medium at the START of the space it is
   given (`.output-frame.card { justify-content: flex-start }` — the flow's own
   rule, where the card grows WITH the picture and there is never a space to put
   it in). So the picture hung at the top of the square with the card's dark
   ground under it. Measured at a cell of 509: picture 338 high, back 505, and
   163 px of ground below the picture.

   The back is therefore taken OUT of the height: absolutely placed, it fills the
   card without saying how tall the card should be. `.asm-item.two` carries a
   `transform`, so it is already the containing block — nothing has to be added
   to `FlowCard` for it, and nothing changes for a card that stands anywhere
   else. What the back loses is the room to be as long as it likes, so it
   scrolls; clipped it would drop the end of the prompt without saying so. */
.mgc-card {
  width: 100%;
}

.media-grid-cell :deep(.asm-item.two > .face.back) {
  position: absolute;
  inset: 0;
  overflow-y: auto;
}

/* A refusal runs to about two hundred characters and a cell is one of several
   sharing the surface — so it stays reachable inside the cell instead of being
   cut off at whatever line the box ends on. The size step is the flow's where
   the page has that stylesheet, and a readable hint size where it has not. */
/* The note fills the cell and scrolls; the sentence in it is centred by its
   own auto margins, which is the one centring that survives overflow. A note
   that was a centred flex item was clipped on the side the moment one word
   was wider than the cell (`min-width: auto` on a flex item) and on top the
   moment it was taller (the cell's height comes from `aspect-ratio`, against
   which `max-height: 100%` resolves to nothing): the cause sentence of a
   failed run, with a class name or a path in it, showed its middle and lost
   both ends. Measured 2026-09-18 at a cell of 135: the sentence was 175 wide
   and 168 high. */
.mgc-note {
  position: absolute;
  inset: 0;
  display: flex;
  overflow-y: auto;
  overflow-wrap: anywhere;
  padding: 8px;
  font-size: var(--flow-fs-hint, 0.78rem);
  color: rgba(255, 255, 255, 0.55);
  text-align: center;
}

.mgc-note > span {
  margin: auto;
}
</style>
