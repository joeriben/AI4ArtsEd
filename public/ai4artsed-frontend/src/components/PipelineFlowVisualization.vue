<template>
  <div dir="ltr" class="pipeline-flow-container">
    <!-- Pipeline Type Badge (optional, can be hidden) -->
    <div v-if="showPipelineType && pipelineVisualization" class="pipeline-header">
      <span class="pipeline-badge">{{ pipelineVisualization.pipeline_type }}</span>
    </div>

    <!-- Horizontal Flow -->
    <div class="pipeline-flow" :class="{ 'is-executing': isExecuting }">
      <!-- User Input Bubble -->
      <div class="flow-step input-step">
        <div class="step-bubble completed">
          <span class="step-icon">IN</span>
          <div class="step-label">{{ $t('pipeline.yourInput') }}</div>
          <div class="step-preview">{{ truncatedInput }}</div>
        </div>
      </div>

      <!-- Arrow -->
      <div class="flow-arrow">→</div>

      <!-- Pipeline Steps (from pipeline definition) -->
      <template v-for="(step, index) in mergedSteps" :key="`step-${step.step_number}`">
        <div class="flow-step processing-step">
          <div
            class="step-bubble"
            :class="{
              'active': step.status === 'running',
              'completed': step.status === 'completed',
              'pending': step.status === 'pending',
              'failed': step.status === 'failed'
            }"
            @click="toggleStepDetails(step)"
            :title="step.description"
          >
            <span class="step-icon">{{ step.icon }}</span>
            <div class="step-label">{{ step.label }}</div>

            <!-- Status Indicator -->
            <div v-if="step.status === 'running'" class="step-status">
              <div class="spinner"></div>
            </div>
            <div v-else-if="step.status === 'completed'" class="step-status">
              <span class="checkmark">✓</span>
              <span v-if="step.duration_ms" class="duration">
                {{ formatDuration(step.duration_ms) }}
              </span>
            </div>
            <div v-else-if="step.status === 'failed'" class="step-status">
              <span class="error-icon">✗</span>
            </div>
          </div>

          <!-- Expandable Details (click to see full output) -->
          <Transition name="details-fade">
            <div v-if="step.showDetails && step.output" class="step-details">
              <div class="details-content">
                <div class="details-header">
                  <strong>{{ step.description }}</strong>
                  <button @click.stop="step.showDetails = false" class="close-btn">×</button>
                </div>
                <div class="details-body">
                  {{ formatStepOutput(step.output) }}
                </div>
              </div>
            </div>
          </Transition>
        </div>

        <!-- Arrow (if not last step) -->
        <div v-if="index < mergedSteps.length - 1" class="flow-arrow">→</div>
      </template>

      <!-- Final Output (if media generation) -->
      <template v-if="finalOutput">
        <div class="flow-arrow">→</div>
        <div class="flow-step output-step">
          <div class="step-bubble completed">
            <span class="step-icon">{{ finalOutputIcon }}</span>
            <div class="step-label">{{ $t('pipeline.result') }}</div>

            <!-- Image preview -->
            <img
              v-if="finalOutput.run_id && (finalOutput.media_type === 'image' || !finalOutput.media_type)"
              :src="getMediaUrl(finalOutput.run_id)"
              :alt="$t('pipeline.generatedMedia')"
              class="result-image"
              @error="onImageError"
            />

            <!-- Status placeholder -->
            <div v-else class="result-placeholder">
              {{ finalOutput.status || 'Ready' }}
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

// TypeScript interfaces
interface PipelineStepDefinition {
  step_number: number
  chunk_name: string
  label: string
  description: string
  icon: string
  output_type: string
  inputs?: Record<string, string>
}

interface PipelineVisualization {
  pipeline_name: string
  pipeline_type: string
  visualization_type: string
  steps: PipelineStepDefinition[]
}

interface ExecutionStep {
  step_number: number
  chunk_name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  output?: any
  duration_ms?: number
}

interface MergedStep extends PipelineStepDefinition {
  status: 'pending' | 'running' | 'completed' | 'failed'
  output?: any
  duration_ms?: number
  showDetails?: boolean
}

interface FinalOutput {
  run_id?: string
  status?: string
  media_type?: string
}

// Props
const props = defineProps<{
  inputText: string
  pipelineVisualization?: PipelineVisualization
  executionSteps?: ExecutionStep[]
  finalOutput?: FinalOutput
  isExecuting?: boolean
  showPipelineType?: boolean
}>()

const { t } = useI18n()

// Truncate input for display (max 60 chars for kids)
const truncatedInput = computed(() => {
  if (!props.inputText) return ''
  return props.inputText.length > 60
    ? props.inputText.substring(0, 60) + '...'
    : props.inputText
})

// Merge pipeline definition with execution results
const mergedSteps = computed((): MergedStep[] => {
  if (!props.pipelineVisualization?.steps) return []

  return props.pipelineVisualization.steps.map(stepDef => {
    // Find matching execution step
    const execStep = props.executionSteps?.find(
      e => e.chunk_name === stepDef.chunk_name
    )

    return {
      ...stepDef,
      status: execStep?.status || 'pending',
      output: execStep?.output,
      duration_ms: execStep?.duration_ms,
      showDetails: false
    }
  })
})

// Final output icon (visual-first for kids)
const finalOutputIcon = computed(() => {
  if (!props.finalOutput) return 'OUT'

  const iconMap: Record<string, string> = {
    'image': 'IMG',
    'audio': 'AUD',
    'music': 'MUS',
    'video': 'VID'
  }

  return iconMap[props.finalOutput.media_type || 'image'] || 'OUT'
})

// Toggle step details (click to expand)
const toggleStepDetails = (step: MergedStep) => {
  if (step.status === 'completed' && step.output) {
    step.showDetails = !step.showDetails
  }
}

// Format step output for display (simple for kids)
const formatStepOutput = (output: any): string => {
  if (typeof output === 'string') {
    // Truncate long strings
    return output.length > 300 ? output.substring(0, 300) + '...' : output
  }

  if (typeof output === 'object' && output !== null) {
    // Show key-value pairs (for T5/CLIP optimization outputs)
    return Object.entries(output)
      .map(([key, value]) => `${key}: ${value}`)
      .join('\n')
  }

  return JSON.stringify(output)
}

// Format duration (milliseconds to readable format)
const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

// Generate media URL
const getMediaUrl = (runId: string): string => {
  return `/api/media/image/${runId}`
}

// Handle image load errors
const onImageError = (event: Event) => {
  console.error('Failed to load image:', event)
}
</script>

<style scoped>
.pipeline-flow-container {
  padding: 1.5rem;
  background: #f9fafb;
  border-radius: 12px;
  margin: 1rem 0;
}

.pipeline-header {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1rem;
}

.pipeline-badge {
  background: #3b82f6;
  color: white;
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.pipeline-flow {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  overflow-x: auto;
  padding: 1rem 0;
  /* Smooth scrolling for mobile */
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
}

.flow-step {
  flex-shrink: 0;
  position: relative;
}

.step-bubble {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  min-width: 100px;
  max-width: 140px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.step-bubble:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.step-bubble.active {
  border-color: #3b82f6;
  background: #eff6ff;
  animation: pulse 2s ease-in-out infinite;
}

.step-bubble.completed {
  border-color: #10b981;
  background: #f0fdf4;
}

.step-bubble.pending {
  border-color: #d1d5db;
  background: #f9fafb;
  opacity: 0.6;
}

.step-bubble.failed {
  border-color: #ef4444;
  background: #fef2f2;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.step-icon {
  font-size: 2rem;
  line-height: 1;
}

.step-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  text-align: center;
  line-height: 1.2;
  /* Word wrap for long labels */
  word-break: break-word;
  hyphens: auto;
}

.step-preview {
  font-size: 0.75rem;
  color: #6b7280;
  text-align: center;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}

.step-status {
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.checkmark {
  color: #10b981;
  font-size: 1.5rem;
  font-weight: bold;
}

.error-icon {
  color: #ef4444;
  font-size: 1.5rem;
  font-weight: bold;
}

.duration {
  font-size: 0.65rem;
  color: #10b981;
  font-weight: 500;
}

.flow-arrow {
  font-size: 1.5rem;
  color: #9ca3af;
  display: flex;
  align-items: center;
  padding: 0 0.25rem;
  flex-shrink: 0;
}

/* Expandable details */
.step-details {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 0.5rem;
  z-index: 10;
  min-width: 250px;
}

.details-content {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 0.75rem;
  font-size: 0.75rem;
  color: #4b5563;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.details-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #e5e7eb;
}

.details-header strong {
  font-size: 0.8rem;
  color: #111827;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #6b7280;
  padding: 0;
  line-height: 1;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  color: #374151;
}

.details-body {
  white-space: pre-wrap;
  max-height: 200px;
  overflow-y: auto;
  line-height: 1.5;
}

.details-fade-enter-active,
.details-fade-leave-active {
  transition: opacity 0.3s ease;
}

.details-fade-enter-from,
.details-fade-leave-to {
  opacity: 0;
}

/* Result image */
.result-image {
  width: 100px;
  height: 100px;
  object-fit: cover;
  border-radius: 8px;
  margin-top: 0.5rem;
}

.result-placeholder {
  font-size: 0.75rem;
  color: #6b7280;
  text-align: center;
  padding: 0.5rem;
}

/* Responsive: Stack vertically on mobile */
@media (max-width: 768px) {
  .pipeline-flow {
    flex-direction: column;
    align-items: stretch;
  }

  .flow-arrow {
    transform: rotate(90deg);
    margin: 0.5rem 0;
    align-self: center;
  }

  .step-bubble {
    max-width: 100%;
  }

  .step-details {
    position: relative;
    min-width: 100%;
  }
}

/* Accessibility: High contrast mode support */
@media (prefers-contrast: high) {
  .step-bubble {
    border-width: 3px;
  }

  .step-label {
    font-weight: 600;
  }
}

/* Accessibility: Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .step-bubble {
    transition: none;
  }

  .spinner {
    animation: none;
    border-top-color: #3b82f6;
  }

  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
  }
}
</style>
