<!--
  CanvasPresetOverlay — what "New" opens on the Canvas: the ready-made
  workflows, on the bubble ring of the platform.

  The ring is the one the perspectives and the LoRAs are chosen on
  (`BubbleRingFrame`, `fitRing`): a ready-made workflow is a kind of preset, and
  a second form for the same gesture would be the break. Two kinds stand on it,
  as `RingKind`: the BASIC FORMS, the Flow's paths laid out as nodes, and the
  EXPLORATIONS, after instruments of the Latent Lab and of Compare and the chain
  game Telephone. In the middle, where the perspectives hang "Du bestimmst!",
  stands the EMPTY BOARD: the board as "New" made it until 2026-10-02, and
  still one click.

  A preset is a `PerspectiveBubble`: the picture its own result made, where it
  yields a picture (public/canvas-presets/<id>.webp), else the sign of its
  medium (`MediumGlyph`) on the disc's dark ground. Its name stands across it
  the whole time, as on the LoRA ring — the pictures are examples of what comes
  out, not names of what goes in; what it does is the title under a resting
  pointer. A person's own workflows are not here: they are kept in the
  favourites strip and open from there.

  Picking only says WHICH; whether the board holds work that would be lost,
  and loading, are the page's (views/canvas_workflow.vue). See
  docs/ELEMENT_STRUCTURE_REGISTRY.md.
-->
<template>
  <BubbleRingFrame
    :visible="modelValue"
    :diameter="geo.diameter"
    :square="geo.square"
    @close="close"
  >
    <div class="cp-item" data-ring-bubble :style="bubbleStyle(MIDDLE, geo.itemPct)">
      <PerspectiveBubble
        :name="t('canvas.presets.empty')"
        :title="t('canvas.presets.emptyDescription')"
        revealed
        @open="pickEmpty"
      />
    </div>

    <RingKind
      v-for="(k, i) in KINDS"
      :key="k"
      :open="k === openKind"
      :disabled="!byKind[k].length"
      :style="[bubbleStyle(catPos[i], geo.catPct), kindStyle]"
      @click="openKind = k"
      @mouseenter="onKindHover(k)"
    >
      {{ t(`canvas.presets.kinds.${k}`) }}
    </RingKind>

    <div
      v-for="(p, j) in openItems"
      :key="p.info.id"
      class="cp-item"
      data-ring-bubble
      :style="bubbleStyle(itemPos[j], geo.itemPct)"
    >
      <PerspectiveBubble
        :src="presetPicture(p.info)"
        :name="t(p.info.name)"
        :title="t(p.info.description)"
        revealed
        @open="pick(p)"
      >
        <template v-if="!presetPicture(p.info)" #default>
          <MediumGlyph :id="p.info.medium" class="cp-glyph" />
        </template>
      </PerspectiveBubble>
    </div>

    <p v-if="note" class="cp-note" :class="{ 'cp-err': !!error }">{{ note }}</p>
  </BubbleRingFrame>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import BubbleRingFrame from '@/components/BubbleRingFrame.vue'
import PerspectiveBubble from '@/components/PerspectiveBubble.vue'
import RingKind from '@/components/RingKind.vue'
import MediumGlyph from '@/components/MediumGlyph.vue'
import { fitRing, ringPositions, bloomPositions, type RingPos } from '@/composables/useBubbleRing'
import { presetPicture, type CanvasPreset, type PresetKind } from '@/lib/canvasPresets'

const props = defineProps<{
  modelValue: boolean
  presets: readonly CanvasPreset[]
  loading?: boolean
  /** Why there are no presets to show, where the server did not answer. */
  error?: string
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'pick', preset: CanvasPreset): void
  (e: 'empty'): void
}>()

const { t } = useI18n()

const KINDS: PresetKind[] = ['basic', 'explore']
const MIDDLE: RingPos = { x: 50, y: 50 }

const byKind = computed<Record<PresetKind, CanvasPreset[]>>(() => ({
  basic: props.presets.filter(p => p.info.kind === 'basic'),
  explore: props.presets.filter(p => p.info.kind === 'explore'),
}))

/** None is open until one is asked for, as on the LoRA ring with several kinds. */
const openKind = ref<PresetKind | null>(null)
watch(
  () => props.modelValue,
  (open) => {
    if (!open) openKind.value = null
  },
)

/** The short side of the window: the disc may not leave it. */
const viewport = ref(1024)
function measure(): void {
  if (typeof window === 'undefined') return
  viewport.value = Math.min(window.innerWidth, window.innerHeight)
}
onMounted(() => {
  measure()
  window.addEventListener('resize', measure)
})
onBeforeUnmount(() => window.removeEventListener('resize', measure))

/**
 * The circle, reckoned from BOTH kinds and the piece in the middle, never from
 * the open kind, so the frame stands still while somebody looks through them.
 */
const geo = computed(() =>
  fitRing({
    counts: KINDS.map(k => Math.max(1, byKind.value[k].length)),
    viewportPx: viewport.value,
    centre: true,
  }),
)
const catPos = computed<RingPos[]>(() => ringPositions(KINDS.length, geo.value.ringPct))
const openIndex = computed(() => (openKind.value ? KINDS.indexOf(openKind.value) : -1))
const openItems = computed<CanvasPreset[]>(() => (openKind.value ? byKind.value[openKind.value] : []))
const itemPos = computed<RingPos[]>(() => {
  const cat = catPos.value[openIndex.value]
  const distance = geo.value.bloomPct[openIndex.value]
  if (!cat || distance === undefined) return []
  return bloomPositions(cat, openItems.value.length, distance)
})

/** A bubble sits on its point and is as wide as the ring says. */
function bubbleStyle(pos: RingPos | undefined, sizePct: number) {
  const p = pos ?? MIDDLE
  return {
    left: `${p.x}%`,
    top: `${p.y}%`,
    width: `${sizePct}%`,
    height: `${sizePct}%`,
  }
}

/** A kind's name is measured off its bubble, as on the LoRA ring. */
const kindStyle = computed(() => {
  const size = (geo.value.catPct / 100) * geo.value.square
  return { fontSize: `${Math.max(9, size * 0.14)}px` }
})

/** A pointer that rests on a kind opens it (see LoraPickOverlay). */
function onKindHover(kind: PresetKind): void {
  if (!byKind.value[kind].length) return
  if (typeof window !== 'undefined' && window.matchMedia?.('(hover: hover) and (pointer: fine)').matches) {
    openKind.value = kind
  }
}

/** What stands at the foot of the disc while the presets are not there. */
const note = computed<string>(() => {
  if (props.error) return t('canvas.presets.unavailable')
  if (props.loading && !props.presets.length) return t('canvas.presets.loading')
  return ''
})

function close(): void {
  emit('update:modelValue', false)
}

function pick(preset: CanvasPreset): void {
  close()
  emit('pick', preset)
}

function pickEmpty(): void {
  close()
  emit('empty')
}
</script>

<style scoped>
.cp-item {
  position: absolute;
  transform: translate(-50%, -50%);
}

/* The sign of the medium, smaller than the disc and in the light weight the
   LoRA ring gives its sign under a name (LoraGlyph `light`): thin and faint,
   so the name reads first. At full weight the three lines of the text sign
   ran through the name like a strike-through. */
.cp-glyph {
  display: block;
  width: 56%;
  height: 56%;
  margin: 22%;
  stroke-width: 1.1;
  opacity: 0.4;
}

/* At the foot of the disc, below the lower kind: the LoRA ring sets its note
   in the middle, where this ring has the empty board, and every height
   between the two kinds crosses one of them. */
.cp-note {
  position: absolute;
  left: 0;
  right: 0;
  top: 86%;
  transform: translateY(-50%);
  margin: 0;
  padding: 0 2rem;
  text-align: center;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.95rem;
}

.cp-err {
  color: #e0568a;
}
</style>
