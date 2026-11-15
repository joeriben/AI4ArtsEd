<template>
  <div class="vla">
    <!-- `defer` is not optional: a Teleport resolves its target against the live
         document, and on the app's FIRST render the tree is still detached, so
         `.shell-bar-run` cannot be found. -->
    <ShellRun
      :ready="canAnalyze"
      :running="isAnalyzing"
      :title="t('compare.vlmAnalysis.analyzeBtn')"
      :label="t('latentLab.runLine.reading')"
      :count="doneCount"
      :total="columns.length"
      @run="startAnalysis"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <!-- The case: ONE picture, ONE reading frame, and the readers that
               get both. Two columns side by side therefore differ in the model
               and in nothing else — the discipline of every comparison here. -->
          <section class="cmp-column vla-case lab-col col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <!-- Die schlanke Form, wie sie die Laborflaechen tragen: die
                 Beschriftung steht als Titel ueber dem Feld, der 2-px-Rahmen
                 der vollen Form faellt weg. Der Bild-Eingang blieb am
                 2026-08-18 als einer von dreien voll, weil ein Feld, in das
                 man eine Datei zieht, den Rahmen als Aufforderung hat; die
                 Aufforderung steht hier in `ImageUploadWidget` selbst. -->
            <MediaInputBox
              chrome="bare"
              :value="uploadedImage ?? ''"
              @update:value="(val: string) => uploadedImage = val || undefined"
              input-type="image"
              :allow-sketch="true"
              :initial-image="uploadedImage"
              @image-uploaded="onImageUploaded"
              @image-removed="onImageRemoved"
              @copy="() => {}"
              @paste="() => {}"
              @clear="onImageRemoved"
            />

            <!-- The platform's standard pair: the list offers the ready
                 reading frames, the field under it holds what runs and stays
                 writable — a frame of one's own is a reading like any other,
                 and what the models are asked stands there to be read. -->
            <label class="lab-pick-label">{{ t('compare.vlmAnalysis.perspectiveLabel') }}</label>
            <PromptExamples
              :items="frameExamples"
              :current="analysisPrompt"
              :disabled="isAnalyzing"
              @pick="applyFrame"
            />
            <MediaInputBox
              chrome="bare"
              v-model:value="analysisPrompt"
              input-type="text"
              :rows="5"
              :is-filled="!!analysisPrompt"
              :disabled="isAnalyzing"
              :placeholder="t('compare.vlmAnalysis.freePromptPlaceholder')"
              :show-preset-button="true"
              :preset-busy="enriching"
              @copy="copyPrompt"
              @paste="pastePrompt"
              @clear="analysisPrompt = ''"
              @open-preset-selector="showPresetOverlay = true"
            />
            <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>

            <!-- Two lineups from the register (model_register.json), as on
                 Interception across Models: three makers at one size, and one
                 family over its sizes. Headed and laid out as the sets of
                 Model Comparison. The single readers stay under them; a hand
                 that changes them leaves the lineup, and its chip goes dark. -->
            <label class="lab-pick-label">{{ t('compare.setsLabel') }}</label>
            <ChipSelect
              :model-value="lineupInForce"
              :options="lineupChoices"
              :columns="2"
              :disabled="isAnalyzing"
              @update:model-value="v => applyLineup(v as string)"
            />

            <label class="lab-pick-label">{{ t('compare.vlmAnalysis.modelsLabel') }}</label>
            <div class="vlm-chips">
              <template v-for="vlm in orderedVlmModels" :key="vlm.id">
                <label
                  v-if="vlm.available"
                  class="vlm-chip"
                  :class="{ active: selectedModels.includes(vlm.id) }"
                >
                  <input type="checkbox" :value="vlm.id" v-model="selectedModels" class="vlm-chip-input" />
                  <span class="vlm-chip-label">{{ vlmLabel(vlm) }}</span>
                </label>
                <button
                  v-else-if="vlm.installable"
                  type="button"
                  class="vlm-chip vlm-chip-install"
                  :disabled="installActive"
                  @click="triggerInstall(vlm.id, vlm.label)"
                >
                  <span class="vlm-chip-label">
                    {{ vlmLabel(vlm) }}
                    <span class="vlm-chip-install-cta">
                      ⤓ {{ t('compare.shared.install.downloadCta', { mb: vlm.approxDownloadMb }) }}
                    </span>
                  </span>
                </button>
                <label v-else class="vlm-chip disabled">
                  <span class="vlm-chip-label">
                    {{ vlmLabel(vlm) }}<span class="vlm-chip-unavailable"> {{ t('compare.shared.modelNotDownloaded') }}</span>
                  </span>
                </label>
              </template>
              <span v-if="!vlmLoading && vlmModels.length === 0" class="vlm-empty">
                {{ t('compare.vlmAnalysis.noModelsInstalled') }}
              </span>
            </div>

            <!-- The explanation box at the foot of the preparing column, the
                 platform's `.lab-note` (docs/ELEMENT_STRUCTURE_REGISTRY.md). Its
                 heading is the menu title of this surface, its text is
                 `compare.vlmAnalysis.noteBody`, cut into paragraphs at the blank line,
                 and the titles it cites stand under it in LabReferences. -->
            <aside class="lab-note">
              <h3>{{ t('compare.tabs.vlm-analysis') }}</h3>
              <p
                v-for="(para, i) in t('compare.vlmAnalysis.noteBody').split('\n\n')"
                :key="i"
              >{{ para }}</p>
              <LabReferences
                :title="t('compare.vlmAnalysis.referencesTitle')"
                :items="REFERENCES"
                flat
              />
            </aside>
          </section>

          <!-- One column per reader, all of them the same width: what is read
               across is the DIFFERENCE between the readings, so no column may
               be wider than another. Before the first press the chosen readers
               already stand there, darkened, with their heads — an empty
               surface says nothing about what a press would do. -->
          <section class="lab-plot">
            <div class="lab-grid" :style="{ '--lab-grid-cols': columns.length }">
              <div
                v-for="col in columns"
                :key="col.model"
                class="lab-grid-col lab-readcol"
                :class="{ 'is-preview': col.state === 'preview', 'is-waiting': col.state === 'waiting' }"
              >
                <div class="lab-readcol-head">
                  <span class="lab-readcol-name">{{ col.label }}</span>
                  <span v-if="col.latency != null" class="lab-readcol-time">{{ col.latency }}s</span>
                  <span v-else-if="col.state === 'active'" class="typing-dots"><span>.</span><span>.</span><span>.</span></span>
                  <span v-else-if="col.state === 'waiting'" class="lab-readcol-wait">{{ t('compare.vlmAnalysis.waiting') }}</span>
                </div>
                <!-- The reading scrolls in its own column. A surface that grew
                     with the longest of them would push the fourth reader below
                     the window, and reading them against each other is the
                     whole point of standing them side by side. -->
                <div class="lab-readcell">
                  <p v-if="col.description" class="vla-reading">{{ col.description }}</p>
                  <p v-if="col.note" class="vla-note">{{ col.note }}</p>
                  <p v-if="col.error" class="vla-error">{{ col.error }}</p>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>

    <InterceptionPresetOverlay
      :visible="showPresetOverlay"
      single
      @close="showPresetOverlay = false"
      @preset-selected="handlePresetSelected"
    />
  </div>
</template>

<script setup lang="ts">
import ColumnFold from '@/components/ColumnFold.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { useI18n } from 'vue-i18n'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import ShellRun from '@/components/ShellRun.vue'
import ChipSelect from '@/components/ChipSelect.vue'
import { useVlmModels, type VlmModelOption } from '@/composables/useVlmModels'
import { bareName, fillableLineup, isLocalModel, lineupMembers, useModelRegister } from '@/composables/useModelRegister'
import { useDeviceId } from '@/composables/useDeviceId'
import { useModelInstall } from '@/composables/useModelInstall'
import { READING_FRAMES, type ReadingFrame } from '@/data/readingFrames'
import { readSseFrames } from '@/lib/sseStream'
import { safetyBlockMessageKey, safetyBlockOf } from '@/composables/useGenerationStream'
import { useSafetyEventStore } from '@/stores/safetyEvent'
import { generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { apiBase } from '@/services/labApi'

const { t, locale } = useI18n()

/**
 * The titles the explanation box cites: two architectures of image-reading
 * models, the image encoder one of them projects from, and two measurements
 * of what captioning models write.
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'Li et al. (2023)',
    title: '"BLIP-2: Bootstrapping Language-Image Pre-training with Frozen Image Encoders and Large Language Models"',
    venue: 'ICML 2023, PMLR 202, 19730–19742',
    doi: 'https://arxiv.org/abs/2301.12597',
  },
  {
    authors: 'Liu et al. (2023)',
    title: '"Visual Instruction Tuning"',
    venue: 'NeurIPS 2023',
    doi: 'https://arxiv.org/abs/2304.08485',
  },
  {
    authors: 'Radford et al. (2021)',
    title: '"Learning Transferable Visual Models From Natural Language Supervision"',
    venue: 'ICML 2021, PMLR 139, 8748–8763',
    doi: 'https://arxiv.org/abs/2103.00020',
  },
  {
    authors: 'Rohrbach et al. (2018)',
    title: '"Object Hallucination in Image Captioning"',
    venue: 'EMNLP 2018',
    doi: 'https://arxiv.org/abs/1809.02156',
  },
  {
    authors: 'Zhao, Wang & Russakovsky (2021)',
    title: '"Understanding and Evaluating Racial Biases in Image Captioning"',
    venue: 'ICCV 2021',
    doi: 'https://arxiv.org/abs/2106.08503',
  },
]

// --- VLM Models (fetched dynamically from backend) ---
const { vlmModels, loading: vlmLoading } = useVlmModels()

// --- Install handler ---
const { install, isActive: installActive } = useModelInstall()

async function triggerInstall(alias: string, label: string): Promise<void> {
  try {
    await install(alias, label)
  } catch (e: any) {
    console.warn('[vlm_analysis] install did not start:', e)
  }
}

// --- The reading frames on offer ---
// The list belongs to the PAGE and the field holds what runs: choosing writes
// the frame's wording into the field, and it stays writable from there.
//
// WHICH frames there are is the platform's (`data/readingFrames.ts`, shared with
// the flow board and with Perspectives on a Template since 2026-09-04); the
// ORDER is this page's own and stays here, and so does `neutral`, whose wording
// lives on this page rather than in the backend. Typing the order against the
// shared list is what keeps the two from drifting apart again.
// Where each of the shared frames stands here. Written as a place PER FRAME
// rather than as a list of frames: the key set is the shared list itself, so a
// frame added there and not placed here fails to compile, and one removed there
// leaves a place with nothing to give.
const FRAME_PLACE: Record<ReadingFrame, number> = {
  descriptive: 0,
  bildwissenschaftlich: 1,
  bildungstheoretisch: 2,
  ethisch: 3,
  kritisch: 4,
}
const FRAME_ORDER: readonly ReadingFrame[] = [...READING_FRAMES].sort(
  (a, b) => FRAME_PLACE[a] - FRAME_PLACE[b],
)
const FRAMES = ['neutral', ...FRAME_ORDER] as const

// The one frame whose wording lives here rather than in the backend config.
const NEUTRAL_PROMPT = 'Describe this image in 2-3 sentences. Focus on subject, composition, colors, and style.'

const framePrompts = ref<Record<string, string>>({})

/** Only the frames whose wording actually arrived stand in the list: an entry
 *  that writes nothing into the field would offer a reading that has none. */
const frameExamples = computed(() =>
  FRAMES
    .filter(id => framePrompts.value[id])
    .map(id => ({ id, label: t(`compare.vlmAnalysis.perspectives.${id}`), fill: [framePrompts.value[id]!] }))
)

/** Which frame the field is holding, for what Help is told. Written over by
 *  hand, it is a reading of one's own and says so. */
const frameLabel = computed(() => {
  const hit = frameExamples.value.find(f => f.fill[0] === analysisPrompt.value)
  return hit ? hit.label : t('compare.vlmAnalysis.perspectives.free')
})

function applyFrame(item: { fill: string[] }): void {
  analysisPrompt.value = item.fill[0] ?? ''
}

async function loadFramePrompts(): Promise<void> {
  const entries = await Promise.all(FRAMES.map(async id => {
    if (id === 'neutral') return [id, NEUTRAL_PROMPT] as const
    try {
      const resp = await fetch(
        `${apiBase()}/api/schema/compare/analysis-prompt?perspective=${id}&lang=${locale.value}`)
      if (!resp.ok) return [id, ''] as const
      const data = await resp.json()
      return [id, (data.prompt as string) || ''] as const
    } catch {
      return [id, ''] as const
    }
  }))
  framePrompts.value = Object.fromEntries(entries.filter(([, prompt]) => prompt))
  if (!analysisPrompt.value) analysisPrompt.value = framePrompts.value.neutral ?? ''
}

onMounted(loadFramePrompts)

// The perspective in the field, as every prompt field on an instrument surface
// carries it: it rewrites what stands there — here the instruction the readers
// are given, so a frame can be pushed towards a way of looking before it runs.
const deviceId = useDeviceId()
const showPresetOverlay = ref(false)
const enriching = ref(false)

// What the ring in the corner of the field says when the perspective wrote
// nothing: a refusal, a failure with its status, an empty answer, or no
// connection (composables/useLabRun.ts). Until 2026-10-10 all four ended in
// the console here, and the ring spun and stopped in silence.
const perspectiveError = ref('')

async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  if (!analysisPrompt.value.trim()) return

  enriching.value = true
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, analysisPrompt.value, deviceId)
    if ('written' in outcome) {
      analysisPrompt.value = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (error) {
    perspectiveError.value = generationErrorFor(t, error)
  } finally {
    enriching.value = false
  }
}

async function copyPrompt(): Promise<void> {
  try { await navigator.clipboard.writeText(analysisPrompt.value) } catch { /* denied */ }
}

async function pastePrompt(): Promise<void> {
  try { analysisPrompt.value = await navigator.clipboard.readText() } catch { /* denied */ }
}

// --- State ---
const uploadedImage = ref<string | undefined>(undefined)
const imagePath = ref<string | null>(null)
/** What the models are asked. A frame writes it, a hand may rewrite it. */
const analysisPrompt = ref('')
const selectedModels = ref<string[]>([])

// The lineups this surface offers, in the order of their chips. Which models
// each one stands for is data (devserver/config/model_register.json); a member
// this installation does not offer is left out rather than replaced.
const LINEUPS = ['sameSize', 'family'] as const
const DEFAULT_LINEUP = 'sameSize'

/** The readers as the lineups are written: under the register's bare name. */
const lineupList = computed(() =>
  vlmModels.value.map(m => ({ id: m.id, register: bareName(m.id), available: m.available })),
)

function membersOf(id: string): string[] {
  return lineupMembers(id, lineupList.value)
}

const lineupChoices = computed(() =>
  LINEUPS.map(id => ({
    value: id,
    label: t(`compare.vlmAnalysis.lineups.${id}`),
    title: t(`compare.vlmAnalysis.lineups.${id}Note`),
    disabled: membersOf(id).length === 0,
  })),
)

/** The lineup whose members are exactly the chosen readers, '' for a choice
 *  made by hand. */
const lineupInForce = computed(() =>
  LINEUPS.find(id => {
    const members = membersOf(id)
    return members.length > 0 &&
      members.length === selectedModels.value.length &&
      members.every(m => selectedModels.value.includes(m))
  }) ?? '',
)

function applyLineup(id: string): void {
  const members = membersOf(id)
  if (members.length) selectedModels.value = members
}

// The surface opens on ONE lineup of three, not on every reader installed:
// ten readings side by side are a catalogue, and each of them costs a load.
// The reader list and the register arrive separately, so this waits until a
// lineup can be filled, and fills it once.
let preselected = false
watch(() => membersOf(fillableLineup(DEFAULT_LINEUP, lineupList.value, LINEUPS)), (members) => {
  if (preselected || members.length === 0) return
  preselected = true
  if (selectedModels.value.length === 0) selectedModels.value = members
}, { immediate: true })
const isAnalyzing = ref(false)
const activeModelIdx = ref(-1)
const comparisonContext = ref('')

interface AnalysisResult {
  model: string
  description: string
  latency_s: number | null
  loading: boolean
  // What went wrong on the way here -- a broken connection, lost pieces, a
  // model that did not answer.
  error: string | null
  // What the MODEL did: it ran out of context, or it started repeating itself
  // and was stopped. Not a failure of the page, and shown as what it is.
  note: string | null
}

const results = ref<AnalysisResult[]>([])
const safetyStore = useSafetyEventStore()

/** What stands in the columns: the readings once a press has been made, and
 *  before that the chosen readers as darkened heads over empty cells. */
interface ReadingColumn {
  model: string
  label: string
  latency: number | null
  description: string
  note: string | null
  error: string | null
  state: 'preview' | 'active' | 'waiting' | 'done' | 'error'
}

const columns = computed<ReadingColumn[]>(() => {
  if (results.value.length === 0) {
    return selectedInListOrder.value.map(model => ({
      model,
      label: getModelLabel(model),
      latency: null,
      description: '',
      note: null,
      error: null,
      state: 'preview' as const,
    }))
  }
  return results.value.map((r, idx) => ({
    model: r.model,
    label: getModelLabel(r.model),
    latency: r.latency_s,
    description: r.description,
    note: r.note,
    error: r.error,
    state: r.error
      ? ('error' as const)
      : r.loading
        ? (idx === activeModelIdx.value ? ('active' as const) : ('waiting' as const))
        : ('done' as const),
  }))
})

/** For the counter in the bar: readings that are finished, however they ended. */
const doneCount = computed(() => results.value.filter(r => !r.loading).length)

const canAnalyze = computed(() => {
  if (!imagePath.value) return false
  if (selectedModels.value.length === 0) return false
  if (!analysisPrompt.value.trim()) return false
  return true
})

// A model is offered under the line every list of language models on the
// platform gives it (useModelRegister.modelLabel).
const register = useModelRegister()
function vlmLabel(m: VlmModelOption): string {
  return register.modelLabel(
    m.id, m.label, locale.value,
    isLocalModel(m.id) ? t('compare.shared.localModel') : '',
  )
}

/** In the order every list of models offers them in (useModelRegister.ordered). */
const orderedVlmModels = computed(() => register.ordered(
  vlmModels.value,
  m => ({ local: isLocalModel(m.id), key: m.id, label: vlmLabel(m) }),
  locale.value,
))

/** The chosen readers in that order: the columns and the run follow it, as
 *  the chips above them do. One the list no longer names stands at the end. */
const selectedInListOrder = computed(() => [
  ...orderedVlmModels.value.map(m => m.id).filter(id => selectedModels.value.includes(id)),
  ...selectedModels.value.filter(id => !vlmModels.value.some(m => m.id === id)),
])

function getModelLabel(modelId: string): string {
  const m = vlmModels.value.find(v => v.id === modelId)
  return m ? vlmLabel(m) : modelId
}

function onImageUploaded(data: { image_path: string; preview_url: string }) {
  imagePath.value = data.image_path
  uploadedImage.value = data.preview_url
  // The readings standing in the columns were made of the picture that has
  // just been replaced, and next to the new one they read as its readings.
  // They go with it. A reading still being written keeps its place, because
  // the stream is writing into these very cards.
  if (!isAnalyzing.value) results.value = []
}

function onImageRemoved() {
  imagePath.value = null
  uploadedImage.value = undefined
}


/**
 * Fill one card while the model is still writing it.
 *
 * The backend hands the reading over piece by piece; the frames are found by
 * the platform's own reader (lib/sseStream), and the events inside them are
 * token / done / error / blocked. A card that stops without any of them has lost its
 * connection mid-sentence -- what arrived stays, and the card says so.
 */
async function readReadingStream(
  body: ReadableStream<Uint8Array>,
  idx: number,
): Promise<void> {
  const card = () => results.value[idx]!

  try {
    // The response was opened by the caller, which reads off the content type
    // whether a stream or a JSON error came back; from here on there is only
    // framing, so this takes the stream rather than posting for one.
    for await (const frame of readSseFrames<any>(body)) {
      const ev = frame.data
      if (ev.type === 'token') {
        card().description += ev.text
      } else if (ev.type === 'done') {
        card().latency_s = ev.latency_s ?? null
        card().loading = false
        // A reading counts as finished only if the model came to its own end
        // AND everything that was sent arrived. Counted in characters on both
        // sides (the spread iterates code points, as Python's len does).
        if (ev.finish_reason === 'repetition') {
          card().note = t('compare.vlmAnalysis.readingLooped')
        } else if (ev.finish_reason === 'length') {
          card().note = t('compare.vlmAnalysis.readingHitCeiling')
        } else if (typeof ev.char_count === 'number' &&
                   [...card().description].length !== ev.char_count) {
          card().error = t('compare.vlmAnalysis.readingIncomplete')
        }
        // Counted first, trimmed after: the card is pre-wrap, and a reading
        // that opens with two newlines would start with two empty lines.
        card().description = card().description.trim()
      } else if (ev.type === 'error') {
        card().error = ev.error || t('generationError.unknown')
        card().loading = false
      } else if (ev.type === 'blocked') {
        // A paragraph the check held back ends the reading: what passed before
        // it stays, and the card says why the rest does not come.
        const block = safetyBlockOf(ev)
        card().error = t(block ? safetyBlockMessageKey(block) : 'safetyBlocked.generic')
        card().description = card().description.trim()
        card().loading = false
      }
    }
  } catch {
    // The connection died mid-reading. Handled below like any other card that
    // stops without a closing event -- the text that arrived is kept.
  }

  if (card().loading) {
    card().loading = false
    card().error = t('compare.vlmAnalysis.readingBrokeOff')
  }
}

async function startAnalysis() {
  if (!canAnalyze.value || isAnalyzing.value) return

  isAnalyzing.value = true
  // Reset — what Help reads belongs to the run that is starting.
  comparisonContext.value = ''

  const prompt = analysisPrompt.value.trim()
  const models = [...selectedInListOrder.value]  // Snapshot — won't change mid-loop

  // Initialize result cards with loading state
  results.value = models.map(model => ({
    model,
    description: '',
    latency_s: null,
    loading: true,
    error: null,
    note: null,
  }))

  // Sequential execution — must swap VLMs one at a time (VRAM)
  for (let idx = 0; idx < models.length; idx++) {
    const model = models[idx]!
    activeModelIdx.value = idx
    try {
      const resp = await fetch(`${apiBase()}/api/schema/compare/analyze-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_path: imagePath.value,
          model,
          prompt,
          // Hand the reading over as it is written. Everything that goes wrong
          // before the first word still comes back as JSON, so which of the two
          // arrived is read off the content type.
          stream: true,
        }),
      })

      if ((resp.headers.get('content-type') || '').includes('text/event-stream') && resp.body) {
        await readReadingStream(resp.body, idx)
        continue
      }

      const data = await resp.json()
      const refused = resp.status === 403 ? safetyBlockOf(data) : null
      if (refused?.checkpoint === 'intake') {
        // The instruction itself was refused, and every further model would be
        // asked the same: the run stops, every card left says why, and the
        // companion explains.
        const said = t(safetyBlockMessageKey(refused))
        for (let rest = idx; rest < models.length; rest++) {
          results.value[rest] = {
            model: models[rest]!,
            description: '',
            latency_s: null,
            loading: false,
            error: said,
            note: null,
          }
        }
        safetyStore.reportBlock(refused)
        break
      }
      if (refused) {
        // This model's reading was held back at the result; the next model
        // reads the picture as before.
        results.value[idx] = {
          model,
          description: '',
          latency_s: null,
          loading: false,
          error: t(safetyBlockMessageKey(refused)),
          note: null,
        }
        continue
      }
      if (data.status === 'success') {
        results.value[idx] = {
          model,
          description: data.description,
          latency_s: data.latency_s,
          loading: false,
          error: null,
          note: null,
        }
      } else {
        results.value[idx] = {
          model,
          description: '',
          latency_s: null,
          loading: false,
          error: data.error || t('generationError.unknown'),
          note: null,
        }
      }
    } catch (e: any) {
      results.value[idx] = {
        model,
        description: '',
        latency_s: null,
        loading: false,
        error: e.message || 'Connection error',
        note: null,
      }
    }
  }
  isAnalyzing.value = false
  activeModelIdx.value = -1

  // Build comparison context for Help — only if >= 2 models succeeded
  // Text alone is not a reading: a card can carry a fragment plus the note that
  // it stopped, and a fragment is not something to compare like the others.
  const successful = results.value.filter(r => r.description && !r.error && !r.note)
  if (successful.length >= 2) {
    const descriptions = successful
      .map(r => `[${getModelLabel(r.model)} (${r.latency_s}s)]\n${r.description}`)
      .join('\n\n')
    const failed = results.value.filter(r => r.error)
    const failNote = failed.length > 0
      ? `\n\nFailed models: ${failed.map(r => getModelLabel(r.model)).join(', ')}`
      : ''
    // A model that ran out of context or looped is not a failure to hide: the
    // page context carries what it did, so it can be talked about.
    const stopped = results.value.filter(r => r.note)
    const stoppedNote = stopped.length > 0
      ? `\n\nStopped mid-reading (kept, but not comparable): ${stopped
          .map(r => `${getModelLabel(r.model)} — ${r.note}`)
          .join(' | ')}`
      : ''
    comparisonContext.value = `generation_complete\n\nReading frame: ${frameLabel.value}\n\n${descriptions}${failNote}${stoppedNote}`
  }
}
const pageContextStore = usePageContextStore()

// Which of the tabs is open. The catalogue (platform_items.json) is keyed to
// this, and carries what this place says about its own technology.
const pageContext = computed<PageContext>(() => ({
  activeViewType: 'vlm_analysis_comparison',
  pageContent: {
    // The block that fed the column beside the readings until 2026-08-23 goes
    // to Help now, in the field made for what a surface has produced.
    instrumentRuns: comparisonContext.value
      ? [{
          label: `${results.value.map(r => getModelLabel(r.model)).join(', ')} · ${frameLabel.value}`,
          text: comparisonContext.value,
        }]
      : [],
  },
  // Held up as a sign while the conversation is closed, and only once the
  // surface has something to interpret.
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
/* The frame, the proportion, the counter and the labels above the controls are
   shared — assets/flow-stage.css, `.lab-main` / `.lab-stage` / `.lab-work` /
   `.lab-prog` / `.lab-pick-label`. What stands here is what only this
   instrument does. */
.vla { display: flex; flex-direction: column; height: 100%; min-height: 0; }

.vla-case { gap: 10px; overflow-y: auto; }


.vlm-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.vlm-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.6rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.vlm-chip:hover {
  background: rgba(255, 255, 255, 0.08);
}

.vlm-chip.active {
  background: rgba(76, 175, 80, 0.15);
  border-color: rgba(76, 175, 80, 0.4);
}

.vlm-chip.disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.vlm-chip.disabled:hover {
  background: rgba(255, 255, 255, 0.04);
}

.vlm-chip-install {
  font: inherit;
  color: inherit;
  background: rgba(76, 175, 80, 0.06);
  border-color: rgba(76, 175, 80, 0.25);
}

.vlm-chip-install:not(:disabled):hover {
  background: rgba(76, 175, 80, 0.14);
  border-color: rgba(76, 175, 80, 0.5);
}

.vlm-chip-install:disabled {
  opacity: 0.45;
  cursor: wait;
}

.vlm-chip-install-cta {
  color: rgba(129, 199, 132, 0.9);
  font-size: 0.7rem;
  margin-left: 0.3rem;
}

.vlm-chip-input {
  display: none;
}

.vlm-chip-label {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.7);
  white-space: nowrap;
}

.vlm-chip-unavailable {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.4);
  font-style: italic;
}

.vlm-chip.active .vlm-chip-label {
  color: rgba(255, 255, 255, 0.9);
}

.vlm-empty {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  font-style: italic;
  padding: 0.3rem 0;
}


/* The columns, their heads and their cells are the shared reading columns —
   `.lab-readcol` on the raster `.lab-grid` in assets/flow-stage.css, which
   started on this surface.
   What stands below is what a cell of THIS surface holds. */

.vla-reading {
  margin: 0;
  font-size: var(--flow-fs-hint);
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.72);
  white-space: pre-wrap;
}

/* An observation about the model, not an alarm: same size as the reading, in
   the quieter voice. */
.vla-note {
  margin: 0.6rem 0 0;
  padding-top: 0.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  font-size: var(--flow-fs-hint);
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.45);
}

.vla-error {
  margin: 0;
  font-size: var(--flow-fs-hint);
  color: rgba(244, 67, 54, 0.8);
}

.typing-dots {
  margin-left: auto;
}

.typing-dots span {
  animation: typing 1.2s infinite;
  font-size: 1.2rem;
  color: rgba(255, 255, 255, 0.4);
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
}
</style>
