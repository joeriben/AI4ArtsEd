<!--
  Bereichsgleis — up to four ranges over ONE scale, in ONE track: the fills say
  which part of the scale each range takes, two handles set it, and the numbers
  below say it again in figures, with `+` to add a range and `×` to take one
  away. Each range keeps its colour, so a consumer can carry that colour on into
  whatever it draws the ranges against.

  Taken out of `views/latent_lab/feature_probing.vue`, where it had stood
  inline since the instrument was built and where the Fusion Workbench would
  have been the second hand-built copy, a parallel structure.

  The clamping is the rule that stood there, word for word, with the two numbers
  it hard-coded taken as `min` and `max`: `from` is held at the floor, `to` at
  the ceiling, and a `from` dragged past its `to` collapses onto it. What is new:
  `marks`, the layer of words above the track; `maxRanges`, which Feature Probing
  kept as its own constant; `min`, which was 1 there; `disabled`, `addTitle` and
  `removeTitle`; the `actions` slot; and the array is EMITTED rather than mutated
  in place, so a caller may hold its ranges wherever it likes.

  What a range MEANS is the consumer's business and nothing is assumed here:
  Feature Probing reads the four as a UNION and hands one run the ranks they
  cover; the Fusion Workbench reads each one as a value of an axis, one raster
  column per range.
-->
<template>
  <div class="range-track">
    <!-- The words over the scale, where the consumer has any. Each sits at the
         START of what it names, loosely: the phase names of a denoising run are
         empirically adapted observations, and a word set exactly on a step would
         claim more than they carry. -->
    <div v-if="marks.length" class="rt-marks">
      <span v-for="m in marks" :key="m.at" class="rt-mark" :style="{ insetInlineStart: pct(m.at) }">{{ m.label }}</span>
    </div>

    <div class="unified-slider">
      <div class="slider-track">
        <div v-for="(range, rIdx) in ranges" :key="`fill-${rIdx}`"
          class="slider-fill" :class="`range-color-${rIdx}`"
          :style="fillStyle(range)">
        </div>
      </div>
      <template v-for="(range, rIdx) in ranges" :key="`handles-${rIdx}`">
        <input type="range" class="slider-handle" :class="`handle-color-${rIdx}`"
          :style="{ zIndex: rIdx * 2 + 1 }" :min="min" :max="max || min" step="1"
          :value="range.from" :disabled="disabled" @input="onHandle(rIdx, 'from', $event)" />
        <input type="range" class="slider-handle" :class="`handle-color-${rIdx}`"
          :style="{ zIndex: rIdx * 2 + 2 }" :min="min" :max="max || min" step="1"
          :value="range.to" :disabled="disabled" @input="onHandle(rIdx, 'to', $event)" />
      </template>
    </div>

    <div class="ranges-row">
      <div v-for="(range, rIdx) in ranges" :key="`rg-${rIdx}`" class="range-group" :class="`range-color-${rIdx}`">
        <span class="range-tag">{{ rIdx + 1 }}</span>
        <input type="number" :value="range.from" :min="min" :max="range.to || min" class="range-input"
          :disabled="disabled" @change="onNumber(rIdx, 'from', $event)" @focus="($event.target as HTMLInputElement).select()" />
        <span class="range-sep">&ndash;</span>
        <input type="number" :value="range.to" :min="range.from" :max="max || 0" class="range-input"
          :disabled="disabled" @change="onNumber(rIdx, 'to', $event)" @focus="($event.target as HTMLInputElement).select()" />
        <button v-if="ranges.length > 1" class="remove-btn" :disabled="disabled" :title="removeTitle" @click="removeRange(rIdx)">&times;</button>
      </div>
      <button v-if="ranges.length < maxRanges" class="mini-btn add-btn" :disabled="disabled" :title="addTitle" @click="addRange">+</button>
      <slot name="actions"></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/** One range on the scale, in the scale's own figures, both ends included. */
export interface RangeSelection {
  from: number
  to: number
}

/** A word over the track, at the value it names. */
export interface RangeMark {
  at: number
  label: string
}

const props = withDefaults(
  defineProps<{
    modelValue: RangeSelection[]
    /** The scale, in the consumer's own figures. `max` of 0 means: nothing to pick yet. */
    min?: number
    max: number
    maxRanges?: number
    disabled?: boolean
    marks?: RangeMark[]
    addTitle?: string
    removeTitle?: string
  }>(),
  { min: 1, maxRanges: 4, disabled: false, marks: () => [], addTitle: undefined, removeTitle: undefined },
)

const emit = defineEmits<{ 'update:modelValue': [RangeSelection[]] }>()

const ranges = computed(() => props.modelValue)
/** How many figures the scale holds — `to` counts, so a full scale is max−min+1. */
const span = computed(() => Math.max(0, props.max - props.min + 1))

function pct(at: number): string {
  if (span.value <= 0) return '0%'
  return `${((at - props.min) / span.value) * 100}%`
}

function fillStyle(range: RangeSelection): Record<string, string> {
  if (span.value <= 0 || range.to < range.from) {
    return { insetInlineStart: '0%', width: '0%' }
  }
  const start = ((range.from - props.min) / span.value) * 100
  const width = ((range.to - range.from + 1) / span.value) * 100
  return { insetInlineStart: `${start}%`, width: `${width}%` }
}

/**
 * Both ends of one range, under the rule Feature Probing wrote for them: `from`
 * is held at the floor, `to` at the ceiling, and a `from` that has passed its
 * `to` collapses onto it. `to` is NOT held at the floor, and that is what keeps
 * `to = 0` reachable — the state a fresh range starts in, and the one the
 * Fusion Workbench reads as a window that injects nowhere.
 */
function write(rIdx: number, end: 'from' | 'to', raw: number): void {
  const next = props.modelValue.map((r) => ({ ...r }))
  const r = next[rIdx]
  if (!r) return
  r[end] = Number.isFinite(raw) ? Math.round(raw) : props.min
  if (r.from < props.min) r.from = props.min
  if (r.to > props.max) r.to = props.max
  if (r.from > r.to && r.to > 0) r.from = r.to
  emit('update:modelValue', next)
}
function onHandle(rIdx: number, end: 'from' | 'to', ev: Event): void {
  write(rIdx, end, Number((ev.target as HTMLInputElement).value))
}
function onNumber(rIdx: number, end: 'from' | 'to', ev: Event): void {
  write(rIdx, end, Number((ev.target as HTMLInputElement).value))
}

function addRange(): void {
  if (props.modelValue.length >= props.maxRanges) return
  emit('update:modelValue', [...props.modelValue.map((r) => ({ ...r })), { from: props.min, to: 0 }])
}
function removeRange(rIdx: number): void {
  if (props.modelValue.length <= 1) return
  emit('update:modelValue', props.modelValue.filter((_, i) => i !== rIdx).map((r) => ({ ...r })))
}
</script>

<style scoped>
/* === The words over the scale === */
.rt-marks {
  position: relative;
  height: 0.95rem;
}
.rt-mark {
  position: absolute;
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.45);
  white-space: nowrap;
}

/* === Unified slider (all handles in one track) === */
.unified-slider {
  position: relative;
  height: 40px;
  margin: 0.25rem 0;
}

.slider-track {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  left: 0;
  right: 0;
  height: 20px;
  background: rgb(var(--surface-2-rgb) / 0.8);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  overflow: hidden;
}

.slider-fill {
  position: absolute;
  top: 2px;
  bottom: 2px;
  border-radius: 8px;
  transition: inset-inline-start 0.1s ease, width 0.1s ease;
}

.slider-fill.range-color-0 {
  background: linear-gradient(135deg, rgba(124, 77, 255, 0.5), rgba(101, 31, 255, 0.5));
  box-shadow: 0 0 6px rgba(124, 77, 255, 0.3);
}
.slider-fill.range-color-1 {
  background: linear-gradient(135deg, rgba(0, 188, 212, 0.5), rgba(0, 151, 167, 0.5));
  box-shadow: 0 0 6px rgba(0, 188, 212, 0.3);
}
.slider-fill.range-color-2 {
  background: linear-gradient(135deg, rgba(255, 152, 0, 0.5), rgba(245, 124, 0, 0.5));
  box-shadow: 0 0 6px rgba(255, 152, 0, 0.3);
}
.slider-fill.range-color-3 {
  background: linear-gradient(135deg, rgba(102, 187, 106, 0.5), rgba(67, 160, 71, 0.5));
  box-shadow: 0 0 6px rgba(102, 187, 106, 0.3);
}

/* Handle inputs — overlaid on the track */
.slider-handle {
  position: absolute;
  width: 100%;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  -webkit-appearance: none;
  appearance: none;
  background: transparent;
  margin: 0;
  padding: 0;
  height: 20px;
}

.slider-handle::-webkit-slider-runnable-track {
  height: 20px;
  background: transparent;
  border-radius: 10px;
}
.slider-handle::-moz-range-track {
  height: 20px;
  background: transparent;
  border-radius: 10px;
}

.slider-handle::-webkit-slider-thumb {
  pointer-events: all;
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid white;
  cursor: grab;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
  transition: transform 0.15s ease;
}
.slider-handle::-webkit-slider-thumb:hover { transform: scale(1.2); }
.slider-handle::-webkit-slider-thumb:active { cursor: grabbing; }

.slider-handle::-moz-range-thumb {
  pointer-events: all;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid white;
  cursor: grab;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
}

.handle-color-0::-webkit-slider-thumb { background: linear-gradient(135deg, #7C4DFF, #651FFF); }
.handle-color-0::-moz-range-thumb { background: linear-gradient(135deg, #7C4DFF, #651FFF); }
.handle-color-1::-webkit-slider-thumb { background: linear-gradient(135deg, #00BCD4, #0097A7); }
.handle-color-1::-moz-range-thumb { background: linear-gradient(135deg, #00BCD4, #0097A7); }
.handle-color-2::-webkit-slider-thumb { background: linear-gradient(135deg, #FF9800, #F57C00); }
.handle-color-2::-moz-range-thumb { background: linear-gradient(135deg, #FF9800, #F57C00); }
.handle-color-3::-webkit-slider-thumb { background: linear-gradient(135deg, #66BB6A, #43A047); }
.handle-color-3::-moz-range-thumb { background: linear-gradient(135deg, #66BB6A, #43A047); }

/* === The ranges, as numbers === */
.ranges-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.range-group {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.range-group + .range-group {
  margin-left: 0.15rem;
  padding-left: 0.4rem;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
}

.range-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-size: 0.65rem;
  font-weight: 700;
  color: white;
  flex-shrink: 0;
}

.range-color-0 .range-tag { background: #7C4DFF; }
.range-color-1 .range-tag { background: #00BCD4; }
.range-color-2 .range-tag { background: #FF9800; }
.range-color-3 .range-tag { background: #66BB6A; }

/* Narrower than the 65 px they had in a 900 px document: four ranges plus their
   marks stand in a column of about 300, and a rank runs to four digits. */
.range-input {
  width: 52px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  padding: 0.25rem 0.3rem;
  color: white;
  font-size: 0.75rem;
  font-family: 'Fira Code', 'Consolas', monospace;
  text-align: center;
}

.range-sep {
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.9rem;
}

.remove-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.4);
  border-radius: 50%;
  cursor: pointer;
  font-size: 0.75rem;
  line-height: 1;
}
.remove-btn:hover { color: #ef5350; border-color: rgba(244, 67, 54, 0.3); }

/* `.mini-btn` itself is unscoped in assets/flow-stage.css and reaches in here;
   this is only the square shape the `+` takes. */
.add-btn {
  width: 24px;
  height: 24px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  font-weight: 700;
}
</style>
