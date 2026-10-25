<!--
  MMAudio — a picture is given to a sound model, and what comes back is what
  that model makes of it, with a prompt beside it and a second prompt saying
  what is not wanted.

  Split out of views/latent_lab/crossmodal_lab.vue on 2026-09-05, where it stood
  with the Latent Audio Synth and ImageBind Guidance in one file. The SURFACE is
  the one that file carried at a50054bc: picture, prompt, negative prompt, the
  four numbers, the trigger, and the sound underneath — one under another. A
  two-column frame was put here on 2026-09-05 and taken out the same day.

  The picture is the one ImageBind Guidance works on as well
  (composables/useCrossmodalPicture.ts), which is what the two shared refs of
  the old single file did.
-->
<template>
  <div class="xm-lab">
    <div class="xm-panel">
      <h3>{{ t('latentLab.crossmodal.tabs.mmaudio.title') }}</h3>


      <MediaInputBox
        inputType="image"
        icon="image"
        :label="t('latentLab.crossmodal.mmaudio.imageUpload')"
        :allow-sketch="true"
        value=""
        :initial-image="imagePreview"
        @image-uploaded="handleImageUpload"
        @image-removed="clearImage"
        @copy="copyImage"
        @paste="pasteImage"
        @clear="clearImage"
      />

      <PromptExamples
        :items="mmaudioExamples"
        :current="mmaudio.prompt"
        @pick="applyMMAudioExample"
      />
      <MediaInputBox
        chrome="bare"
        icon="lightbulb"
        :label="t('latentLab.crossmodal.mmaudio.prompt')"
        :placeholder="t('mediaInput.freePromptPlaceholder')"
        :value="mmaudio.prompt"
        @update:value="mmaudio.prompt = $event"
        :rows="2"
        :isEmpty="!mmaudio.prompt"
        :isFilled="!!mmaudio.prompt"
        :is-loading="readingPicture"
        :disabled="readingPicture"
        @copy="copyMMAudioPrompt"
        @paste="pasteMMAudioPrompt"
        @clear="clearMMAudioPrompt"
        :show-preset-button="true"
        :preset-busy="enriching === 'a'"
        @open-preset-selector="openPreset('a')"
        @image-uploaded="handlePicture"
        @image-removed="dropPicture"
      />
      <!-- The reading of a dropped picture, where it did not come back. -->
      <p v-if="readingFailedKey" class="lab-prep-err">{{ t(readingFailedKey) }}</p>

      <MediaInputBox
        chrome="bare"
        icon="clipboard"
        :label="t('latentLab.crossmodal.mmaudio.negativePrompt')"
        :value="mmaudio.negativePrompt"
        @update:value="mmaudio.negativePrompt = $event"
        :rows="2"
        :isEmpty="!mmaudio.negativePrompt"
        :isFilled="!!mmaudio.negativePrompt"
        :showTranslate="false"
        @copy="copyMMAudioNeg"
        @paste="pasteMMAudioNeg"
        @clear="clearMMAudioNeg"
        :show-preset-button="true"
        :preset-busy="enriching === 'b'"
        @open-preset-selector="openPreset('b')"
      />
      <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>

      <div class="xm-params-row">
        <div class="xm-param">
          <label>{{ t('latentLab.crossmodal.mmaudio.duration') }}</label>
          <input v-model.number="mmaudio.duration" type="number" min="1" max="8" step="1" />
        </div>
        <div class="xm-param">
          <label>{{ t('latentLab.crossmodal.mmaudio.cfg') }}</label>
          <input v-model.number="mmaudio.cfg" type="number" min="1" max="15" step="0.5" />
        </div>
        <div class="xm-param">
          <label>{{ t('latentLab.crossmodal.mmaudio.steps') }}</label>
          <input v-model.number="mmaudio.steps" type="number" min="10" max="50" step="5" />
        </div>
        <div class="xm-param">
          <label>{{ t('latentLab.crossmodal.seed') }}</label>
          <input v-model.number="mmaudio.seed" type="number" />
        </div>
      </div>

      <button class="xm-generate" :disabled="(!mmaudio.prompt && !imagePath) || generating" @click="runMMAudio">
        {{ generating ? t('latentLab.crossmodal.generating') : t('latentLab.crossmodal.generate') }}
      </button>
    </div>

    <div v-if="error" class="xm-output">
      <div class="xm-error">{{ error }}</div>
    </div>

    <div class="output-section">
      <MediaOutputBox
        :output-image="resultAudio"
        media-type="audio"
        :is-executing="generating"
        :progress="0"
        @download="downloadResultAudio"
      />
      <div v-if="resultSeed !== null || generationTimeMs" class="xm-result-meta">
        <span v-if="resultSeed !== null" class="xm-meta-item">{{ t('latentLab.crossmodal.seed') }}: {{ resultSeed }}</span>
        <span v-if="generationTimeMs" class="xm-meta-item">{{ t('latentLab.crossmodal.generationTime') }}: {{ generationTimeMs }}ms</span>
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
import { ref, reactive, computed, watch, onBeforeUnmount, toRef } from 'vue'
import { usePictureTemplate } from '@/composables/usePictureTemplate'
import { useI18n } from 'vue-i18n'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { apiPost, base64ToDataUrl, generationErrorFor as labErrorText, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { downloadMedia } from '@/lib/downloadMedia'
import MediaInputBox from '@/components/MediaInputBox.vue'
import MediaOutputBox from '@/components/MediaOutputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import { useDeviceId } from '@/composables/useDeviceId'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useCrossmodalPicture } from '@/composables/useCrossmodalPicture'
import { useLatentLabRecorder, type InstrumentRun } from '@/composables/useLatentLabRecorder'
import { useSeedAutomatic } from '@/composables/useSeedAutomatic'
import { useInstrumentRuns } from '@/composables/useInstrumentRuns'
import type { DrawerItem } from '@/components/canvas/OutputDrawer.vue'

const { t } = useI18n()

/**
 * The tool key stays `crossmodal_lab` after the split: the sitting ids live in
 * sessionStorage under `ai4artsed:lab-sittings:crossmodal_lab`, so a key of
 * this instrument's own would orphan every run a workshop has already made.
 * Which runs belong HERE is said by the run's own `tab`, the way it always was.
 */
const TOOL = 'crossmodal_lab'
const TAB = 'mmaudio'

const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const { imagePath, imagePreview, setPicture, clearPicture } = useCrossmodalPicture()
const { record: labRecord } = useLatentLabRecorder(TOOL)

/** The reasons a run did not come back, in the reader's language. */
function generationErrorFor(failure: unknown): string {
  return labErrorText(t, failure)
}

const error = ref('')
const isRunning = ref(false)
/** The name the surface of yesterday uses; the state is one ref. */
const generating = computed(() => isRunning.value)

// ---------------------------------------------------------------------------
// The perspective in the corner of the two written fields — the platform's
// mandatory pair with a written field (registry, Rule #13;
// test_element_structure_policy.py, R3). ONE overlay serves both; which one
// opened it decides where the answer is written back. Wired on 2026-10-10
// (finding S-041 of the code review of 2026-10-10), when the policy began to see the three surfaces of the Crossmodal Lab.
// ---------------------------------------------------------------------------
type PromptField = 'a' | 'b'

const deviceId = useDeviceId()
const showPresetOverlay = ref(false)
// The perspective's failure stands under the field (`.lab-prep-err`), as on
// mean_images; the run's own error keeps the foot of the output.
const perspectiveError = ref('')
const enriching = ref<PromptField | ''>('')
let presetTarget: PromptField = 'a'

function openPreset(which: PromptField): void {
  presetTarget = which
  showPresetOverlay.value = true
}

async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  const which = presetTarget
  const before = which === 'a' ? mmaudio.prompt : mmaudio.negativePrompt
  if (!before.trim()) return
  enriching.value = which
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, before, deviceId)
    if ('written' in outcome) {
      // A perspective takes minutes; a run started meanwhile was sent the
      // wording that stood then.
      if (!generating.value) {
        if (which === 'a') mmaudio.prompt = outcome.written
        else mmaudio.negativePrompt = outcome.written
      }
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (e) {
    perspectiveError.value = labErrorText(t, e)
  } finally {
    enriching.value = ''
  }
}

const resultAudio = ref('')
const resultSeed = ref<number | null>(null)
const generationTimeMs = ref<number | null>(null)

const mmaudio = reactive({
  prompt: '',
  negativePrompt: '',
  duration: 8,
  cfg: 4.5,
  steps: 25,
  seed: -1,
})

/**
 * Everything a run goes out with except its seed, as one key: what the seed
 * automatic compares the next press with. This surface has no tick „Random
 * variation“.
 */
function inputsKey(): string {
  return JSON.stringify([mmaudio.prompt, mmaudio.negativePrompt, mmaudio.duration, mmaudio.cfg,
    mmaudio.steps, imagePath.value])
}
// null: this instrument keeps none of its fields, so the yardstick starts afresh with them.
const seedAutomatic = useSeedAutomatic(toRef(mmaudio, 'seed'), ref(false), null)

const { addRun } = useInstrumentRuns(TOOL, cardFor, {
  shell: { sourceView: computed(() => 'latent-lab/mmaudio') },
  // Three instruments record into one strip, and a sound made here has nothing
  // to be compared with a sound made in another of them. Each card says which
  // one it came out of (`cardFor` puts the tab in `configId`).
  shownWhen: card => card.configId === TAB,
})

function cardFor(run: InstrumentRun): DrawerItem | null {
  const params = (run.parameters || {}) as Record<string, unknown>
  const results = (run.results || {}) as Record<string, unknown>
  const sound = (run.outputs || []).find(o => o.type === 'audio')
  if (!sound?.url) return null
  const head = (text: unknown) => String(text ?? '').trim().split(/\s+/).slice(0, 4).join(' ')
  return {
    id: run.run_id,
    label: head(params.prompt),
    sub: `${String(params.tab ?? '')} · ${params.duration ?? ''}s`,
    meta: [
      `seed: ${results.seed ?? params.seed ?? ''}`,
      `cfg: ${params.cfg ?? ''}`,
      `steps: ${params.steps ?? ''}`,
    ],
    prompt: String(params.prompt ?? ''),
    configId: String(params.tab ?? ''),
    sourceView: 'latent-lab/mmaudio',
    createdAt: Date.parse(run.timestamp || '') || Date.now(),
    modelMeta: null,
    runId: run.run_id,
    output: { url: sound.url, media_type: 'audio' },
    error: null,
  }
}

/** A take just made, laid as a card through the same reader that reads one back. */
async function keepTake(parameters: Record<string, unknown>, results: Record<string, unknown>, wavBase64: string) {
  const runId = await labRecord({
    parameters,
    results,
    outputs: [{ type: 'audio', format: 'wav', dataBase64: wavBase64 }],
  })
  if (!runId) return
  addRun(cardFor({
    run_id: runId,
    tool: TOOL,
    timestamp: new Date().toISOString(),
    parameters,
    results,
    outputs: [{ type: 'audio', format: 'wav', url: `/api/media/audio/${runId}`, meta: {} }],
  }))
}


/**
 * A picture dropped onto the prompt field is read as a description, and the
 * reading then stands in the field (`composables/usePictureTemplate.ts`). This
 * way in belongs on every FREE prompt field of the lab, and the hint over the
 * field names it. The picture field ABOVE this one is a different
 * thing and keeps its own meaning: there a picture stays a picture.
 */
const {
  reading: readingPicture,
  readingFailedKey,
  handlePicture,
  dropPicture,
} = usePictureTemplate(toRef(mmaudio, 'prompt'))

const mmaudioExamples = computed(() => [
  {
    id: 'campfire',
    label: t('latentLab.crossmodal.mmaudio.promptExamples.campfire'),
    fill: [t('latentLab.crossmodal.mmaudio.promptExamples.campfire')],
  },
])

function applyMMAudioExample(item: { fill: string[] }) {
  mmaudio.prompt = item.fill[0] ?? ''
}

function handleImageUpload(data: { image_path: string; preview_url: string }) {
  setPicture(data)
}

function copyImage() { copyToClipboard(imagePreview.value) }
function pasteImage() {
  const content = pasteFromClipboard()
  if (content) imagePreview.value = content
}
function clearImage() { clearPicture() }

function copyMMAudioPrompt() { copyToClipboard(mmaudio.prompt) }
function pasteMMAudioPrompt() { mmaudio.prompt = pasteFromClipboard() }
function clearMMAudioPrompt() { mmaudio.prompt = '' }

function copyMMAudioNeg() { copyToClipboard(mmaudio.negativePrompt) }
function pasteMMAudioNeg() { mmaudio.negativePrompt = pasteFromClipboard() }
function clearMMAudioNeg() { mmaudio.negativePrompt = '' }

function clearResults() {
  error.value = ''
  resultAudio.value = ''
  resultSeed.value = null
  generationTimeMs.value = null
}

async function runMMAudio() {
  clearResults()
  isRunning.value = true
  // The seed automatic (composables/useSeedAutomatic): the same seed when
  // something changed since the sound on the surface was made, a new one when
  // nothing did, the field's when it was typed. The seed goes into the field.
  const runInputs = inputsKey()
  const runSeed = seedAutomatic.seedForRun(runInputs)
  try {
    const body: Record<string, unknown> = {
      prompt: mmaudio.prompt,
      negative_prompt: mmaudio.negativePrompt,
      duration_seconds: mmaudio.duration,
      cfg_strength: mmaudio.cfg,
      num_steps: mmaudio.steps,
      seed: runSeed,
    }
    if (imagePath.value) {
      body.image_path = imagePath.value
    }

    const result = await apiPost('/api/cross_aesthetic/mmaudio', body)
    if (result.success) {
      resultAudio.value = base64ToDataUrl(result.audio_base64, 'audio/wav')
      resultSeed.value = result.seed
      generationTimeMs.value = result.generation_time_ms
      // This sound is now the one the next press is compared with.
      seedAutomatic.arrived(runInputs, result.seed ?? runSeed)

      void keepTake(
        { tab: TAB, prompt: mmaudio.prompt, negative_prompt: mmaudio.negativePrompt,
          duration: mmaudio.duration, cfg: mmaudio.cfg, steps: mmaudio.steps, seed: runSeed,
          has_image: !!imagePath.value },
        { seed: result.seed, generation_time_ms: result.generation_time_ms },
        result.audio_base64,
      )
    } else {
      error.value = generationErrorFor(result.error || 'MMAudio generation failed')
    }
  } catch (e) {
    error.value = generationErrorFor(e)
  } finally {
    isRunning.value = false
  }
}

function downloadResultAudio() {
  if (!resultAudio.value) return
  void downloadMedia(resultAudio.value, `mmaudio_${resultSeed.value ?? 0}.wav`)
}

const pageContextStore = usePageContextStore()

// The catalogue (platform_items.json) is keyed to this, and carries what this
// place says about its own technology.
const pageContext = computed<PageContext>(() => ({
  activeViewType: `crossmodal_lab.${TAB}`,
  pageContent: {},
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onBeforeUnmount(() => {
  // Before, not after: the instrument taking over writes the page context in
  // its own setup, and setup runs ahead of a post-flush onUnmounted.
  pageContextStore.clearContext()
})
</script>

<style scoped>
.xm-params-row {
  display: flex;
  gap: 1rem;
  margin: 1rem 0;
  flex-wrap: wrap;
}

.xm-param label {
  display: block;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 0.3rem;
}

.xm-param input {
  width: 100%;
  padding: 0.5rem;
  background: var(--surface-2);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  color: #ffffff;
  font-size: 0.85rem;
}
</style>
