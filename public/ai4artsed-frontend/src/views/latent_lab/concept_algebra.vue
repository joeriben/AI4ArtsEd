<template>
  <div class="concept-algebra">
    <!-- Header -->
    <div class="page-header">
      <h2 class="page-title">
        {{ t('latentLab.algebra.headerTitle') }}
      </h2>
      <p class="page-subtitle">{{ t('latentLab.algebra.headerSubtitle') }}</p>
      <details class="explanation-details" :open="explainOpen" @toggle="onExplainToggle">
        <summary>{{ t('latentLab.algebra.explanationToggle') }}</summary>
        <div class="explanation-body">
          <div class="explanation-section">
            <h4>{{ t('latentLab.algebra.explainWhatTitle') }}</h4>
            <p>{{ t('latentLab.algebra.explainWhatText') }}</p>
          </div>
          <div class="explanation-section">
            <h4>{{ t('latentLab.algebra.explainHowTitle') }}</h4>
            <p>{{ t('latentLab.algebra.explainHowText') }}</p>
          </div>
          <div class="explanation-section">
            <h4>{{ t('latentLab.algebra.explainReadTitle') }}</h4>
            <p>{{ t('latentLab.algebra.explainReadText') }}</p>
          </div>
          <div class="explanation-section explanation-tech">
            <h4>{{ t('latentLab.algebra.techTitle') }}</h4>
            <p>{{ t('latentLab.algebra.techText') }}</p>
          </div>
          <div class="explanation-section explanation-references">
            <h4>{{ t('latentLab.algebra.referencesTitle') }}</h4>
            <ul class="reference-list">
              <li>
                <span class="ref-authors">Mikolov et al. (2013)</span>
                <span class="ref-title">"Distributed Representations of Words and Phrases and their Compositionality"</span>
                <span class="ref-venue">NeurIPS 2013</span>
                <a href="https://doi.org/10.48550/arXiv.1310.4546" target="_blank" rel="noopener" class="ref-doi">DOI</a>
              </li>
              <li>
                <span class="ref-authors">Liu et al. (2022)</span>
                <span class="ref-title">"Compositional Visual Generation with Composable Diffusion Models"</span>
                <span class="ref-venue">ECCV 2022</span>
                <a href="https://doi.org/10.1007/978-3-031-19803-8_12" target="_blank" rel="noopener" class="ref-doi">DOI</a>
              </li>
            </ul>
          </div>
        </div>
      </details>
    </div>

    <!-- Input Section -->
    <div class="input-section">
      <!-- Prompt A (full width) -->
      <div class="input-row-a">
        <MediaInputBox
          icon="lightbulb"
          :label="t('latentLab.algebra.promptALabel')"
          :placeholder="t('latentLab.algebra.promptAPlaceholder')"
          v-model:value="promptA"
          input-type="text"
          :rows="2"
          resize-type="auto"
          :disabled="isGenerating"
          @copy="copyPromptA"
          @paste="pastePromptA"
          @clear="clearPromptA"
        />
      </div>

      <!-- Formula visualization -->
      <div class="formula-row">
        <span class="formula-text">{{ t('latentLab.algebra.formulaLabel') }}</span>
      </div>

      <!-- Prompt B and C (side by side) -->
      <div class="input-pair">
        <MediaInputBox
          icon="−"
          :label="t('latentLab.algebra.promptBLabel')"
          :placeholder="t('latentLab.algebra.promptBPlaceholder')"
          v-model:value="promptB"
          input-type="text"
          :rows="2"
          resize-type="auto"
          :disabled="isGenerating"
          @copy="copyPromptB"
          @paste="pastePromptB"
          @clear="clearPromptB"
        />
        <MediaInputBox
          icon="＋"
          :label="t('latentLab.algebra.promptCLabel')"
          :placeholder="t('latentLab.algebra.promptCPlaceholder')"
          v-model:value="promptC"
          input-type="text"
          :rows="2"
          resize-type="auto"
          :disabled="isGenerating"
          @copy="copyPromptC"
          @paste="pastePromptC"
          @clear="clearPromptC"
        />
      </div>

      <!-- Encoder Toggle + Generate Button -->
      <div class="action-row">
        <div class="control-group">
          <label class="control-label">{{ t('latentLab.algebra.encoderLabel') }}</label>
          <div class="layer-toggles">
            <button
              v-for="enc in encoders"
              :key="enc.id"
              class="layer-btn"
              :class="{ active: selectedEncoder === enc.id }"
              @click="selectedEncoder = enc.id"
              :disabled="isGenerating"
            >
              {{ t(`latentLab.algebra.${enc.labelKey}`) }}
            </button>
          </div>
          <div class="control-hint">{{ t('latentLab.algebra.encoderHint') }}</div>
        </div>
        <button
          class="generate-btn"
          :disabled="isGenerating || !promptA.trim() || !promptB.trim() || !promptC.trim()"
          @click="compute"
        >
          <span v-if="isGenerating" class="spinner"></span>
          <span v-else>{{ t('latentLab.algebra.generateBtn') }}</span>
        </button>
      </div>

      <!-- Advanced Settings -->
      <details class="advanced-settings" :open="advancedOpen" @toggle="onAdvancedToggle">
        <summary>{{ t('latentLab.algebra.advancedLabel') }}</summary>
        <div class="settings-grid">
          <label>
            {{ t('latentLab.algebra.negativeLabel') }}
            <input v-model="negativePrompt" type="text" class="setting-input" />
            <div class="control-hint">{{ t('latentLab.shared.negativeHint') }}</div>
          </label>
          <label>
            {{ t('latentLab.algebra.stepsLabel') }}
            <input v-model.number="steps" type="number" min="10" max="50" class="setting-input setting-small" />
            <div class="control-hint">{{ t('latentLab.shared.stepsHint') }}</div>
          </label>
          <label>
            {{ t('latentLab.algebra.cfgLabel') }}
            <input v-model.number="cfgScale" type="number" min="1" max="20" step="0.5" class="setting-input setting-small" />
            <div class="control-hint">{{ t('latentLab.shared.cfgHint') }}</div>
          </label>
          <label>
            {{ t('latentLab.algebra.scaleSubLabel') }}
            <input v-model.number="scaleSub" type="number" min="0" max="3" step="0.1" class="setting-input setting-small" />
            <div class="control-hint">{{ t('latentLab.algebra.scaleSubHint') }}</div>
          </label>
          <label>
            {{ t('latentLab.algebra.scaleAddLabel') }}
            <input v-model.number="scaleAdd" type="number" min="0" max="3" step="0.1" class="setting-input setting-small" />
            <div class="control-hint">{{ t('latentLab.algebra.scaleAddHint') }}</div>
          </label>
        </div>
      </details>

      <!-- Seed (always visible) -->
      <SeedControl v-model:seed="seed" v-model:random="randomSeed" />
    </div>

    <!-- Side-by-Side Image Comparison -->
    <div class="comparison-section" :class="{ disabled: !hasResult && !isGenerating }">
      <div class="image-pair">
        <div class="image-panel">
          <div class="panel-label">{{ t('latentLab.algebra.referenceLabel') }}</div>
          <div class="image-frame" :class="{ empty: !referenceImage }">
            <img v-if="referenceImage" :src="`data:image/png;base64,${referenceImage}`" class="result-image" />
            <div v-else-if="isGenerating" class="image-placeholder">
              <div class="progress-spinner"></div>
              <p>{{ t('latentLab.algebra.generating') }}</p>
            </div>
          </div>
          <button v-if="referenceImage" class="download-btn" @click="downloadReference">
            {{ t('latentLab.algebra.downloadReference') }}
          </button>
        </div>
        <div class="image-panel">
          <div class="panel-label">{{ t('latentLab.algebra.resultLabel') }}</div>
          <div class="image-frame" :class="{ empty: !resultImage }">
            <img v-if="resultImage" :src="`data:image/png;base64,${resultImage}`" class="result-image" />
            <div v-else-if="isGenerating" class="image-placeholder">
              <div class="progress-spinner"></div>
              <p>{{ t('latentLab.algebra.generating') }}</p>
            </div>
            <div v-else class="image-placeholder-hint">
              <p>{{ t('latentLab.algebra.resultHint') }}</p>
            </div>
          </div>
          <button v-if="resultImage" class="download-btn" @click="downloadResult">
            {{ t('latentLab.algebra.downloadResult') }}
          </button>
        </div>
      </div>

      <!-- Metadata display -->
      <div v-if="l2Distance !== null" class="metadata-row">
        <span class="metadata-label">{{ t('latentLab.algebra.l2Label') }}:</span>
        <span class="metadata-value">{{ l2Distance.toFixed(4) }}</span>
        <div class="control-hint">{{ t('latentLab.algebra.l2Hint') }}</div>
      </div>
      <div v-if="actualSeed !== null" class="seed-display">
        Seed: {{ actualSeed }}
      </div>
    </div>

    <!-- Error Display -->
    <div class="error-display" v-if="errorMessage">
      <p>{{ errorMessage }}</p>
      <button @click="errorMessage = ''" class="dismiss-btn">&times;</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import MediaInputBox from '@/components/MediaInputBox.vue'
import SeedControl from '@/components/SeedControl.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useLatentLabRecorder } from '@/composables/useLatentLabRecorder'
import { useDetailsState } from '@/composables/useDetailsState'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext, FocusHint } from '@/composables/usePageContext'

const { t } = useI18n()
const pageContextStore = usePageContextStore()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const { record: labRecord } = useLatentLabRecorder('concept_algebra')
const { isOpen: explainOpen, onToggle: onExplainToggle } = useDetailsState('ll_algebra_explain')
const { isOpen: advancedOpen, onToggle: onAdvancedToggle } = useDetailsState('ll_algebra_advanced')

// Encoder options
type EncoderId = 'all' | 'clip_l' | 'clip_g' | 't5'
const encoders: { id: EncoderId; labelKey: string }[] = [
  { id: 'all', labelKey: 'encoderAll' },
  { id: 'clip_l', labelKey: 'encoderClipL' },
  { id: 'clip_g', labelKey: 'encoderClipG' },
  { id: 't5', labelKey: 'encoderT5' },
]

// State
const promptA = ref('')
const promptB = ref('')
const promptC = ref('')
const selectedEncoder = ref<EncoderId>('all')
const negativePrompt = ref('')
const steps = ref(25)
const cfgScale = ref(4.5)
const seed = ref(123456789)
const randomSeed = ref(false)
const scaleSub = ref(1.0)
const scaleAdd = ref(1.0)
const isGenerating = ref(false)
const errorMessage = ref('')

// Result data
const referenceImage = ref('')
const resultImage = ref('')
const actualSeed = ref<number | null>(null)
const l2Distance = ref<number | null>(null)

// Computed
const hasResult = computed(() => !!resultImage.value)

// Session persistence — restore on mount
onMounted(() => {
  const sa = sessionStorage
  const s = (k: string) => sa.getItem(k)
  if (s('lat_lab_ca_promptA')) promptA.value = s('lat_lab_ca_promptA')!
  if (s('lat_lab_ca_promptB')) promptB.value = s('lat_lab_ca_promptB')!
  if (s('lat_lab_ca_promptC')) promptC.value = s('lat_lab_ca_promptC')!
  const enc = s('lat_lab_ca_encoder')
  if (enc && ['all', 'clip_l', 'clip_g', 't5'].includes(enc)) selectedEncoder.value = enc as EncoderId
  if (s('lat_lab_ca_negative')) negativePrompt.value = s('lat_lab_ca_negative')!
  if (s('lat_lab_ca_steps')) steps.value = parseFloat(s('lat_lab_ca_steps')!) || 25
  if (s('lat_lab_ca_cfg')) cfgScale.value = parseFloat(s('lat_lab_ca_cfg')!) || 4.5
  if (s('lat_lab_ca_seed')) seed.value = parseFloat(s('lat_lab_ca_seed')!) || 123456789
  if (s('lat_lab_ca_random_seed')) randomSeed.value = s('lat_lab_ca_random_seed') === 'true'
  if (s('lat_lab_ca_scaleSub')) scaleSub.value = parseFloat(s('lat_lab_ca_scaleSub')!) || 1.0
  if (s('lat_lab_ca_scaleAdd')) scaleAdd.value = parseFloat(s('lat_lab_ca_scaleAdd')!) || 1.0
})

// Session persistence — save on change
watch(promptA, v => sessionStorage.setItem('lat_lab_ca_promptA', v))
watch(promptB, v => sessionStorage.setItem('lat_lab_ca_promptB', v))
watch(promptC, v => sessionStorage.setItem('lat_lab_ca_promptC', v))
watch(selectedEncoder, v => sessionStorage.setItem('lat_lab_ca_encoder', v))
watch([negativePrompt, steps, cfgScale, seed, randomSeed, scaleSub, scaleAdd], () => {
  sessionStorage.setItem('lat_lab_ca_negative', negativePrompt.value)
  sessionStorage.setItem('lat_lab_ca_steps', String(steps.value))
  sessionStorage.setItem('lat_lab_ca_cfg', String(cfgScale.value))
  sessionStorage.setItem('lat_lab_ca_seed', String(seed.value))
  sessionStorage.setItem('lat_lab_ca_random_seed', String(randomSeed.value))
  sessionStorage.setItem('lat_lab_ca_scaleSub', String(scaleSub.value))
  sessionStorage.setItem('lat_lab_ca_scaleAdd', String(scaleAdd.value))
})

// Clipboard helpers
function copyPromptA() { copyToClipboard(promptA.value) }
function pastePromptA() { promptA.value = pasteFromClipboard() }
function clearPromptA() { promptA.value = ''; sessionStorage.removeItem('lat_lab_ca_promptA') }
function copyPromptB() { copyToClipboard(promptB.value) }
function pastePromptB() { promptB.value = pasteFromClipboard() }
function clearPromptB() { promptB.value = ''; sessionStorage.removeItem('lat_lab_ca_promptB') }
function copyPromptC() { copyToClipboard(promptC.value) }
function pastePromptC() { promptC.value = pasteFromClipboard() }
function clearPromptC() { promptC.value = ''; sessionStorage.removeItem('lat_lab_ca_promptC') }

function downloadReference() {
  if (!referenceImage.value) return
  const link = document.createElement('a')
  link.href = `data:image/png;base64,${referenceImage.value}`
  link.download = `concept_algebra_reference_${actualSeed.value}.png`
  link.click()
}

function downloadResult() {
  if (!resultImage.value) return
  const link = document.createElement('a')
  link.href = `data:image/png;base64,${resultImage.value}`
  link.download = `concept_algebra_result_${actualSeed.value}.png`
  link.click()
}

async function compute() {
  if (!promptA.value.trim() || !promptB.value.trim() || !promptC.value.trim() || isGenerating.value) return

  isGenerating.value = true
  errorMessage.value = ''
  referenceImage.value = ''
  resultImage.value = ''
  actualSeed.value = null
  l2Distance.value = null

  try {
    const baseUrl = import.meta.env.DEV ? 'http://localhost:17802' : ''
    const response = await axios.post(`${baseUrl}/api/schema/pipeline/legacy`, {
      prompt: promptA.value,
      output_config: 'concept_algebra_diffusers',
      seed: randomSeed.value ? -1 : seed.value,
      negative_prompt: negativePrompt.value,
      steps: steps.value,
      cfg: cfgScale.value,
      prompt_b: promptB.value,
      prompt_c: promptC.value,
      algebra_encoder: selectedEncoder.value,
      scale_sub: scaleSub.value,
      scale_add: scaleAdd.value,
    })

    if (response.data.status === 'success') {
      const algData = response.data.algebra_data
      if (algData) {
        referenceImage.value = algData.reference_image || ''
        resultImage.value = algData.result_image || ''
        l2Distance.value = algData.l2_distance ?? null
        actualSeed.value = response.data.media_output?.seed ?? algData.seed ?? null

        // Record for research export
        const outputs: { type: 'image'; format: string; dataBase64: string }[] = []
        if (referenceImage.value) outputs.push({ type: 'image', format: 'png', dataBase64: referenceImage.value })
        if (resultImage.value) outputs.push({ type: 'image', format: 'png', dataBase64: resultImage.value })
        labRecord({
          parameters: {
            prompt_a: promptA.value, prompt_b: promptB.value, prompt_c: promptC.value,
            encoder: selectedEncoder.value, negative_prompt: negativePrompt.value,
            steps: steps.value, cfg: cfgScale.value, seed: seed.value,
            scale_sub: scaleSub.value, scale_add: scaleAdd.value,
          },
          results: { seed: actualSeed.value, l2_distance: l2Distance.value },
          outputs,
        })
      } else {
        errorMessage.value = 'No algebra data in response'
      }
    } else {
      errorMessage.value = response.data.error || response.data.message || 'Computation failed'
    }
  } catch (err: unknown) {
    const axiosErr = err as { response?: { data?: { error?: string } }; message?: string }
    errorMessage.value = axiosErr.response?.data?.error || axiosErr.message || 'Network error'
  } finally {
    isGenerating.value = false
  }
}

// Trashy Page Context
const trashyFocusHint = computed<FocusHint>(() => {
  if (isGenerating.value || resultImage.value) {
    return { x: 95, y: 85, anchor: 'bottom-right' }
  }
  return { x: 8, y: 95, anchor: 'bottom-left' }
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'concept_algebra',
  pageContent: {
    inputText: `A: ${promptA.value}\nB: ${promptB.value}\nC: ${promptC.value}`,
  },
  focusHint: trashyFocusHint.value,
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onUnmounted(() => {
  pageContextStore.clearContext()
})
</script>

<style scoped>
.concept-algebra {
  max-width: 1000px;
  margin: 0 auto;
  padding: 1.5rem 1.5rem 3rem;
}

/* === Page Header === */
.page-header { margin-bottom: 1.5rem; }
.page-title { color: #667eea; font-size: 1.2rem; font-weight: 700; margin: 0 0 0.5rem; }
.page-subtitle { color: rgba(255, 255, 255, 0.7); font-size: 0.95rem; line-height: 1.6; margin: 0 0 0.75rem; }

.explanation-details {
  background: rgba(102, 126, 234, 0.06);
  border: 1px solid rgba(102, 126, 234, 0.15);
  border-radius: 10px;
  overflow: hidden;
}
.explanation-details summary {
  padding: 0.65rem 1rem;
  color: rgba(102, 126, 234, 0.8);
  font-size: 0.85rem;
  cursor: pointer;
  user-select: none;
}
.explanation-details summary:hover { color: #667eea; }
.explanation-body { padding: 0 1rem 1rem; display: flex; flex-direction: column; gap: 0.75rem; }
.explanation-section h4 { color: rgba(255, 255, 255, 0.85); font-size: 0.85rem; margin: 0 0 0.25rem; }
.explanation-section p { color: rgba(255, 255, 255, 0.6); font-size: 0.82rem; line-height: 1.6; margin: 0; }
.explanation-tech { background: rgba(0, 0, 0, 0.2); border-radius: 8px; padding: 0.75rem; }
.explanation-tech p { font-size: 0.78rem; }

.reference-list { list-style: none; padding: 0; margin: 0.5rem 0 0; }
.reference-list li { margin-bottom: 0.4rem; font-size: 0.8rem; color: rgba(255,255,255,0.6); }
.ref-authors { font-weight: 500; color: rgba(255,255,255,0.8); }
.ref-title { font-style: italic; }
.ref-venue { color: rgba(255,255,255,0.5); }
.ref-doi { color: rgba(102,126,234,0.8); text-decoration: none; margin-left: 0.3rem; }
.ref-doi:hover { text-decoration: underline; }

/* === Input Section === */
.input-section { display: flex; flex-direction: column; gap: 0.75rem; margin-bottom: 1.5rem; }

.input-row-a {
  display: flex;
  justify-content: center;
}

.formula-row {
  display: flex;
  justify-content: center;
  padding: 0.25rem 0;
}

.formula-text {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 1.1rem;
  font-weight: 700;
  color: rgba(102, 126, 234, 0.8);
  letter-spacing: 0.1em;
}

.input-pair {
  display: flex;
  gap: clamp(1rem, 3vw, 2rem);
  width: 100%;
  justify-content: center;
  flex-wrap: wrap;
}

.action-row { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.control-group { display: flex; align-items: center; gap: 0.75rem; flex: 1; }
.control-label { color: rgba(255, 255, 255, 0.5); font-size: 0.8rem; flex-shrink: 0; }
.layer-toggles { display: flex; gap: 0.35rem; }

.layer-btn {
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s ease;
}
.layer-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.layer-btn.active { background: rgba(102, 126, 234, 0.2); border-color: rgba(102, 126, 234, 0.5); color: #667eea; }

.generate-btn {
  padding: 0.75rem 1.5rem;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  border-radius: 10px;
  color: white;
  font-weight: 700;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  min-height: 42px;
}
.generate-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3); }
.generate-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Advanced Settings */
.advanced-settings { margin-top: 0.25rem; }
.advanced-settings summary { color: rgba(255, 255, 255, 0.5); font-size: 0.8rem; cursor: pointer; padding: 0.25rem 0; }
.settings-grid { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.5rem; }
.settings-grid label { display: flex; flex-direction: column; gap: 0.25rem; color: rgba(255, 255, 255, 0.5); font-size: 0.75rem; }
.setting-input {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
  color: white;
  font-size: 0.85rem;
}
.setting-small { width: 80px; }
.setting-seed { width: 14ch; }

/* === Disabled state === */
.comparison-section.disabled { opacity: 0.35; pointer-events: none; }

/* === Comparison Section === */
.comparison-section { margin-bottom: 1.5rem; }
.image-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.image-panel { display: flex; flex-direction: column; gap: 0.35rem; }
.panel-label { color: rgba(255, 255, 255, 0.5); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; }

.image-frame {
  border-radius: 12px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.08);
  aspect-ratio: 1 / 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.image-frame.empty { border-style: dashed; border-color: rgba(255, 255, 255, 0.15); }
.result-image { width: 100%; height: 100%; object-fit: cover; display: block; }

.image-placeholder { text-align: center; color: rgba(102, 126, 234, 0.7); padding: 2rem; }
.image-placeholder p { font-size: 0.85rem; margin-top: 0.75rem; }
.image-placeholder-hint { text-align: center; padding: 2rem 1.5rem; }
.image-placeholder-hint p { color: rgba(255, 255, 255, 0.3); font-size: 0.8rem; line-height: 1.5; margin: 0; }

.progress-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(102, 126, 234, 0.2);
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto;
}

.metadata-row {
  margin-top: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.metadata-label {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.8rem;
}
.metadata-value {
  color: rgba(102, 126, 234, 0.9);
  font-size: 0.85rem;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-weight: 600;
}

.seed-display {
  margin-top: 0.5rem;
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.7rem;
  font-family: 'Fira Code', 'Consolas', monospace;
}

/* === Download === */
.download-btn {
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  width: 100%;
}
.download-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

/* === Error === */
.error-display {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: rgba(244, 67, 54, 0.1);
  border: 1px solid rgba(244, 67, 54, 0.3);
  border-radius: 8px;
  color: #ef5350;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.dismiss-btn { background: none; border: none; color: rgba(244, 67, 54, 0.6); font-size: 1.2rem; cursor: pointer; }

/* === Responsive === */
@media (max-width: 768px) {
  .input-pair { flex-direction: column; }
}
@media (max-width: 640px) {
  .image-pair { grid-template-columns: 1fr; }
  .action-row { flex-direction: column; align-items: stretch; }
  .control-group { flex-direction: column; align-items: flex-start; }
}

.control-hint {
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.7rem;
  line-height: 1.4;
}


</style>

<style>
/* Force INPUT boxes to have proper width */
.concept-algebra .input-row-a .media-input-box {
  flex: 0 1 960px !important;
  width: 100% !important;
  max-width: 960px !important;
}
.concept-algebra .input-pair .media-input-box {
  flex: 1 1 0 !important;
  width: 100% !important;
  max-width: 480px !important;
}
</style>
