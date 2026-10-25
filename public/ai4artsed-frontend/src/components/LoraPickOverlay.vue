<!--
  LoraPickOverlay — the chooser the Flow's LoRA sign opens: the adapters this
  session may lay on the table, on the bubble ring of the platform.

  It stands in `BubbleRingFrame`, a circle, and not in a rectangle: the
  perspectives are chosen on a ring, a LoRA is chosen beside them
  for the same table, and two forms for one gesture were the break. The ring
  carries the KIND of thing an adapter makes, which the register says
  (`category`; what the platform's own presets bring carries `photography`). An
  adapter the register names no kind for hangs under its release instead — the platform's, the
  course's, one's own — so a fresh training is in the chooser from the first
  moment and gets its kind when somebody gives it one.

  The circle is as wide as what stands in it, as flexible in extent as
  possible: `fitRing` reckons the diameter from the number of kinds and the
  widest ring of adapters, and only a circle that would leave the window is cut
  down to it. ONE kind stands in the middle and is open from the start — a ring
  of one bubble would be a circle around nothing.

  A kind is a `RingKind`. An adapter is a `PerspectiveBubble` with the net in it and its name across
  it. The name stays there, where a perspective shows its own only while it is
  held: the faces here are one and the same net, and a ring of unnamed nets
  says nothing. A click lays it on the table beside the zone and closes the
  frame. An adapter whose file the folder does not hold stands in its ring and
  cannot be taken — like a model the availability check reports absent — with
  the cause in its title. See docs/ELEMENT_STRUCTURE_REGISTRY.md.
-->
<template>
  <BubbleRingFrame
    :visible="modelValue"
    :diameter="geo.diameter"
    :square="geo.square"
    @close="close"
  >
    <p v-if="note" class="lp-note" :class="{ 'lp-err': !!loras.error }">{{ note }}</p>
    <template v-else>
      <RingKind
        v-for="(r, i) in rings"
        :key="r.key"
        :open="r.key === openKey"
        :style="[bubbleStyle(catPos[i], geo.catPct), kindStyle]"
        @click="openKey = r.key"
        @mouseenter="onKindHover(r.key)"
      >
        {{ kindLabel(r) }}
      </RingKind>

      <div
        v-for="(l, j) in openItems"
        :key="l.id"
        class="lp-item"
        data-ring-bubble
        :style="bubbleStyle(itemPos[j], geo.itemPct)"
      >
        <PerspectiveBubble
          :name="l.name"
          :title="hint(l)"
          :disabled="!l.present"
          :read-color="LORA_COLOR"
          openable
          revealed
          @open="pick(l)"
        >
          <LoraGlyph light />
        </PerspectiveBubble>
      </div>
    </template>
  </BubbleRingFrame>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import BubbleRingFrame from '@/components/BubbleRingFrame.vue'
import PerspectiveBubble from '@/components/PerspectiveBubble.vue'
import RingKind from '@/components/RingKind.vue'
import LoraGlyph from '@/components/LoraGlyph.vue'
import { fitRing, ringPositions, bloomPositions, type RingPos } from '@/composables/useBubbleRing'
import { useLoraStore, LORA_COLOR, type LoraAdapter, type LoraRing } from '@/stores/loras'

const props = defineProps<{
  modelValue: boolean
  /** What the surface calls a config, for the title of a disc. */
  labelFor: (configId: string) => string
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'pick', l: LoraAdapter): void
}>()

const { t, te } = useI18n()
const loras = useLoraStore()

const rings = computed<LoraRing[]>(() => loras.rings)
const openKey = ref<string | null>(null)

watch(
  () => props.modelValue,
  (open) => {
    if (open) void loras.load()
  },
  { immediate: true }
)

// One kind: it stands in the middle and is open, because there is nothing to
// choose between. Several: none is open until one is asked for, and a kind
// that has gone (the register was read again) takes the opening with it.
watch(
  rings,
  (rs) => {
    const only = rs.length === 1 ? rs[0] : undefined
    if (only) openKey.value = only.key
    else if (!rs.some((r) => r.key === openKey.value)) openKey.value = null
  },
  { immediate: true }
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
 * The circle. Reckoned from ALL the kinds, never from the open one, so the
 * frame stands still while somebody looks through them.
 */
const geo = computed(() =>
  fitRing({ counts: rings.value.map((r) => r.items.length), viewportPx: viewport.value })
)
const catPos = computed<RingPos[]>(() => ringPositions(rings.value.length, geo.value.ringPct))
const openIndex = computed(() => rings.value.findIndex((r) => r.key === openKey.value))
const openItems = computed<LoraAdapter[]>(() => rings.value[openIndex.value]?.items ?? [])
const itemPos = computed<RingPos[]>(() => {
  const cat = catPos.value[openIndex.value]
  const distance = geo.value.bloomPct[openIndex.value]
  if (!cat || distance === undefined) return []
  return bloomPositions(cat, openItems.value.length, distance)
})

/** A bubble sits on its point and is as wide as the ring says. */
function bubbleStyle(pos: RingPos | undefined, sizePct: number) {
  const p = pos ?? { x: 50, y: 50 }
  return {
    left: `${p.x}%`,
    top: `${p.y}%`,
    width: `${sizePct}%`,
    height: `${sizePct}%`,
  }
}

/**
 * A kind carries nothing but its name, so the name is measured off the bubble
 * and not off the disc: the same circle reads the same whether it stands in a
 * wide frame or a narrow one.
 */
const kindStyle = computed(() => {
  const size = (geo.value.catPct / 100) * geo.value.square
  return {
    width: `${geo.value.catPct}%`,
    height: `${geo.value.catPct}%`,
    fontSize: `${Math.max(9, size * 0.14)}px`,
  }
})

/**
 * A pointer that rests on a kind opens it — the ring is one move away, as it is
 * with the perspectives. A finger raises a `mouseenter` of its own after a tap,
 * and the tap has already opened the same kind, so nothing is lost by letting
 * it through.
 */
function onKindHover(key: string): void {
  if (typeof window !== 'undefined' && window.matchMedia?.('(hover: hover) and (pointer: fine)').matches) {
    openKey.value = key
  }
}

/** What stands in the middle while there is nothing to choose. */
const note = computed<string>(() => {
  if (loras.error) return loras.error
  if (loras.loading && !loras.items.length) return t('x2xFlow.loraLoading')
  if (!loras.items.length) return t('x2xFlow.loraNone')
  return ''
})

/**
 * The name of a kind. A kind the register names is looked up; one the platform
 * has no word for is shown as the register wrote it, rather than not at all.
 */
function kindLabel(r: LoraRing): string {
  if (r.kind === 'platform') return t('x2xFlow.loraGroupPlatform')
  if (r.kind === 'course') return t('x2xFlow.loraGroupCourse', { course: loras.courseName })
  if (r.kind === 'own') return t('x2xFlow.loraGroupOwn')
  // `te` asks the CURRENT locale alone, so a key that stands only in `en.ts`
  // — every kind, until the translator has been through — would read as its
  // raw register key in a German session.
  const key = `x2xFlow.loraCategories.${r.category}`
  return te(key) || te(key, 'en') ? t(key) : (r.category || '').replace(/_/g, ' ')
}

function close(): void {
  emit('update:modelValue', false)
}

function pick(l: LoraAdapter): void {
  if (!l.present) return
  emit('pick', l)
  close()
}

/**
 * The title of a disc: the model it runs under and its trigger, or why it
 * cannot be taken. Two configs can run the same model and carry the same name,
 * so each name is said once.
 */
function hint(l: LoraAdapter): string {
  if (!l.present) return t('x2xFlow.loraAbsent', { file: l.file })
  const names: string[] = []
  for (const c of l.base_configs) {
    const label = props.labelFor(c)
    if (label && !names.includes(label)) names.push(label)
  }
  return [l.name, names.join(' · '), l.trigger].filter(Boolean).join(' — ')
}
</script>

<style scoped>
.lp-item {
  position: absolute;
  transform: translate(-50%, -50%);
}

.lp-note {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  margin: 0;
  padding: 0 2rem;
  text-align: center;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.95rem;
}

.lp-err {
  color: #e0568a;
}
</style>
