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
          <section class="vla-case lab-col col-fold-host" :class="{ folded }">
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

            <label class="lab-pick-label">{{ t('compare.vlmAnalysis.modelsLabel') }}</label>
            <div class="vlm-chips">
              <template v-for="vlm in vlmModels" :key="vlm.id">
                <label
                  v-if="vlm.available"
                  class="vlm-chip"
                  :class="{ active: selectedModels.includes(vlm.id) }"
                >
                  <input type="checkbox" :value="vlm.id" v-model="selectedModels" class="vlm-chip-input" />
                  <span class="vlm-chip-label">{{ vlm.label }}</span>
                </label>
                <button
                  v-else-if="vlm.installable"
                  type="button"
                  class="vlm-chip vlm-chip-install"
                  :disabled="installActive"
                  @click="triggerInstall(vlm.id, vlm.label)"
                >
                  <span class="vlm-chip-label">
                    {{ vlm.label }}
                    <span class="vlm-chip-install-cta">
                      ⤓ {{ t('compare.shared.install.downloadCta', { mb: vlm.approxDownloadMb }) }}
                    </span>
                  </span>
                </button>
                <label v-else class="vlm-chip disabled">
                  <span class="vlm-chip-label">
                    {{ vlm.label }}<span class="vlm-chip-unavailable"> {{ t('compare.shared.modelNotDownloaded') }}</span>
                  </span>
                </label>
              </template>
              <span v-if="!vlmLoading && vlmModels.length === 0" class="vlm-empty">
                {{ t('compare.vlmAnalysis.noModelsInstalled') }}
              </span>
            </div>
          </section>

          <!-- One column per reader, all of them the same width: what is read
               across is the DIFFERENCE between the readings, so no column may
               be wider than another. Before the first press the chosen readers
               already stand there, darkened, with their heads — an empty
               surface says nothing about what a press would do. -->
          <section class="vla-plot">
            <div class="vla-cols" :style="{ '--vla-cols': columns.length }">
              <div
                v-for="col in columns"
                :key="col.model"
                class="vla-col"
                :class="{ 'is-preview': col.state === 'preview', 'is-waiting': col.state === 'waiting' }"
              >
                <div class="vla-col-head">
                  <span class="vla-col-name">{{ col.label }}</span>
                  <span v-if="col.latency != null" class="vla-col-latency">{{ col.latency }}s</span>
                  <span v-else-if="col.state === 'active'" class="typing-dots"><span>.</span><span>.</span><span>.</span></span>
                  <span v-else-if="col.state === 'waiting'" class="vla-col-waiting">{{ t('compare.vlmAnalysis.waiting') }}</span>
                </div>
                <!-- The reading scrolls in its own column. A surface that grew
                     with the longest of them would push the fourth reader below
                     the window, and reading them against each other is the
                     whole point of standing them side by side. -->
                <div class="vla-cell">
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
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { useI18n } from 'vue-i18n'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import ShellRun from '@/components/ShellRun.vue'
import { useVlmModels } from '@/composables/useVlmModels'
import { useDeviceId } from '@/composables/useDeviceId'
import { useModelInstall } from '@/composables/useModelInstall'
import { READING_FRAMES, type ReadingFrame } from '@/data/readingFrames'
import { readSseFrames } from '@/lib/sseStream'
import { generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { apiBase } from '@/services/labApi'

const { t, locale } = useI18n()

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

// Pre-select the small readers once the list arrives from the backend. The
// large one is offered, not switched on: it holds 19 GB for as long as it is
// loaded, and on a smaller card that pushes the image model off.
watch(vlmModels, (models) => {
  if (selectedModels.value.length > 0) return
  selectedModels.value = models.filter(m => m.available && m.backend === 'llm').map(m => m.id)
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
    return selectedModels.value.map(model => ({
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

function getModelLabel(modelId: string): string {
  return vlmModels.value.find(m => m.id === modelId)?.label ?? modelId
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
 * token / done / error. A card that stops without either has lost its
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
  const models = [...selectedModels.value]  // Snapshot — won't change mid-loop

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
          label: `${selectedModels.value.map(m => getModelLabel(m)).join(', ')} · ${frameLabel.value}`,
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


/* Heads and cells share ONE grid, and a column contributes its two children to
   it (`display: contents`) instead of forming a grid of its own — the same
   arrangement Cultural (Un)Known uses. A head that wraps to two lines would
   otherwise shorten the cell in ITS column only. */
.vla-plot { overflow: hidden; }

.vla-cols {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(var(--vla-cols), minmax(0, 1fr));
  grid-template-rows: auto minmax(0, 1fr);
  grid-auto-flow: column;
  gap: 6px 10px;
}

.vla-col { display: contents; }

.vla-col-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  min-width: 0;
}

.vla-col-name {
  font-size: var(--flow-fs-label);
  color: rgba(255, 255, 255, 0.8);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vla-col-latency {
  margin-left: auto;
  font-size: var(--flow-fs-hint);
  color: rgba(76, 175, 80, 0.7);
  font-variant-numeric: tabular-nums;
}

.vla-col-waiting {
  margin-left: auto;
  font-size: var(--flow-fs-hint);
  color: rgba(255, 255, 255, 0.25);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* The cell takes the height the surface gives it and scrolls inside — see the
   note in the template. Its ground is the surface stack, never a literal. */
.vla-cell {
  min-height: 0;
  overflow-y: auto;
  background: var(--surface-2);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  padding: 10px 12px;
}

.vla-col.is-preview .vla-col-head,
.vla-col.is-preview .vla-cell { opacity: 0.45; }

.vla-col.is-waiting .vla-cell { opacity: 0.5; }

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
