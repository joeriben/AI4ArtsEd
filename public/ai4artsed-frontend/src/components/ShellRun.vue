<!--
  ShellRun — the trigger of a surface and the state of its run, together, in the
  middle of the shell bar.

  Seven surfaces once each wrote the same Teleport block by hand, and what
  stood in it drifted: two hung a trigger with no readout at all, and the
  readouts that were there had been four different grammars. Trigger and state
  are ONE thing here, so a surface can no longer put up the one without the
  other. See docs/ELEMENT_STRUCTURE_REGISTRY.md.

  In the bar stands the triangle and, while a run is out, the line that says how
  far it has come. NOTHING else, and no name of the instrument beside it: the
  left of the bar already says where the visitor is, and saying it twice makes
  the second one furniture.

  `steps` is for a surface whose work is two runs in order — Feature Probing
  measures first, then carries a chosen part over. It puts up one triangle per
  run, each with its number in it, and `run` says which was pressed. They come
  from here and not from a second ShellRun, because the bar holds ONE claim per
  surface and a second one would take the place from the first. The readout
  stays one line: `running` says whether any of them is out.

  Which shape the readout takes is `FlowRunProgress`' business and a fact about
  the run: a count where a run makes countable things, a percentage where it
  makes one. A surface that has nothing to count passes neither and the line
  stays away.

  `defer` is not optional: a Teleport resolves its target against the live
  document, and on the app's FIRST render the tree is still detached, so
  `.shell-bar-run` cannot be found. Where there is no shell around the surface
  (an instrument opened at its own address), the Teleport is switched off and
  both stand where the surface put this component.
-->
<template>
  <Teleport v-if="isCurrent" defer to=".shell-bar-run" :disabled="!inShellFrame">
    <template v-if="steps">
      <FlowRunButton
        v-for="(step, i) in steps"
        :key="i"
        :number="i + 1"
        :ready="step.ready"
        :running="step.running"
        :title="step.title"
        @click="emit('run', i)"
      />
    </template>
    <FlowRunButton v-else :ready="ready" :running="running" :title="title" @click="emit('run')" />
    <FlowRunProgress
      :active="running"
      :label="label"
      :count="count"
      :total="total"
      :percent="percent"
      :note="note"
    />
  </Teleport>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import FlowRunButton from '@/components/FlowRunButton.vue'
import FlowRunProgress from '@/components/FlowRunProgress.vue'
import { useShellRunSlot } from '@/composables/useShellRunSlot'

/** One of several runs a surface starts in order, as its numbered triangle. */
export interface ShellRunStep {
  ready: boolean
  running?: boolean
  title?: string
}

withDefaults(
  defineProps<{
    /** Ready to run: bright, clickable. */
    ready?: boolean
    /** A run is out: the triangle breathes and the readout appears. */
    running?: boolean
    /** Hover text on the triangle; without it the button carries none. */
    title?: string
    /** The word for what is counted, already translated. */
    label?: string
    count?: number
    total?: number
    /** Where a run makes ONE thing: 0..100. */
    percent?: number
    /** What the line says once there is nothing left to count, already translated. */
    note?: string
    /** Several runs in order, one numbered triangle each; `ready` and `title` then go unread. */
    steps?: ShellRunStep[]
  }>(),
  {
    ready: false,
    running: false,
    title: undefined,
    label: undefined,
    count: undefined,
    total: undefined,
    percent: undefined,
    note: undefined,
    steps: undefined,
  },
)

/** `step` is the index of the numbered triangle pressed; a single trigger sends none. */
const emit = defineEmits<{ (e: 'run', step?: number): void }>()

const inShellFrame = inject('shellFrame', false)
const isCurrent = useShellRunSlot()
</script>
