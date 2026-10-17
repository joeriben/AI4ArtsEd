<template>
  <div class="image-upload-widget">
    <!-- Drop Zone -->
    <div
      class="drop-zone"
      :class="{ 'drag-over': isDragging, 'has-image': previewUrl, disabled: disabled }"
      @drop.prevent="handleDrop"
      @dragover.prevent="onDragOver"
      @dragleave="isDragging = false"
      @click="triggerFileInput"
    >
      <!-- Preview -->
      <div v-if="previewUrl" class="image-preview">
        <img :src="previewUrl" alt="Uploaded image preview" />

      </div>

      <div v-else class="upload-prompt">
        <div class="upload-icon">
          <svg xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" fill="currentColor">
            <path d="M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h560q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560H200v560Zm40-80h480L570-480 450-320l-90-120-120 160Zm-40 80v-560 560Zm140-360q25 0 42.5-17.5T400-620q0-25-17.5-42.5T340-680q-25 0-42.5 17.5T280-620q0 25 17.5 42.5T340-560Z"/>
          </svg>
        </div>
        <p class="upload-text">
          <strong>{{ t('imageUpload.clickHere') }}</strong> {{ t('imageUpload.orDragImage') }}
        </p>
        <p class="upload-hint">{{ t('imageUpload.formatHint') }}</p>
      </div>
    </div>

    <!-- Hidden File Input -->
    <input
      ref="fileInput"
      type="file"
      accept="image/png,image/jpeg,image/jpg,image/webp"
      @change="handleFileSelect"
      style="display: none"
    />

    <!-- Error Message -->
    <div v-if="error" class="error-message">
      {{ error }}
    </div>

    <!-- Upload Info -->
    <div v-if="uploadInfo" class="upload-info">
      <span class="info-label">{{ t('imageUpload.infoOriginal') }}</span> {{ uploadInfo.original_size[0] }}×{{ uploadInfo.original_size[1] }}px
      <span v-if="wasResized" class="resize-badge">
        → {{ uploadInfo.resized_size[0] }}×{{ uploadInfo.resized_size[1] }}px
      </span>
      <span class="info-label">{{ t('imageUpload.infoSize') }}</span> {{ (uploadInfo.file_size_bytes / 1024).toFixed(1) }}KB
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSafetyEventStore } from '@/stores/safetyEvent'
import { quickImageSafetyCheck, uploadImageFile } from '@/composables/useMaterialIntake'

const { t } = useI18n()
const safetyStore = useSafetyEventStore()

// Props
interface Props {
  maxSizeMB?: number
  initialImage?: string | null  // URL to pre-load image
  /**
   * The field is CLOSED: it takes no click, no drop and no file. A run is
   * standing on what lies in it, or the picture in it is being read, and a
   * second picture arriving mid-way would replace what the work is about. It
   * wears the same look the platform's text field wears while it is held.
   */
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  maxSizeMB: 10,
  initialImage: null,
  disabled: false
})

// Emits
const emit = defineEmits<{
  'image-uploaded': [data: {
    image_id: string
    image_path: string
    filename: string
    preview_url: string
    upload_info: any
  }]
  'image-removed': []
  // A picture is travelling: upload and the check that runs over it. The
  // field around this widget carries the waiting circle for it.
  'image-busy': [busy: boolean]
}>()

// State
const fileInput = ref<HTMLInputElement | null>(null)
const previewUrl = ref<string | null>(null)
const isDragging = ref(false)
// A picture on its way to the server. While this stands, the parent holds no
// path at all, and the preview belongs to the file in flight.
const isUploading = ref(false)
const error = ref<string | null>(null)
const uploadInfo = ref<any>(null)
/** Which file the preview being read belongs to; see processFile. */
let previewGeneration = 0

/**
 * The box shows no picture any more.
 *
 * Raising the generation is what makes that stick: the preview is read
 * asynchronously, and a read that lands afterwards would otherwise put the
 * withheld picture back on screen under the sentence saying it was withheld.
 * Every path that empties this box goes through here, including a refusal of
 * the file whose own read is still running.
 */
function emptyBox() {
  previewGeneration++
  previewUrl.value = null
  uploadInfo.value = null
  if (fileInput.value) fileInput.value.value = ''
}

// Computed
const wasResized = computed(() => {
  if (!uploadInfo.value) return false
  const orig = uploadInfo.value.original_size
  const resized = uploadInfo.value.resized_size
  return orig[0] !== resized[0] || orig[1] !== resized[1]
})

// Allowed file types
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp']

// Methods
function triggerFileInput() {
  if (props.disabled) return
  if (!previewUrl.value) {
    fileInput.value?.click()
  }
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    processFile(file)
  }
}

// A closed field does not light up under something being dragged over it, so
// nothing about it says it would take the picture.
function onDragOver() {
  if (props.disabled) return
  isDragging.value = true
}

function handleDrop(event: DragEvent) {
  isDragging.value = false
  if (props.disabled) return
  const file = event.dataTransfer?.files[0]
  if (file) {
    processFile(file)
  }
}

async function processFile(file: File) {
  // The last word, for a caller that went round the field: nothing is uploaded
  // while it is closed.
  if (props.disabled) return
  error.value = null

  // Validate file type
  if (!ALLOWED_TYPES.includes(file.type)) {
    error.value = t('imageUpload.invalidFormat')
    return
  }

  // Validate file size
  const maxBytes = props.maxSizeMB * 1024 * 1024
  if (file.size > maxBytes) {
    error.value = t('imageUpload.fileTooLarge', { max: props.maxSizeMB })
    return
  }

  // Create preview. The read is asynchronous and can land AFTER a refusal has
  // cleared the field — on a fast-failing upload with a large file it did, and
  // the withheld picture reappeared in the box under a message saying it had
  // been refused. So the preview belongs to the file that is still current.
  const mine = ++previewGeneration
  const reader = new FileReader()
  reader.onload = (e) => {
    if (mine !== previewGeneration) return
    previewUrl.value = e.target?.result as string
  }
  reader.readAsDataURL(file)

  // The picture the parent still holds is the one being replaced, and its path
  // no longer belongs to what stands on screen. Void it here, at the start, so
  // a run begun while the upload is still travelling can never reach for the
  // picture before this one - the larger the file, the longer that window was.
  // The preview stays where it is: the watcher below leaves it alone for as
  // long as an upload is in flight.
  isUploading.value = true
  emit('image-removed')

  // Upload to server: the platform's one upload (`uploadImageFile`), which
  // throws where the server refused. This box posted the form itself, a
  // second copy of that call, until 2026-10-10.
  try {
    const uploaded = await uploadImageFile(file)
    // The picture is checked by the platform's own check, the one every
    // other surface asks (`quickImageSafetyCheck`). It fails CLOSED in both
    // of its directions: a refusal and a check that could not be carried out
    // both keep the picture out of the field. This box ran a second copy of
    // that request until 2026-09-04.
    const safety = await quickImageSafetyCheck(uploaded.path)
    if (!safety.safe) {
      // The parent's picture was voided when this upload began and no
      // image-uploaded followed, so its state is already empty; only what
      // this box shows has to go.
      emptyBox()
      // The box says why it stands empty. Träshy carries the explanation,
      // but the box is where the picture was, and a field that empties itself
      // in silence reads as a fault of the person using it.
      // Short, where the picture was. The whole explanation stands in the
      // panel, which has room for it; a 250-character paragraph in the strip
      // under a drop zone is not where anyone reads it.
      error.value = safety.operational
        ? t('imageUpload.checkUnavailable')
        : t('imageUpload.heldBack')
      safetyStore.reportBlock(
        'vlm_input',
        safety.errorMessage || '',
        [],
        safety.vlmDescription,
        safety.operational,
      )
      return
    }
    // Safe: inform Trashy about what the VLM saw
    if (safety.vlmDescription) {
      safetyStore.reportAnalysis(safety.vlmDescription, true)
    }

    uploadInfo.value = uploaded.raw

    emit('image-uploaded', {
      image_id: uploaded.imageId,
      image_path: uploaded.path,
      // As the server wrote it, the way response.data.filename travelled before.
      filename: uploaded.raw.filename as string,
      preview_url: previewUrl.value!,
      upload_info: uploaded.raw
    })
  } catch (err: any) {
    // Through emptyBox, like every other way this box comes to stand empty:
    // the preview read is still running and would otherwise put the picture
    // back on screen under the sentence saying it did not go up.
    console.error('Upload error:', err)
    emptyBox()
    // The server's own reason where it gave one (a size, a type, a refusal);
    // the house sentence only where nothing was said.
    error.value = err?.said || t('imageUpload.uploadFailed')
  } finally {
    isUploading.value = false
  }
}

watch(isUploading, (busy) => emit('image-busy', busy))

// Watch for initial image prop changes
watch(() => props.initialImage, (newImage) => {
  // While a picture is travelling to the server the parent holds nothing, and
  // syncing to that would blank the picture just chosen.
  if (isUploading.value) return
  // Always sync previewUrl with initialImage (including null/empty)
  previewUrl.value = newImage || null
}, { immediate: true })

// Load initial image on mount (if provided)
onMounted(() => {
  if (props.initialImage) {
    previewUrl.value = props.initialImage
  }
})
</script>

<style scoped>
.image-upload-widget {
  width: 100%;
}

/* How deep the field is before anything lies in it. A page that gives the field
   a narrow column sets its own floor (`--iuw-min-height`), the way
   `SayableFieldMap` takes its own from the page it stands on; unset, it is the
   200 px this widget has always had. */
.drop-zone {
  width: 100%;
  min-height: var(--iuw-min-height, 200px);
  border: 2px dashed #4a8f4d;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  /* A recess: the field lies a shade deeper than what it stands on. The wash was
     a hardcoded neutral dark until 2026-09-04 (Rule 7) and is now the page's own
     ground at the same strength, so it follows the tone the reader has set
     instead of staying black under all of them. On the default tone the two are
     three values apart. */
  background: rgb(var(--bg-base-rgb) / 0.3);
  position: relative;
}

.drop-zone:hover {
  border-color: #5fb563;
  background: rgba(74, 143, 77, 0.1);
}

.drop-zone.drag-over {
  border-color: #76c77b;
  background: rgba(74, 143, 77, 0.2);
  border-style: solid;
}

.drop-zone.has-image {
  cursor: default;
  border-color: #4a8f4d;
}

/* A picture lies in it: the hover keeps the resting wash rather than lighting
   the field up under it. */
.drop-zone.has-image:hover {
  background: rgb(var(--bg-base-rgb) / 0.3);
}

/* Held. The same look the platform's text field carries while it is disabled
   (`.bubble-textarea.disabled` in components/MediaInputBox.vue), so a closed
   field reads the same wherever it stands. */
.drop-zone.disabled,
.drop-zone.disabled:hover {
  opacity: 0.5;
  cursor: not-allowed;
  border-color: #4a8f4d;
  background: rgb(var(--surface-2-rgb) / 0.6);
}

/* Upload Prompt */
.upload-prompt {
  text-align: center;
  padding: 2rem;
}

.upload-icon {
  margin-bottom: 1rem;
  opacity: 0.7;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-icon svg {
  width: 64px;
  height: 64px;
}

.upload-text {
  font-size: var(--flow-fs-body);
  color: #e0e0e0;
  margin-bottom: 0.5rem;
}

.upload-text strong {
  color: #fff;
}

.upload-hint {
  font-size: var(--flow-fs-hint);
  color: #999;
}

/* Image Preview */
.image-preview {
  width: 100%;
  height: 100%;
  min-height: var(--iuw-min-height, 200px);
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.image-preview img {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
  object-fit: contain;
}

/* Error Message */
.error-message {
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
  background: rgba(255, 0, 0, 0.2);
  border: 1px solid rgba(255, 0, 0, 0.5);
  border-radius: 6px;
  color: #ff6b6b;
  font-size: var(--flow-fs-hint);
}

/* Upload Info */
.upload-info {
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
  background: rgba(74, 143, 77, 0.2);
  border: 1px solid rgba(74, 143, 77, 0.5);
  border-radius: 6px;
  font-size: var(--flow-fs-hint);
  color: #b0e0b3;
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.info-label {
  color: #76c77b;
  font-weight: 700;
}

.resize-badge {
  color: #FFB300;
}
</style>
