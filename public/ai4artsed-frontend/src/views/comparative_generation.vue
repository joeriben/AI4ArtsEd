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
          @copy="copyPrompt"
          @paste="pastePrompt"
          @clear="clearPrompt"
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

        <button
          class="generate-btn"
          :disabled="!canGenerate || isGenerating"
          @click="startComparison"
        >
          {{ isGenerating ? t('compare.generatingAll') : t('compare.generateAll') }}
        </button>
      </div>

      <!-- Comparison Grid -->
      <div class="comparison-grid" :class="'grid-' + slots.length">
        <div v-for="slot in slots" :key="slot.langCode" class="comparison-slot">
          <div class="slot-header">
            <span class="slot-lang-name">{{ slot.langName }}</span>
            <span class="slot-lang-code">{{ slot.langCode }}</span>
            <span v-if="slot.queuePosition > 0 && !slot.isExecuting && !slot.outputUrl" class="slot-queue">{{ slot.queuePosition }}/{{ slots.length }}</span>
          </div>
          <!-- Translation box -->
          <div v-if="slot.translatedPrompt" class="slot-translation">
            <div class="slot-translated-text">{{ slot.translatedPrompt }}</div>
            <div v-if="slot.backTranslation" class="slot-back-translation">&#x2192; {{ slot.backTranslation }}</div>
          </div>
          <div class="slot-output" :class="{ generating: slot.isExecuting, complete: !!slot.outputUrl }">
            <template v-if="slot.isExecuting && !slot.outputUrl">
              <div class="slot-progress-track">
                <div class="slot-progress-fill" :class="{ indeterminate: slot.progress <= 0 }" :style="slot.progress > 0 ? { width: slot.progress + '%' } : {}"></div>
              </div>
            </template>
            <img v-if="slot.outputUrl" :src="slot.outputUrl" alt="" class="slot-image" />
            <div v-if="slot.blockedReason" class="slot-blocked">{{ slot.blockedReason }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Trashy Chat Panel -->
    <ComparisonChat
      ref="chatRef"
      class="compare-chat-panel"
      :comparison-context="comparisonContext"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MediaInputBox from '@/components/MediaInputBox.vue'
import LanguageChipSelector from '@/components/LanguageChipSelector.vue'
import ComparisonChat from '@/components/ComparisonChat.vue'
import { useGenerationStream } from '@/composables/useGenerationStream'
import { useUserPreferencesStore } from '@/stores/userPreferences'

const { t } = useI18n()
const userPreferences = useUserPreferencesStore()

// --- State ---
const userPrompt = ref('')
const selectedLanguages = ref<string[]>(['en', 'ar'])
const selectedModel = ref('sd35_large')
const isGenerating = ref(false)
const currentSeed = ref<number | null>(null)
const chatRef = ref<InstanceType<typeof ComparisonChat> | null>(null)
const comparisonContext = ref('')

const availableModels = [
  { id: 'sd35_large', label: 'SD 3.5 Large' },
  { id: 'sd35_large_turbo', label: 'SD 3.5 Large Turbo (fast)' },
  { id: 'flux2_diffusers', label: 'Flux 2' },
  { id: 'gpt_image_1', label: 'GPT-Image-1' },
]

interface ComparisonSlot {
  langCode: string
  langName: string
  translatedPrompt: string
  backTranslation: string
  outputUrl: string | null
  runId: string | null
  isExecuting: boolean
  progress: number
  queuePosition: number
  blockedReason: string | null
}

const slots = ref<ComparisonSlot[]>([])

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
  chatRef.value?.resetChat()

  const isDev = import.meta.env.DEV
  const baseUrl = isDev ? 'http://localhost:17802' : ''

  // Initialize slots
  slots.value = selectedLanguages.value.map((code, idx) => ({
    langCode: code,
    langName: LANGUAGE_NAMES[code] || code,
    translatedPrompt: '',
    backTranslation: '',
    outputUrl: null,
    runId: null,
    isExecuting: false,
    progress: 0,
    queuePosition: idx + 1,
    blockedReason: null,
  }))

  chatRef.value?.injectMessage(t('compare.trashyTranslating'))

  try {
    // Step 1: Translate — same endpoint as MediaInputBox translate button
    const sourceLang = /[äöüßÄÖÜ]/.test(userPrompt.value) ? 'de' : 'en'
    const translations: Record<string, string> = { [sourceLang]: userPrompt.value }

    for (const lang of selectedLanguages.value.filter(l => l !== sourceLang)) {
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

    // Back-translate to settings language (non-blocking, runs in parallel with generation)
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

    chatRef.value?.injectMessage(t('compare.trashyGenerating'))

    // Step 3: Sequential generation using useGenerationStream (same as all other pages)
    for (let i = 0; i < slots.value.length; i++) {
      const slot = slots.value[i]!
      slot.isExecuting = true

      for (let j = i + 1; j < slots.value.length; j++) {
        slots.value[j]!.queuePosition = j - i
      }

      const stream = useGenerationStream()

      // Reactively sync progress from composable to slot
      const stopWatch = setInterval(() => {
        slot.progress = stream.generationProgress.value
      }, 200)

      try {
        const result = await stream.executeWithStreaming({
          prompt: slot.translatedPrompt,
          output_config: selectedModel.value,
          seed,
          skip_stage3_translation: true,
          device_id: `compare_${Date.now()}_${i}`,
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
      } finally {
        clearInterval(stopWatch)
        slot.isExecuting = false
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
  } catch (e) {
    console.error('[COMPARE] Failed:', e)
    chatRef.value?.injectMessage(t('compare.trashyError'))
  } finally {
    isGenerating.value = false
  }
}
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

.generate-btn {
  display: block;
  width: 100%;
  padding: 0.75rem;
  margin-top: 0.75rem;
  background: rgba(76, 175, 80, 0.15);
  border: 1px solid rgba(76, 175, 80, 0.3);
  border-radius: 10px;
  color: rgba(76, 175, 80, 0.9);
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.generate-btn:hover:not(:disabled) {
  background: rgba(76, 175, 80, 0.25);
  border-color: rgba(76, 175, 80, 0.5);
}

.generate-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
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

.slot-output {
  border: 1px dashed rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  overflow: hidden;
  aspect-ratio: 1 / 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 15, 15, 0.5);
}

.slot-output.generating {
  border-color: rgba(76, 175, 80, 0.3);
  border-style: solid;
}

.slot-output.complete {
  border-color: rgba(255, 255, 255, 0.12);
  border-style: solid;
}

.slot-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.slot-progress-track {
  width: 60%;
  height: 3px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 2px;
  overflow: hidden;
}

.slot-progress-fill {
  height: 100%;
  background: rgba(76, 175, 80, 0.6);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.slot-progress-fill.indeterminate {
  width: 30%;
  animation: progress-slide 1.5s ease-in-out infinite;
}

@keyframes progress-slide {
  0% { transform: translateX(-100%); }
  50% { transform: translateX(250%); }
  100% { transform: translateX(-100%); }
}

.slot-blocked {
  font-size: 0.75rem;
  color: rgba(239, 83, 80, 0.7);
  text-align: center;
  padding: 0.5rem;
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
</style>
