<template>
  <div class="direct-view">
    <!-- Main Content -->
    <div class="main-container">
      <!-- Info Box -->
      <div class="info-box" :class="{ 'expanded': infoExpanded }">
        <div class="info-header" @click="infoExpanded = !infoExpanded">
          <span class="info-icon"><svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="currentColor"><path d="M440-280h80v-240h-80v240Zm40-320q17 0 28.5-11.5T520-640q0-17-11.5-28.5T480-680q-17 0-28.5 11.5T440-640q0 17 11.5 28.5T480-600Zm0 520q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-320Z"/></svg></span>
          <span class="info-title">{{ t('splitCombine.infoTitle') }}</span>
          <span class="info-toggle">{{ infoExpanded ? '▲' : '▼' }}</span>
        </div>
        <div v-if="infoExpanded" class="info-content">
          <p>{{ t('splitCombine.infoDescription') }}</p>
          <div class="info-purpose">
            <strong>{{ t('splitCombine.purposeTitle') }}</strong>
            <p>{{ t('splitCombine.purposeText') }}</p>
          </div>
          <div class="info-tech">
            <strong>{{ t('splitCombine.techTitle') }}</strong>
            <p class="tech-text">{{ t('splitCombine.techText') }}</p>
          </div>
        </div>
      </div>

      <!-- Input Section: Element 1 + Element 2 (Side by Side) -->
      <section class="input-context-section">
        <!-- Element 1 Bubble -->
        <MediaInputBox
          icon="🅰️"
          label="Element 1"
          placeholder="z.B. ein Meteorit im Weltall"
          v-model:value="prompt1"
          input-type="text"
          :rows="6"
          :is-filled="!!prompt1"
          @copy="copyElement1"
          @paste="pasteElement1"
          @clear="clearElement1"
        />

        <!-- Element 2 Bubble -->
        <MediaInputBox
          icon="🅱️"
          label="Element 2"
          placeholder="z.B. ein Silberlöffel in der Besteckschublade"
          v-model:value="prompt2"
          input-type="text"
          :rows="6"
          :is-filled="!!prompt2"
          @copy="copyElement2"
          @paste="pasteElement2"
          @clear="clearElement2"
        />
      </section>

      <!-- Combination Type Dropdown -->
      <section class="input-section">
        <div class="section-card">
          <div class="card-header">
            <span class="card-icon">🎛️</span>
            <span class="card-label">Kombinationsmodus</span>
          </div>
          <div class="dropdown-container">
            <select v-model="combinationType" class="mode-select">
              <option value="linear">Linear (Lineare Kombination)</option>
              <option value="spherical">Spherical (Sphärische Kombination)</option>
            </select>
            <div class="mode-description">{{ modeDescription }}</div>
          </div>
        </div>

        <!-- Execute Button -->
        <button
          class="execute-button"
          :class="{ disabled: !canExecute }"
          :disabled="!canExecute"
          @click="executeWorkflow"
        >
          <span class="button-text">{{ isExecuting ? 'Generiere...' : 'Ausführen' }}</span>
        </button>
      </section>

      <!-- Output Frame (3 States: empty, generating, final) -->
      <section class="output-section">
        <div class="output-frame" :class="{
          empty: !isExecuting && outputs.length === 0,
          generating: isExecuting && outputs.length === 0
        }">
          <!-- State 1: Empty (before generation) -->
          <div v-if="!isExecuting && outputs.length === 0" class="empty-state">
            <div class="empty-icon">🖼️</div>
            <p>Deine 4 Bildvarianten erscheinen hier</p>
            <p class="empty-subtitle">Original · Element 1 · Element 2 · Fusion</p>
          </div>

          <!-- State 2: Generating (progress animation) -->
          <div v-if="isExecuting && outputs.length === 0" class="generation-animation-container">
            <SpriteProgressAnimation :progress="generationProgress" />
          </div>

          <!-- State 3: Final Output (4 Images Side by Side) -->
          <div v-else-if="outputs.length > 0" class="final-output">
            <div class="multi-image-grid">
              <div
                v-for="(output, idx) in outputs"
                :key="idx"
                class="image-box"
              >
                <!-- Image with Actions -->
                <div class="image-with-actions">
                  <img
                    :src="output.url"
                    :alt="output.label"
                    class="output-image"
                    @click="showFullscreen(output.url)"
                  />

                  <!-- Action Toolbar (vertical, right side) -->
                  <div class="action-toolbar">
                    <button class="action-btn" @click="saveMedia(idx)" disabled title="Merken (Coming Soon)">
                      <span class="action-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                          <path d="M440-501Zm0 381L313-234q-72-65-123.5-116t-85-96q-33.5-45-49-87T40-621q0-94 63-156.5T260-840q52 0 99 22t81 62q34-40 81-62t99-22q81 0 136 45.5T831-680h-85q-18-40-53-60t-73-20q-51 0-88 27.5T463-660h-46q-31-45-70.5-72.5T260-760q-57 0-98.5 39.5T120-621q0 33 14 67t50 78.5q36 44.5 98 104T440-228q26-23 61-53t56-50l9 9 19.5 19.5L605-283l9 9q-22 20-56 49.5T498-172l-58 52Zm280-160v-120H600v-80h120v-120h80v120h120v80H800v120h-80Z"/>
                        </svg>
                      </span>
                    </button>
                    <button class="action-btn" @click="sendToI2I(idx)" title="Weiterreichen zu Bild-Transformation">
                      <span class="action-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                          <path d="M480-480ZM200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h320v80H200v560h560v-280h80v280q0 33-23.5 56.5T760-120H200Zm40-160h480L570-480 450-320l-90-120-120 160Zm480-280v-167l-64 63-56-56 160-160 160 160-56 56-64-63v167h-80Z"/>
                        </svg>
                      </span>
                    </button>
                    <button class="action-btn" @click="downloadMedia(idx)" title="Herunterladen">
                      <span class="action-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                          <path d="M480-320 280-520l56-58 104 104v-326h80v326l104-104 56 58-200 200ZM240-160q-33 0-56.5-23.5T160-240v-120h80v120h480v-120h80v120q0 33-23.5 56.5T720-160H240Z"/>
                        </svg>
                      </span>
                    </button>
                    <button class="action-btn" @click="printImage(idx)" title="Drucken">
                      <span class="action-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                          <path d="M640-640v-120H320v120h-80v-200h480v200h-80Zm-480 80h640-640Zm560 100q17 0 28.5-11.5T760-500q0-17-11.5-28.5T720-540q-17 0-28.5 11.5T680-500q0 17 11.5 28.5T720-460Zm-80 260v-160H320v160h320Zm80 80H240v-160H80v-240q0-51 35-85.5t85-34.5h560q51 0 85.5 34.5T880-520v240H720v160Zm80-240v-160q0-17-11.5-28.5T760-560H200q-17 0-28.5 11.5T160-520v160h80v-80h480v80h80Z"/>
                        </svg>
                      </span>
                    </button>
                  </div>
                </div>

                <!-- Image Label -->
                <div class="image-label">
                  <h4>{{ output.label }}</h4>
                  <p>{{ output.description }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Fullscreen Image Modal -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div v-if="fullscreenImage" class="fullscreen-modal" @click="fullscreenImage = null">
          <img :src="fullscreenImage" alt="Fullscreen" class="fullscreen-image" />
          <button class="close-fullscreen" @click="fullscreenImage = null">×</button>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import SpriteProgressAnimation from '@/components/SpriteProgressAnimation.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext, FocusHint } from '@/composables/usePageContext'

// ============================================================================
// Types
// ============================================================================

interface ImageOutput {
  url: string
  label: string
  description: string
  filename: string
}

// ============================================================================
// STATE
// ============================================================================

// Global clipboard
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()

// Router for navigation
const router = useRouter()

// i18n
const { t } = useI18n()

// Info box state
const infoExpanded = ref(false)

const prompt1 = ref('')
const prompt2 = ref('')
const combinationType = ref('linear')
const isExecuting = ref(false)
const outputs = ref<ImageOutput[]>([])
const fullscreenImage = ref<string | null>(null)
const generationProgress = ref(0)

// Seed management for iterative experimentation
const previousPrompt1 = ref('')
const previousPrompt2 = ref('')
const previousType = ref('linear')
const currentSeed = ref<number | null>(null)

// Page Context for Träshy (Session 133)
const pageContextStore = usePageContextStore()

const trashyFocusHint = computed<FocusHint>(() => {
  // During/after execution: bottom-right
  if (isExecuting.value || outputs.value.length > 0) {
    return { x: 95, y: 85, anchor: 'bottom-right' }
  }
  // Default: bottom-left
  return { x: 2, y: 95, anchor: 'bottom-left' }
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'split_and_combine',
  pageContent: {
    inputText: `Prompt 1: ${prompt1.value}\nPrompt 2: ${prompt2.value}`
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

const canExecute = computed(() => {
  return prompt1.value.trim().length > 0 && prompt2.value.trim().length > 0 && !isExecuting.value
})

const modeDescription = computed(() => {
  const descriptions: Record<string, string> = {
    linear: 'Kombiniert Vektoren durch lineare Interpolation',
    spherical: 'Kombiniert Vektoren durch sphärische Interpolation (erhält Vektorlängen)'
  }
  return descriptions[combinationType.value] || ''
})

// ============================================================================
// Methods
// ============================================================================

async function executeWorkflow() {
  if (!canExecute.value) return

  isExecuting.value = true
  outputs.value = []
  generationProgress.value = 0

  // Progress simulation (75 seconds for split and combine)
  const durationSeconds = 75 * 0.9
  const targetProgress = 98
  const updateInterval = 100
  const totalUpdates = (durationSeconds * 1000) / updateInterval
  const progressPerUpdate = targetProgress / totalUpdates

  const progressInterval = setInterval(() => {
    if (generationProgress.value < targetProgress) {
      generationProgress.value += progressPerUpdate
      if (generationProgress.value > targetProgress) {
        generationProgress.value = targetProgress
      }
    }
  }, updateInterval)

  try {
    // Combine elements with brackets for backend
    const combinedPrompt = `${prompt1.value} ${prompt2.value}`  // For "Original" image (no brackets)

    // Intelligent seed logic
    const prompt1Changed = prompt1.value !== previousPrompt1.value
    const prompt2Changed = prompt2.value !== previousPrompt2.value
    const typeChanged = combinationType.value !== previousType.value

    if (prompt1Changed || prompt2Changed || typeChanged) {
      // Elements OR type changed → Keep same seed (user wants to see parameter variation)
      if (currentSeed.value === null) {
        // First run → Use default seed
        currentSeed.value = 123456789
        console.log('[Seed Logic] First run → Default seed:', currentSeed.value)
      } else {
        console.log('[Seed Logic] Elements or type changed → Keeping seed:', currentSeed.value)
      }
      // Update tracking variables
      previousPrompt1.value = prompt1.value
      previousPrompt2.value = prompt2.value
      previousType.value = combinationType.value
    } else {
      // Elements AND type unchanged → New random seed (user wants different variation)
      currentSeed.value = Math.floor(Math.random() * 2147483647)
      console.log('[Seed Logic] No changes → New random seed:', currentSeed.value)
    }

    // Lab Architecture: /legacy = Stage 1 (Safety) + Direct ComfyUI workflow
    const response = await axios.post('/api/schema/pipeline/legacy', {
      prompt: combinedPrompt,
      prompt1: prompt1.value,
      prompt2: prompt2.value,
      output_config: 'split_and_combine_legacy',
      combination_type: combinationType.value,
      seed: currentSeed.value
    })

    if (response.data.status === 'success') {
      // Get run_id to fetch all entities
      const runId = response.data.run_id

      if (runId) {
        clearInterval(progressInterval)
        generationProgress.value = 100

        // Fetch all outputs from pipeline recorder
        await fetchAllOutputs(runId)
      } else {
        clearInterval(progressInterval)
        console.error('[Split and Combine] No run_id in response')
        alert('Fehler: Keine run_id erhalten')
      }
    } else {
      clearInterval(progressInterval)
      alert(`Fehler: ${response.data.error}`)
    }
  } catch (error: any) {
    clearInterval(progressInterval)
    console.error('[Split and Combine] Execution error:', error)
    const errorMessage = error.response?.data?.error || error.message
    alert(`Fehler: ${errorMessage}`)
  } finally {
    isExecuting.value = false
  }
}

async function fetchAllOutputs(runId: string) {
  try {
    // Step 1: Fetch all entities metadata
    const entitiesResponse = await axios.get(`/api/pipeline/${runId}/entities`)
    const entities = entitiesResponse.data.entities || []

    console.log('[Split and Combine] All entities:', entities)

    // Step 2: First, get the 4 individual images using /api/media/images
    try {
      const imagesResponse = await axios.get(`/api/media/images/${runId}`)

      if (imagesResponse.data.images && imagesResponse.data.images.length > 0) {
        // Match images by SaveImage node title (robust against non-deterministic order)
        // Node titles from workflow are used DIRECTLY as display labels
        const images = imagesResponse.data.images || []

        const findByTitle = (substring: string) =>
          images.find((img: any) => img.node_title?.includes(substring))

        const orderedImages = [
          findByTitle('Reference'),        // Node 110: "Reference (Prompt1 + Prompt 2)"
          findByTitle('Combined Vectors'),  // Node 9: "Combined Vectors"
          findByTitle('Prompt 1 only'),    // Node 124: "Prompt 1 only"
          findByTitle('Prompt 2 only')     // Node 131: "Prompt 2 only"
        ].filter(img => img !== undefined)

        // Use node_title DIRECTLY as label (NO translation)
        outputs.value = orderedImages.map((img: any) => ({
          url: img.url,
          label: img.node_title,  // ← DIRECT from backend, NO mapping
          description: '',
          filename: img.metadata?.original_filename || img.filename
        }))

        console.log('[Split and Combine] Loaded 4 individual images')
      }
    } catch (error) {
      console.error('[Split and Combine] Failed to load individual images:', error)
    }

    // Step 3: Then, try to fetch the composite image separately (if it exists)
    const compositeEntity = entities.find((e: any) => e.type === 'output_image_composite')

    if (compositeEntity) {
      try {
        console.log('[Split and Combine] Found composite entity:', compositeEntity.filename)

        // Fetch composite using new filename-based endpoint
        const compositeResponse = await axios.get(`/api/pipeline/${runId}/file/${compositeEntity.filename}`, {
          responseType: 'blob'
        })

        const compositeUrl = URL.createObjectURL(compositeResponse.data)

        // Add composite as 5th image
        outputs.value.push({
          url: compositeUrl,
          label: 'Composite (alle 4)',
          description: 'Zusammengesetztes Bild mit allen Varianten',
          filename: compositeEntity.filename
        })

        console.log('[Split and Combine] Loaded composite image:', compositeEntity.filename)
      } catch (error) {
        console.error('[Split and Combine] Failed to load composite:', error)
      }
    } else {
      console.log('[Split and Combine] No composite entity found')
    }
  } catch (error: any) {
    console.error('[Split and Combine] Error fetching outputs:', error)
  }
}

function showFullscreen(url: string) {
  fullscreenImage.value = url
}

// ============================================================================
// Textbox Actions (Copy/Paste/Clear)
// ============================================================================

function copyElement1() {
  copyToClipboard(prompt1.value)
  console.log('[Split and Combine] Element 1 copied to clipboard')
}

function pasteElement1() {
  prompt1.value = pasteFromClipboard()
  console.log('[Split and Combine] Text pasted to Element 1')
}

function clearElement1() {
  prompt1.value = ''
  console.log('[Split and Combine] Element 1 cleared')
}

function copyElement2() {
  copyToClipboard(prompt2.value)
  console.log('[Split and Combine] Element 2 copied to clipboard')
}

function pasteElement2() {
  prompt2.value = pasteFromClipboard()
  console.log('[Split and Combine] Text pasted to Element 2')
}

function clearElement2() {
  prompt2.value = ''
  console.log('[Split and Combine] Element 2 cleared')
}

// ============================================================================
// Media Actions (For Each Image)
// ============================================================================

function saveMedia(idx: number) {
  // TODO: Implement save/bookmark feature
  console.log('[Media Actions] Save media (not yet implemented)', idx)
  alert('Merken-Funktion kommt bald!')
}

function printImage(idx: number) {
  if (!outputs.value[idx]?.url) return

  const printWindow = window.open(outputs.value[idx].url, '_blank')
  if (printWindow) {
    printWindow.onload = () => {
      printWindow.print()
    }
  }
}

function sendToI2I(idx: number) {
  if (!outputs.value[idx]?.url) return

  // Extract run_id from URL
  const runIdMatch = outputs.value[idx].url.match(/\/api\/.*\/(.+)$/)
  const runId = runIdMatch ? runIdMatch[1] : null

  // Store image data in localStorage for cross-component transfer
  const transferData = {
    imageUrl: outputs.value[idx].url,
    runId: runId,
    timestamp: Date.now()
  }

  localStorage.setItem('i2i_transfer_data', JSON.stringify(transferData))

  console.log('[Image Actions] Transferring to i2i:', transferData)

  // Navigate to image transformation
  router.push('/image-transformation')
}

async function downloadMedia(idx: number) {
  if (!outputs.value[idx]?.url) return

  try {
    // Extract run_id from URL
    const runIdMatch = outputs.value[idx].url.match(/\/api\/.*\/(.+)$/)
    const runId = runIdMatch ? runIdMatch[1] : 'media'

    const filename = `ai4artsed_split_and_combine_${outputs.value[idx].label.replace(/\s+/g, '_')}_${runId}.png`

    // Fetch and download
    const response = await fetch(outputs.value[idx].url)
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`)
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)

    console.log('[Download] Media downloaded:', filename)

  } catch (error) {
    console.error('[Download] Error:', error)
    alert('Download fehlgeschlagen. Bitte versuche es erneut.')
  }
}
</script>

<style scoped>
/* ============================================================================
   Root Container
   ============================================================================ */

.direct-view {
  min-height: 100vh;
  background: #0a0a0a;
  color: #ffffff;
  display: flex;
  flex-direction: column;
}

/* ============================================================================
   Main Container
   ============================================================================ */

.main-container {
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

/* ============================================================================
   Info Box
   ============================================================================ */

.info-box {
  background: rgba(59, 130, 246, 0.1);
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s ease;
}

.info-header {
  display: flex;
  align-items: center;
  padding: 1rem 1.5rem;
  cursor: pointer;
  gap: 0.75rem;
}

.info-header:hover {
  background: rgba(59, 130, 246, 0.15);
}

.info-icon {
  font-size: 1.25rem;
}

.info-title {
  flex: 1;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.info-toggle {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.875rem;
}

.info-content {
  padding: 0 1.5rem 1.5rem;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.6;
}

.info-content p {
  margin: 0 0 1rem 0;
}

.info-purpose {
  margin-top: 1rem;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
}

.info-purpose strong {
  color: rgba(255, 255, 255, 0.9);
  display: block;
  margin-bottom: 0.5rem;
}

.info-purpose p {
  margin: 0;
}

.info-tech {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: rgba(102, 126, 234, 0.15);
  border-radius: 8px;
  border-left: 3px solid rgba(102, 126, 234, 0.6);
}

.info-tech strong {
  color: rgba(255, 255, 255, 0.8);
  display: block;
  margin-bottom: 0.25rem;
  font-size: 0.85rem;
}

.info-tech .tech-text {
  margin: 0;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.7);
  user-select: all;
}

/* ============================================================================
   Sections
   ============================================================================ */

/* Input + Context Section (Side by Side) */
.input-context-section {
  display: flex;
  gap: clamp(1rem, 3vw, 2rem);
  width: 100%;
  justify-content: center;
  flex-wrap: wrap;
}

.input-section {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  width: 100%;
  max-width: calc(480px * 2 + clamp(1rem, 3vw, 2rem)); /* Match width of two side-by-side bubbles */
  margin: 0 auto;
}

.output-section {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* Bubble Cards (from text_transformation.vue) */
.bubble-card {
  background: rgba(20, 20, 20, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: clamp(12px, 2vw, 20px);
  padding: clamp(1rem, 2.5vw, 1.5rem);
  transition: all 0.3s ease;
}

.bubble-card.filled {
  border-color: rgba(102, 126, 234, 0.6);
  background: rgba(102, 126, 234, 0.1);
}

.input-context-section :deep(.media-input-box) {
  flex: 0 1 480px;
  width: 100%;
  max-width: 480px;
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
  min-height: 150px;
}

.bubble-textarea:focus {
  outline: none;
  border-color: rgba(102, 126, 234, 0.8);
  background: rgba(0, 0, 0, 0.4);
}

.bubble-textarea::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

/* Section cards (for dropdown and other elements) */
.section-card {
  background: rgba(20, 20, 20, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  padding: 1.5rem;
  transition: all 0.3s ease;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.card-icon {
  font-size: 1.5rem;
}

/* ============================================================================
   Input Elements
   ============================================================================ */

/* ============================================================================
   Dropdown
   ============================================================================ */

.dropdown-container {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.mode-select {
  width: 100%;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: white;
  font-size: 1rem;
  padding: 0.75rem;
  cursor: pointer;
  font-family: inherit;
}

.mode-select:focus {
  outline: none;
  border-color: rgba(102, 126, 234, 0.8);
}

.mode-description {
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.6);
  font-style: italic;
  padding-left: 0.5rem;
}

/* ============================================================================
   Execute Button
   ============================================================================ */

.execute-button {
  width: 100%;
  padding: 1rem 2rem;
  font-size: 1.2rem;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
}

.execute-button:hover:not(.disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
}

.execute-button.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

/* ============================================================================
   Output Frame (3 States)
   ============================================================================ */

.output-frame {
  width: 100%;
  max-width: calc(480px * 2 + clamp(1rem, 3vw, 2rem)); /* Match width of input elements */
  margin: 2rem auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  background: rgba(30, 30, 30, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  transition: all 0.3s ease;
  min-height: 400px;
}

.output-frame.empty {
  border: 2px dashed rgba(255, 255, 255, 0.2);
  background: rgba(20, 20, 20, 0.5);
}

.output-frame.generating {
  border: 2px solid rgba(76, 175, 80, 0.6);
  background: rgba(30, 30, 30, 0.9);
  box-shadow: 0 0 30px rgba(76, 175, 80, 0.3);
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  opacity: 0.4;
}

.empty-icon {
  font-size: 5rem;
  opacity: 0.5;
}

.empty-state p {
  font-size: 1.1rem;
  color: rgba(255, 255, 255, 0.6);
  text-align: center;
  margin: 0;
}

.empty-subtitle {
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.4);
}

/* Generation Animation Container */
.generation-animation-container {
  width: 100%;
  display: flex;
  justify-content: center;
}

/* Final Output - Multi-Image Grid */
.final-output {
  width: 100%;
}

.multi-image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
  width: 100%;
}

.image-box {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Image with Actions */
.image-with-actions {
  position: relative;
  display: inline-block;
}

.output-image {
  width: 100%;
  max-width: 100%;
  max-height: 400px;
  border-radius: 12px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
  cursor: pointer;
  transition: transform 0.3s ease;
  object-fit: contain;
}

.output-image:hover {
  transform: scale(1.02);
}

/* Action Toolbar */
.action-toolbar {
  position: absolute;
  right: 1rem;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.5rem;
  background: rgba(20, 20, 20, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.action-toolbar .action-btn {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(30, 30, 30, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  padding: 0;
  opacity: 1;
}

.action-toolbar .action-btn:hover:not(:disabled) {
  border-color: rgba(102, 126, 234, 0.8);
  background: rgba(102, 126, 234, 0.2);
  transform: scale(1.1);
}

.action-toolbar .action-btn:active:not(:disabled) {
  transform: scale(0.95);
}

.action-toolbar .action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-icon {
  font-size: 1.5rem;
  line-height: 1;
}

/* Image Label */
.image-label {
  text-align: center;
  padding: 1rem;
  background: rgba(20, 20, 20, 0.8);
  border-radius: 8px;
}

.image-label h4 {
  margin: 0 0 0.5rem 0;
  font-size: 1.1rem;
  color: rgba(255, 255, 255, 0.9);
}

.image-label p {
  margin: 0;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.6);
}

/* Responsive: Stack toolbar below media on mobile */
@media (max-width: 768px) {
  .multi-image-grid {
    grid-template-columns: 1fr;
  }

  .image-with-actions {
    flex-direction: column;
  }

  .action-toolbar {
    position: static;
    transform: none;
    flex-direction: row;
    gap: 0.5rem;
    margin-top: 1rem;
    justify-content: center;
  }

  .action-toolbar .action-btn {
    width: 40px;
    height: 40px;
  }

  .action-icon {
    font-size: 1.25rem;
  }
}

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

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

/* ============================================================================
   Responsive
   ============================================================================ */

@media (max-width: 768px) {
  .main-container {
    padding: 1rem;
  }

  .input-context-section {
    flex-direction: column;
  }

  .input-bubble,
  .context-bubble {
    max-width: 100%;
  }
}
</style>

<style>
/* GLOBAL unscoped - force MediaInputBox width */
.direct-view .input-context-section .media-input-box {
  flex: 0 1 480px !important;
  width: 100% !important;
  max-width: 480px !important;
}
</style>
