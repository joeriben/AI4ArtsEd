<template>
  <!-- Each of the three instruments of this lab has been a file of its own since
       2026-09-05 (views/latent_lab/audio_synth.vue, mmaudio.vue,
       imagebind_guidance.vue), each laid out in the frame the Latent Lab shares.
       What is left here is the dispatch, the way
       views/latent_lab/image_lab.vue dispatches its own — no panel, no
       instrument, no strip of runs of its own.

       KEPT ALIVE, because leaving an instrument must not throw its work away.
       While the three were one file, only `watch(activeTab)` stopped the
       engines: the sound that had been made, the wavetable frames, the
       dimension offsets, the axis slots, the whole modulation, filter, effects
       and sequencer setting and both prompts survived a switch. Three
       components behind a plain `v-if` unmount instead, and the synth's
       `onUnmounted` disposes eight audio nodes, `looper.dispose()` among them —
       measured 2026-09-05: a prompt and an alpha of 1.50 came back as the
       defaults after one switch and back. `composables/useShellRunSlot.ts` and
       `composables/useInstrumentRuns.ts` both answer
       `onActivated`/`onDeactivated`, so the trigger in the bar and the strip of
       runs still change hands at a switch rather than at a mount. -->
  <KeepAlive>
    <AudioSynth v-if="activeTab === 'synth'" />
    <MMAudio v-else-if="activeTab === 'mmaudio'" />
    <ImageBindGuidance v-else-if="activeTab === 'guidance'" />
  </KeepAlive>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AudioSynth from './audio_synth.vue'
import MMAudio from './mmaudio.vue'
import ImageBindGuidance from './imagebind_guidance.vue'

type TabId = 'synth' | 'mmaudio' | 'guidance'

const props = defineProps<{ tab: string }>()

// The left column owns the choice. The name stays activeTab so the chain of
// v-ifs above — and everything the instruments hang off it — reads unchanged.
const activeTab = computed(() => props.tab as TabId)
</script>
