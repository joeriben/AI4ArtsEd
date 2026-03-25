<template>
  <section class="pipeline-section" ref="sectionRef">
    <!-- Output Frame (Always visible) -->
    <div class="output-frame" :class="{ empty: !isExecuting && !outputImage && !meshUrl, generating: isExecuting && !outputImage && !meshUrl }">
      <!-- Generation Progress Animation -->
      <div v-if="isExecuting && !outputImage" class="generation-animation-container">
        <!-- Expert mode: Full denoising view with model Steckbrief -->
        <DenoisingProgressView
          v-if="uiMode === 'expert'"
          :progress="progress"
          :preview-image="previewImage"
          :model-meta="modelMeta"
          :estimated-seconds="estimatedSeconds"
          @stats-snapshot="handleStatsSnapshot"
        />
        <!-- Kids/Youth mode: Edutainment games with small preview overlay -->
        <template v-else>
          <RandomEdutainmentAnimation :progress="progress" :estimated-seconds="estimatedSeconds" />
          <Transition name="fade">
            <img v-if="previewImage" :src="previewImage" alt="" class="denoising-preview" />
          </Transition>
        </template>
      </div>

      <!-- Empty State with inactive Actions -->
      <div v-else-if="!outputImage" class="empty-with-actions">
        <!-- Action Toolbar (inactive) -->
        <div class="action-toolbar inactive">
          <button class="action-btn" disabled title="Merken (Coming Soon)">
            <span class="action-icon">
              <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                <path d="M440-501Zm0 381L313-234q-72-65-123.5-116t-85-96q-33.5-45-49-87T40-621q0-94 63-156.5T260-840q52 0 99 22t81 62q34-40 81-62t99-22q81 0 136 45.5T831-680h-85q-18-40-53-60t-73-20q-51 0-88 27.5T463-660h-46q-31-45-70.5-72.5T260-760q-57 0-98.5 39.5T120-621q0 33 14 67t50 78.5q36 44.5 98 104T440-228q26-23 61-53t56-50l9 9 19.5 19.5L605-283l9 9q-22 20-56 49.5T498-172l-58 52Zm280-160v-120H600v-80h120v-120h80v120h120v80H800v120h-80Z"/>
              </svg>
            </span>
          </button>
          <button class="action-btn" disabled :title="forwardButtonTitle">
            <span class="action-icon">
              <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                <path d="M480-480ZM200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h320v80H200v560h560v-280h80v280q0 33-23.5 56.5T760-120H200Zm40-160h480L570-480 450-320l-90-120-120 160Zm480-280v-167l-64 63-56-56 160-160 160 160-56 56-64-63v167h-80Z"/>
              </svg>
            </span>
          </button>
          <button class="action-btn" disabled title="Herunterladen">
            <span class="action-icon">
              <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                <path d="M480-320 280-520l56-58 104 104v-326h80v326l104-104 56 58-200 200ZM240-160q-33 0-56.5-23.5T160-240v-120h80v120h480v-120h80v120q0 33-23.5 56.5T720-160H240Z"/>
              </svg>
            </span>
          </button>
          <button class="action-btn" disabled title="Drucken">
            <span class="action-icon">
              <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                <path d="M640-640v-120H320v120h-80v-200h480v200h-80Zm-480 80h640-640Zm560 100q17 0 28.5-11.5T760-500q0-17-11.5-28.5T720-540q-17 0-28.5 11.5T680-500q0 17 11.5 28.5T720-460Zm-80 260v-160H320v160h320Zm80 80H240v-160H80v-240q0-51 35-85.5t85-34.5h560q51 0 85.5 34.5T880-520v240H720v160Zm80-240v-160q0-17-11.5-28.5T760-560H200q-17 0-28.5 11.5T160-520v160h80v-80h480v80h80Z"/>
              </svg>
            </span>
          </button>
          <button class="action-btn" disabled title="Bildanalyse">
            <span class="action-icon">
              <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                <path d="M440-240q116 0 198-81.5T720-520q0-116-82-198t-198-82q-117 0-198.5 82T160-520q0 117 81.5 198.5T440-240Zm0-280Zm0 160q-83 0-147.5-44.5T200-520q28-70 92.5-115T440-680q82 0 146.5 45T680-520q-29 71-93.5 115.5T440-360Zm0-60q55 0 101-26.5t72-73.5q-26-46-72-73t-101-27q-56 0-102 27t-72 73q26 47 72 73.5T440-420Zm0-40q25 0 42.5-17t17.5-43q0-25-17.5-42.5T440-580q-26 0-43 17.5T380-520q0 26 17 43t43 17Zm0 300q-75 0-140.5-28.5t-114-77q-48.5-48.5-77-114T80-520q0-74 28.5-139.5t77-114.5q48.5-49 114-77.5T440-880q74 0 139.5 28.5T694-774q49 49 77.5 114.5T800-520q0 64-21 121t-58 104l159 159-57 56-159-158q-47 37-104 57.5T440-160Z"/>
              </svg>
            </span>
          </button>
        </div>
      </div>

      <!-- Final Output -->
      <div v-else-if="outputImage || meshUrl" class="final-output">
        <!-- Image with Actions -->
        <div v-if="mediaType === 'image'" class="image-with-actions">
          <img
            :src="outputImage"
            alt="Generiertes Bild"
            class="output-image"
            @click="$emit('image-click', outputImage)"
          />

          <!-- Action Toolbar (vertical, right side — inline style bypasses scoped CSS specificity) -->
          <div class="action-toolbar" style="position: absolute; right: 8px; top: 50%; transform: translateY(-50%); z-index: 10;">
            <button
              class="action-btn"
              :class="{ 'favorited': isFavorited }"
              @click="$emit('toggle-favorite')"
              :disabled="!runId"
              :title="isFavorited ? $t('gallery.unfavorite') : $t('gallery.favorite')"
            >
              <span class="action-icon">
                <!-- Filled heart when favorited -->
                <svg v-if="isFavorited" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="m480-120-58-52q-101-91-167-157T150-447.5Q111-500 95.5-544T80-634q0-94 63-157t157-63q52 0 99 22t81 62q34-40 81-62t99-22q94 0 157 63t63 157q0 46-15.5 90T810-447.5Q771-395 705-329T538-172l-58 52Z"/>
                </svg>
                <!-- Outline heart when not favorited -->
                <svg v-else xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="m480-120-58-52q-101-91-167-157T150-447.5Q111-500 95.5-544T80-634q0-94 63-157t157-63q52 0 99 22t81 62q34-40 81-62t99-22q94 0 157 63t63 157q0 46-15.5 90T810-447.5Q771-395 705-329T538-172l-58 52Zm0-108q96-86 158-147.5t98-107q36-45.5 50-81t14-70.5q0-60-40-100t-100-40q-47 0-87 26.5T518-680h-76q-15-41-55-67.5T300-774q-60 0-100 40t-40 100q0 35 14 70.5t50 81q36 45.5 98 107T480-228Zm0-273Z"/>
                </svg>
              </span>
            </button>
            <button class="action-btn" @click="$emit('forward')" :title="forwardButtonTitle">
              <span class="action-icon">
                <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="M480-480ZM200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h320v80H200v560h560v-280h80v280q0 33-23.5 56.5T760-120H200Zm40-160h480L570-480 450-320l-90-120-120 160Zm480-280v-167l-64 63-56-56 160-160 160 160-56 56-64-63v167h-80Z"/>
                </svg>
              </span>
            </button>
            <button class="action-btn" @click="$emit('download')" title="Herunterladen">
              <span class="action-icon">
                <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="M480-320 280-520l56-58 104 104v-326h80v326l104-104 56 58-200 200ZM240-160q-33 0-56.5-23.5T160-240v-120h80v120h480v-120h80v120q0 33-23.5 56.5T720-160H240Z"/>
                </svg>
              </span>
            </button>
            <button class="action-btn" @click="$emit('print')" title="Drucken">
              <span class="action-icon">
                <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="M640-640v-120H320v120h-80v-200h480v200h-80Zm-480 80h640-640Zm560 100q17 0 28.5-11.5T760-500q0-17-11.5-28.5T720-540q-17 0-28.5 11.5T680-500q0 17 11.5 28.5T720-460Zm-80 260v-160H320v160h320Zm80 80H240v-160H80v-240q0-51 35-85.5t85-34.5h560q51 0 85.5 34.5T880-520v240H720v160Zm80-240v-160q0-17-11.5-28.5T760-560H200q-17 0-28.5 11.5T160-520v160h80v-80h480v80h80Z"/>
                </svg>
              </span>
            </button>
            <button class="action-btn" @click="triggerAnalysis" :disabled="isAnalyzing" :title="isAnalyzing ? 'Analysiere...' : 'Bildanalyse'">
              <span class="action-icon">
                <svg v-if="!isAnalyzing" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="M440-240q116 0 198-81.5T720-520q0-116-82-198t-198-82q-117 0-198.5 82T160-520q0 117 81.5 198.5T440-240Zm0-280Zm0 160q-83 0-147.5-44.5T200-520q28-70 92.5-115T440-680q82 0 146.5 45T680-520q-29 71-93.5 115.5T440-360Zm0-60q55 0 101-26.5t72-73.5q-26-46-72-73t-101-27q-56 0-102 27t-72 73q26 47 72 73.5T440-420Zm0-40q25 0 42.5-17t17.5-43q0-25-17.5-42.5T440-580q-26 0-43 17.5T380-520q0 26 17 43t43 17Zm0 300q-75 0-140.5-28.5t-114-77q-48.5-48.5-77-114T80-520q0-74 28.5-139.5t77-114.5q48.5-49 114-77.5T440-880q74 0 139.5 28.5T694-774q49 49 77.5 114.5T800-520q0 64-21 121t-58 104l159 159-57 56-159-158q-47 37-104 57.5T440-160Z"/>
                </svg>
                <span v-else>⏳</span>
              </span>
            </button>
          </div>
        </div>

        <!-- Video with Actions -->
        <div v-else-if="mediaType === 'video'" class="video-with-actions">
          <video
            :src="outputImage"
            controls
            class="output-video"
          />

          <!-- Action Toolbar -->
          <div class="action-toolbar">
            <button
              class="action-btn"
              :class="{ 'favorited': isFavorited }"
              @click="$emit('toggle-favorite')"
              :disabled="!runId"
              :title="isFavorited ? $t('gallery.unfavorite') : $t('gallery.favorite')"
            >
              <span class="action-icon">
                <svg v-if="isFavorited" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="m480-120-58-52q-101-91-167-157T150-447.5Q111-500 95.5-544T80-634q0-94 63-157t157-63q52 0 99 22t81 62q34-40 81-62t99-22q94 0 157 63t63 157q0 46-15.5 90T810-447.5Q771-395 705-329T538-172l-58 52Z"/>
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="m480-120-58-52q-101-91-167-157T150-447.5Q111-500 95.5-544T80-634q0-94 63-157t157-63q52 0 99 22t81 62q34-40 81-62t99-22q94 0 157 63t63 157q0 46-15.5 90T810-447.5Q771-395 705-329T538-172l-58 52Zm0-108q96-86 158-147.5t98-107q36-45.5 50-81t14-70.5q0-60-40-100t-100-40q-47 0-87 26.5T518-680h-76q-15-41-55-67.5T300-774q-60 0-100 40t-40 100q0 35 14 70.5t50 81q36 45.5 98 107T480-228Zm0-273Z"/>
                </svg>
              </span>
            </button>
            <button class="action-btn" @click="$emit('download')" title="Herunterladen">
              <span class="action-icon">
                <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="M480-320 280-520l56-58 104 104v-326h80v326l104-104 56 58-200 200ZM240-160q-33 0-56.5-23.5T160-240v-120h80v120h480v-120h80v120q0 33-23.5 56.5T720-160H240Z"/>
                </svg>
              </span>
            </button>
          </div>
        </div>

        <!-- Audio / Music with Actions -->
        <div v-else-if="mediaType === 'audio' || mediaType === 'music'" class="audio-with-actions">
          <audio
            :src="outputImage"
            controls
            class="output-audio"
          />

          <!-- Action Toolbar -->
          <div class="action-toolbar">
            <button
              class="action-btn"
              :class="{ 'favorited': isFavorited }"
              @click="$emit('toggle-favorite')"
              :disabled="!runId"
              :title="isFavorited ? $t('gallery.unfavorite') : $t('gallery.favorite')"
            >
              <span class="action-icon">
                <svg v-if="isFavorited" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="m480-120-58-52q-101-91-167-157T150-447.5Q111-500 95.5-544T80-634q0-94 63-157t157-63q52 0 99 22t81 62q34-40 81-62t99-22q94 0 157 63t63 157q0 46-15.5 90T810-447.5Q771-395 705-329T538-172l-58 52Z"/>
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="m480-120-58-52q-101-91-167-157T150-447.5Q111-500 95.5-544T80-634q0-94 63-157t157-63q52 0 99 22t81 62q34-40 81-62t99-22q94 0 157 63t63 157q0 46-15.5 90T810-447.5Q771-395 705-329T538-172l-58 52Zm0-108q96-86 158-147.5t98-107q36-45.5 50-81t14-70.5q0-60-40-100t-100-40q-47 0-87 26.5T518-680h-76q-15-41-55-67.5T300-774q-60 0-100 40t-40 100q0 35 14 70.5t50 81q36 45.5 98 107T480-228Zm0-273Z"/>
                </svg>
              </span>
            </button>
            <button class="action-btn" @click="$emit('download')" title="Herunterladen">
              <span class="action-icon">
                <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="M480-320 280-520l56-58 104 104v-326h80v326l104-104 56 58-200 200ZM240-160q-33 0-56.5-23.5T160-240v-120h80v120h480v-120h80v120q0 33-23.5 56.5T720-160H240Z"/>
                </svg>
              </span>
            </button>
          </div>
        </div>

        <!-- 3D Model with Actions -->
        <div v-else-if="mediaType === '3d'" class="model-with-actions">
          <div class="model-viewer-container" dir="ltr">
            <model-viewer
              v-if="meshUrl"
              :src="meshUrl"
              :poster="thumbnailUrl || undefined"
              auto-rotate
              camera-controls
              shadow-intensity="1"
              environment-image="neutral"
              interaction-prompt="auto"
              touch-action="pan-y"
              style="width: 100%; height: 100%; background-color: #0a0a0a;"
            ></model-viewer>
            <div v-else class="model-fallback">
              <p>{{ $t('mediaOutput.model3dReady') }}</p>
            </div>
          </div>

          <!-- Action Toolbar -->
          <div class="action-toolbar" style="position: absolute; right: 8px; top: 50%; transform: translateY(-50%); z-index: 10;">
            <button
              class="action-btn"
              :class="{ 'favorited': isFavorited }"
              @click="$emit('toggle-favorite')"
              :disabled="!runId"
              :title="isFavorited ? $t('gallery.unfavorite') : $t('gallery.favorite')"
            >
              <span class="action-icon">
                <svg v-if="isFavorited" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="m480-120-58-52q-101-91-167-157T150-447.5Q111-500 95.5-544T80-634q0-94 63-157t157-63q52 0 99 22t81 62q34-40 81-62t99-22q94 0 157 63t63 157q0 46-15.5 90T810-447.5Q771-395 705-329T538-172l-58 52Z"/>
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="m480-120-58-52q-101-91-167-157T150-447.5Q111-500 95.5-544T80-634q0-94 63-157t157-63q52 0 99 22t81 62q34-40 81-62t99-22q94 0 157 63t63 157q0 46-15.5 90T810-447.5Q771-395 705-329T538-172l-58 52Zm0-108q96-86 158-147.5t98-107q36-45.5 50-81t14-70.5q0-60-40-100t-100-40q-47 0-87 26.5T518-680h-76q-15-41-55-67.5T300-774q-60 0-100 40t-40 100q0 35 14 70.5t50 81q36 45.5 98 107T480-228Zm0-273Z"/>
                </svg>
              </span>
            </button>
            <button class="action-btn" @click="$emit('download')" :title="$t('mediaOutput.download')">
              <span class="action-icon">
                <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                  <path d="M480-320 280-520l56-58 104 104v-326h80v326l104-104 56 58-200 200ZM240-160q-33 0-56.5-23.5T160-240v-120h80v120h480v-120h80v120q0 33-23.5 56.5T720-160H240Z"/>
                </svg>
              </span>
            </button>
          </div>
        </div>

        <!-- Fallback for unknown types with Actions -->
        <div v-else class="unknown-media-with-actions">
          <div class="unknown-media">
            <p>Mediendatei erstellt</p>
          </div>

          <!-- Action Toolbar -->
          <div class="action-toolbar">
            <button class="action-btn" @click="$emit('download')" title="Herunterladen">
              <span class="action-icon">💾</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Expert Generation Summary (mirrors denoising-compact layout) -->
      <div v-if="uiMode === 'expert' && outputImage && modelMeta" class="expert-generation-summary">
        <div class="summary-bar-track">
          <div class="summary-bar-fill"></div>
        </div>
        <div class="summary-stats-line">
          <span class="summary-seg">{{ resolveModelName(modelMeta) }}</span>
          <span v-if="stage4DurationMs" class="summary-seg">{{ (stage4DurationMs / 1000).toFixed(1) }}s</span>
          <span v-if="generationEnergyWh > 0" class="summary-seg">{{ (generationEnergyWh / 1000).toFixed(3) }} kWh</span>
          <span v-if="modelMeta.recommended_resolution" class="summary-seg">{{ modelMeta.recommended_resolution }}</span>
          <span class="summary-sep" v-if="modelMeta.seed != null || modelMeta.cfg != null">|</span>
          <span v-if="modelMeta.seed != null" class="summary-seg">seed:{{ modelMeta.seed }}</span>
          <span v-if="modelMeta.cfg != null" class="summary-seg">CFG:{{ modelMeta.cfg }}</span>
          <span v-if="modelMeta.steps != null" class="summary-seg">{{ modelMeta.steps }} steps</span>
        </div>
      </div>

      <!-- Model Provenance Card (all modes, post-generation) -->
      <ModelProvenanceCard
        v-if="outputImage && modelMeta"
        :meta="modelMeta"
        :safety-level="mapUiModeToSafetyLevel(uiMode ?? 'youth')"
      />

      <!-- Image analysis now handled by Trashy (ChatOverlay) — no inline box -->
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import '@google/model-viewer'
import RandomEdutainmentAnimation from '@/components/edutainment/RandomEdutainmentAnimation.vue'
import DenoisingProgressView from '@/components/edutainment/DenoisingProgressView.vue'
import ModelProvenanceCard from '@/components/ModelProvenanceCard.vue'
import { useAnalysisEventStore } from '@/stores/analysisEvent'

const analysisEventStore = useAnalysisEventStore()

// Captured from DenoisingProgressView on unmount
const generationEnergyWh = ref(0)
function handleStatsSnapshot(stats: { energyWh: number, co2Grams: number }) {
  generationEnergyWh.value = stats.energyWh
}

// Template ref for autoscroll functionality
const sectionRef = ref<HTMLElement | null>(null)

interface AnalysisData {
  analysis: string
  reflection_prompts: string[]
  insights: string[]
  success: boolean
}

interface Props {
  outputImage: string | null
  mediaType: string
  isExecuting: boolean
  progress: number
  estimatedSeconds?: number
  previewImage?: string | null
  isAnalyzing?: boolean
  showAnalysis?: boolean
  analysisData?: AnalysisData | null
  forwardButtonTitle?: string
  // Favorites support
  runId?: string | null
  isFavorited?: boolean
  // Expert denoising view
  modelMeta?: Record<string, any> | null
  uiMode?: string
  stage4DurationMs?: number
  // 3D model support
  meshUrl?: string | null
  thumbnailUrl?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  mediaType: 'image',
  isExecuting: false,
  progress: 0,
  previewImage: null,
  isAnalyzing: false,
  showAnalysis: false,
  analysisData: null,
  forwardButtonTitle: 'Weiterreichen',
  runId: null,
  isFavorited: false,
  modelMeta: null,
  uiMode: 'youth',
  stage4DurationMs: 0,
  meshUrl: null,
  thumbnailUrl: null,
})

defineEmits<{
  'save': []
  'print': []
  'forward': []
  'download': []
  'image-click': [imageUrl: string]
  'toggle-favorite': []
}>()

/** Trigger image analysis via Trashy (dispatches to analysisEventStore → ChatOverlay handles) */
function triggerAnalysis() {
  if (!props.runId || props.mediaType !== 'image') return
  // Extract clean run_id from runId prop (may include path parts)
  const cleanRunId = props.runId.includes('/') ? props.runId.match(/(run_[^/]+)/)?.[1] || props.runId : props.runId
  analysisEventStore.requestReflection('', '', 'media_output', cleanRunId)
}

/** Map uiMode prop to safety level for provenance card */
function mapUiModeToSafetyLevel(mode: string): string {
  if (mode === 'kids') return 'kids'
  if (mode === 'expert') return 'adult'
  return 'youth'
}

/**
 * Resolve a human-readable model name from meta (reads display_name from config)
 */
function resolveModelName(meta: Record<string, any> | null): string {
  if (!meta) return 'Model'
  return meta.display_name || meta.model_file || meta.backend_type || 'Model'
}

// Expose the section element for autoscroll functionality
defineExpose({
  sectionRef
})
</script>

<style scoped>
/* ============================================================================
   Output Frame (3 States)
   ============================================================================ */

.pipeline-section {
  width: 100%;
  display: flex;
  justify-content: center;
}

.output-frame {
  width: 100%;
  max-width: 1000px;
  margin: clamp(1rem, 3vh, 2rem) auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: clamp(1.5rem, 3vh, 2rem);
  /* FIXED height — identical across all states (empty, loading, output) */
  height: clamp(400px, 54vh, 680px);
  overflow: hidden;
  background: rgba(30, 30, 30, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: clamp(12px, 2vw, 20px);
  transition: border-color 0.3s ease, background 0.3s ease, box-shadow 0.3s ease;
}

/* When analysis section is visible, allow frame to grow beyond fixed height */
.output-frame:has(.image-analysis-section) {
  height: auto;
  min-height: clamp(400px, 54vh, 680px);
  overflow: visible;
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

/* Generation Animation Container */
.generation-animation-container {
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
  overflow: hidden;
}

.denoising-preview {
  position: absolute;
  bottom: 12px;
  right: 12px;
  width: 120px;
  height: 120px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Final Output */
.final-output {
  width: 100%;
  text-align: center;
}

.output-image {
  max-width: 100%;
  max-height: clamp(300px, 40vh, 500px);
  object-fit: contain;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  cursor: pointer;
}

.output-image:hover {
  transform: scale(1.02);
}

.output-video {
  width: 100%;
  max-height: 500px;
  border-radius: 12px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
}

.output-audio {
  width: 100%;
  max-height: 500px;
  border-radius: 12px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
}

/* ============================================================================
   Action Toolbar for Output Media
   ============================================================================ */

/* Empty State with Actions */
.empty-with-actions {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

/* Image with Actions Container */
.image-with-actions {
  position: relative;
  display: flex;
  justify-content: center;
  width: 100%;
}

/* Universal Media with Actions Containers */
.video-with-actions,
.audio-with-actions,
.model-with-actions,
.unknown-media-with-actions {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  width: 100%;
}

.video-with-actions .output-video,
.audio-with-actions .output-audio {
  flex: 1;
  max-width: 800px;
}

.model-with-actions .model-viewer-container {
  flex: 1;
  width: 100%;
  min-height: 400px;
  max-height: 600px;
}

.model-with-actions .model-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 400px;
  color: rgba(255, 255, 255, 0.5);
}

.model-with-actions .model-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.action-toolbar {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.5rem;
  background: rgba(20, 20, 20, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.action-toolbar.inactive {
  opacity: 0.3;
  pointer-events: none;
}

/* Action Buttons */
.action-btn {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(30, 30, 30, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.9);
  cursor: pointer;
  transition: all 0.3s ease;
  padding: 0;
}

.action-btn:hover:not(:disabled) {
  background: rgba(102, 126, 234, 0.3);
  border-color: rgba(102, 126, 234, 0.8);
  transform: scale(1.05);
}

.action-btn:active:not(:disabled) {
  transform: scale(0.95);
}

.action-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.action-btn.favorited {
  background: rgba(244, 67, 54, 0.2);
  border-color: rgba(244, 67, 54, 0.5);
  color: #f44336;
}

.action-btn.favorited:hover {
  background: rgba(244, 67, 54, 0.3);
  border-color: rgba(244, 67, 54, 0.8);
}

.action-icon {
  font-size: 1.5rem;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-icon svg {
  width: 20px;
  height: 20px;
}

/* Model/Unknown Media Styling */
.model-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}

.model-hint {
  font-size: 1rem;
  color: rgba(255, 255, 255, 0.8);
  margin: 0;
}

.unknown-media p {
  font-size: 1rem;
  color: rgba(255, 255, 255, 0.8);
  margin: 0;
}

/* ============================================================================
   Expert Generation Summary (persists below final output)
   ============================================================================ */

/* Expert summary mirrors .denoising-compact layout exactly */
.expert-generation-summary {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  width: 100%;
}

.summary-bar-track {
  height: 3px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
  overflow: hidden;
}

.summary-bar-fill {
  width: 100%;
  height: 100%;
  background: rgba(76, 175, 80, 0.4);
  border-radius: 2px;
}

.summary-stats-line {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-size: 0.72rem;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: rgba(255, 255, 255, 0.5);
  flex-wrap: wrap;
}

.summary-seg {
  white-space: nowrap;
}

.summary-sep {
  color: rgba(255, 255, 255, 0.2);
}

/* ============================================================================
   Analysis Section
   ============================================================================ */

.image-analysis-section {
  margin-top: 1.5rem;
  padding: 1.5rem;
  background: rgba(30, 30, 30, 0.9);
  border: 2px solid rgba(102, 126, 234, 0.5);
  border-radius: 12px;
  animation: fadeIn 0.3s ease;
}

.analysis-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.analysis-header h3 {
  margin: 0;
  font-size: 1.25rem;
  color: rgba(255, 255, 255, 0.95);
}

.collapse-btn {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.7);
  font-size: 2rem;
  cursor: pointer;
  line-height: 1;
  padding: 0;
  transition: color 0.2s;
}

.collapse-btn:hover {
  color: rgba(255, 255, 255, 1);
}

.analysis-text {
  color: rgba(255, 255, 255, 0.9);
  line-height: 1.6;
  white-space: pre-wrap;
}

.reflection-prompts {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
}

.reflection-prompts h4 {
  margin: 0 0 0.5rem 0;
  color: rgba(255, 179, 0, 0.95);
}

.reflection-prompts li {
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.5;
  margin-bottom: 0.5rem;
}

.analysis-expand-enter-active,
.analysis-expand-leave-active {
  transition: all 0.3s ease;
  max-height: 1000px;
  overflow: hidden;
}

.analysis-expand-enter-from,
.analysis-expand-leave-to {
  max-height: 0;
  opacity: 0;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Responsive: Stack toolbar below on mobile */
@media (max-width: 768px) {
  .image-with-actions .action-toolbar {
    position: static !important;
    transform: none !important;
    right: auto !important;
    top: auto !important;
    z-index: auto !important;
    flex-direction: row;
    margin-top: 0.5rem;
  }

  .video-with-actions,
  .audio-with-actions {
    flex-direction: column;
  }

  .action-toolbar {
    flex-direction: row;
  }

  .action-btn {
    width: 40px;
    height: 40px;
  }

  .action-icon {
    font-size: 1.25rem;
  }
}
</style>
