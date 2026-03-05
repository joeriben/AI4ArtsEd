<template>
  <div class="music-generation-view">
    <div class="phase-2a" ref="mainContainerRef">

      <!-- ================================================================
           PROCESS A: LYRICS WORKSHOP
           ================================================================ -->
      <section class="workshop-section">
        <h2 class="section-title">{{ $t('musicGenV2.lyricsWorkshop') }}</h2>

        <!-- Lyrics Input -->
        <MediaInputBox
          ref="lyricsBoxRef"
          icon="💡"
          :label="$t('musicGenV2.lyricsInput')"
          :placeholder="$t('musicGenV2.lyricsPlaceholder')"
          v-model:value="lyricsInput"
          input-type="text"
          :rows="6"
          :is-filled="!!lyricsInput"
          @copy="copyToClipboard(lyricsInput)"
          @paste="async () => { const t = await pasteFromClipboard(); if (t) lyricsInput = t }"
          @clear="lyricsInput = ''"
        />

        <!-- Action Chips: Theme→Lyrics | Refine Lyrics -->
        <div class="action-chips">
          <button
            class="action-chip"
            :class="{
              active: activeLyricsAction === 'expand',
              disabled: !lyricsInput && !isAnySafetyChecking,
              'checking-safety': isAnySafetyChecking
            }"
            :disabled="!lyricsInput || isLyricsProcessing || isAnySafetyChecking"
            @click="runLyricsAction('expand')"
          >
            {{ isAnySafetyChecking ? $t('common.checkingSafety') : $t('musicGenV2.themeToLyrics') }}
          </button>
          <button
            class="action-chip"
            :class="{
              active: activeLyricsAction === 'refine',
              disabled: !lyricsInput && !isAnySafetyChecking,
              'checking-safety': isAnySafetyChecking
            }"
            :disabled="!lyricsInput || isLyricsProcessing || isAnySafetyChecking"
            @click="runLyricsAction('refine')"
          >
            {{ isAnySafetyChecking ? $t('common.checkingSafety') : $t('musicGenV2.refineLyrics') }}
          </button>
        </div>

        <!-- Lyrics Result (streaming) -->
        <MediaInputBox
          v-if="lyricsResult || isLyricsProcessing"
          icon="→"
          :label="$t('musicGenV2.resultLabel')"
          :placeholder="$t('musicGenV2.resultPlaceholder')"
          v-model:value="lyricsResult"
          input-type="text"
          :rows="8"
          resize-type="auto"
          :is-empty="!lyricsResult"
          :is-loading="isLyricsProcessing"
          :loading-message="lyricsLoadingMessage"
          :enable-streaming="true"
          :stream-url="lyricsStreamUrl"
          :stream-params="lyricsStreamParams"
          @stream-started="isLyricsProcessing = true"
          @stream-complete="handleLyricsComplete"
          @stream-error="handleLyricsError"
          @copy="copyToClipboard(lyricsResult)"
          @paste="async () => { const t = await pasteFromClipboard(); if (t) lyricsResult = t }"
          @clear="lyricsResult = ''"
        />
      </section>

      <!-- ================================================================
           PROCESS B: SOUND EXPLORER
           ================================================================ -->
      <section class="workshop-section">
        <h2 class="section-title">{{ $t('musicGenV2.soundExplorer') }}</h2>

        <!-- Auto-suggest button -->
        <div class="action-chips">
          <button
            class="action-chip suggest-chip"
            :class="{ disabled: !effectiveLyrics }"
            :disabled="!effectiveLyrics || isSuggesting"
            @click="suggestTagsFromLyrics"
          >
            <span v-if="isSuggesting" class="chip-spinner"></span>
            {{ $t('musicGenV2.suggestFromLyrics') }}
          </button>
        </div>

        <!-- 8-Dimension Tag Selector -->
        <MusicTagSelector
          :dimensions="tagDimensions"
          v-model:selected="selectedTags"
          v-model:customTags="customTags"
          :disabled="isSuggesting"
        />
      </section>

      <!-- ================================================================
           GENERATION CONTROLS
           ================================================================ -->

      <!-- Generation Parameters -->
      <section class="params-section">
        <!-- Audio Length -->
        <div class="param-row">
          <label class="slider-label">
            <span class="slider-label-text">{{ $t('musicGenV2.audioLength') }}</span>
            <span class="slider-value">{{ audioLengthDisplay }}</span>
          </label>
          <input type="range" class="audio-slider" v-model.number="audioLengthSeconds" :min="30" :max="240" :step="10" />
          <div class="slider-marks"><span>0:30</span><span>1:00</span><span>2:00</span><span>3:00</span><span>4:00</span></div>
        </div>

        <!-- Temperature -->
        <div class="param-row">
          <label class="slider-label">
            <span class="slider-label-text">Temperature</span>
            <span class="slider-value">{{ temperature.toFixed(1) }}</span>
          </label>
          <input type="range" class="audio-slider" v-model.number="temperature" :min="0.1" :max="2.0" :step="0.1" />
          <div class="slider-marks"><span>0.1</span><span>0.5</span><span>1.0</span><span>1.5</span><span>2.0</span></div>
        </div>

        <!-- Top-K -->
        <div class="param-row">
          <label class="slider-label">
            <span class="slider-label-text">Top-K</span>
            <span class="slider-value">{{ topk }}</span>
          </label>
          <input type="range" class="audio-slider" v-model.number="topk" :min="10" :max="100" :step="5" />
          <div class="slider-marks"><span>10</span><span>30</span><span>50</span><span>70</span><span>100</span></div>
        </div>

        <!-- CFG Scale -->
        <div class="param-row">
          <label class="slider-label">
            <span class="slider-label-text">CFG Scale</span>
            <span class="slider-value">{{ cfgScale.toFixed(1) }}</span>
          </label>
          <input type="range" class="audio-slider" v-model.number="cfgScale" :min="0.5" :max="4.0" :step="0.25" />
          <div class="slider-marks"><span>0.5</span><span>1.5</span><span>2.5</span><span>3.5</span><span>4.0</span></div>
        </div>
      </section>

      <!-- Generate Button + Batch -->
      <GenerationButton
        :disabled="!canGenerate"
        :executing="isGenerating"
        :checking-safety="isAnySafetyChecking"
        :label="generateButtonLabel"
        :checking-label="$t('common.checkingSafety')"
        :executing-label="$t('common.generating')"
        :error-message="generationErrorMessage"
        @click="startGeneration"
      >
        <template #before>
          <div class="batch-control">
            <button class="batch-btn" :disabled="batchCount <= 1" @click="batchCount--">-</button>
            <span class="batch-value">{{ batchCount }}x</span>
            <button class="batch-btn" @click="batchCount++">+</button>
          </div>
        </template>
      </GenerationButton>

      <!-- OUTPUT -->
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
import MusicTagSelector from '@/components/MusicTagSelector.vue'
import GenerationButton from '@/components/GenerationButton.vue'
import type { DimensionConfig } from '@/components/MusicTagSelector.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// ============================================================================
// Stores & Composables
// ============================================================================

const route = useRoute()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const pageContextStore = usePageContextStore()
const favoritesStore = useFavoritesStore()
const pipelineStore = usePipelineExecutionStore()

// ============================================================================
// Device ID (consistent with v1)
// ============================================================================

const deviceId = useDeviceId()

// ============================================================================
// Tag Dimensions Configuration
// ============================================================================

const tagDimensions: DimensionConfig[] = [
  {
    name: 'genre',
    label_de: 'Genre',
    label_en: 'Genre',
    color: '#e91e63',
    importance: 'high',
    chips: ['pop', 'rock', 'jazz', 'classical', 'electronic', 'hip-hop', 'r&b', 'country', 'folk', 'metal', 'indie', 'blues', 'latin', 'reggae', 'funk', 'soul', 'dance', 'punk', 'ambient', 'gospel', 'afrobeat', 'k-pop', 'bollywood', 'bossa_nova', 'salsa', 'flamenco', 'qawwali', 'highlife', 'cumbia', 'tango', 'fado', 'samba', 'house', 'techno', 'trance', 'dubstep', 'drum_and_bass', 'synthwave', 'lo-fi', 'trap']
  },
  {
    name: 'timbre',
    label_de: 'Klangfarbe',
    label_en: 'Timbre',
    color: '#9c27b0',
    chips: ['bright', 'dark', 'warm', 'crisp', 'smooth', 'mellow', 'harsh', 'soft', 'rich', 'thin']
  },
  {
    name: 'gender',
    label_de: 'Stimme',
    label_en: 'Voice',
    color: '#2196f3',
    chips: ['male', 'female', 'mixed', 'choir']
  },
  {
    name: 'mood',
    label_de: 'Stimmung',
    label_en: 'Mood',
    color: '#ff9800',
    chips: ['happy', 'sad', 'energetic', 'calm', 'romantic', 'melancholic', 'aggressive', 'dreamy', 'nostalgic', 'upbeat', 'dark', 'hopeful', 'playful', 'dramatic', 'festive']
  },
  {
    name: 'instrument',
    label_de: 'Instrumente',
    label_en: 'Instruments',
    color: '#4caf50',
    chips: ['piano', 'guitar', 'drums', 'bass', 'violin', 'saxophone', 'trumpet', 'synthesizer', 'flute', 'keyboard', 'cello', 'harmonica', 'organ', 'ukulele', 'sitar', 'tabla', 'koto', 'erhu', 'djembe', 'gamelan', 'oud', 'shamisen', 'didgeridoo', 'kalimba', 'guzheng', 'mbira', 'kora', 'steel_drum', 'saz', 'shakuhachi', 'darbuka', 'balafon', 'pipa']
  },
  {
    name: 'scene',
    label_de: 'Szene',
    label_en: 'Scene',
    color: '#00bcd4',
    chips: ['wedding', 'party', 'meditation', 'workout', 'study', 'road_trip', 'summer', 'nature', 'night', 'morning', 'rain']
  },
  {
    name: 'region',
    label_de: 'Region (UNESCO)',
    label_en: 'Region (UNESCO)',
    color: '#795548',
    chips: ['west_africa', 'east_africa', 'southern_africa', 'arab_world', 'south_asia', 'east_asia', 'southeast_asia', 'central_asia', 'northern_europe', 'southern_europe', 'eastern_europe', 'caribbean', 'south_america', 'north_america']
  },
  {
    name: 'topic',
    label_de: 'Thema',
    label_en: 'Topic',
    color: '#607d8b',
    chips: ['love', 'heartbreak', 'freedom', 'nature', 'city', 'friendship', 'loss', 'hope', 'rebellion', 'celebration', 'journey']
  }
]

// ============================================================================
// STATE: Lyrics Workshop (Process A)
// ============================================================================

const lyricsInput = ref('')
const lyricsResult = ref('')
const isLyricsProcessing = ref(false)
const activeLyricsAction = ref<'expand' | 'refine' | null>(null)
const lyricsStreamUrl = ref('')
const lyricsStreamParams = ref<Record<string, any>>({})

const lyricsLoadingMessage = computed(() => {
  return activeLyricsAction.value === 'expand'
    ? t('musicGenV2.expandingTheme')
    : t('musicGenV2.refiningLyrics')
})

// ============================================================================
// STATE: Sound Explorer (Process B)
// ============================================================================

const selectedTags = ref<Record<string, string[]>>({
  genre: [], timbre: [], gender: [], mood: [],
  instrument: [], scene: [], region: [], topic: []
})
const customTags = ref('')
const isSuggesting = ref(false)

// ============================================================================
// STATE: Generation
// ============================================================================

const isGenerating = ref(false)
const generationErrorMessage = ref('')
const generationProgress = ref(0)
const estimatedGenerationSeconds = ref(180)
const outputAudio = ref<string | null>(null)
const currentRunId = ref<string | null>(null)
const isFavorited = ref(false)
const audioLengthSeconds = ref(200)
const temperature = ref(1.0)
const topk = ref(65)
const cfgScale = ref(2.75)
const batchCount = ref(1)
const batchCurrent = ref(0)

const audioLengthDisplay = computed(() => {
  const mins = Math.floor(audioLengthSeconds.value / 60)
  const secs = audioLengthSeconds.value % 60
  return mins > 0 ? `${mins}:${secs.toString().padStart(2, '0')}` : `${secs}s`
})

// ============================================================================
// Refs
// ============================================================================

const mainContainerRef = ref<HTMLElement | null>(null)
const lyricsBoxRef = ref<InstanceType<typeof MediaInputBox> | null>(null)
const isAnySafetyChecking = computed(() => !!lyricsBoxRef.value?.isCheckingSafety)
const outputSectionRef = ref<InstanceType<typeof MediaOutputBox> | null>(null)

// ============================================================================
// Computed
// ============================================================================

const effectiveLyrics = computed(() => lyricsResult.value || lyricsInput.value)

const compiledTags = computed(() => {
  const chipTags = Object.values(selectedTags.value).flat()
  const custom = customTags.value
    ? customTags.value.split(',').map(t => t.trim()).filter(Boolean)
    : []
  return [...chipTags, ...custom].join(',')
})

const canGenerate = computed(() => {
  return !!effectiveLyrics.value && !isGenerating.value
})

const generateButtonLabel = computed(() => {
  const prefix = batchCount.value > 1 ? `${batchCurrent.value}/${batchCount.value} ` : ''
  return prefix + t('musicGenV2.generateButton')
})

// ============================================================================
// Page Context for Trashy
// ============================================================================

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
    contextPrompt: compiledTags.value,
    refinedText: lyricsResult.value
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
// PROCESS A: Lyrics Workshop
// ============================================================================

async function runLyricsAction(action: 'expand' | 'refine') {
  if (!lyricsInput.value || isLyricsProcessing.value) return

  activeLyricsAction.value = action
  isLyricsProcessing.value = true
  lyricsResult.value = ''

  // Reset URL so MediaInputBox watch fires when we set it again
  lyricsStreamUrl.value = ''

  const isDev = import.meta.env.DEV
  const url = isDev
    ? 'http://localhost:17802/api/schema/pipeline/interception'
    : '/api/schema/pipeline/interception'

  lyricsStreamParams.value = {
    schema: action === 'expand' ? 'lyrics_from_theme' : 'lyrics_refinement',
    input_text: lyricsInput.value,
    device_id: deviceId,
    enable_streaming: true
  }

  // Set URL in next tick — component is now mounted with empty URL,
  // this change triggers the MediaInputBox watch
  await nextTick()
  lyricsStreamUrl.value = url
}

function handleLyricsComplete() {
  isLyricsProcessing.value = false
}

function handleLyricsError(error: string) {
  console.error('[MusicGenV2] Lyrics stream error:', error)
  isLyricsProcessing.value = false
  if (!lyricsResult.value) {
    lyricsResult.value = lyricsInput.value
  }
}

// ============================================================================
// PROCESS B: Sound Explorer — Auto-suggest from Lyrics
// ============================================================================

async function suggestTagsFromLyrics() {
  if (!effectiveLyrics.value || isSuggesting.value) return

  isSuggesting.value = true

  try {
    // POST uses Vite proxy (relative URL), only EventSource/SSE needs full URL
    const response = await axios.post('/api/schema/pipeline/interception', {
      schema: 'tag_suggestion_from_lyrics',
      input_text: effectiveLyrics.value,
      device_id: deviceId
    })

    if (response.data.status === 'success') {
      const outputText = response.data.final_output || ''
      parseAndApplyTagSuggestions(outputText)
    }
  } catch (error) {
    console.error('[MusicGenV2] Tag suggestion error:', error)
  } finally {
    isSuggesting.value = false
  }
}

function parseAndApplyTagSuggestions(text: string) {
  try {
    // Extract JSON from LLM response (may have surrounding text)
    const jsonMatch = text.match(/\{[\s\S]*\}/)
    if (!jsonMatch) {
      console.warn('[MusicGenV2] No JSON found in tag suggestion response. Raw text:', text)
      return
    }

    const suggestions = JSON.parse(jsonMatch[0]) as Record<string, string[]>
    const newSelection: Record<string, string[]> = { ...selectedTags.value }

    // Get all known chips per dimension for validation
    const knownChips: Record<string, Set<string>> = {}
    for (const dim of tagDimensions) {
      knownChips[dim.name] = new Set(dim.chips)
    }

    let totalSuggested = 0
    let totalMatched = 0

    for (const [dimName, tags] of Object.entries(suggestions)) {
      if (!Array.isArray(tags) || !knownChips[dimName]) continue
      totalSuggested += tags.length
      const matched = tags.filter(tag => knownChips[dimName]!.has(tag))
      const dropped = tags.filter(tag => !knownChips[dimName]!.has(tag))
      totalMatched += matched.length
      if (dropped.length > 0) {
        console.warn(`[MusicGenV2] ${dimName}: dropped unknown tags:`, dropped, '| matched:', matched)
      }
      newSelection[dimName] = matched
    }

    console.log(`[MusicGenV2] Tag suggestion: ${totalMatched}/${totalSuggested} tags matched`)

    if (totalMatched === 0) {
      console.warn('[MusicGenV2] No suggested tags matched known chips. Suggestions were:', suggestions)
    }

    selectedTags.value = newSelection
  } catch (e) {
    console.error('[MusicGenV2] Failed to parse tag suggestions:', e)
  }
}

// ============================================================================
// GENERATION
// ============================================================================

async function startGeneration() {
  if (!canGenerate.value) return

  const total = batchCount.value
  for (let i = 1; i <= total; i++) {
    batchCurrent.value = i
    console.log(`[MusicGenV2] Batch ${i}/${total}`)
    await runSingleGeneration()
  }
  batchCurrent.value = 0
}

async function runSingleGeneration() {
  isGenerating.value = true
  generationErrorMessage.value = ''
  outputAudio.value = null
  generationProgress.value = 0
  const finalLyrics = effectiveLyrics.value
  const finalTags = compiledTags.value

  const progressInterval = setInterval(() => {
    if (generationProgress.value < 98) {
      generationProgress.value += 0.5
    }
  }, 1000)

  try {
    // POST uses Vite proxy (relative URL), only EventSource/SSE needs full URL
    const response = await axios.post('/api/schema/pipeline/interception', {
      schema: 'heartmula',
      input_text: finalLyrics,
      output_config: 'heartmula_standard',
      device_id: deviceId,
      custom_placeholders: {
        TEXT_1: finalLyrics,
        TEXT_2: finalTags,
        max_audio_length_ms: audioLengthSeconds.value * 1000,
        temperature: temperature.value,
        topk: topk.value,
        cfg_scale: cfgScale.value
      }
    }, { timeout: 360000 })

    if (response.data.status === 'success') {
      const runId = response.data.run_id
      currentRunId.value = runId
      const mediaOutput = response.data.media_output
      if (runId && mediaOutput?.status === 'success') {
        outputAudio.value = `/api/media/music/${runId}`
      } else {
        console.error('[MusicGenV2] Stage 4 failed:', mediaOutput?.error || 'unknown')
      }
    } else {
      console.error('[MusicGenV2] Generation failed:', response.data.error)
      const msg = response.data.error || ''
      if (/queue full/i.test(msg)) generationErrorMessage.value = t('generationError.busy')
      else if (/not available|not reachable/i.test(msg)) generationErrorMessage.value = t('generationError.offline')
      else generationErrorMessage.value = t('generationError.unknown')
    }
  } catch (error) {
    console.error('[MusicGenV2] Error:', error)
    generationErrorMessage.value = t('generationError.unknown')
  } finally {
    clearInterval(progressInterval)
    generationProgress.value = 100
    isGenerating.value = false

    nextTick(() => {
      if (outputSectionRef.value) {
        (outputSectionRef.value.$el as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })
  }
}

// ============================================================================
// Media Actions
// ============================================================================

async function saveMedia() {
  if (outputAudio.value && currentRunId.value) {
    const success = await favoritesStore.addFavorite(currentRunId.value, 'music', deviceId, 'anonymous', 'music-generation')
    if (success) isFavorited.value = true
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
  if (currentRunId.value) {
    isFavorited.value = favoritesStore.isFavorited(currentRunId.value)
  }
})
</script>

<style scoped>
.music-generation-view {
  min-height: 100vh;
  background: #0a0a0a;
  color: white;
  padding: 2rem 1rem;
}

.phase-2a {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

/* Section Titles */
.section-title {
  font-size: 0.9rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 0.5rem;
}

/* Workshop Section */
.workshop-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Action Chips */
.action-chips {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.action-chip {
  padding: 0.5rem 1.2rem;
  font-size: 0.85rem;
  font-weight: 600;
  border-radius: 20px;
  border: 2px solid rgba(156, 39, 176, 0.5);
  background: transparent;
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.action-chip:hover:not(.disabled) {
  background: rgba(156, 39, 176, 0.2);
  border-color: #9c27b0;
  color: white;
}

.action-chip.active {
  background: rgba(156, 39, 176, 0.3);
  border-color: #9c27b0;
  color: white;
}

.action-chip.disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.suggest-chip {
  border-color: rgba(33, 150, 243, 0.5);
}

.suggest-chip:hover:not(.disabled) {
  background: rgba(33, 150, 243, 0.2);
  border-color: #2196f3;
}

.chip-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Generation Parameters */
.params-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 0 0.5rem;
}

.param-row {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.slider-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.slider-label-text {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.slider-value {
  font-size: 1.1rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  font-variant-numeric: tabular-nums;
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
  background: #9c27b0;
  cursor: pointer;
  border: 2px solid rgba(255, 255, 255, 0.3);
  transition: transform 0.15s;
}

.audio-slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

.audio-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #9c27b0;
  cursor: pointer;
  border: 2px solid rgba(255, 255, 255, 0.3);
}

.slider-marks {
  display: flex;
  justify-content: space-between;
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.3);
}

/* Batch Control */
.batch-control {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.batch-btn {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
  font-size: 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  font-family: inherit;
}

.batch-btn:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.5);
  color: white;
}

.batch-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.batch-value {
  font-size: 0.85rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
  min-width: 2rem;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

/* Start button styles now in GenerationButton.vue + generation-button.css */

.action-chip.checking-safety {
  opacity: 0.6;
  cursor: not-allowed;
  animation: safety-check-pulse 1.2s ease-in-out infinite;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Responsive */
@media (max-width: 600px) {
  .music-generation-view {
    padding: 1rem 0.5rem;
  }

  .phase-2a {
    gap: 1.5rem;
  }

  .action-chip {
    padding: 0.4rem 0.8rem;
    font-size: 0.8rem;
  }
}
</style>
