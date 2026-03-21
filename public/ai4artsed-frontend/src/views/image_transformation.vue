<template>
  <div class="image-transformation-view">

    <div class="phase-2a" ref="mainContainerRef">

      <!-- Section 1: Image Upload + Context (Side by Side) -->
      <section class="input-context-section">
        <!-- Image Upload/Sketch Bubble (LEFT) -->
        <MediaInputBox
          icon="💡"
          :label="$t('imageTransform.imageLabel')"
          :value="uploadedImage ?? ''"
          @update:value="(val: string) => uploadedImage = val || undefined"
          input-type="image"
          :allow-sketch="true"
          :initial-image="uploadedImage"
          @image-uploaded="handleImageUpload"
          @image-removed="handleImageRemove"
          @copy="copyUploadedImage"
          @paste="pasteUploadedImage"
          @clear="clearImage"
        />

        <!-- Context Bubble (RIGHT) — with Stage 2 Interception streaming -->
        <MediaInputBox
          icon="📋"
          :label="$t('imageTransform.contextLabel')"
          :placeholder="$t('imageTransform.contextPlaceholder')"
          v-model:value="contextPrompt"
          input-type="text"
          :rows="6"
          :is-filled="!!contextPrompt"
          :is-required="!contextPrompt"
          :is-loading="isInterceptionLoading"
          :show-preset-button="true"
          :enable-streaming="true"
          :stream-url="interceptionStreamingUrl"
          :stream-params="interceptionStreamingParams"
          @open-preset-selector="showPresetOverlay = true"
          @stream-started="handleInterceptionStreamStarted"
          @stream-complete="handleInterceptionStreamComplete"
          @stream-error="handleInterceptionStreamError"
          @copy="copyContextPrompt"
          @paste="pasteContextPrompt"
          @clear="clearContextPrompt"
        />
      </section>

      <!-- Section 3: Category Selection (Horizontal Row) - Always visible after context -->
      <section v-if="canSelectMedia" class="category-section" ref="categorySectionRef">
        <div class="category-bubbles-row">
          <div
            v-for="category in availableCategories"
            :key="category.id"
            class="category-bubble"
            :class="{ selected: selectedCategory === category.id, disabled: category.disabled }"
            :style="{ '--bubble-color': category.color }"
            @click="!category.disabled && selectCategory(category.id)"
            role="button"
            :aria-pressed="selectedCategory === category.id"
            :aria-disabled="category.disabled"
            :tabindex="category.disabled ? -1 : 0"
            @keydown.enter="!category.disabled && selectCategory(category.id)"
            @keydown.space.prevent="!category.disabled && selectCategory(category.id)"
          >
            <div class="bubble-emoji-small">
              <svg v-if="category.id === 'image'" height="32" viewBox="0 -960 960 960" width="32" fill="currentColor">
                <path d="M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h560q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560H200v560Zm40-80h480L570-480 450-320l-90-120-120 160Zm-40 80v-560 560Zm140-360q25 0 42.5-17.5T400-620q0-25-17.5-42.5T340-680q-25 0-42.5 17.5T280-620q0 25 17.5 42.5T340-560Z"/>
              </svg>
              <svg v-else-if="category.id === 'video'" xmlns="http://www.w3.org/2000/svg" height="32" viewBox="0 -960 960 960" width="32" fill="currentColor">
                <path d="M200-320h400L462-500l-92 120-62-80-108 140Zm-40 160q-33 0-56.5-23.5T80-240v-480q0-33 23.5-56.5T160-800h480q33 0 56.5 23.5T720-720v180l160-160v440L720-420v180q0 33-23.5 56.5T640-160H160Zm0-80h480v-480H160v480Zm0 0v-480 480Z"/>
              </svg>
              <svg v-else-if="category.id === 'sound'" xmlns="http://www.w3.org/2000/svg" height="32" viewBox="0 -960 960 960" width="32" fill="currentColor">
                <path d="M709-255H482L369-142q-23 23-56.5 23T256-142L143-255q-23-23-23-57t23-57l112-112v-227l454 453Zm-193-80L335-516v68L199-312l113 113 136-136h68ZM289-785q107-68 231.5-54.5T735-736q90 90 103.5 214.5T784-290l-58-58q45-82 31.5-173.5T678-679q-66-66-157.5-79.5T347-727l-58-58Zm118 118q57-17 115-7t100 52q42 42 51.5 99.5T666-408l-68-68q0-25-7.5-48.5T566-565q-18-18-41.5-26t-49.5-8l-68-68Zm-49 309Z"/>
              </svg>
              <span v-else>{{ category.emoji }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Section 3.5: Model Selection (appears BELOW category, filtered by selected category) -->
      <section v-if="selectedCategory" class="config-section">
        <h2 class="section-title">wähle ein Modell aus</h2>
        <div class="config-bubbles-container">
          <div class="config-bubbles-row">
            <div
              v-for="config in configsForCategory"
              :key="config.id"
              class="config-bubble"
              :class="{
                selected: selectedConfig === config.id,
                'light-bg': config.lightBg,
                disabled: false,
                hovered: hoveredConfigId === config.id
              }"
              :style="{ '--bubble-color': config.color }"
              @click="selectModel(config.id)"
              @mouseenter="hoveredConfigId = config.id"
              @mouseleave="hoveredConfigId = null"
              role="button"
              :aria-pressed="selectedConfig === config.id"
              tabindex="0"
            >
              <img v-if="config.logo" :src="config.logo" :alt="config.label" class="bubble-logo" />
              <div v-else class="bubble-emoji-medium">{{ config.emoji }}</div>

              <!-- Hover info overlay (shows INSIDE bubble when hovered) -->
              <div v-if="hoveredConfigId === config.id" class="bubble-hover-info">
                <div class="hover-info-name">{{ config.name }}</div>
                <div class="hover-info-meta">
                  <div class="meta-row">
                    <span class="meta-label">Qual.</span>
                    <span class="meta-value">
                      <span class="stars-filled">{{ '★'.repeat(config.quality) }}</span><span class="stars-unfilled">{{ '☆'.repeat(5 - config.quality) }}</span>
                    </span>
                  </div>
                  <div class="meta-row">
                    <span class="meta-label">Speed</span>
                    <span class="meta-value">
                      <span class="stars-filled">{{ '★'.repeat(config.speed) }}</span><span class="stars-unfilled">{{ '☆'.repeat(5 - config.speed) }}</span>
                    </span>
                  </div>
                  <div class="meta-row">
                    <span class="meta-value duration-only">⏱ {{ config.duration }} sec</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- START BUTTON (Always Visible) -->
      <GenerationButton
        :disabled="!canStartGeneration"
        :executing="isPipelineExecuting"
        :label="$t('common.start')"
        :executing-label="$t('common.generating')"
        :error-message="generationErrorMessage"
        @click="startGeneration"
      >
        <SafetyBadges v-if="safetyChecks.length > 0" :checks="safetyChecks" />
      </GenerationButton>

      <!-- OUTPUT BOX (Template Component) -->
      <MediaOutputBox
        ref="pipelineSectionRef"
        :output-image="outputImage"
        :media-type="outputMediaType"
        :mesh-url="outputMeshUrl"
        :thumbnail-url="outputThumbnailUrl"
        :is-executing="isPipelineExecuting"
        :progress="generationProgress"
        :estimated-seconds="estimatedGenerationSeconds"
        :preview-image="previewImage"
        :is-analyzing="isAnalyzing"
        :show-analysis="showAnalysis"
        :analysis-data="imageAnalysis"
        :run-id="currentRunId"
        :is-favorited="isFavorited"
        :model-meta="modelMeta"
        :ui-mode="uiModeStore.mode"
        :stage4-duration-ms="stage4DurationMs"
        forward-button-title="Erneut Transformieren"
        @save="saveMedia"
        @print="printImage"
        @forward="sendToI2I"
        @download="downloadMedia"
        @analyze="analyzeImage"
        @image-click="showImageFullscreen"
        @close-analysis="showAnalysis = false"
        @toggle-favorite="toggleFavorite"
      />

    </div>

    <!-- Fullscreen Image Modal -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div v-if="fullscreenImage" class="fullscreen-modal" @click="fullscreenImage = null">
          <img :src="fullscreenImage" alt="Dein Bild" class="fullscreen-image" />
          <button class="close-fullscreen" @click="fullscreenImage = null">×</button>
        </div>
      </Transition>
    </Teleport>

    <!-- Interception Preset Selection Overlay -->
    <InterceptionPresetOverlay
      :visible="showPresetOverlay"
      @close="showPresetOverlay = false"
      @preset-selected="handlePresetSelected"
    />

  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import ImageUploadWidget from '@/components/ImageUploadWidget.vue'
import MediaOutputBox from '@/components/MediaOutputBox.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import SafetyBadges from '@/components/SafetyBadges.vue'
import GenerationButton from '@/components/GenerationButton.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import { usePipelineExecutionStore } from '@/stores/pipelineExecution'
import { useFavoritesStore } from '@/stores/favorites'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useDeviceId } from '@/composables/useDeviceId'
import { getModelAvailability, type ModelAvailability } from '@/services/api'
import { usePageContextStore } from '@/stores/pageContext'
import { useUiModeStore } from '@/stores/uiMode'
import { useGenerationStream } from '@/composables/useGenerationStream'
import { useI18n } from 'vue-i18n'
import type { SupportedLanguage } from '@/i18n'
import type { PageContext, FocusHint } from '@/composables/usePageContext'

// ============================================================================
// STATE
// ============================================================================

// Global clipboard (shared across all views)
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()

// UI mode for expert denoising view
const uiModeStore = useUiModeStore()

// Image upload
const uploadedImage = ref<string | undefined>(undefined)  // Base64 preview URL or server URL
const uploadedImagePath = ref<string | undefined>(undefined)  // Server path for backend
const uploadedImageId = ref<string | undefined>(undefined)  // Run ID or pasted timestamp

// Form inputs
const contextPrompt = ref('')
const showPresetOverlay = ref(false)
const selectedCategory = ref<string | null>(null)
const selectedConfig = ref<string | null>(null)  // User selects model from bubbles
const hoveredConfigId = ref<string | null>(null)  // For hover cards

// Estimated generation duration from selected config
const estimatedGenerationSeconds = computed(() => {
  if (!selectedConfig.value || !selectedCategory.value) return 30
  const configs = configsByCategory.value[selectedCategory.value] || []
  const config = configs.find(c => c.id === selectedConfig.value)
  return parseInt(config?.duration || '30') || 30
})

// Model availability (Session 91+)
const modelAvailability = ref<ModelAvailability>({})
const availabilityLoading = ref(true)

// Phase 4: Seed management
const previousOptimizedPrompt = ref('')
const previousSelectedConfig = ref('')
const currentSeed = ref<number | null>(null)

const deviceId = useDeviceId()

// Stage 2 Interception (Jugendschutz)
const isInterceptionLoading = ref(false)
const interceptionDone = ref(false)
const lastInterceptionConfigId = ref<string | null>(null)
const pendingGeneration = ref(false)  // true when startGeneration triggered interception

// Execution
const executionPhase = ref<'initial' | 'image_uploaded' | 'ready_for_media' | 'generation_done'>('initial')
const isPipelineExecuting = ref(false)
const generationErrorMessage = ref('')
const outputImage = ref<string | null>(null)
const outputMediaType = ref<string>('image')
const outputMeshUrl = ref<string | null>(null)
const outputThumbnailUrl = ref<string | null>(null)
const fullscreenImage = ref<string | null>(null)

// Session 148: SSE-based generation with real-time badge updates
const {
  showSafetyApprovedStamp,
  showTranslatedStamp,
  safetyChecks,
  generationProgress,
  previewImage,
  currentStage,
  modelMeta,
  stage4DurationMs,
  executeWithStreaming,
  reset: resetGenerationStream
} = useGenerationStream()

const { t, locale } = useI18n()

// Image Analysis
const isAnalyzing = ref(false)
const imageAnalysis = ref<{
  analysis: string
  reflection_prompts: string[]
  insights: string[]
  success: boolean
} | null>(null)
const showAnalysis = ref(false)

// Refs
const mainContainerRef = ref<HTMLElement | null>(null)
const categorySectionRef = ref<HTMLElement | null>(null)
const pipelineSectionRef = ref<any>(null) // MediaOutputBox component instance

// ============================================================================
// Page Context for Träshy (Session 133)
// ============================================================================
const pageContextStore = usePageContextStore()

const trashyFocusHint = computed<FocusHint>(() => {
  // During/after generation: bottom-right near output
  if (isPipelineExecuting.value || outputImage.value) {
    return { x: 95, y: 85, anchor: 'bottom-right' }
  }
  // After image upload, during selection: move right
  if (uploadedImage.value && selectedCategory.value) {
    return { x: 95, y: 70, anchor: 'bottom-right' }
  }
  // Image uploaded but no category yet: center-right
  if (uploadedImage.value) {
    return { x: 95, y: 50, anchor: 'bottom-right' }
  }
  // Initial: bottom-left
  return { x: 2, y: 95, anchor: 'bottom-left' }
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'image_transformation',
  pageContent: {
    uploadedImage: uploadedImage.value ? '[Bild hochgeladen]' : null,
    contextPrompt: contextPrompt.value,
    selectedCategory: selectedCategory.value,
    selectedConfig: selectedConfig.value
  },
  focusHint: trashyFocusHint.value
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onUnmounted(() => {
  pageContextStore.clearContext()
})

// ============================================================================
// CONFIGURATION
// ============================================================================

interface Category {
  id: string
  label: string
  emoji: string
  color: string
  disabled?: boolean
}

const availableCategories = computed<Category[]>(() => [
  { id: 'image', label: t('imageTransform.categories.image'), emoji: '🖼️', color: '#4CAF50' },
  { id: 'video', label: t('imageTransform.categories.video'), emoji: '🎬', color: '#9C27B0' },
  { id: '3d', label: t('imageTransform.categories.threeD'), emoji: '🧊', color: '#00BCD4' },
  { id: 'sound', label: t('imageTransform.categories.sound'), emoji: '🔊', color: '#FF9800', disabled: true }
])

// Available IMG2IMG Models (copied structure from text_transformation.vue)
interface ModelConfig {
  id: string
  label: string
  emoji: string
  name: string
  quality: number  // 1-5 stars
  speed: number    // 1-5 stars
  duration: string // e.g. "23" or "40-60"
  color: string    // Bubble color
  logo?: string    // Logo path
  lightBg?: boolean
}

const configsByCategory = computed<Record<string, ModelConfig[]>>(() => ({
  image: [
    {
      id: 'qwen_img2img',
      label: 'Qwen',
      emoji: '🌸',
      name: t('imageTransform.configs.qwenImg2img.name'),
      quality: 3,
      speed: 5,
      duration: '23',
      color: '#9C27B0',
      logo: '/logos/Qwen_logo.png',
      lightBg: false
    }
  ],
  video: [
    {
      id: 'wan22_i2v_video',
      label: 'WAN 2.2',
      emoji: '🎬',
      name: t('imageTransform.configs.wan22I2v.name'),
      quality: 4,
      speed: 3,
      duration: '35',
      color: '#9C27B0',
      logo: '/logos/Qwen_logo.png',
      lightBg: false
    }
  ],
  '3d': [
    {
      id: 'hunyuan3d_text_to_3d',
      label: t('imageTransform.configs.hunyuan3d.label'),
      emoji: '🧊',
      name: t('imageTransform.configs.hunyuan3d.name'),
      quality: 4,
      speed: 2,
      duration: '60',
      color: '#00BCD4'
    }
  ],
  sound: []   // Future
}))

// ============================================================================
// COMPUTED
// ============================================================================

const configsForCategory = computed(() => {
  if (!selectedCategory.value) return []

  const categoryConfigs = configsByCategory.value[selectedCategory.value] || []

  // Filter out unavailable configs (Session 91+)
  if (Object.keys(modelAvailability.value).length > 0) {
    return categoryConfigs.filter(config => {
      // STRICT MODE: Only show if explicitly marked as available
      // If not in availability map or marked as false → HIDE
      return modelAvailability.value[config.id] === true
    })
  }

  // While loading, show all configs (avoid flicker)
  return categoryConfigs
})

const canSelectMedia = computed(() => {
  return uploadedImage.value && contextPrompt.value.trim().length > 0
})

const canStartGeneration = computed(() => {
  return (
    uploadedImage.value &&
    contextPrompt.value.trim().length > 0 &&
    selectedCategory.value &&
    selectedConfig.value &&
    !isPipelineExecuting.value
  )
})

// Check if current output is favorited
const isFavorited = computed(() => {
  if (!currentRunId.value) return false
  return favoritesStore.isFavorited(currentRunId.value)
})

// ============================================================================
// IMAGE UPLOAD HANDLERS
// ============================================================================

function handleImageUpload(data: any) {
  console.log('[Image Upload] Success:', data)
  console.log('[Image Upload] Preview URL type:', typeof data.preview_url)
  console.log('[Image Upload] Preview URL length:', data.preview_url?.length)
  uploadedImage.value = data.preview_url
  uploadedImagePath.value = data.image_path
  uploadedImageId.value = data.image_id
  executionPhase.value = 'image_uploaded'
}

function clearImage() {
  handleImageRemove()
  sessionStorage.removeItem('i2i_uploaded_image')
  sessionStorage.removeItem('i2i_uploaded_image_path')
  sessionStorage.removeItem('i2i_uploaded_image_id')
  console.log('[I2I] Image cleared via action button')
}

// ============================================================================
// Image Clipboard Actions
// ============================================================================

function copyUploadedImage() {
  if (!uploadedImage.value) {
    console.warn('[I2I] No image to copy')
    return
  }

  // Copy image URL to clipboard (like text)
  copyToClipboard(uploadedImage.value)
  console.log('[I2I] Image URL copied to app clipboard:', uploadedImage.value)
}

function base64ToBlob(dataUrl: string): Blob | null {
  try {
    const [header, base64Content] = dataUrl.split(',')
    if (!header || !base64Content) return null

    const mimeMatch = header.match(/data:(.*?);/)
    const mimeType = mimeMatch ? mimeMatch[1] : 'image/png'

    const binaryString = atob(base64Content)
    const bytes = new Uint8Array(binaryString.length)
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i)
    }

    return new Blob([bytes], { type: mimeType })
  } catch (error) {
    console.error('[I2I] Failed to convert Base64 to Blob:', error)
    return null
  }
}

async function uploadImageToBackend(imageBlob: Blob, filename: string = 'pasted-image.png'): Promise<string | null> {
  try {
    const formData = new FormData()
    formData.append('file', imageBlob, filename)

    const response = await axios.post('/api/media/upload/image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    if (response.data.success) {
      console.log('[I2I] Image uploaded successfully:', response.data.image_path)
      return response.data.image_path
    } else {
      console.error('[I2I] Upload failed:', response.data.error)
      return null
    }
  } catch (error: any) {
    console.error('[I2I] Upload error:', error)
    return null
  }
}

async function pasteUploadedImage() {
  const clipboardContent = pasteFromClipboard()

  if (!clipboardContent) {
    console.warn('[I2I] Clipboard is empty')
    return
  }

  // Check if clipboard contains a valid image URL (Base64 Data-URL, Server-URL, or external URL)
  const isImageUrl = clipboardContent.startsWith('data:image/') ||
                     clipboardContent.startsWith('/api/media/image/') ||
                     clipboardContent.startsWith('http://') ||
                     clipboardContent.startsWith('https://')

  if (!isImageUrl) {
    console.warn('[I2I] Clipboard does not contain a valid image URL:', clipboardContent.substring(0, 100))
    return
  }

  // CASE 1: Server URL or external URL - use directly
  if (!clipboardContent.startsWith('data:image/')) {
    uploadedImage.value = clipboardContent
    uploadedImagePath.value = clipboardContent

    const runIdMatch = clipboardContent.match(/\/api\/media\/image\/(.+)$/)
    uploadedImageId.value = runIdMatch ? runIdMatch[1] : `pasted_${Date.now()}`
    executionPhase.value = 'image_uploaded'

    console.log('[I2I] Image pasted from URL:', clipboardContent.substring(0, 100))
    return
  }

  // CASE 2: Base64 Data URL - convert and upload
  console.log('[I2I] Detected Base64 data URL, uploading to backend...')

  // Set preview immediately for instant feedback
  uploadedImage.value = clipboardContent
  executionPhase.value = 'image_uploaded'

  // Convert Base64 to Blob
  const imageBlob = base64ToBlob(clipboardContent)
  if (!imageBlob) {
    console.error('[I2I] Failed to convert Base64 to Blob')
    uploadedImagePath.value = clipboardContent // Fallback (will fail on generation)
    return
  }

  // Generate filename from timestamp
  const timestamp = Date.now()
  const filename = `pasted-image-${timestamp}.png`

  // Upload to backend
  const serverPath = await uploadImageToBackend(imageBlob, filename)

  if (serverPath) {
    // Success: Update with server path
    uploadedImagePath.value = serverPath
    uploadedImageId.value = `pasted_${timestamp}`
    console.log('[I2I] Base64 image uploaded successfully:', serverPath)
  } else {
    // Failure: Keep Base64 (will fail on generation, but at least preview works)
    console.error('[I2I] Failed to upload Base64 image to backend')
    uploadedImagePath.value = clipboardContent
    uploadedImageId.value = `pasted_failed_${timestamp}`
  }
}

function handleImageRemove() {
  console.log('[Image Upload] Removed')
  uploadedImage.value = undefined
  uploadedImagePath.value = undefined
  uploadedImageId.value = undefined
  // NOTE: Keep contextPrompt - user might want to upload different image with same context
  selectedCategory.value = null
  selectedConfig.value = null
  hoveredConfigId.value = null
  executionPhase.value = 'initial'
  outputImage.value = null
  isPipelineExecuting.value = false
}

// Watch contextPrompt changes and update phase
watch(contextPrompt, (newValue) => {
  console.log('[Context] Edited:', newValue.length, 'chars')

  // Manual edit after interception → re-check needed (but not during streaming)
  if (interceptionDone.value && !isInterceptionLoading.value && !pendingGeneration.value) {
    interceptionDone.value = false
    console.log('[I2I-STAGE2] Context edited after interception — re-check required')
  }

  // Update phase based on context prompt presence
  if (newValue.trim() && uploadedImage.value) {
    if (executionPhase.value === 'image_uploaded') {
      executionPhase.value = 'ready_for_media'
    }
  } else {
    if (executionPhase.value === 'ready_for_media') {
      executionPhase.value = 'image_uploaded'
    }
  }
})

// ============================================================================
// STAGE 2 INTERCEPTION (Jugendschutz — same pattern as t2x)
// ============================================================================

const interceptionStreamingUrl = computed(() => {
  if (!isInterceptionLoading.value) return undefined
  const isDev = import.meta.env.DEV
  return isDev
    ? 'http://localhost:17802/api/schema/pipeline/interception'
    : '/api/schema/pipeline/interception'
})

const interceptionStreamingParams = computed(() => {
  return {
    schema: lastInterceptionConfigId.value || 'user_defined',
    input_text: contextPrompt.value || t('imageTransform.defaultPrompt'),
    // Config-based interception: remind LLM that output will be applied to an input image
    context_prompt: 'IMPORTANT: The output text will be used as an instruction to transform an input image. Always reference "this image" or "the image" in your output. The user has uploaded a photo that the model will modify based on your text.',
    enable_streaming: true,
    device_id: deviceId
  }
})

async function runInterception(configId?: string) {
  const config = configId || 'user_defined'
  lastInterceptionConfigId.value = config
  interceptionDone.value = false
  // Clear box for streaming (unless user_defined safety-only — keep text visible)
  if (config !== 'user_defined') {
    contextPrompt.value = ''
  }
  await nextTick()
  isInterceptionLoading.value = true
  console.log(`[I2I-STAGE2] Starting interception with config: ${config}`)
}

function handleInterceptionStreamStarted() {
  console.log('[I2I-STAGE2] Stream started')
}

function handleInterceptionStreamComplete(data: any) {
  isInterceptionLoading.value = false
  interceptionDone.value = true
  console.log('[I2I-STAGE2] Stream complete:', data)

  // Check if LLM refused (safety block)
  const result = contextPrompt.value.trim()
  const isBlocked = result.includes('Hierbei kann ich Dich nicht unterstützen') ||
      result.includes('kann ich dich nicht unterstützen')

  if (isBlocked) {
    console.log('[I2I-STAGE2] Safety block detected in interception result')
    pendingGeneration.value = false
    // Keep the refusal text visible — user sees why it was blocked
    return
  }

  // If generation was pending (triggered by startGeneration), resume it
  if (pendingGeneration.value) {
    pendingGeneration.value = false
    console.log('[I2I-STAGE2] Interception done — resuming generation')
    startGeneration()
  }
}

function handleInterceptionStreamError(error: any) {
  isInterceptionLoading.value = false
  pendingGeneration.value = false
  console.error('[I2I-STAGE2] Stream error:', error)
}

// ============================================================================
// MODEL SELECTION (copied from text_transformation.vue)
// ============================================================================

function selectModel(modelId: string) {
  selectedConfig.value = modelId
  console.log('[Model] Selected:', modelId)
}

// ============================================================================
// CATEGORY SELECTION
// ============================================================================

async function selectCategory(categoryId: string) {
  selectedCategory.value = categoryId
  console.log('[Category] Selected:', categoryId)

  await nextTick()
  scrollDownOnly(categorySectionRef.value, 'start')
}

// ============================================================================
// GENERATION (Stage 4)
// ============================================================================

async function startGeneration() {
  if (!canStartGeneration.value) return

  // Stage 2 Jugendschutz gate (no config selected):
  // Uses /pipeline/stage2 endpoint which runs ONLY Stage 1 (§86a+DSGVO) + Stage 2
  // (interception with safety prefix). No optimization, no Stage 3-4, no image generation.
  // The LLM either passes the text through or refuses — we check the result but do NOT
  // modify the user's original text in the box.
  if (!interceptionDone.value) {
    console.log('[I2I] No interception done — running Stage 2 safety check')
    isPipelineExecuting.value = true  // Show loading state on button
    generationErrorMessage.value = ''
    const isDev = import.meta.env.DEV
    const baseUrl = isDev ? 'http://localhost:17802' : ''
    try {
      const res = await fetch(`${baseUrl}/api/schema/pipeline/stage2`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          schema: 'user_defined',
          input_text: contextPrompt.value,
          skip_optimization: true
        })
      })
      const data = await res.json()

      // Stage 1 blocked (§86a or DSGVO)
      if (!data.success) {
        generationErrorMessage.value = data.error || 'Safety check failed'
        isPipelineExecuting.value = false
        console.log('[I2I-STAGE2] Blocked by Stage 1:', data.error)
        return
      }

      // Stage 2 refusal check — LLM handles safety via SAFETY_PREFIX
      const result = (data.interception_result || data.stage2_result || '').trim()
      const isRefusal = result.includes('Hierbei kann ich Dich nicht unterstützen') ||
          result.includes('kann ich dich nicht unterstützen') ||
          result.toLowerCase().includes('cannot support you') ||
          result.toLowerCase().includes('i can\'t help') ||
          result.toLowerCase().includes('i cannot') ||
          result === ''

      if (isRefusal) {
        generationErrorMessage.value = result || 'Content blocked by safety check'
        isPipelineExecuting.value = false
        console.log(`[I2I-STAGE2] Blocked by LLM refusal`)
        return
      }
      interceptionDone.value = true
      console.log(`[I2I-STAGE2] Safety passed`)
    } catch (e) {
      console.error('[I2I-STAGE2] Safety check error:', e)
      generationErrorMessage.value = 'Safety check unavailable'
      isPipelineExecuting.value = false
      return
    }
  }

  isPipelineExecuting.value = true
  resetGenerationStream()  // Session 148: Reset badges via composable
  generationErrorMessage.value = ''
  outputImage.value = null  // Clear previous output
  outputMeshUrl.value = null
  outputThumbnailUrl.value = null

  // Scroll to output frame
  await nextTick()
  setTimeout(() => scrollDownOnly(pipelineSectionRef.value?.sectionRef, 'start'), 150)

  // Phase 4: Intelligent seed logic
  // Track both prompt AND model — only randomize seed when NEITHER changed (user wants variation)
  const currentPromptToUse = contextPrompt.value
  const currentConfig = selectedConfig.value || ''

  if (currentPromptToUse === previousOptimizedPrompt.value && currentConfig === previousSelectedConfig.value) {
    // Prompt AND model unchanged → Generate new random seed (user wants variation)
    currentSeed.value = Math.floor(Math.random() * 2147483647)
    console.log('[Phase 4] Prompt+model unchanged → New random seed:', currentSeed.value)
  } else {
    // Prompt OR model changed → Keep same seed (user wants to compare)
    if (currentSeed.value === null) {
      currentSeed.value = 123456789
      console.log('[Phase 4] First run → Default seed:', currentSeed.value)
    } else {
      console.log('[Phase 4] Prompt or model changed → Keeping seed:', currentSeed.value)
    }
    previousOptimizedPrompt.value = currentPromptToUse
    previousSelectedConfig.value = currentConfig
  }

  try {
    // Session 148: Use SSE streaming for real-time badge updates
    const result = await executeWithStreaming({
      prompt: contextPrompt.value,
      output_config: selectedConfig.value || '',
      input_image: uploadedImagePath.value,
      seed: currentSeed.value,
      input_text: contextPrompt.value,
      context_prompt: contextPrompt.value,
      device_id: deviceId
    })

    console.log('[GENERATION-STREAM] Result:', result)

    if (result.status === 'success' && result.media_output) {
      const runId = result.media_output.run_id || result.run_id
      const mediaType = result.media_output.media_type || 'image'
      const mediaIndex = result.media_output.index ?? 0

      console.log('[Generation] Success, run_id:', runId, 'media_type:', mediaType, 'index:', mediaIndex, 'full media_output:', JSON.stringify(result.media_output))

      if (runId) {
        currentRunId.value = runId
        outputMediaType.value = mediaType

        if (mediaType === '3d') {
          // 3D model: set mesh URL for <model-viewer>, thumbnail as poster
          const meshUrl = result.media_output.mesh_url || result.media_output.url || `/api/media/3d/${runId}`
          const thumbUrl = result.media_output.thumbnail_url || null
          console.log('[3D] meshUrl:', meshUrl, 'thumbnailUrl:', thumbUrl)
          outputMeshUrl.value = meshUrl
          outputThumbnailUrl.value = thumbUrl
          outputImage.value = thumbUrl  // fallback for non-3d contexts
        } else {
          outputImage.value = `/api/media/${mediaType}/${runId}/${mediaIndex}`
        }

        executionPhase.value = 'generation_done'
      }
    } else if (result.status === 'blocked') {
      // safetyStore.reportBlock now handled centrally in useGenerationStream
      generationProgress.value = 0
    } else if (result.status === 'error') {
      console.error('[Generation] Failed:', result.error)
      generationProgress.value = 0
      const errorKey = result.errorType || 'unknown'
      generationErrorMessage.value = t(`generationError.${errorKey}`)
    }
  } catch (error: any) {
    console.error('[Generation] Error:', error)
    generationProgress.value = 0
    generationErrorMessage.value = t('generationError.unknown')
  } finally {
    isPipelineExecuting.value = false
  }
}

// ============================================================================
// FULLSCREEN
// ============================================================================

function showImageFullscreen(imageUrl: string) {
  fullscreenImage.value = imageUrl
}

// ============================================================================
// SCROLL HELPERS
// ============================================================================

function scrollDownOnly(element: HTMLElement | null, block: ScrollLogicalPosition = 'start') {
  if (!element) return
  const rect = element.getBoundingClientRect()
  const targetTop = block === 'start' ? rect.top : rect.bottom - window.innerHeight
  // Only scroll if target is below current viewport
  if (targetTop > 0) {
    element.scrollIntoView({ behavior: 'smooth', block })
  }
}

// ============================================================================
// Route handling & Store
// ============================================================================

const route = useRoute()
const pipelineStore = usePipelineExecutionStore()
const favoritesStore = useFavoritesStore()

// Current run tracking for favorites
const currentRunId = ref<string | null>(null)

// ============================================================================
// Textbox Actions (Copy/Paste/Delete)
// ============================================================================

function copyContextPrompt() {
  copyToClipboard(contextPrompt.value)
  console.log('[I2I] Context prompt copied to app clipboard')
}

function pasteContextPrompt() {
  contextPrompt.value = pasteFromClipboard()
  console.log('[I2I] Text pasted from app clipboard into context')
}

function clearContextPrompt() {
  contextPrompt.value = ''
  sessionStorage.removeItem('i2i_context_prompt')
  console.log('[I2I] Context prompt cleared')
}

function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  // Set context as input_text for interception (will be transformed)
  contextPrompt.value = payload.context
  sessionStorage.setItem('i2i_context_prompt', payload.context)
  console.log(`[I2I] Preset selected: ${payload.configName} (${payload.configId})`)
  // Trigger Stage 2 interception with selected config
  runInterception(payload.configId)
}

// ============================================================================
// Output Actions (Print, Download, Re-transform, Analyze, Save)
// ============================================================================

function saveMedia() {
  alert('Speichern-Funktion kommt bald!')
}

async function toggleFavorite() {
  if (!currentRunId.value) {
    console.warn('[I2I] No current run_id to favorite')
    return
  }

  // Convert outputMediaType to the correct type for favorites
  const mediaType = outputMediaType.value as 'image' | 'video' | 'audio' | 'music'
  await favoritesStore.toggleFavorite(currentRunId.value, mediaType, deviceId, 'anonymous', 'image-transformation')
  console.log('[I2I] Favorite toggled for run_id:', currentRunId.value)
}

function printImage() {
  if (!outputImage.value) return
  const printWindow = window.open('', '_blank')
  if (printWindow) {
    printWindow.document.write(`
      <html><head><title>Druck: Transformiertes Bild</title></head>
      <body style="margin:0;display:flex;justify-content:center;align-items:center;height:100vh;">
        <img src="${outputImage.value}" style="max-width:100%;max-height:100%;" onload="window.print();window.close()">
      </body></html>
    `)
    printWindow.document.close()
  }
  console.log('[I2I] Print initiated')
}

function sendToI2I() {
  if (!outputImage.value || outputMediaType.value !== 'image') return

  // Set current output as new input
  uploadedImage.value = outputImage.value
  uploadedImagePath.value = outputImage.value
  uploadedImageId.value = `retransform_${Date.now()}`

  // Keep context prompt for editing
  // Clear output to start fresh
  outputImage.value = null
  isPipelineExecuting.value = false
  executionPhase.value = 'image_uploaded'

  // Scroll to top to show input section
  window.scrollTo({ top: 0, behavior: 'smooth' })

  console.log('[I2I] Re-transform: Using output as new input')
}

async function downloadMedia() {
  if (!outputImage.value) return

  try {
    const response = await fetch(outputImage.value)
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url

    // Generate filename with timestamp
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:]/g, '-')
    const ext = outputMediaType.value === 'video' ? 'mp4' :
                outputMediaType.value === 'audio' || outputMediaType.value === 'music' ? 'mp3' :
                'png'
    a.download = `ai4artsed_i2i_${timestamp}.${ext}`

    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)

    console.log('[I2I Download] Media saved:', a.download)
  } catch (error) {
    console.error('[I2I Download] Error:', error)
    alert('Fehler beim Herunterladen')
  }
}

async function analyzeImage() {
  if (!outputImage.value || isAnalyzing.value) return

  isAnalyzing.value = true

  try {
    const response = await fetch('/api/image/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image_url: outputImage.value,
        context: contextPrompt.value || ''
      })
    })

    const data = await response.json()

    if (data.success) {
      imageAnalysis.value = {
        analysis: data.analysis || '',
        reflection_prompts: data.reflection_prompts || [],
        insights: data.insights || [],
        success: true
      }
      showAnalysis.value = true
      console.log('[I2I Analysis] Success:', data)
    } else {
      console.error('[I2I Analysis] Failed:', data.error)
      alert('Bildanalyse fehlgeschlagen')
    }
  } catch (error) {
    console.error('[I2I Analysis] Error:', error)
    alert('Fehler bei der Bildanalyse')
  } finally {
    isAnalyzing.value = false
  }
}

// ============================================================================
// Lifecycle - sessionStorage persistence + Phase1 config loading
// ============================================================================

onMounted(async () => {
  // Fetch model availability (Session 91+)
  try {
    const result = await getModelAvailability()
    if (result.status === 'success') {
      modelAvailability.value = result.availability
      console.log('[MODEL_AVAILABILITY] Loaded:', result.availability)
    } else {
      console.warn('[MODEL_AVAILABILITY] Check failed:', result.error)
    }
  } catch (error) {
    console.error('[MODEL_AVAILABILITY] Error fetching:', error)
  } finally {
    availabilityLoading.value = false
  }

  // Session persistence - restore previous context value
  const savedContext = sessionStorage.getItem('i2i_context_prompt')
  if (savedContext) {
    contextPrompt.value = savedContext
    console.log('[I2I] Restored context from sessionStorage')
  }

  // Check if coming from Phase1 with configId
  const configId = route.params.configId as string

  if (configId) {
    console.log('[I2I] Received configId from Phase1:', configId)

    try {
      // Load config and meta-prompt from backend
      await pipelineStore.setConfig(configId)
      await pipelineStore.loadMetaPromptForLanguage(locale.value as SupportedLanguage)

      // Overwrite ONLY context (unified with t2i pattern)
      const freshContext = pipelineStore.metaPrompt || ''
      contextPrompt.value = freshContext

      // Overwrite context storage for both t2i and i2i
      sessionStorage.setItem('t2i_context_prompt', freshContext)
      sessionStorage.setItem('i2i_context_prompt', freshContext)

      console.log('[I2I] Context overwritten from Phase1 config')
    } catch (error) {
      console.error('[I2I] Failed to load config:', error)
    }
  }

  // LEGACY: Check if there's a transferred image from text_transformation (Weiterreichen)
  const transferDataStr = localStorage.getItem('i2i_transfer_data')

  if (transferDataStr) {
    try {
      const transferData = JSON.parse(transferDataStr)
      const now = Date.now()
      const fiveMinutes = 5 * 60 * 1000

      // Check if transfer is recent (within last 5 minutes)
      if (now - transferData.timestamp < fiveMinutes) {
        console.log('[i2i Transfer] Loading transferred image:', transferData)

        // Set the image as if it was uploaded
        uploadedImage.value = transferData.imageUrl
        // Use the URL for display, but store run_id for backend
        uploadedImagePath.value = transferData.imageUrl
        uploadedImageId.value = transferData.runId || `transferred_${transferData.timestamp}`
        executionPhase.value = 'image_uploaded'

        // Clear the transfer data
        localStorage.removeItem('i2i_transfer_data')

        console.log('[i2i Transfer] Image loaded successfully')
      } else {
        // Transfer expired, clean up
        localStorage.removeItem('i2i_transfer_data')
        console.log('[i2i Transfer] Transfer expired (>5 minutes old)')
      }
    } catch (error) {
      console.error('[i2i Transfer] Error parsing transfer data:', error)
      localStorage.removeItem('i2i_transfer_data')
    }
  }

  // Clean up old format (backward compatibility)
  localStorage.removeItem('i2i_transfer_image')
  localStorage.removeItem('i2i_transfer_timestamp')

  // Check for sessionStorage persistence (normal reload)
  const savedImage = sessionStorage.getItem('i2i_uploaded_image')
  const savedImagePath = sessionStorage.getItem('i2i_uploaded_image_path')
  const savedImageId = sessionStorage.getItem('i2i_uploaded_image_id')

  if (savedImage && !transferDataStr) {  // Only if NOT from transfer
    console.log('[I2I] Restoring image from sessionStorage')
    console.log('[I2I] Preview URL:', savedImage.substring(0, 50) + '...')
    console.log('[I2I] Server Path:', savedImagePath)

    uploadedImage.value = savedImage
    uploadedImagePath.value = savedImagePath || savedImage
    uploadedImageId.value = savedImageId || `restored_${Date.now()}`
    executionPhase.value = 'image_uploaded'

    console.log('[I2I] Image restored successfully')
  }
})

// Watch for changes and persist to sessionStorage
watch(contextPrompt, (newVal) => {
  sessionStorage.setItem('i2i_context_prompt', newVal)
})

// ============================================================================
// Image Persistence - sessionStorage
// ============================================================================

watch(uploadedImage, (newVal) => {
  if (newVal) {
    sessionStorage.setItem('i2i_uploaded_image', newVal)
    console.log('[I2I] Saved image preview to sessionStorage')
  } else {
    sessionStorage.removeItem('i2i_uploaded_image')
  }
})

watch(uploadedImagePath, (newVal) => {
  if (newVal) {
    sessionStorage.setItem('i2i_uploaded_image_path', newVal)
  } else {
    sessionStorage.removeItem('i2i_uploaded_image_path')
  }
})

watch(uploadedImageId, (newVal) => {
  if (newVal) {
    sessionStorage.setItem('i2i_uploaded_image_id', newVal)
  } else {
    sessionStorage.removeItem('i2i_uploaded_image_id')
  }
})

// Restore from favorites (reactive, works even if already on page)
watch(() => favoritesStore.pendingRestoreData, (restoreData) => {
  if (!restoreData) return

  console.log('[I2I Restore] Processing:', Object.keys(restoreData))

  // Sequential copy/paste per JSON field
  // In I2I: context_prompt = input_text = transformation instruction
  // Prefer context_prompt if available, fallback to input_text
  const promptToRestore = restoreData.context_prompt || restoreData.input_text
  if (promptToRestore) {
    copyToClipboard(promptToRestore)
    contextPrompt.value = pasteFromClipboard()
  }

  // Note: I2I doesn't have interception result display
  // Input images not persisted (privacy) - user must re-upload

  // Clear after processing
  favoritesStore.setRestoreData(null)
}, { immediate: true })
</script>

<style scoped>
/* ============================================================================
   Root Container
   ============================================================================ */

.image-transformation-view {
  min-height: 100%;
  background: #0a0a0a;
  color: #ffffff;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  overflow-y: auto;
  overflow-x: hidden;
  padding-bottom: 120px; /* Space for FooterGallery */
}

/* ============================================================================
   Phase 2a: Vertical Flow
   ============================================================================ */

.phase-2a {
  max-width: clamp(320px, 90vw, 1100px);
  width: 100%;
  padding: clamp(1rem, 3vw, 2rem);
  padding-top: clamp(1rem, 3vw, 2rem); /* Reduced - App.vue header is smaller now */

  display: flex;
  flex-direction: column;
  align-items: center;
  gap: clamp(1rem, 3vh, 2rem);
}

/* ============================================================================
   Input + Context Section (Side by Side)
   ============================================================================ */

.input-context-section {
  display: flex;
  gap: clamp(1rem, 3vw, 2rem);
  width: 100%;
  justify-content: center;
  flex-wrap: wrap;
}

.input-context-section :deep(.media-input-box) {
  flex: 0 1 480px;
  width: 100%;
  max-width: 480px;
}

@media (max-width: 768px) {
  .input-context-section {
    flex-direction: column;
  }
}

/* ============================================================================
   Bubble Cards (Input/Context)
   ============================================================================ */

.bubble-card {
  background: rgba(20, 20, 20, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: clamp(12px, 2vw, 20px);
  padding: clamp(1rem, 2.5vw, 1.5rem);
  transition: all 0.3s ease;
  width: 100%;
  max-width: 1000px;
  display: flex;
  flex-direction: column;
}

.bubble-card.filled {
  border-color: rgba(102, 126, 234, 0.6);
  background: rgba(102, 126, 234, 0.1);
}

.bubble-card.required {
  border-color: rgba(255, 193, 7, 0.6);
  background: rgba(255, 193, 7, 0.05);
  animation: pulse-required 2s ease-in-out infinite;
}

@keyframes pulse-required {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.bubble-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.bubble-icon {
  font-size: clamp(1.25rem, 3vw, 1.5rem);
  flex-shrink: 0;
}

.bubble-label {
  font-size: clamp(0.9rem, 2vw, 1rem);
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.bubble-actions {
  display: flex;
  gap: 0.25rem;
  margin-left: auto;
}

.action-btn {
  background: transparent;
  border: none;
  font-size: 0.9rem;
  opacity: 0.4;
  cursor: pointer;
  transition: opacity 0.2s;
  padding: 0.25rem;
}

.action-btn:hover {
  opacity: 0.8;
}

.bubble-textarea {
  width: 100%;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: white;
  font-size: clamp(0.9rem, 2vw, 1rem);
  padding: clamp(0.5rem, 1.5vw, 0.75rem);
  resize: vertical;
  font-family: inherit;
  line-height: 1.4;
  flex-grow: 1;
  min-height: 0;
}

.bubble-textarea:focus {
  outline: none;
  border-color: rgba(102, 126, 234, 0.8);
  background: rgba(0, 0, 0, 0.4);
}

.bubble-textarea::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

/* ============================================================================
   Section: Image Upload & Context
   ============================================================================ */

.image-upload-section,
.context-section {
  width: 100%;
  display: flex;
  justify-content: center;
}

/* ============================================================================
   Section 3: Category Bubbles (Horizontal Row)
   ============================================================================ */

.category-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.category-bubbles-row {
  display: flex;
  flex-direction: row;
  gap: clamp(1rem, 2.5vw, 1.5rem);
  justify-content: center;
  flex-wrap: wrap;
}

.category-bubble {
  width: clamp(70px, 12vw, 90px);
  height: clamp(70px, 12vw, 90px);

  display: flex;
  align-items: center;
  justify-content: center;

  background: rgba(30, 30, 30, 0.9);
  border: 3px solid var(--bubble-color, rgba(255, 255, 255, 0.3));
  border-radius: 50%;

  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
}

.category-bubble:hover {
  transform: scale(1.08);
  box-shadow: 0 0 20px var(--bubble-color);
  border-width: 4px;
}

.category-bubble.selected {
  transform: scale(1.15);
  background: var(--bubble-color);
  box-shadow: 0 0 30px var(--bubble-color),
              0 0 60px var(--bubble-color);
  border-color: #ffffff;
}

.category-bubble:focus-visible {
  outline: 3px solid rgba(102, 126, 234, 0.8);
  outline-offset: 4px;
}

.category-bubble:active {
  transform: scale(0.95);
}

.category-bubble.disabled {
  opacity: 0.3;
  cursor: not-allowed;
  pointer-events: none;
  filter: grayscale(1);
}

.bubble-emoji-small {
  font-size: clamp(2rem, 4.5vw, 2.5rem);
  line-height: 1;
  transition: filter 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bubble-emoji-small svg {
  width: 32px;
  height: 32px;
}

.category-bubble.selected .bubble-emoji-small {
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.5));
}

/* Start button styles now in GenerationButton.vue + generation-button.css */

/* ============================================================================
   Fullscreen Modal
   ============================================================================ */

.fullscreen-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.95);
  backdrop-filter: blur(8px);
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.fullscreen-image {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.close-fullscreen {
  position: absolute;
  top: 2rem;
  right: 2rem;
  width: 4rem;
  height: 4rem;
  background: rgba(255, 255, 255, 0.1);
  border: 2px solid white;
  color: white;
  font-size: 2.5rem;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.close-fullscreen:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: scale(1.1);
}

/* ============================================================================
   Transitions
   ============================================================================ */

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

/* ============================================================================
   Responsive: Mobile Adjustments
   ============================================================================ */

@media (max-width: 768px) {
  .category-bubbles-row {
    gap: 1rem;
  }
}

/* iPad 1024×768 Optimization */
@media (min-width: 1024px) and (max-height: 768px) {
  .phase-2a {
    padding: 1.5rem;
    gap: 1.25rem;
  }
}

/* ============================================================================
   Model Selection Bubbles (copied from text_transformation.vue)
   ============================================================================ */

.config-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.config-bubbles-container {
  width: 100%;
  display: flex;
  justify-content: center;
}

.config-bubbles-row {
  display: inline-flex;
  flex-direction: row;
  gap: clamp(0.75rem, 2vw, 1rem);
  justify-content: center;
  flex-wrap: wrap;
  max-width: fit-content;
}

.config-bubble {
  position: relative;
  z-index: 1;
  width: clamp(80px, 12vw, 100px);
  height: clamp(80px, 12vw, 100px);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(30, 30, 30, 0.9);
  border: 3px solid var(--bubble-color, rgba(255, 255, 255, 0.3));
  border-radius: 50%;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
}

.config-bubble:hover:not(.disabled),
.config-bubble.hovered {
  transform: scale(2.0);
  background: rgba(20, 20, 20, 0.9);
  box-shadow: 0 0 30px var(--bubble-color);
  z-index: 100;
}

.config-bubble.selected {
  transform: scale(1.1);
  background: var(--bubble-color);
  box-shadow: 0 0 30px var(--bubble-color),
              0 0 60px var(--bubble-color);
  border-color: #ffffff;
}

.config-bubble.disabled {
  opacity: 0.3;
  cursor: not-allowed;
  pointer-events: none;
  filter: grayscale(0.8);
}

.bubble-emoji-medium {
  font-size: clamp(2.5rem, 5vw, 3.5rem);
  line-height: 1;
}

.bubble-logo {
  width: clamp(72px, 11vw, 92px);
  height: clamp(72px, 11vw, 92px);
  object-fit: contain;
}

.config-bubble.light-bg {
  background: rgba(255, 255, 255, 0.95);
}

.config-bubble.light-bg.selected {
  background: var(--bubble-color);
}

/* Hover info overlay */
.bubble-hover-info {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 18%;
  color: white;
  z-index: 10;
  pointer-events: none;
  gap: 0.3rem;
}

.hover-info-name {
  font-size: 0.5rem;
  font-weight: 600;
  text-align: center;
  line-height: 1.25;
  margin-bottom: 0;
  letter-spacing: -0.01em;
  color: rgba(255, 255, 255, 0.95);
  max-width: 100%;
  word-wrap: break-word;
}

.hover-info-meta {
  display: flex;
  flex-direction: column;
  gap: 0;
  width: 100%;
}

.meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.18rem;
  width: 100%;
  line-height: 1;
  margin: 0;
  padding: 0;
}

.meta-label {
  font-size: 0.45rem;
  color: rgba(255, 255, 255, 0.75);
  font-weight: 400;
  text-align: left;
  flex-shrink: 0;
  flex-basis: 35%;
  letter-spacing: -0.01em;
}

.meta-value {
  font-size: 0.65rem;
  font-weight: 500;
  text-align: right;
  white-space: nowrap;
  flex-shrink: 0;
  flex-basis: 60%;
  letter-spacing: 0.02em;
}

.stars-filled {
  color: #FFD700;
}

.stars-unfilled {
  color: rgba(150, 150, 150, 0.5);
}

.meta-value.duration-only {
  width: 100%;
  text-align: center;
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.45rem;
  flex-basis: auto;
  margin-top: 0.25rem;
  line-height: 1;
}

/* Hide logo/emoji when hovering */
.config-bubble.hovered .bubble-logo,
.config-bubble.hovered .bubble-emoji-medium {
  opacity: 0;
  display: none;
}

/* Action toolbar and analysis styles moved to MediaOutputBox.vue component */
</style>

<style>
/* GLOBAL unscoped - force MediaInputBox width */
.image-transformation-view .input-context-section > .media-input-box {
  flex: 0 1 480px !important;
  width: 100% !important;
  max-width: 480px !important;
}
</style>
