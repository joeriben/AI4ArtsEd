<template>
  <section class="pipeline-section" ref="sectionRef">
    <!-- Output Frame (Always visible) -->
    <div class="output-frame" :class="{ empty: !isExecuting && !outputImage && !meshUrl, generating: isExecuting && !outputImage && !meshUrl, card: frame === 'card' }">
      <!-- Generation Progress Animation -->
      <div v-if="isExecuting && !outputImage" class="generation-animation-container">
        <!-- In a card: a bar, the model's name, the picture forming. The full
             sheet is a page-width thing — it stands on the card's back, where it
             has room and can be scrolled, instead of being squeezed into 300px
             until the model's name breaks one word per line. -->
        <div v-if="frame === 'card'" class="card-progress">
          <img v-if="previewImage" :src="previewImage" alt="" class="card-progress-preview" />
          <div class="card-progress-track">
            <div class="card-progress-fill" :style="{ width: Math.min(100, Math.max(0, progress)) + '%' }"></div>
          </div>
          <div class="card-progress-line">
            <span v-if="modelMeta">{{ resolveModelName(modelMeta) }} · </span>{{ Math.round(progress) }} %
          </div>
        </div>
        <!-- Expert mode: Full denoising view with model Steckbrief -->
        <DenoisingProgressView
          v-else-if="uiMode === 'expert'"
          :progress="progress"
          :preview-image="previewImage"
          :model-meta="modelMeta"
          :encoding-info="encodingInfo"
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
        <MediaActionBar v-if="showActions" inactive :forward-title="forwardButtonTitle" />
      </div>

      <!-- Final Output -->
      <div v-else-if="outputImage || meshUrl" class="final-output">
        <!-- Image with Actions -->
        <div v-if="mediaType === 'image'" class="image-with-actions">
          <img
            :src="outputImage"
            :alt="$t('mediaOutput.generatedImage')"
            class="output-image"
            @click="$emit('image-click', outputImage)"
          />

          <!-- The row hangs over the picture, or stays away entirely where the
               card around this box carries it on its back. -->
          <MediaActionBar
            v-if="showActions"
            media-type="image"
            :run-id="runId"
            :is-favorited="isFavorited"
            :forward-title="forwardButtonTitle"
            @toggle-favorite="$emit('toggle-favorite')"
            @forward="$emit('forward')"
            @download="$emit('download')"
            @print="$emit('print')"
          />
        </div>

        <!-- Video with Actions -->
        <div v-else-if="mediaType === 'video'" class="video-with-actions">
          <video
            :src="outputImage"
            controls
            class="output-video"
          />

          <MediaActionBar
            v-if="showActions"
            media-type="video"
            :run-id="runId"
            :is-favorited="isFavorited"
            @toggle-favorite="$emit('toggle-favorite')"
            @download="$emit('download')"
          />
        </div>

        <!-- Audio / Music with Actions -->
        <div v-else-if="mediaType === 'audio' || mediaType === 'music'" class="audio-with-actions">
          <audio
            :src="outputImage"
            controls
            class="output-audio"
          />

          <MediaActionBar
            v-if="showActions"
            :media-type="mediaType"
            :run-id="runId"
            :is-favorited="isFavorited"
            @toggle-favorite="$emit('toggle-favorite')"
            @download="$emit('download')"
          />
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
              style="width: 100%; height: 100%; background-color: var(--bg-base);"
            ></model-viewer>
            <div v-else class="model-fallback">
              <p>{{ $t('mediaOutput.model3dReady') }}</p>
            </div>
          </div>

          <MediaActionBar
            v-if="showActions"
            media-type="3d"
            :run-id="runId"
            :is-favorited="isFavorited"
            @toggle-favorite="$emit('toggle-favorite')"
            @download="$emit('download')"
          />
        </div>

        <!-- Fallback for unknown types with Actions -->
        <div v-else class="unknown-media-with-actions">
          <div class="unknown-media">
            <p>{{ $t('mediaOutput.mediaCreated') }}</p>
          </div>

          <MediaActionBar
            v-if="showActions"
            media-type="unknown"
            @download="$emit('download')"
          />
        </div>
      </div>

      <!-- Expert Generation Summary (mirrors denoising-compact layout) -->
      <div v-if="uiMode === 'expert' && frame !== 'card' && outputImage && modelMeta" class="expert-generation-summary">
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

      <!-- Model Provenance Card (post-generation). In a card it is NOT drawn
           here: the frame is 300px wide and clips it with no way to scroll —
           what a click on it produced was an unreachable half of a sheet. It
           belongs on the card's back, which is where the enclosing FlowCard
           puts it. -->
      <ModelProvenanceCard
        v-if="frame !== 'card' && outputImage && modelMeta"
        :meta="modelMeta"
      />

      <!-- Image analysis now handled by Trashy (ChatOverlay) — no inline box -->
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import '@google/model-viewer'
import RandomEdutainmentAnimation from '@/components/edutainment/RandomEdutainmentAnimation.vue'
import DenoisingProgressView from '@/components/edutainment/DenoisingProgressView.vue'
import ModelProvenanceCard from '@/components/ModelProvenanceCard.vue'
import { useUiModeStore } from '@/stores/uiMode'
import MediaActionBar from '@/components/MediaActionBar.vue'


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
  encodingInfo?: Record<string, any> | null
  /**
   * How this box is framed. 'page' draws the platform's big output frame —
   * fixed height, 2px border, page padding. 'card' draws NO frame at all,
   * because something else already is one: a FlowCard on a board. Four pages
   * had each overridden .output-frame from outside to get somewhere near this,
   * and each got somewhere different.
   */
  frame?: 'page' | 'card'
  /**
   * Where the row of things one can do with the result stands. 'front' hangs it
   * over the medium, as it has always stood on a page. 'none' keeps it away
   * entirely - for a box that sits inside a card, because the card carries the
   * row on its BACK.
   */
  actions?: 'front' | 'none'
  stage4DurationMs?: number
  // 3D model support
  meshUrl?: string | null
  thumbnailUrl?: string | null
}

// The UI mode decides the expert views of this box; read from its store since
// 2026-10-10. Until then it was a prop nobody set, so the box stood at
// 'medium' in every mode (finding S-017 of the code review of 2026-10-10).
const uiMode = computed(() => useUiModeStore().mode)

const props = withDefaults(defineProps<Props>(), {
  mediaType: 'image',
  isExecuting: false,
  progress: 0,
  previewImage: null,
  isAnalyzing: false,
  showAnalysis: false,
  analysisData: null,
  forwardButtonTitle: '',
  runId: null,
  isFavorited: false,
  modelMeta: null,
  encodingInfo: null,
  frame: 'page',
  actions: 'front',
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


/**
 * Resolve a human-readable model name from meta (reads display_name from config)
 */
const showActions = computed(() => props.actions !== 'none')

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
  background: rgb(var(--surface-2-rgb) / 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: clamp(12px, 2vw, 20px);
  transition: border-color 0.3s ease, background 0.3s ease, box-shadow 0.3s ease;
}

/* In a card the enclosing card IS the frame. Not a smaller version of this one
   — none: no border, no radius, no page padding, no fixed height. And the
   medium follows the card's width, because that is what "pull it larger"
   means: the card grows and the picture, the video, the player grow with it. */
.output-frame.card {
  height: auto;
  min-height: 0;
  margin: 0;
  padding: 6px;
  border: none;
  border-radius: 0;
  background: transparent;
  overflow: visible;
  justify-content: flex-start;
}
.output-frame.card.empty,
.output-frame.card.generating {
  border: none;
  background: transparent;
  box-shadow: none;
}
.output-frame.card .output-image,
.output-frame.card .output-video,
.output-frame.card .output-audio {
  width: 100%;
  max-width: 100%;
  max-height: none;
  box-shadow: none;
}
.output-frame.card .model-with-actions .model-viewer-container {
  min-height: 160px;
}
.output-frame.card .empty-with-actions {
  min-height: 0;
}

/* The compact run: a bar, a line, and the picture forming — sized to a card. */
.card-progress {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.card-progress-preview {
  width: 100%;
  border-radius: 6px;
  object-fit: contain;
}
.card-progress-track {
  width: 100%;
  height: 3px;
  border-radius: 2px;
  background: rgb(var(--surface-3-rgb) / 0.9);
  overflow: hidden;
}
.card-progress-fill {
  height: 100%;
  background: rgba(76, 175, 80, 0.75);
  transition: width 0.3s ease;
}
.card-progress-line {
  font-size: 0.72rem;
  color: rgba(230, 230, 230, 0.55);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* When analysis section is visible, allow frame to grow beyond fixed height.
   Never in a card: both selectors weigh the same, this one stands later, and it
   would pull every card back up to 400 px the day the inline analysis returns. */
.output-frame:not(.card):has(.image-analysis-section) {
  height: auto;
  min-height: clamp(400px, 54vh, 680px);
  overflow: visible;
}

.output-frame.empty {
  border: 2px dashed rgba(255, 255, 255, 0.2);
  background: rgb(var(--surface-1-rgb) / 0.5);
}

.output-frame.generating {
  border: 2px solid rgba(76, 175, 80, 0.6);
  background: rgb(var(--surface-2-rgb) / 0.9);
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

/* Image with Actions — the toolbar overlays the media: faint at rest so it
   never obscures the image, surfacing on hover/focus when the user reaches
   for it. */
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

/* Overlay toolbars (image + 3d model): sit over the media, translucent until
   the user hovers or tabs in — so they never block the view of the result. */
.image-with-actions .action-toolbar,
.model-with-actions .action-toolbar {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 10;
  opacity: 0.1;
  transition: opacity 0.2s ease;
}

.image-with-actions:hover .action-toolbar,
.image-with-actions:focus-within .action-toolbar,
.model-with-actions:hover .action-toolbar,
.model-with-actions:focus-within .action-toolbar {
  opacity: 0.8;
}

/* Touch devices have no hover — keep the controls legible there. */
@media (hover: none) {
  .image-with-actions .action-toolbar,
  .model-with-actions .action-toolbar {
    opacity: 0.8;
  }
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
  background: rgb(var(--surface-2-rgb) / 0.9);
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

</style>
