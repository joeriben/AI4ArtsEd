<template>
  <div dir="ltr" class="vector-fusion-flow">
    <!-- Step 1: Input Stage -->
    <div v-if="currentStep === 'input'" class="input-stage">
      <div class="input-container">
        <div class="stage-title">
          {{ $t('vectorFusion.inputTitle') || 'Beschreibe zwei Dinge zum Kombinieren' }}
        </div>
        <textarea
          v-model="userInput"
          class="main-input"
          :placeholder="$t('vectorFusion.inputPlaceholder') || 'z.B.: [ein Meteorit im Weltall] [ein silberner Löffel]'"
          rows="4"
          maxlength="500"
        ></textarea>
        <div class="char-count">{{ userInput.length }} / 500</div>

        <button
          class="split-btn"
          :disabled="!canSplit || isSplitting"
          @click="handleSplit"
        >
          <span v-if="!isSplitting">
            {{ $t('vectorFusion.splitButton') || 'Text aufteilen & visualisieren' }}
          </span>
          <span v-else>
            {{ $t('vectorFusion.splitting') || 'Teile auf...' }}
          </span>
        </button>
      </div>
    </div>

    <!-- Step 2: Split Flow Animation -->
    <div v-if="currentStep === 'split'" class="split-flow-stage">
      <!-- Original Input Bubble -->
      <div class="flow-row">
        <div class="bubble bubble-input">
          <div class="bubble-icon">IN</div>
          <div class="bubble-title">{{ $t('vectorFusion.originalInput') || 'Deine Eingabe' }}</div>
          <div class="bubble-text">{{ userInput }}</div>
        </div>
      </div>

      <!-- Arrow Down -->
      <div class="flow-arrow">
        <div class="arrow-line"></div>
        <div class="arrow-head">↓</div>
      </div>

      <!-- Explanation: Splitting -->
      <div class="flow-row">
        <div class="explanation-box">
          <div class="explanation-icon">Split</div>
          <div class="explanation-text">
            {{ $t('vectorFusion.splitExplanation') || 'Die KI teilt deinen Text in zwei semantische Konzepte' }}
          </div>
        </div>
      </div>

      <!-- Arrow Down -->
      <div class="flow-arrow">
        <div class="arrow-line"></div>
        <div class="arrow-head">↓</div>
      </div>

      <!-- Two Parallel Bubbles -->
      <div class="flow-row parallel">
        <div class="bubble bubble-part-a">
          <div class="bubble-icon dot-a">A</div>
          <div class="bubble-title">{{ $t('vectorFusion.partA') || 'Konzept A' }}</div>
          <div class="bubble-text">{{ splitResult?.part_a }}</div>
        </div>

        <div class="bubble bubble-part-b">
          <div class="bubble-icon dot-b">B</div>
          <div class="bubble-title">{{ $t('vectorFusion.partB') || 'Konzept B' }}</div>
          <div class="bubble-text">{{ splitResult?.part_b }}</div>
        </div>
      </div>

      <!-- Parallel Arrows -->
      <div class="flow-row parallel">
        <div class="flow-arrow">
          <div class="arrow-line"></div>
          <div class="arrow-head">↓</div>
        </div>
        <div class="flow-arrow">
          <div class="arrow-line"></div>
          <div class="arrow-head">↓</div>
        </div>
      </div>

      <!-- Explanation: Vectorization -->
      <div class="flow-row">
        <div class="explanation-box">
          <div class="explanation-icon">CLIP</div>
          <div class="explanation-text">
            {{ $t('vectorFusion.vectorExplanation') || 'Beide Texte werden in semantische Vektoren umgewandelt (CLIP)' }}
          </div>
        </div>
      </div>

      <!-- Parallel Arrows -->
      <div class="flow-row parallel">
        <div class="flow-arrow">
          <div class="arrow-line"></div>
          <div class="arrow-head">↓</div>
        </div>
        <div class="flow-arrow">
          <div class="arrow-line"></div>
          <div class="arrow-head">↓</div>
        </div>
      </div>

      <!-- Explanation: Fusion -->
      <div class="flow-row">
        <div class="explanation-box highlight">
          <div class="explanation-icon">SLERP</div>
          <div class="explanation-text">
            {{ $t('vectorFusion.fusionExplanation') || 'Die Vektoren werden im semantischen Raum kombiniert (SLERP)' }}
          </div>
        </div>
      </div>

      <!-- Converging Arrows -->
      <div class="flow-row converging">
        <div class="converging-arrows">
          <div class="arrow-left">→</div>
          <div class="arrow-merge">↓</div>
          <div class="arrow-right">←</div>
        </div>
      </div>

      <!-- Fusion Bubble -->
      <div class="flow-row">
        <div class="bubble bubble-fusion">
          <div class="bubble-icon">A+B</div>
          <div class="bubble-title">{{ $t('vectorFusion.fusion') || 'Fusion beider Konzepte' }}</div>
          <div class="bubble-text">{{ interpolationMethod === 'linear' ? 'Linear (LERP)' : 'Spherical (SLERP)' }} @ α=0.5</div>
        </div>
      </div>

      <!-- Generate Button -->
      <div class="flow-row">
        <button
          class="generate-btn"
          :disabled="isGenerating"
          @click="handleGenerate"
        >
          <span v-if="!isGenerating">
            {{ $t('vectorFusion.generateImages') || '4 Bilder generieren' }}
          </span>
          <span v-else>
            {{ $t('vectorFusion.generating') || 'Generiere...' }}
          </span>
        </button>
      </div>
    </div>

    <!-- Step 3: Image Generation Progress & Results -->
    <div v-if="currentStep === 'generating' || currentStep === 'complete'" class="results-stage">
      <div class="stage-title">
        {{ $t('vectorFusion.results') || 'Ergebnisse' }}
      </div>

      <div class="images-grid">
        <!-- Image 1: Original -->
        <div class="image-card" :class="{ loading: generationStep < 1, active: generationStep === 1, complete: generationStep > 1 }">
          <div class="image-header">
            <div class="image-icon">1</div>
            <div class="image-title">{{ $t('vectorFusion.original') || 'Original' }}</div>
          </div>
          <div v-if="generationStep >= 1 && images.original" class="image-container">
            <img :src="images.original" alt="Original" />
          </div>
          <div v-else class="image-placeholder">
            <div v-if="generationStep === 1" class="spinner">...</div>
            <div v-else class="waiting">—</div>
          </div>
          <div class="image-caption">{{ $t('vectorFusion.originalDesc') || 'Ganzer Input' }}</div>
        </div>

        <!-- Image 2: Split A -->
        <div class="image-card" :class="{ loading: generationStep < 2, active: generationStep === 2, complete: generationStep > 2 }">
          <div class="image-header">
            <div class="image-icon">🔵</div>
            <div class="image-title">{{ $t('vectorFusion.partA') || 'Konzept A' }}</div>
          </div>
          <div v-if="generationStep >= 2 && images.splitA" class="image-container">
            <img :src="images.splitA" alt="Split A" />
          </div>
          <div v-else class="image-placeholder">
            <div v-if="generationStep === 2" class="spinner">...</div>
            <div v-else class="waiting">—</div>
          </div>
          <div class="image-caption">{{ splitResult?.part_a }}</div>
        </div>

        <!-- Image 3: Split B -->
        <div class="image-card" :class="{ loading: generationStep < 3, active: generationStep === 3, complete: generationStep > 3 }">
          <div class="image-header">
            <div class="image-icon dot-b">3</div>
            <div class="image-title">{{ $t('vectorFusion.partB') || 'Konzept B' }}</div>
          </div>
          <div v-if="generationStep >= 3 && images.splitB" class="image-container">
            <img :src="images.splitB" alt="Split B" />
          </div>
          <div v-else class="image-placeholder">
            <div v-if="generationStep === 3" class="spinner">...</div>
            <div v-else class="waiting">—</div>
          </div>
          <div class="image-caption">{{ splitResult?.part_b }}</div>
        </div>

        <!-- Image 4: Fusion -->
        <div class="image-card" :class="{ loading: generationStep < 4, active: generationStep === 4, complete: generationStep > 4 }">
          <div class="image-header">
            <div class="image-icon">4</div>
            <div class="image-title">{{ $t('vectorFusion.fusion') || 'Fusion' }}</div>
          </div>
          <div v-if="generationStep >= 4 && images.fusion" class="image-container">
            <img :src="images.fusion" alt="Fusion" />
          </div>
          <div v-else class="image-placeholder">
            <div v-if="generationStep === 4" class="spinner">...</div>
            <div v-else class="waiting">—</div>
          </div>
          <div class="image-caption">{{ $t('vectorFusion.fusionDesc') || 'A ⊕ B (α=0.5)' }}</div>
        </div>
      </div>

      <!-- Reset Button -->
      <div v-if="currentStep === 'complete'" class="flow-row">
        <button class="reset-btn" @click="handleReset">
          {{ $t('vectorFusion.reset') || 'Neu beginnen' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { executePipeline, type PipelineExecuteRequest } from '@/services/api'

interface Props {
  configId: string
  safetyLevel?: 'kids' | 'youth' | 'adult'
}

const props = withDefaults(defineProps<Props>(), {
  safetyLevel: 'kids'
})

const emit = defineEmits<{
  generated: [runId: string]
}>()

const { t } = useI18n()

// State
type Step = 'input' | 'split' | 'generating' | 'complete'
const currentStep = ref<Step>('input')
const userInput = ref('')
const splitResult = ref<{ part_a: string; part_b: string } | null>(null)
const interpolationMethod = ref<'linear' | 'spherical'>('linear')
const isSplitting = ref(false)
const isGenerating = ref(false)
const generationStep = ref(0) // 0=not started, 1=original, 2=splitA, 3=splitB, 4=fusion, 5=complete

// Image URLs
const images = ref({
  original: '',
  splitA: '',
  splitB: '',
  fusion: ''
})

// Computed
const canSplit = computed(() => userInput.value.trim().length > 0)

// Determine interpolation method from configId
if (props.configId.includes('spherical')) {
  interpolationMethod.value = 'spherical'
}

// Methods
async function handleSplit() {
  if (!canSplit.value) return

  isSplitting.value = true

  try {
    console.log('[VectorFusion] Starting split...')

    const request: PipelineExecuteRequest = {
      schema: props.configId,
      input_text: userInput.value,
    }

    const response = await executePipeline(request)

    if (response.status !== 'success' || !response.final_output) {
      throw new Error(response.error || 'Split failed')
    }

    console.log('[VectorFusion] Split complete:', response.final_output)

    // Parse split result
    const parsed = JSON.parse(response.final_output)
    splitResult.value = {
      part_a: parsed.part_a || '',
      part_b: parsed.part_b || ''
    }

    currentStep.value = 'split'

  } catch (err) {
    console.error('[VectorFusion] Split error:', err)
    alert(`Split fehlgeschlagen: ${err instanceof Error ? err.message : 'Unknown error'}`)
  } finally {
    isSplitting.value = false
  }
}

async function handleGenerate() {
  if (!splitResult.value) return

  isGenerating.value = true
  currentStep.value = 'generating'
  generationStep.value = 0

  try {
    // Step 1: Generate Original (whole input)
    generationStep.value = 1
    console.log('[VectorFusion] Generating original...')
    const originalResult = await generateImage(userInput.value, userInput.value, 0.5)
    images.value.original = `/api/media/${originalResult.run_id}`

    // Step 2: Generate Split A
    generationStep.value = 2
    console.log('[VectorFusion] Generating split A...')
    const splitAResult = await generateImage(splitResult.value.part_a, splitResult.value.part_a, 0.0)
    images.value.splitA = `/api/media/${splitAResult.run_id}`

    // Step 3: Generate Split B
    generationStep.value = 3
    console.log('[VectorFusion] Generating split B...')
    const splitBResult = await generateImage(splitResult.value.part_b, splitResult.value.part_b, 1.0)
    images.value.splitB = `/api/media/${splitBResult.run_id}`

    // Step 4: Generate Fusion
    generationStep.value = 4
    console.log('[VectorFusion] Generating fusion...')
    const fusionResult = await generateImage(splitResult.value.part_a, splitResult.value.part_b, 0.5)
    images.value.fusion = `/api/media/${fusionResult.run_id}`

    generationStep.value = 5
    currentStep.value = 'complete'
    console.log('[VectorFusion] ✅ All images generated!')

    // Emit last run_id for potential Phase 3 navigation
    if (fusionResult.run_id) {
      emit('generated', fusionResult.run_id)
    }

  } catch (err) {
    console.error('[VectorFusion] Generation error:', err)
    alert(`Generierung fehlgeschlagen: ${err instanceof Error ? err.message : 'Unknown error'}`)
    currentStep.value = 'split'
  } finally {
    isGenerating.value = false
  }
}

async function generateImage(partA: string, partB: string, alpha: number) {
  const outputConfig = interpolationMethod.value === 'linear'
    ? 'vector_fusion_linear_clip'
    : 'vector_fusion_spherical_clip'

  const request: PipelineExecuteRequest = {
    schema: outputConfig,
    input_text: `${partA} + ${partB}`, // Backend requires input_text even with custom_placeholders
    custom_placeholders: {
      PART_A: partA,
      PART_B: partB,
      ALPHA: alpha.toString()
    }
  }

  const response = await executePipeline(request)

  if (response.status !== 'success' || !response.run_id) {
    throw new Error(response.error || 'Image generation failed')
  }

  return response
}

function handleReset() {
  currentStep.value = 'input'
  userInput.value = ''
  splitResult.value = null
  generationStep.value = 0
  images.value = {
    original: '',
    splitA: '',
    splitB: '',
    fusion: ''
  }
}
</script>

<style scoped>
.vector-fusion-flow {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 20px;
  overflow-y: auto;
  max-height: 100vh;
}

/* Input Stage */
.input-stage {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}

.input-container {
  width: 100%;
  max-width: 700px;
  text-align: center;
}

.stage-title {
  font-size: 32px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 32px;
}

.main-input {
  width: 100%;
  background: rgba(30, 30, 30, 0.95);
  border: 3px solid rgba(102, 126, 234, 0.5);
  border-radius: 16px;
  padding: 24px;
  color: #e0e0e0;
  font-size: 18px;
  line-height: 1.6;
  font-family: inherit;
  resize: vertical;
  transition: all 0.3s ease;
}

.main-input:focus {
  outline: none;
  border-color: rgba(102, 126, 234, 0.8);
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.2);
}

.char-count {
  text-align: right;
  font-size: 14px;
  color: #888;
  margin: 12px 0 24px;
}

.split-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 20px 60px;
  border-radius: 12px;
  font-size: 20px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.5);
}

.split-btn:hover:not(:disabled) {
  transform: translateY(-3px);
  box-shadow: 0 12px 40px rgba(102, 126, 234, 0.6);
}

.split-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Split Flow Stage */
.split-flow-stage {
  padding: 40px 0;
}

.flow-row {
  display: flex;
  justify-content: center;
  align-items: center;
  margin: 24px 0;
}

.flow-row.parallel {
  gap: 40px;
  justify-content: center;
}

.flow-row.converging {
  margin: 16px 0;
}

/* Bubbles */
.bubble {
  background: rgba(30, 30, 30, 0.95);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 20px;
  padding: 24px;
  min-width: 300px;
  max-width: 450px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  transition: all 0.3s ease;
}

.bubble-input {
  border-color: rgba(102, 126, 234, 0.5);
}

.bubble-part-a {
  border-color: rgba(74, 144, 226, 0.5);
}

.bubble-part-b {
  border-color: rgba(243, 156, 18, 0.5);
}

.bubble-fusion {
  border-color: rgba(155, 89, 182, 0.5);
}

.bubble-icon {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.05em;
  margin-bottom: 12px;
  opacity: 0.7;
}
.bubble-icon.dot-a {
  color: #4a9eff;
}
.bubble-icon.dot-b {
  color: #ff8c42;
}

.bubble-title {
  font-size: 16px;
  font-weight: 600;
  color: #aaa;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 12px;
}

.bubble-text {
  font-size: 16px;
  color: #e0e0e0;
  line-height: 1.6;
}

/* Explanation Boxes */
.explanation-box {
  background: rgba(42, 42, 42, 0.9);
  border: 2px dashed rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  padding: 20px 32px;
  max-width: 600px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.explanation-box.highlight {
  border-color: rgba(155, 89, 182, 0.5);
  background: rgba(155, 89, 182, 0.1);
}

.explanation-icon {
  font-size: 32px;
  flex-shrink: 0;
}

.explanation-text {
  font-size: 15px;
  color: #ccc;
  line-height: 1.5;
}

/* Arrows */
.flow-arrow {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.arrow-line {
  width: 2px;
  height: 40px;
  background: rgba(255, 255, 255, 0.2);
}

.arrow-head {
  font-size: 32px;
  color: rgba(255, 255, 255, 0.3);
}

.converging-arrows {
  display: flex;
  align-items: center;
  gap: 20px;
  font-size: 32px;
  color: rgba(155, 89, 182, 0.6);
}

.arrow-left, .arrow-right {
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

/* Generate Button */
.generate-btn {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: white;
  border: none;
  padding: 20px 60px;
  border-radius: 12px;
  font-size: 20px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 8px 32px rgba(240, 147, 251, 0.5);
  margin-top: 32px;
}

.generate-btn:hover:not(:disabled) {
  transform: translateY(-3px);
  box-shadow: 0 12px 40px rgba(240, 147, 251, 0.6);
}

.generate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Results Stage */
.results-stage {
  padding: 40px 0;
}

.images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
  margin: 40px 0;
}

.image-card {
  background: rgba(30, 30, 30, 0.95);
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 20px;
  transition: all 0.3s ease;
}

.image-card.loading {
  opacity: 0.5;
}

.image-card.active {
  border-color: rgba(102, 126, 234, 0.8);
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4);
}

.image-card.complete {
  opacity: 1;
}

.image-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.image-icon {
  font-size: 28px;
}

.image-title {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.image-container {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
  background: #000;
}

.image-container img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-placeholder {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
}

.spinner {
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.waiting {
  opacity: 0.3;
}

.image-caption {
  margin-top: 12px;
  font-size: 13px;
  color: #888;
  text-align: center;
  line-height: 1.4;
}

/* Reset Button */
.reset-btn {
  background: transparent;
  color: #888;
  border: 2px solid #555;
  padding: 16px 40px;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  margin-top: 40px;
}

.reset-btn:hover {
  border-color: #888;
  color: #fff;
  background: rgba(255, 255, 255, 0.05);
}

/* Responsive */
@media (max-width: 768px) {
  .flow-row.parallel {
    flex-direction: column;
    gap: 24px;
  }

  .bubble {
    min-width: auto;
    max-width: 100%;
  }

  .images-grid {
    grid-template-columns: 1fr;
  }
}
</style>
