<!--
  Model Comparison (Transformers Lab): System Prompts with the two axes
  exchanged. It carries the name of the image models' Model Comparison, which
  puts image models side by side as this one puts language models.

  ONE system prompt, in the preparing column, for all three columns, and a model
  per column. A column here differs from its neighbour in its model and in
  nothing else: the message, the system prompt and the randomness are the same
  for all three, which is why all three stand once, at the left.

  Built on 2026-10-27 as a copy of views/compare/system_prompt_comparison.vue.
  What the two have in common is not copied but shared: the column
  (components/ChatColumn.vue), the system-prompt field with its presets and its
  published sources (components/SystemPromptField.vue,
  views/compare/system_prompt_presets.ts), the randomness axis
  (components/RandomnessAxis.vue), and the round that puts the message to the
  three columns (composables/useChatColumns.ts). What is this surface's own is
  the model chooser in each column's head and where the three columns start.

  Every column names its model. The row „Default (Settings)" that System
  Prompts offers is not offered here: it names no model, the server then walks
  its chain of fallbacks, and a column could be answered by a model nobody
  sees — on a surface whose one question is which model answered.
-->
<template>
  <div class="cmp-page spm-compare">
    <ShellRun
      :ready="canSend"
      :running="isSending"
      :title="t('compare.shared.sendAll')"
      :label="t('latentLab.runLine.answer')"
      :count="answered"
      :total="total"
      @run="sendToAll"
    />
    <!-- The preparing column at the left, the three models beside it. Page
         frame, column box and the order of the two come from
         `assets/compare-stage.css`; the handle that folds the column away is
         components/ColumnFold.vue. -->
    <div class="cmp-stage cmp-work" :class="{ folded }">
      <section class="cmp-column cmp-ask col-fold-host" :class="{ folded }">
        <ColumnFold v-model:folded="folded" />

        <!-- The written message stands first: it is what all three columns
             answer, and it is what the visitor comes here to write. -->
        <MediaInputBox
          chrome="bare"
          :placeholder="t('latentLab.textLab.systempromptModels.inputPlaceholder')"
          :value="userInput"
          @update:value="userInput = $event"
          :rows="4"
          :disabled="isSending"
          :show-preset-button="true"
          :preset-busy="enriching"
          @copy="copyPrompt"
          @paste="pastePrompt"
          @clear="clearPrompt"
          @open-preset-selector="showPresetOverlay = true"
        />
        <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>
        <button
          v-if="store.hasConversation"
          class="cmp-new-conversation"
          :disabled="isSending"
          @click="store.clearAll()"
        >
          {{ t('compare.shared.newConversation') }}
        </button>

        <!-- The ONE system prompt all three columns run under, where System
             Prompts has its one model. -->
        <label class="lab-pick-label">{{ t('compare.systemprompt.promptLabel') }}</label>
        <SystemPromptField
          :prompt="store.systemPrompt"
          :preset-id="store.presetId"
          :disabled="isSending"
          @change="store.setSystemPrompt"
        />

        <!-- ONE setting for all three columns. It determines what the run IS,
             which is why it stands with the system prompt and not behind a
             fold of its own. -->
        <RandomnessAxis v-model="temperature" :disabled="isSending" />

        <!-- The list of models never arrived, or arrived without the local
             ones. Without these lines the heads would offer nothing, or only
             what runs elsewhere, and say nothing about why. -->
        <p v-if="loadFailed" class="lab-prep-err quiet">
          {{ t('latentLab.textLab.systempromptModels.modelsUnavailable') }}
        </p>
        <p v-if="gpuServiceUnreachable" class="lab-prep-err quiet">
          {{ t('latentLab.textLab.error.gpuUnreachable') }}
        </p>
      </section>

      <!-- 3 columns, a model in the head of each. -->
      <div class="cmp-results cmp-chat-columns">
        <ChatColumn
          v-for="(col, idx) in store.columns"
          :key="idx"
          :messages="col.messages"
          :loading="!!colLoading[idx]"
          :tint="idx"
        >
          <template #head>
            <div class="cmp-pick-row">
              <label>{{ t('compare.shared.modelLabel') }}</label>
              <select
                :value="col.modelId"
                :disabled="isSending"
                @change="onModelChange(idx, $event.target as HTMLSelectElement)"
              >
                <!-- A column with no model sits the round out. -->
                <option v-if="!col.modelId" value="" disabled>
                  {{ t('latentLab.textLab.systempromptModels.noModel') }}
                </option>
                <!-- A model the column holds and the list does not name: the
                     settings no longer offer it, or the list did not come. The
                     column keeps sending to it, and without this the select
                     would stand blank over it. -->
                <option v-if="!isOffered(col.modelId)" :value="col.modelId">{{ col.modelId }}</option>
                <option
                  v-for="m in offered"
                  :key="m.id"
                  :value="m.id"
                  :disabled="!m.available && !m.installable"
                >{{ optionLabel(m) }}</option>
              </select>
            </div>
          </template>
        </ChatColumn>
      </div>
    </div>

    <!-- Interception Preset Overlay -->
    <InterceptionPresetOverlay
      :visible="showPresetOverlay"
      single
      @close="showPresetOverlay = false"
      @preset-selected="handlePresetSelected"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { useI18n } from 'vue-i18n'
import { useSystemPromptAcrossModelsStore } from '@/stores/systemPromptAcrossModels'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useDeviceId } from '@/composables/useDeviceId'
import { useChatModels } from '@/composables/useChatModels'
import { useModelInstall } from '@/composables/useModelInstall'
import { useModelRegister, lineupMembers } from '@/composables/useModelRegister'
import { useChatColumns } from '@/composables/useChatColumns'
import MediaInputBox from '@/components/MediaInputBox.vue'
import RandomnessAxis, { RANDOMNESS_START } from '@/components/RandomnessAxis.vue'
import ChatColumn from '@/components/ChatColumn.vue'
import SystemPromptField from '@/components/SystemPromptField.vue'
import ShellRun from '@/components/ShellRun.vue'
import ColumnFold from '@/components/ColumnFold.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'

const { t } = useI18n()
const store = useSystemPromptAcrossModelsStore()
const userPreferences = useUserPreferencesStore()
const deviceId = useDeviceId()

// ---------- The one temperature ----------

/** What the whole comparison is run AT (components/RandomnessAxis.vue). It is
 *  kept in the store, with the answers that were drawn at it. */
const temperature = computed<number>({
  get: () => store.temperature ?? RANDOMNESS_START,
  set: (v) => { store.temperature = v },
})

// ---------- The round ----------

// The message, the clipboard, the perspective ring and the round itself are
// System Prompts' as well (composables/useChatColumns.ts). What is this
// surface's own is what a column is sent with: its model.
const {
  userInput,
  isSending,
  colLoading,
  answered,
  total,
  canSend,
  copyPrompt,
  pastePrompt,
  clearPrompt,
  showPresetOverlay,
  enriching,
  perspectiveError,
  handlePresetSelected,
  sendToAll,
} = useChatColumns(store, {
  tag: 'SYSPROMPT-MODELS',
  runs: idx => !!store.columns[idx]?.modelId,
  // The server reads this mode exactly as it reads System Prompts': the system
  // prompt goes out as written, or none at all, with no tools and no thinking
  // (devserver/my_app/routes/chat_routes.py, build_system_prompt). A named
  // model is the only candidate: no fallback answers in its place.
  body: (idx, message, history) => ({
    message,
    history,
    temperature: temperature.value,
    model: store.columns[idx]?.modelId,
    context: {
      llm_model_compare_mode: true,
      custom_system_prompt: store.systemPrompt,
      language: userPreferences.language,
      device_id: deviceId,
    },
  }),
  sentWith: () => ({
    temperature: temperature.value,
    systemPrompt: store.systemPrompt,
    presetId: store.presetId,
    models: store.columns.map(c => c.modelId),
  }),
  afterRound: recordRound,
})

// ---------- The models ----------

const {
  chosenModels, loading, loadFailed, gpuServiceUnreachable, optionLabel, refresh,
} = useChatModels()

/**
 * What a column head offers: the models of this machine and every model of
 * the ONE external provider the settings choose, through that provider. The
 * server builds that list (`chosen_models`, chat_routes.chat_models): the full
 * list offers every provider that has a key here (2026-09-12), one route per
 * model, and a model the chosen provider reaches can stand there under
 * another provider's id. Until the server builds it, the full list.
 */
const offered = chosenModels

/** Whether the head offers this id; '' is the column without a model. */
function isOffered(id: string): boolean {
  return !id || offered.value.some(m => m.id === id)
}


// The list is asked again whenever the surface is built anew, so a provider
// switched in the settings reaches the heads on the way back to this tab and
// not only on the next reload. The first build leaves it to useChatModels,
// which is fetching already.
onMounted(() => {
  if (!loading.value) void refresh()
})
const { install } = useModelInstall()
const register = useModelRegister()

/**
 * A model chosen in a column's head. One that is not on this machine yet is
 * downloaded instead, and the column keeps the model it runs: the select is put
 * back on that one by hand, because its binding has not changed and would not
 * put it back by itself. Keeping it is a choice made by hand as well, so the
 * list that comes back after the download fills nothing in over it.
 */
function onModelChange(idx: number, el: HTMLSelectElement): void {
  const modelId = el.value
  const model = offered.value.find(m => m.id === modelId)
  if (model && !model.available && model.installable) {
    install(modelId, model.label).catch((e: any) =>
      console.warn('[sys_prompt_across_models] install did not start:', e)
    )
    const held = store.columns[idx]?.modelId ?? ''
    el.value = held
    store.setModel(idx, held)
    return
  }
  store.setModel(idx, modelId)
}

/**
 * Where the three columns start: the register's lineup `family`, one maker's
 * model in rising sizes, in the lineup's own order (devserver/config/
 * model_register.json). Which models a lineup names is data, never a list in
 * this file. The family runs on this machine: where it is installed whole,
 * the first press costs nothing and sends nothing away.
 *
 * Both the model list and the register arrive after the surface does, and the
 * lineup needs both — so this waits until the lineup reaches a model, and asks
 * once: a column with no member left has no model until one is chosen, and
 * what a visitor chooses by hand is never overwritten
 * (stores/systemPromptAcrossModels.ts). It watches which models are AVAILABLE,
 * not how many are listed: a local model is listed before it is installed,
 * and an installation that ends changes nothing but that.
 *
 * A column whose model is changed in the middle of a conversation hands the
 * new model the conversation so far, the old model's answers included — as
 * System Prompts hands a column's history on under a changed system prompt.
 */
const FIRST_LINEUP = 'family'

watch(
  [() => offered.value.filter(m => m.available).map(m => m.id).join('\n'), () => register.lineups.value],
  () => {
    if (store.preselected) return
    const members = lineupMembers(FIRST_LINEUP, offered.value)
    if (members.length) store.preselect(members)
  },
  { immediate: true },
)

// ---------- What Help is told ----------

/** What the three columns now hold, for the page context, where Help reads it,
 *  under the settings the round was sent with. */
function recordRound(sent: { temperature: number; systemPrompt: string; presetId: string; models: string[] }) {
  const promptDesc = sent.systemPrompt ? `"${sent.systemPrompt.slice(0, 80)}..."` : '(empty)'
  const lastResponses = store.columns.map((col, i) => {
    const model = sent.models[i]
    if (!model) return `Column ${i + 1}: no model chosen, not asked`
    const lastAssistant = [...col.messages].reverse().find(m => m.role === 'assistant')
    return `Column ${i + 1} [model=${model}]: ${lastAssistant?.content || '(no response yet)'}`
  }).join('\n')
  store.lastRound = {
    label: `T=${sent.temperature} · ${sent.models.map(m => m || '-').join(', ')}`,
    text: `[Model Comparison (Transformers Lab) Mode — generation_complete]\nThree columns, a model chosen per column. Same user message, same system prompt [${sent.presetId}, prompt=${promptDesc}], same temperature (T=${sent.temperature}) for all three.\nLatest responses:\n${lastResponses}`,
  }
}

const pageContextStore = usePageContextStore()

// Which of the instruments is open. The catalogue (platform_items.json) has no
// item for this one yet: it is keyed to this name, and an item carries what a
// place says about itself, which has not been written for this one
// (devserver/my_app/routes/chat_routes.py, ITEM_FOR_VIEW). Until it is, Help is
// told which view is open and what the columns hold.
const pageContext = computed<PageContext>(() => ({
  activeViewType: 'system_prompt_across_models',
  pageContent: {
    inputText: userInput.value,
    instrumentRuns: store.lastRound ? [{ ...store.lastRound }] : [],
  },
  // Held up as a sign while the conversation is closed, and only once the
  // surface has something to interpret — before the first run
  // it would be taken with nothing standing there.
  offer: store.lastRound ? { label: t('compare.ask.sign') } : null,
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onBeforeUnmount(() => {
  pageContextStore.clearContext()
})

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
</script>

<style scoped>
/* The page frame, the column box and the whole order -- preparing column at the
   left, the three models at the right, and how the two stack on a narrow work
   area -- are `assets/compare-stage.css`, down to the three columns
   (`.cmp-chat-columns`), the chooser in each head (`.cmp-pick-row`) and „New
   conversation" (`.cmp-new-conversation`); the column itself is
   components/ChatColumn.vue.

   What is this surface's own: a model's name with its facts („Qwen 3.5 9B
   (local) · Open Weights · klein") is longer than any column is wide, and a
   select takes the width of its longest option unless it is allowed to shrink.
   The preset list of System Prompts keeps its width as it has it. */
.cmp-pick-row > select {
  min-width: 0;
}
</style>
