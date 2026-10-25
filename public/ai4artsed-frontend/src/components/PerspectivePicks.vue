<!--
  THE STRIP OF CHOSEN PERSPECTIVES.

  What a surface has picked out of the platform's perspective catalogue, as the
  discs those perspectives are shown as, one beside the other and wrapping onto
  the next line — and at its end the empty place of one more, which opens the
  chooser (`components/InterceptionPresetOverlay.vue`). The order of the strip
  is the order the surface works in.

  It holds ONE perspective as readily as several: Interception across Models
  runs a single standing choice, Perspectives on a Template runs one row per
  perspective. Where a surface may only ever hold one, `single` closes the strip
  once it is filled — there is nothing to add, and the disc itself opens the
  chooser to exchange it.

  WHAT A PERSPECTIVE SAYS hangs on the disc: rest the pointer on one that is
  already chosen — hold it, on the reference device — and its interception
  prompt stands there to be read. It is the box the
  flow board opens at a perspective (`.persp-edit` in `views/x2x_flow.vue`),
  WITHOUT its writing half: no name field, no text field, no keeping — a chosen
  perspective is read here and written there. The card is the platform's own
  (`components/InfoCard.vue`), entered so a prompt longer than the card can be
  scrolled rather than cut off.

  What it does NOT hold: the catalogue, the overlay, or what a perspective is
  worth to the surface. It emits, and the surface answers.
-->
<template>
  <div class="pp-picks" :class="{ single }">
    <div
      v-for="p in picks"
      :key="p.configId"
      class="pp-pick"
      @pointerenter="restOn(p, $event)"
      @pointerleave="leaveDisc"
      @pointerdown="pressOn(p, $event)"
      @pointerup="releaseCard"
      @pointercancel="releaseCard"
    >
      <PerspectiveBubble
        :preview-id="p.previewId"
        :config-id="p.configId"
        :color="p.color || ''"
        :name="p.configName"
        revealed
        :disabled="disabled"
        @open="openChooser"
      />
      <RemoveBadge
        v-if="!single"
        :title="removeTitle"
        @remove="emit('remove', p.configId)"
      />
    </div>
    <button
      v-if="!single || !picks.length"
      type="button"
      class="pp-add"
      :disabled="disabled"
      :title="addTitle"
      @click="emit('add')"
    >
      +
    </button>

    <InfoCard
      :open="!!shown"
      :x="x"
      :y="y"
      :above="above"
      :width="420"
      interactive
      @enter="keepCard"
      @leave="dismissCard"
    >
      <template v-if="shown">
        <PerspectiveInfo :name="shown.configName" :text="shown.prompt" />
      </template>
    </InfoCard>
  </div>
</template>

<script setup lang="ts">
import PerspectiveBubble from '@/components/PerspectiveBubble.vue'
import RemoveBadge from '@/components/RemoveBadge.vue'
import InfoCard from '@/components/InfoCard.vue'
import PerspectiveInfo from '@/components/PerspectiveInfo.vue'
import { useInfoCard } from '@/composables/useInfoCard'

/** One perspective in the strip, as the chooser hands it over. */
export interface PerspectivePick {
  configId: string
  configName: string
  previewId: string
  /** A palette colour where the perspective is one of this person's own. */
  color?: string
  /**
   * What this perspective tells the writing model — the interception prompt, in
   * the reader's language, as the chooser handed it over. Without it the disc
   * stays silent: there is nothing to show, and an empty card would claim there
   * was.
   */
  prompt?: string
}

withDefaults(
  defineProps<{
    picks: PerspectivePick[]
    /** A run is out: nothing is chosen, exchanged or taken away meanwhile. */
    disabled?: boolean
    /** The surface holds at most one, so there is nothing to add beside it. */
    single?: boolean
    addTitle?: string
    removeTitle?: string
  }>(),
  { disabled: false, single: false, addTitle: '', removeTitle: '' },
)

const emit = defineEmits<{
  /** Open the chooser — from the plus, or from a disc that is to be exchanged. */
  add: []
  /** Take this one out of the strip. */
  remove: [configId: string]
}>()

const {
  shown,
  x,
  y,
  above,
  enter: openCard,
  down: pressCard,
  up: releaseCard,
  leave: leaveDisc,
  keep: keepCard,
  dismiss: dismissCard,
  close: closeCard,
  consumePress,
} = useInfoCard<PerspectivePick>()

/* The card may be ENTERED, because an interception prompt runs to 3750
   characters and is read by scrolling; the grace that lets the pointer walk
   from the disc to the card is the composable's (`useInfoCard`). */

function restOn(p: PerspectivePick, event: PointerEvent) {
  openCard(p.prompt ? p : undefined, event)
}

function pressOn(p: PerspectivePick, event: PointerEvent) {
  pressCard(p.prompt ? p : undefined, event)
}


/**
 * The disc opens the chooser, as it did — except at the end of a long press,
 * which belongs to the press that opened the card. The card goes first either
 * way: the chooser is a disc over the whole window and would stand under it.
 */
function openChooser() {
  if (consumePress()) return
  dismissCard()
  emit('add')
}

</script>

<style scoped>
.pp-picks {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-start;
}

/* A surface that holds ONE perspective has nothing to line it up with, so the
   disc stands in the middle of its place instead of at the left edge of a
   strip. */
.pp-picks.single {
  justify-content: center;
}

/* 88 px, not the 62 it was: the name stands ACROSS the disc (`CircleTitle`), and
   that is sized to the disc — at 62 px the longer names came out at 9.6 px and
   filled the circle from rim to rim over the picture. The flow board gives the
   same disc 144 px, which is why the name reads there. 88 px is the largest that
   still puts THREE in a row of the preparation column (3 x 88 + 2 x 8 = 280 of
   303 px) and lifts the name to about 15 px (2026-09-06). */
.pp-pick {
  position: relative;
  width: 88px;
}

/* One more. It is the plus of a list and not the free sign of a surface
   (components/IntakePlus.vue is that one), so it is drawn as the empty place a
   disc would take. */
.pp-add {
  width: 88px;
  aspect-ratio: 1;
  border-radius: 50%;
  border: 1px dashed rgb(var(--surface-4-rgb) / 0.9);
  background: none;
  color: rgba(255, 255, 255, 0.55);
  font-size: 1.4rem;
  line-height: 1;
  cursor: pointer;
  font-family: inherit;
}

.pp-add:hover:not(:disabled) {
  color: rgba(255, 255, 255, 0.85);
  border-color: rgba(255, 255, 255, 0.35);
}

.pp-add:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

</style>
