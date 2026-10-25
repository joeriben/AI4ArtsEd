<!--
  System Prompts, with Randomness.

  Three columns, three system prompts, ONE written line — and since 2026-08-22 ONE
  temperature for all three. Not one per column: a column here differs from its
  neighbour in its system prompt and in nothing else, and a temperature of its own
  would make every difference readable as the draw instead. The temperature is
  what the whole comparison is run AT, which is why it stands once, above the
  columns, beside the model.

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
-->
<template>
  <div class="cmp-page sp-compare">
    <ShellRun
      :ready="!!userInput.trim() && !isSending"
      :running="isSending"
      :title="t('compare.shared.sendAll')"
      :label="t('latentLab.runLine.answer')"
      :count="answered"
      :total="store.columns.length"
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
          class="clear-btn"
          @click="startNewConversation"
        >
          {{ t('compare.shared.newConversation') }}
        </button>

        <label class="lab-pick-label">{{ t('compare.shared.modelLabel') }}</label>
        <select
          :value="selectedModel"
          class="model-select"
          @change="onModelSelect(($event.target as HTMLSelectElement).value)"
        >
          <option
            v-for="m in chatModels"
            :key="m.id"
            :value="m.id"
            :disabled="!m.available && !m.installable"
          >{{ optionLabel(m) }}</option>
        </select>

        <!-- ONE setting for all three columns. It determines what the run IS,
             which is why it stands with the model and not behind a fold of its
             own. The number stands in the label as well: between two notches
             the handle alone says no 0.7. -->
        <label class="lab-pick-label sp-temp-label">
          {{ t('compare.systemprompt.temperatureLabel') }}
          <b>{{ t('compare.shared.temperatureValue', { v: temperatureText }) }}</b>
        </label>
        <MarkedSlider
          class="sp-temp-slider"
          v-model="temperature"
          :min="TEMPERATURE_MIN"
          :max="TEMPERATURE_MAX"
          :step="0.1"
          :marks="temperatureMarks"
          :disabled="isSending"
          :aria-label="t('compare.systemprompt.temperatureLabel')"
          :value-text="temperatureText"
        />
      </section>

      <!-- 3 columns -->
      <div class="cmp-results sp-columns">
        <div
          v-for="(col, idx) in store.columns"
          :key="idx"
          class="sp-column"
          :class="columnClass(idx)"
        >
          <div class="column-header">
            <div class="preset-row">
              <label class="preset-label">{{ t('compare.systemprompt.presetLabel') }}</label>
              <select
                :value="col.presetId"
                class="preset-select"
                @change="onPresetChange(idx, ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="p in presets" :key="p.id" :value="p.id">{{ t(`compare.systemprompt.presets.${p.id}`) }}</option>
                <option value="custom">{{ t('compare.systemprompt.custom') }}</option>
              </select>
            </div>
            <textarea
              :ref="el => setPromptRef(idx, el)"
              :value="col.systemPrompt"
              class="prompt-textarea"
              :placeholder="t('compare.systemprompt.emptyPrompt')"
              @input="onPromptEdit(idx, ($event.target as HTMLTextAreaElement).value)"
            />
            <!-- Where this prompt is published, and when. It stands AT the
                 prompt and not in a footnote: without its source a system
                 prompt is a claim about a product, and what this column is for
                 is reading a document from one. -->
            <p v-if="sourceOf(col.presetId)" class="prompt-source">
              <a :href="sourceOf(col.presetId)!.source" target="_blank" rel="noopener noreferrer">
                {{ t('compare.systemprompt.publishedOn', { date: sourceOf(col.presetId)!.published }) }}
              </a>
            </p>
          </div>
          <div class="column-messages" :ref="el => setColRef(idx, el)">
            <div
              v-for="msg in col.messages"
              :key="msg.id"
              class="chat-bubble"
              :class="msg.role"
            >
              {{ msg.content }}
            </div>
            <div v-if="colLoading[idx]" class="chat-bubble assistant loading">
              <span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>
            </div>
          </div>
        </div>
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
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { useI18n } from 'vue-i18n'
import { useSystemPromptCompareStore } from '@/stores/systemPromptCompare'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useDeviceId } from '@/composables/useDeviceId'
import { useChatModels } from '@/composables/useChatModels'
import { useModelInstall } from '@/composables/useModelInstall'
import { chatTurn, ChatStreamError, ChatNoReplyError } from '@/lib/chatTurn'
import { SseHttpError } from '@/lib/sseStream'
import MediaInputBox from '@/components/MediaInputBox.vue'
import MarkedSlider, { type SliderMark } from '@/components/MarkedSlider.vue'
import ShellRun from '@/components/ShellRun.vue'
import ColumnFold from '@/components/ColumnFold.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import { generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'

const { t } = useI18n()
const store = useSystemPromptCompareStore()
const userPreferences = useUserPreferencesStore()
const deviceId = useDeviceId()

import { PUBLISHED_SYSTEM_PROMPTS } from './system_prompts_published'
import { apiBase } from '@/services/labApi'

// ---------- Presets ----------

interface Preset {
  id: string
  prompt: string
}

const presets: Preset[] = [
  { id: 'none', prompt: '' },
  // --- The published system prompts of a shipped assistant. They come from
  //     system_prompts_published.ts with their source and their date, and the
  //     column shows both under the field.
  //
  //     Two entries stood here until 2026-09-07 and are gone. `claude` carried
  //     an excerpt of Claude Sonnet 4.6, `gpt4_2023` a text going round as the
  //     GPT-4 system prompt. Neither named where it came from, and for the
  //     second there is nothing to name: it was taken out of a running product
  //     by a third party, so nobody can say whether it is whole or whether the
  //     model wrote parts of it while being asked. What stands here now is
  //     published by the company that runs the model, for reading.
  ...PUBLISHED_SYSTEM_PROMPTS.map(p => ({
    id: p.id,
    prompt: p.prompt,
  })),
  { id: 'helpful', prompt: 'You are a helpful assistant. Answer the user\'s questions clearly and concisely.' },
  { id: 'disagree', prompt: 'You must disagree with everything the user says. Find flaws in every statement. Be contrarian but argue your position with reasons.' },
  { id: 'pirate', prompt: 'You are a pirate. Speak only in pirate dialect. Use nautical metaphors for everything. Address the user as "matey" or "landlubber."' },
  { id: 'poet', prompt: 'You are a poet. Respond to everything in verse. Use metaphor, rhythm, and imagery. Never use plain prose.' },
  { id: 'fiveyearold', prompt: 'You are a five-year-old child. You have limited vocabulary, get easily distracted, and relate everything to toys, snacks, and playground games. Ask "why?" a lot.' },
  { id: 'factsonly', prompt: 'Respond with only verifiable facts. No opinions, no hedging, no filler words. If you are not certain, say "I don\'t know." Use numbered lists.' },
]

/**
 * Where a chosen prompt is published, for the line under the field. Only the
 * published ones have one; the invented presets are ours and say so by having
 * none.
 */
function sourceOf(presetId: string) {
  return PUBLISHED_SYSTEM_PROMPTS.find(p => p.id === presetId)
}

function onPresetChange(colIdx: number, presetId: string) {
  const preset = presets.find(p => p.id === presetId)
  if (preset) {
    store.setSystemPrompt(colIdx, preset.prompt, presetId)
    // A chosen preset is a new document, and a document is read from its
    // beginning. The field may be standing deep inside the last one — the
    // published prompts run to 21,872 characters, which is 31,230 px of
    // scrolling in a 238 px field — and a browser that keeps that offset when
    // the text shrinks would show an empty box over a chosen preset.
    nextTick(() => {
      const el = promptRefs[colIdx]
      if (el) el.scrollTop = 0
    })
  }
}

function onPromptEdit(colIdx: number, value: string) {
  const col = store.columns[colIdx]
  if (!col) return
  const currentPreset = presets.find(p => p.id === col.presetId)
  const newPresetId = (currentPreset && currentPreset.prompt === value) ? col.presetId : 'custom'
  store.setSystemPrompt(colIdx, value, newPresetId)
}

// ---------- Column refs ----------

/** The three prompt fields, so a newly chosen document can be shown from its top. */
const promptRefs: (HTMLTextAreaElement | null)[] = [null, null, null]

function setPromptRef(idx: number, el: unknown) {
  promptRefs[idx] = (el as HTMLTextAreaElement) ?? null
}

const colRefs: (HTMLElement | null)[] = [null, null, null]

function setColRef(idx: number, el: unknown) {
  colRefs[idx] = el as HTMLElement | null
}

function scrollColumn(idx: number) {
  nextTick(() => {
    const el = colRefs[idx]
    if (el) el.scrollTop = el.scrollHeight
  })
}

function scrollAllColumns() {
  for (let i = 0; i < 3; i++) scrollColumn(i)
}

// ---------- Column state ----------

const userInput = ref('')
const selectedModel = ref('')
const isSending = ref(false)

/**
 * How many of the three have answered — what the bar counts while a run is out.
 * The three go out at once, so this counts what has come BACK: a column whose
 * last line is the machine's has answered this round.
 */
const answered = computed(
  () => store.columns.filter(c => c.messages[c.messages.length - 1]?.role === 'assistant').length,
)
const colLoading = ref([false, false, false])
const comparisonContext = ref('')
const showPresetOverlay = ref(false)
// The perspective is at work on the prompt: the symbol that was pressed pulses.
const enriching = ref(false)

// --- Clipboard ---
function copyPrompt() { window.navigator.clipboard.writeText(userInput.value) }
async function pastePrompt() { userInput.value = await window.navigator.clipboard.readText() }
function clearPrompt() { userInput.value = '' }

// --- Interception Preset ---
// What the ring in the corner of the field says when the perspective wrote
// nothing: a refusal, a failure with its status, an empty answer, or no
// connection (composables/useLabRun.ts). Until 2026-10-10 all four ended in
// the console here, and the ring spun and stopped in silence.
const perspectiveError = ref('')

async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  if (!userInput.value.trim()) return

  enriching.value = true
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, userInput.value, deviceId)
    if ('written' in outcome) {
      userInput.value = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (error) {
    perspectiveError.value = generationErrorFor(t, error)
  } finally {
    enriching.value = false
  }
}

const { chatModels , optionLabel } = useChatModels()
const { install } = useModelInstall()

async function onModelSelect(newId: string): Promise<void> {
  const model = chatModels.value.find(m => m.id === newId)
  if (model && !model.available && model.installable) {
    install(newId, model.label).catch((e: any) =>
      console.warn('[sys_prompt_compare] install did not start:', e)
    )
    const prev = selectedModel.value
    selectedModel.value = ''
    await nextTick()
    selectedModel.value = prev
    return
  }
  selectedModel.value = newId
}

const COL_CLASSES = ['col-a', 'col-b', 'col-c'] as const

function columnClass(idx: number): string {
  return COL_CLASSES[idx] ?? 'col-b'
}

// ---------- The one temperature ----------

/**
 * Three fixed offers stood here until 2026-09-08, held as strings because that
 * is what a chip carries. The surface opens at 0.5: the deterministic end makes
 * three system prompts look more alike than they are, the free end more unlike.
 */
const TEMPERATURE_MIN = 0
const TEMPERATURE_MAX = 2
const temperature = ref<number>(0.5)

/**
 * The named places of the axis: the three words the platform gave its former
 * offers, at the values they stood for. The end of the axis carries its number
 * alone — it is the end, and there is no word for it.
 */
const TEMPERATURE_MARKS: { at: number; i18n?: string }[] = [
  { at: 0, i18n: 'compare.temperature.cold' },
  { at: 0.5, i18n: 'compare.temperature.warm' },
  { at: 1, i18n: 'compare.temperature.hot' },
  { at: TEMPERATURE_MAX },
]

const temperatureMarks = computed<SliderMark[]>(() =>
  TEMPERATURE_MARKS.map(m => ({
    value: m.at,
    label: m.i18n ? t(m.i18n) : undefined,
    pct: ((m.at - TEMPERATURE_MIN) / (TEMPERATURE_MAX - TEMPERATURE_MIN)) * 100,
  }))
)

/** The set value, for the label and for a screen reader: 0.5, 1, 1.7 — no 1.0. */
const temperatureText = computed(() => String(Number(temperature.value.toFixed(1))))

// ---------- API ----------

async function callChatWithSystemPrompt(
  message: string,
  history: Array<{ role: string; content: string }>,
  systemPrompt: string
): Promise<string | null> {
  try {
    const data = await chatTurn(`${apiBase()}/api/chat/stream`, {
      message,
      history,
      temperature: temperature.value,
      ...(selectedModel.value ? { model: selectedModel.value } : {}),
      context: {
        system_prompt_compare_mode: true,
        custom_system_prompt: systemPrompt,
        language: userPreferences.language,
        device_id: deviceId,
      },
    })
    return data.reply || null
  } catch (e) {
    // Three endings that this function read as "no reply" while it called the
    // blocking endpoint, and the column showed as such: a turn the server
    // itself ended (a non-2xx JSON body then, an event in the stream now), a
    // refusal before the stream opened (the non-2xx itself), and a stream that
    // stopped without a turn in it. All three keep that wording — with the
    // cause on the console, which is the only spot it was ever legible. A torn
    // connection and an abort throw something else and still reach the caller's
    // error branch, which says something else.
    if (e instanceof ChatStreamError || e instanceof SseHttpError
        || e instanceof ChatNoReplyError) {
      console.error('[SYSPROMPT-COMPARE] chat turn failed:', e)
      return null
    }
    throw e
  }
}

// ---------- Send to all 3 columns ----------

async function sendToAll() {
  const text = userInput.value.trim()
  if (!text || isSending.value) return

  userInput.value = ''
  isSending.value = true

  for (let i = 0; i < 3; i++) {
    store.addMessage(i, 'user', text)
  }
  scrollAllColumns()

  colLoading.value = [true, true, true]

  const promises = store.columns.map(async (col, idx) => {
    try {
      const history = col.messages
        .slice(0, -1)
        .map(m => ({ role: m.role, content: m.content }))
      const reply = await callChatWithSystemPrompt(text, history, col.systemPrompt)
      store.addMessage(idx, 'assistant', reply || t('compare.shared.noResponse'))
    } catch {
      store.addMessage(idx, 'assistant', t('compare.shared.error'))
    } finally {
      colLoading.value[idx] = false
      scrollColumn(idx)
    }
  })

  await Promise.allSettled(promises)
  isSending.value = false

  // What the three columns now hold goes into the page context, where Help
  // reads it.
  updateComparisonContext()
}

// ---------- What Help is told ----------

function updateComparisonContext() {
  const cols = store.columns
  const lastResponses = cols.map((col, i) => {
    const presetName = presets.find(p => p.id === col.presetId)?.id ?? 'custom'
    const promptDesc = col.systemPrompt ? `"${col.systemPrompt.slice(0, 80)}..."` : '(empty)'
    const lastAssistant = [...col.messages].reverse().find(m => m.role === 'assistant')
    return `Column ${i + 1} [${presetName}, prompt=${promptDesc}]: ${lastAssistant?.content || '(no response yet)'}`
  }).join('\n')
  comparisonContext.value = `[System Prompt Comparison Mode — generation_complete]\nThree columns, each with a different system prompt. Same user message, same model, same temperature (T=${temperature.value}) for all three.\nLatest responses:\n${lastResponses}`
}

function startNewConversation() {
  store.clearAll()
}

// ---------- Init ----------

function resolvePresetDefaults() {
  for (let i = 0; i < store.columns.length; i++) {
    const col = store.columns[i]
    if (!col) continue
    if (!col.systemPrompt && col.presetId !== 'none' && col.presetId !== 'custom') {
      // A preset taken out of the list above leaves the column with a selection
      // the field cannot show and with no system prompt at all. The column falls
      // back to none, which is a state this surface has a name for.
      const preset = presets.find(p => p.id === col.presetId)
      if (preset) col.systemPrompt = preset.prompt
      else col.presetId = 'none'
    }
  }
}

onMounted(() => {
  resolvePresetDefaults()
  if (store.hasConversation) {
    scrollAllColumns()
  }
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
    instrumentRuns: comparisonContext.value
      ? [{
          label: `T=${temperature.value} · ${store.columns.map(c => c.presetId ?? 'custom').join(', ')}`,
          text: comparisonContext.value,
        }]
      : [],
  },
  // Held up as a sign while the conversation is closed, and only once the
  // surface has something to interpret — before the first run
  // it would be taken with nothing standing there.
  offer: comparisonContext.value ? { label: t('compare.ask.sign') } : null,
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

/* The axis of this column is 274 px wide and carries four marks, three of them
   with a word. At the component's own 10 % inset each mark box is 47 px, and
   „Unvorhersehbar" falls to THREE hyphenated lines - which lifts its number out
   of the row the other numbers stand in (measured 2026-09-09: its head at
   399 px against 415). At 4 % the box is 55 px, all three words take two lines,
   and the outermost mark still ends 4 px inside the column. A language whose
   word for the far end is longer than the German one will reach three lines
   again; this number is where to look. */
.sp-temp-slider {
  --ms-inset: 4%;
}

/* The axis carries its number in its own label, as the set size of Mean Images
   does: the handle of an axis says the value only where a notch stands. */
.sp-temp-label {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.sp-temp-label b {
  font-weight: 500;
  color: rgba(255, 255, 255, 0.8);
}

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

.clear-btn {
  align-self: flex-start;
  padding: 0.35rem 0.75rem;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.35);
  font-size: 0.72rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.clear-btn:hover {
  border-color: rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.6);
}

/* ---------- 3 columns ---------- */

.sp-columns {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: minmax(0, 1fr);
  gap: 1rem;
  min-height: 0;
}

.sp-column {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: rgb(var(--bg-base-rgb) / 0.6);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  overflow: hidden;
}

/* The head keeps the height its field is pulled to instead of shrinking under
   it: without this a field pulled past the column's height would be cut off by
   the flex layout and paint over the answers under it. Pulled that far the
   stream of answers is what gives way, which is what somebody pulling the field
   that far is asking for, and one pull back returns it. */
.column-header {
  display: flex;
  flex-direction: column;
  flex: 0 0 auto;
  gap: 0.4rem;
  padding: 0.6rem 0.8rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.preset-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.preset-label {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.35);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  flex-shrink: 0;
}

.preset-select {
  flex: 1;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 0.25rem 0.4rem;
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.75rem;
  outline: none;
}

.preset-select option {
  background: var(--surface-2);
  color: rgba(255, 255, 255, 0.85);
}

.prompt-source {
  margin: 4px 0 0;
  font-size: 0.72rem;
  line-height: 1.3;
  color: rgba(255, 255, 255, 0.45);
}

.prompt-source a {
  color: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.prompt-source a:hover {
  color: rgba(255, 255, 255, 0.75);
}

/* The field holds a DOCUMENT — what the maker of a model published as its
   system prompt — and it is there to be read.

   It stood at 0.72 rem once, which is tiny. Nothing
   computed that; it was written into this file, while the platform carries a
   step for monospace text and that step starts at 13 px. A monospace face reads
   smaller than a proportional one at the same size, so 11.5 px here was the
   smallest text on the surface.

   And it had a ceiling of 120 px, which made the grip a token: two pulls and it
   stopped, with the rest of the document behind a scrollbar. The field opens
   at twice that ceiling now and grows as far as it is pulled. */
.prompt-textarea {
  width: 100%;
  height: 240px;
  min-height: 48px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  padding: 0.35rem 0.5rem;
  color: rgba(255, 255, 255, 0.7);
  font-size: var(--flow-fs-mono);
  font-family: monospace;
  line-height: 1.4;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s ease;
}

.prompt-textarea:focus {
  border-color: rgba(255, 255, 255, 0.2);
}

.prompt-textarea::placeholder {
  color: rgba(255, 255, 255, 0.2);
  font-style: italic;
}

/* Column color tints */
.col-a .column-header {
  border-bottom-color: rgba(171, 130, 255, 0.2);
}

.col-a .preset-select {
  border-color: rgba(171, 130, 255, 0.15);
}

.col-b .column-header {
  border-bottom-color: rgba(130, 200, 160, 0.2);
}

.col-b .preset-select {
  border-color: rgba(130, 200, 160, 0.15);
}

.col-c .column-header {
  border-bottom-color: rgba(255, 160, 100, 0.2);
}

.col-c .preset-select {
  border-color: rgba(255, 160, 100, 0.15);
}

.column-messages {
  flex: 1;
  overflow-y: auto;
  padding: 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-height: 0;
}

/* ---------- Chat bubbles (shared) ---------- */

.chat-bubble {
  max-width: 95%;
  padding: 0.5rem 0.7rem;
  border-radius: 10px;
  font-size: var(--flow-fs-body);
  line-height: 1.45;
  word-break: break-word;
}

.chat-bubble.assistant {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.85);
  border-bottom-left-radius: 3px;
}

.chat-bubble.user {
  align-self: flex-end;
  background: rgba(76, 175, 80, 0.12);
  color: rgba(255, 255, 255, 0.9);
  border-bottom-right-radius: 3px;
}

.chat-bubble.loading {
  padding: 0.5rem 0.8rem;
}

.typing-dots span {
  animation: typing 1.2s infinite;
  font-size: 1.1rem;
  color: rgba(255, 255, 255, 0.4);
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
}


/* ---------- Responsive ---------- */

/* A container query, not a window one: the preparing column is 300 px and can
   be folded away, and a window width cannot see that difference.

   The stage puts that column on top at 900 px of work area
   (assets/compare-stage.css), so the three columns already have the full width
   here: (700 - 32 frame - 32 gaps) / 3 = 212 px each at this threshold. Under
   it they stack. */
@container (max-width: 700px) {
  .sp-columns {
    grid-template-columns: 1fr;
  }

  /* Stacked, the row takes the height of its content, so the stream of answers
     needs a bound of its own. */
  .column-messages {
    max-height: 300px;
  }
}
</style>
