<template>
  <div class="text-transformation-view">

    <!-- Single Continuous Flow (no phase transitions) -->
    <div class="phase-2a" ref="mainContainerRef">

        <!-- Section 1: Input + Context (Side by Side) -->
        <section class="input-context-section" ref="inputSectionRef">
          <!-- Input Bubble -->
          <MediaInputBox
            ref="inputBoxRef"
            icon="💡"
            :label="$t('textTransform.inputLabel')"
            :tooltip="$t('textTransform.inputTooltip')"
            :placeholder="$t('textTransform.inputPlaceholder')"
            v-model:value="inputText"
            input-type="text"
            :rows="6"
            :is-filled="!!inputText"
            @copy="copyInputText"
            @paste="pasteInputText"
            @clear="clearInputText"
            @focus="focusedField = 'input'"
            @blur="(val: string) => logPromptChange('input', val)"
          />

          <!-- Context Bubble -->
          <MediaInputBox
            ref="contextBoxRef"
            icon="📋"
            :label="$t('textTransform.contextLabel')"
            :tooltip="$t('textTransform.contextTooltip')"
            :placeholder="$t('textTransform.contextPlaceholder')"
            v-model:value="contextPrompt"
            input-type="text"
            :rows="6"
            :is-filled="!!contextPrompt"
            :is-required="!contextPrompt"
            :show-preset-button="true"
            @open-preset-selector="showPresetOverlay = true"
            @copy="copyContextPrompt"
            @paste="pasteContextPrompt"
            @clear="clearContextPrompt"
            @focus="focusedField = 'context'"
            @blur="(val: string) => logPromptChange('context_prompt', val)"
          />
        </section>

        <!-- START BUTTON #1: Trigger Interception (Between Context and Interception) -->
        <GenerationButton
          :disabled="!inputText"
          :executing="isInterceptionLoading"
          :checking-safety="isAnySafetyChecking"
          :label="$t('common.start')"
          :checking-label="$t('common.checkingSafety')"
          :executing-label="$t('common.generating')"
          @click="runInterception()"
        >
          <!-- Wikipedia Badge (Session 139) - stable area next to Stage 1 -->
          <transition name="fade">
            <div v-if="wikipediaData.terms.length > 0" class="lora-stamp wikipedia-lora" @click="wikipediaExpanded = !wikipediaExpanded">
              <div class="stamp-inner lora-inner">
                <div class="stamp-icon lora-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
                    <!-- Wikipedia "W" in puzzle globe style -->
                    <circle cx="12" cy="12" r="10" fill="#fff" stroke="#000" stroke-width="1"/>
                    <!-- Puzzle pieces (simplified globe) -->
                    <path d="M12 2 A10 10 0 0 1 22 12" fill="none" stroke="#000" stroke-width="0.5"/>
                    <path d="M22 12 A10 10 0 0 1 12 22" fill="none" stroke="#000" stroke-width="0.5"/>
                    <path d="M12 22 A10 10 0 0 1 2 12" fill="none" stroke="#000" stroke-width="0.5"/>
                    <path d="M2 12 A10 10 0 0 1 12 2" fill="none" stroke="#000" stroke-width="0.5"/>
                    <!-- "W" letterform -->
                    <text x="12" y="17" font-family="Georgia, serif" font-size="14" font-weight="bold" text-anchor="middle" fill="#000">W</text>
                  </svg>
                </div>
                <div class="stamp-text">
                  {{ wikipediaData.terms.length }} Begriff{{ wikipediaData.terms.length > 1 ? 'e' : '' }}
                </div>
              </div>
              <div v-if="wikipediaExpanded" class="lora-details">
                <div v-for="(item, index) in wikipediaData.terms" :key="index" class="lora-item">
                  <template v-if="item.success && item.url">
                    <a :href="item.url" target="_blank" rel="noopener">
                      {{ item.title }}
                    </a>
                  </template>
                  <template v-else>
                    <span class="wikipedia-not-found">
                      {{ item.term }} <small>(nicht gefunden)</small>
                    </span>
                  </template>
                </div>
              </div>
            </div>
          </transition>
        </GenerationButton>

        <!-- Section 3: Interception Preview (filled after Start #1) -->
        <section class="interception-section" ref="interceptionSectionRef">
          <MediaInputBox
            icon="→"
            :label="$t('textTransform.resultLabel')"
            :placeholder="$t('textTransform.resultPlaceholder')"
            v-model:value="interceptionResult"
            input-type="text"
            :rows="5"
            resize-type="auto"
            :is-empty="!interceptionResult"
            :is-loading="isInterceptionLoading"
            :loading-message="interceptionLoadingMessage"
            :enable-streaming="true"
            :stream-url="streamingUrl"
            :stream-params="streamingParams"
            @stream-started="handleStreamStarted"
            @stream-complete="handleStreamComplete"
            @stream-error="handleStreamError"
            @wikipedia-lookup="handleWikipediaLookup"
            @copy="copyInterceptionResult"
            @paste="pasteInterceptionResult"
            @clear="clearInterceptionResult"
            @focus="focusedField = 'interception'"
            @blur="(val: string) => logPromptChange('interception', val)"
          />
          <!-- LoRA Badge (Session 116) - shows when interception config has LoRAs -->
          <transition name="fade">
            <div v-if="configLoras.length > 0" class="lora-stamp config-lora" @click="loraExpanded = !loraExpanded">
              <div class="stamp-inner lora-inner">
                <div class="stamp-icon lora-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
                    <ellipse cx="12" cy="12" rx="6" ry="7" fill="#22c55e"/>
                    <ellipse cx="14" cy="13" rx="3" ry="4" fill="#16a34a"/>
                    <ellipse cx="15" cy="14" rx="1.5" ry="2.5" fill="#eab308"/>
                    <circle cx="9" cy="7" r="4" fill="#22c55e"/>
                    <path d="M5 7 Q4 8 5 9 Q6 8.5 6 7.5 Q6 7 5 7" fill="#f97316"/>
                    <circle cx="8" cy="6.5" r="0.8" fill="#1e1e1e"/>
                    <ellipse cx="6.5" cy="8.5" rx="1" ry="0.8" fill="#f97316"/>
                    <path d="M14 18 Q16 20 15 22 Q14 21 13 22 Q12 20 14 18" fill="#16a34a"/>
                    <rect x="2" y="17" width="20" height="1.5" rx="0.75" fill="#a16207"/>
                    <path d="M10 17 L9 18.5 M10 17 L10.5 18.5 M11 17 L11 18.5" stroke="#f97316" stroke-width="0.8" fill="none"/>
                    <path d="M14 17 L13.5 18.5 M14 17 L14.5 18.5 M15 17 L15 18.5" stroke="#f97316" stroke-width="0.8" fill="none"/>
                  </svg>
                </div>
                <div class="stamp-text">
                  {{ configLoras.length }} LoRA{{ configLoras.length > 1 ? 's' : '' }}
                </div>
              </div>
              <div v-if="loraExpanded" class="lora-details">
                <div v-for="lora in configLoras" :key="lora.name" class="lora-item">
                  {{ formatLoraName(lora.name) }} <span class="lora-strength">{{ lora.strength }}</span>
                </div>
              </div>
            </div>
          </transition>
        </section>

        <!-- Section 2: Category Selection (Horizontal Row) - Always visible -->
        <section class="category-section" ref="categorySectionRef">
          <h2 v-if="executionPhase !== 'initial'" class="section-title">Wähle ein Medium aus</h2>
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
                <svg v-if="category.id === 'image'" xmlns="http://www.w3.org/2000/svg" height="32" viewBox="0 -960 960 960" width="32" fill="currentColor">
                  <path d="M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h560q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560H200v560Zm40-80h480L570-480 450-320l-90-120-120 160Zm-40 80v-560 560Zm140-360q25 0 42.5-17.5T400-620q0-25-17.5-42.5T340-680q-25 0-42.5 17.5T280-620q0 25 17.5 42.5T340-560Z"/>
                </svg>
                <svg v-else-if="category.id === 'video'" xmlns="http://www.w3.org/2000/svg" height="32" viewBox="0 -960 960 960" width="32" fill="currentColor">
                  <path d="M200-320h400L462-500l-92 120-62-80-108 140Zm-40 160q-33 0-56.5-23.5T80-240v-480q0-33 23.5-56.5T160-800h480q33 0 56.5 23.5T720-720v180l160-160v440L720-420v180q0 33-23.5 56.5T640-160H160Zm0-80h480v-480H160v480Zm0 0v-480 480Z"/>
                </svg>
                <svg v-else-if="category.id === 'sound'" xmlns="http://www.w3.org/2000/svg" height="32" viewBox="0 -960 960 960" width="32" fill="currentColor">
                  <path d="M709-255H482L369-142q-23 23-56.5 23T256-142L143-255q-23-23-23-57t23-57l112-112v-227l454 453Zm-193-80L335-516v68L199-312l113 113 136-136h68ZM289-785q107-68 231.5-54.5T735-736q90 90 103.5 214.5T784-290l-58-58q45-82 31.5-173.5T678-679q-66-66-157.5-79.5T347-727l-58-58Zm118 118q57-17 115-7t100 52q42 42 51.5 99.5T666-408l-68-68q0-25-7.5-48.5T566-565q-18-18-41.5-26t-49.5-8l-68-68Zm-49 309Z"/>
                </svg>
                <svg v-else-if="category.id === '3d'" xmlns="http://www.w3.org/2000/svg" height="32" viewBox="0 -960 960 960" width="32" fill="currentColor">
                  <path d="M520-360h120q33 0 56.5-23.5T720-440v-80q0-33-23.5-56.5T640-600H520v240Zm60-60v-120h60q8 0 14 6t6 14v80q0 8-6 14t-14 6h-60Zm-320 60h140q17 0 28.5-11.5T440-400v-40q0-17-11.5-28.5T400-480q17 0 28.5-11.5T440-520v-40q0-17-11.5-28.5T400-600H260v60h120v30h-80v60h80v30H260v60ZM160-160q-33 0-56.5-23.5T80-240v-480q0-33 23.5-56.5T160-800h640q33 0 56.5 23.5T880-720v480q0 33-23.5 56.5T800-160H160Zm0-80h640v-480H160v480Zm0 0v-480 480Z"/>
                </svg>
                <span v-else>{{ category.emoji }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- Section 2.5: Model Selection (Shows DIRECTLY under category, disabled until after interception) -->
        <section class="config-section">
          <h2 v-if="selectedCategory" class="section-title">wähle ein Modell aus</h2>
          <div class="config-bubbles-container">
            <div class="config-bubbles-row">
              <div
                v-for="config in configsForCategory"
                :key="config.id"
                class="config-bubble"
                :class="{
                  selected: selectedConfig === config.id,
                  loading: config.id === selectedConfig && isOptimizationLoading,
                  'light-bg': config.lightBg,
                  disabled: !areModelBubblesEnabled,
                  hovered: hoveredConfigId === config.id
                }"
                :style="{ '--bubble-color': config.color }"
                :data-config="config.id"
                @click="areModelBubblesEnabled && selectConfig(config.id)"
                @mouseenter="handleBubbleMouseEnter(config.id)"
                @mouseleave="handleBubbleMouseLeave"
                role="button"
                :aria-pressed="selectedConfig === config.id"
                :aria-disabled="!areModelBubblesEnabled"
                :tabindex="areModelBubblesEnabled ? 0 : -1"
                @keydown.enter="areModelBubblesEnabled && selectConfig(config.id)"
                @keydown.space.prevent="areModelBubblesEnabled && selectConfig(config.id)"
              >
                <img v-if="config.logo" :src="config.logo" :alt="config.label" class="bubble-logo" />
                <div v-else class="bubble-emoji-medium">{{ config.emoji }}</div>

                <!-- Hover info overlay (shows INSIDE bubble when hovered) -->
                <div v-if="hoveredConfigId === config.id" class="bubble-hover-info">
                  <div class="hover-info-name">{{ getHoverCardData(config.id).name }}</div>
                  <div class="hover-info-meta">
                    <div class="meta-row">
                      <span class="meta-label">Qual.</span>
                      <span class="meta-value">
                        <span class="stars-filled">{{ '★'.repeat(getHoverCardData(config.id).quality) }}</span><span class="stars-unfilled">{{ '☆'.repeat(5 - getHoverCardData(config.id).quality) }}</span>
                      </span>
                    </div>
                    <div class="meta-row">
                      <span class="meta-label">Speed</span>
                      <span class="meta-value">
                        <span class="stars-filled">{{ '★'.repeat(getHoverCardData(config.id).speed) }}</span><span class="stars-unfilled">{{ '☆'.repeat(5 - getHoverCardData(config.id).speed) }}</span>
                      </span>
                    </div>
                    <div class="meta-row">
                      <span class="meta-value duration-only">⏱ {{ getHoverCardData(config.id).durationRange }} sec</span>
                    </div>
                  </div>
                </div>

                <div v-if="config.id === selectedConfig && isOptimizationLoading" class="loading-indicator">
                  <div class="spinner"></div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- Section 4: Optimized Prompt Preview (Always visible, disabled until model selected) -->
        <section class="optimization-section" ref="optimizationSectionRef">
          <MediaInputBox
            icon="✨"
            :label="$t('textTransform.optimizedLabel')"
            :placeholder="optimizedPrompt ? '' : $t('textTransform.optimizedPlaceholder')"
            v-model:value="optimizedPrompt"
            input-type="text"
            :rows="5"
            resize-type="auto"
            :is-empty="!optimizedPrompt"
            :is-loading="isOptimizationLoading"
            :disabled="!selectedConfig"
            :loading-message="optimizationLoadingMessage"
            :enable-streaming="true"
            :stream-url="optimizationStreamingUrl"
            :stream-params="optimizationStreamingParams"
            @stream-started="handleOptimizationStreamStarted"
            @stream-complete="handleOptimizationStreamComplete"
            @stream-error="handleOptimizationStreamError"
            @copy="copyOptimizedPrompt"
            @paste="pasteOptimizedPrompt"
            @clear="clearOptimizedPrompt"
            @focus="focusedField = 'optimization'"
            @blur="(val: string) => logPromptChange('optimized_prompt', val)"
          />
        </section>

        <!-- Code Output (p5.js) - appears right after optimization -->
        <!-- P5.js Code Output -->
        <div v-if="outputMediaType === 'code' && outputCode && selectedConfig === 'p5js_code'" class="code-output-stage2">
          <div class="code-display">
            <div class="code-header">
              <h3>P5.js Code</h3>
              <button @click="runCode" class="action-btn run-btn" title="Code ausführen">▶️</button>
            </div>
            <textarea
              v-model="editedCode"
              class="code-textarea"
              rows="15"
            ></textarea>
          </div>
          <div class="code-preview">
            <h3>Live Preview</h3>
            <iframe
              :key="iframeKey"
              :srcdoc="getP5jsIframeContent()"
              class="p5js-iframe"
              sandbox="allow-scripts"
            ></iframe>
          </div>
        </div>

        <!-- Tone.js Code Output -->
        <div v-if="outputMediaType === 'code' && outputCode && selectedConfig === 'tonejs_code'" class="code-output-stage2 tonejs-output">
          <div class="code-display">
            <div class="code-header">
              <h3>Tone.js Code</h3>
              <button @click="runCode" class="action-btn run-btn" title="Code ausführen">▶️</button>
            </div>
            <textarea
              v-model="editedCode"
              class="code-textarea"
              rows="15"
            ></textarea>
          </div>
          <div class="code-preview tonejs-preview">
            <h3>Audio Player</h3>
            <iframe
              :key="iframeKey"
              :srcdoc="getToneJsIframeContent()"
              class="tonejs-iframe"
              sandbox="allow-scripts"
            ></iframe>
          </div>
        </div>

        <!-- START BUTTON #2: Trigger Generation (Between Optimized Prompt and Output) -->
        <GenerationButton
          :disabled="(executionPhase !== 'optimization_done' && executionPhase !== 'generation_done') || !optimizedPrompt"
          :executing="isPipelineExecuting"
          :label="$t('common.start')"
          :executing-label="$t('common.generating')"
          :error-message="generationErrorMessage"
          @click="startGeneration()"
        >
          <!-- Stage 3+4 Safety Badges (generation path) -->
          <SafetyBadges v-if="safetyChecks.length > 0" :checks="safetyChecks" />

          <!-- LoRA Badge (Session 116) - shows configLoras before generation, activeLoras after -->
          <transition name="fade">
            <div v-if="stage4Loras.length > 0" class="lora-stamp" @click="loraExpanded = !loraExpanded">
              <div class="stamp-inner lora-inner">
                <div class="stamp-icon lora-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
                    <ellipse cx="12" cy="12" rx="6" ry="7" fill="#22c55e"/>
                    <ellipse cx="14" cy="13" rx="3" ry="4" fill="#16a34a"/>
                    <ellipse cx="15" cy="14" rx="1.5" ry="2.5" fill="#eab308"/>
                    <circle cx="9" cy="7" r="4" fill="#22c55e"/>
                    <path d="M5 7 Q4 8 5 9 Q6 8.5 6 7.5 Q6 7 5 7" fill="#f97316"/>
                    <circle cx="8" cy="6.5" r="0.8" fill="#1e1e1e"/>
                    <ellipse cx="6.5" cy="8.5" rx="1" ry="0.8" fill="#f97316"/>
                    <path d="M14 18 Q16 20 15 22 Q14 21 13 22 Q12 20 14 18" fill="#16a34a"/>
                    <rect x="2" y="17" width="20" height="1.5" rx="0.75" fill="#a16207"/>
                    <path d="M10 17 L9 18.5 M10 17 L10.5 18.5 M11 17 L11 18.5" stroke="#f97316" stroke-width="0.8" fill="none"/>
                    <path d="M14 17 L13.5 18.5 M14 17 L14.5 18.5 M15 17 L15 18.5" stroke="#f97316" stroke-width="0.8" fill="none"/>
                  </svg>
                </div>
                <div class="stamp-text">
                  {{ stage4Loras.length }} LoRA{{ stage4Loras.length > 1 ? 's' : '' }}
                </div>
              </div>
              <!-- Expandable Liste -->
              <div v-if="loraExpanded" class="lora-details">
                <div v-for="lora in stage4Loras" :key="lora.name" class="lora-item">
                  {{ formatLoraName(lora.name) }} <span class="lora-strength">{{ lora.strength }}</span>
                </div>
              </div>
            </div>
          </transition>
        </GenerationButton>

        <!-- OUTPUT BOX (Template Component) -->
        <MediaOutputBox
          ref="pipelineSectionRef"
          :output-image="outputImage"
          :media-type="outputMediaType"
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
          :mesh-url="outputMeshUrl"
          :thumbnail-url="outputThumbnailUrl"
          forward-button-title="Weiterreichen zu Bild-Transformation"
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
import { ref, computed, nextTick, onMounted, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePipelineExecutionStore } from '@/stores/pipelineExecution'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useFavoritesStore } from '@/stores/favorites'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useDeviceId } from '@/composables/useDeviceId'
import axios from 'axios'
import MediaOutputBox from '@/components/MediaOutputBox.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import SafetyBadges from '@/components/SafetyBadges.vue'
import GenerationButton from '@/components/GenerationButton.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import { useCurrentSession } from '@/composables/useCurrentSession'
import { useGenerationStream } from '@/composables/useGenerationStream'
import { useI18n } from 'vue-i18n'
import { usePageContextStore } from '@/stores/pageContext'
import { useUiModeStore } from '@/stores/uiMode'
import type { PageContext, FocusHint } from '@/composables/usePageContext'
import { getModelAvailability, type ModelAvailability } from '@/services/api'
import { useSafetyEventStore } from '@/stores/safetyEvent'

// Import styles (Phase 1 refactoring: extracted from inline <style scoped>)
import '@/assets/animations.css'
import './text_transformation.css'

// Language support
const userPreferences = useUserPreferencesStore()
const currentLanguage = computed(() => userPreferences.language)

// Favorites support (Session 127)
const favoritesStore = useFavoritesStore()

// UI mode for expert denoising view
const uiModeStore = useUiModeStore()

// Safety store for pre-generation check
const safetyStore = useSafetyEventStore()

// ============================================================================
// Session Management (Session 82: Chat Overlay Context)
// ============================================================================
const { updateSession } = useCurrentSession()

// ============================================================================
// Types
// ============================================================================

type StageStatus = 'waiting' | 'processing' | 'completed'

interface Category {
  id: string
  label: string
  emoji: string
  color: string
  disabled?: boolean
}

interface Config {
  id: string
  label: string
  emoji: string
  color: string
  description: string
  logo?: string
  lightBg?: boolean
}

interface PipelineStage {
  id: string
  label: string
  emoji: string
  color: string
  status: StageStatus
}

// ============================================================================
// State
// ============================================================================

// Global clipboard (shared across all views)
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()

// Form state
const inputText = ref('')
const contextPrompt = ref('')
const focusedField = ref<'input' | 'context' | 'interception' | 'optimization' | null>(null)
const showPresetOverlay = ref(false)
const selectedCategory = ref<string | null>(null)
const selectedConfig = ref<string | null>(null)

// Estimated generation duration from output config (for animation display)
const estimatedGenerationSeconds = computed(() => {
  if (!selectedConfig.value) return 30
  const chunk = chunkMetadata.value[selectedConfig.value]
  if (!chunk?.duration) return 30
  // Handle ranges like "20-60" → use average
  const durationStr = String(chunk.duration)
  if (durationStr.includes('-')) {
    const [min, max] = durationStr.split('-').map(s => parseInt(s))
    return Math.round(((min || 30) + (max || 30)) / 2)
  }
  return parseInt(durationStr) || 30
})

const interceptionResult = ref('')
const isInterceptionLoading = ref(false)
const optimizedPrompt = ref('')
const isOptimizationLoading = ref(false)
const hasOptimization = ref(false)  // Track if optimization was applied
const optimizationInstruction = ref('')  // Loaded from backend before streaming

// Contextual loading message for optimization (model-specific + translation hint)
const optimizationLoadingMessage = computed(() => {
  const cfg = selectedConfig.value || ''
  const isSd35 = cfg.startsWith('sd35')
  const base = isSd35 ? t('textTransform.loadingSd35') : t('textTransform.loadingDefault')
  return base + ' ' + t('textTransform.loadingTranslateHint')
})

// Model availability (Session 91+)
const modelAvailability = ref<ModelAvailability>({})
const availabilityLoading = ref(true)

// Phase 4: Seed management for iterative correction
const previousOptimizedPrompt = ref('')  // Track previous prompt for comparison
const previousSelectedConfig = ref('')  // Track previous model for comparison
const currentSeed = ref<number | null>(null)  // Current seed (null = first run)
const currentRunId = ref<string | null>(null)  // Run ID from interception (prompting_process_xxx)
const currentRunHasOutput = ref(false)  // Session 130: True after media generation (stops logging)
const lastInterceptionConfig = ref<string | null>(null)  // Track which interception config was used

const deviceId = useDeviceId()

// Execution phase tracking
// 'initial' -> 'interception_done' -> 'optimization_done' -> 'generation_done'
const executionPhase = ref<'initial' | 'interception_done' | 'optimization_done' | 'generation_done'>('initial')

// Pipeline execution state
const isPipelineExecuting = ref(false)
const generationErrorMessage = ref('')
const outputImage = ref<string | null>(null)
const outputMediaType = ref<string>('image') // Media type: image, video, audio, music, 3d, code
const outputCode = ref<string | null>(null) // For code output (p5.js, etc.)
const outputMeshUrl = ref<string | null>(null) // For 3D model GLB URL
const outputThumbnailUrl = ref<string | null>(null) // For 3D Blender thumbnail
const editedCode = ref<string>('') // Editable code (user can modify)
const iframeKey = ref<number>(0) // Force iframe re-render
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

const estimatedDurationSeconds = ref<string>('30')  // Stores duration from backend (30s default if optimization skipped)
const activeLoras = ref<Array<{name: string, strength: number}>>([])
const loraExpanded = ref(false)

// Session 139: Wikipedia lookup state
// Session 136: terms now include actual Wikipedia results (title, url, language)
const wikipediaData = ref<{ active: boolean; terms: Array<{ term: string; lang: string; title: string; url: string; success: boolean }> }>({ active: false, terms: [] })
const wikipediaExpanded = ref(false)
const wikipediaStatusText = ref<string>('')  // Session 139: Live status text for loading message

// Refs for DOM elements and scrolling
const mainContainerRef = ref<HTMLElement | null>(null)
const startButtonRef = ref<HTMLElement | null>(null)
const pipelineSectionRef = ref<any>(null) // MediaOutputBox component instance
const categorySectionRef = ref<HTMLElement | null>(null)
const inputSectionRef = ref<HTMLElement | null>(null)
const inputBoxRef = ref<InstanceType<typeof MediaInputBox> | null>(null)
const contextBoxRef = ref<InstanceType<typeof MediaInputBox> | null>(null)
const isAnySafetyChecking = computed(() => !!(inputBoxRef.value?.isCheckingSafety || contextBoxRef.value?.isCheckingSafety))
const interceptionSectionRef = ref<HTMLElement | null>(null)
const optimizationSectionRef = ref<HTMLElement | null>(null)

// ============================================================================
// Page Context for Träshy (Session 133)
// Using Pinia store instead of provide/inject for cross-component communication
// ============================================================================
const pageContextStore = usePageContextStore()

// Helper: Get element's vertical center as viewport percentage
function getElementY(el: HTMLElement | null): number {
  if (!el) return 50
  const rect = el.getBoundingClientRect()
  const centerY = rect.top + rect.height / 2
  return Math.max(10, Math.min(90, (centerY / window.innerHeight) * 100))
}

// Track current Träshy Y position (updated on focus/phase changes)
const trashyY = ref(50)

// Update Träshy position when focus or phase changes
watch([focusedField, executionPhase, isPipelineExecuting, outputImage, selectedCategory], () => {
  nextTick(() => {
    // Priority 1: Follow focused field
    if (focusedField.value === 'input' || focusedField.value === 'context') {
      trashyY.value = getElementY(inputSectionRef.value)
      return
    }
    if (focusedField.value === 'interception') {
      trashyY.value = getElementY(interceptionSectionRef.value)
      return
    }
    if (focusedField.value === 'optimization') {
      trashyY.value = getElementY(optimizationSectionRef.value)
      return
    }

    // Priority 2: Follow workflow phase
    if (isPipelineExecuting.value || outputImage.value) {
      // During/after generation: near output
      trashyY.value = pipelineSectionRef.value?.sectionRef
        ? getElementY(pipelineSectionRef.value.sectionRef)
        : 85
    } else if (executionPhase.value !== 'initial' && selectedCategory.value) {
      // Category selected: near category section
      trashyY.value = getElementY(categorySectionRef.value)
    } else if (executionPhase.value !== 'initial') {
      // After interception: near interception result
      trashyY.value = getElementY(interceptionSectionRef.value)
    } else {
      // Initial: near input section
      trashyY.value = getElementY(inputSectionRef.value)
    }
  })
}, { immediate: true })

// Determine Träshy position - always right side, Y follows focus/phase
const trashyFocusHint = computed<FocusHint>(() => {
  return { x: 95, y: trashyY.value, anchor: 'bottom-right' }
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'text_transformation',
  pageContent: {
    inputText: inputText.value,
    contextPrompt: contextPrompt.value,
    interceptionResult: interceptionResult.value,
    optimizedPrompt: optimizedPrompt.value,
    selectedCategory: selectedCategory.value,
    selectedConfig: selectedConfig.value
  },
  focusHint: trashyFocusHint.value
}))

// Update store whenever context changes
watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

// Clear context when leaving the view
onUnmounted(() => {
  pageContextStore.clearContext()
})

// ============================================================================
// Data
// ============================================================================

const availableCategories: Category[] = [
  { id: 'image', label: 'Bild', emoji: '🖼️', color: '#4CAF50' },
  { id: 'video', label: 'Video', emoji: '📽️', color: '#9C27B0' },
  { id: 'sound', label: 'Sound', emoji: '🔊', color: '#FF9800' },
]

const configsByCategory: Record<string, Config[]> = {
  image: [
    { id: 'sd35_large', label: 'Stable\nDiffusion', emoji: '🎨', color: '#2196F3', description: 'Klassische Bildgenerierung', logo: '/logos/logo_stable_diffusion.png', lightBg: false },
    { id: 'qwen', label: 'Qwen', emoji: '🌸', color: '#9C27B0', description: 'Qwen Vision Model', logo: '/logos/Qwen_logo.png', lightBg: false },
    { id: 'flux2', label: 'Flux 2', emoji: '⚡', color: '#FF6B35', description: 'Hochwertige Bildgenerierung mit Flux 2 Dev', logo: '/logos/flux2_logo.png', lightBg: false },
    { id: 'gemini_3_pro_image', label: 'Gemini 3\nPro', emoji: '🔷', color: '#4285F4', description: 'Google Gemini 3 Pro via Mammouth AI (EU)', logo: '/logos/gemini_logo.png', lightBg: false },
    { id: 'p5js_code', label: 'P5.js', emoji: '💻', color: '#ED225D', description: 'Generative Computergrafik mit P5.js Code', logo: '/logos/p5js_logo.png', lightBg: false }
  ],
  video: [
    { id: 'ltx_video', label: 'LTX\nVideo', emoji: '⚡', color: '#9C27B0', description: 'Schnelle lokale Videogenerierung', logo: '/logos/ltx_logo.png', lightBg: false },
    { id: 'wan22_t2v_video_fast', label: 'Wan 2.2\n14B Fast', emoji: '🎬', color: '#E91E63', description: 'Schnelle 14B Videogenerierung mit LightX2V (4 Steps)', logo: '/logos/Qwen_logo.png', lightBg: false }
  ],
  sound: [
    { id: 'acenet_t2instrumental', label: 'ACE\nInstrumental', emoji: '🎵', color: '#FF5722', description: 'KI-Musikgenerierung für Instrumentalstücke', logo: '/logos/ace_logo.png', lightBg: false },
    { id: 'stableaudio_open', label: 'Stable\nAudio', emoji: '🔊', color: '#00BCD4', description: 'Open-Source Audio-Generierung (max 47s)', logo: '/logos/stableaudio_logo.png', lightBg: false },
    { id: 'tonejs_code', label: 'Tone.js', emoji: '🎹', color: '#FF4081', description: 'Browser-basierte Musiksynthese mit Live-Code' }
  ],
}

// ============================================================================
// Hover Card State & Metadata
// ============================================================================

// Hover state
const hoveredConfigId = ref<string | null>(null)

// Chunk metadata (loaded from API - NO hardcoded values!)
const chunkMetadata = ref<Record<string, any>>({})

// Mapping from config IDs to chunk base names (after stripping "output_X_")
const configIdToChunkName: Record<string, string> = {
  'sd35_large': 'sd35_large',
  'qwen': 'qwen',
  'flux2': 'flux2_diffusers',
  'gemini_3_pro_image': 'gemini_3_pro',
  'p5js_code': 'p5js',
  'tonejs_code': 'tonejs',
  'ltx_video': 'ltx',
  'wan22_t2v_video_fast': 'wan22_t2v_fast',
  'acenet_t2instrumental': 'acenet',
  'stableaudio_open': 'stableaudio',
  'hunyuan3d_text_to_3d': 'hunyuan3d'
}

// Helper to calculate speed from duration (0s=5★, 90s=1★)
function calculateSpeedFromDuration(durationStr: string | number): number {
  // Parse duration (handle ranges like "10-30" or single values like "12")
  let duration: number
  const durationString = String(durationStr)

  if (durationString.includes('-')) {
    // Range: take the lower bound for speed calculation
    const parts = durationString.split('-').map(s => parseFloat(s.trim()))
    duration = parts[0] || 0
  } else {
    duration = parseFloat(durationString) || 0
  }

  // Linear interpolation: 0s → 5★, 90s → 1★
  // Formula: speed = max(1, min(5, floor((90 - duration) / 18) + 1))
  const speed = Math.max(1, Math.min(5, Math.floor((90 - duration) / 18) + 1))
  return speed
}

// Load ALL metadata from chunks (Q, Spd auto-calculated, Duration, VRAM)
onMounted(async () => {
  try {
    const response = await fetch('/api/schema/chunk-metadata')
    const chunks = await response.json()

    Object.values(chunks).forEach((chunk: any) => {
      const chunkName = chunk.name
      const chunkBaseName = chunkName.replace(/^output_(image|video|audio|code)_/, '')

      // Find ALL matching config IDs (multiple configs can share one chunk)
      const matchingConfigIds = Object.keys(configIdToChunkName).filter(
        key => configIdToChunkName[key] === chunkBaseName
      )

      for (const configId of matchingConfigIds) {
        const duration = chunk.meta?.estimated_duration_seconds || '?'

        chunkMetadata.value[configId] = {
          quality: chunk.meta?.quality_rating || 3,
          speed: duration !== '?' ? calculateSpeedFromDuration(duration) : 3,
          duration: duration,
          vram: chunk.meta?.gpu_vram_mb || 0
        }
      }
    })
  } catch (error) {
    console.error('Failed to load chunk metadata:', error)
  }
})

// Hover handlers
function handleBubbleMouseEnter(configId: string) {
  if (!areModelBubblesEnabled.value) return
  hoveredConfigId.value = configId
}

function handleBubbleMouseLeave() {
  hoveredConfigId.value = null
}

// Helper to calculate duration range
function calculateDurationRange(configId: string): string {
  const chunk = chunkMetadata.value[configId]
  if (!chunk) return '?'

  const baseDuration = chunk.duration
  const vramMb = chunk.vram || 0

  // Handle existing ranges (e.g., "5-15", "20-60")
  if (typeof baseDuration === 'string' && baseDuration.includes('-')) {
    return baseDuration  // Already a range, use as-is
  }

  // Parse numeric duration
  const base = parseInt(String(baseDuration)) || 0

  // Special case: API models or instant (0s)
  if (base === 0 || vramMb === 0) {
    return '~1'  // API latency or instant
  }

  // Calculate VRAM load time: ~1s per GB, minimum 2s
  const loadTime = Math.max(2, Math.round(vramMb / 1000))

  // Only show range if load time significant (>2s)
  if (loadTime > 2) {
    return `${base}-${base + loadTime}`
  } else {
    return String(base)
  }
}

// Full model names for hover cards
const modelFullNames: Record<string, string> = {
  sd35_large: 'Stable Diffusion 3.5 Large',
  qwen: 'Qwen 2.5 Vision',
  flux2: 'Flux 2 Dev',
  gemini_3_pro_image: 'Gemini 3 Pro',
  p5js_code: 'p5.js Code Generation',
  tonejs_code: 'Tone.js Music Generation',
  ltx_video: 'LTX Video',
  wan22_t2v_video_fast: 'Wan 2.2 T2V 14B Fast',
  acenet_t2instrumental: 'ACE Step Instrumental',
  stableaudio_open: 'Stable Audio Open'
}

// Helper to get hover data from chunks
function getHoverCardData(configId: string) {
  const chunk = chunkMetadata.value[configId]
  if (!chunk) return { name: '', quality: 3, speed: 3, durationRange: '?' }

  return {
    name: modelFullNames[configId] || configId,
    quality: chunk.quality,
    speed: chunk.speed,
    durationRange: calculateDurationRange(configId)
  }
}

// Helper to render stars
function renderStars(count: number): string {
  return '★'.repeat(count) + '☆'.repeat(5 - count)
}

const pipelineStages = ref<PipelineStage[]>([
  { id: 'generation', label: 'Bild', emoji: '🎨', color: '#2196F3', status: 'waiting' }
])

// Computed: Pipeline stages with dynamic medium label
const displayPipelineStages = computed(() => {
  const stages = [...pipelineStages.value]

  // Update generation stage label based on selected category
  if (selectedCategory.value && stages[1]) {
    const category = availableCategories.find(c => c.id === selectedCategory.value)
    if (category) {
      stages[1] = {
        ...stages[1],
        label: category.label,
        emoji: category.emoji
      }
    }
  }

  return stages
})

// ============================================================================
// Computed
// ============================================================================

const configsForCategory = computed(() => {
  if (!selectedCategory.value) return []

  const categoryConfigs = configsByCategory[selectedCategory.value] || []

  // Filter out unavailable configs (Session 91+)
  if (Object.keys(modelAvailability.value).length > 0) {
    return categoryConfigs.filter(config => {
      // STRICT MODE: Only show if explicitly marked as available
      // If not in availability map or marked as false → HIDE
      // Check both the tile ID and the mapped output config ID (e.g. flux2 → flux2_diffusers)
      const mappedId = configIdToChunkName[config.id]
      return modelAvailability.value[config.id] === true
        || (mappedId && modelAvailability.value[mappedId] === true)
    })
  }

  // While loading, show all configs (avoid flicker)
  return categoryConfigs
})

const truncatedInput = computed(() => {
  if (!inputText.value) return ''
  const maxLength = 100
  return inputText.value.length > maxLength
    ? inputText.value.substring(0, maxLength) + '...'
    : inputText.value
})

const truncatedContext = computed(() => {
  if (!contextPrompt.value) return ''
  const maxLength = 100
  return contextPrompt.value.length > maxLength
    ? contextPrompt.value.substring(0, maxLength) + '...'
    : contextPrompt.value
})

const truncatedInterception = computed(() => {
  if (!interceptionResult.value) return ''
  const maxLength = 150
  return interceptionResult.value.length > maxLength
    ? interceptionResult.value.substring(0, maxLength) + '...'
    : interceptionResult.value
})

const canStartPipeline = computed(() => {
  // Phase 1: Before interception - need input and category
  if (executionPhase.value === 'initial') {
    return inputText.value && selectedCategory.value && !isInterceptionLoading.value
  }
  // Phase 2: After optimization - need both prompts and config
  else if (executionPhase.value === 'optimization_done') {
    return interceptionResult.value && optimizedPrompt.value && selectedConfig.value && !isPipelineExecuting.value
  }
  // Otherwise disabled
  return false
})

const areModelBubblesEnabled = computed(() => {
  // Enable when interception result has content (from API or manual entry)
  return interceptionResult.value.trim().length > 0
})

// Check if current output is favorited (Session 127)
const isFavorited = computed(() => {
  if (!currentRunId.value) return false
  return favoritesStore.isFavorited(currentRunId.value)
})

// Streaming computed properties
const streamingUrl = computed(() => {
  const isLoading = isInterceptionLoading.value
  console.log('[UNIFIED-STREAMING] streamingUrl computed, isInterceptionLoading:', isLoading)

  if (!isLoading) {
    console.log('[UNIFIED-STREAMING] Not loading, returning undefined')
    return undefined
  }

  // INTERCEPTION ENDPOINT - Stage 1 (Safety) + Stage 2 (Interception)
  const isDev = import.meta.env.DEV
  const url = isDev
    ? 'http://localhost:17802/api/schema/pipeline/interception'  // Dev: Direct to port 17802
    : '/api/schema/pipeline/interception'  // Prod: Relative URL via Nginx

  console.log('[INTERCEPTION-STREAMING] Base URL:', url, isDev ? '(dev - direct)' : '(prod - nginx)')
  return url
})

const streamingParams = computed(() => {
  // UNIFIED ORCHESTRATED STREAMING: All parameters for /api/schema/pipeline/execute
  const params = {
    schema: pipelineStore.selectedConfig?.id || 'user_defined',
    input_text: inputText.value,
    context_prompt: contextPrompt.value || '',
    enable_streaming: true,  // KEY: Request SSE streaming
    device_id: deviceId  // Session 129: Folder structure
  }
  console.log('[UNIFIED-STREAMING] streamingParams:', params)
  return params
})

// Session 116: LoRAs from interception config (shown early, before generation)
const configLoras = computed(() => {
  return pipelineStore.selectedConfig?.loras || []
})

// Session 139: Dynamic loading message with Wikipedia status
const interceptionLoadingMessage = computed(() => {
  const baseMessage = 'Die KI kombiniert jetzt deine Idee mit den Regeln'
  if (wikipediaStatusText.value) {
    return `${baseMessage} ... ${wikipediaStatusText.value}`
  }
  return `${baseMessage} ...`
})

// Session 116: LoRAs for Stage 4 badge (uses activeLoras if available, falls back to configLoras)
const stage4Loras = computed(() => {
  // After generation: use activeLoras (confirmed from backend)
  if (activeLoras.value.length > 0) {
    return activeLoras.value
  }
  // Before generation: use configLoras (from Phase 1 selection)
  return configLoras.value
})

// Streaming computed properties (Optimization)
// LAB ARCHITECTURE: Optimization uses dedicated /optimize endpoint (no Stage 1)
// This is an atomic service - input is already safe interception result
const optimizationStreamingUrl = computed(() => {
  const isLoading = isOptimizationLoading.value
  console.log('[OPTIMIZATION-STREAMING] optimizationStreamingUrl computed, isOptimizationLoading:', isLoading)

  if (!isLoading) {
    console.log('[OPTIMIZATION-STREAMING] Not loading, returning undefined')
    return undefined
  }

  // DEDICATED OPTIMIZE ENDPOINT - no Stage 1 safety check (input is already safe)
  const isDev = import.meta.env.DEV
  const url = isDev
    ? 'http://localhost:17802/api/schema/pipeline/optimize'
    : '/api/schema/pipeline/optimize'

  console.log('[OPTIMIZATION-STREAMING] URL:', url, isDev ? '(dev - direct)' : '(prod - nginx)')
  return url
})

const optimizationStreamingParams = computed(() => {
  // LAB ARCHITECTURE: Optimization uses /optimize endpoint
  // Input is already safe interception result, context is optimization instruction
  const params = {
    schema: pipelineStore.selectedConfig?.id || 'user_defined',
    input_text: interceptionResult.value,  // Already safe interception result
    context_prompt: optimizationInstruction.value || '',  // Model-specific optimization instruction
    enable_streaming: true,
    run_id: currentRunId.value || '',  // Session 130: For persistence
    device_id: deviceId,
    output_config: selectedConfig.value || ''  // Session 153: For model override (e.g., CODING_MODEL)
  }
  console.log('[OPTIMIZATION-STREAMING] params:', params)
  return params
})

// ============================================================================
// Route handling & Store
// ============================================================================

const route = useRoute()
const router = useRouter()
const pipelineStore = usePipelineExecutionStore()

// ============================================================================
// Lifecycle
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

  // Session persistence - restore previous input values
  const savedInput = sessionStorage.getItem('t2i_input_text')
  const savedContext = sessionStorage.getItem('t2i_context_prompt')
  const savedInterception = sessionStorage.getItem('t2i_interception_result')

  if (savedInput) {
    inputText.value = savedInput
    console.log('[T2I] Restored input from sessionStorage')
  }
  if (savedContext) {
    contextPrompt.value = savedContext
    console.log('[T2I] Restored context from sessionStorage')
  }
  if (savedInterception) {
    interceptionResult.value = savedInterception
    console.log('[T2I] Restored interception from sessionStorage')
  }

  // Check if we're coming from Phase1 with a configId
  const configId = route.params.configId as string

  if (configId) {
    console.log('[T2I] Received configId from Phase1:', configId)

    try {
      // STEP 1: Load config from backend
      await pipelineStore.setConfig(configId)
      console.log('[T2I] Config loaded:', pipelineStore.selectedConfig?.id)

      // STEP 2: Load meta-prompt for current language
      await pipelineStore.loadMetaPromptForLanguage(currentLanguage.value)
      console.log('[T2I] Meta-prompt loaded:', pipelineStore.metaPrompt?.substring(0, 50))

      // STEP 3: Overwrite ONLY context (NOT input!)
      const freshContext = pipelineStore.metaPrompt || ''
      contextPrompt.value = freshContext

      // STEP 4: Overwrite context storage for both t2i and i2i
      sessionStorage.setItem('t2i_context_prompt', freshContext)
      sessionStorage.setItem('i2i_context_prompt', freshContext)

      console.log('[T2I] Context overwritten from Phase1 config (input preserved)')

      // STEP 5: Find which category this config belongs to
      let foundCategory: string | null = null
      for (const [categoryId, configs] of Object.entries(configsByCategory)) {
        if (configs.some(config => config.id === configId)) {
          foundCategory = categoryId
          break
        }
      }

      if (foundCategory) {
        console.log('[T2I] Auto-selecting category:', foundCategory, 'and config:', configId)
        selectedCategory.value = foundCategory
        selectedConfig.value = configId
      } else {
        console.warn('[T2I] ConfigId not found in any category:', configId)
      }
    } catch (error) {
      console.error('[T2I] Initialization error:', error)
    }
  }
})

// Watch for changes and persist to sessionStorage
watch(inputText, (newVal) => {
  sessionStorage.setItem('t2i_input_text', newVal)
})

watch(contextPrompt, (newVal, oldVal) => {
  sessionStorage.setItem('t2i_context_prompt', newVal)

  // If user edits context, invalidate cached optimization
  // (optimization depends on context rules)
  if (oldVal !== '' && newVal !== oldVal && optimizedPrompt.value) {
    console.log('[T2I] User edited contextPrompt, clearing cached optimizedPrompt')
    optimizedPrompt.value = ''
    hasOptimization.value = false
  }
})

watch(interceptionResult, (newVal) => {
  sessionStorage.setItem('t2i_interception_result', newVal)
})

// Initialize editedCode when outputCode changes
watch(outputCode, (newCode) => {
  if (newCode) {
    editedCode.value = newCode
  }
})

// ============================================================================
// Textbox Actions (Copy/Paste/Delete)
// ============================================================================

function copyInputText() {
  copyToClipboard(inputText.value)
  console.log('[T2I] Input text copied to app clipboard')
}

function pasteInputText() {
  inputText.value = pasteFromClipboard()
  console.log('[T2I] Text pasted from app clipboard into input')
}

function clearInputText() {
  inputText.value = ''
  sessionStorage.removeItem('t2i_input_text')
  console.log('[T2I] Input text cleared')
}

function copyContextPrompt() {
  copyToClipboard(contextPrompt.value)
  console.log('[T2I] Context prompt copied to app clipboard')
}

function pasteContextPrompt() {
  contextPrompt.value = pasteFromClipboard()
  console.log('[T2I] Text pasted from app clipboard into context')
}

function clearContextPrompt() {
  contextPrompt.value = ''
  sessionStorage.removeItem('t2i_context_prompt')
  console.log('[T2I] Context prompt cleared')
}

function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  contextPrompt.value = payload.context
  sessionStorage.setItem('t2i_context_prompt', payload.context)
  console.log(`[T2I] Preset selected: ${payload.configName} (${payload.configId})`)
}

function copyInterceptionResult() {
  copyToClipboard(interceptionResult.value)
  console.log('[T2I] Interception result copied to app clipboard')
}

function pasteInterceptionResult() {
  interceptionResult.value = pasteFromClipboard()
  console.log('[T2I] Text pasted from app clipboard into interception result')
}

function clearInterceptionResult() {
  interceptionResult.value = ''
  sessionStorage.removeItem('t2i_interception_result')
  console.log('[T2I] Interception result cleared')
}

function copyOptimizedPrompt() {
  copyToClipboard(optimizedPrompt.value)
  console.log('[T2I] Optimized prompt copied to app clipboard')
}

function pasteOptimizedPrompt() {
  optimizedPrompt.value = pasteFromClipboard()
  console.log('[T2I] Text pasted from app clipboard into optimized prompt')
}

function clearOptimizedPrompt() {
  optimizedPrompt.value = ''
  console.log('[T2I] Optimized prompt cleared')
}

function runCode() {
  if (!editedCode.value) {
    console.warn('[T2I] No code to run')
    return
  }
  // Force iframe re-render by incrementing key
  iframeKey.value++
  console.log('[T2I] Running code, iframe key:', iframeKey.value)
}

// ============================================================================
// Methods
// ============================================================================

// Helper: Only scroll DOWN, never back up
function scrollDownOnly(element: HTMLElement | null, block: ScrollLogicalPosition = 'start') {
  if (!element) return
  const rect = element.getBoundingClientRect()
  const targetTop = block === 'start' ? rect.top : rect.bottom - window.innerHeight
  // Only scroll if target is below current viewport
  if (targetTop > 0) {
    element.scrollIntoView({ behavior: 'smooth', block })
  }
}

function scrollToBottomOnly() {
  // Scroll the window (container no longer has overflow)
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

// Session 116: Format LoRA filename for display
function formatLoraName(filename: string): string {
  // "sd3.5-large_cooked_negatives.safetensors" → "Cooked Negatives"
  return filename
    .replace(/\.safetensors$/, '')
    .replace(/^sd3\.5-large_/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

async function selectCategory(categoryId: string) {
  selectedCategory.value = categoryId
  selectedConfig.value = null
  // Don't clear interception or optimization results when changing category

  // Scroll2: Category bubbles at top, model selection + prompt/start2 visible below
  await nextTick()
  scrollDownOnly(categorySectionRef.value, 'start')
}

async function selectConfig(configId: string) {
  // Only allow selection after interception is done
  if (!areModelBubblesEnabled.value || isOptimizationLoading.value) return

  // ALWAYS set selectedConfig (even if same) to trigger optimization
  selectedConfig.value = configId

  // Skip optimization if no interception result (direct execution mode)
  if (!interceptionResult.value || interceptionResult.value.trim() === '') {
    optimizedPrompt.value = inputText.value  // Use original input directly
    hasOptimization.value = false
    executionPhase.value = 'optimization_done'
    console.log('[Direct Mode] Skipping optimization, using input text directly')
    return
  }

  // ALWAYS trigger optimization when model is clicked (even if already selected)
  console.log('[SelectConfig] Triggering optimization for:', configId)
  await runOptimization()
}

async function runInterception() {
  // STREAMING MODE: Just set loading state
  // MediaInputBox will automatically connect to streaming endpoint
  // when streamingUrl becomes active (computed property)

  console.log('[Streaming] Starting interception with streaming mode')
  console.log('[DEBUG] Before - isInterceptionLoading:', isInterceptionLoading.value)
  console.log('[DEBUG] Input text:', inputText.value?.substring(0, 50), '...')
  console.log('[DEBUG] Context prompt:', contextPrompt.value?.substring(0, 50), '...')
  console.log('[DEBUG] Meta prompt:', pipelineStore.metaPrompt?.substring(0, 50), '...')

  interceptionResult.value = '' // Clear previous result
  // Session 130: Reset output flag (new interception = new run)
  currentRunHasOutput.value = false
  // Session 139: Reset Wikipedia data completely at start of new run
  wikipediaData.value = { active: false, terms: [] }
  wikipediaExpanded.value = false
  wikipediaStatusText.value = ''

  // CRITICAL FIX: Wait for Vue to process all pending reactive updates
  // before setting isInterceptionLoading, which triggers the streaming chain
  await nextTick()

  isInterceptionLoading.value = true

  console.log('[DEBUG] After - isInterceptionLoading:', isInterceptionLoading.value)
  console.log('[DEBUG] This should trigger streamingUrl computed property')

  // Note: isInterceptionLoading will be set to false by handleStreamComplete()
  // or handleStreamError() when streaming finishes
}

async function runOptimization() {
  try {
    console.log('[Streaming] Starting optimization with streaming mode')
    console.log('[DEBUG] Before - isOptimizationLoading:', isOptimizationLoading.value)
    console.log('[DEBUG] Input text:', interceptionResult.value?.substring(0, 50), '...')
    console.log('[DEBUG] Selected config:', selectedConfig.value)

    // STEP 1: Load metadata first (optimization_instruction only)
    const metaResponse = await axios.get(
      `/api/schema/pipeline/optimize/meta/${selectedConfig.value}`
    )
    optimizationInstruction.value = metaResponse.data.optimization_instruction || ''

    console.log('[Optimize] Loaded optimization_instruction:', optimizationInstruction.value.substring(0, 100))

    // Check if optimization is actually needed FIRST
    if (!optimizationInstruction.value || optimizationInstruction.value.trim() === '') {
      console.log('[Optimize] No optimization instruction found, skipping optimization phase')
      optimizedPrompt.value = interceptionResult.value  // Use interception result directly
      hasOptimization.value = false
      executionPhase.value = 'optimization_done'
      return  // Exit early - don't set duration, don't trigger streaming!
    }

    // Only set duration if we're actually going to optimize
    estimatedDurationSeconds.value = metaResponse.data.estimated_duration_seconds || '30'
    console.log('[Optimize] Estimated duration:', estimatedDurationSeconds.value)

    // STEP 2: Start streaming (clear previous result and set loading state)
    // (Only reached if optimization_instruction is NOT empty)
    optimizedPrompt.value = ''  // Clear previous result

    // CRITICAL FIX: Wait for Vue to process all pending reactive updates
    // before setting isOptimizationLoading, which triggers the streaming chain
    await nextTick()

    isOptimizationLoading.value = true

    console.log('[DEBUG] After - isOptimizationLoading:', isOptimizationLoading.value)
    console.log('[DEBUG] This should trigger optimizationStreamingUrl computed property')

    // Note: isOptimizationLoading will be set to false by handleOptimizationStreamComplete()
    // or handleOptimizationStreamError() when streaming finishes

  } catch (error: any) {
    console.error('[Optimize] Error loading metadata:', error)
    const errorMessage = error.response?.data?.error || error.message
    alert(`Fehler beim Laden der Optimization-Metadaten: ${errorMessage}`)
    isOptimizationLoading.value = false
  }
}

// Streaming event handlers
function handleStreamStarted() {
  console.log('[Stream] First chunk received, hiding spinner')
  isInterceptionLoading.value = false  // Hide spinner, show typewriter effect

  // Track which interception config was used (for generation context)
  lastInterceptionConfig.value = pipelineStore.selectedConfig?.id || 'user_defined'
  console.log('[Stream] Saved interception config:', lastInterceptionConfig.value)
}

function handleStreamComplete(data: any) {
  console.log('[Stream] Complete:', data)
  executionPhase.value = 'interception_done'

  // Save run_id for unified export (used by /generation)
  if (data.run_id) {
    currentRunId.value = data.run_id
    console.log('[Stream] Saved run_id for export:', data.run_id)
  }

  // Scroll to category section (existing behavior)
  nextTick().then(() => {
    scrollDownOnly(categorySectionRef.value, 'end')
  })
}

function handleStreamError(error: string) {
  console.error('[Stream] Error:', error)
  isInterceptionLoading.value = false
  alert('Streaming-Fehler. Bitte erneut versuchen.')
}

// Session 139: Wikipedia lookup event handler
// Session 136: terms now include REAL Wikipedia results (title, url)
function handleWikipediaLookup(data: { status: string; terms: Array<{ term: string; lang: string; title: string; url: string; success: boolean }> }) {
  console.log('[Wikipedia] Lookup event:', data.status, data.terms)

  if (data.status === 'start') {
    wikipediaData.value.active = true
    // KEINE terms bei start - sie haben leere URLs!
    wikipediaStatusText.value = '(Wikipedia-Recherche läuft...)'
  } else if (data.status === 'complete') {
    wikipediaData.value.active = false
    // Bei complete: Backend hat schon mit r.success gefiltert
    if (data.terms && data.terms.length > 0) {
      wikipediaData.value.terms = [...wikipediaData.value.terms, ...data.terms]
    }
    const successCount = wikipediaData.value.terms.length
    wikipediaStatusText.value = successCount > 0
      ? `(Wikipedia: ${successCount} Artikel gefunden)`
      : ''
    // Debug: Log actual URLs
    console.log('[Wikipedia] Articles found:')
    wikipediaData.value.terms.forEach(t => {
      console.log(`  - ${t.lang}: ${t.title} -> ${t.url}`)
    })
  }
}

// Streaming event handlers (Optimization)
function handleOptimizationStreamStarted() {
  console.log('[Optimization Stream] First chunk received, hiding spinner')
  isOptimizationLoading.value = false  // Hide spinner, show typewriter effect
}

function handleOptimizationStreamComplete(data: any) {
  console.log('[Optimization Stream] Complete:', data)
  hasOptimization.value = true
  executionPhase.value = 'optimization_done'

  // Extract and display code if optimization result is JavaScript (content-based detection)
  if (optimizedPrompt.value && (
      optimizedPrompt.value.includes('```javascript') ||
      optimizedPrompt.value.includes('function setup(') ||
      optimizedPrompt.value.includes('function draw(')
  )) {
    // Clean markdown wrappers
    let code = optimizedPrompt.value
    code = code.replace(/```javascript\n?/g, '')
               .replace(/```js\n?/g, '')
               .replace(/```\n?/g, '')
               .trim()
    outputCode.value = code
    outputMediaType.value = 'code'
    console.log('[Stage2-Code] Code detected and displayed, length:', code.length)
  }

  console.log('[Optimize] Complete:', optimizedPrompt.value.substring(0, 60), '| Applied:', hasOptimization.value)
}

function handleOptimizationStreamError(error: string) {
  console.error('[Optimization Stream] Error:', error)
  isOptimizationLoading.value = false
  alert('Optimization-Streaming-Fehler. Bitte erneut versuchen.')
}

async function startGeneration() {
  // Check if model is selected
  if (!selectedConfig.value) {
    alert('Bitte wähle ein Modell aus')
    return
  }

  // Pre-generation safety check on the prompt that will be sent to Stage 3-4.
  // MediaInputBox checks on blur/paste, but if the user edits the optimized prompt
  // and clicks Generate without blurring, the check wouldn't have fired.
  const finalPrompt = optimizedPrompt.value || interceptionResult.value || inputText.value
  if (finalPrompt?.trim()) {
    try {
      const baseUrl = import.meta.env.DEV ? 'http://localhost:17802' : ''
      const res = await fetch(`${baseUrl}/api/schema/pipeline/safety/quick`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: finalPrompt.trim(), user_language: locale.value })
      })
      const data = await res.json()
      if (!data.safe) {
        safetyStore.reportBlock(1, data.error_message || t('mediaInput.contentBlocked'), [])
        return
      }
    } catch {
      // Network error → fail-open, let Stage 3 backend handle it
    }
  }

  isPipelineExecuting.value = true

  // Scroll3: Show animation/output box fully
  await nextTick()
  setTimeout(() => scrollDownOnly(pipelineSectionRef.value?.sectionRef, 'start'), 150)

  // Start pipeline execution (Stage 3-4)
  await executePipeline()
}

async function executePipeline() {
  // Reset UI state for fresh generation
  outputImage.value = ''  // Clear previous image
  outputCode.value = null  // Clear previous code
  outputMeshUrl.value = null  // Clear previous 3D mesh
  outputThumbnailUrl.value = null  // Clear previous 3D thumbnail
  outputMediaType.value = 'image'  // Reset to default media type
  resetGenerationStream()  // Session 148: Reset badges via composable
  generationErrorMessage.value = ''
  activeLoras.value = []  // Session 116: Reset LoRAs
  loraExpanded.value = false
  // Session 139: Don't reset Wikipedia terms - badge stays persistent during generation
  wikipediaExpanded.value = false

  // Phase 4: Intelligent seed logic
  // Track both prompt AND model — only randomize seed when NEITHER changed (user wants variation)
  const currentPromptToUse = optimizedPrompt.value || interceptionResult.value || inputText.value
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
    const finalPrompt = optimizedPrompt.value || interceptionResult.value || inputText.value

    console.log('[GENERATION-STREAM] === PROMPT SELECTION ===')
    console.log('[GENERATION-STREAM] SELECTED finalPrompt:', finalPrompt?.substring(0, 100) + '...')
    console.log('[GENERATION-STREAM] currentSeed:', currentSeed.value)

    // Session 148: Use SSE streaming for real-time badge updates
    const result = await executeWithStreaming({
      prompt: finalPrompt,
      output_config: selectedConfig.value || '',
      seed: currentSeed.value,
      run_id: currentRunId.value || undefined,
      input_text: inputText.value,
      context_prompt: contextPrompt.value,
      interception_result: interceptionResult.value,
      interception_config: lastInterceptionConfig.value || pipelineStore.selectedConfig?.id,
      device_id: deviceId
    })

    console.log('[GENERATION-STREAM] Result:', result)

    if (result.status === 'success' && result.media_output) {
      // Session 116: Extract LoRAs from response
      if (result.loras) {
        activeLoras.value = result.loras
      }

      const runId = result.media_output.run_id || result.run_id
      const mediaType = result.media_output.media_type || 'image'
      const mediaIndex = result.media_output.index ?? 0

      if (runId) {
        currentRunId.value = runId
        currentRunHasOutput.value = true

        outputMediaType.value = mediaType
        executionPhase.value = 'generation_done'

        if (mediaType === 'code' && result.media_output.code) {
          // Code output (Tone.js, p5.js): display in code editor, not MediaOutputBox
          outputCode.value = result.media_output.code
        } else if (mediaType === '3d') {
          // 3D model: set mesh URL for <model-viewer>, use thumbnail as fallback image
          const meshUrl = result.media_output.mesh_url || result.media_output.url
          const apiPrefix = import.meta.env.DEV ? `http://localhost:17802` : ''
          outputMeshUrl.value = `${apiPrefix}${meshUrl}`
          if (result.media_output.thumbnail_url) {
            outputThumbnailUrl.value = `${apiPrefix}${result.media_output.thumbnail_url}`
          }
          // outputImage is set so MediaOutputBox shows the final output section
          outputImage.value = outputMeshUrl.value
        } else {
          outputImage.value = `/api/media/${mediaType}/${runId}/${mediaIndex}`
        }

        // Session 82: Register session for chat overlay context
        updateSession(runId, {
          mediaType,
          configName: selectedConfig.value || 'unknown'
        })

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
    console.error('Pipeline error:', error)

    generationProgress.value = 0
    generationErrorMessage.value = t('generationError.unknown')
    isPipelineExecuting.value = false
    outputImage.value = null
    outputCode.value = null
  } finally {
    isPipelineExecuting.value = false
  }
}

// Generate iframe content for p5.js code display
function getP5jsIframeContent(): string {
  const codeToRender = editedCode.value || outputCode.value
  if (!codeToRender) return ''

  return `<!DOCTYPE html>
<html>
<head>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.7.0/p5.min.js"><\/script>
    <style>
        body {
            margin: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background: #f7fafc;
        }
        canvas {
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
    <script>
        try {
            ${codeToRender}
        } catch (error) {
            document.body.innerHTML = '<div style="color: red; padding: 20px; font-family: monospace;">Error: ' + error.message + '<\/div>';
            console.error('p5.js error:', error);
        }
    <\/script>
</body>
</html>`
}

// Generate iframe content for Tone.js audio playback
function getToneJsIframeContent(): string {
  const codeToRender = editedCode.value || outputCode.value
  if (!codeToRender) return ''

  return `<!DOCTYPE html>
<html>
<head>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tone/14.8.49/Tone.js"><\/script>
    <style>
        body {
            margin: 0;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: white;
        }
        .controls {
            display: flex;
            gap: 16px;
            margin-bottom: 20px;
        }
        button {
            padding: 16px 32px;
            font-size: 18px;
            border: none;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 600;
        }
        .play-btn {
            background: linear-gradient(135deg, #FF4081 0%, #FF6EC4 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(255, 64, 129, 0.4);
        }
        .play-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 6px 20px rgba(255, 64, 129, 0.6);
        }
        .play-btn:active {
            transform: scale(0.98);
        }
        .stop-btn {
            background: linear-gradient(135deg, #424242 0%, #616161 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        }
        .stop-btn:hover {
            transform: scale(1.05);
        }
        .status {
            font-size: 14px;
            color: #b0b0b0;
            margin-top: 10px;
        }
        .status.playing {
            color: #FF4081;
        }
        .visualizer {
            width: 200px;
            height: 60px;
            display: flex;
            align-items: flex-end;
            justify-content: center;
            gap: 4px;
            margin-top: 20px;
        }
        .bar {
            width: 8px;
            background: linear-gradient(180deg, #FF4081 0%, #FF6EC4 100%);
            border-radius: 4px;
            transition: height 0.1s ease;
        }
        .error {
            color: #ff6b6b;
            padding: 20px;
            font-family: monospace;
            background: rgba(255, 107, 107, 0.1);
            border-radius: 8px;
            max-width: 80%;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="controls">
        <button class="play-btn" id="playBtn">▶️ Play</button>
        <button class="stop-btn" id="stopBtn">⏹️ Stop</button>
    </div>
    <div class="status" id="status">Klicke Play um die Musik zu starten</div>
    <div class="visualizer" id="visualizer">
        <div class="bar" style="height: 20px"></div>
        <div class="bar" style="height: 30px"></div>
        <div class="bar" style="height: 25px"></div>
        <div class="bar" style="height: 40px"></div>
        <div class="bar" style="height: 35px"></div>
        <div class="bar" style="height: 28px"></div>
        <div class="bar" style="height: 32px"></div>
    </div>
    <script>
        let isPlaying = false;
        let visualizerInterval = null;
        const bars = document.querySelectorAll('.bar');

        function updateVisualizer() {
            bars.forEach(bar => {
                const height = Math.random() * 50 + 10;
                bar.style.height = height + 'px';
            });
        }

        function startVisualizer() {
            visualizerInterval = setInterval(updateVisualizer, 100);
        }

        function stopVisualizer() {
            clearInterval(visualizerInterval);
            bars.forEach(bar => bar.style.height = '20px');
        }

        document.getElementById('playBtn').onclick = async () => {
            if (isPlaying) return;

            try {
                await Tone.start();
                document.getElementById('status').textContent = '🎵 Musik spielt...';
                document.getElementById('status').classList.add('playing');
                isPlaying = true;
                startVisualizer();

                // Execute generated code
                ${codeToRender}
            } catch (error) {
                document.getElementById('status').textContent = '❌ Fehler: ' + error.message;
                console.error('Tone.js error:', error);
            }
        };

        document.getElementById('stopBtn').onclick = () => {
            Tone.Transport.stop();
            Tone.Transport.cancel();

            // Dispose all scheduled events
            Tone.Transport.position = 0;

            document.getElementById('status').textContent = '⏹️ Gestoppt';
            document.getElementById('status').classList.remove('playing');
            isPlaying = false;
            stopVisualizer();
        };
    <\/script>
</body>
</html>`
}

function showImageFullscreen(imageUrl: string) {
  fullscreenImage.value = imageUrl
}

// ============================================================================
// Media Actions (Universal for all media types)
// ============================================================================

function saveMedia() {
  // TODO: Implement save/bookmark feature for all media types
  console.log('[Media Actions] Save media (not yet implemented):', outputMediaType.value)
  alert('Merken-Funktion kommt bald!')
}

async function toggleFavorite() {
  if (!currentRunId.value) {
    console.warn('[Media Actions] No current run_id to favorite')
    return
  }

  // Convert outputMediaType to the correct type for favorites
  const mediaType = outputMediaType.value as 'image' | 'video' | 'audio' | 'music'
  await favoritesStore.toggleFavorite(currentRunId.value, mediaType, deviceId, 'anonymous', 'text-transformation')
  console.log('[Media Actions] Favorite toggled for run_id:', currentRunId.value)
}

function printImage() {
  if (!outputImage.value) return

  // Open image in new window and print
  const printWindow = window.open(outputImage.value, '_blank')
  if (printWindow) {
    printWindow.onload = () => {
      printWindow.print()
    }
  }
}

// Session 130: Log prompt changes to prompting_process/ folder
// Called on blur of any text input box
async function logPromptChange(entityType: string, content: string) {
  if (!currentRunId.value) {
    console.log('[LOG-PROMPT] No current run_id, skipping')
    return
  }

  // Session 130: Don't log changes after media generation (run is complete)
  if (currentRunHasOutput.value) {
    console.log('[LOG-PROMPT] Run already has output, skipping (start new interception for new run)')
    return
  }

  if (!content || content.trim() === '') {
    console.log('[LOG-PROMPT] Empty content, skipping')
    return
  }

  try {
    const response = await fetch('/api/schema/pipeline/log-prompt-change', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        run_id: currentRunId.value,
        entity_type: entityType,
        content: content,
        device_id: deviceId
      })
    })

    if (response.ok) {
      const data = await response.json()
      console.log(`[LOG-PROMPT] Saved ${entityType} change:`, data.filename)
    }
  } catch (error) {
    console.warn('[LOG-PROMPT] Failed to log change:', error)
    // Don't show error to user - this is background logging
  }
}

function sendToI2I() {
  if (!outputImage.value || outputMediaType.value !== 'image') return

  // Extract run_id from URL: /api/media/image/run_123 -> run_123
  const runIdMatch = outputImage.value.match(/\/api\/media\/image\/(.+)$/)
  const runId = runIdMatch ? runIdMatch[1] : null

  // Store image data in localStorage for cross-component transfer
  const transferData = {
    imageUrl: outputImage.value,  // For display
    runId: runId,  // For backend reference
    timestamp: Date.now()
  }

  localStorage.setItem('i2i_transfer_data', JSON.stringify(transferData))

  console.log('[Image Actions] Transferring to i2i:', transferData)

  // Navigate to image transformation
  router.push('/image-transformation')
}

async function downloadMedia() {
  if (!outputImage.value || !outputMediaType.value) return

  try {
    // Extract run_id from URL: /api/media/{type}/{run_id}
    const runIdMatch = outputImage.value.match(/\/api\/media\/\w+\/(.+)$/)
    const runId = runIdMatch ? runIdMatch[1] : 'media'

    // Determine file extension based on media type
    const extensions: Record<string, string> = {
      'image': 'png',
      'audio': 'mp3',
      'video': 'mp4',
      'music': 'mp3',
      'code': 'js',
      '3d': 'glb'
    }
    const ext = extensions[outputMediaType.value] || 'bin'
    const filename = `ai4artsed_${runId}.${ext}`

    // Special handling for code output (Blob from variable, not URL)
    if (outputMediaType.value === 'code' && outputCode.value) {
      const blob = new Blob([outputCode.value], { type: 'text/javascript' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      link.click()
      URL.revokeObjectURL(url)
      console.log('[Download] Code downloaded:', filename)
      return
    }

    // For binary media: Fetch and download
    const response = await fetch(outputImage.value)
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

// ============================================================================
// Stage 5: Image Analysis (Pedagogical Reflection)
// ============================================================================

const isAnalyzing = ref(false)
const imageAnalysis = ref<{
  analysis: string
  reflection_prompts: string[]
  insights: string[]
  success: boolean
} | null>(null)
const showAnalysis = ref(false)

async function analyzeImage() {
  if (!outputImage.value || outputMediaType.value !== 'image') {
    console.warn('[Stage 5] Can only analyze images')
    return
  }

  // Extract run_id from URL: /api/media/image/run_abc123
  const runIdMatch = outputImage.value.match(/\/api\/media\/image\/(.+)$/)
  const runId = runIdMatch ? runIdMatch[1] : null

  if (!runId) {
    alert('Error: Cannot determine image ID')
    return
  }

  isAnalyzing.value = true
  imageAnalysis.value = null
  console.log('[Stage 5] Starting image analysis for run_id:', runId)

  try {
    // NEW: Call universal image analysis endpoint
    const response = await fetch('/api/image/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        run_id: runId,
        analysis_type: 'bildwissenschaftlich'  // Default: Panofsky framework
        // Can be changed to: bildungstheoretisch, ethisch, kritisch
        // No prompt parameter = uses default from config.py
      })
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || `HTTP ${response.status}`)
    }

    const data = await response.json()

    if (data.success && data.analysis) {
      // Parse analysis text into structured format
      imageAnalysis.value = {
        analysis: data.analysis,
        reflection_prompts: extractReflectionPrompts(data.analysis),
        insights: extractInsights(data.analysis),
        success: true
      }
      showAnalysis.value = true
      console.log('[Stage 5] Analysis complete')
    } else {
      throw new Error(data.error || 'Unknown error')
    }

  } catch (error: any) {
    console.error('[Stage 5] Error:', error)
    alert(`Image analysis failed: ${error.message || error}`)
  } finally {
    isAnalyzing.value = false
  }
}

// Helper functions for parsing analysis text
function extractReflectionPrompts(analysisText: string): string[] {
  const match = analysisText.match(/REFLEXIONSFRAGEN:|REFLECTION QUESTIONS:([\s\S]*?)(?:\n\n|$)/i)
  if (match && match[1]) {
    return match[1]
      .split('\n')
      .filter(line => line.trim().startsWith('-'))
      .map(line => line.replace(/^-\s*/, '').trim())
      .filter(q => q.length > 0)
  }
  return []
}

function extractInsights(analysisText: string): string[] {
  const keywords = ['Komposition', 'Farbe', 'Licht', 'Perspektive', 'Stil',
                   'Composition', 'Color', 'Light', 'Perspective', 'Style']
  return keywords.filter(kw =>
    analysisText.toLowerCase().includes(kw.toLowerCase())
  )
}


// Watch metaPrompt changes and sync to local state
watch(() => pipelineStore.metaPrompt, (newMetaPrompt) => {
  if (newMetaPrompt !== contextPrompt.value) {
    contextPrompt.value = newMetaPrompt || ''
    console.log('[Youth Flow] Meta-prompt synced from store')
  }
})

// Watch contextPrompt changes and update store
watch(contextPrompt, (newValue) => {
  pipelineStore.updateMetaPrompt(newValue)
  console.log('[Youth Flow] Context prompt edited:', newValue.substring(0, 50) + '...')
})

// Auto-advance phase when manual text is entered
// Also clear optimizedPrompt when user manually edits interceptionResult
watch(interceptionResult, (newValue, oldValue) => {
  if (newValue.trim().length > 0 && executionPhase.value === 'initial') {
    executionPhase.value = 'interception_done'
  }

  // If user manually edits (not during streaming), invalidate cached optimizedPrompt
  // so that generation uses the fresh edited value
  if (!isInterceptionLoading.value && oldValue !== '' && newValue !== oldValue) {
    if (optimizedPrompt.value) {
      console.log('[T2I] User edited interceptionResult, clearing cached optimizedPrompt')
      optimizedPrompt.value = ''
      hasOptimization.value = false
    }
    // Reset prompt comparison baseline so next generation recognizes the change
    previousOptimizedPrompt.value = ''
    console.log('[T2I] User edited interceptionResult, reset prompt baseline')
  }
})

// Restore from favorites (reactive, works even if already on page)
watch(() => favoritesStore.pendingRestoreData, (restoreData) => {
  if (!restoreData) return

  console.log('[T2I Restore] Processing:', Object.keys(restoreData))

  // Sequential copy/paste per JSON field
  if (restoreData.input_text) {
    copyToClipboard(restoreData.input_text)
    inputText.value = pasteFromClipboard()
  }
  if (restoreData.context_prompt) {
    copyToClipboard(restoreData.context_prompt)
    contextPrompt.value = pasteFromClipboard()
  }
  if (restoreData.transformed_text) {
    copyToClipboard(restoreData.transformed_text)
    interceptionResult.value = pasteFromClipboard()
  }

  // Clear after processing
  favoritesStore.setRestoreData(null)
}, { immediate: true })
</script>

<style>
/* GLOBAL unscoped - force MediaInputBox width in single-column sections */
.text-transformation-view .interception-section .media-input-box,
.text-transformation-view .optimization-section .media-input-box {
  width: 100% !important;
  max-width: 1000px !important;
}

/* Force INPUT boxes (side-by-side) to have proper width */
.text-transformation-view .input-context-section .media-input-box {
  flex: 0 1 480px !important;
  width: 100% !important;
  max-width: 480px !important;
}

/* Media Category Icons */
.bubble-emoji-small {
  display: flex;
  align-items: center;
  justify-content: center;
}

.bubble-emoji-small svg {
  width: 32px;
  height: 32px;
}
</style>
