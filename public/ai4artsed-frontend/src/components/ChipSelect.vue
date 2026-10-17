<template>
  <div
    class="chip-select"
    :class="{ flow: minWidth > 0 }"
    :style="minWidth > 0
      ? { '--chip-min': `${minWidth}px` }
      : { '--chip-columns': String(columns) }"
  >
    <button
      v-for="option in options"
      :key="option.value"
      class="chip-select-option"
      :class="[`tone-${option.tone ?? 'green'}`, { selected: isOn(option.value) }]"
      :disabled="disabled || blocked(option.value)"
      :title="option.title"
      @click="pick(option.value)"
      @pointerenter="onEnter(option, $event)"
      @pointerleave="closeCard"
      @pointerdown="onDown(option, $event)"
      @pointerup="onUp"
      @pointercancel="onUp"
      @focus="onEnter(option, $event)"
      @blur="closeCard"
      @keydown.esc="closeCard"
    >
      <span>{{ option.label }}</span><wbr />
      <span v-if="option.aside" class="chip-select-aside">{{ option.aside }}</span>
    </button>

    <!-- One card for the row. The card itself is the platform's own
         (components/InfoCard.vue); what stands IN it is what a field of models
         has to say (components/InfoCardFacts.vue, the same lines the rows of
         Interception across Models show). -->
    <InfoCard :open="!!shown" :x="x" :y="y" :above="above">
      <InfoCardFacts v-if="shown" :info="shown" />
    </InfoCard>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import InfoCard from '@/components/InfoCard.vue'
import InfoCardFacts from '@/components/InfoCardFacts.vue'
import { useInfoCard } from '@/composables/useInfoCard'

/**
 * One choice out of a handful, laid out as a grid of clickable fields.
 *
 * For choices short enough to be read at a glance and few enough to be seen at
 * once — where a drop-down would hide the options behind a click and say
 * nothing about how many there are. The look is the platform's chip
 * (`LanguageChipSelector`), which is the multi-select, language-specific
 * sibling of this; if a third caller appears, fold that one into this rather
 * than growing a third.
 *
 * One choice, or several. `clearable` lets a click on the chosen field give it
 * back - which is how "not asked" is reached where the caller allows it, and it
 * beats a field labelled "not asked" sitting in the row looking like one of the
 * answers. `multiple` takes an array instead and every field toggles on its
 * own; there is no floor there, an empty selection is a selection.
 *
 * `max` is the CEILING on a multiple selection, folded in here on 2026-08-24
 * when a third caller wanted one (Cultural (Un)Known, at most three models).
 * `LanguageChipSelector` had counted for itself since it was written and now
 * runs on this - the registry said to fold that one in rather than let a third
 * count appear, and this is that moment. Reached, the fields that are NOT on go
 * unselectable and stay visible: dimmed the way any disabled field is, because
 * hiding them would take away the sight of what else there is.
 *
 * Without either, the choice can only move, never empty, which is what a list
 * needs where something has to be picked.
 */
/**
 * What this field stands for, shown beside it while the pointer rests on it or
 * a finger holds it down. On a field of this component four lines at most:
 * what it is called, one line of
 * plain facts, one state with a mark on it, and — where the thing is reached
 * through a service — which one, with what the register records about that
 * service's data path.
 *
 * Deliberately without labels in front of the values and without a heading —
 * „Alibaba · 2026" says itself, and a card that first says what it is says the
 * obvious. What the caller does not know it leaves out; a card is built from
 * what is known, never padded to a fixed shape. Drawn by
 * `components/InfoCardFacts.vue`, here and on the rows of Interception across
 * Models.
 *
 * The Flow's model choice adds what the t2x page's hover card carried (since
 * 2026-09-27, `stars` and `seconds`): quality and speed in five stars, with
 * the labels „Qual." and „Speed" in front as that page had them, and the
 * estimated time of the generation. Two rows of stars without a label would
 * not say which is which.
 */
export interface ChipInfo {
  name: string
  /** One line of plain facts, already joined by the caller. */
  line?: string
  /**
   * One state, marked in one of three steps. The steps carry the colour and
   * nothing else: `full` green, `partial` amber, `none` grey. What they MEAN is
   * the caller's business — here they are only kept apart, in the same two
   * tones the fields themselves use.
   */
  mark?: { level: 'full' | 'partial' | 'none'; text: string }
  /**
   * Through which service the thing is reached, and what the register records
   * about that service's data path (the three states of `DsgvoBadge`). Added
   * 2026-09-12 when the model list began to offer every provider with a key:
   * a route that is offered is a route that is shown.
   */
  route?: { via: string; recorded: boolean | null }
  /**
   * Quality and speed in five stars each, as the t2x hover card showed them
   * (the Flow's model choice, since 2026-09-27): quality is the output chunk's
   * rating, speed follows from its estimated duration. A missing one leaves
   * its line out. Built by `composables/useOutputCards.ts`.
   */
  stars?: { quality?: number; speed?: number }
  /** The estimated time of the generation, in seconds: '12-40'. */
  seconds?: string
}

export interface ChipOption {
  value: string
  label: string
  /**
   * Which side of the row's leading distinction this one is on. Two tones, and
   * they mean whatever the row says they mean - the caller decides, the
   * component only holds them apart. Left unset, everything is green.
   */
  tone?: 'green' | 'amber'
  /**
   * A short id or measurement that belongs to this one and is not its name -
   * held beside the name, in the same size, dimmer. For fields that have to be
   * checked against something as well as read.
   */
  aside?: string
  /**
   * What this one is, in a sentence, on hover. A row of chips names the choices
   * in two or three words each; where those words are a shorthand the reader
   * has not met yet, this is where the long form goes. Added 2026-08-21 with
   * the two text-lab instruments, whose set names („one family", „one size")
   * each carried such a note in the band they came out of.
   */
  title?: string
  /**
   * This one cannot be picked, whatever the rest of the row does. For a field
   * that BELONGS in the list and is not reachable here and now - a model this
   * installation lists and has never installed. It stays visible and dimmed,
   * like a field held back by the ceiling: hiding it would take away the sight
   * of what else there is. Added 2026-09-03 with Interception across Models.
   */
  disabled?: boolean
  /**
   * The card that shows while the pointer rests here. Where `title` is one
   * sentence about what a shorthand means, this is what the thing behind the
   * field IS. Added 2026-09-04 for the model fields, which name a model and say
   * nothing about who made it, when, or whether its weights are open.
   */
  info?: ChipInfo
}

const props = withDefaults(
  defineProps<{
    /** One value, or - with `multiple` - the set of values that are on. */
    modelValue: string | string[]
    options: ChipOption[]
    /** How many fit in a row. */
    columns?: number
    /**
     * How WIDE a field is at least, in pixels — the other way of asking for the
     * row, and the one to use where a list is long and its names are short. The
     * row then holds as many as fit, so the fields keep a readable width instead
     * of each taking half a column: at the reference device's preparation column
     * that is two of them, and on a wide screen six or seven. `columns` is
     * ignored while this stands.
     */
    minWidth?: number
    disabled?: boolean
    /** Clicking the chosen field again clears it. Single choice only. */
    clearable?: boolean
    /** Several at once. `modelValue` is then an array, and every field toggles. */
    multiple?: boolean
    /** At most this many at once, with `multiple`. 0 is no ceiling. */
    max?: number
  }>(),
  { columns: 4, minWidth: 0, disabled: false, clearable: false, multiple: false, max: 0 }
)

// ---------------------------------------------------------------------------
// The card beside a field. The waiting, the long press and the placing are the
// platform's own (`composables/useInfoCard.ts`); what is left here is WHAT a
// field has to say.
// ---------------------------------------------------------------------------

const {
  shown,
  x,
  y,
  above,
  enter: openCard,
  down: pressCard,
  up: releaseCard,
  close: closeCard,
  consumePress,
} = useInfoCard<ChipInfo>()

function onEnter(option: ChipOption, event: Event) { openCard(option.info, event) }
function onDown(option: ChipOption, event: PointerEvent) { pressCard(option.info, event) }
function onUp() { releaseCard() }

const emit = defineEmits<{ 'update:modelValue': [value: string | string[]] }>()

function isOn(value: string): boolean {
  return Array.isArray(props.modelValue)
    ? props.modelValue.includes(value)
    : props.modelValue === value
}

/** As many as there may be are on. */
const atCeiling = computed(
  () =>
    props.multiple &&
    props.max > 0 &&
    Array.isArray(props.modelValue) &&
    props.modelValue.length >= props.max
)

/**
 * What cannot be picked. Whatever holds the rest back, the chosen ones stay
 * clickable: on the ceiling because letting one go is how room is made, and on
 * a field that is itself unreachable because a choice made while it WAS
 * reachable has to be given back. A model ticked here and then gone from the
 * installation would otherwise stand in the selection with no way to take it
 * out — and the run would keep asking for it.
 */
function blocked(value: string): boolean {
  if (isOn(value)) return false
  if (props.options.find((o) => o.value === value)?.disabled) return true
  return atCeiling.value
}

function pick(value: string) {
  // The long press that opened the card ends in a click. It chose nothing.
  if (consumePress()) return
  if (blocked(value)) return
  if (props.multiple) {
    const now = Array.isArray(props.modelValue) ? props.modelValue : []
    emit('update:modelValue', now.includes(value)
      ? now.filter((v) => v !== value)
      : [...now, value])
    return
  }
  const again = props.modelValue === value
  if (again && !props.clearable) return
  emit('update:modelValue', again ? '' : value)
}
</script>

<style scoped>
.chip-select {
  display: grid;
  grid-template-columns: repeat(var(--chip-columns), minmax(0, 1fr));
  gap: 0.35rem;
}

/* Asked for a WIDTH instead of a count: the row takes as many fields as fit and
   the rest go to the next one. A fixed count stretches every field to its share
   of whatever width the column happens to have — two of them across a wide
   preparation column are two hand-broad pills with four words between them.
   `min(100%, …)` is what keeps a container narrower than one field from
   overflowing: the field then takes the whole width rather than running past
   it. */
.chip-select.flow {
  grid-template-columns: repeat(auto-fill, minmax(min(100%, var(--chip-min)), 1fr));
}

/* The two tones. Which is which is the caller's business; here they are only
   kept apart, and they are the same two the checkbox list uses so that a colour
   means the same thing across the columns. */
.tone-green {
  --tone: 76 175 80;
  --tone-text: rgba(160, 220, 160, 0.95);
}

.tone-amber {
  --tone: 255 179 0;
  --tone-text: rgba(255, 210, 120, 0.95);
}

.chip-select-option {
  padding: 0.32rem 0.45rem;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.7);
  font-family: inherit;
  font-size: 0.78rem;
  line-height: 1.3;
  text-align: center;
  /* The field is as wide as its share of the row and no wider, so a name longer
     than that share has to break inside the word rather than run past the
     border. The `wbr` in the template is the other half of this: name and aside
     carry no whitespace between them, so without it the two are one unbreakable
     run and the break would land in the middle of the name while the aside
     still hangs over the edge. */
  overflow-wrap: anywhere;
  cursor: pointer;
  transition: all 0.15s ease;
}

/* Only the unchosen ones light up under the pointer. Left alone, the hover
   rule is the more specific of the two and wins while the pointer rests on the
   field - which is exactly where it is the moment after a click, so the choice
   stayed invisible until the mouse moved away, and merely passing over a
   chosen field wiped its green. */
.chip-select-option:hover:not(:disabled):not(.selected) {
  border-color: rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.08);
}

/* Colour is what "on" looks like. Unlit, a field is grey - the tone used to sit
   on every border at rest, and then on and off were the same picture. Where a
   row's leading distinction has to stay readable while nothing is chosen, the
   `aside` carries it: it keeps its tone whether the field is lit or not. */
.chip-select-option.selected {
  border-color: rgb(var(--tone) / 0.75);
  background: rgb(var(--tone) / 0.14);
  color: rgba(255, 255, 255, 0.95);
}

.chip-select-option.selected:hover:not(:disabled) {
  border-color: rgb(var(--tone) / 0.95);
  background: rgb(var(--tone) / 0.22);
}

/* Same size as the name, so nothing has to be squinted at, and in the row's
   own tone: it says what this field is, not what it is called. */
.chip-select-aside {
  margin-left: 0.35rem;
  color: rgb(var(--tone) / 0.75);
  white-space: nowrap;
}

.chip-select-option:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

/* What stands IN the card is components/InfoCardFacts.vue, with its own rules;
   the card itself is components/InfoCard.vue. */
</style>
