<!--
  ImageBind Guidance — a picture and a text are put into ONE embedding space
  (Girdhar et al. 2023), and the sound is pulled towards the picture while it is
  being made. What comes back carries the cosine between the finished clip and
  the picture that guided it.

  Split out of views/latent_lab/crossmodal_lab.vue on 2026-09-05, where it stood
  with the Latent Audio Synth and MMAudio in one file. The SURFACE is the one
  that file carried at a50054bc: the research basis, the picture, the prompt,
  the two axes, the four numbers, the trigger, and the sound underneath — one
  under another. A two-column frame was put here on 2026-09-05 and taken out the
  same day.

  The picture is the one MMAudio works on as well
  (composables/useCrossmodalPicture.ts), which is what the two shared refs of
  the old single file did.
-->
<template>
  <div class="xm-lab">
    <div class="xm-panel">
      <h3>{{ t('latentLab.crossmodal.tabs.guidance.title') }}</h3>

      <LabReferences
        :title="t('latentLab.crossmodal.guidance.referencesTitle')"
        :items="GUIDANCE_REFERENCES"
        storage-key="ll_crossmodal_guidance_explain"
      />

      <MediaInputBox
        inputType="image"
        icon="image"
        :label="t('latentLab.crossmodal.guidance.imageUpload')"
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
        :items="guidanceExamples"
        :current="guidance.prompt"
        @pick="applyGuidanceExample"
      />
      <MediaInputBox
        chrome="bare"
        icon="lightbulb"
        :label="t('latentLab.crossmodal.guidance.prompt')"
        :placeholder="t('mediaInput.freePromptPlaceholder')"
        :value="guidance.prompt"
        @update:value="guidance.prompt = $event"
        :rows="2"
        :isEmpty="!guidance.prompt"
        :isFilled="!!guidance.prompt"
        :is-loading="readingPicture"
        :disabled="readingPicture"
        @copy="copyGuidancePrompt"
        @paste="pasteGuidancePrompt"
        @clear="clearGuidancePrompt"
        :show-preset-button="true"
        :preset-busy="enriching"
        @open-preset-selector="showPresetOverlay = true"
        @image-uploaded="handlePicture"
        @image-removed="dropPicture"
      />
      <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>

      <!-- Guidance sliders -->
      <div class="xm-slider-group">
        <div class="xm-slider-item">
          <div class="xm-slider-header">
            <label>{{ t('latentLab.crossmodal.guidance.lambda') }}</label>
            <span class="xm-slider-value">{{ guidance.lambda.toFixed(1) }}</span>
          </div>
          <input type="range" v-model.number="guidance.lambda" min="0" max="10" step="0.1" />
        </div>

        <div class="xm-slider-item">
          <div class="xm-slider-header">
            <label>{{ t('latentLab.crossmodal.guidance.warmupSteps') }}</label>
            <span class="xm-slider-value">{{ guidance.warmupSteps }}</span>
          </div>
          <input type="range" v-model.number="guidance.warmupSteps" min="1" :max="guidance.totalSteps" step="1" />
        </div>
      </div>

      <div class="xm-params-row">
        <div class="xm-param">
          <label>{{ t('latentLab.crossmodal.guidance.totalSteps') }}</label>
          <input v-model.number="guidance.totalSteps" type="number" min="4" max="20" step="1" />
        </div>
        <div class="xm-param">
          <label>{{ t('latentLab.crossmodal.guidance.duration') }}</label>
          <input v-model.number="guidance.duration" type="number" min="1" max="30" step="1" />
        </div>
        <div class="xm-param">
          <label>{{ t('latentLab.crossmodal.guidance.cfg') }}</label>
          <input v-model.number="guidance.cfg" type="number" min="0.5" max="3" step="0.1" />
        </div>
        <div class="xm-param">
          <label>{{ t('latentLab.crossmodal.seed') }}</label>
          <input v-model.number="guidance.seed" type="number" />
        </div>
      </div>

      <p class="first-run-notice">{{ t('latentLab.crossmodal.guidance.firstRunNotice') }}</p>

      <button class="xm-generate" :disabled="!imagePath || generating" @click="runGuidance">
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
      <div v-if="resultSeed !== null || generationTimeMs || cosineSimilarity !== null" class="xm-result-meta">
        <span v-if="resultSeed !== null" class="xm-meta-item">{{ t('latentLab.crossmodal.seed') }}: {{ resultSeed }}</span>
        <span v-if="generationTimeMs" class="xm-meta-item">{{ t('latentLab.crossmodal.generationTime') }}: {{ generationTimeMs }}ms</span>
        <span v-if="cosineSimilarity !== null" class="xm-meta-item">{{ t('latentLab.crossmodal.guidance.cosineSimilarity') }}: {{ cosineSimilarity.toFixed(4) }}</span>
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
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useCrossmodalPicture } from '@/composables/useCrossmodalPicture'
import { useLatentLabRecorder } from '@/composables/useLatentLabRecorder'
import { useSeedAutomatic } from '@/composables/useSeedAutomatic'

const { t } = useI18n()

/** The shared space this instrument reads from is ImageBind's. */
const GUIDANCE_REFERENCES: LabReference[] = [
  {
    authors: 'Girdhar et al. (2023)',
    title: '"ImageBind: One Embedding Space To Bind Them All"',
    venue: 'CVPR 2023',
    doi: 'https://doi.org/10.48550/arXiv.2305.05665',
  },
]

/**
 * The tool key stays `crossmodal_lab` after the split: the sitting ids live in
 * sessionStorage under `ai4artsed:lab-sittings:crossmodal_lab`, so a key of
 * this instrument's own would orphan every run a workshop has already made.
 */
const TOOL = 'crossmodal_lab'
const TAB = 'guidance'

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
// The perspective in the field's corner — the platform's mandatory pair with a
// written field (registry, Rule #13; test_element_structure_policy.py, R3).
// Wired on 2026-10-10 (finding S-041 of the code review of 2026-10-10), when the policy began to see the three surfaces
// of the Crossmodal Lab.
// ---------------------------------------------------------------------------
const deviceId = useDeviceId()
const showPresetOverlay = ref(false)
// The perspective's failure stands under the field (`.lab-prep-err`), as on
// mean_images; the run's own error keeps the foot of the output.
const perspectiveError = ref('')
const enriching = ref(false)

async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  const before = guidance.prompt
  if (!before.trim()) return
  enriching.value = true
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, before, deviceId)
    if ('written' in outcome) {
      // A perspective takes minutes; a run started meanwhile was sent the
      // wording that stood then.
      if (!generating.value) guidance.prompt = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (e) {
    perspectiveError.value = labErrorText(t, e)
  } finally {
    enriching.value = false
  }
}

const resultAudio = ref('')
const resultSeed = ref<number | null>(null)
const generationTimeMs = ref<number | null>(null)
const cosineSimilarity = ref<number | null>(null)

const guidance = reactive({
  prompt: '',
  // Measured on the finished clip (ImageBind cosine against the guiding image):
  // 0.16 unguided, 0.21 at lambda 1, 0.23 at lambda 5, falling again from 20 on.
  // Below 1 the slider does nothing, so the old default of 0.1 guided nothing.
  lambda: 5,
  // The sampler mixes fresh noise into every step, so guidance on the first steps
  // alone is overwritten before the clip is finished: guide all of them.
  warmupSteps: 8,
  totalSteps: 8,
  duration: 10,
  cfg: 1.0,
  seed: -1,
})

/**
 * Everything a run goes out with except its seed, as one key: what the seed
 * automatic compares the next press with. This surface has no tick „Random
 * variation“.
 */
function inputsKey(): string {
  return JSON.stringify([guidance.prompt, guidance.lambda, guidance.warmupSteps,
    guidance.totalSteps, guidance.duration, guidance.cfg, imagePath.value])
}
// null: this instrument keeps none of its fields, so the yardstick starts afresh with them.
const seedAutomatic = useSeedAutomatic(toRef(guidance, 'seed'), ref(false), null)

watch(() => guidance.totalSteps, (steps) => {
  if (guidance.warmupSteps > steps) guidance.warmupSteps = steps
})


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
} = usePictureTemplate(toRef(guidance, 'prompt'))

const guidanceExamples = computed(() => [
  {
    id: 'ambient',
    label: t('latentLab.crossmodal.guidance.promptExamples.ambient'),
    fill: [t('latentLab.crossmodal.guidance.promptExamples.ambient')],
  },
])

function applyGuidanceExample(item: { fill: string[] }) {
  guidance.prompt = item.fill[0] ?? ''
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

function copyGuidancePrompt() { copyToClipboard(guidance.prompt) }
function pasteGuidancePrompt() { guidance.prompt = pasteFromClipboard() }
function clearGuidancePrompt() { guidance.prompt = '' }

function clearResults() {
  error.value = ''
  resultAudio.value = ''
  resultSeed.value = null
  generationTimeMs.value = null
  cosineSimilarity.value = null
}

async function runGuidance() {
  clearResults()
  isRunning.value = true
  // The seed automatic (composables/useSeedAutomatic): the same seed when
  // something changed since the sound on the surface was made, a new one when
  // nothing did, the field's when it was typed. The seed goes into the field.
  const runInputs = inputsKey()
  const runSeed = seedAutomatic.seedForRun(runInputs)
  try {
    const result = await apiPost('/api/cross_aesthetic/image_guided_audio', {
      image_path: imagePath.value,
      prompt: guidance.prompt,
      lambda_guidance: guidance.lambda,
      warmup_steps: guidance.warmupSteps,
      total_steps: guidance.totalSteps,
      duration_seconds: guidance.duration,
      cfg_scale: guidance.cfg,
      seed: runSeed,
    })
    if (result.success) {
      resultAudio.value = base64ToDataUrl(result.audio_base64, 'audio/wav')
      resultSeed.value = result.seed
      generationTimeMs.value = result.generation_time_ms
      cosineSimilarity.value = result.cosine_similarity ?? null
      // This sound is now the one the next press is compared with.
      seedAutomatic.arrived(runInputs, result.seed ?? runSeed)

      labRecord({
        parameters: { tab: TAB, prompt: guidance.prompt,
          lambda: guidance.lambda, warmup_steps: guidance.warmupSteps,
          total_steps: guidance.totalSteps, duration: guidance.duration,
          cfg: guidance.cfg, seed: runSeed, has_image: !!imagePath.value },
        results: { seed: result.seed, generation_time_ms: result.generation_time_ms,
          cosine_similarity: result.cosine_similarity },
        outputs: [{ type: 'audio', format: 'wav', dataBase64: result.audio_base64 }],
      })
    } else {
      error.value = generationErrorFor(result.error || 'Guided generation failed')
    }
  } catch (e) {
    error.value = generationErrorFor(e)
  } finally {
    isRunning.value = false
  }
}

function downloadResultAudio() {
  if (!resultAudio.value) return
  void downloadMedia(resultAudio.value, `imagebind_${resultSeed.value ?? 0}.wav`)
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

.first-run-notice {
  font-size: 0.75rem;
  color: rgba(255, 200, 80, 0.6);
  margin: 0.4rem 0 0.6rem;
  line-height: 1.4;
}
</style>
