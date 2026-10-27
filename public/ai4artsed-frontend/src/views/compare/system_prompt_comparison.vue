<!--
  System Prompts, with Randomness.

  Three columns, three system prompts, ONE written line — and since 2026-08-22 ONE
  temperature for all three. Not one per column: a column here differs from its
  neighbour in its system prompt and in nothing else, and a temperature of its own
  would make every difference readable as the draw instead. The temperature is
  what the whole comparison is run AT, which is why it stands once, in the
  preparing column beside the model, and in no column head.

  The surface belongs to the Latent Text Lab since the same day. It kept the file
  it was built in; what moved is the category, and a category is not a folder —
  the address does not carry one either (see `SLUGS` in views/latent_lab.vue).

  Randomness is an AXIS (a slider), and it is the parameter of the draw the
  overview's sampling station
  draws: at the end of every step the model holds a probability for every token
  of its vocabulary, and this setting flattens or steepens that distribution
  before one token is drawn from it. The three words the platform gave its
  former fixed offers keep their places on the axis — deterministic at 0,
  balanced at 0.5, unpredictable at 1 — and it runs on to 2, so
  that the range where the output visibly falls apart can be set at all.

  Since 2026-10-27 the column, the system-prompt field in its head and the
  randomness axis are components (components/ChatColumn.vue,
  components/SystemPromptField.vue, components/RandomnessAxis.vue), and the
  round that puts the message to the three columns is
  composables/useChatColumns.ts. Model Comparison (Transformers Lab) stands on
  the same parts with the two axes exchanged: one system prompt for all three columns,
  and a model per column.
-->
<template>
  <div class="cmp-page sp-compare">
    <ShellRun
      :ready="canSend"
      :running="isSending"
      :title="t('compare.shared.sendAll')"
      :label="t('latentLab.runLine.answer')"
      :count="answered"
      :total="total"
      @run="sendToAll"
    />
    <!-- The preparing column at the left, the three system prompts beside it.
         Page frame, column box and the order of the two come from
         `assets/compare-stage.css`; the handle that folds the column away is
         components/ColumnFold.vue. -->
    <div class="cmp-stage cmp-work" :class="{ folded }">
      <section class="cmp-column cmp-ask col-fold-host" :class="{ folded }">
        <ColumnFold v-model:folded="folded" />

        <!-- The written message stands first: it is what all three columns
             answer, and it is what the visitor comes here to write. -->
        <MediaInputBox
          chrome="bare"
          :placeholder="t('compare.systemprompt.inputPlaceholder')"
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

        <label class="lab-pick-label">{{ t('compare.shared.modelLabel') }}</label>
        <select
          :value="store.modelId"
          class="model-select"
          :disabled="isSending"
          @change="onModelSelect($event.target as HTMLSelectElement)"
        >
          <!-- A model the store still holds and the list no longer names —
               it went, or the list did not come. -->
          <option v-if="!isListed(store.modelId)" :value="store.modelId">{{ store.modelId }}</option>
          <option
            v-for="m in chatModels"
            :key="m.id"
            :value="m.id"
            :disabled="!m.available && !m.installable"
          >{{ optionLabel(m) }}</option>
        </select>

        <!-- ONE setting for all three columns. It determines what the run IS,
             which is why it stands with the model and not behind a fold of its
             own. -->
        <RandomnessAxis v-model="temperature" :disabled="isSending" />
      </section>

      <!-- 3 columns. The column and the field in its head are components,
           shared with Model Comparison (Transformers Lab). -->
      <div class="cmp-results cmp-chat-columns">
        <ChatColumn
          v-for="(col, idx) in store.columns"
          :key="idx"
          :messages="col.messages"
          :loading="!!colLoading[idx]"
          :tint="idx"
        >
          <template #head>
            <SystemPromptField
              :prompt="col.systemPrompt"
              :preset-id="col.presetId"
              :disabled="isSending"
              @change="(prompt, presetId) => store.setSystemPrompt(idx, prompt, presetId)"
            />
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
import { computed, watch, onMounted, onBeforeUnmount, ref } from 'vue'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { useI18n } from 'vue-i18n'
import { useSystemPromptCompareStore } from '@/stores/systemPromptCompare'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useDeviceId } from '@/composables/useDeviceId'
import { useChatModels } from '@/composables/useChatModels'
import { useModelInstall } from '@/composables/useModelInstall'
import { useChatColumns } from '@/composables/useChatColumns'
import MediaInputBox from '@/components/MediaInputBox.vue'
import RandomnessAxis, { RANDOMNESS_START } from '@/components/RandomnessAxis.vue'
import ChatColumn from '@/components/ChatColumn.vue'
import SystemPromptField from '@/components/SystemPromptField.vue'
import ShellRun from '@/components/ShellRun.vue'
import ColumnFold from '@/components/ColumnFold.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import { SYSTEM_PROMPT_PRESETS } from './system_prompt_presets'

const { t } = useI18n()
const store = useSystemPromptCompareStore()
const userPreferences = useUserPreferencesStore()
const deviceId = useDeviceId()

const { chatModels, optionLabel, isListed } = useChatModels()
const { install } = useModelInstall()

/**
 * The model chosen in the preparing column. One that is not on this machine
 * yet is downloaded instead, and the three columns keep the model they run:
 * the select is put back on that one by hand, because its binding has not
 * changed and would not put it back by itself.
 */
function onModelSelect(el: HTMLSelectElement): void {
  const newId = el.value
  const model = chatModels.value.find(m => m.id === newId)
  if (model && !model.available && model.installable) {
    install(newId, model.label).catch((e: any) =>
      console.warn('[sys_prompt_compare] install did not start:', e)
    )
    el.value = store.modelId
    return
  }
  store.modelId = newId
}

// ---------- The one temperature ----------

/** What the whole comparison is run AT (components/RandomnessAxis.vue). It is
 *  kept in the store, with the answers that were drawn at it. */
const temperature = computed<number>({
  get: () => store.temperature ?? RANDOMNESS_START,
  set: (v) => { store.temperature = v },
})

// ---------- The round ----------

// The message, the clipboard, the perspective ring and the round itself are
// shared with Model Comparison (Transformers Lab, composables/useChatColumns.ts). What
// is this surface's own is what a column is sent with: its system prompt.
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
  tag: 'SYSPROMPT-COMPARE',
  body: (idx, message, history) => ({
    message,
    history,
    temperature: temperature.value,
    ...(store.modelId ? { model: store.modelId } : {}),
    context: {
      system_prompt_compare_mode: true,
      custom_system_prompt: store.columns[idx]?.systemPrompt ?? '',
      language: userPreferences.language,
      device_id: deviceId,
    },
  }),
  sentWith: () => ({
    temperature: temperature.value,
    columns: store.columns.map(c => ({ presetId: c.presetId, systemPrompt: c.systemPrompt })),
  }),
  afterRound: recordRound,
})

// ---------- What Help is told ----------

/** What the three columns now hold, for the page context, where Help reads it,
 *  under the settings the round was sent with. */
function recordRound(sent: { temperature: number; columns: { presetId: string; systemPrompt: string }[] }) {
  const lastResponses = store.columns.map((col, i) => {
    const was = sent.columns[i] ?? { presetId: 'custom', systemPrompt: '' }
    const presetName = SYSTEM_PROMPT_PRESETS.find(p => p.id === was.presetId)?.id ?? 'custom'
    const promptDesc = was.systemPrompt ? `"${was.systemPrompt.slice(0, 80)}..."` : '(empty)'
    const lastAssistant = [...col.messages].reverse().find(m => m.role === 'assistant')
    return `Column ${i + 1} [${presetName}, prompt=${promptDesc}]: ${lastAssistant?.content || '(no response yet)'}`
  }).join('\n')
  store.lastRound = {
    label: `T=${sent.temperature} · ${sent.columns.map(c => c.presetId ?? 'custom').join(', ')}`,
    text: `[System Prompt Comparison Mode — generation_complete]\nThree columns, each with a different system prompt. Same user message, same model, same temperature (T=${sent.temperature}) for all three.\nLatest responses:\n${lastResponses}`,
  }
}

// ---------- Init ----------

function resolvePresetDefaults() {
  for (let i = 0; i < store.columns.length; i++) {
    const col = store.columns[i]
    if (!col) continue
    if (!col.systemPrompt && col.presetId !== 'none' && col.presetId !== 'custom') {
      // A preset taken out of the list (system_prompt_presets.ts) leaves the column with a selection
      // the field cannot show and with no system prompt at all. The column falls
      // back to none, which is a state this surface has a name for.
      const preset = SYSTEM_PROMPT_PRESETS.find(p => p.id === col.presetId)
      if (preset) col.systemPrompt = preset.prompt
      else col.presetId = 'none'
    }
  }
}

onMounted(() => {
  resolvePresetDefaults()
})
const pageContextStore = usePageContextStore()

// Which of the tabs is open. The catalogue (platform_items.json) is keyed to
// this, and carries what this place says about its own technology.
const pageContext = computed<PageContext>(() => ({
  activeViewType: 'system_prompt_comparison',
  pageContent: {
    inputText: userInput.value,
    // The block that fed the column beside the columns until 2026-08-25 goes
    // to Help unchanged, in the field made for what a surface has produced.
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
/* The page frame, the column box, and the whole order -- preparing column at
   the left, the three system prompts at the right, and how the two stack on a
   narrow work area -- come from `assets/compare-stage.css`, as they do on the
   model comparison and on Language Understanding. What is left here is what
   fills the columns.

   The clearance above the favourites strip comes from the shell this
   instrument is mounted in (`.shell-page`, assets/shell.css, and it is mounted
   nowhere else). It stood here a second time until 2026-09-08 and cost the
   three columns 36 px of height -- measured at 1210x834, where the last column
   ended at 749 with the strip beginning at 797.

   Die Flaeche sitzt im Rahmen, statt ihn zu ueberschreiten. Bis zum 2026-09-02
   stand hier `min-height: 100%`, und die Spalte darunter deckelte sich mit
   `calc(100vh - 440px)` gegen das FENSTER: 394 px beansprucht, 364 vorhanden,
   also standen die drei Spalten 30 px unter der Rahmenkante und die letzte
   Zeile jeder Antwort lag im unsichtbaren Streifen -- sichtbar, solange das
   Gummiband hielt. Gemessen bei 1210x834, 1440x900 und 1024x768: jedes Mal
   30 px, weil das Fenster nicht der Kasten ist, in dem dieses Instrument steht.
   Denselben Weg ist Representation Engineering am 2026-08-26 gegangen. */
/* ---------- The preparing column ---------- */

/* The column lays its children out in one flex column, so the field takes the
   whole width without asking for one. */
.model-select {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 0.4rem 0.6rem;
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.8rem;
  outline: none;
}

.model-select:focus {
  border-color: rgba(76, 175, 80, 0.4);
}

.model-select option {
  background: var(--surface-2);
  color: rgba(255, 255, 255, 0.85);
}

/* „New conversation" and the three columns are `.cmp-new-conversation` and
   `.cmp-chat-columns` (assets/compare-stage.css), shared with Model
   Comparison (Transformers Lab); they stood here until 2026-10-27. */
</style>
