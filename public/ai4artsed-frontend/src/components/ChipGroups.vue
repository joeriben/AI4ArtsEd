<!--
  A choice out of several NAMED groups: one heading, one grid of chips under it,
  and the whole selection handed to every group — so a ceiling counts across all
  of them and something ticked in one is seen by the others.

  One out of all the groups, or several: `multiple` is `ChipSelect`'s own and
  means here what it means there, only that the choice reaches across the
  groups. Singly, exactly one chip in one group stands on.

  The frame is `LanguageChipSelector`'s, which carried it alone from the day it
  was written; the first instrument of the Prompt Interception group hand-rolled
  the same thing a second time on 2026-09-03 (`.ilm-group` / `.ilm-svc`), and
  this is that consolidation (Rule 13). What was a caller's own — WHICH groups,
  what they are called, the line that counts — stays with the caller.

  The heading can carry ONE thing beside the name (`group-aside`): the mark of
  what a group reaches, where a group is a service and the mark is the record of
  its data path. Nothing else goes there; a heading is a name.

  The groups are rendered as SIBLINGS with no box around them, so a column that
  spaces its children spaces the groups too. What that costs is that the look of
  the heading has to be settable from outside, and it is — by variables, not by
  a variant switch. Unset, they give exactly the language selector's heading.
-->
<template>
  <div v-for="group in groups" :key="group.id" class="chip-group">
    <span class="chip-group-label">
      <span class="chip-group-name">{{ group.label }}</span>
      <slot name="group-aside" :group="group" />
    </span>
    <ChipSelect
      :multiple="multiple"
      :model-value="modelValue"
      :options="group.options"
      :columns="columns"
      :min-width="minWidth"
      :max="max"
      :disabled="disabled"
      @update:model-value="v => emit('update:modelValue', v)"
    />
  </div>
</template>

<script setup lang="ts">
import ChipSelect, { type ChipOption } from '@/components/ChipSelect.vue'

export interface ChipGroup {
  /** What the group IS — the service, the category. Never its place. */
  id: string
  /** What it is called, in the reader's language. */
  label: string
  options: ChipOption[]
}

withDefaults(
  defineProps<{
    /** What is on: the one value, or — with `multiple` — the set of them. */
    modelValue: string | string[]
    groups: ChipGroup[]
    /** How many chips fit in a row. */
    columns?: number
    /**
     * How WIDE a chip is at least, in pixels — the other way of asking for
     * the row. Given, the row takes as many fields as fit at that width and
     * `columns` is ignored; see ChipSelect. For a list whose entries differ
     * in length, this is what keeps the longest of them on one line.
     */
    minWidth?: number
    /** At most this many at once, counted across the groups. 0 is no ceiling. */
    max?: number
    /** Several at once, across the groups. `modelValue` is then an array. */
    multiple?: boolean
    disabled?: boolean
  }>(),
  { columns: 4, minWidth: 0, max: 0, multiple: false, disabled: false },
)

const emit = defineEmits<{ 'update:modelValue': [value: string | string[]] }>()
</script>

<style scoped>
.chip-group {
  margin-bottom: var(--chip-group-space, 0.75rem);
}

/* Where a column already spaces its children, the groups want a little more
   between them than between the other controls, and nothing around them. */
.chip-group + .chip-group {
  margin-top: var(--chip-group-step, 0);
}

/* The heading. Its look is settable because the two places that carry it are
   set differently: the language selector's is a small caps line over a wide
   grid, an instrument's is a quiet word in a narrow column with a mark beside
   it. The defaults are the language selector's, character for character. */
.chip-group-label {
  display: var(--chip-group-label-display, block);
  align-items: baseline;
  gap: 6px;
  font-size: var(--chip-group-label-size, 0.72rem);
  text-transform: var(--chip-group-label-case, uppercase);
  letter-spacing: var(--chip-group-label-tracking, 0.5px);
  line-height: var(--chip-group-label-line, inherit);
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: var(--chip-group-label-gap, 0.4rem);
}
</style>
