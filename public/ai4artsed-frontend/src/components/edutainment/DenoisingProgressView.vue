<template>
  <div dir="ltr" class="denoising-progress-view">
    <!-- Phase A/B crossfade transition -->
    <Transition name="phase-switch" mode="out-in">
      <!-- Phase A: Model Loading
           Diffusers: progress stays 0 during loading (only reports during inference)
           ComfyUI: sends progress during loading nodes, but no preview until denoising -->
      <div v-if="isModelLoading" key="loading" class="model-loading-phase">
        <div class="model-card">
          <div class="model-card-header">
            <span class="model-name">{{ profileName }}</span>
            <span class="model-card-label">{{ t('edutainment.denoising.modelCard') }}</span>
          </div>

          <div class="model-specs">
            <div v-if="modelMeta?.publisher" class="spec-row">
              <span class="spec-label">{{ t('edutainment.denoising.publisher') }}</span>
              <span class="spec-value">{{ modelMeta.publisher }}</span>
            </div>
            <div v-if="modelMeta?.architecture" class="spec-row">
              <span class="spec-label">{{ t('edutainment.denoising.architecture') }}</span>
              <span class="spec-value">{{ modelMeta.architecture }}</span>
            </div>
            <div v-if="modelMeta?.params" class="spec-row">
              <span class="spec-label">{{ t('edutainment.denoising.parameters') }}</span>
              <span class="spec-value">{{ modelMeta.params }}</span>
            </div>
            <div v-if="modelMeta?.text_encoders?.length" class="spec-row">
              <span class="spec-label">{{ t('edutainment.denoising.textEncoders') }}</span>
              <span class="spec-value">{{ modelMeta.text_encoders.join(', ') }}</span>
            </div>
            <div v-if="modelMeta?.quantization" class="spec-row">
              <span class="spec-label">{{ t('edutainment.denoising.quantization') }}</span>
              <span class="spec-value">{{ modelMeta.quantization }}</span>
            </div>
            <div v-if="vramDisplay" class="spec-row">
              <span class="spec-label">{{ t('edutainment.denoising.vramRequired') }}</span>
              <span class="spec-value">{{ vramDisplay }}</span>
            </div>
            <div v-if="resolutionDisplay" class="spec-row">
              <span class="spec-label">{{ t('edutainment.denoising.resolution') }}</span>
              <span class="spec-value">{{ resolutionDisplay }}</span>
            </div>
            <div v-if="modelMeta?.license" class="spec-row">
              <span class="spec-label">{{ t('edutainment.denoising.license') }}</span>
              <span class="spec-value">{{ modelMeta.license }}</span>
            </div>
            <div v-if="modelMeta?.fair_culture" class="spec-row">
              <span class="spec-label">{{ t('edutainment.denoising.fairCulture') }}</span>
              <span class="spec-value">{{ modelMeta.fair_culture }}</span>
            </div>
            <div v-if="modelMeta?.safety_by_design" class="spec-row">
              <span class="spec-label">{{ t('edutainment.denoising.safetyByDesign') }}</span>
              <span class="spec-value">{{ modelMeta.safety_by_design }}</span>
            </div>
          </div>
        </div>

        <div class="loading-bar-section">
          <div class="loading-bar-track">
            <div
              class="loading-bar-fill"
              :class="{ 'loading-bar-indeterminate': loadingPercent <= 0 }"
              :style="loadingPercent > 0 ? { width: loadingPercent + '%' } : {}"
            ></div>
          </div>
          <span class="loading-label">
            <template v-if="isCloudModel">{{ t('edutainment.denoising.cloudProcessing') }}</template>
            <template v-else-if="loadingPercent > 0">{{ t('edutainment.denoising.modelLoadingVram', { used: loadingVramUsed, expected: loadingVramExpected }) }}</template>
            <template v-else>{{ t('edutainment.denoising.modelLoading') }}</template>
          </span>
        </div>

        <!-- Rotating fact -->
        <div v-if="currentFact" class="expert-fact">
          {{ currentFact.text }}
        </div>
      </div>

      <!-- Phase B: Denoising Active (progress > 0 = model loaded) -->
      <div v-else key="denoising" class="denoising-active-phase">
        <div v-if="previewImage" class="preview-container">
          <img :src="previewImage" alt="" class="denoising-preview-large" />
        </div>

        <div class="denoising-compact">
          <div class="step-bar-track">
            <div class="step-bar-fill" :style="{ width: progress + '%' }"></div>
          </div>
          <div class="stats-line-compact">
            <!-- Encoding status: sequential encoder steps before denoising stats -->
            <template v-if="encodingStatusText">
              <span class="encoding-step-text">{{ encodingStatusText }}</span>
            </template>
            <template v-else>
              <span v-if="gpuStats.available && gpuStats.power_draw_watts" class="stat-seg">{{ Math.round(gpuStats.power_draw_watts) }}W · {{ totalKwh }} kWh</span>
              <span class="stat-sep" v-if="gpuStats.available && gpuStats.power_draw_watts">|</span>
              <span v-if="gpuStats.available" class="stat-seg">GPU {{ gpuStats.utilization_percent ?? 0 }}%<template v-if="gpuStats.memory_used_mb && gpuStats.memory_total_mb"> · {{ (gpuStats.memory_used_mb / 1024).toFixed(1) }}/{{ (gpuStats.memory_total_mb / 1024).toFixed(0) }}GB</template></span>
              <span class="stat-sep" v-if="gpuStats.available">|</span>
              <span class="stat-seg"><template v-if="modelMeta?.seed != null">seed:{{ modelMeta.seed }}</template><template v-if="modelMeta?.cfg != null"> · CFG:{{ modelMeta.cfg }}</template><template v-if="stepTotal"> · {{ stepCurrent }}/{{ stepTotal }}</template></span>
            </template>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onUnmounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useEdutainmentFacts } from '@/composables/useEdutainmentFacts'

const { t } = useI18n()

interface Props {
  progress: number
  previewImage: string | null
  modelMeta: Record<string, any> | null
  encodingInfo: Record<string, any> | null
  estimatedSeconds?: number
}

const props = withDefaults(defineProps<Props>(), {
  progress: 0,
  previewImage: null,
  modelMeta: null,
  encodingInfo: null,
  estimatedSeconds: 30
})

const emit = defineEmits<{
  'stats-snapshot': [stats: { energyWh: number, co2Grams: number }]
}>()

// --- Model profile: read directly from config meta (single source of truth) ---
const profileName = computed(() =>
  props.modelMeta?.display_name || props.modelMeta?.model_file || 'Model'
)
const vramDisplay = computed(() => {
  const vram = props.modelMeta?.gpu_vram_mb
  if (!vram) return ''
  return `~${Math.round(vram / 1024)} GB`
})

const resolutionDisplay = computed(() => {
  return props.modelMeta?.recommended_resolution || ''
})

// Cloud/API models have no local GPU loading phase
const isCloudModel = computed(() => props.modelMeta?.requires_gpu === false)

/**
 * Detect model loading phase based on backend type:
 * - Cloud/API: no GPU loading phase, but still waiting for API response
 * - Diffusers: only reports progress during actual inference → progress === 0 means loading
 * - ComfyUI: reports progress across ALL nodes (including loading) → no preview means loading
 */
const isModelLoading = computed(() => {
  if (isCloudModel.value) {
    // Cloud models: "loading" until we get a result (progress stays 0 the whole time)
    return props.progress === 0 && !props.previewImage
  }
  if (props.modelMeta?.backend_type === 'diffusers') {
    return props.progress === 0
  }
  // ComfyUI and other backends: preview image is the definitive denoising signal
  return !props.previewImage
})

// Derive step info from progress + meta.steps
const stepTotal = computed(() => props.modelMeta?.steps ?? 0)
const stepCurrent = computed(() => {
  if (!stepTotal.value || props.progress <= 0) return 0
  return Math.round(props.progress * stepTotal.value / 100)
})

// --- Model loading progress from live VRAM ---
const loadingPercent = computed(() => {
  if (!isModelLoading.value || !gpuStats.value?.memory_used_mb) return 0
  const expectedMb = props.modelMeta?.gpu_vram_mb || 0
  if (!expectedMb) return 0
  return Math.min(Math.round((gpuStats.value.memory_used_mb / expectedMb) * 100), 95)
})
const loadingVramUsed = computed(() =>
  gpuStats.value?.memory_used_mb ? (gpuStats.value.memory_used_mb / 1024).toFixed(1) : '0'
)
const loadingVramExpected = computed(() => {
  const mb = props.modelMeta?.gpu_vram_mb || 0
  return mb ? (mb / 1024).toFixed(0) : '?'
})

// --- Encoding transparency: animated status line in Phase B ---
const encodingSteps = ref<string[]>([])
const currentEncodingStep = ref(-1)
let _encodingTimers: ReturnType<typeof setTimeout>[] = []
let _encodingAnimationStarted = false

function clearEncodingTimers() {
  _encodingTimers.forEach(clearTimeout)
  _encodingTimers = []
}

function startEncodingAnimation(info: Record<string, any>) {
  clearEncodingTimers()
  const steps: string[] = []
  if (info.clip_l) steps.push(t('edutainment.denoising.encodingClipL', { count: info.clip_l.count }))
  if (info.clip_g) steps.push(t('edutainment.denoising.encodingClipG', { count: info.clip_g.count }))
  if (info.t5) steps.push(t('edutainment.denoising.encodingT5', { count: info.t5.count }))
  steps.push(t('edutainment.denoising.encodingEmbeddings'))
  steps.push(t('edutainment.denoising.encodingDenoisingStarts'))

  encodingSteps.value = steps
  currentEncodingStep.value = 0

  let delay = 0
  for (let i = 1; i < steps.length; i++) {
    delay += 700
    const timer = setTimeout(() => { currentEncodingStep.value = i }, delay)
    _encodingTimers.push(timer)
  }
  // Clear after last step plays
  delay += 700
  _encodingTimers.push(setTimeout(() => { currentEncodingStep.value = -1 }, delay))
}

const encodingStatusText = computed(() => {
  if (currentEncodingStep.value < 0 || currentEncodingStep.value >= encodingSteps.value.length) return ''
  return encodingSteps.value[currentEncodingStep.value]
})

// Start animation when Phase B appears AND encoding data is available
// immediate: true ensures it fires on HMR reload when data is already present
const encodingReady = computed(() => !!props.encodingInfo && !isModelLoading.value)
watch(encodingReady, (ready) => {
  if (ready && !_encodingAnimationStarted) {
    _encodingAnimationStarted = true
    startEncodingAnimation(props.encodingInfo!)
  }
}, { immediate: true })

// Reset when encodingInfo is cleared (new generation cycle)
watch(() => props.encodingInfo, (info) => {
  if (!info) {
    _encodingAnimationStarted = false
    clearEncodingTimers()
    currentEncodingStep.value = -1
    encodingSteps.value = []
  }
})

// --- Edutainment facts + GPU stats ---
const {
  gpuStats,
  currentFact,
  totalEnergyWh,
  totalCo2Grams,
  startRotation,
  stopRotation,
} = useEdutainmentFacts('expert')

const totalKwh = computed(() => (totalEnergyWh.value / 1000).toFixed(3))

// Start/stop rotation when component is shown
// Energy counters accumulate across both phases — do NOT restart on phase change
startRotation()
onBeforeUnmount(() => {
  emit('stats-snapshot', { energyWh: totalEnergyWh.value, co2Grams: totalCo2Grams.value })
})
onUnmounted(() => {
  stopRotation()
  clearEncodingTimers()
})
</script>

<style scoped>
.denoising-progress-view {
  width: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.5rem;
  overflow-y: auto;
}

/* Phase A: Model Loading */
.model-loading-phase {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  width: 100%;
}

.model-card {
  background: rgba(20, 20, 20, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 1.25rem;
  overflow-y: auto;
  flex-shrink: 1;
  min-height: 0;
}

.model-card-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.model-name {
  font-size: 1.1rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.95);
  flex: 1;
}

.model-card-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: rgba(76, 175, 80, 0.7);
  font-weight: 600;
}

.model-specs {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.4rem 1rem;
}

.spec-row {
  display: contents;
}

.spec-label {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.5);
  white-space: nowrap;
}

.spec-value {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.85);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

/* Loading bar */
.loading-bar-section {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.loading-bar-track {
  height: 3px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
  overflow: hidden;
}

.loading-bar-fill {
  height: 100%;
  border-radius: 2px;
  background: rgba(76, 175, 80, 0.6);
}

.loading-bar-indeterminate {
  width: 40%;
  animation: indeterminate 1.8s ease-in-out infinite;
}

@keyframes indeterminate {
  0% { transform: translateX(-100%); }
  50% { transform: translateX(150%); }
  100% { transform: translateX(350%); }
}

.loading-label {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.45);
  text-align: center;
}

/* Phase B: Denoising Active */
.denoising-active-phase {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  width: 100%;
}

.preview-container {
  width: 100%;
  display: flex;
  justify-content: center;
}

.denoising-preview-large {
  max-width: 100%;
  max-height: clamp(300px, 40vh, 500px);
  object-fit: contain;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.denoising-compact {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.denoising-compact .step-bar-track {
  height: 3px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
  overflow: hidden;
}

.denoising-compact .step-bar-fill {
  height: 100%;
  background: rgba(76, 175, 80, 0.7);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.stats-line-compact {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-size: 0.72rem;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: rgba(255, 255, 255, 0.5);
  flex-wrap: wrap;
}

.stat-seg {
  white-space: nowrap;
}

.stat-sep {
  color: rgba(255, 255, 255, 0.2);
}

/* Encoding step status */
.encoding-step-text {
  color: rgba(76, 175, 80, 0.85);
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 0.72rem;
  white-space: nowrap;
}

/* Expert fact (shared between phases) */
.expert-fact {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  padding: 0.6rem 0.8rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  border-left: 2px solid rgba(76, 175, 80, 0.3);
  line-height: 1.4;
  min-height: 2.5rem;
  transition: opacity 0.3s ease;
}

/* Phase A→B crossfade transition */
.phase-switch-enter-active,
.phase-switch-leave-active {
  transition: opacity 0.25s ease;
}

.phase-switch-enter-from,
.phase-switch-leave-to {
  opacity: 0;
}

/* Responsive */
@media (max-width: 768px) {
  .model-specs {
    grid-template-columns: 1fr;
    gap: 0.25rem;
  }

  .spec-row {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }

  .denoising-preview-large {
    max-height: clamp(200px, 30vh, 350px);
  }
}
</style>
