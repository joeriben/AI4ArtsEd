<!--
  The ONE randomness a chat comparison runs at, as an axis with its number in
  its label.

  Lifted out of views/compare/system_prompt_comparison.vue on 2026-10-27, when
  Model Comparison (Transformers Lab) needed the same setting for its three
  columns.
  On both surfaces it is what the whole comparison is run AT, so it stands once,
  in the preparing column, and never per column: a temperature of its own would
  make every difference between two columns readable as the draw instead.

  Randomness is the parameter of the draw the overview's sampling station
  draws: at the end of every step the model holds a probability for every token
  of its vocabulary, and this setting flattens or steepens that distribution
  before one token is drawn from it. The three words the platform gave its
  former fixed offers keep their places on the axis — deterministic at 0,
  balanced at 0.5, unpredictable at 1 — and it runs on to 2, so that the range
  where the output visibly falls apart can be set at all.

  Two roots, label and axis, so that the column's own gap stands between them
  as it did when both were written into the surface.
-->
<template>
  <!-- The number stands in the label as well: between two notches the handle
       alone says no 0.7. -->
  <label class="lab-pick-label temp-label">
    {{ t('compare.systemprompt.temperatureLabel') }}
    <b>{{ t('compare.shared.temperatureValue', { v: valueText }) }}</b>
  </label>
  <MarkedSlider
    class="temp-slider"
    :model-value="modelValue"
    :min="RANDOMNESS_MIN"
    :max="RANDOMNESS_MAX"
    :step="0.1"
    :marks="marks"
    :disabled="disabled"
    :aria-label="t('compare.systemprompt.temperatureLabel')"
    :value-text="valueText"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>

<script lang="ts">
/**
 * Where the axis opens. Three fixed offers stood on System Prompts until
 * 2026-09-08. The surface opens at 0.5: the deterministic end makes three
 * columns look more alike than they are, the free end more unlike.
 */
export const RANDOMNESS_START = 0.5
</script>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkedSlider, { type SliderMark } from '@/components/MarkedSlider.vue'

const props = defineProps<{
  modelValue: number
  disabled?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [value: number] }>()

const { t } = useI18n()

const RANDOMNESS_MIN = 0
const RANDOMNESS_MAX = 2

/**
 * The named places of the axis: the three words the platform gave its former
 * offers, at the values they stood for. The end of the axis carries its number
 * alone — it is the end, and there is no word for it.
 */
const RANDOMNESS_MARKS: { at: number; i18n?: string }[] = [
  { at: 0, i18n: 'compare.temperature.cold' },
  { at: 0.5, i18n: 'compare.temperature.warm' },
  { at: 1, i18n: 'compare.temperature.hot' },
  { at: RANDOMNESS_MAX },
]

const marks = computed<SliderMark[]>(() =>
  RANDOMNESS_MARKS.map(m => ({
    value: m.at,
    label: m.i18n ? t(m.i18n) : undefined,
    pct: ((m.at - RANDOMNESS_MIN) / (RANDOMNESS_MAX - RANDOMNESS_MIN)) * 100,
  }))
)

/** The set value, for the label and for a screen reader: 0.5, 1, 1.7 — no 1.0. */
const valueText = computed(() => String(Number(props.modelValue.toFixed(1))))
</script>

<style scoped>
/* The axis of a preparing column is 274 px wide and carries four marks, three
   of them with a word. At the component's own 10 % inset each mark box is
   47 px, and „Unvorhersehbar" falls to THREE hyphenated lines - which lifts its
   number out of the row the other numbers stand in (measured 2026-09-09: its
   head at 399 px against 415). At 4 % the box is 55 px, all three words take
   two lines, and the outermost mark still ends 4 px inside the column. A
   language whose word for the far end is longer than the German one will reach
   three lines again; this number is where to look. */
.temp-slider {
  --ms-inset: 4%;
}

/* The axis carries its number in its own label, as the set size of Mean Images
   does: the handle of an axis says the value only where a notch stands. */
.temp-label {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.temp-label b {
  font-weight: 500;
  color: rgba(255, 255, 255, 0.8);
}
</style>
