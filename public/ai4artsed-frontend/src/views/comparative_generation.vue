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
        <ComparisonCard
          v-for="(slot, idx) in slots"
          :key="slot.langCode"
          :language-code="slot.langCode"
          :language-name="slot.langName"
          :prompt="slot.translatedPrompt"
          :output-image="slot.outputImage"
          :is-executing="slot.isExecuting"
          :progress="slot.progress"
          :queue-position="slot.queuePosition"
          :queue-total="slots.length"
          :blocked-reason="slot.blockedReason"
        />
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
import ComparisonCard from '@/components/ComparisonCard.vue'
import ComparisonChat from '@/components/ComparisonChat.vue'

const { t } = useI18n()

// State
const userPrompt = ref('')
const selectedLanguages = ref<string[]>(['en', 'ar'])
const isGenerating = ref(false)
const currentSeed = ref<number | null>(null)
const chatRef = ref<InstanceType<typeof ComparisonChat> | null>(null)

interface ComparisonSlot {
  langCode: string
  langName: string
  translatedPrompt: string
  outputImage: string | null
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
  fry: 'Frysk', yo: 'Yorùbá', sw: 'Kiswahili', cy: 'Cymraeg', qu: 'Runasimi',
}

const canGenerate = computed(() => {
  return userPrompt.value.trim().length > 0 && selectedLanguages.value.length >= 2
})

function copyPrompt() {
  window.navigator.clipboard.writeText(userPrompt.value)
}

async function pastePrompt() {
  userPrompt.value = await window.navigator.clipboard.readText()
}

function clearPrompt() {
  userPrompt.value = ''
}

// Build context string for Trashy
const comparisonContext = ref('')

function buildContext(phase: string): string {
  const langList = slots.value.map(s => `${s.langName} (${s.langCode}): "${s.translatedPrompt}"`).join('\n')
  const results = slots.value.filter(s => s.outputImage).map(s => `${s.langName}: image generated`).join(', ')
  const blocked = slots.value.filter(s => s.blockedReason).map(s => `${s.langName}: blocked (${s.blockedReason})`).join(', ')

  return `[Language Comparison — ${phase}]
User prompt: "${userPrompt.value}"
Languages: ${selectedLanguages.value.join(', ')}
Translations:
${langList}
${results ? `Results: ${results}` : ''}
${blocked ? `Blocked: ${blocked}` : ''}
Model: SD3.5 Large (CLIP-L + CLIP-G + T5-XXL)
Same seed for all languages.`
}

async function startComparison() {
  if (!canGenerate.value || isGenerating.value) return

  isGenerating.value = true

  // Initialize slots
  slots.value = selectedLanguages.value.map((code, idx) => ({
    langCode: code,
    langName: LANGUAGE_NAMES[code] || code,
    translatedPrompt: '',
    outputImage: null,
    isExecuting: false,
    progress: 0,
    queuePosition: idx + 1,
    blockedReason: null,
  }))

  chatRef.value?.injectMessage(t('compare.trashyTranslating'))

  try {
    // Step 1: Translate prompt to all selected languages
    const isDev = import.meta.env.DEV
    const baseUrl = isDev ? 'http://localhost:17802' : ''

    // Determine source language (assume the user writes in EN or DE)
    const sourceLang = /[äöüßÄÖÜ]/.test(userPrompt.value) ? 'de' : 'en'
    const targetLanguages = selectedLanguages.value.filter(l => l !== sourceLang)

    let translations: Record<string, string> = { [sourceLang]: userPrompt.value }

    if (targetLanguages.length > 0) {
      const translateRes = await fetch(`${baseUrl}/api/schema/compare/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: userPrompt.value,
          languages: targetLanguages,
          source_language: sourceLang,
        })
      })
      if (!translateRes.ok) {
        chatRef.value?.injectMessage(t('compare.trashyTranslateError'))
        isGenerating.value = false
        return
      }
      const translateData = await translateRes.json()
      if (translateData.status !== 'success') {
        chatRef.value?.injectMessage(t('compare.trashyTranslateError'))
        isGenerating.value = false
        return
      }
      translations = { ...translations, ...translateData.translations }
    }

    // Update slots with translations
    for (const slot of slots.value) {
      slot.translatedPrompt = translations[slot.langCode] || userPrompt.value
      slot.queuePosition = 0 // Reset — will be set during generation
    }

    comparisonContext.value = buildContext('translations_ready')

    // Step 2: Generate seed (same for all) — displayed in UI for verification
    const seed = Math.floor(Math.random() * 4294967296)
    currentSeed.value = seed

    chatRef.value?.injectMessage(t('compare.trashyGenerating'))

    // Step 3: Sequential generation for each language
    for (let i = 0; i < slots.value.length; i++) {
      const slot = slots.value[i]!
      slot.isExecuting = true
      slot.queuePosition = 0

      // Update queue positions for remaining slots
      for (let j = i + 1; j < slots.value.length; j++) {
        slots.value[j]!.queuePosition = j - i
      }

      try {
        // Use SSE streaming for generation
        const params = new URLSearchParams({
          prompt: slot.translatedPrompt,
          output_config: 'sd35_large',
          seed: seed.toString(),
          enable_streaming: 'true',
          skip_stage3_translation: 'true',
          device_id: `compare_${Date.now()}`,
        })

        const eventSource = new EventSource(`${baseUrl}/api/schema/pipeline/generation?${params}`)

        await new Promise<void>((resolve, reject) => {
          eventSource.addEventListener('complete', (event) => {
            const data = JSON.parse(event.data)
            if (data.media_output) {
              slot.outputImage = `${baseUrl}${data.media_output}`
            }
            slot.isExecuting = false
            eventSource.close()
            resolve()
          })

          eventSource.addEventListener('generation_progress', (event) => {
            const data = JSON.parse(event.data)
            slot.progress = data.percent || 0
          })

          eventSource.addEventListener('blocked', (event) => {
            const data = JSON.parse(event.data)
            slot.blockedReason = data.reason || 'Blocked'
            slot.isExecuting = false
            eventSource.close()
            resolve()
          })

          eventSource.addEventListener('error', () => {
            slot.blockedReason = 'Connection error'
            slot.isExecuting = false
            eventSource.close()
            resolve()
          })

          // Timeout after 5 minutes
          setTimeout(() => {
            slot.blockedReason = 'Timeout'
            slot.isExecuting = false
            eventSource.close()
            resolve()
          }, 300000)
        })
      } catch (e) {
        slot.blockedReason = 'Error'
        slot.isExecuting = false
      }
    }

    // All done
    comparisonContext.value = buildContext('generation_complete')
  } catch (e) {
    console.error('[COMPARE] Generation failed:', e)
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
