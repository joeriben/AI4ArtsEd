<!--
  ModelPicker — which models a measuring instrument compares.

  Four presets, one of them chosen. They are the four questions this platform
  asks of a lineup: what the small models do, what the large ones do, what one
  family does across its sizes, and what ONE family at ONE size did over five
  generations. The last is the only one where the models are base models: over
  five generations the tuning is what changed most and most unevenly, so the
  base model is the closer thing to „the same model, later" (see
  gpu_service/config.py).

  A second row once stood under these four, in which every model went in and
  out on its own. It is gone; there are no chips, presets only: sixteen chips
  took 327 px of a
  column that has 809, and pushed the translation of the case and the box that
  explains it under the window edge. What the four names say is what is being
  compared; a row that has to be scrolled past to reach the case does not say
  it better.

  The catalogue comes from the service, never from a list in here: a model
  identifier is data. Both text-lab instruments use this component — it grew out
  of the row that stood twice, once in each of them.
-->
<template>
  <div class="model-picker">
    <label class="lab-pick-label">{{ t('latentLab.textLab.models.label') }}</label>

    <ChipSelect
      :model-value="chosen"
      :options="presetChoices"
      :columns="2"
      :disabled="disabled"
      @update:model-value="v => applyPreset(v as string)"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import ChipSelect from '@/components/ChipSelect.vue'

const { t } = useI18n()

interface Member { id: string; label: string; vram: number }

const props = defineProps<{
  /** The models to compare, as the run needs them. */
  modelValue: Member[]
  disabled?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [Member[]] }>()

type Scenario = 'qwen' | 'mixed' | 'history'
interface Preset { id: string; description: string; vram_gb: number; params_b?: number }

const SCENARIOS: Scenario[] = ['mixed', 'qwen', 'history']

/** Which models each preset stands for, named the way the service names them. */
const PRESETS: { id: string; i18n: string; note: string; members: [Scenario, string][] }[] = [
  {
    id: 'small',
    i18n: 'latentLab.textLab.models.small',
    note: 'latentLab.textLab.models.smallNote',
    // Phi 3.5 mini is not a member: its tokenizer opens " A" and " B" with the
    // same token, both probes read the answer off that first token, and the
    // service refuses the model with a 422 (services/text_probes.py).
    members: [['mixed', 'gemma'], ['mixed', 'llama'], ['qwen', 'tiny'], ['qwen', 'small']],
  },
  {
    id: 'large',
    i18n: 'latentLab.textLab.models.large',
    note: 'latentLab.textLab.models.largeNote',
    members: [['mixed', 'olmo3'], ['mixed', 'apertus'], ['mixed', 'nemotron'], ['mixed', 'qwen35_9b'], ['mixed', 'gemma4_12b'], ['mixed', 'ministral_14b']],
  },
  {
    id: 'family',
    i18n: 'latentLab.textLab.models.family',
    note: 'latentLab.textLab.models.familyNote',
    members: [['qwen', 'tiny'], ['qwen', 'small'], ['qwen', 'medium'], ['qwen', 'large']],
  },
  {
    id: 'history',
    i18n: 'latentLab.textLab.models.history',
    note: 'latentLab.textLab.models.historyNote',
    members: [['history', 'gen1'], ['history', 'gen2'], ['history', 'gen3'], ['history', 'gen4'], ['history', 'gen5']],
  },
]

const catalogue = ref<Record<Scenario, Record<string, Preset>>>({ qwen: {}, mixed: {}, history: {} })
const chosen = ref('small')

const presetChoices = computed(() =>
  PRESETS.map(p => ({ value: p.id, label: t(p.i18n), title: t(p.note) }))
)

/** The lineup a preset stands for, smallest first. Missing members are skipped:
 *  what the service does not offer is not compared, and saying so is the
 *  service's business, not a gap this row invents a model for. Smallest is
 *  said in parameters (params_b), not in the card the model wants: a maker
 *  that ships FP8 fits more parameters on less card, and the large row
 *  holds one of those. */
function membersOf(preset: typeof PRESETS[number]): Member[] {
  return preset.members
    .map(([scenario, key]) => catalogue.value[scenario]?.[key])
    .filter((p): p is Preset => !!p)
    .sort((a, b) => (a.params_b ?? a.vram_gb) - (b.params_b ?? b.vram_gb))
    .map(p => ({
      id: p.id,
      label: (p.description.split(' - ')[0] ?? p.description).trim(),
      vram: p.vram_gb,
    }))
}

function applyPreset(id: string) {
  const preset = PRESETS.find(p => p.id === id)
  if (!preset) return
  chosen.value = id
  emit('update:modelValue', membersOf(preset))
}

onMounted(async () => {
  const answers = await Promise.all(
    SCENARIOS.map(s => axios.get('/api/text/presets', { params: { scenario: s } }).catch(() => null))
  )
  SCENARIOS.forEach((scenario, i) => {
    catalogue.value[scenario] = answers[i]?.data?.presets ?? {}
  })
  // The lineup a surface opens with is the small one: it is the quickest to
  // run, and every model in it is one a course can also run at home.
  if (!props.modelValue.length) applyPreset('small')
})
</script>

<style scoped>
.model-picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
</style>
