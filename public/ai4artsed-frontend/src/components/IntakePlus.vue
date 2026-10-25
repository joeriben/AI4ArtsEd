<script lang="ts">
/** What a surface can take in through the plus. `audio` is declared because the
 *  sign is meant to carry it; no surface offers it yet, because the platform has
 *  no channel that would receive spoken input here. Declaring it without
 *  offering it keeps the gap visible instead of silently closing it. */
export type IntakeKind = 'upload' | 'camera' | 'audio' | 'text'
</script>

<script setup lang="ts">
/**
 * INTAKE PLUS — the free fixture that brings material in.
 *
 * WHAT THIS IS
 *   The plus of the flow canvas, on the surfaces where a human talks with an
 *   agent. Not a button in a bar: a sign lying ON the surface, drawn at the
 *   platform's fixture step (--flow-glyph-plus), breathing in the same slow
 *   rhythm, and opening its ways on an ARC around itself — the same drawing and
 *   the same gesture as `views/x2x_flow.vue`, so the two places do not each
 *   teach their own vocabulary.
 *
 * WHAT IT IS NOT
 *   It opens no channel of its own. It names a kind and hands it to the surface,
 *   which already knows how to receive that kind. A surface offers only what it
 *   can take.
 *
 * WHERE IT STANDS
 *   The consumer places it (the root is absolutely positioned by the page). It
 *   belongs to no node and no bar.
 *
 * IT MOVES
 *   Like every sign of its kind on this platform, it is put where the hand
 *   wants it — the shared gesture of `composables/usePointDrag.ts`, the same
 *   one the flow canvas's fixtures answer to. Until it is first moved it keeps
 *   the resting place its surface gave it in CSS; from the first drag on it
 *   carries its own place, seeded from where it was standing, so nothing jumps.
 */
import { ref, computed, reactive, onMounted, onUnmounted } from 'vue'
import { usePointDrag } from '@/composables/usePointDrag'
import { useI18n } from 'vue-i18n'

const props = withDefaults(
  defineProps<{
    disabled?: boolean
    /** What this surface can actually receive. */
    offers?: IntakeKind[]
  }>(),
  { disabled: false, offers: () => ['upload', 'camera', 'text'] as IntakeKind[] },
)

const emit = defineEmits<{ pick: [kind: IntakeKind] }>()

const { t } = useI18n()
const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)

// Where the hand has put it. Empty until the first drag: before that the sign
// stands where its surface rests it, and measuring that place back into pixels
// would only reproduce, less exactly, what the CSS already does.
const at = reactive({ x: 0, y: 0 })
const placed = ref(false)
const { startPointDrag, dragMoved } = usePointDrag()

function grab(e: PointerEvent) {
  if (props.disabled) return
  // Seeded from where the sign is STANDING, so taking hold of it moves nothing.
  if (!placed.value) {
    const r = rootEl.value?.getBoundingClientRect()
    if (!r) return
    at.x = Math.round(r.left)
    at.y = Math.round(r.top)
    placed.value = true
  }
  startPointDrag(e, at)
}

/* The marks, on the platform's 960 grid — the plus and the three ways are the
   same paths the flow canvas draws. */
const D_PLUS = 'M440-440H200v-80h240v-240h80v240h240v80H520v240h-80v-240Z'
const GLYPH: Record<IntakeKind, string> = {
  upload:
    'M480-480ZM200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h320v80H200v560h560v-320h80v320q0 33-23.5 56.5T760-120H200Zm40-160h480L570-480 450-320l-90-120-120 160Zm440-320v-80h-80v-80h80v-80h80v80h80v80h-80v80h-80Z',
  camera:
    'M480-260q75 0 127.5-52.5T660-440q0-75-52.5-127.5T480-620q-75 0-127.5 52.5T300-440q0 75 52.5 127.5T480-260Zm0-80q-42 0-71-29t-29-71q0-42 29-71t71-29q42 0 71 29t29 71q0 42-29 71t-71 29ZM160-120q-33 0-56.5-23.5T80-200v-480q0-33 23.5-56.5T160-760h126l74-80h240l74 80h126q33 0 56.5 23.5T880-680v480q0 33-23.5 56.5T800-120H160Zm0-80h640v-480H638l-73-80H395l-73 80H160v480Zm320-240Z',
  audio:
    'M480-400q-50 0-85-35t-35-85v-240q0-50 35-85t85-35q50 0 85 35t35 85v240q0 50-35 85t-85 35Zm-40 280v-123q-104-14-172-93t-68-184h80q0 83 58.5 141.5T480-320q83 0 141.5-58.5T680-520h80q0 105-68 184t-172 93v123h-80Z',
  text:
    'm40-200 210-560h100l210 560h-96l-51-143H187l-51 143H40Zm176-224h168l-82-232h-4l-82 232Zm504 104v-120H600v-80h120v-120h80v120h120v80H800v120h-80Z',
}
const LABEL: Record<IntakeKind, string> = {
  upload: 'intake.upload',
  camera: 'intake.camera',
  audio: 'intake.audio',
  text: 'intake.text',
}

/* The arc opens UPWARD — the sign rests low on the surface, and an arc turned
   down would open off the screen — and it TURNS TOWARD THE FREE MIDDLE, exactly
   as it does on the flow canvas: a sign resting at the left edge that opened
   symmetrically would put its outer way off the glass. Set when the arc opens,
   from where the sign actually is. */
const span = ref<[number, number]>([-160, -20])
function measureSpan() {
  const r = rootEl.value?.getBoundingClientRect()
  if (!r) return
  const cx = r.left + r.width / 2
  let s: [number, number]
  if (cx < window.innerWidth * 0.3) s = [-100, -10]
  else if (cx > window.innerWidth * 0.7) s = [-170, -80]
  else s = [-160, -20]
  // Carried to the top of the surface, an arc opening upward opens off the
  // screen. Mirrored, it blooms downward from the same sign.
  const cy = r.top + r.height / 2
  if (cy < window.innerHeight * 0.34) s = [-s[0], -s[1]]
  span.value = s
}

const ways = computed(() =>
  props.offers.map((kind, i) => {
    const n = props.offers.length
    const [from, to] = span.value
    const deg = n > 1 ? from + (i * (to - from)) / (n - 1) : (from + to) / 2
    const rad = (deg * Math.PI) / 180
    return {
      kind,
      d: GLYPH[kind],
      label: t(LABEL[kind]),
      ux: Math.cos(rad).toFixed(4),
      uy: Math.sin(rad).toFixed(4),
      delay: `${i * 45}ms`,
    }
  }),
)

function toggle() {
  if (props.disabled) return
  // A click that ended a drag is not a click.
  if (dragMoved()) return
  if (!open.value) measureSpan()
  open.value = !open.value
}

function choose(kind: IntakeKind) {
  open.value = false
  emit('pick', kind)
}

/* Pressing anywhere else puts the arc away — captured, so it closes before the
   press lands on whatever was pressed. */
function onDocPointerDown(e: PointerEvent) {
  if (!open.value) return
  const root = rootEl.value
  if (root && e.target instanceof Node && root.contains(e.target)) return
  open.value = false
}
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && open.value) open.value = false
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocPointerDown, true)
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  document.removeEventListener('pointerdown', onDocPointerDown, true)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div
    ref="rootEl"
    class="ip"
    :class="{ placed }"
    :style="placed ? { left: at.x + 'px', top: at.y + 'px' } : undefined"
  >
    <button
      type="button"
      class="ip-mark"
      :class="{ open }"
      :disabled="props.disabled"
      :title="t('intake.plus')"
      :aria-label="t('intake.plus')"
      :aria-expanded="open"
      @pointerdown.stop.prevent="grab"
      @click="toggle"
    >
      <svg viewBox="0 -960 960 960" fill="currentColor" aria-hidden="true">
        <path :d="D_PLUS" />
      </svg>
    </button>

    <!-- The ways, on an arc around the sign. The box is the size of the sign and
         lies over it, so the ways can be placed from ITS centre; it catches
         nothing itself, or the sign underneath would stop being clickable. -->
    <div v-if="open" class="ip-arc">
      <button
        v-for="(w, i) in ways"
        :key="w.kind"
        type="button"
        class="ip-way"
        :style="{
          transform: `translate(-50%, -50%) translate(calc(var(--ip-r) * ${w.ux}), calc(var(--ip-r) * ${w.uy}))`,
          '--ip-d': w.delay,
        }"
        :title="w.label"
        @click.stop="choose(w.kind)"
      >
        <svg viewBox="0 -960 960 960" fill="currentColor" aria-hidden="true">
          <path :d="w.d" />
        </svg>
        <span class="ip-l">{{ w.label }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.ip { position: relative; display: block; width: var(--flow-glyph-plus); height: var(--flow-glyph-plus); }
/* Once a hand has moved it, the sign holds its own place on the view. */
.ip.placed { position: fixed; right: auto; bottom: auto; z-index: 62; }

/* The sign itself: drawn, not framed. Same step, same green, same slow breath
   as the free fixtures of the flow canvas. */
.ip-mark {
  display: flex; padding: 0; border: none; background: transparent;
  color: #3ecf8e; cursor: pointer;
  animation: ip-pulse 3.2s ease-in-out infinite;
}
.ip-mark svg { width: var(--flow-glyph-plus); height: var(--flow-glyph-plus); transition: transform 0.18s ease; }
.ip-mark:hover:not(:disabled) { color: #5fe0a6; }
.ip-mark.open svg { transform: rotate(45deg); }
.ip-mark:disabled { opacity: 0.35; cursor: default; animation: none; }

.ip-arc {
  position: absolute; left: 0; top: 0; z-index: 25;
  width: var(--flow-glyph-plus); height: var(--flow-glyph-plus);
  pointer-events: none;
  --ip-r: calc(var(--flow-glyph-fixture) * 1.7);
}
.ip-way {
  position: absolute; left: 50%; top: 50%;
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  padding: 0; border: none; background: transparent;
  color: #3ecf8e; cursor: pointer; pointer-events: auto;
}
.ip-way svg { width: calc(var(--flow-glyph-fixture) * 0.5); height: calc(var(--flow-glyph-fixture) * 0.5); }
.ip-l { font-size: var(--flow-fs-hint); color: #9a97a8; white-space: nowrap; }
.ip-way:hover { color: #5fe0a6; }
.ip-way:hover .ip-l { color: #e9e6fb; }
.ip-way svg, .ip-l { animation: ip-in 0.18s ease-out both; animation-delay: var(--ip-d, 0ms); }
@keyframes ip-in { from { opacity: 0; transform: scale(0.6); } to { opacity: 1; transform: none; } }

/* Faint, and slow: an invitation, not a signal. */
@keyframes ip-pulse { 0%, 100% { opacity: 0.82; } 50% { opacity: 1; } }

@media (prefers-reduced-motion: reduce) {
  .ip-mark { animation: none; }
  .ip-mark.open svg { transform: none; }
  .ip-way svg, .ip-l { animation: none; }
}
</style>
