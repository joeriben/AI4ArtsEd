<template>
  <div ref="inputBoxRef" class="media-input-box bubble-card" :style="isBare ? { '--bare-actions': String(bareActionCount) } : undefined" :class="{
    empty: isEmpty,
    filled: isFilled,
    required: isRequired,
    loading: isLoading,
    bare: isBare,
    'has-title': isBare && !!label,
    'run-over': runOver
  }"
    @dragover="onRunDragOver"
    @dragleave="onRunDragLeave"
    @drop="onRunDrop"
  >
    <!-- Header -->
    <!-- The slim form has no heading row - its buttons sit in the field's own
         corner. Where the surroundings do not already say which field this is,
         the caller names it and the name stands here, one line above the field.
         Left unnamed, nothing stands here at all. -->
    <div v-if="isBare && label" class="bare-title">{{ label }}</div>
    <div class="bubble-header" :title="tooltip">
      <span v-if="!isBare" class="bubble-icon">
        <!-- Lightbulb / Idea -->
        <svg v-if="icon === 'lightbulb'" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
          <path d="M480-80q-26 0-47-12.5T400-126q-33 0-56.5-23.5T320-206v-142q-59-39-94.5-103T190-590q0-121 84.5-205.5T480-880q121 0 205.5 84.5T770-590q0 77-35.5 140T640-348v142q0 33-23.5 56.5T560-126q-12 21-33 33.5T480-80Zm-80-126h160v-36H400v36Zm0-76h160v-38H400v38Zm-8-118h58v-108l-88-88 42-42 76 76 76-76 42 42-88 88v108h58q54-26 88-76.5T690-590q0-88-61-149t-149-61q-88 0-149 61t-61 149q0 63 34 113.5t88 76.5Zm88-162Zm0-38Z"/>
        </svg>
        <!-- Clipboard / List -->
        <svg v-else-if="icon === 'clipboard'" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
          <path d="M120-80v-60h100v-30h-60v-60h60v-30H120v-60h120q17 0 28.5 11.5T280-280v40q0 17-11.5 28.5T240-200q17 0 28.5 11.5T280-160v40q0 17-11.5 28.5T240-80H120Zm0-280v-110q0-17 11.5-28.5T160-510h60v-30H120v-60h120q17 0 28.5 11.5T280-560v70q0 17-11.5 28.5T240-450h-60v30h100v60H120Zm60-280v-180h-60v-60h120v240h-60Zm180 440v-80h480v80H360Zm0-240v-80h480v80H360Zm0-240v-80h480v80H360Z"/>
        </svg>
        <!-- Arrow / Forward -->
        <svg v-else-if="icon === 'arrow'" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
          <path d="m440-200 137-240H80v-80h497L440-760l440 280-440 280Z"/>
        </svg>
        <!-- Stars / AI Optimization -->
        <svg v-else-if="icon === 'stars'" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
          <path d="M160-120v-200q0-33 23.5-56.5T240-400h480q33 0 56.5 23.5T800-320v200H160Zm200-320q-83 0-141.5-58.5T160-640q0-83 58.5-141.5T360-840h240q83 0 141.5 58.5T800-640q0 83-58.5 141.5T600-440H360ZM240-200h480v-120H240v120Zm120-320h240q50 0 85-35t35-85q0-50-35-85t-85-35H360q-50 0-85 35t-35 85q0 50 35 85t85 35Zm0-80q17 0 28.5-11.5T400-640q0-17-11.5-28.5T360-680q-17 0-28.5 11.5T320-640q0 17 11.5 28.5T360-600Zm240 0q17 0 28.5-11.5T640-640q0-17-11.5-28.5T600-680q-17 0-28.5 11.5T560-640q0 17 11.5 28.5T600-600ZM480-200Zm0-440Z"/>
        </svg>
        <!-- Image / Picture -->
        <svg v-else-if="icon === 'image'" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
          <path d="M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h560q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560H200v560Zm40-80h480L570-480 450-320l-90-120-120 160Zm-40 80v-560 560Zm140-360q25 0 42.5-17.5T400-620q0-25-17.5-42.5T340-680q-25 0-42.5 17.5T280-620q0 25 17.5 42.5T340-560Z"/>
        </svg>
        <!-- Plus (for optional images) -->
        <svg v-else-if="icon === 'plus'" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
          <path d="M480-480ZM200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h320v80H200v560h560v-320h80v320q0 33-23.5 56.5T760-120H200Zm40-160h480L570-480 450-320l-90-120-120 160Zm440-320v-80h-80v-80h80v-80h80v80h80v80h-80v80h-80Z"/>
        </svg>
        <!-- Microphone -->
        <svg v-else-if="icon === 'mic'" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
          <path d="M480-400q-50 0-85-35t-35-85v-240q0-50 35-85t85-35q50 0 85 35t35 85v240q0 50-35 85t-85 35Zm-40 280v-123q-104-14-172-93t-68-184h80q0 83 58.5 141.5T480-320q83 0 141.5-58.5T680-520h80q0 105-68 184t-172 93v123h-80Z"/>
        </svg>
        <!-- Fallback to emoji -->
        <span v-else>{{ icon }}</span>
      </span>
      <span v-if="!isBare" class="bubble-label">{{ label }}</span>
      <!-- A run brought into this field is fetched and uploaded before the
           field can show it, and on a picture that takes a moment. Without a
           sign the box stood exactly as before and the drop read as though
           nothing had happened. It sits in the header, which in the slim form
           is the strip in the field's own corner. -->
      <span
        v-if="takingRun || imageBusy"
        class="taking-run"
        role="status"
        :aria-label="t('mediaInput.loading')"
        :title="t('mediaInput.loading')"
      ></span>
      <div v-if="showActions" class="bubble-actions">
        <button v-if="showPresetButton" @click="$emit('open-preset-selector')" class="action-btn preset-btn" :class="{ 'preset-suggesting': isRequired, 'preset-busy': presetBusy }" :disabled="presetBusy || disabled" :title="t('mediaInput.choosePreset')">
          <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M480-60q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm0-80q17 0 28.5-11.5T520-180q0-17-11.5-28.5T480-220q-17 0-28.5 11.5T440-180q0 17 11.5 28.5T480-140Zm-260-70q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm520 0q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm-520-80q17 0 28.5-11.5T260-330q0-17-11.5-28.5T220-370q-17 0-28.5 11.5T180-330q0 17 11.5 28.5T220-290Zm520 0q17 0 28.5-11.5T780-330q0-17-11.5-28.5T740-370q-17 0-28.5 11.5T700-330q0 17 11.5 28.5T740-290ZM220-510q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm520 0q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm-520-80q17 0 28.5-11.5T260-630q0-17-11.5-28.5T220-670q-17 0-28.5 11.5T180-630q0 17 11.5 28.5T220-590Zm520 0q17 0 28.5-11.5T780-630q0-17-11.5-28.5T740-670q-17 0-28.5 11.5T700-630q0 17 11.5 28.5T740-590Zm-260-70q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm0-80q17 0 28.5-11.5T520-780q0-17-11.5-28.5T480-820q-17 0-28.5 11.5T440-780q0 17 11.5 28.5T480-740Z"/>
          </svg>
        </button>
        <button
          v-if="showTranslate && inputType === 'text'"
          @click="translateToEnglish"
          class="action-btn translate-btn"
          :class="{ translating: isTranslating }"
          :disabled="isTranslating || !value.trim() || disabled"
          :title="t('mediaInput.translateToEnglish')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 30" class="union-jack">
            <!-- Background (blue) -->
            <rect width="60" height="30" fill="#012169"/>
            <!-- Diagonals (white + red) -->
            <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" stroke-width="6"/>
            <path d="M0,0 L60,30 M60,0 L0,30" stroke="#C8102E" stroke-width="2"/>
            <!-- Cross (white + red) -->
            <path d="M30,0 V30 M0,15 H60" stroke="#fff" stroke-width="10"/>
            <path d="M30,0 V30 M0,15 H60" stroke="#C8102E" stroke-width="6"/>
          </svg>
        </button>
        <button v-if="showCopy && inputType !== 'audio'" @click="$emit('copy')" class="action-btn copy-btn" :title="t('mediaInput.copy')">
          <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M360-240q-33 0-56.5-23.5T280-320v-480q0-33 23.5-56.5T360-880h360q33 0 56.5 23.5T800-800v480q0 33-23.5 56.5T720-240H360Zm0-80h360v-480H360v480ZM200-80q-33 0-56.5-23.5T120-160v-560h80v560h440v80H200Zm160-240v-480 480Z"/>
          </svg>
        </button>
        <button v-if="showPaste && inputType !== 'audio'" @click="onPasteButton" class="action-btn paste-btn" :disabled="disabled" :title="t('mediaInput.paste')">
          <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h167q11-35 43-57.5t70-22.5q40 0 71.5 22.5T594-840h166q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560h-80v120H280v-120h-80v560Zm280-560q17 0 28.5-11.5T520-800q0-17-11.5-28.5T480-840q-17 0-28.5 11.5T440-800q0 17 11.5 28.5T480-760Z"/>
          </svg>
        </button>
        <button v-if="showClear" @click="$emit('clear')" class="action-btn clear-btn" :disabled="disabled" :title="t('mediaInput.delete')">
          <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M280-120q-33 0-56.5-23.5T200-200v-520h-40v-80h200v-40h240v40h200v80h-40v520q0 33-23.5 56.5T680-120H280Zm400-600H280v520h400v-520ZM360-280h80v-360h-80v360Zm160 0h80v-360h-80v360ZM280-720v520-520Z"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Loading Overlay. Not over audio: there the content IS the recorder,
         and replacing it mid-recording closes the microphone and discards the
         take (AudioRecordWidget's onBeforeUnmount). -->
    <div v-if="isLoading && inputType !== 'audio'" class="preview-loading">
      <div class="spinner-large" :class="{ queued: queueStatus === 'waiting' }"></div>
      <p class="loading-text" :class="{ queued: queueStatus === 'waiting' }">
        {{ queueStatus === 'waiting' ? queueMessage : (loadingMessage || t('mediaInput.loading')) }}
      </p>
    </div>


    <!-- Content: per-encoder display (SD3.5 — both CLIP encoders read the caption, T5 the long form) -->
    <div v-else-if="inputType === 'text' && shownParts" class="triple-prompt-display">
      <div class="triple-section">
        <div class="triple-label">CLIP-L + CLIP-G <span class="triple-tag">Caption</span></div>
        <textarea
          v-if="editableParts"
          class="triple-content triple-edit"
          :value="shownParts.clip"
          :disabled="disabled"
          @input="handlePartInput('clip', $event)"
          @focus="handleFocus"
          @blur="handleBlur"
          @paste="handlePaste"
        ></textarea>
        <div v-else class="triple-content">{{ shownParts.clip }}</div>
      </div>
      <div class="triple-section">
        <div class="triple-label">T5-XXL <span class="triple-tag">Long form</span></div>
        <textarea
          v-if="editableParts"
          class="triple-content triple-edit"
          :value="shownParts.t5"
          :disabled="disabled"
          @input="handlePartInput('t5', $event)"
          @focus="handleFocus"
          @blur="handleBlur"
          @paste="handlePaste"
        ></textarea>
        <div v-else class="triple-content">{{ shownParts.t5 }}</div>
      </div>
      <div class="triple-t5-note">
        <svg xmlns="http://www.w3.org/2000/svg" height="14" viewBox="0 -960 960 960" width="14" fill="currentColor">
          <path d="M440-280h80v-240h-80v240Zm40-320q17 0 28.5-11.5T520-640q0-17-11.5-28.5T480-680q-17 0-28.5 11.5T440-640q0 17 11.5 28.5T480-600Zm0 520q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Z"/>
        </svg>
        {{ t('mediaInput.bothClipEncodersReadTheCaption') }}
      </div>
    </div>

    <!-- Content: Text Input

         An editable div, not a <textarea>. In the slim form the symbols stand
         IN the field's own corner, and the text has to run around them for the
         line or two they cover and then take the full width again. Nothing can
         float inside a textarea, so the only way to keep that corner clear
         there is to narrow the whole column from top to bottom - which is what
         stood here until 2026-08-23 and is not what the corner costs.

         The cut-out is a floated ::before on the field itself (see the bare
         block at the end of the styles), so it lives in ONE place and every box
         with symbols in its corner has it. What a textarea gave for free is
         written out: the line breaks it kept (white-space), the height it
         started at (--rows), the plain text it accepted (paste handler). -->
    <div
      v-else-if="inputType === 'text'"
      ref="textareaRef"
      :contenteditable="disabled || readonly ? 'false' : plaintextMode"
      :data-placeholder="placeholder"
      :style="{ '--rows': String(rows) }"
      :tabindex="disabled ? -1 : 0"
      role="textbox"
      aria-multiline="true"
      @input="handleInput"
      @focus="handleFocus"
      @blur="handleBlur"
      @paste="handlePaste"
      @compositionstart="isComposing = true"
      @compositionend="handleCompositionEnd"
      :class="['bubble-textarea', resizeClass, { disabled: disabled, 'is-empty': !value }]"
    ></div>

    <!-- Content: Image Input (with optional sketch toggle) -->
    <template v-else-if="inputType === 'image'">
      <!-- Upload / Sketch toggle (only when allowSketch is true) -->
      <div v-if="allowSketch" class="input-mode-toggle">
        <button
          class="mode-btn"
          :class="{ active: !sketchMode }"
          @click="sketchMode = false"
          :title="t('imageTransform.uploadMode')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" height="18" viewBox="0 -960 960 960" width="18" fill="currentColor">
            <path d="M440-200h80v-167l64 64 56-57-160-160-160 160 57 56 63-63v167ZM240-80q-33 0-56.5-23.5T160-160v-640q0-33 23.5-56.5T240-880h320l240 240v480q0 33-23.5 56.5T720-80H240Zm280-520v-200H240v640h480v-440H520ZM240-800v200-200 640-640Z"/>
          </svg>
          {{ t('imageTransform.uploadMode') }}
        </button>
        <button
          class="mode-btn"
          :class="{ active: sketchMode }"
          @click="sketchMode = true"
          :title="t('imageTransform.sketchMode')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" height="18" viewBox="0 -960 960 960" width="18" fill="currentColor">
            <path d="M200-200h57l391-391-57-57-391 391v57Zm-80 80v-170l528-527q12-11 26.5-17t30.5-6q16 0 31 6t26 18l55 56q12 11 17.5 26t5.5 30q0 16-5.5 30.5T817-647L290-120H120Zm640-584-56-56 56 56Zm-141 85-28-29 57 57-29-28Z"/>
          </svg>
          {{ t('imageTransform.sketchMode') }}
        </button>
      </div>

      <SketchCanvas
        v-if="sketchMode"
        @image-uploaded="handleImageUpload"
        @image-removed="$emit('image-removed')"
      />
      <ImageUploadWidget
        v-else
        :initial-image="initialImage"
        :disabled="disabled"
        @image-uploaded="handleImageUpload"
        @image-removed="$emit('image-removed')"
        @image-busy="(busy: boolean) => imageBusy = busy"
      />
    </template>

    <!-- Content: Audio Input -->
    <AudioRecordWidget
      v-else-if="inputType === 'audio'"
      :src="audioSrc"
      :max-seconds="maxSeconds"
      :disabled="disabled"
      @audio-recorded="(wav: Blob, seconds: number) => $emit('audio-recorded', wav, seconds)"
      @mic-error="$emit('mic-error')"
    />

    <!-- Whatever else belongs INSIDE this box. Empty on every page that does
         not fill it, so nothing renders and nothing moves. -->
    <slot name="footer" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AudioRecordWidget from '@/components/AudioRecordWidget.vue'
import ImageUploadWidget from '@/components/ImageUploadWidget.vue'
import SketchCanvas from '@/components/SketchCanvas.vue'
import { useSafetyEventStore } from '@/stores/safetyEvent'
import {
  FAVORITE_DT,
  quickImageSafetyCheck,
  quickTextSafetyCheck,
  resolveRunAs,
  uploadImageFile,
  type MaterialWant,
} from '@/composables/useMaterialIntake'
import { postStreamedRun } from '@/services/directRun'
import { wordFeed, type WordFeed } from '@/composables/useWordFeed'
import { apiBase } from '@/services/labApi'

const { t, locale } = useI18n()
const safetyStore = useSafetyEventStore()

/** A run is being held over this field. */
const runOver = ref(false)

// Template refs for parent access (like MediaOutputBox sectionRef)
const inputBoxRef = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLElement | null>(null)

// The field is contenteditable (see the template). Two things follow from that
// and both live here rather than in every page that puts a box on a surface.
//
// 'plaintext-only' keeps markup out of the field and makes Return a line break
// instead of a new block. Where a browser does not have that mode, plain
// 'true' plus the paste handler below comes to the same thing.
const plaintextMode = (() => {
  const probe = document.createElement('div')
  try {
    probe.setAttribute('contenteditable', 'plaintext-only')
  } catch {
    return 'true'
  }
  return probe.contentEditable === 'plaintext-only' ? 'plaintext-only' : 'true'
})()

// While a syllable is being composed (Korean, Japanese, any keyboard that
// builds a character from several keys) the field is mid-word and must not be
// written over from the outside.
const isComposing = ref(false)

// Streaming state
const eventSource = ref<EventSource | null>(null)
const streamedValue = ref('')
const isStreamComplete = ref(false)
const isFirstChunkReceived = ref(false)
// The platform's word queue (composables/useWordFeed.ts): one word every 50 ms,
// whatever pace the chunks arrive at. This box ran a second copy of that queue
// until 2026-10-10.
let feed: WordFeed | null = null

// Autonomous safety state (fuzzy filter + NER + LLM on blur/paste)
const safetyResult = ref<
  { safe: boolean; checks: string[]; error?: string; operational?: boolean } | null
>(null)
/**
 * WHICH text the standing verdict judged, and which check it came from.
 *
 * A verdict that outlives the text it was about is worse than none: it let an
 * edited line go to the translation route on the strength of the last one's
 * pass, and it told a writer their fresh line had been blocked when the block
 * belonged to the line before it. The field is blurred by the very tap that
 * presses a button, so both were one gesture away.
 */
let judgedText: string | null = null
let checkGeneration = 0
const isCheckingSafety = ref(false)

// Translation state
const isTranslating = ref(false)

// Sketch mode (internal toggle when allowSketch + inputType=image)
const sketchMode = ref(false)

// Queue state
const queueStatus = ref<'idle' | 'waiting' | 'acquired'>('idle')
const queueMessage = ref('')

interface Props {
  /**
   * The heading row of the full form. Both are optional, because the slim form
   * has no heading row: there the symbol falls away entirely and the name only
   * stands where the caller gives one. A field whose surroundings already say
   * what it is passes neither.
   */
  icon?: string
  label?: string
  tooltip?: string
  placeholder?: string
  value: string
  inputType?: 'text' | 'image' | 'audio'
  rows?: number
  resizeType?: 'standard' | 'auto' | 'none'
  isEmpty?: boolean
  isRequired?: boolean
  isFilled?: boolean
  isLoading?: boolean
  loadingMessage?: string
  showActions?: boolean
  showCopy?: boolean
  showPaste?: boolean
  showClear?: boolean
  showTranslate?: boolean
  initialImage?: string
  /** The take, when inputType is 'audio'. The page owns the URL. */
  audioSrc?: string
  /** The ceiling on a recording, in seconds. */
  maxSeconds?: number
  disabled?: boolean
  /**
   * The text is shown but cannot be typed over - for fields that display what a
   * run is working on. Unlike `disabled` the box stays lit and its symbols keep
   * working, so the text can still be copied or read aloud.
   */
  readonly?: boolean
  showPresetButton?: boolean
  /** Pulses the preset button for as long as the page waits for the answer. */
  presetBusy?: boolean
  /**
   * How much of the box is drawn. 'bare' keeps the field and its actions and
   * drops everything around them - frame, heading, icon - for places where a
   * full box would sit too heavily over one or two lines of text. The actions
   * themselves stay here, once, rather than being built again in a page.
   */
  chrome?: 'full' | 'bare'
  allowSketch?: boolean
  /** Let the two-part SD3.5 prompt be edited in place (off everywhere else). */
  editableParts?: boolean
  // Streaming props
  enableStreaming?: boolean
  streamUrl?: string
  streamParams?: Record<string, string | boolean>
}

const props = withDefaults(defineProps<Props>(), {
  inputType: 'text',
  rows: 6,
  resizeType: 'standard',
  isEmpty: false,
  isRequired: false,
  isFilled: false,
  isLoading: false,
  loadingMessage: undefined,
  showActions: true,
  showCopy: true,
  showPaste: true,
  showClear: true,
  showTranslate: true,
  initialImage: undefined,
  audioSrc: '',
  maxSeconds: 240,
  disabled: false,
  readonly: false,
  showPresetButton: false,
  presetBusy: false,
  chrome: 'full',
  icon: '',
  label: '',
  tooltip: undefined,
  allowSketch: false
})

const emit = defineEmits<{
  'update:value': [value: string]
  'copy': []
  'paste': []
  'clear': []
  'focus': []  // Emit when textarea gains focus (for Träshy positioning)
  'blur': [value: string]  // Emit when textarea loses focus
  'image-uploaded': [data: any]  // Changed: Accept full data object from ImageUploadWidget
  'image-removed': []
  'audio-recorded': [wav: Blob, seconds: number]
  'mic-error': []
  'open-preset-selector': []
  'stream-started': []  // Emitted on first chunk (to hide loading spinner)
  'stream-complete': [data: any]
  'stream-error': [error: string]
  'wikipedia-lookup': [data: { status: string; terms: Array<{ term: string; lang: string; title: string; url: string; success: boolean }> }]  // Wikipedia lookup events (with real URLs)
}>()

// Expose refs for parent access (like MediaOutputBox)
defineExpose({
  inputBoxRef,
  textareaRef,
  safetyResult,
  isCheckingSafety,
  // Text can reach the field without a keystroke - a transformation writing back
  // into it, a paste button that never focuses it. Neither fires blur or the
  // DOM paste listener, so a page that puts text there itself has to be able to
  // put it through the same check.
  checkSafety,
  // A page that starts a stream must be able to end one. Without this the only
  // way out of a stream that never answers is a reload, because the URL watcher
  // starts streams and nothing stops them.
  closeStream
})

// Computed Properties
// The adaptation hands over one object. Current form {clip, t5}: both CLIP
// encoders read the same caption — they are concatenated feature-wise at the
// same token positions, so they must not diverge — and T5-XXL reads the long
// form. The older {clip_l, clip_g} is still read, because saved and
// hand-edited prompts carry it.
const triplePromptData = computed(() => {
  if (!props.value || props.inputType !== 'text') return null
  const trimmed = props.value.trim()
  if (!trimmed.startsWith('{')) return null
  try {
    const data = JSON.parse(trimmed)
    if (!data || typeof data !== 'object') return null
    const clip = typeof data.clip === 'string' ? data.clip : data.clip_l
    const t5 = typeof data.t5 === 'string' ? data.t5 : data.clip_g
    if (typeof clip === 'string' && clip.trim() && typeof t5 === 'string' && t5.trim()) {
      return { clip: clip.trim(), t5: t5.trim() }
    }
  } catch {
    // Not valid JSON — fall through to normal textarea
  }
  return null
})

/**
 * What the two boxes show. The read-only display above demands both parts be
 * non-empty, because a half-empty two-part prompt is not a prompt. While
 * EDITING, that same rule would delete the editor under the user's hands the
 * moment they clear one field — and would hand the raw JSON, braces and key
 * names included, to the plain textarea and from there to the encoders. So in
 * edit mode the shape decides, not the fill: both keys present is enough.
 */
const editableParts_ = computed(() => {
  if (!props.editableParts || !props.value || props.inputType !== 'text') return null
  const trimmed = props.value.trim()
  if (!trimmed.startsWith('{')) return null
  try {
    const data = JSON.parse(trimmed)
    if (!data || typeof data !== 'object') return null
    const clip = typeof data.clip === 'string' ? data.clip : data.clip_l
    const t5 = typeof data.t5 === 'string' ? data.t5 : data.clip_g
    if (typeof clip === 'string' && typeof t5 === 'string') return { clip, t5 }
  } catch {
    // Not valid JSON — the plain textarea takes it.
  }
  return null
})

const shownParts = computed(() =>
  isBare.value ? null : (editableParts_.value ?? triplePromptData.value)
)

const isBare = computed(() => props.chrome === 'bare')

/**
 * How many symbols the bare row actually shows. The field reserves its corner
 * from this number, so a box that switches one of them off does not keep the
 * room for it - and one that switches another ON does not lose the text under
 * it. Mirrors the v-if conditions of the buttons above; a symbol added there
 * has to be counted here.
 */
const bareActionCount = computed(() => {
  if (!props.showActions) return 0
  let n = 0
  if (props.showPresetButton) n++
  if (props.showTranslate && props.inputType === 'text') n++
  if (props.showCopy && props.inputType !== 'audio') n++
  if (props.showPaste && props.inputType !== 'audio') n++
  if (props.showClear) n++
  return n
})

const resizeClass = computed(() => {
  switch (props.resizeType) {
    case 'auto': return 'auto-resize-textarea'
    case 'none': return 'no-resize-textarea'
    case 'standard':
    default: return 'standard-resize-textarea'
  }
})

// Functions
/**
 * The tags a browser writes into an editable field when Return is pressed. Each
 * one of them IS a line; a <br> is a break WITHIN a line. The difference is the
 * whole reason `innerText` cannot be used below.
 */
const BLOCK_TAGS = new Set(['DIV', 'P', 'LI', 'UL', 'OL', 'BLOCKQUOTE', 'PRE', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6'])

/**
 * The text of an editable field, read the way a textarea's `value` reads.
 *
 * NOT `innerText`: Chrome writes an empty line as `<div><br></div>`, and
 * innerText counts that as two breaks - one for the block, one for the <br>.
 * Measured 2026-08-23: 'a' Return 'b' Return Return 'c' comes back as
 * "a\nb\n\n\nc" where a textarea gives "a\nb\n\nc", and every further empty
 * line widens the gap. So the children are walked here: each block child is one
 * line, a <br> inside one is a break, and a <br> that stands last is the one
 * the browser leaves behind to keep an empty line visible - not one anybody
 * typed.
 */
function readEditable(root: HTMLElement): string {
  const lines: string[] = []
  let head = ''
  const kids = Array.from(root.childNodes)
  kids.forEach((node, i) => {
    if (node.nodeType === Node.ELEMENT_NODE && BLOCK_TAGS.has((node as HTMLElement).tagName)) {
      if (lines.length === 0) lines.push(head)
      lines.push(readEditable(node as HTMLElement))
      return
    }
    let piece = ''
    if (node.nodeType === Node.TEXT_NODE) {
      piece = (node as Text).data
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as HTMLElement
      piece = el.tagName === 'BR'
        ? (i === kids.length - 1 ? '' : '\n')
        : readEditable(el)
    }
    if (lines.length === 0) head += piece
    else lines[lines.length - 1] += piece
  })
  return lines.length === 0 ? head : lines.join('\n')
}

/**
 * What stands in a field. The two-part prompt is edited in real textareas, the
 * field itself is an editable div - both are read here so no caller has to know
 * which one it is holding.
 */
function readField(el: EventTarget | HTMLElement | null): string {
  if (!el) return ''
  if (el instanceof HTMLTextAreaElement) return el.value
  if (el instanceof HTMLElement) return readEditable(el)
  return ''
}

/** Writes text INTO the field, but only when it is not already there - writing
 *  puts the caret back at the start, which must not happen while someone is
 *  typing. `textContent` and not `innerText`: one text node with the line
 *  breaks in it, which `white-space: pre-wrap` draws and `readEditable` reads
 *  back unchanged. */
function syncField(el: HTMLElement) {
  if (isComposing.value) return
  const v = props.value ?? ''
  if (readField(el) !== v) el.textContent = v
}

function handleInput(event: Event) {
  if (isComposing.value) return
  emit('update:value', readField(event.target))
}

function handleCompositionEnd(event: CompositionEvent) {
  isComposing.value = false
  emit('update:value', readField(event.target))
}

/**
 * The two-part prompt is one JSON string on the wire, so an edit to either part
 * has to be written back into that string. The caption goes to both CLIP
 * encoders and the long form to T5, which is why they are edited separately but
 * never stored separately.
 */
function handlePartInput(part: 'clip' | 't5', event: Event) {
  const target = event.target as HTMLTextAreaElement
  let data: Record<string, unknown>
  try {
    data = JSON.parse((props.value || '').trim())
  } catch {
    return
  }
  if (!data || typeof data !== 'object') return
  // Written back into the object that came in, so the untouched part keeps its
  // exact text and the older {clip_l, clip_g} form is edited in place rather
  // than rewritten into the new one behind the user's back.
  const key = part === 'clip'
    ? (typeof data.clip === 'string' ? 'clip' : 'clip_l')
    : (typeof data.t5 === 'string' ? 't5' : 'clip_g')
  emit('update:value', JSON.stringify({ ...data, [key]: target.value }))
}

// Emit focus event for Träshy positioning
function handleFocus() {
  emit('focus')
}

// Emit blur event for prompt logging + autonomous safety check
function handleBlur(event: Event) {
  emit('blur', readField(event.target))
  checkSafety()
}

// Paste handler: only plain text goes in - a prompt is text, never markup. Done
// by hand rather than left to 'plaintext-only', so the browsers without that
// mode behave the same. Then the check, once the text is in.
function handlePaste(event: ClipboardEvent) {
  const target = event.target as HTMLElement | null
  if (target && target.isContentEditable) {
    event.preventDefault()
    insertPlainText(event.clipboardData?.getData('text/plain') ?? '')
    emit('update:value', readField(target))
  }
  nextTick(() => checkSafety())
}

/**
 * execCommand is deprecated and still the only insertion that leaves the
 * field's own undo history intact; the range fallback is there for the day a
 * browser drops it.
 */
function insertPlainText(text: string) {
  try {
    if (document.execCommand('insertText', false, text)) return
  } catch {
    /* falls through to the range below */
  }
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0) return
  const range = sel.getRangeAt(0)
  range.deleteContents()
  const node = document.createTextNode(text)
  range.insertNode(node)
  range.setStartAfter(node)
  range.collapse(true)
  sel.removeAllRanges()
  sel.addRange(range)
}

// Quick-translate: destructive in-place DE→EN translation via backend
async function translateToEnglish() {
  if (!props.value.trim() || isTranslating.value) return
  // This button is a way OUT of the box: it sends the text to a cloud model on
  // a route that runs no check of its own. So it goes only for text that HAS
  // been judged and passed — the tap itself blurs the field, so without this
  // the text it sends is the text the standing verdict was never about. Where
  // no verdict stands it asks for one and waits, and where the answer holds the
  // text back it says so, rather than standing disabled with a reason nobody
  // can reach on a touch screen.
  if (safetyResult.value?.safe !== true) await checkSafety()
  if (safetyResult.value?.safe !== true) {
    // A judged refusal has already been said by the check itself, and it took
    // the text with it. What is left to say is the other case.
    if (safetyResult.value?.operational) safetyStore.reportBlock(1, '', [], undefined, true)
    return
  }
  isTranslating.value = true
  try {
    const baseUrl = apiBase()
    // Streamed, not awaited in one silent POST: the translation is one cloud
    // model call, and the edge in front of this server cuts a request whose
    // origin has sent nothing for about 100 seconds. Every status resolves,
    // because the answer was read out of the body whatever the status was.
    const res = await postStreamedRun('/api/schema/pipeline/translate', {
      text: props.value, target_language: 'en',
    }, { baseUrl, validateStatus: () => true })
    const data = res.data
    if (data.status === 'success' && data.translated_text) {
      emit('update:value', data.translated_text)
    }
  } catch (e) {
    console.warn('[MediaInputBox] Translation failed:', e)
  } finally {
    isTranslating.value = false
  }
}

// Autonomous safety check (called on blur + paste — NOT on stream-complete)
// "Innocent until proven guilty": text stays visible, only cleared if blocked.
// Backend safety checks (Stage 1 + Stage 3 + VLM) are the actual security boundary.
async function checkSafety() {
  const text = props.value?.trim()
  if (!text || props.inputType !== 'text' || props.disabled) return

  // Two blurs in a row are two checks in flight, and the one that answers last
  // is not the one that belongs to the field. Only the newest may write.
  const mine = ++checkGeneration
  isCheckingSafety.value = true

  try {
    const safety = await quickTextSafetyCheck(text, locale.value)
    if (mine !== checkGeneration) return
    judgedText = text
    safetyResult.value = {
      safe: safety.safe,
      checks: safety.checks || [],
      error: safety.operational
        ? t('safetyBlocked.systemUnavailable')
        : safety.errorMessage || undefined,
      operational: safety.operational,
    }
    if (!safety.safe && !safety.operational) {
      // A judged refusal clears the field, as it always has, and the companion
      // says why.
      emit('update:value', '')
      safetyStore.reportBlock(1, safety.errorMessage || '', [])
    }
    // A check that could not run keeps the text — the fault is this platform's
    // and says nothing about what was written. It is not announced here either:
    // this runs on every blur and every paste, and an explanation thrown over
    // the field on each of them says nothing new while the outage lasts. The
    // state holds the text as unjudged, and the ways OUT of this box say so when
    // they are used.
  } finally {
    if (mine === checkGeneration) isCheckingSafety.value = false
  }
}

function handleImageUpload(data: any) {
  // ImageUploadWidget emits full data object with preview_url, image_path, image_id
  emit('image-uploaded', data)
  // In a PICTURE field the value IS the picture, so the address of the preview
  // is what the field holds. In a TEXT field that takes a picture as its second
  // way in, the value is the TEXT — writing the address into it would throw
  // away what the visitor wrote and put a URL in its place, and a reading that
  // failed would leave that URL standing. What a picture becomes there is the
  // surface's answer, not this box's.
  if (props.inputType !== 'text') emit('update:value', data.preview_url)
}

/**
 * Material that was made somewhere else on the platform and is being brought
 * here: a run dragged out of the favourites strip, or a run in the platform's
 * hand put down with the paste button.
 *
 * The run arrives WHOLE - prompt, parameters and media hanging together - and
 * THIS field decides what it takes out of it, namely the one thing the field
 * is. A text field takes the prompt the run was made from, a picture field
 * takes the picture. Nothing about the run's own surroundings comes along, so
 * dropping something into a field can never rewrite the instrument around it.
 *
 * Sound fields stay out of it: what a recorder holds is a take with a length,
 * a run hands over a finished file, and nothing here would know how to turn one
 * into the other. Such a field neither lights up nor accepts.
 */
const wanted = computed<MaterialWant | null>(() =>
  props.inputType === 'image' ? 'image' : props.inputType === 'text' ? 'text' : null
)

/** A run on its way into this field, so the box can say that it is working. */
const takingRun = ref(false)

/**
 * A picture on its way to the server: it is uploaded and checked before the
 * field holds its path, and on a large file that takes seconds. The same
 * waiting circle a dropped run lights stands for it.
 */
const imageBusy = ref(false)

async function takeRun(runId: string) {
  if (!wanted.value) return
  takingRun.value = true
  let material: Awaited<ReturnType<typeof resolveRunAs>> = null
  try {
    material = await resolveRunAs(runId, wanted.value)
  } finally {
    takingRun.value = false
  }
  if (!material) return
  if (material.kind === 'text') {
    emit('update:value', material.text)
    // A run made at one safety level can be carried into a field standing at
    // another: the level is the FIELD's, now, not the run's. Text that arrives
    // without a keystroke fires neither blur nor the DOM paste listener, so the
    // check has to be asked for — the same way the paste button asks for it.
    nextTick(() => checkSafety())
  } else if (material.kind === 'image') {
    // The check takes its turn in the plant-wide queue and can be seconds. The
    // waiting circle an upload lights stands for it too, so the box is not
    // sitting there looking idle while a picture is being judged.
    imageBusy.value = true
    // A run made at one safety level can be carried into a field standing at
    // another — the level is the FIELD's, now, not the run's. The text branch
    // above has said so since it was written; the picture branch went without a
    // check until 2026-09-04, so a picture starred in an adult session landed in
    // a kids field unjudged.
    const safety = await quickImageSafetyCheck(material.image.path)
    if (!safety.safe) {
      safetyStore.reportBlock(
        'vlm_input',
        // No sentence of this client's: the reason is CLASSIFIED where it is
        // read, and a translated one would be classified as a rating.
        safety.errorMessage || '',
        [],
        safety.vlmDescription,
        safety.operational,
      )
      imageBusy.value = false
      return
    }
    if (safety.vlmDescription) safetyStore.reportAnalysis(safety.vlmDescription, true)
    // Exactly the payload ImageUploadWidget produces, so a page that already
    // takes an uploaded picture takes this one without knowing the difference.
    emit('image-uploaded', {
      image_id: material.image.imageId,
      image_path: material.image.path,
      filename: material.image.filename,
      preview_url: material.image.servedUrl,
      upload_info: material.image.raw
    })
    emit('update:value', material.image.servedUrl)
    imageBusy.value = false
  }
}

/**
 * A picture dragged onto the box, which every field on this platform takes.
 * A PICTURE field has the picture widget inside it and that widget takes its
 * own drops, so files fall through there; a TEXT field has nothing inside to
 * take them, and the box itself does.
 */
function claimsFile(dt: DataTransfer): boolean {
  return props.inputType === 'text' && dt.types.includes('Files')
}

/**
 * A picture that arrived by being dragged onto the box. It goes up the
 * platform's own two steps — the one upload and the one quick check — and
 * leaves the field the way the picture field leaves it: the same
 * `image-uploaded` payload, so a page that takes an uploaded picture takes
 * this one without knowing where it came from.
 */
async function takePicture(file: File) {
  imageBusy.value = true
  // The picture the page still holds is the one being replaced, and it is void
  // from here on: a run begun while this upload travels would otherwise reach
  // for the earlier one. Same order as in the picture field.
  emit('image-removed')
  try {
    const up = await uploadImageFile(file)
    const safety = await quickImageSafetyCheck(up.path)
    if (!safety.safe) {
      safetyStore.reportBlock(
        'vlm_input',
        // No sentence of this client's: the reason is CLASSIFIED where it is
        // read, and a translated one would be classified as a rating.
        safety.errorMessage || '',
        [],
        safety.vlmDescription,
        // Whether the check judged the picture or could not run at all.
        safety.operational,
      )
      return
    }
    if (safety.vlmDescription) safetyStore.reportAnalysis(safety.vlmDescription, true)
    emit('image-uploaded', {
      image_id: up.imageId,
      image_path: up.path,
      filename: up.filename,
      preview_url: up.servedUrl,
      upload_info: up.raw,
    })
  } catch {
    /* an upload that failed leaves the field as it was */
  } finally {
    imageBusy.value = false
  }
}

function onRunDragOver(e: DragEvent) {
  if (props.disabled || !wanted.value) return
  const dt = e.dataTransfer
  if (!dt) return
  // A run or a picture. Everything else falls through to whatever is inside
  // the box - a picture field's own widget takes its drops there.
  if (!dt.types.includes(FAVORITE_DT) && !claimsFile(dt)) return
  e.preventDefault()
  dt.dropEffect = 'copy'
  runOver.value = true
}

function onRunDragLeave(e: DragEvent) {
  if (!runOver.value) return
  const to = e.relatedTarget as Node | null
  if (to && inputBoxRef.value?.contains(to)) return  // still inside, over a child
  runOver.value = false
}

function onRunDrop(e: DragEvent) {
  if (props.disabled || !wanted.value) return
  const dt = e.dataTransfer
  if (!dt) return
  const raw = dt.getData(FAVORITE_DT)
  if (raw) {
    e.preventDefault()
    e.stopPropagation()
    runOver.value = false
    try {
      const fav = JSON.parse(raw) as { run_id?: string }
      if (fav.run_id) void takeRun(fav.run_id)
    } catch {
      /* an unreadable payload leaves the field as it was */
    }
    return
  }
  const picture = claimsFile(dt)
    ? Array.from(dt.files).find((f) => f.type.startsWith('image/'))
    : undefined
  if (!picture) return
  e.preventDefault()
  e.stopPropagation()
  runOver.value = false
  void takePicture(picture)
}

/** Text goes on to the page, which is where the paste button has always led. */
function onPasteButton() {
  emit('paste')
}

function autoResizeTextarea() {
  if (props.resizeType !== 'auto' || !textareaRef.value) return
  textareaRef.value.style.height = 'auto'
  textareaRef.value.style.height = (textareaRef.value.scrollHeight + 4) + 'px'
}

// Watchers
// Text reaches the field from outside all the time - an example being picked, a
// perspective written back, a translation, a stream arriving word by word. The
// field is a div, so that text has to be put into it.
watch(() => props.value, async () => {
  // A verdict belongs to the text it judged. The moment that text changes, the
  // verdict is gone and any check still in flight is stale.
  if (safetyResult.value && props.value?.trim() !== judgedText) {
    safetyResult.value = null
    judgedText = null
    checkGeneration++
    isCheckingSafety.value = false
  }
  if (textareaRef.value) syncField(textareaRef.value)
  if (props.inputType === 'text' && props.resizeType === 'auto') {
    await nextTick()
    autoResizeTextarea()
  }
})

// The field itself comes and goes - it is behind a v-if, and the loading
// overlay takes its place while a run is out. Whatever stands in  goes
// back in as soon as it is there again.
watch(textareaRef, (el) => {
  if (el) syncField(el)
})

// Streaming functions
function startStreaming() {

  if (!props.streamUrl) {
    return
  }

  // Close any existing stream first
  closeStream()

  // Reset state
  streamedValue.value = ''
  isStreamComplete.value = false
  isFirstChunkReceived.value = false
  safetyResult.value = null
  judgedText = null
  checkGeneration++
  queueStatus.value = 'idle'
  queueMessage.value = ''

  // Build URL with query parameters (convert boolean values to strings)
  const paramsAsStrings = Object.fromEntries(
    Object.entries(props.streamParams || {}).map(([k, v]) => [k, String(v)])
  )
  const params = new URLSearchParams(paramsAsStrings)
  const url = `${props.streamUrl}?${params.toString()}`


  eventSource.value = new EventSource(url)

  feed = wordFeed((text) => {
    streamedValue.value = text
    emit('update:value', text)
    // Auto-scroll textarea to bottom during streaming
    if (textareaRef.value) textareaRef.value.scrollTop = textareaRef.value.scrollHeight
  })

  // Handle Queue Status
  eventSource.value.addEventListener('queue_status', (event) => {
    const data = JSON.parse(event.data)
    
    if (data.status === 'waiting') {
      queueStatus.value = 'waiting'
      queueMessage.value = data.message
    } else if (data.status === 'acquired') {
      queueStatus.value = 'acquired'
      queueMessage.value = data.message
      // Short delay before switching back to loading text if needed
      setTimeout(() => {
        if (queueStatus.value === 'acquired') queueStatus.value = 'idle'
      }, 2000)
    }
  })

  eventSource.value.addEventListener('connected', (event) => {
  })

  // Handle Wikipedia Lookup Status - emit to parent
  // terms include REAL Wikipedia results (title, url)
  eventSource.value.addEventListener('wikipedia_lookup', (event) => {
    const data = JSON.parse(event.data) as { status: string; terms: Array<{ term: string; lang: string; title: string; url: string; success: boolean }> }
    emit('wikipedia-lookup', data)
  })

  eventSource.value.addEventListener('chunk', (event) => {
    const data = JSON.parse(event.data)

    // Emit stream-started on first chunk (so parent can hide loading spinner)
    if (!isFirstChunkReceived.value) {
      isFirstChunkReceived.value = true
      emit('stream-started')
    }

    feed?.push(data.text_chunk)
  })

  eventSource.value.addEventListener('complete', (event) => {
    const data = JSON.parse(event.data)
    isStreamComplete.value = true

    // Close EventSource but keep buffer processor running until empty
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }

    // The queue goes on draining; once it is empty the box holds the stream's
    // own final text, and only then is the stream complete for the page. A
    // feed closed meanwhile (closeStream) says nothing.
    // System-generated text is safe by definition — no checkSafety() here.
    // Safety only runs on user actions (blur, paste).
    const mine = feed
    void mine?.finish(data.final_text).then(() => {
      if (feed === mine) {
        feed = null
        emit('stream-complete', data)
      }
    })
  })

  eventSource.value.addEventListener('blocked', (event) => {
    const data = JSON.parse(event.data)
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
    feed?.stop()
    feed = null
    safetyStore.reportBlock(data.stage || 'safety', data.reason || t('mediaInput.contentBlocked'), data.found_terms || [])
    emit('stream-complete', { blocked: true, reason: data.reason })
  })

  eventSource.value.addEventListener('error', (event) => {
    // Ignore error if stream already completed successfully
    if (isStreamComplete.value) {
      return
    }

    console.error('[MediaInputBox] Stream error:', event)
    emit('stream-error', 'Stream connection failed')
    closeStream()
  })
}

function closeStream() {
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }
  if (feed) {
    // What is still queued goes into the box at once, unless the stream had
    // already ended on its own: then what stands stays.
    if (!isStreamComplete.value) feed.flush()
    else feed.stop()
    feed = null
  }
}

// Watch for streaming activation (only when URL changes)
watch(() => props.streamUrl, (newUrl, oldUrl) => {
  if (props.enableStreaming && newUrl && newUrl !== oldUrl) {
    startStreaming()
  }
})

// Lifecycle
onMounted(() => {
  if (props.inputType === 'text' && props.resizeType === 'auto') {
    autoResizeTextarea()
  }
})

onUnmounted(() => {
  closeStream()
})
</script>

<style scoped>
.media-input-box {
  background: rgb(var(--surface-1-rgb) / 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: clamp(12px, 2vw, 20px);
  padding: clamp(1rem, 2.5vw, 1.5rem);
  transition: all 0.3s ease;
}

.media-input-box.filled {
  border-color: rgba(102, 126, 234, 0.6);
  background: rgba(102, 126, 234, 0.1);
}

.media-input-box.required {
  border-color: rgba(255, 193, 7, 0.6);
  background: rgba(255, 193, 7, 0.05);
  animation: pulse-required 2s ease-in-out infinite;
}

@keyframes pulse-required {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

/* A run is being held over the field. An outline rather than a border: the
   slim form has no border to colour (`.bare` below drops it). */
/* A run on its way in. Small on purpose: the box keeps standing as it is,
   one turning ring says it is working. Shares the `spin` of the large one. */
.taking-run {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  border: 2px solid rgba(255, 255, 255, 0.15);
  border-top-color: rgba(102, 126, 234, 0.9);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.media-input-box.bare .taking-run {
  margin-inline-end: 2px;
}

.media-input-box.run-over {
  outline: 2px solid rgba(102, 126, 234, 0.8);
  outline-offset: 3px;
}

.media-input-box.empty {
  border: 2px dashed rgba(255, 255, 255, 0.3);
  background: rgb(var(--surface-1-rgb) / 0.5);
}

.media-input-box.loading {
  background: rgb(var(--surface-1-rgb) / 0.7);
  border: 2px solid rgba(79, 172, 254, 0.4);
}

/* Header */
.bubble-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.bubble-icon {
  /* A glyph, not type. The slot holds a drawn SVG or an emoji standing in for
     one, so both are sized by the same drawing measure — the type steps size
     text and would let the two drift apart. */
  --bubble-glyph: clamp(20px, 3vw, 24px);
  font-size: var(--bubble-glyph);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bubble-icon svg {
  width: var(--bubble-glyph);
  height: var(--bubble-glyph);
}

/* The name of the field carries the same step as the text it names and is told
   apart by weight alone — in this scale `head` sits BELOW `body`, so it would
   put the heading under its own field. */
.bubble-label {
  font-size: var(--flow-fs-body);
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
}

.bubble-actions {
  display: flex;
  gap: 0.25rem;
  margin-inline-start: auto;
}

.action-btn {
  background: transparent;
  border: none;
  opacity: 0.4;
  cursor: pointer;
  transition: opacity 0.2s;
  padding: 0.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.9);
}

.action-btn:hover {
  opacity: 0.8;
}

.action-btn.preset-btn {
  opacity: 1;
  color: #FFB300;
  filter: drop-shadow(0 0 4px rgba(255, 179, 0, 0.6));
  margin-inline-end: 30px;
}

.action-btn.preset-btn svg {
  width: 30px;
  height: 30px;
}

.action-btn.preset-btn:hover:not(:disabled) {
  opacity: 1;
  filter: drop-shadow(0 0 6px rgba(255, 179, 0, 0.9));
}

/* Pulse when WIE-Box is empty — opacity only, like pulse-translate */
.action-btn.preset-btn.preset-suggesting {
  animation: preset-pulse 1.5s ease-in-out infinite;
}

@keyframes preset-pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.action-btn svg {
  width: 20px;
  height: 20px;
}

/* Translate (Union Jack) Button */
.action-btn.translate-btn {
  opacity: 0.5;
  padding: 0.25rem 0.15rem;
}

.action-btn.translate-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.action-btn.translate-btn:disabled {
  opacity: 0.2;
  cursor: not-allowed;
}

.action-btn.translate-btn.translating {
  animation: pulse-translate 1s ease-in-out infinite;
}

@keyframes pulse-translate {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.union-jack {
  width: 20px;
  height: 10px;
}

/* The field. It is an editable div rather than a textarea (see the template),
   so what a textarea gave for free is written out here: the line breaks it
   kept, the scrolling, and the height `rows` used to set. */
.bubble-textarea {
  width: 100%;
  background-color: rgb(var(--bg-base-rgb) / 0.3);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: white;
  font-size: var(--flow-fs-body);
  padding: clamp(0.5rem, 1.5vw, 0.75rem);
  font-family: inherit;
  line-height: 1.4;
  white-space: pre-wrap;
  overflow-wrap: break-word;
  overflow-y: auto;
  cursor: text;
  /* What the `rows` attribute did: that many lines of text high, and no taller
     for a longer text - what does not fit scrolls. Pages that hand the field a
     height of their own outrank this line and keep doing so. */
  height: calc(var(--rows, 6) * 1.4em + 2 * clamp(0.5rem, 1.5vw, 0.75rem) + 2px);
}

.bubble-textarea:focus {
  outline: none;
  border-color: rgba(102, 126, 234, 0.8);
  background-color: rgb(var(--bg-base-rgb) / 0.4);
}

/* The placeholder. A div has none, so it is drawn - after the ::before that
   cuts the corner out, which means it keeps clear of the symbols the same way
   the text does. */
.bubble-textarea.is-empty::after {
  content: attr(data-placeholder);
  color: rgba(255, 255, 255, 0.4);
  pointer-events: none;
}

.bubble-textarea.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: rgb(var(--surface-2-rgb) / 0.6);
}

/* The field can be pulled taller. On a dark ground the browser draws its own
   grabber in a tone that is there and cannot be seen, so the corner it sits in
   gets two short lines. Painted by the field itself, so it follows the height it
   is dragged to; only on the two kinds that can be dragged. */
.bubble-textarea.standard-resize-textarea,
.bubble-textarea.auto-resize-textarea {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='11' height='11'%3E%3Cpath d='M10 1.5 1.5 10M10 6 6 10' stroke='%23ffffff' stroke-opacity='.4' stroke-width='1.3' stroke-linecap='round' fill='none'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 4px bottom 4px;
}

/* Resize Types */
.standard-resize-textarea {
  resize: vertical;
  min-height: clamp(44px, 6vh, 56px);
}

.auto-resize-textarea {
  resize: vertical;
  overflow-y: auto;
  min-height: clamp(44px, 6vh, 56px);
  max-height: clamp(150px, 20vh, 250px);
}

.no-resize-textarea {
  resize: none;
  min-height: clamp(44px, 6vh, 56px);
}

/* Upload / Sketch Toggle */
.input-mode-toggle {
  display: flex;
  gap: 0.25rem;
  padding: 0.2rem;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  align-self: flex-start;
  margin-bottom: 0.5rem;
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.75rem;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: rgba(255, 255, 255, 0.5);
  font-size: var(--flow-fs-label);
  cursor: pointer;
  transition: all 0.15s ease;
}

.mode-btn:hover {
  color: rgba(255, 255, 255, 0.8);
  background: rgba(255, 255, 255, 0.05);
}

.mode-btn.active {
  background: rgba(102, 126, 234, 0.2);
  border-color: rgba(102, 126, 234, 0.4);
  color: rgba(255, 255, 255, 0.9);
}

.mode-btn svg {
  width: 16px;
  height: 16px;
}

/* Triple-Prompt Display (SD3.5 per-encoder) */
.triple-prompt-display {
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  overflow: hidden;
}

.triple-section {
  padding: clamp(0.4rem, 1vw, 0.6rem) clamp(0.5rem, 1.5vw, 0.75rem);
  background: rgb(var(--bg-base-rgb) / 0.3);
}

.triple-section + .triple-section {
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.triple-label {
  font-size: var(--flow-fs-label);
  font-weight: 700;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.triple-tag {
  font-size: var(--flow-fs-sub);
  font-weight: 400;
  color: rgba(102, 126, 234, 0.8);
  background: rgba(102, 126, 234, 0.1);
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  text-transform: none;
  letter-spacing: 0;
}

.triple-content {
  color: rgba(255, 255, 255, 0.85);
  font-size: var(--flow-fs-body);
  line-height: 1.4;
  word-break: break-word;
}

.triple-edit {
  width: 100%;
  background: transparent;
  border: none;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  color: inherit;
  /* NOT the `font` shorthand: it stands on the same element as .triple-content
     and would reset that rule's size back to the inherited one. */
  font-family: inherit;
  font-weight: inherit;
  font-style: inherit;
  line-height: inherit;
  resize: vertical;
  min-height: 3.2em;
  padding: 0 0 0.25rem 0;
}

.triple-edit:focus {
  outline: none;
  border-bottom-color: rgba(255, 255, 255, 0.35);
}

.triple-t5-note {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem clamp(0.5rem, 1.5vw, 0.75rem);
  color: rgba(255, 255, 255, 0.35);
  font-size: var(--flow-fs-hint);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.triple-t5-note svg {
  flex-shrink: 0;
  opacity: 0.5;
}

/* Loading Overlay */
.preview-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  min-height: 100px;
}

.spinner-large {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(255, 255, 255, 0.1);
  border-top-color: rgba(102, 126, 234, 0.8);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  color: rgba(255, 255, 255, 0.7);
  font-size: var(--flow-fs-label);
  text-align: center;
}

/* Queue Feedback Styling */
.spinner-large.queued {
  border-top-color: #ff4757;
  border-color: rgba(255, 71, 87, 0.2);
  animation: spin 1.5s linear infinite;
}

.loading-text.queued {
  color: #ff4757;
  font-weight: 400;
  animation: pulse-text 2s ease-in-out infinite;
}

@keyframes pulse-text {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* --- bare: the field and its actions, nothing around them ---
   For a field of one or two lines, where the box would weigh more than what is
   written in it. The frame, the heading and the icon are gone; the actions move
   into the field's own corner, and the field keeps that corner clear of text.
   The buttons are the same buttons - only their order changes, to the order in
   which they are read: copy, paste, perspective, English. */
/* The name of a field in the slim form: the size of the field's own text, in
   the platform's light weight, dim enough to stay under the text it names. */
.media-input-box.bare .bare-title {
  margin-bottom: 0.3rem;
  font-size: var(--flow-fs-body);
  font-weight: 400;
  line-height: 1.3;
  color: rgba(255, 255, 255, 0.55);
}

.media-input-box.bare {
  position: relative;
  background: transparent;
  border: 0;
  padding: 0;
}

.media-input-box.bare .bubble-header {
  position: absolute;
  top: 6px;
  inset-inline-end: 8px;
  margin: 0;
  z-index: 1;
  /* An empty strip in this mode: the clicks belong to the buttons, and
     everything between and around them to the field underneath. */
  pointer-events: none;
}

.media-input-box.bare .bubble-actions {
  margin: 0;
  gap: 6px;
  align-items: center;
  pointer-events: auto;
}

.media-input-box.bare .action-btn {
  padding: 3px;
}

.media-input-box.bare .copy-btn { order: 1; }
.media-input-box.bare .paste-btn { order: 2; }

.media-input-box.bare .preset-btn {
  order: 3;
  margin-inline-end: 0;
}

.media-input-box.bare .preset-btn svg {
  width: 20px;
  height: 20px;
}

.media-input-box.bare .translate-btn { order: 4; }
.media-input-box.bare .clear-btn { order: 5; }

/* The corner the symbols stand in, cut out of the TEXT rather than out of the
   field: a floated box at the head of the flow, so the lines it reaches run
   short and every line below it takes the full width again. That is one or two
   lines. Until 2026-08-23 this was `padding-inline-end` instead, which narrows
   the column from top to bottom - at 376px of column, five symbols left 150px
   of text and a prompt came out two words to the line. This is the ONE place it
   is written; every box that carries its symbols in the corner has it.

   In pixels for the same reason the symbols are drawn in pixels: each is 20px
   with 3px of padding on both sides = 26px, 6px between them, 8px inset at the
   edge - and the field's own inline padding already accounts for the rest, so
   `count * 32px` lands the text just clear of the leftmost symbol. The count
   comes from the box, so three symbols cut less and five cut more. The 20px
   above is load-bearing for this sum - the preset symbol is 30px in the full
   box. The height is the row's own: it stands 6px down and is 26px tall, and
   28px covers what the field's padding does not. */
/* Not where the field is named: the name's line is what the symbols stand in
   then (`.bare-title` is a row of its own and the strip is absolute to the box,
   not to the field), so they end above the first line of text and nothing has
   to be cut out at all. Measured 2026-08-23 in Concept Algebra: symbols end at
   376.5px, the text begins at 380. */
.media-input-box.bare:not(.has-title) .bubble-textarea::before {
  content: '';
  float: inline-end;
  width: calc(var(--bare-actions, 4) * 32px);
  height: 28px;
}

/* 'Required' is drawn by frame and by a pulse of the whole box - in bare mode
   there is no frame, and pulsing the box means pulsing the text one is writing.
   The preset symbol keeps its own suggestion pulse. */
.media-input-box.bare.required {
  animation: none;
}

/* Waiting for the answer, at the symbol that was pressed. */
.action-btn.preset-btn.preset-busy {
  animation: preset-pulse 1.5s ease-in-out infinite;
}

.action-btn.preset-btn:disabled {
  cursor: wait;
}

/* The three that CHANGE the field, while the field is disabled: a run that has
   already gone out is standing on the text in it, and a perspective, a
   translation, a paste or a delete after the fact makes the result a statement
   about a prompt that is no longer there. Same look the translate button has
   carried since it had a disabled state. `preset-busy` is excluded because that
   is the button working, not the field being held. */
.action-btn.preset-btn:disabled:not(.preset-busy),
.action-btn.paste-btn:disabled,
.action-btn.clear-btn:disabled {
  opacity: 0.2;
  cursor: not-allowed;
}

</style>
