<template>
  <div class="compare-page">
    <div class="compare-main">
      <!-- Input Section -->
      <div class="input-section">
        <!-- Preset selector -->
        <div class="preset-selector">
          <button
            v-for="(preset, key) in PRESETS"
            :key="key"
            class="preset-card"
            :class="{ active: activePreset === key }"
            :disabled="isGenerating"
            @click="activePreset = key as PresetKey"
          >
            <span class="preset-models">{{ preset.models.map(m => m.label).join(' · ') }}</span>
          </button>
        </div>

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

        <!-- Seed display -->
        <div v-if="currentSeed !== null" class="seed-display">
          <span class="seed-label">Seed:</span>
          <span class="seed-value">{{ currentSeed }}</span>
        </div>

        <GenerationButton
          :disabled="!userPrompt.trim()"
          :executing="isGenerating"
          :label="t('compare.generateAll')"
          :executing-label="t('compare.generatingAll')"
          @click="startComparison"
        />
      </div>

      <!-- 3-Column Grid — always visible for flow transparency -->
      <div class="comparison-grid">
        <div v-for="(model, idx) in MODELS.value" :key="model.id" class="comparison-slot">
          <div class="slot-header">
            <span class="slot-model-name">{{ model.label }}</span>
            <span v-if="slots[idx]?.queuePosition > 0 && !slotStreams[idx]?.isExecuting && !slots[idx]?.outputUrl" class="slot-queue">{{ slots[idx]?.queuePosition }}/{{ MODELS.value.length }}</span>
          </div>
          <div class="slot-output-wrapper">
            <MediaOutputBox
              :output-image="slots[idx]?.outputUrl ?? null"
              media-type="image"
              :is-executing="slotStreams[idx]?.isExecuting ?? false"
              :progress="slotStreams[idx]?.generationProgress ?? 0"
              :preview-image="slotStreams[idx]?.previewImage ?? null"
              :model-meta="slotStreams[idx]?.modelMeta ?? null"
              :stage4-duration-ms="slotStreams[idx]?.stage4DurationMs ?? 0"
              :ui-mode="uiModeStore.mode"
              :run-id="slots[idx]?.runId ?? null"
              :is-favorited="slots[idx]?.isFavorited ?? false"
              :is-analyzing="true"
              @toggle-favorite="slots[idx] && toggleSlotFavorite(slots[idx]!)"
              @forward="slots[idx] && forwardToPage(slots[idx]!)"
              @download="slots[idx] && downloadSlotImage(slots[idx]!)"
              @image-click="fullscreenImage = $event"
            />
          </div>
          <div v-if="slots[idx]?.blockedReason" class="slot-blocked">{{ slots[idx]!.blockedReason }}</div>
        </div>
      </div>
    </div>

    <!-- Trashy Chat Panel -->
    <ComparisonChat
      ref="chatRef"
      class="compare-chat-panel"
      :comparison-context="comparisonContext"
      compare-type="model"
      @use-prompt="useTrashyPrompt"
    />

    <!-- Interception Preset Overlay -->
    <InterceptionPresetOverlay
      :visible="showPresetOverlay"
      @close="showPresetOverlay = false"
      @preset-selected="handlePresetSelected"
    />

    <!-- Fullscreen image modal -->
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
import { ref, computed, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import MediaInputBox from '@/components/MediaInputBox.vue'
import MediaOutputBox from '@/components/MediaOutputBox.vue'
import GenerationButton from '@/components/GenerationButton.vue'
import ComparisonChat from '@/components/ComparisonChat.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import { useGenerationStream, type GenerationResult } from '@/composables/useGenerationStream'
import { useFavoritesStore } from '@/stores/favorites'
import { useUiModeStore } from '@/stores/uiMode'
import { useDeviceId } from '@/composables/useDeviceId'

const { t } = useI18n()
const router = useRouter()
const favoritesStore = useFavoritesStore()
const uiModeStore = useUiModeStore()
const deviceId = useDeviceId()

// --- Model presets ---
const PRESETS = {
  current: {
    label: 'Current Top Models',
    models: [
      { id: 'sd35_large', label: 'SD 3.5 Large' },
      { id: 'flux2', label: 'Flux 2' },
      { id: 'gemini_3_pro_image', label: 'Gemini 3 Pro' },
    ],
  },
  history: {
    label: 'SD History',
    models: [
      { id: 'sd15', label: 'SD 1.5 (2022)' },
      { id: 'sdxl', label: 'SDXL (2023)' },
      { id: 'sd35_large', label: 'SD 3.5 Large (2024)' },
    ],
  },
} as const

type PresetKey = keyof typeof PRESETS

// --- State ---
const activePreset = ref<PresetKey>('current')
const MODELS = computed(() => PRESETS[activePreset.value].models)
const userPrompt = ref('')
const isGenerating = ref(false)
const currentSeed = ref<number | null>(null)
const chatRef = ref<InstanceType<typeof ComparisonChat> | null>(null)
const comparisonContext = ref('')
const showPresetOverlay = ref(false)
const isEnriching = ref(false)
const fullscreenImage = ref<string | null>(null)

interface ModelSlot {
  configId: string
  label: string
  outputUrl: string | null
  runId: string | null
  queuePosition: number
  blockedReason: string | null
  isFavorited: boolean
}

const slots = ref<ModelSlot[]>([])
const slotStreams = ref<ReturnType<typeof useGenerationStream>[]>([])

// --- Clipboard ---
function copyPrompt() { window.navigator.clipboard.writeText(userPrompt.value) }
async function pastePrompt() { userPrompt.value = await window.navigator.clipboard.readText() }
function clearPrompt() { userPrompt.value = '' }

// --- Trashy prompt injection ---
function useTrashyPrompt(prompt: string) {
  userPrompt.value = prompt
}

// --- Slot actions ---
async function toggleSlotFavorite(slot: ModelSlot) {
  if (!slot.runId) return
  const success = await favoritesStore.toggleFavorite(slot.runId, 'image', deviceId, 'anonymous', 'compare')
  if (success) {
    slot.isFavorited = !slot.isFavorited
  }
}

function forwardToPage(slot: ModelSlot) {
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

async function downloadSlotImage(slot: ModelSlot) {
  if (!slot.outputUrl) return
  try {
    const runIdMatch = slot.outputUrl.match(/\/api\/.*\/(.+)$/)
    const runId = runIdMatch ? runIdMatch[1] : 'media'
    const filename = `ai4artsed_model_${slot.configId}_${runId}.png`
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
    console.error('[MODEL-COMPARE] Download error:', error)
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
      const result = data.interception_result || data.stage2_result
      if (data.success && result) {
        userPrompt.value = typeof result === 'string'
          ? result
          : JSON.stringify(result)
        console.log(`[MODEL-COMPARE] Prompt enriched via ${payload.configName} (${payload.configId})`)
      }
    }
  } catch (error) {
    console.error('[MODEL-COMPARE] Interception failed:', error)
  } finally {
    isEnriching.value = false
  }
}

// --- Trashy context ---
function buildContext(): string {
  const modelList = slots.value.map(s => s.label).join(', ')
  const results = slots.value.filter(s => s.outputUrl).length
  const blocked = slots.value.filter(s => s.blockedReason).map(s => s.label).join(', ')
  return `[Model Comparison]\nPrompt: "${userPrompt.value}"\nModels: ${modelList}\nSeed: ${currentSeed.value}\nImages generated: ${results}/${slots.value.length}${blocked ? `\nBlocked: ${blocked}` : ''}`
}

// --- Main generation flow ---
async function startComparison() {
  if (!userPrompt.value.trim() || isGenerating.value) return
  isGenerating.value = true
  chatRef.value?.onNewRun()

  const isDev = import.meta.env.DEV
  const baseUrl = isDev ? 'http://localhost:17802' : ''

  // Initialize slots + streams
  slots.value = MODELS.value.map((m, idx) => ({
    configId: m.id,
    label: m.label,
    outputUrl: null,
    runId: null,
    queuePosition: idx + 1,
    blockedReason: null,
    isFavorited: false,
  }))
  slotStreams.value = MODELS.value.map(() => useGenerationStream())

  // Fixed seed for all
  const seed = Math.floor(Math.random() * 4294967296)
  currentSeed.value = seed

  chatRef.value?.injectMessage(t('compare.trashyGenerating'))

  try {
    // Sequential generation — one model at a time
    for (let i = 0; i < slots.value.length; i++) {
      const slot = slots.value[i]!
      const stream = slotStreams.value[i]!

      for (let j = i + 1; j < slots.value.length; j++) {
        slots.value[j]!.queuePosition = j - i
      }

      try {
        const result: GenerationResult = await stream.executeWithStreaming({
          prompt: userPrompt.value,
          output_config: slot.configId,
          seed,
          device_id: deviceId,
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
        console.error(`[MODEL-COMPARE] Generation for ${slot.configId} failed:`, e)
        slot.blockedReason = 'Error'
      }
    }

    // Describe generated images via VLM and feed to Trashy
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
              descriptions.push(`[${slot.label}]:\n${data.description}`)
            }
          }
        } catch {
          // Non-critical
        }
      }

      if (descriptions.length > 0) {
        comparisonContext.value = buildContext() + '\n\n--- VLM Image Descriptions ---\n' + descriptions.join('\n\n')
      } else {
        comparisonContext.value = buildContext()
      }
    } else {
      comparisonContext.value = buildContext()
    }
  } catch (e) {
    console.error('[MODEL-COMPARE] Failed:', e)
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
  padding-bottom: 200px;
}

.compare-chat-panel {
  width: 300px;
  flex-shrink: 0;
  position: sticky;
  top: 80px;
  max-height: calc(100vh - 120px);
}

/* Preset selector — above grid, visually distinct from tabs */
.preset-selector {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.preset-card {
  flex: 1;
  padding: 0.6rem 0.8rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
  text-align: center;
}

.preset-card:hover:not(.active):not(:disabled) {
  border-color: rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.04);
}

.preset-card.active {
  border-color: rgba(76, 175, 80, 0.4);
  background: rgba(76, 175, 80, 0.08);
}

.preset-card:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.preset-models {
  font-size: 0.8rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
  letter-spacing: 0.3px;
}

.preset-card.active .preset-models {
  color: rgba(76, 175, 80, 0.9);
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


/* Comparison Grid — always 3 columns */
.comparison-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1rem;
}

.comparison-slot {
  min-width: 0;
}

.slot-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0;
}

.slot-model-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  flex: 1;
}

.slot-queue {
  font-size: 0.65rem;
  color: rgba(255, 183, 77, 0.7);
  background: rgba(255, 183, 77, 0.1);
  padding: 0.1rem 0.4rem;
  border-radius: 8px;
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

/* Fullscreen image modal */
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
