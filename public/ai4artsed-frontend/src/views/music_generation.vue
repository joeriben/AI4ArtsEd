<template>
  <div class="music-generation-view">

    <!-- Single Continuous Flow (t2x pattern) -->
    <div class="phase-2a" ref="mainContainerRef">

      <!-- Section 1: Dual Input (Lyrics + Tags) -->
      <section class="input-section" ref="inputSectionRef">
        <!-- Lyrics Input (TEXT_1) -->
        <MediaInputBox
          ref="lyricsBoxRef"
          icon="lightbulb"
          :label="$t('musicGen.lyricsLabel')"
          :placeholder="$t('musicGen.lyricsPlaceholder')"
          v-model:value="lyricsInput"
          input-type="text"
          :rows="8"
          :is-filled="!!lyricsInput"
          @copy="copyLyrics"
          @paste="pasteLyrics"
          @clear="clearLyrics"
          @focus="focusedField = 'lyrics'"
          @blur="(val: string) => logPromptChange('lyrics', val)"
        />

        <!-- Tags Input (TEXT_2) -->
        <MediaInputBox
          ref="tagsBoxRef"
          icon="clipboard"
          :label="$t('musicGen.tagsLabel')"
          :placeholder="$t('musicGen.tagsPlaceholder')"
          v-model:value="tagsInput"
          input-type="text"
          :rows="3"
          :is-filled="!!tagsInput"
          @copy="copyTags"
          @paste="pasteTags"
          @clear="clearTags"
          @focus="focusedField = 'tags'"
          @blur="(val: string) => logPromptChange('tags', val)"
        />
      </section>

      <!-- START BUTTON #1: Dual Interception (Lyrics + Tags) -->
      <GenerationButton
        :disabled="!lyricsInput"
        :executing="isLyricsInterceptionLoading || isTagsInterceptionLoading"
        :checking-safety="isAnySafetyChecking"
        :label="$t('musicGen.refineButton')"
        :checking-label="$t('common.checkingSafety')"
        :executing-label="$t('common.generating')"
        @click="runDualInterception()"
      />

      <!-- Section 2: Dual Interception Results (Side by Side) -->
      <section class="interception-section dual-outputs" ref="interceptionSectionRef">
        <!-- Refined Lyrics (TEXT_1) -->
        <MediaInputBox
          icon="→"
          :label="$t('musicGen.refinedLyricsLabel')"
          :placeholder="$t('musicGen.refinedLyricsPlaceholder')"
          v-model:value="refinedLyrics"
          input-type="text"
          :rows="8"
          resize-type="auto"
          :is-empty="!refinedLyrics"
          :is-loading="isLyricsInterceptionLoading"
          :loading-message="$t('musicGen.refiningLyricsMessage')"
          :enable-streaming="true"
          :stream-url="lyricsStreamingUrl"
          :stream-params="lyricsStreamingParams"
          @stream-started="handleLyricsStreamStarted"
          @stream-complete="handleLyricsStreamComplete"
          @stream-error="handleLyricsStreamError"
          @copy="copyRefinedLyrics"
          @paste="pasteRefinedLyrics"
          @clear="clearRefinedLyrics"
          @focus="focusedField = 'refinedLyrics'"
          @blur="(val: string) => logPromptChange('refined_lyrics', val)"
        />

        <!-- Refined Tags (TEXT_2) -->
        <MediaInputBox
          icon="stars"
          :label="$t('musicGen.refinedTagsLabel')"
          :placeholder="$t('musicGen.refinedTagsPlaceholder')"
          v-model:value="refinedTags"
          input-type="text"
          :rows="8"
          resize-type="auto"
          :is-empty="!refinedTags"
          :is-loading="isTagsInterceptionLoading"
          :loading-message="$t('musicGen.refiningTagsMessage')"
          :enable-streaming="true"
          :stream-url="tagsStreamingUrl"
          :stream-params="tagsStreamingParams"
          @stream-started="handleTagsStreamStarted"
          @stream-complete="handleTagsStreamComplete"
          @stream-error="handleTagsStreamError"
          @copy="copyRefinedTags"
          @paste="pasteRefinedTags"
          @clear="clearRefinedTags"
          @focus="focusedField = 'refinedTags'"
          @blur="(val: string) => logPromptChange('refined_tags', val)"
        />
      </section>

      <!-- Section 3: Model Selection -->
      <section class="config-section">
        <h2 v-if="executionPhase !== 'initial'" class="section-title">{{ $t('musicGen.selectModel') }}</h2>
        <div class="config-bubbles-container">
          <div class="config-bubbles-row">
            <div
              v-for="config in availableConfigs"
              :key="config.id"
              class="config-bubble"
              :class="{
                selected: selectedConfig === config.id,
                hovered: hoveredConfigId === config.id
              }"
              :style="{ '--bubble-color': config.color }"
              @click="selectConfig(config.id)"
              @mouseenter="hoveredConfigId = config.id"
              @mouseleave="hoveredConfigId = null"
              role="button"
              :aria-pressed="selectedConfig === config.id"
              tabindex="0"
              @keydown.enter="selectConfig(config.id)"
              @keydown.space.prevent="selectConfig(config.id)"
            >
              <div class="bubble-emoji-medium">{{ config.emoji }}</div>

              <!-- Hover info -->
              <div v-if="hoveredConfigId === config.id" class="bubble-hover-info">
                <div class="hover-info-name">{{ config.name }}</div>
                <div class="hover-info-meta">
                  <div class="meta-row">
                    <span class="meta-label">{{ $t('musicGen.quality') }}</span>
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
                    <span class="meta-value duration-only">⏱ {{ config.duration }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Audio Length Slider -->
      <section class="slider-section">
        <label class="slider-label">
          <span class="slider-label-text">Audio Length</span>
          <span class="slider-value">{{ audioLengthDisplay }}</span>
        </label>
        <input
          type="range"
          class="audio-slider"
          v-model.number="audioLengthSeconds"
          :min="30"
          :max="240"
          :step="10"
        />
        <div class="slider-marks">
          <span>0:30</span>
          <span>1:00</span>
          <span>2:00</span>
          <span>3:00</span>
          <span>4:00</span>
        </div>
      </section>

      <!-- START BUTTON #2: Generate Music -->
      <GenerationButton
        :disabled="!canGenerate"
        :executing="isGenerating"
        :checking-safety="isAnySafetyChecking"
        :label="$t('musicGen.generateButton')"
        :checking-label="$t('common.checkingSafety')"
        :executing-label="$t('common.generating')"
        :error-message="generationErrorMessage"
        @click="startGeneration()"
      />

      <!-- OUTPUT BOX -->
      <MediaOutputBox
        ref="outputSectionRef"
        :output-image="outputAudio"
        media-type="music"
        :is-executing="isGenerating"
        :progress="generationProgress"
        :estimated-seconds="estimatedGenerationSeconds"
        :run-id="currentRunId"
        :is-favorited="isFavorited"
        @save="saveMedia"
        @download="downloadMedia"
        @toggle-favorite="toggleFavorite"
      />

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useDeviceId } from '@/composables/useDeviceId'
import { usePageContextStore } from '@/stores/pageContext'
import { useFavoritesStore } from '@/stores/favorites'
import { usePipelineExecutionStore } from '@/stores/pipelineExecution'
import type { PageContext, FocusHint } from '@/composables/usePageContext'
import axios from 'axios'
import MediaOutputBox from '@/components/MediaOutputBox.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import GenerationButton from '@/components/GenerationButton.vue'
import '@/assets/animations.css'

// ============================================================================
// i18n (temporary inline, move to i18n.ts later)
// ============================================================================

import { useI18n } from 'vue-i18n'
const { t } = useI18n()

// ============================================================================
// Types
// ============================================================================

interface MusicConfig {
  id: string
  name: string
  emoji: string
  color: string
  quality: number
  speed: number
  duration: string
}

type ExecutionPhase = 'initial' | 'interception_loading' | 'interception_done' | 'generating' | 'generation_done'

// ============================================================================
// STATE
// ============================================================================

const route = useRoute()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const pageContextStore = usePageContextStore()
const favoritesStore = useFavoritesStore()
const pipelineStore = usePipelineExecutionStore()

// Refs
const mainContainerRef = ref<HTMLElement | null>(null)
const inputSectionRef = ref<HTMLElement | null>(null)
const lyricsBoxRef = ref<InstanceType<typeof MediaInputBox> | null>(null)
const tagsBoxRef = ref<InstanceType<typeof MediaInputBox> | null>(null)
const isAnySafetyChecking = computed(() => !!(lyricsBoxRef.value?.isCheckingSafety || tagsBoxRef.value?.isCheckingSafety))
const interceptionSectionRef = ref<HTMLElement | null>(null)
const startButtonRef = ref<HTMLButtonElement | null>(null)
const outputSectionRef = ref<InstanceType<typeof MediaOutputBox> | null>(null)

// Input state
const lyricsInput = ref('')
const tagsInput = ref('')
const focusedField = ref<'lyrics' | 'tags' | 'refinedLyrics' | 'refinedTags' | null>(null)

// Interception state - Dual (Lyrics + Tags)
const refinedLyrics = ref('')
const refinedTags = ref('')
const isLyricsInterceptionLoading = ref(false)
const isTagsInterceptionLoading = ref(false)
const lyricsStreamingUrl = ref('')
const lyricsStreamingParams = ref<Record<string, any>>({})
const tagsStreamingUrl = ref('')
const tagsStreamingParams = ref<Record<string, any>>({})

const deviceId = useDeviceId()

// Config selection
const selectedConfig = ref<string>('heartmula_standard')
const hoveredConfigId = ref<string | null>(null)

// Available music generation configs
const availableConfigs = ref<MusicConfig[]>([
  {
    id: 'heartmula_standard',
    name: 'HeartMuLa',
    emoji: '🎵',
    color: '#9C27B0',
    quality: 4,
    speed: 2,
    duration: '30-240s'
  }
])

// Audio length slider (30s - 240s, step 10s)
const audioLengthSeconds = ref(120)
const audioLengthDisplay = computed(() => {
  const mins = Math.floor(audioLengthSeconds.value / 60)
  const secs = audioLengthSeconds.value % 60
  return mins > 0 ? `${mins}:${secs.toString().padStart(2, '0')}` : `${secs}s`
})

// Generation state
const isGenerating = ref(false)
const generationErrorMessage = ref('')
const generationProgress = ref(0)
const estimatedGenerationSeconds = ref(180)
const outputAudio = ref<string | null>(null)
const currentRunId = ref<string | null>(null)
const executionPhase = ref<ExecutionPhase>('initial')
// Favorites
const isFavorited = ref(false)

// Page Context for Trashy
const trashyFocusHint = computed<FocusHint>(() => {
  if (isGenerating.value || outputAudio.value) {
    return { x: 95, y: 85, anchor: 'bottom-right' }
  }
  return { x: 2, y: 95, anchor: 'bottom-left' }
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'music_generation',
  pageContent: {
    inputText: lyricsInput.value,
    contextPrompt: tagsInput.value,
    refinedText: refinedLyrics.value
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
// Computed
// ============================================================================

const canGenerate = computed(() => {
  // Can generate if we have lyrics (either original or refined) and a selected config
  const hasLyrics = refinedLyrics.value || lyricsInput.value
  return hasLyrics && selectedConfig.value && executionPhase.value !== 'generating'
})

// ============================================================================
// Methods - Clipboard
// ============================================================================

function copyLyrics() {
  copyToClipboard(lyricsInput.value)
}

async function pasteLyrics() {
  const text = await pasteFromClipboard()
  if (text) lyricsInput.value = text
}

function clearLyrics() {
  lyricsInput.value = ''
}

function copyTags() {
  copyToClipboard(tagsInput.value)
}

async function pasteTags() {
  const text = await pasteFromClipboard()
  if (text) tagsInput.value = text
}

function clearTags() {
  tagsInput.value = ''
}

function copyRefinedLyrics() {
  copyToClipboard(refinedLyrics.value)
}

async function pasteRefinedLyrics() {
  const text = await pasteFromClipboard()
  if (text) refinedLyrics.value = text
}

function clearRefinedLyrics() {
  refinedLyrics.value = ''
}

function copyRefinedTags() {
  copyToClipboard(refinedTags.value)
}

async function pasteRefinedTags() {
  const text = await pasteFromClipboard()
  if (text) refinedTags.value = text
}

function clearRefinedTags() {
  refinedTags.value = ''
}

// ============================================================================
// Methods - Logging
// ============================================================================

function logPromptChange(field: string, value: string) {
  console.log(`[MusicGen] ${field} changed:`, value.substring(0, 50))
}

// ============================================================================
// Methods - Config Selection
// ============================================================================

function selectConfig(configId: string) {
  selectedConfig.value = configId
  console.log('[MusicGen] Selected config:', configId)
}

// ============================================================================
// Methods - Dual Interception (Lyrics + Tags separately)
// ============================================================================

async function runDualInterception() {
  if (!lyricsInput.value) return

  executionPhase.value = 'interception_loading'

  // Start Lyrics Interception
  isLyricsInterceptionLoading.value = true
  refinedLyrics.value = ''

  // Use correct endpoint (same as text_transformation.vue)
  const isDev = import.meta.env.DEV
  lyricsStreamingUrl.value = isDev
    ? 'http://localhost:17802/api/schema/pipeline/interception'
    : '/api/schema/pipeline/interception'

  lyricsStreamingParams.value = {
    schema: 'lyrics_refinement',
    input_text: lyricsInput.value,
    device_id: deviceId,  // FIX: Persistent device_id for consistent folders
    enable_streaming: true  // KEY: Request SSE streaming
  }

  // Start Tags Interception (if tags exist)
  if (tagsInput.value) {
    isTagsInterceptionLoading.value = true
    refinedTags.value = ''

    tagsStreamingUrl.value = isDev
      ? 'http://localhost:17802/api/schema/pipeline/interception'
      : '/api/schema/pipeline/interception'

    tagsStreamingParams.value = {
      schema: 'tags_generation',
      input_text: tagsInput.value,
      device_id: deviceId,  // FIX: Persistent device_id for consistent folders
      enable_streaming: true
    }
  } else {
    // No tags input, just use empty
    refinedTags.value = ''
  }

  console.log('[MusicGen] Starting dual interception (lyrics + tags)')
}

// Lyrics Stream Handlers
function handleLyricsStreamStarted() {
  console.log('[MusicGen] Lyrics stream started')
}

function handleLyricsStreamComplete(data: any) {
  console.log('[MusicGen] Lyrics stream complete:', data)
  // v-model already updated by MediaInputBox, no need to set refinedLyrics
  isLyricsInterceptionLoading.value = false
  checkInterceptionComplete()
}

function handleLyricsStreamError(error: string) {
  console.error('[MusicGen] Lyrics stream error:', error)
  isLyricsInterceptionLoading.value = false
  refinedLyrics.value = lyricsInput.value // Fallback
  checkInterceptionComplete()
}

// Tags Stream Handlers
function handleTagsStreamStarted() {
  console.log('[MusicGen] Tags stream started')
}

function handleTagsStreamComplete(data: any) {
  console.log('[MusicGen] Tags stream complete:', data)
  // v-model already updated by MediaInputBox, no need to set refinedTags
  isTagsInterceptionLoading.value = false
  checkInterceptionComplete()
}

function handleTagsStreamError(error: string) {
  console.error('[MusicGen] Tags stream error:', error)
  isTagsInterceptionLoading.value = false
  refinedTags.value = tagsInput.value || '' // Fallback
  checkInterceptionComplete()
}

// Check if both interceptions are done
function checkInterceptionComplete() {
  if (!isLyricsInterceptionLoading.value && !isTagsInterceptionLoading.value) {
    executionPhase.value = 'interception_done'
    // Scroll to next section
    nextTick(() => {
      if (interceptionSectionRef.value) {
        interceptionSectionRef.value.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })
  }
}

// ============================================================================
// Methods - Generation
// ============================================================================

async function startGeneration() {
  if (!canGenerate.value) return

  isGenerating.value = true
  executionPhase.value = 'generating'
  generationErrorMessage.value = ''
  outputAudio.value = null
  generationProgress.value = 0
  // Use refined lyrics if available, otherwise original
  const finalLyrics = refinedLyrics.value || lyricsInput.value

  // Progress simulation
  const progressInterval = setInterval(() => {
    if (generationProgress.value < 98) {
      generationProgress.value += 0.5
    }
  }, 1000)

  try {
    // Use refined lyrics + tags if available, otherwise original
    const finalTags = refinedTags.value || tagsInput.value || ''

    // Call pipeline execution endpoint with dual text inputs (TEXT_1 + TEXT_2 separately)
    const response = await axios.post('/api/schema/pipeline/interception', {
      schema: 'heartmula', // Use heartmula interception config
      input_text: finalLyrics,
      output_config: selectedConfig.value,
      device_id: deviceId, // FIX: Persistent device_id for consistent export folders
      custom_placeholders: {
        TEXT_1: finalLyrics,
        TEXT_2: finalTags,
        max_audio_length_ms: audioLengthSeconds.value * 1000
      }
    })

    if (response.data.status === 'success') {
      const runId = response.data.run_id
      currentRunId.value = runId

      if (runId) {
        // Fetch music output
        await fetchMusicOutput(runId)
      }

      executionPhase.value = 'generation_done'
    } else {
      console.error('[MusicGen] Generation failed:', response.data.error)
      const msg = response.data.error || ''
      if (/queue full/i.test(msg)) generationErrorMessage.value = t('generationError.busy')
      else if (/not available|not reachable/i.test(msg)) generationErrorMessage.value = t('generationError.offline')
      else generationErrorMessage.value = t('generationError.unknown')
    }
  } catch (error) {
    console.error('[MusicGen] Error:', error)
    generationErrorMessage.value = t('generationError.unknown')
  } finally {
    clearInterval(progressInterval)
    generationProgress.value = 100
    isGenerating.value = false

    // Scroll to output
    nextTick(() => {
      if (outputSectionRef.value) {
        (outputSectionRef.value.$el as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })
  }
}

async function fetchMusicOutput(runId: string) {
  // The /api/media/music/ endpoint serves the file directly - use as audio src URL
  outputAudio.value = `/api/media/music/${runId}`
  console.log('[MusicGen] Music output URL:', outputAudio.value)
}

// ============================================================================
// Methods - Media Actions
// ============================================================================

async function saveMedia() {
  if (outputAudio.value && currentRunId.value) {
    console.log('[MusicGen] Save media:', currentRunId.value)
    const success = await favoritesStore.addFavorite(
      currentRunId.value,
      'music',
      deviceId,
      'anonymous',
      'music-generation'
    )
    if (success) {
      isFavorited.value = true
    }
  }
}

function downloadMedia() {
  if (outputAudio.value) {
    const a = document.createElement('a')
    a.href = outputAudio.value
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:]/g, '-')
    a.download = `ai4artsed_music_${timestamp}.mp3`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }
}

function toggleFavorite() {
  if (currentRunId.value) {
    if (isFavorited.value) {
      favoritesStore.removeFavorite(currentRunId.value)
      isFavorited.value = false
    } else {
      saveMedia()
    }
  }
}

// ============================================================================
// Lifecycle
// ============================================================================

onMounted(() => {
  // Check if config was passed via route
  const configId = route.params.configId as string
  if (configId) {
    selectedConfig.value = configId
    console.log('[MusicGen] Config from route:', configId)
  }

  // Check if run is favorited
  if (currentRunId.value) {
    isFavorited.value = favoritesStore.isFavorited(currentRunId.value)
  }
})
</script>

<style scoped>
/* ============================================================================
   music_generation.vue Styles
   Design system aligned with text_transformation.css
   ============================================================================ */

/* ============================================================================
   Root Container
   ============================================================================ */

.music-generation-view {
  min-height: 100%;
  background: #0a0a0a;
  color: #ffffff;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  overflow-y: auto;
  overflow-x: hidden;
  padding-bottom: 120px;
}

/* ============================================================================
   Phase 2a: Vertical Flow
   ============================================================================ */

.phase-2a {
  max-width: clamp(320px, 90vw, 1100px);
  width: 100%;
  padding: clamp(1rem, 3vw, 2rem);
  padding-top: clamp(1rem, 3vw, 2rem);

  display: flex;
  flex-direction: column;
  align-items: center;
  gap: clamp(1rem, 3vh, 2rem);
}

/* Section Titles */
.section-title {
  font-size: clamp(1rem, 2.5vw, 1.2rem);
  font-weight: 700;
  text-align: center;
  margin: 0 0 1rem 0;
  color: transparent;
  -webkit-text-stroke: 2px #FFB300;
  text-stroke: 2px #FFB300;
  text-shadow: 0 0 10px rgba(255, 179, 0, 0.6),
               0 0 20px rgba(255, 179, 0, 0.4),
               0 0 30px rgba(255, 179, 0, 0.2);
  animation: neon-pulse 2s ease-in-out infinite;
}

/* ============================================================================
   Section 1: Dual Input (Lyrics + Tags, Side by Side)
   ============================================================================ */

.input-section {
  display: flex;
  gap: clamp(1rem, 3vw, 2rem);
  width: 100%;
  justify-content: center;
  flex-wrap: wrap;
}

/* ============================================================================
   Section 2: Interception Results (Dual Outputs, Side by Side)
   ============================================================================ */

.interception-section,
.config-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.interception-section.dual-outputs {
  display: flex;
  flex-direction: row;
  gap: clamp(1rem, 3vw, 2rem);
  width: 100%;
  justify-content: center;
  flex-wrap: wrap;
}

/* ============================================================================
   Section 3: Config Bubbles (Model Selection)
   ============================================================================ */

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

.config-bubble:hover:not(.disabled):not(.loading),
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

/* Hide emoji when hovered (to show hover info) */
.config-bubble.hovered .bubble-emoji-medium {
  opacity: 0;
  display: none;
}

/* ============================================================================
   Hover Info Overlay - Mathematical precision for circular constraint
   ============================================================================ */

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
  hyphens: manual;
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

/* ============================================================================
   Audio Length Slider (Music-specific, adapted to design language)
   ============================================================================ */

.slider-section {
  width: 100%;
  max-width: 480px;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0 0.5rem;
}

.slider-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.slider-label-text {
  font-size: clamp(0.75rem, 2vw, 0.85rem);
  color: transparent;
  -webkit-text-stroke: 1px #FFB300;
  text-stroke: 1px #FFB300;
  text-shadow: 0 0 8px rgba(255, 179, 0, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 700;
}

.slider-value {
  font-size: clamp(1rem, 2.5vw, 1.1rem);
  font-weight: 600;
  color: #FFB300;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 10px rgba(255, 179, 0, 0.6);
}

.audio-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.15);
  outline: none;
}

.audio-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #FFB300;
  cursor: pointer;
  border: 2px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 0 10px rgba(255, 179, 0, 0.4);
  transition: transform 0.15s;
}

.audio-slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
  box-shadow: 0 0 15px rgba(255, 179, 0, 0.6);
}

.audio-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #FFB300;
  cursor: pointer;
  border: 2px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 0 10px rgba(255, 179, 0, 0.4);
}

.slider-marks {
  display: flex;
  justify-content: space-between;
  font-size: clamp(0.6rem, 1.5vw, 0.7rem);
  color: rgba(255, 255, 255, 0.3);
}

/* Start button styles now in GenerationButton.vue + generation-button.css */

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

/* ============================================================================
   Responsive: Mobile Adjustments
   ============================================================================ */

@media (max-width: 768px) {
  .input-section {
    flex-direction: column;
  }

  .interception-section.dual-outputs {
    flex-direction: column;
  }
}

/* iPad 1024x768 Optimization */
@media (min-width: 1024px) and (max-height: 768px) {
  .phase-2a {
    padding: 1.5rem;
    gap: 1.25rem;
  }
}
</style>

<style>
/* GLOBAL unscoped - force MediaInputBox width in music sections */
.music-generation-view .input-section .media-input-box,
.music-generation-view .interception-section.dual-outputs .media-input-box {
  flex: 0 1 480px !important;
  width: 100% !important;
  max-width: 480px !important;
}
</style>
