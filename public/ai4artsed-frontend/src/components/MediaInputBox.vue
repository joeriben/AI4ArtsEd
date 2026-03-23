<template>
  <div ref="inputBoxRef" class="media-input-box bubble-card" :class="{
    empty: isEmpty,
    filled: isFilled,
    required: isRequired,
    loading: isLoading
  }">
    <!-- Header -->
    <div class="bubble-header" :title="tooltip">
      <span class="bubble-icon">
        <!-- Lightbulb / Idea -->
        <svg v-if="icon === '💡' || icon === 'lightbulb'" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
          <path d="M480-80q-26 0-47-12.5T400-126q-33 0-56.5-23.5T320-206v-142q-59-39-94.5-103T190-590q0-121 84.5-205.5T480-880q121 0 205.5 84.5T770-590q0 77-35.5 140T640-348v142q0 33-23.5 56.5T560-126q-12 21-33 33.5T480-80Zm-80-126h160v-36H400v36Zm0-76h160v-38H400v38Zm-8-118h58v-108l-88-88 42-42 76 76 76-76 42 42-88 88v108h58q54-26 88-76.5T690-590q0-88-61-149t-149-61q-88 0-149 61t-61 149q0 63 34 113.5t88 76.5Zm88-162Zm0-38Z"/>
        </svg>
        <!-- Clipboard / List -->
        <svg v-else-if="icon === '📋' || icon === 'clipboard'" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
          <path d="M120-80v-60h100v-30h-60v-60h60v-30H120v-60h120q17 0 28.5 11.5T280-280v40q0 17-11.5 28.5T240-200q17 0 28.5 11.5T280-160v40q0 17-11.5 28.5T240-80H120Zm0-280v-110q0-17 11.5-28.5T160-510h60v-30H120v-60h120q17 0 28.5 11.5T280-560v70q0 17-11.5 28.5T240-450h-60v30h100v60H120Zm60-280v-180h-60v-60h120v240h-60Zm180 440v-80h480v80H360Zm0-240v-80h480v80H360Zm0-240v-80h480v80H360Z"/>
        </svg>
        <!-- Arrow / Forward -->
        <svg v-else-if="icon === '➡️' || icon === '→' || icon === 'arrow'" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
          <path d="m440-200 137-240H80v-80h497L440-760l440 280-440 280Z"/>
        </svg>
        <!-- Stars / AI Optimization -->
        <svg v-else-if="icon === '✨' || icon === 'stars'" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
          <path d="M160-120v-200q0-33 23.5-56.5T240-400h480q33 0 56.5 23.5T800-320v200H160Zm200-320q-83 0-141.5-58.5T160-640q0-83 58.5-141.5T360-840h240q83 0 141.5 58.5T800-640q0 83-58.5 141.5T600-440H360ZM240-200h480v-120H240v120Zm120-320h240q50 0 85-35t35-85q0-50-35-85t-85-35H360q-50 0-85 35t-35 85q0 50 35 85t85 35Zm0-80q17 0 28.5-11.5T400-640q0-17-11.5-28.5T360-680q-17 0-28.5 11.5T320-640q0 17 11.5 28.5T360-600Zm240 0q17 0 28.5-11.5T640-640q0-17-11.5-28.5T600-680q-17 0-28.5 11.5T560-640q0 17 11.5 28.5T600-600ZM480-200Zm0-440Z"/>
        </svg>
        <!-- Image / Picture -->
        <svg v-else-if="icon === '🖼️' || icon === '📷' || icon === 'image'" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
          <path d="M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h560q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560H200v560Zm40-80h480L570-480 450-320l-90-120-120 160Zm-40 80v-560 560Zm140-360q25 0 42.5-17.5T400-620q0-25-17.5-42.5T340-680q-25 0-42.5 17.5T280-620q0 25 17.5 42.5T340-560Z"/>
        </svg>
        <!-- Plus (for optional images) -->
        <svg v-else-if="icon === '➕' || icon === '+' || icon === 'plus'" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
          <path d="M480-480ZM200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h320v80H200v560h560v-320h80v320q0 33-23.5 56.5T760-120H200Zm40-160h480L570-480 450-320l-90-120-120 160Zm440-320v-80h-80v-80h80v-80h80v80h80v80h-80v80h-80Z"/>
        </svg>
        <!-- Fallback to emoji -->
        <span v-else>{{ icon }}</span>
      </span>
      <span class="bubble-label">{{ label }}</span>
      <div v-if="showActions" class="bubble-actions">
        <button v-if="showPresetButton" @click="$emit('open-preset-selector')" class="action-btn preset-btn" :class="{ 'preset-suggesting': isRequired }" :title="t('mediaInput.choosePreset')">
          <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M480-60q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm0-80q17 0 28.5-11.5T520-180q0-17-11.5-28.5T480-220q-17 0-28.5 11.5T440-180q0 17 11.5 28.5T480-140Zm-260-70q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm520 0q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm-520-80q17 0 28.5-11.5T260-330q0-17-11.5-28.5T220-370q-17 0-28.5 11.5T180-330q0 17 11.5 28.5T220-290Zm520 0q17 0 28.5-11.5T780-330q0-17-11.5-28.5T740-370q-17 0-28.5 11.5T700-330q0 17 11.5 28.5T740-290ZM220-510q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm520 0q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm-520-80q17 0 28.5-11.5T260-630q0-17-11.5-28.5T220-670q-17 0-28.5 11.5T180-630q0 17 11.5 28.5T220-590Zm520 0q17 0 28.5-11.5T780-630q0-17-11.5-28.5T740-670q-17 0-28.5 11.5T700-630q0 17 11.5 28.5T740-590Zm-260-70q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm0-80q17 0 28.5-11.5T520-780q0-17-11.5-28.5T480-820q-17 0-28.5 11.5T440-780q0 17 11.5 28.5T480-740Z"/>
          </svg>
        </button>
        <button
          v-if="showTranslate && inputType === 'text'"
          @click="translateToEnglish"
          class="action-btn translate-btn"
          :class="{ translating: isTranslating }"
          :disabled="isTranslating || !value.trim()"
          :title="t('mediaInput.translateToEnglish')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 30" class="union-jack">
            <!-- Background (blue) -->
            <rect width="60" height="30" fill="#012169"/>
            <!-- Diagonals (white + red) -->
            <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" stroke-width="6"/>
            <path d="M0,0 L60,30 M60,0 L0,30" stroke="#C8102E" stroke-width="2"/>
            <!-- Cross (white + red) -->
            <path d="M30,0 V30 M0,15 H60" stroke="#fff" stroke-width="10"/>
            <path d="M30,0 V30 M0,15 H60" stroke="#C8102E" stroke-width="6"/>
          </svg>
        </button>
        <button v-if="showCopy" @click="$emit('copy')" class="action-btn" :title="t('mediaInput.copy')">
          <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M360-240q-33 0-56.5-23.5T280-320v-480q0-33 23.5-56.5T360-880h360q33 0 56.5 23.5T800-800v480q0 33-23.5 56.5T720-240H360Zm0-80h360v-480H360v480ZM200-80q-33 0-56.5-23.5T120-160v-560h80v560h440v80H200Zm160-240v-480 480Z"/>
          </svg>
        </button>
        <button v-if="showPaste" @click="$emit('paste')" class="action-btn" :title="t('mediaInput.paste')">
          <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h167q11-35 43-57.5t70-22.5q40 0 71.5 22.5T594-840h166q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560h-80v120H280v-120h-80v560Zm280-560q17 0 28.5-11.5T520-800q0-17-11.5-28.5T480-840q-17 0-28.5 11.5T440-800q0 17 11.5 28.5T480-760Z"/>
          </svg>
        </button>
        <button v-if="showClear" @click="$emit('clear')" class="action-btn" :title="t('mediaInput.delete')">
          <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M280-120q-33 0-56.5-23.5T200-200v-520h-40v-80h200v-40h240v40h200v80h-40v520q0 33-23.5 56.5T680-120H280Zm400-600H280v520h400v-520ZM360-280h80v-360h-80v360Zm160 0h80v-360h-80v360ZM280-720v520-520Z"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Loading Overlay -->
    <div v-if="isLoading" class="preview-loading">
      <div class="spinner-large" :class="{ queued: queueStatus === 'waiting' }"></div>
      <p class="loading-text" :class="{ queued: queueStatus === 'waiting' }">
        {{ queueStatus === 'waiting' ? queueMessage : (loadingMessage || t('mediaInput.loading')) }}
      </p>
    </div>


    <!-- Content: CLIP-Prompt Display (SD3.5 per-encoder, T5 uses interception result) -->
    <div v-else-if="inputType === 'text' && triplePromptData" class="triple-prompt-display">
      <div class="triple-section">
        <div class="triple-label">CLIP-L <span class="triple-tag">Visual</span></div>
        <div class="triple-content">{{ triplePromptData.clip_l }}</div>
      </div>
      <div class="triple-section">
        <div class="triple-label">CLIP-G <span class="triple-tag">Semantic</span></div>
        <div class="triple-content">{{ triplePromptData.clip_g }}</div>
      </div>
      <div class="triple-t5-note">
        <svg xmlns="http://www.w3.org/2000/svg" height="14" viewBox="0 -960 960 960" width="14" fill="currentColor">
          <path d="M440-280h80v-240h-80v240Zm40-320q17 0 28.5-11.5T520-640q0-17-11.5-28.5T480-680q-17 0-28.5 11.5T440-640q0 17 11.5 28.5T480-600Zm0 520q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Z"/>
        </svg>
        {{ t('mediaInput.t5UsesYourText') }}
      </div>
    </div>

    <!-- Content: Text Input -->
    <textarea
      v-else-if="inputType === 'text'"
      ref="textareaRef"
      :value="value"
      @input="handleInput"
      @focus="handleFocus"
      @blur="handleBlur"
      @paste="handlePaste"
      :placeholder="placeholder"
      :rows="rows"
      :disabled="disabled"
      :class="['bubble-textarea', resizeClass, { disabled: disabled }]"
    ></textarea>

    <!-- Content: Image Input (with optional sketch toggle) -->
    <template v-else-if="inputType === 'image'">
      <!-- Upload / Sketch toggle (only when allowSketch is true) -->
      <div v-if="allowSketch" class="input-mode-toggle">
        <button
          class="mode-btn"
          :class="{ active: !sketchMode }"
          @click="sketchMode = false"
          :title="t('imageTransform.uploadMode')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" height="18" viewBox="0 -960 960 960" width="18" fill="currentColor">
            <path d="M440-200h80v-167l64 64 56-57-160-160-160 160 57 56 63-63v167ZM240-80q-33 0-56.5-23.5T160-160v-640q0-33 23.5-56.5T240-880h320l240 240v480q0 33-23.5 56.5T720-80H240Zm280-520v-200H240v640h480v-440H520ZM240-800v200-200 640-640Z"/>
          </svg>
          {{ t('imageTransform.uploadMode') }}
        </button>
        <button
          class="mode-btn"
          :class="{ active: sketchMode }"
          @click="sketchMode = true"
          :title="t('imageTransform.sketchMode')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" height="18" viewBox="0 -960 960 960" width="18" fill="currentColor">
            <path d="M200-200h57l391-391-57-57-391 391v57Zm-80 80v-170l528-527q12-11 26.5-17t30.5-6q16 0 31 6t26 18l55 56q12 11 17.5 26t5.5 30q0 16-5.5 30.5T817-647L290-120H120Zm640-584-56-56 56 56Zm-141 85-28-29 57 57-29-28Z"/>
          </svg>
          {{ t('imageTransform.sketchMode') }}
        </button>
      </div>

      <SketchCanvas
        v-if="sketchMode"
        @image-uploaded="handleImageUpload"
        @image-removed="$emit('image-removed')"
      />
      <ImageUploadWidget
        v-else
        :initial-image="initialImage"
        @image-uploaded="handleImageUpload"
        @image-removed="$emit('image-removed')"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import ImageUploadWidget from '@/components/ImageUploadWidget.vue'
import SketchCanvas from '@/components/SketchCanvas.vue'
import { useSafetyEventStore } from '@/stores/safetyEvent'

const { t, locale } = useI18n()
const safetyStore = useSafetyEventStore()

// Template refs for parent access (like MediaOutputBox sectionRef)
const inputBoxRef = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)

// Streaming state
const eventSource = ref<EventSource | null>(null)
const streamedValue = ref('')
const isStreamComplete = ref(false)
const isFirstChunkReceived = ref(false)
const chunkBuffer = ref<string[]>([])
let bufferInterval: number | null = null

// Autonomous safety state (fuzzy filter + NER + LLM on blur/paste)
const safetyResult = ref<{ safe: boolean; checks: string[]; error?: string } | null>(null)
const isCheckingSafety = ref(false)

// Translation state
const isTranslating = ref(false)

// Sketch mode (internal toggle when allowSketch + inputType=image)
const sketchMode = ref(false)

// Queue state
const queueStatus = ref<'idle' | 'waiting' | 'acquired'>('idle')
const queueMessage = ref('')

interface Props {
  icon: string
  label: string
  tooltip?: string
  placeholder?: string
  value: string
  inputType?: 'text' | 'image'
  rows?: number
  resizeType?: 'standard' | 'auto' | 'none'
  isEmpty?: boolean
  isRequired?: boolean
  isFilled?: boolean
  isLoading?: boolean
  loadingMessage?: string
  showActions?: boolean
  showCopy?: boolean
  showPaste?: boolean
  showClear?: boolean
  showTranslate?: boolean
  initialImage?: string
  disabled?: boolean
  showPresetButton?: boolean
  allowSketch?: boolean
  // Streaming props
  enableStreaming?: boolean
  streamUrl?: string
  streamParams?: Record<string, string | boolean>
}

const props = withDefaults(defineProps<Props>(), {
  inputType: 'text',
  rows: 6,
  resizeType: 'standard',
  isEmpty: false,
  isRequired: false,
  isFilled: false,
  isLoading: false,
  loadingMessage: undefined,
  showActions: true,
  showCopy: true,
  showPaste: true,
  showClear: true,
  showTranslate: true,
  initialImage: undefined,
  disabled: false,
  showPresetButton: false,
  tooltip: undefined,
  allowSketch: false
})

const emit = defineEmits<{
  'update:value': [value: string]
  'copy': []
  'paste': []
  'clear': []
  'focus': []  // Session 133: Emit when textarea gains focus (for Träshy positioning)
  'blur': [value: string]  // Session 130: Emit when textarea loses focus
  'image-uploaded': [data: any]  // Changed: Accept full data object from ImageUploadWidget
  'image-removed': []
  'open-preset-selector': []
  'stream-started': []  // Emitted on first chunk (to hide loading spinner)
  'stream-complete': [data: any]
  'stream-error': [error: string]
  'wikipedia-lookup': [data: { status: string; terms: Array<{ term: string; lang: string; title: string; url: string; success: boolean }> }]  // Session 139: Wikipedia lookup events (Session 136: with real URLs)
}>()

// Expose refs for parent access (like MediaOutputBox)
defineExpose({
  inputBoxRef,
  textareaRef,
  safetyResult,
  isCheckingSafety
})

// Computed Properties
const triplePromptData = computed(() => {
  if (!props.value || props.inputType !== 'text') return null
  const trimmed = props.value.trim()
  if (!trimmed.startsWith('{')) return null
  try {
    const data = JSON.parse(trimmed)
    if (data && typeof data === 'object' && 'clip_l' in data && 'clip_g' in data) {
      return data as { clip_l: string; clip_g: string }
    }
  } catch {
    // Not valid JSON — fall through to normal textarea
  }
  return null
})

const resizeClass = computed(() => {
  switch (props.resizeType) {
    case 'auto': return 'auto-resize-textarea'
    case 'none': return 'no-resize-textarea'
    case 'standard':
    default: return 'standard-resize-textarea'
  }
})

// Functions
function handleInput(event: Event) {
  const target = event.target as HTMLTextAreaElement
  emit('update:value', target.value)
}

// Session 133: Emit focus event for Träshy positioning
function handleFocus() {
  emit('focus')
}

// Session 130: Emit blur event for prompt logging + autonomous safety check
function handleBlur(event: Event) {
  const target = event.target as HTMLTextAreaElement
  emit('blur', target.value)
  checkSafety()
}

// Paste handler: check safety after pasted content is applied
function handlePaste() {
  nextTick(() => checkSafety())
}

// Quick-translate: destructive in-place DE→EN translation via backend
async function translateToEnglish() {
  if (!props.value.trim() || isTranslating.value) return
  isTranslating.value = true
  try {
    const baseUrl = import.meta.env.DEV ? 'http://localhost:17802' : ''
    const res = await fetch(`${baseUrl}/api/schema/pipeline/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: props.value, target_language: 'en' })
    })
    const data = await res.json()
    if (data.status === 'success' && data.translated_text) {
      emit('update:value', data.translated_text)
    }
  } catch (e) {
    console.warn('[MediaInputBox] Translation failed:', e)
  } finally {
    isTranslating.value = false
  }
}

// Autonomous safety check (called on blur + paste — NOT on stream-complete)
// "Innocent until proven guilty": text stays visible, only cleared if blocked.
// Backend safety checks (Stage 1 + Stage 3 + VLM) are the actual security boundary.
async function checkSafety() {
  const text = props.value?.trim()
  if (!text || props.inputType !== 'text' || props.disabled) return

  isCheckingSafety.value = true

  try {
    const baseUrl = import.meta.env.DEV ? 'http://localhost:17802' : ''
    const res = await fetch(`${baseUrl}/api/schema/pipeline/safety/quick`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, user_language: locale.value })
    })
    const data = await res.json()
    safetyResult.value = {
      safe: data.safe,
      checks: data.checks_passed || [],
      error: data.error_message || undefined
    }
    if (!data.safe) {
      // Blocked — clear content, Trashy explains why
      emit('update:value', '')
      safetyStore.reportBlock(1, data.error_message || t('mediaInput.contentBlocked'), [])
    }
  } catch {
    // Network error → fail-open, keep content
    safetyResult.value = { safe: true, checks: [] }
  } finally {
    isCheckingSafety.value = false
  }
}

function handleImageUpload(data: any) {
  // ImageUploadWidget emits full data object with preview_url, image_path, image_id
  emit('image-uploaded', data)
  emit('update:value', data.preview_url)  // Update v-model with preview URL
}

function autoResizeTextarea() {
  if (props.resizeType !== 'auto' || !textareaRef.value) return
  textareaRef.value.style.height = 'auto'
  textareaRef.value.style.height = (textareaRef.value.scrollHeight + 4) + 'px'
}

// Watchers
watch(() => props.value, async () => {
  if (props.inputType === 'text' && props.resizeType === 'auto') {
    await nextTick()
    autoResizeTextarea()
  }
})

// Streaming functions
function startStreaming() {
  console.log('[DEBUG MediaInputBox] startStreaming() called, streamUrl:', props.streamUrl, 'streamParams:', props.streamParams)

  if (!props.streamUrl) {
    console.log('[DEBUG MediaInputBox] No streamUrl, returning early')
    return
  }

  // Close any existing stream first
  closeStream()

  // Reset state
  streamedValue.value = ''
  isStreamComplete.value = false
  isFirstChunkReceived.value = false
  chunkBuffer.value = []
  safetyResult.value = null
  queueStatus.value = 'idle'
  queueMessage.value = ''

  // Build URL with query parameters (convert boolean values to strings)
  const paramsAsStrings = Object.fromEntries(
    Object.entries(props.streamParams || {}).map(([k, v]) => [k, String(v)])
  )
  const params = new URLSearchParams(paramsAsStrings)
  const url = `${props.streamUrl}?${params.toString()}`

  console.log('[MediaInputBox] Starting stream:', url)

  eventSource.value = new EventSource(url)

  // Start buffer processor for smooth character-by-character display
  startBufferProcessor()

  // Handle Queue Status
  eventSource.value.addEventListener('queue_status', (event) => {
    const data = JSON.parse(event.data)
    console.log('[MediaInputBox] Queue status:', data.status)
    
    if (data.status === 'waiting') {
      queueStatus.value = 'waiting'
      queueMessage.value = data.message
    } else if (data.status === 'acquired') {
      queueStatus.value = 'acquired'
      queueMessage.value = data.message
      // Short delay before switching back to loading text if needed
      setTimeout(() => {
        if (queueStatus.value === 'acquired') queueStatus.value = 'idle'
      }, 2000)
    }
  })

  eventSource.value.addEventListener('connected', (event) => {
    console.log('[MediaInputBox] Stream connected:', JSON.parse(event.data))
  })

  // Handle Wikipedia Lookup Status - emit to parent
  // Session 136: terms now include REAL Wikipedia results (title, url)
  eventSource.value.addEventListener('wikipedia_lookup', (event) => {
    const data = JSON.parse(event.data) as { status: string; terms: Array<{ term: string; lang: string; title: string; url: string; success: boolean }> }
    console.log('[MediaInputBox] Wikipedia lookup:', data.status, data.terms)
    // Debug: Log actual URLs received
    if (data.status === 'complete') {
      console.log('[MediaInputBox] Wikipedia URLs:')
      data.terms.forEach(t => {
        console.log(`  - ${t.url}`)
      })
    }
    emit('wikipedia-lookup', data)
  })

  eventSource.value.addEventListener('chunk', (event) => {
    const data = JSON.parse(event.data)
    console.log('[MediaInputBox] Chunk received:', data.chunk_count, 'text:', data.text_chunk)

    // Emit stream-started on first chunk (so parent can hide loading spinner)
    if (!isFirstChunkReceived.value) {
      isFirstChunkReceived.value = true
      emit('stream-started')
    }

    // Add chunk to buffer for smooth word-by-word display
    // Split on word boundaries, preserving whitespace with each word
    const text = data.text_chunk
    const words = text.match(/\S+\s*/g) || []
    // If chunk starts with whitespace before first word, capture it
    const leadingSpace = text.match(/^\s+/)
    if (leadingSpace) {
      chunkBuffer.value.push(leadingSpace[0])
    }
    chunkBuffer.value.push(...words)
  })

  eventSource.value.addEventListener('complete', (event) => {
    const data = JSON.parse(event.data)
    console.log('[MediaInputBox] Stream complete:', data.char_count, 'chars')
    isStreamComplete.value = true

    // Close EventSource but keep buffer processor running until empty
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }

    // Store final text for safety check, but let buffer display naturally
    const finalText = data.final_text

    // Check buffer completion periodically until empty
    const checkBufferComplete = setInterval(() => {
      if (chunkBuffer.value.length === 0) {
        // Buffer is empty - verify we have complete text
        if (streamedValue.value !== finalText) {
          console.log('[MediaInputBox] Buffer finished but text incomplete, using final_text')
          streamedValue.value = finalText
          emit('update:value', streamedValue.value)
        }
        emit('stream-complete', data)
        // System-generated text is safe by definition — no checkSafety() here.
        // Safety only runs on user actions (blur, paste).
        stopBufferProcessor()
        clearInterval(checkBufferComplete)
      }
    }, 50)  // Check every 50ms
  })

  eventSource.value.addEventListener('blocked', (event) => {
    const data = JSON.parse(event.data)
    console.log('[MediaInputBox] Stream BLOCKED by safety:', data)
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
    stopBufferProcessor()
    safetyStore.reportBlock(data.stage || 'safety', data.reason || t('mediaInput.contentBlocked'), data.found_terms || [])
    emit('stream-complete', { blocked: true, reason: data.reason })
  })

  eventSource.value.addEventListener('error', (event) => {
    // Ignore error if stream already completed successfully
    if (isStreamComplete.value) {
      console.log('[MediaInputBox] Ignoring error after completion')
      return
    }

    console.error('[MediaInputBox] Stream error:', event)
    emit('stream-error', 'Stream connection failed')
    closeStream()
  })
}

function startBufferProcessor() {
  // Process buffer every 50ms, one word at a time
  // Word-by-word is better for readability (especially kids) and drains
  // the buffer faster than char-by-char, reducing "trickle" lag at the end
  bufferInterval = window.setInterval(() => {
    if (chunkBuffer.value.length > 0) {
      const word = chunkBuffer.value.shift()!
      streamedValue.value += word
      emit('update:value', streamedValue.value)

      // Auto-scroll textarea to bottom during streaming
      if (textareaRef.value) {
        textareaRef.value.scrollTop = textareaRef.value.scrollHeight
      }
    }
  }, 50)
}

function stopBufferProcessor() {
  if (bufferInterval) {
    clearInterval(bufferInterval)
    bufferInterval = null
  }
}

function closeStream() {
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }
  stopBufferProcessor()

  // Clear any remaining buffer
  if (chunkBuffer.value.length > 0 && !isStreamComplete.value) {
    streamedValue.value += chunkBuffer.value.join('')
    emit('update:value', streamedValue.value)
    chunkBuffer.value = []
  }
}

// Watch for streaming activation (only when URL changes)
watch(() => props.streamUrl, (newUrl, oldUrl) => {
  console.log('[DEBUG MediaInputBox] Watch triggered - enableStreaming:', props.enableStreaming, 'newUrl:', newUrl, 'oldUrl:', oldUrl)

  if (props.enableStreaming && newUrl && newUrl !== oldUrl) {
    console.log('[MediaInputBox] Stream URL changed, starting new stream')
    startStreaming()
  } else {
    console.log('[DEBUG MediaInputBox] NOT starting stream - conditions not met')
  }
})

// Lifecycle
onMounted(() => {
  if (props.inputType === 'text' && props.resizeType === 'auto') {
    autoResizeTextarea()
  }
})

onUnmounted(() => {
  closeStream()
})
</script>

<style scoped>
.media-input-box {
  background: rgba(20, 20, 20, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: clamp(12px, 2vw, 20px);
  padding: clamp(1rem, 2.5vw, 1.5rem);
  transition: all 0.3s ease;
}

.media-input-box.filled {
  border-color: rgba(102, 126, 234, 0.6);
  background: rgba(102, 126, 234, 0.1);
}

.media-input-box.required {
  border-color: rgba(255, 193, 7, 0.6);
  background: rgba(255, 193, 7, 0.05);
  animation: pulse-required 2s ease-in-out infinite;
}

@keyframes pulse-required {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.media-input-box.empty {
  border: 2px dashed rgba(255, 255, 255, 0.3);
  background: rgba(20, 20, 20, 0.5);
}

.media-input-box.loading {
  background: rgba(20, 20, 20, 0.7);
  border: 2px solid rgba(79, 172, 254, 0.4);
}

/* Header */
.bubble-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.bubble-icon {
  font-size: clamp(1.25rem, 3vw, 1.5rem);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bubble-icon svg {
  width: clamp(20px, 3vw, 24px);
  height: clamp(20px, 3vw, 24px);
}

.bubble-label {
  font-size: clamp(0.9rem, 2vw, 1rem);
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.bubble-actions {
  display: flex;
  gap: 0.25rem;
  margin-inline-start: auto;
}

.action-btn {
  background: transparent;
  border: none;
  font-size: 0.9rem;
  opacity: 0.4;
  cursor: pointer;
  transition: opacity 0.2s;
  padding: 0.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.9);
}

.action-btn:hover {
  opacity: 0.8;
}

.action-btn.preset-btn {
  opacity: 1;
  color: #FFB300;
  filter: drop-shadow(0 0 4px rgba(255, 179, 0, 0.6));
  margin-inline-end: 30px;
}

.action-btn.preset-btn svg {
  width: 30px;
  height: 30px;
}

.action-btn.preset-btn:hover {
  opacity: 1;
  filter: drop-shadow(0 0 6px rgba(255, 179, 0, 0.9));
}

/* Pulse when WIE-Box is empty — opacity only, like pulse-translate */
.action-btn.preset-btn.preset-suggesting {
  animation: preset-pulse 1.5s ease-in-out infinite;
}

@keyframes preset-pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.action-btn svg {
  width: 20px;
  height: 20px;
}

/* Translate (Union Jack) Button */
.action-btn.translate-btn {
  opacity: 0.5;
  padding: 0.25rem 0.15rem;
}

.action-btn.translate-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.action-btn.translate-btn:disabled {
  opacity: 0.2;
  cursor: not-allowed;
}

.action-btn.translate-btn.translating {
  animation: pulse-translate 1s ease-in-out infinite;
}

@keyframes pulse-translate {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.union-jack {
  width: 20px;
  height: 10px;
}

/* Textarea */
.bubble-textarea {
  width: 100%;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: white;
  font-size: clamp(0.9rem, 2vw, 1rem);
  padding: clamp(0.5rem, 1.5vw, 0.75rem);
  font-family: inherit;
  line-height: 1.4;
}

.bubble-textarea:focus {
  outline: none;
  border-color: rgba(102, 126, 234, 0.8);
  background: rgba(0, 0, 0, 0.4);
}

.bubble-textarea::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.bubble-textarea.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: rgba(30, 30, 30, 0.6);
}

/* Resize Types */
.standard-resize-textarea {
  resize: vertical;
  min-height: clamp(44px, 6vh, 56px);
}

.auto-resize-textarea {
  resize: vertical;
  overflow-y: auto;
  min-height: clamp(44px, 6vh, 56px);
  max-height: clamp(150px, 20vh, 250px);
}

.no-resize-textarea {
  resize: none;
  min-height: clamp(44px, 6vh, 56px);
}

/* Upload / Sketch Toggle */
.input-mode-toggle {
  display: flex;
  gap: 0.25rem;
  padding: 0.2rem;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  align-self: flex-start;
  margin-bottom: 0.5rem;
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.75rem;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.mode-btn:hover {
  color: rgba(255, 255, 255, 0.8);
  background: rgba(255, 255, 255, 0.05);
}

.mode-btn.active {
  background: rgba(102, 126, 234, 0.2);
  border-color: rgba(102, 126, 234, 0.4);
  color: rgba(255, 255, 255, 0.9);
}

.mode-btn svg {
  width: 16px;
  height: 16px;
}

/* Triple-Prompt Display (SD3.5 per-encoder) */
.triple-prompt-display {
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  overflow: hidden;
}

.triple-section {
  padding: clamp(0.4rem, 1vw, 0.6rem) clamp(0.5rem, 1.5vw, 0.75rem);
  background: rgba(0, 0, 0, 0.3);
}

.triple-section + .triple-section {
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.triple-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.triple-tag {
  font-size: 0.6rem;
  font-weight: 400;
  color: rgba(102, 126, 234, 0.8);
  background: rgba(102, 126, 234, 0.1);
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  text-transform: none;
  letter-spacing: 0;
}

.triple-content {
  color: rgba(255, 255, 255, 0.85);
  font-size: clamp(0.8rem, 1.8vw, 0.9rem);
  line-height: 1.4;
  word-break: break-word;
}

.triple-t5-note {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem clamp(0.5rem, 1.5vw, 0.75rem);
  color: rgba(255, 255, 255, 0.35);
  font-size: 0.7rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.triple-t5-note svg {
  flex-shrink: 0;
  opacity: 0.5;
}

/* Loading Overlay */
.preview-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  min-height: 100px;
}

.spinner-large {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(255, 255, 255, 0.1);
  border-top-color: rgba(102, 126, 234, 0.8);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.9rem;
  text-align: center;
}

/* Queue Feedback Styling */
.spinner-large.queued {
  border-top-color: #ff4757;
  border-color: rgba(255, 71, 87, 0.2);
  animation: spin 1.5s linear infinite;
}

.loading-text.queued {
  color: #ff4757;
  font-weight: 500;
  animation: pulse-text 2s ease-in-out infinite;
}

@keyframes pulse-text {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

</style>
