<template>
  <div class="compare-page">
    <div class="compare-main">
      <!-- Input Section -->
      <div class="input-section">
        <MediaInputBox
          icon="💡"
          :label="t('compare.promptLabel')"
          :placeholder="t('compare.promptPlaceholder')"
          v-model:value="userPrompt"
          input-type="text"
          :rows="4"
          :is-filled="!!userPrompt"
          :show-preset-button="true"
          @copy="copyPrompt"
          @paste="pastePrompt"
          @clear="clearPrompt"
          @open-preset-selector="showPresetOverlay = true"
        />

        <LanguageChipSelector v-model="selectedLanguages" :max="4" />

        <!-- Model selection -->
        <div class="model-select-row">
          <label class="model-label">{{ t('compare.modelLabel') }}</label>
          <select v-model="selectedModel" class="model-select">
            <option v-for="m in availableModels" :key="m.id" :value="m.id">{{ m.label }}</option>
          </select>
        </div>

        <!-- Seed display -->
        <div v-if="currentSeed !== null" class="seed-display">
          <span class="seed-label">Seed:</span>
          <span class="seed-value">{{ currentSeed }}</span>
        </div>

        <GenerationButton
          :disabled="!canGenerate"
          :executing="isGenerating"
          :label="t('compare.generateAll')"
          :executing-label="t('compare.generatingAll')"
          @click="startComparison"
        />
        <div v-if="safetyError" class="safety-error">{{ safetyError }}</div>
      </div>

      <!-- Comparison Grid -->
      <div class="comparison-grid" :class="'grid-' + slots.length">
        <div v-for="(slot, idx) in slots" :key="slot.langCode" class="comparison-slot">
          <div class="slot-header">
            <span class="slot-lang-name">{{ slot.langName }}</span>
            <span class="slot-lang-code">{{ slot.langCode }}</span>
            <span v-if="slot.queuePosition > 0 && !slotStreams[idx]?.isExecuting && !slot.outputUrl" class="slot-queue">{{ slot.queuePosition }}/{{ slots.length }}</span>
          </div>
          <!-- Translation box -->
          <div v-if="slot.translatedPrompt" class="slot-translation">
            <div class="slot-translated-text">{{ slot.translatedPrompt }}</div>
            <div v-if="slot.backTranslation" class="slot-back-translation">&#x2192; {{ slot.backTranslation }}</div>
          </div>
          <!-- MediaOutputBox — same component as t2x -->
          <div class="slot-output-wrapper">
            <MediaOutputBox
              :output-image="slot.outputUrl"
              media-type="image"
              :is-executing="slotStreams[idx]?.isExecuting ?? false"
              :progress="slotStreams[idx]?.generationProgress ?? 0"
              :preview-image="slotStreams[idx]?.previewImage ?? null"
              :model-meta="slotStreams[idx]?.modelMeta ?? null"
              :stage4-duration-ms="slotStreams[idx]?.stage4DurationMs ?? 0"
              :ui-mode="uiModeStore.mode"
              :run-id="slot.runId"
              :is-favorited="slot.isFavorited"
              :is-analyzing="true"
              forward-button-title="Weiterreichen zu Bild-Transformation"
              @toggle-favorite="toggleSlotFavorite(slot)"
              @forward="forwardToPage(slot)"
              @download="downloadSlotImage(slot)"
              @image-click="fullscreenImage = $event"
            />
          </div>
          <div v-if="slot.blockedReason" class="slot-blocked">{{ slot.blockedReason }}</div>
        </div>
      </div>
    </div>

    <!-- Trashy Chat Panel -->
    <ComparisonChat
      ref="chatRef"
      class="compare-chat-panel"
      :comparison-context="comparisonContext"
      @use-prompt="useTrashyPrompt"
    />

    <!-- Interception Preset Overlay -->
    <InterceptionPresetOverlay
      :visible="showPresetOverlay"
      @close="showPresetOverlay = false"
      @preset-selected="handlePresetSelected"
    />

    <!-- Fullscreen image modal (same pattern as t2x) -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div v-if="fullscreenImage" class="fullscreen-modal" @click="fullscreenImage = null">
          <img :src="fullscreenImage" alt="" class="fullscreen-image" />
          <button class="close-fullscreen" @click="fullscreenImage = null">&times;</button>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import MediaInputBox from '@/components/MediaInputBox.vue'
import MediaOutputBox from '@/components/MediaOutputBox.vue'
import LanguageChipSelector from '@/components/LanguageChipSelector.vue'
import ComparisonChat from '@/components/ComparisonChat.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import GenerationButton from '@/components/GenerationButton.vue'
import { useGenerationStream, type GenerationResult } from '@/composables/useGenerationStream'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useFavoritesStore } from '@/stores/favorites'
import { useUiModeStore } from '@/stores/uiMode'
import { useDeviceId } from '@/composables/useDeviceId'

const { t } = useI18n()
const router = useRouter()
const userPreferences = useUserPreferencesStore()
const favoritesStore = useFavoritesStore()
const uiModeStore = useUiModeStore()
const deviceId = useDeviceId()

// --- State ---
const userPrompt = ref('')
const selectedLanguages = ref<string[]>(['en', 'ar'])
const selectedModel = ref('sd35_large')
const isGenerating = ref(false)
const currentSeed = ref<number | null>(null)
const chatRef = ref<InstanceType<typeof ComparisonChat> | null>(null)
const comparisonContext = ref('')
const showPresetOverlay = ref(false)
const isEnriching = ref(false)
const safetyError = ref('')
const fullscreenImage = ref<string | null>(null)

const availableModels = [
  { id: 'sd35_large', label: 'SD 3.5 Large' },
  { id: 'sd35_large_turbo', label: 'SD 3.5 Large Turbo (fast)' },
  { id: 'flux2', label: 'Flux 2' },
  { id: 'gemini_3_pro_image', label: 'Gemini 3 Pro (EU)' },
]

interface ComparisonSlot {
  langCode: string
  langName: string
  translatedPrompt: string
  backTranslation: string
  outputUrl: string | null
  runId: string | null
  queuePosition: number
  blockedReason: string | null
  isFavorited: boolean
}

// Slots hold language/translation/output data
const slots = ref<ComparisonSlot[]>([])

// Per-slot generation stream instances — direct reactive binding, no polling
const slotStreams = ref<ReturnType<typeof useGenerationStream>[]>([])

const LANGUAGE_NAMES: Record<string, string> = {
  en: 'English', de: 'Deutsch', ar: 'العربية', he: 'עברית',
  tr: 'Türkçe', ko: '한국어', uk: 'Українська', fr: 'Français',
  es: 'Español', bg: 'Български', hsb: 'Hornjoserbšćina',
  dsb: 'Dolnoserbšćina', fry: 'Frysk', yo: 'Yorùbá', sw: 'Kiswahili',
  cy: 'Cymraeg', qu: 'Runasimi', hi: 'हिन्दी', ja: '日本語', zh: '中文',
}

const canGenerate = computed(() => {
  return userPrompt.value.trim().length > 0 && selectedLanguages.value.length >= 2
})

// --- Clipboard ---
function copyPrompt() { window.navigator.clipboard.writeText(userPrompt.value) }
async function pastePrompt() { userPrompt.value = await window.navigator.clipboard.readText() }
function clearPrompt() { userPrompt.value = '' }

// --- Trashy prompt injection ---
function useTrashyPrompt(prompt: string) {
  userPrompt.value = prompt
}

// --- Slot actions (events from MediaOutputBox) ---
async function toggleSlotFavorite(slot: ComparisonSlot) {
  if (!slot.runId) return
  const success = await favoritesStore.toggleFavorite(slot.runId, 'image', deviceId, 'anonymous', 'compare')
  if (success) {
    slot.isFavorited = !slot.isFavorited
  }
}

function forwardToPage(slot: ComparisonSlot) {
  if (!slot.outputUrl) return
  const runIdMatch = slot.outputUrl.match(/\/api\/.*\/(.+)$/)
  const runId = runIdMatch ? runIdMatch[1] : null
  const transferData = {
    imageUrl: slot.outputUrl,
    runId: runId,
    timestamp: Date.now()
  }
  localStorage.setItem('i2i_transfer_data', JSON.stringify(transferData))
  router.push('/image-transformation')
}

async function downloadSlotImage(slot: ComparisonSlot) {
  if (!slot.outputUrl) return
  try {
    const runIdMatch = slot.outputUrl.match(/\/api\/.*\/(.+)$/)
    const runId = runIdMatch ? runIdMatch[1] : 'media'
    const filename = `ai4artsed_compare_${slot.langCode}_${runId}.png`
    const response = await fetch(slot.outputUrl)
    if (!response.ok) throw new Error(`Download failed: ${response.status}`)
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    console.error('[COMPARE] Download error:', error)
  }
}

async function analyzeSlotImage(slot: ComparisonSlot) {
  if (!slot.runId) return
  const isDev = import.meta.env.DEV
  const baseUrl = isDev ? 'http://localhost:17802' : ''
  try {
    const res = await fetch(`${baseUrl}/api/schema/compare/describe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_id: slot.runId })
    })
    if (res.ok) {
      const data = await res.json()
      if (data.status === 'success' && data.description) {
        chatRef.value?.injectMessage(`[${slot.langName}] ${data.description}`)
      }
    }
  } catch {
    // Non-critical
  }
}

// --- Context Enrichment: Interception Preset ---
async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  if (!userPrompt.value.trim()) return

  isEnriching.value = true
  const isDev = import.meta.env.DEV
  const baseUrl = isDev ? 'http://localhost:17802' : ''

  try {
    const res = await fetch(`${baseUrl}/api/schema/pipeline/stage2`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        schema: payload.configId,
        input_text: userPrompt.value,
        device_id: deviceId,
      })
    })
    if (res.ok) {
      const data = await res.json()
      // Prefer pure interception_result (no optimization) over stage2_result
      const result = data.interception_result || data.stage2_result
      if (data.success && result) {
        userPrompt.value = typeof result === 'string'
          ? result
          : JSON.stringify(result)
        console.log(`[COMPARE] Prompt enriched via ${payload.configName} (${payload.configId})`)
      }
    }
  } catch (error) {
    console.error('[COMPARE] Interception failed:', error)
  } finally {
    isEnriching.value = false
  }
}

// --- Trashy context ---
function buildContext(phase: string): string {
  const langList = slots.value.map(s => `${s.langName} (${s.langCode})`).join(', ')
  const results = slots.value.filter(s => s.outputUrl).length
  const blocked = slots.value.filter(s => s.blockedReason).map(s => s.langName).join(', ')
  return `[Language Comparison — ${phase}]\nPrompt: "${userPrompt.value}"\nLanguages: ${langList}\nModel: ${selectedModel.value}\nSeed: ${currentSeed.value}\nImages generated: ${results}/${slots.value.length}${blocked ? `\nBlocked: ${blocked}` : ''}`
}

// --- Main generation flow ---
async function startComparison() {
  if (!canGenerate.value || isGenerating.value) return
  isGenerating.value = true
  safetyError.value = ''
  chatRef.value?.onNewRun()

  const isDev = import.meta.env.DEV
  const baseUrl = isDev ? 'http://localhost:17802' : ''

  // Stage 2 Jugendschutz gate — check original prompt before translation/generation
  try {
    const safetyRes = await fetch(`${baseUrl}/api/schema/pipeline/stage2`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ schema: 'user_defined', input_text: userPrompt.value, skip_optimization: true })
    })
    const safetyData = await safetyRes.json()
    if (!safetyData.success) {
      safetyError.value = safetyData.error || 'Blocked by safety check'
      isGenerating.value = false
      return
    }
    // Stage 2 refusal check — LLM handles safety via SAFETY_PREFIX
    const result = (safetyData.interception_result || safetyData.stage2_result || '').trim()
    const isRefusal = result.includes('Hierbei kann ich Dich nicht unterstützen') ||
        result.includes('kann ich dich nicht unterstützen') ||
        result.toLowerCase().includes('cannot support you') ||
        result.toLowerCase().includes('i can\'t help') ||
        result.toLowerCase().includes('i cannot') ||
        result === ''
    if (isRefusal) {
      safetyError.value = result || 'Content blocked by safety check'
      isGenerating.value = false
      console.log(`[LANG-COMPARE] Blocked by LLM refusal`)
      return
    }
    console.log(`[LANG-COMPARE] Safety passed`)
  } catch (e) {
    console.error('[LANG-COMPARE] Safety check error:', e)
    safetyError.value = 'Safety check unavailable'
    isGenerating.value = false
    return
  }

  // Initialize slots + one useGenerationStream per slot
  const langCodes = selectedLanguages.value
  slots.value = langCodes.map((code, idx) => ({
    langCode: code,
    langName: LANGUAGE_NAMES[code] || code,
    translatedPrompt: '',
    backTranslation: '',
    outputUrl: null,
    runId: null,
    queuePosition: idx + 1,
    blockedReason: null,
    isFavorited: false,
  }))
  slotStreams.value = langCodes.map(() => useGenerationStream())

  chatRef.value?.injectMessage(t('compare.trashyTranslating'))

  try {
    // Step 1: Translate to ALL selected languages (no source detection —
    // user may type in any language; LLM auto-detects source)
    const translations: Record<string, string> = {}

    for (const lang of langCodes) {
      const res = await fetch(`${baseUrl}/api/schema/pipeline/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: userPrompt.value, target_language: lang })
      })
      if (!res.ok) {
        console.error(`[COMPARE] Translation to ${lang} failed: HTTP ${res.status}`)
        chatRef.value?.injectMessage(t('compare.trashyTranslateError'))
        isGenerating.value = false
        return
      }
      const data = await res.json()
      if (data.status === 'success' && data.translated_text) {
        translations[lang] = data.translated_text
      } else {
        console.error(`[COMPARE] Translation to ${lang} failed:`, data.error)
        chatRef.value?.injectMessage(t('compare.trashyTranslateError'))
        isGenerating.value = false
        return
      }
    }

    for (const slot of slots.value) {
      slot.translatedPrompt = translations[slot.langCode] || userPrompt.value
      slot.queuePosition = 0
    }

    // Back-translate to settings language (non-blocking)
    const uiLang = userPreferences.language
    for (const slot of slots.value) {
      if (slot.langCode === uiLang) {
        slot.backTranslation = slot.translatedPrompt
        continue
      }
      fetch(`${baseUrl}/api/schema/pipeline/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: slot.translatedPrompt, target_language: uiLang })
      }).then(r => r.json()).then(data => {
        if (data.status === 'success' && data.translated_text) {
          slot.backTranslation = data.translated_text
        }
      }).catch(() => { /* non-critical */ })
    }

    // Step 2: Fixed seed for all
    const seed = Math.floor(Math.random() * 4294967296)
    currentSeed.value = seed

    // Session 273: Comparison group ID for linking runs
    const groupId = `cmp_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`

    chatRef.value?.injectMessage(t('compare.trashyGenerating'))

    // Step 3: Sequential generation — same executeWithStreaming as t2x
    for (let i = 0; i < slots.value.length; i++) {
      const slot = slots.value[i]!
      const stream = slotStreams.value[i]!

      for (let j = i + 1; j < slots.value.length; j++) {
        slots.value[j]!.queuePosition = j - i
      }

      try {
        const result: GenerationResult = await stream.executeWithStreaming({
          prompt: slot.translatedPrompt,
          output_config: selectedModel.value,
          seed,
          skip_stage3_translation: true,
          device_id: `${deviceId}_cmp${i}`,
          source_view: 'compare',
          comparison_group_id: groupId,
          comparison_language: slot.langCode,
          comparison_original_prompt: userPrompt.value,
        })

        if (result.status === 'success' && result.media_output?.url) {
          slot.outputUrl = `${baseUrl}${result.media_output.url}`
          slot.runId = result.run_id || null
        } else if (result.status === 'blocked') {
          slot.blockedReason = result.blocked_reason || 'Blocked'
        } else if (result.status === 'error') {
          slot.blockedReason = result.error || 'Error'
        }
      } catch (e) {
        console.error(`[COMPARE] Generation for ${slot.langCode} failed:`, e)
        slot.blockedReason = 'Error'
      }
    }

    // Step 4: Describe generated images via VLM and feed to Trashy
    const successfulSlots = slots.value.filter(s => s.runId && s.outputUrl)
    if (successfulSlots.length >= 2) {
      const descriptions: string[] = []
      for (const slot of successfulSlots) {
        try {
          const res = await fetch(`${baseUrl}/api/schema/compare/describe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ run_id: slot.runId })
          })
          if (res.ok) {
            const data = await res.json()
            if (data.status === 'success' && data.description) {
              descriptions.push(`[${slot.langName} (${slot.langCode})]:\n${data.description}`)
            }
          }
        } catch {
          // Non-critical
        }
      }

      if (descriptions.length > 0) {
        comparisonContext.value = buildContext('generation_complete') + '\n\n--- VLM Image Descriptions ---\n' + descriptions.join('\n\n')
      } else {
        comparisonContext.value = buildContext('generation_complete')
      }
    } else {
      comparisonContext.value = buildContext('generation_complete')
    }

    // Session 273: POST comparison context + trashy chat to each successful run
    const allTranslations = slots.value.map(s => ({
      language: s.langCode,
      translated: s.translatedPrompt,
      back_translation: s.backTranslation,
    }))
    for (const slot of successfulSlots) {
      if (!slot.runId) continue
      fetch(`${baseUrl}/api/schema/pipeline/run/${slot.runId}/context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          comparison_context: {
            original_prompt: userPrompt.value,
            languages: selectedLanguages.value,
            seed,
            model: selectedModel.value,
            this_language: slot.langCode,
            translated_prompt: slot.translatedPrompt,
            back_translation: slot.backTranslation,
            all_translations: allTranslations,
          }
        })
      }).catch(() => { /* fire-and-forget */ })
    }
    // POST trashy analysis to first successful run
    if (successfulSlots.length > 0 && successfulSlots[0]!.runId && chatRef.value) {
      const trashyMessages = chatRef.value.getMessages()
      if (trashyMessages.length > 0) {
        fetch(`${baseUrl}/api/schema/pipeline/run/${successfulSlots[0]!.runId}/context`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            trashy_analysis: { messages: trashyMessages }
          })
        }).catch(() => { /* fire-and-forget */ })
      }
    }
  } catch (e) {
    console.error('[COMPARE] Failed:', e)
    chatRef.value?.injectMessage(t('compare.trashyError'))
  } finally {
    isGenerating.value = false
  }
}

// Session 273: Save trashy chat on page leave (captures post-generation analysis)
function getFirstSuccessfulRunId(): string | null {
  return slots.value.find(s => s.runId)?.runId || null
}

onBeforeUnmount(() => {
  const runId = getFirstSuccessfulRunId()
  if (runId && chatRef.value) {
    const trashyMessages = chatRef.value.getMessages()
    if (trashyMessages.length > 0) {
      const baseUrl = import.meta.env.DEV ? 'http://localhost:17802' : ''
      fetch(`${baseUrl}/api/schema/pipeline/run/${runId}/context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          trashy_analysis: { messages: trashyMessages }
        })
      }).catch(() => { /* fire-and-forget */ })
    }
  }
})
</script>

<style scoped>
.compare-page {
  display: flex;
  gap: 1rem;
  max-width: 1400px;
  margin: 0 auto;
  padding: 1rem;
  min-height: calc(100vh - 120px);
}

.compare-main {
  flex: 1;
  min-width: 0;
  padding-bottom: 200px; /* Space for expanded FooterGallery (36px toggle + 140px content) */
}

.compare-chat-panel {
  width: 300px;
  flex-shrink: 0;
  position: sticky;
  top: 80px;
  max-height: calc(100vh - 120px);
}

/* Input Section */
.input-section {
  margin-bottom: 1.5rem;
}

.input-section :deep(.generation-button-container) {
  margin-top: 1.5rem;
}

.model-select-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.model-label {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.model-select {
  flex: 1;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 0.4rem 0.6rem;
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.8rem;
  outline: none;
}

.model-select:focus {
  border-color: rgba(76, 175, 80, 0.4);
}

.model-select option {
  background: #1a1a1a;
  color: rgba(255, 255, 255, 0.85);
}

.seed-display {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.5rem;
  padding: 0.3rem 0;
}

.seed-label {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.seed-value {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.6);
  font-family: 'SF Mono', 'Fira Code', monospace;
}


/* Comparison Grid */
.comparison-grid {
  display: grid;
  gap: 1rem;
}

.grid-2 { grid-template-columns: 1fr 1fr; }
.grid-3 { grid-template-columns: 1fr 1fr 1fr; }
.grid-4 { grid-template-columns: 1fr 1fr; }

.comparison-slot {
  min-width: 0;
}

.slot-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0;
}

.slot-lang-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  flex: 1;
}

.slot-lang-code {
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.35);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.slot-queue {
  font-size: 0.65rem;
  color: rgba(255, 183, 77, 0.7);
  background: rgba(255, 183, 77, 0.1);
  padding: 0.1rem 0.4rem;
  border-radius: 8px;
}

.slot-translation {
  padding: 0.3rem 0.5rem;
  margin-bottom: 0.3rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.slot-translated-text {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.3;
  word-break: break-word;
}

.slot-back-translation {
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.3);
  line-height: 1.3;
  margin-top: 0.15rem;
  word-break: break-word;
}

.slot-output-wrapper {
  border-radius: 10px;
  overflow: hidden;
}

/* Override MediaOutputBox sizing for compact grid layout */
.slot-output-wrapper :deep(.pipeline-section) {
  margin: 0;
  padding: 0;
}

.slot-output-wrapper :deep(.output-frame) {
  height: auto;
  aspect-ratio: 1 / 1;
  max-width: 100%;
  margin: 0;
  padding: 0.5rem;
}

.slot-output-wrapper :deep(.output-frame.empty) {
  padding: 1rem;
}

.slot-output-wrapper :deep(.output-image) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.slot-output-wrapper :deep(.action-toolbar) {
  gap: 0.15rem;
}

.slot-output-wrapper :deep(.action-btn) {
  width: 28px;
  height: 28px;
  padding: 4px;
}

.slot-blocked {
  font-size: 0.75rem;
  color: rgba(239, 83, 80, 0.7);
  text-align: center;
  padding: 0.5rem;
}

.safety-error {
  font-size: 0.85rem;
  color: rgba(239, 83, 80, 0.9);
  text-align: center;
  padding: 0.75rem;
  margin-top: 0.5rem;
  border: 1px solid rgba(239, 83, 80, 0.3);
  border-radius: 8px;
}

/* Mobile */
@media (max-width: 900px) {
  .compare-page {
    flex-direction: column;
  }

  .compare-chat-panel {
    width: 100%;
    position: static;
    max-height: 300px;
    order: -1;
  }

  .comparison-grid {
    grid-template-columns: 1fr !important;
  }
}

@media (max-width: 600px) {
  .compare-page {
    padding: 0.5rem;
  }
}

/* Fullscreen image modal (same as t2x) */
.fullscreen-modal {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: zoom-out;
}

.fullscreen-image {
  max-width: 95vw;
  max-height: 95vh;
  object-fit: contain;
  border-radius: 4px;
}

.close-fullscreen {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 2rem;
  cursor: pointer;
  line-height: 1;
}

.close-fullscreen:hover {
  color: rgba(255, 255, 255, 0.9);
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
