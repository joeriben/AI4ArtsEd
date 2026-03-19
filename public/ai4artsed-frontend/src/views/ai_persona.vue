<template>
  <div class="persona-page">
    <!-- Floating media output boxes -->
    <div
      v-for="box in mediaBoxes"
      :key="box.id"
      class="floating-media-box"
      :style="{ left: box.x + 'px', top: box.y + 'px' }"
      @mousedown.prevent="startDrag(box.id, $event)"
    >
      <button class="close-box-btn" @click="removeBox(box.id)">x</button>
      <MediaOutputBox
        :output-image="box.outputUrl"
        :media-type="box.mediaType"
        :is-executing="box.stream.isExecuting.value"
        :progress="box.stream.generationProgress.value"
        :preview-image="box.stream.previewImage.value"
        :run-id="box.runId"
        :is-favorited="box.isFavorited"
        :model-meta="box.stream.modelMeta.value"
        :stage4-duration-ms="box.stream.stage4DurationMs.value"
        ui-mode="expert"
        @toggle-favorite="toggleFavorite(box.id)"
        @image-click="fullscreenImage = $event"
        @download="downloadBoxMedia(box)"
        @forward="forwardToI2I(box)"
        @print="printMedia(box)"
      />
    </div>

    <!-- Fullscreen image modal -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div v-if="fullscreenImage" class="fullscreen-modal" @click="fullscreenImage = null">
          <img :src="fullscreenImage" alt="" class="fullscreen-image" />
          <button class="close-fullscreen" @click.stop="fullscreenImage = null">&times;</button>
        </div>
      </Transition>
    </Teleport>

    <!-- Central chat -->
    <div class="chat-container">
      <div class="chat-header">
        <img :src="trashyIcon" alt="" class="trashy-icon" />
        <span class="chat-title">{{ t('persona.title') }}</span>
        <div class="header-spacer"></div>
        <button
          class="tts-toggle"
          :class="{ active: ttsEnabled }"
          @click="ttsEnabled = !ttsEnabled"
          :title="t('persona.toggleTTS')"
        >
          <img :src="ttsEnabled ? volumeOnIcon : volumeOffIcon" alt="" class="tts-icon" />
        </button>
      </div>

      <div class="chat-messages" ref="messagesRef">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="chat-bubble"
          :class="msg.role"
        >
          <template v-if="msg.role === 'assistant'">
            <span v-for="(part, idx) in parseContent(msg.content)" :key="idx">
              <span v-if="part.type === 'text'">{{ part.text }}</span>
              <button v-else-if="part.type === 'prompt'" class="prompt-suggestion" @click="usePrompt(part.text)">{{ part.text }}</button>
            </span>
          </template>
          <template v-else>{{ msg.content }}</template>
        </div>
        <div v-if="isLoading" class="chat-bubble assistant loading">
          <span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>
        </div>
      </div>

      <div class="chat-input-area">
        <input
          v-model="userInput"
          class="chat-input"
          :placeholder="t('persona.inputPlaceholder')"
          @keydown.enter="sendMessage"
          :disabled="isLoading"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef, triggerRef, nextTick, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useFavoritesStore } from '@/stores/favorites'
import { useDeviceId } from '@/composables/useDeviceId'
import { useGenerationStream } from '@/composables/useGenerationStream'
import MediaOutputBox from '@/components/MediaOutputBox.vue'
import trashyIcon from '@/assets/trashy-icon.png'
import volumeOnIcon from '@/assets/icons/volume_up_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg'
import volumeOffIcon from '@/assets/icons/volume_off_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg'

const { t } = useI18n()
const router = useRouter()
const userPreferences = useUserPreferencesStore()
const favoritesStore = useFavoritesStore()
const deviceId = useDeviceId()

// ---------- Fullscreen ----------

const fullscreenImage = ref<string | null>(null)

// ---------- Chat state ----------

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
}

interface ContentPart {
  type: 'text' | 'prompt' | 'generate'
  text: string
  configId?: string
}

const messages = ref<ChatMessage[]>([])
const userInput = ref('')
const isLoading = ref(false)
const messagesRef = ref<HTMLElement | null>(null)
let nextMsgId = 0

// ---------- TTS ----------

const ttsEnabled = ref(false)

function speak(text: string) {
  if (!ttsEnabled.value || !('speechSynthesis' in window)) return
  speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = userPreferences.language === 'de' ? 'de-DE' : 'en-US'
  utterance.rate = 0.9
  speechSynthesis.speak(utterance)
}

function stripMarkers(text: string): string {
  return text
    .replace(/\[GENERATE:\s*[^\]]+\]/g, '')
    .replace(/\[PROMPT:\s*[^\]]+\]/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

// ---------- Floating media boxes ----------

interface MediaBox {
  id: string
  x: number
  y: number
  stream: ReturnType<typeof useGenerationStream>
  outputUrl: string | null
  mediaType: string
  runId: string | null
  isFavorited: boolean
}

const mediaBoxes = shallowRef<MediaBox[]>([])
const BOX_W = 320
const BOX_H = 340

function findFreePosition(): { x: number; y: number } {
  const margin = 20
  const startX = margin
  const startY = 80
  const viewW = window.innerWidth
  const viewH = window.innerHeight

  const cols = Math.max(1, Math.floor((viewW - margin) / (BOX_W + margin)))

  for (let row = 0; row < 20; row++) {
    for (let col = 0; col < cols; col++) {
      const x = startX + col * (BOX_W + margin)
      const y = startY + row * (BOX_H + margin)

      if (y + BOX_H > viewH - margin) continue

      const occupied = mediaBoxes.value.some(b =>
        Math.abs(b.x - x) < BOX_W && Math.abs(b.y - y) < BOX_H
      )
      if (!occupied) return { x, y }
    }
  }
  return { x: startX, y: startY }
}

async function spawnGeneration(configId: string, prompt: string) {
  const pos = findFreePosition()
  const stream = useGenerationStream()
  const box: MediaBox = {
    id: `gen-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    x: pos.x,
    y: pos.y,
    stream,
    outputUrl: null,
    mediaType: 'image',
    runId: null,
    isFavorited: false,
  }
  mediaBoxes.value = [...mediaBoxes.value, box]

  try {
    const result = await stream.executeWithStreaming({
      prompt,
      output_config: configId,
      device_id: deviceId,
    })
    if (result.status === 'success' && result.media_output) {
      box.outputUrl = result.media_output.url
      box.mediaType = result.media_output.media_type
      box.runId = result.run_id || null
      triggerRef(mediaBoxes)
    }
  } catch (e) {
    console.error('[PERSONA] Generation failed:', e)
  }
}

function removeBox(id: string) {
  mediaBoxes.value = mediaBoxes.value.filter(b => b.id !== id)
}

async function toggleFavorite(id: string) {
  const box = mediaBoxes.value.find(b => b.id === id)
  if (!box?.runId) return
  const success = await favoritesStore.toggleFavorite(
    box.runId,
    box.mediaType as 'image' | 'video' | 'audio' | 'music',
    deviceId,
    'anonymous',
    'persona'
  )
  if (success) {
    box.isFavorited = !box.isFavorited
    triggerRef(mediaBoxes)
  }
}

async function downloadBoxMedia(box: MediaBox) {
  if (!box.outputUrl) return
  try {
    const runIdMatch = box.outputUrl.match(/\/api\/media\/\w+\/(.+)$/)
    const runId = runIdMatch ? runIdMatch[1] : 'media'
    const extensions: Record<string, string> = {
      image: 'png', audio: 'mp3', video: 'mp4', music: 'mp3', code: 'js', '3d': 'glb'
    }
    const ext = extensions[box.mediaType] || 'bin'
    const filename = `ai4artsed_${runId}.${ext}`

    const response = await fetch(box.outputUrl)
    if (!response.ok) throw new Error(`Download failed: ${response.status}`)
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    console.error('[PERSONA] Download error:', error)
  }
}

function forwardToI2I(box: MediaBox) {
  if (!box.outputUrl || box.mediaType !== 'image') return
  const runIdMatch = box.outputUrl.match(/\/api\/media\/image\/(.+)$/)
  localStorage.setItem('i2i_transfer_data', JSON.stringify({
    imageUrl: box.outputUrl,
    runId: runIdMatch ? runIdMatch[1] : null,
    timestamp: Date.now()
  }))
  router.push('/image-transformation')
}

function printMedia(box: MediaBox) {
  if (!box.outputUrl) return
  const printWindow = window.open(box.outputUrl, '_blank')
  if (printWindow) {
    printWindow.onload = () => printWindow.print()
  }
}

// ---------- Dragging ----------

let dragState: { boxId: string; offsetX: number; offsetY: number } | null = null

function startDrag(boxId: string, e: MouseEvent) {
  const box = mediaBoxes.value.find(b => b.id === boxId)
  if (!box) return
  // Don't initiate drag on close button or interactive content
  const target = e.target as HTMLElement
  if (target.closest('.close-box-btn') || target.closest('.action-btn') || target.closest('button')) return

  dragState = {
    boxId,
    offsetX: e.clientX - box.x,
    offsetY: e.clientY - box.y,
  }
}

function onMouseMove(e: MouseEvent) {
  if (!dragState) return
  const box = mediaBoxes.value.find(b => b.id === dragState!.boxId)
  if (!box) return

  const x = Math.max(0, Math.min(window.innerWidth - BOX_W, e.clientX - dragState.offsetX))
  const y = Math.max(0, Math.min(window.innerHeight - BOX_H, e.clientY - dragState.offsetY))
  box.x = x
  box.y = y
  triggerRef(mediaBoxes)
}

function onMouseUp() {
  dragState = null
}

onMounted(() => {
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
})

onUnmounted(() => {
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  speechSynthesis.cancel()
})

// ---------- Chat logic ----------

function getBaseUrl(): string {
  return import.meta.env.DEV ? 'http://localhost:17802' : ''
}

function buildAvailableConfigs(): string {
  // Provide the persona with available configs to choose from
  return [
    'sd35_large — Stable Diffusion 3.5 Large (image)',
    'flux2_diffusers — FLUX.2 (image)',
    'gemini_3_pro_image — Gemini 3 Pro image generation (cloud, EU, DSGVO via Mammouth)',
    'stableaudio — Stable Audio (audio/sound)',
    'heartmula_standard — HeartMuLa (music)',
    'p5js_code — p5.js generative code (code)',
    'tonejs_code — Tone.js audio code (code)',
    'wan22_t2v_video_fast — Wan 2.2 video (video)',
    'ltx_video — LTX Video (video)',
    'hunyuan3d_text_to_3d — Hunyuan3D (3D object)',
  ].join('\n')
}

function buildDraftContext(): string {
  return `AVAILABLE GENERATION CONFIGS (use these config_ids in [GENERATE: config_id | prompt]):\n${buildAvailableConfigs()}`
}

function buildHistory(): Array<{ role: string; content: string }> {
  return messages.value.map(m => ({ role: m.role, content: m.content }))
}

/** Parse [PROMPT: ...] and [GENERATE: ...] markers */
function parseContent(content: string): ContentPart[] {
  const parts: ContentPart[] = []
  // Match both [PROMPT: ...] and [GENERATE: ... | ...]
  const regex = /\[PROMPT:\s*(.+?)\]|\[GENERATE:\s*(\S+?)\s*\|\s*(.+?)\]/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', text: content.slice(lastIndex, match.index) })
    }
    if (match[1]) {
      // [PROMPT: ...]
      parts.push({ type: 'prompt', text: match[1] })
    }
    // [GENERATE: ...] markers are stripped from display — generation is triggered separately
    lastIndex = regex.lastIndex
  }
  if (lastIndex < content.length) {
    parts.push({ type: 'text', text: content.slice(lastIndex) })
  }
  return parts.length > 0 ? parts : [{ type: 'text', text: content }]
}

/** Extract [GENERATE: config_id | prompt] markers from response */
function extractGenerateMarkers(content: string): Array<{ configId: string; prompt: string }> {
  const markers: Array<{ configId: string; prompt: string }> = []
  const regex = /\[GENERATE:\s*(\S+?)\s*\|\s*(.+?)\]/g
  let match: RegExpExecArray | null
  while ((match = regex.exec(content)) !== null) {
    markers.push({ configId: match[1]!, prompt: match[2]! })
  }
  return markers
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function addMessage(role: 'user' | 'assistant', content: string) {
  messages.value.push({ id: nextMsgId++, role, content })
  scrollToBottom()
}

async function callChat(message: string, history: Array<{ role: string; content: string }>): Promise<string | null> {
  const response = await fetch(`${getBaseUrl()}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      history,
      context: {
        persona_mode: true,
        language: userPreferences.language,
        device_id: deviceId,
      },
      draft_context: buildDraftContext(),
    })
  })
  const data = await response.json()
  return data.reply || null
}

function handleBotResponse(reply: string) {
  addMessage('assistant', reply)

  // Speak the text (without markers)
  const spokenText = stripMarkers(reply)
  if (spokenText) speak(spokenText)

  // Trigger generations
  const markers = extractGenerateMarkers(reply)
  for (const marker of markers) {
    spawnGeneration(marker.configId, marker.prompt)
  }
}

async function sendMessage() {
  const text = userInput.value.trim()
  if (!text || isLoading.value) return

  addMessage('user', text)
  userInput.value = ''
  isLoading.value = true

  try {
    const history = messages.value
      .slice(0, -1) // Exclude the just-added user message (it goes as 'message')
      .map(m => ({ role: m.role, content: m.content }))
    const reply = await callChat(text, history)
    if (reply) {
      handleBotResponse(reply)
    } else {
      addMessage('assistant', '[No response]')
    }
  } catch {
    addMessage('assistant', '[Connection error]')
  } finally {
    isLoading.value = false
  }
}

function usePrompt(text: string) {
  userInput.value = text
}

// ---------- Init ----------

async function fetchGreeting() {
  isLoading.value = true
  try {
    const langNames: Record<string, string> = {
      de: 'German', en: 'English', tr: 'Turkish', ko: 'Korean',
      uk: 'Ukrainian', fr: 'French', es: 'Spanish', he: 'Hebrew', ar: 'Arabic', bg: 'Bulgarian'
    }
    const lang = langNames[userPreferences.language] || 'German'
    const reply = await callChat(
      `Begin the conversation. Introduce yourself briefly. Speak in ${lang}.`,
      []
    )
    if (reply) {
      handleBotResponse(reply)
    }
  } catch {
    addMessage('assistant', t('persona.fallbackGreeting'))
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  fetchGreeting()
})
</script>

<style scoped>
.persona-page {
  position: relative;
  width: 100vw;
  height: 100vh;
  background: #0a0a0a;
  overflow: hidden;
}

/* ---------- Floating media boxes ---------- */

.floating-media-box {
  position: absolute;
  width: 320px;
  z-index: 10;
  cursor: grab;
  user-select: none;
}

.floating-media-box:active {
  cursor: grabbing;
  z-index: 20;
}

.close-box-btn {
  position: absolute;
  top: -8px;
  right: -8px;
  z-index: 30;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(30, 30, 30, 0.95);
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.7rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.close-box-btn:hover {
  background: rgba(200, 50, 50, 0.6);
  border-color: rgba(200, 50, 50, 0.8);
  color: white;
}

/* Compact MediaOutputBox overrides */
.floating-media-box :deep(.output-frame) {
  height: 280px;
  min-height: 280px;
}

.floating-media-box :deep(.action-toolbar) {
  gap: 0.25rem;
}

.floating-media-box :deep(.action-btn) {
  width: 32px;
  height: 32px;
}

.floating-media-box :deep(.generation-summary) {
  display: none;
}

/* Audio/music boxes need less height */
.floating-media-box :deep(.audio-with-actions) {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.floating-media-box :deep(.output-audio) {
  width: 90%;
}

/* ---------- Central chat ---------- */

.chat-container {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: min(640px, 90vw);
  height: min(520px, 75vh);
  display: flex;
  flex-direction: column;
  background: rgba(15, 15, 15, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  z-index: 5;
  backdrop-filter: blur(20px);
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.trashy-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
}

.chat-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
}

.header-spacer {
  flex: 1;
}

.tts-toggle {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 4px 6px;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
}

.tts-toggle.active {
  background: rgba(76, 175, 80, 0.15);
  border-color: rgba(76, 175, 80, 0.4);
}

.tts-toggle:hover {
  background: rgba(255, 255, 255, 0.08);
}

.tts-icon {
  width: 18px;
  height: 18px;
  opacity: 0.6;
}

.tts-toggle.active .tts-icon {
  opacity: 0.9;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.chat-bubble {
  max-width: 85%;
  padding: 0.6rem 0.9rem;
  border-radius: 14px;
  font-size: 0.85rem;
  line-height: 1.5;
  word-break: break-word;
}

.chat-bubble.assistant {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.85);
  border-bottom-left-radius: 4px;
}

.chat-bubble.user {
  align-self: flex-end;
  background: rgba(76, 175, 80, 0.15);
  color: rgba(255, 255, 255, 0.9);
  border-bottom-right-radius: 4px;
}

.chat-bubble.loading {
  padding: 0.6rem 1rem;
}

.typing-dots span {
  animation: typing 1.2s infinite;
  font-size: 1.2rem;
  color: rgba(255, 255, 255, 0.4);
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
}

.prompt-suggestion {
  display: inline;
  background: rgba(255, 179, 0, 0.12);
  border: 1px solid rgba(255, 179, 0, 0.3);
  border-radius: 6px;
  padding: 0.15rem 0.4rem;
  color: rgba(255, 179, 0, 0.9);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
  line-height: 1.4;
}

.prompt-suggestion:hover {
  background: rgba(255, 179, 0, 0.22);
  border-color: rgba(255, 179, 0, 0.5);
}

.chat-input-area {
  padding: 0.75rem 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.chat-input {
  width: 100%;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 0.6rem 0.9rem;
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.85rem;
  outline: none;
  transition: border-color 0.15s ease;
}

.chat-input:focus {
  border-color: rgba(255, 255, 255, 0.25);
}

.chat-input::placeholder {
  color: rgba(255, 255, 255, 0.2);
}

.chat-input:disabled {
  opacity: 0.5;
}

/* ---------- Fullscreen modal ---------- */

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
}

.close-fullscreen {
  position: absolute;
  top: 1rem;
  right: 1.5rem;
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 2rem;
  cursor: pointer;
  line-height: 1;
}

.close-fullscreen:hover {
  color: white;
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
