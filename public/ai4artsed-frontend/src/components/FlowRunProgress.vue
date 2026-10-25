<!--
  FlowRunProgress - what stands beside the trigger in the shell bar while a run
  is out, and nothing else.

  Every surface once wrote its own readout into that bar, and it came out in
  four grammars: `8 / 15` in Bias Archaeology and in the Coreference test
  (answers), `8 / 15` again in the Default Census with another meaning
  (pictures), `62 %` in the Surrealizer, and two surfaces sent nothing at all.
  A bare pair of numbers says HOW MANY without saying of what. Counting happens
  where there is something to count, with the word for the thing in front of
  the count. This component is that one form
  (docs/ELEMENT_STRUCTURE_REGISTRY.md).

  Two shapes, and which one applies is a fact about the run, not a taste:
   - a COUNT where a run makes a countable number of things, named:
     `Schritt 12 / 25`, `Bild 8 / 15`, `Antwort 8 / 15`.
   - a PERCENTAGE where a run makes ONE thing and only how far it has come is
     known - the Surrealizer returns a single picture.

  A run can outlast its own counting. The Denoising Archaeology is finished
  denoising while its twenty-five pictures are still on their way, and a count
  that stands still reads as stuck. `note` is for that stretch: it stands
  INSTEAD of the count and says what is going on.

  The look is not here: `.lab-prog` is part of the instrument frame and stands
  in `assets/flow-stage.css` with `.lab-main` / `.lab-stage` / `.lab-work`.
-->
<template>
  <div v-if="active && text" class="lab-prog">{{ text }}</div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    /** A run is out. Without it the readout stays away entirely. */
    active?: boolean
    /** The word for what is counted, already translated. */
    label?: string
    /** How many of them are there so far. */
    count?: number
    /** How many there will be; a count needs it, and a 0 keeps it away. */
    total?: number
    /** Where a run makes one thing: 0..100, rounded here. */
    percent?: number
    /**
     * What the line says once there is nothing left to count, already
     * translated. It outranks both shapes for as long as it is set.
     */
    note?: string
  }>(),
  {
    active: false,
    label: undefined,
    count: undefined,
    total: undefined,
    percent: undefined,
    note: undefined,
  },
)

const text = computed(() => {
  if (props.note) return props.note
  if (props.count !== undefined && props.total) {
    const pair = `${props.count} / ${props.total}`
    return props.label ? `${props.label} ${pair}` : pair
  }
  if (props.percent !== undefined) return `${Math.round(props.percent)} %`
  return ''
})
</script>
