<template>
  <div class="chat-overlay" :style="overlayPositionStyle">
    <!-- Collapsed State: Floating Icon Button (Draggable) -->
    <button
      v-if="!isExpanded"
      class="chat-toggle-icon"
      :class="{ 'is-dragging': isDragging }"
      @mousedown="startDrag"
      @click="onIconClick"
      @dblclick="resetPosition"
      :title="t('trashy.openTooltip')"
    >
      <img :src="trashyIcon" alt="Träshy" class="chat-icon-img" />
    </button>

    <!-- Expanded State: Chat Window -->
    <div v-else class="chat-window">
      <!-- Header -->
      <div class="chat-header">
        <span class="chat-title">Träshy</span>
        <img :src="trashyIcon" alt="Träshy" class="header-trashy-icon" />
        <div class="header-right">
          <button class="close-button" @click="collapse" :title="t('trashy.closeTooltip')">×</button>
        </div>
      </div>

      <!-- Messages Container -->
      <div class="chat-messages" ref="messagesContainer">
        <!-- Initial greeting (only if no messages) -->
        <div v-if="messages.length === 0" class="message assistant greeting">
          <div class="message-content">
            {{ t('trashy.greeting') }}
          </div>
        </div>

        <!-- Message History -->
        <div
          v-for="msg in messages"
          :key="msg.id"
          :class="['message', msg.role]"
        >
          <div class="message-content">
            <div v-if="msg.content">{{ msg.content }}</div>
            <div v-else-if="msg.thinking" class="thinking-no-answer">{{ t('trashy.noResponse') }}</div>
            <div v-if="msg.thinking" class="thinking-toggle" @click="toggleThinking(msg.id)">
              <span class="thinking-arrow">{{ expandedThinking.has(msg.id) ? '\u25BE' : '\u25B8' }}</span>
              <span class="thinking-label">Thinking</span>
            </div>
            <div v-if="msg.thinking && expandedThinking.has(msg.id)" class="thinking-text">{{ msg.thinking }}</div>
          </div>
        </div>

        <!-- Loading Indicator -->
        <div v-if="isLoading" class="message assistant loading">
          <div class="message-content">
            <span class="spinner"></span>
            <span class="loading-text">{{ t('trashy.thinking') }}</span>
          </div>
        </div>
      </div>

      <!-- Input Container -->
      <div class="chat-input-container">
        <textarea
          v-model="inputMessage"
          :placeholder="t('trashy.placeholder')"
          @keydown.enter.exact.prevent="sendMessage"
          @keydown.shift.enter="inputMessage += '\n'"
          :disabled="isLoading"
          rows="2"
          ref="inputTextarea"
        ></textarea>
        <button
          class="send-button"
          @click="sendMessage"
          :disabled="!canSend"
          :title="t('trashy.sendTooltip')"
        >
          ➤
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { useCurrentSession } from '../composables/useCurrentSession'
import { usePageContextStore } from '../stores/pageContext'
import { useSafetyEventStore } from '../stores/safetyEvent'
import { DEFAULT_FOCUS_HINT } from '../composables/usePageContext'
import { useI18n } from 'vue-i18n'
import trashyIcon from '../assets/trashy-icon.png'

interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  thinking?: string | null
}

const { t, locale } = useI18n()

// State
const isExpanded = ref(false)
const isLoading = ref(false)
const inputMessage = ref('')
const messages = ref<Message[]>([])
let messageIdCounter = 0
const expandedThinking = ref(new Set<number>())

function toggleThinking(messageId: number) {
  const s = new Set(expandedThinking.value)
  if (s.has(messageId)) s.delete(messageId)
  else s.add(messageId)
  expandedThinking.value = s
}

// Drag state
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })
const userPosition = ref<{ right: number; bottom: number } | null>(null)

// Load saved position from localStorage
const STORAGE_KEY = 'trashy-position'
const savedPosition = localStorage.getItem(STORAGE_KEY)
if (savedPosition) {
  try {
    userPosition.value = JSON.parse(savedPosition)
  } catch {
    // Invalid JSON, ignore
  }
}

// Reactive viewport dimensions (makes overlayPositionStyle re-evaluate on resize)
const viewportWidth = ref(window.innerWidth)
const viewportHeight = ref(window.innerHeight)

function onWindowResize() {
  viewportWidth.value = window.innerWidth
  viewportHeight.value = window.innerHeight

  // Re-clamp saved position so Träshy stays in viewport
  if (userPosition.value) {
    const maxRight = viewportWidth.value - ICON_SIZE - CHAT_MIN_MARGIN
    const maxBottom = viewportHeight.value - ICON_SIZE - CHAT_MIN_MARGIN
    userPosition.value = {
      right: Math.max(CHAT_MIN_MARGIN, Math.min(maxRight, userPosition.value.right)),
      bottom: Math.max(CHAT_MIN_MARGIN, Math.min(maxBottom, userPosition.value.bottom))
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(userPosition.value))
  }
}

onMounted(() => window.addEventListener('resize', onWindowResize))
onUnmounted(() => window.removeEventListener('resize', onWindowResize))

// Refs
const messagesContainer = ref<HTMLElement | null>(null)
const inputTextarea = ref<HTMLTextAreaElement | null>(null)

// Session context
const { currentSession } = useCurrentSession()

// Page context (Session 133: Träshy knows about current page state)
// Using Pinia store instead of inject (works across component tree siblings)
const pageContextStore = usePageContextStore()
const route = useRoute()

// Safety event store — auto-expand Träshy when safety blocks occur
const safetyStore = useSafetyEventStore()

// Build draft context string for LLM
const draftContextString = computed(() => {
  return pageContextStore.formatForLLM(route.path)
})

// Chat window dimensions
const CHAT_HEIGHT = 520
const CHAT_WIDTH = 380
const CHAT_MIN_MARGIN = 10 // Minimum margin from viewport edges
const ICON_SIZE = 100 // Maximum icon size (clamp max)

// Dynamic positioning based on focusHint OR user drag position
// Clamp position to keep Träshy FULLY within viewport (never outside, not even partially)
const overlayPositionStyle = computed(() => {
  const hint = pageContextStore.currentFocusHint
  const style: Record<string, string> = {}
  const vw = viewportWidth.value
  const vh = viewportHeight.value

  if (isExpanded.value) {
    // EXPANDED: Chat window positioning (uses hint, not user position)
    const chatHeight = Math.min(CHAT_HEIGHT, vh - 120)

    // Horizontal: Convert hint.x to pixels and clamp
    const requestedRight = ((100 - hint.x) / 100) * vw
    const minRight = CHAT_MIN_MARGIN
    const maxRight = vw - CHAT_WIDTH - CHAT_MIN_MARGIN
    const clampedRight = Math.max(minRight, Math.min(maxRight, requestedRight))
    style.right = `${clampedRight}px`
    style.left = 'auto'

    // Vertical: Convert hint.y to pixels and clamp
    const requestedTop = (hint.y / 100) * vh
    const minTop = CHAT_MIN_MARGIN
    const maxTop = vh - chatHeight - CHAT_MIN_MARGIN
    const clampedTop = Math.max(minTop, Math.min(maxTop, requestedTop))
    style.top = `${clampedTop}px`
    style.bottom = 'auto'
  } else {
    // COLLAPSED: Icon positioning
    // Use user-dragged position if available, otherwise use hint
    let finalRight: number
    let finalBottom: number

    if (userPosition.value) {
      // User has dragged Träshy — re-clamp against current viewport
      const maxRight = vw - ICON_SIZE - CHAT_MIN_MARGIN
      const maxBottom = vh - ICON_SIZE - CHAT_MIN_MARGIN
      finalRight = Math.max(CHAT_MIN_MARGIN, Math.min(maxRight, userPosition.value.right))
      finalBottom = Math.max(CHAT_MIN_MARGIN, Math.min(maxBottom, userPosition.value.bottom))
    } else {
      // No user position - calculate from hint
      const requestedRight = ((100 - hint.x) / 100) * vw
      const requestedBottom = ((100 - hint.y) / 100) * vh

      // Clamp horizontal: icon must not extend past left or right edge
      const maxRight = vw - ICON_SIZE - CHAT_MIN_MARGIN
      finalRight = Math.max(CHAT_MIN_MARGIN, Math.min(maxRight, requestedRight))

      // Clamp vertical: icon must not extend past top or bottom edge
      const maxBottom = vh - ICON_SIZE - CHAT_MIN_MARGIN
      finalBottom = Math.max(CHAT_MIN_MARGIN, Math.min(maxBottom, requestedBottom))
    }

    style.right = `${finalRight}px`
    style.left = 'auto'
    style.bottom = `${finalBottom}px`
    style.top = 'auto'
  }

  return style
})

// Double-click to reset to default position
function resetPosition() {
  userPosition.value = null
  localStorage.removeItem(STORAGE_KEY)
}

// Drag handlers - track if we actually dragged (vs just clicked)
let dragStartMouse = { x: 0, y: 0 }
let dragStartPosition = { right: 0, bottom: 0 }
let hasDragged = false

function startDrag(event: MouseEvent) {
  if (isExpanded.value) return

  hasDragged = false
  isDragging.value = true

  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight

  // Store mouse start position
  dragStartMouse = { x: event.clientX, y: event.clientY }

  // Store current icon position
  dragStartPosition = {
    right: userPosition.value?.right ??
      Math.max(CHAT_MIN_MARGIN, Math.min(
        viewportWidth - ICON_SIZE - CHAT_MIN_MARGIN,
        ((100 - pageContextStore.currentFocusHint.x) / 100) * viewportWidth
      )),
    bottom: userPosition.value?.bottom ??
      Math.max(CHAT_MIN_MARGIN, Math.min(
        viewportHeight - ICON_SIZE - CHAT_MIN_MARGIN,
        ((100 - pageContextStore.currentFocusHint.y) / 100) * viewportHeight
      ))
  }

  document.body.style.cursor = 'grabbing'

  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', endDrag)

  event.preventDefault()
}

function onDrag(event: MouseEvent) {
  if (!isDragging.value) return

  // Check if we've moved enough to count as a drag (5px threshold)
  const dx = event.clientX - dragStartMouse.x
  const dy = event.clientY - dragStartMouse.y
  if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
    hasDragged = true
  }

  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight

  // Calculate new position based on mouse delta
  // Moving mouse RIGHT (positive dx) → decrease "right" value
  // Moving mouse DOWN (positive dy) → decrease "bottom" value
  let newRight = dragStartPosition.right - dx
  let newBottom = dragStartPosition.bottom - dy

  // Clamp to viewport bounds
  const minRight = CHAT_MIN_MARGIN
  const maxRight = viewportWidth - ICON_SIZE - CHAT_MIN_MARGIN
  const minBottom = CHAT_MIN_MARGIN
  const maxBottom = viewportHeight - ICON_SIZE - CHAT_MIN_MARGIN

  newRight = Math.max(minRight, Math.min(maxRight, newRight))
  newBottom = Math.max(minBottom, Math.min(maxBottom, newBottom))

  userPosition.value = { right: newRight, bottom: newBottom }
}

function endDrag() {
  isDragging.value = false
  document.body.style.cursor = ''

  if (userPosition.value && hasDragged) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(userPosition.value))
  }

  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', endDrag)
}

// Click handler: only expand if we didn't drag
function onIconClick(event: MouseEvent) {
  if (hasDragged) {
    event.preventDefault()
    event.stopPropagation()
    return
  }
  expand()
}

// Computed
const canSend = computed(() => {
  return inputMessage.value.trim().length > 0 && !isLoading.value
})

// Methods
async function expand() {
  isExpanded.value = true

  // Focus input after expansion
  await nextTick()
  inputTextarea.value?.focus()

  // Load chat history if session exists
  if (currentSession.value.runId) {
    await loadChatHistory()
  }
}

function collapse() {
  isExpanded.value = false
}

async function loadChatHistory() {
  if (!currentSession.value.runId) return

  try {
    const response = await axios.get(`/api/chat/history/${currentSession.value.runId}`)
    const history = response.data.history || []

    // Convert history to messages (filter out system messages)
    messages.value = history
      .filter((msg: any) => msg.role !== 'system')
      .map((msg: any, index: number) => ({
        id: index,
        role: msg.role,
        content: msg.content
      }))

    messageIdCounter = messages.value.length

    // Scroll to bottom
    await nextTick()
    scrollToBottom()

    console.log('[ChatOverlay] Loaded chat history:', messages.value.length, 'messages')
  } catch (error) {
    console.error('[ChatOverlay] Error loading chat history:', error)
    // Don't show error to user - just start with empty chat
  }
}

async function sendMessage() {
  if (!canSend.value) return

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''

  // Add user message to UI (show original message only)
  messages.value.push({
    id: messageIdCounter++,
    role: 'user',
    content: userMessage
  })

  // Scroll to bottom
  await nextTick()
  scrollToBottom()

  // Call API
  isLoading.value = true

  try {
    // Prepare history for backend
    const historyForBackend = messages.value.map(msg => ({
      role: msg.role,
      content: msg.content
    }))

    // Send draft_context as separate field (not embedded in message)
    // Backend uses it for system prompt but does NOT save it to exports/
    const response = await axios.post('/api/chat', {
      message: userMessage,  // Original message without context prefix
      run_id: currentSession.value.runId || undefined,
      draft_context: draftContextString.value || undefined,  // Always send current page state
      history: historyForBackend,
      language: locale.value,
    })

    const assistantReply = response.data.reply
    const assistantThinking = response.data.thinking || null

    // Add assistant response to UI
    messages.value.push({
      id: messageIdCounter++,
      role: 'assistant',
      content: assistantReply,
      thinking: assistantThinking
    })

    // Scroll to bottom
    await nextTick()
    scrollToBottom()

    console.log('[ChatOverlay] Message sent, context_used:', response.data.context_used)
  } catch (error) {
    console.error('[ChatOverlay] Error sending message:', error)

    // Add error message
    messages.value.push({
      id: messageIdCounter++,
      role: 'assistant',
      content: t('trashy.sendError')
    })

    await nextTick()
    scrollToBottom()
  } finally {
    isLoading.value = false
    // Re-focus input after response
    await nextTick()
    inputTextarea.value?.focus()
  }
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// Watch for session changes - clear messages if session changes
watch(
  () => currentSession.value.runId,
  async (newRunId, oldRunId) => {
    // If run_id changed (and not just initialized), reload history
    if (newRunId !== oldRunId && isExpanded.value) {
      if (newRunId) {
        console.log('[ChatOverlay] Session changed, reloading history')
        await loadChatHistory()
      } else {
        // Session cleared
        console.log('[ChatOverlay] Session cleared, resetting chat')
        messages.value = []
        messageIdCounter = 0
      }
    }
  }
)

// Watch for safety block events — auto-expand Träshy and explain
watch(
  () => safetyStore.pendingBlock,
  async (block) => {
    if (!block) return

    const event = safetyStore.consume()
    if (!event) return

    console.log('[ChatOverlay] Safety block received:', event)

    // Build pedagogical explanation based on block type
    let explanation: string
    const reason = event.reason || ''

    if (event.stage === 'vlm_input') {
      explanation = t('safetyBlocked.inputImage')
      if (event.vlmDescription) {
        explanation += `\n\n*${t('safetyBlocked.vlmSaw')}: "${event.vlmDescription}"*`
      }
    } else if (reason.includes('VLM') || event.stage === 'vlm_safety') {
      explanation = t('safetyBlocked.vlm')
      if (event.vlmDescription) {
        explanation += `\n\n*${t('safetyBlocked.vlmSaw')}: "${event.vlmDescription}"*`
      }
    } else if (reason.includes('§86a')) {
      explanation = t('safetyBlocked.para86a')
    } else if (reason.includes('DSGVO') || reason.includes('Persönliche Daten')) {
      explanation = t('safetyBlocked.dsgvo')
    } else if (reason.includes('Kids-Filter') || reason.includes('Kinder-Schutzfilter')) {
      explanation = t('safetyBlocked.kids')
    } else if (reason.includes('Youth-Filter') || reason.includes('Jugendschutzfilter')) {
      explanation = t('safetyBlocked.youth')
    } else if (reason.includes('reagiert nicht') || reason.includes('not responding') || reason.includes('Systemadministrator')) {
      explanation = t('safetyBlocked.systemUnavailable')
    } else {
      explanation = t('safetyBlocked.generic')
    }

    // Detect if this is an age-appropriate block (kids/youth)
    const isAgeBlock = reason.includes('Kids-Filter') || reason.includes('Kinder-Schutzfilter')
      || reason.includes('Youth-Filter') || reason.includes('Jugendschutzfilter')

    // Auto-expand Träshy
    if (!isExpanded.value) {
      isExpanded.value = true
      await nextTick()
    }

    // Add assistant message with explanation
    messages.value.push({
      id: messageIdCounter++,
      role: 'assistant',
      content: explanation
    })

    await nextTick()
    scrollToBottom()

    // For age-appropriate blocks: generate a creative alternative suggestion
    const userInput = pageContextStore.pageContent.inputText
    if (isAgeBlock && userInput) {
      await generateSafetySuggestion(userInput, reason)
    }
  }
)

/**
 * Generate a creative alternative suggestion via LLM when a kids/youth safety block occurs.
 * Two-step: immediately shows a loading message, then replaces it with the LLM response.
 */
async function generateSafetySuggestion(userInput: string, blockReason: string) {
  // Step 1: Show loading message immediately
  const loadingId = messageIdCounter++
  messages.value.push({
    id: loadingId,
    role: 'assistant',
    content: t('safetyBlocked.suggestionLoading')
  })

  await nextTick()
  scrollToBottom()

  try {
    // Step 2: Call /api/chat WITHOUT run_id (general mode, no history persistence)
    const suggestionPrompt = `The user tried to generate an image with this prompt: "${userInput}"
This was blocked by a safety filter (reason: ${blockReason}).
Suggest ONE creative alternative prompt that keeps the user's core idea but avoids the problematic aspect. Be brief (1-2 sentences). Do NOT reveal what was blocked or why. Just offer the alternative as a friendly suggestion. Respond in the language of the user's prompt.`

    const response = await axios.post('/api/chat', {
      message: suggestionPrompt
    })

    // Replace loading message in-place
    const msg = messages.value.find(m => m.id === loadingId)
    if (msg) {
      msg.content = response.data.reply
    }
  } catch (error) {
    console.error('[ChatOverlay] Error generating safety suggestion:', error)

    // Replace loading message with error
    const msg = messages.value.find(m => m.id === loadingId)
    if (msg) {
      msg.content = t('safetyBlocked.suggestionError')
    }
  }

  await nextTick()
  scrollToBottom()
}

// Watch for VLM analysis events (safe images) — add context without auto-expanding
watch(
  () => safetyStore.pendingAnalysis,
  async (analysis) => {
    if (!analysis) return

    const event = safetyStore.consumeAnalysis()
    if (!event || !event.description) return

    // Add as quiet context message (no auto-expand)
    messages.value.push({
      id: messageIdCounter++,
      role: 'assistant',
      content: `*${t('safetyBlocked.vlmSaw')}: "${event.description}"*`
    })

    if (isExpanded.value) {
      await nextTick()
      scrollToBottom()
    }
  }
)
</script>

<style scoped>
.chat-overlay {
  position: fixed;
  z-index: 10000;
  /* Smooth movement with slight overshoot for organic feel */
  transition: left 0.6s cubic-bezier(0.34, 1.56, 0.64, 1),
              right 0.6s cubic-bezier(0.34, 1.56, 0.64, 1),
              top 0.6s cubic-bezier(0.34, 1.56, 0.64, 1),
              bottom 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* Collapsed State */
.chat-toggle-icon {
  width: clamp(75px, 10vw, 100px);
  height: clamp(75px, 10vw, 100px);
  background: transparent;
  border: none;
  box-shadow: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  /* Gentle idle floating animation */
  animation: trashy-idle 4s ease-in-out infinite;
}

.chat-toggle-icon:hover {
  transform: scale(1.1);
  animation-play-state: paused;
}

.chat-toggle-icon.is-dragging {
  animation: none !important;
  cursor: grabbing;
  transform: scale(1.05);
}

.chat-toggle-icon.is-dragging .chat-icon-img {
  animation: none !important;
}

/* Idle floating animation - subtle movement */
@keyframes trashy-idle {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg);
  }
  25% {
    transform: translate(2px, -3px) rotate(1deg);
  }
  50% {
    transform: translate(-1px, -5px) rotate(-0.5deg);
  }
  75% {
    transform: translate(-2px, -2px) rotate(0.5deg);
  }
}

.chat-icon-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  /* Subtle breathing effect */
  animation: trashy-breathe 3s ease-in-out infinite;
}

@keyframes trashy-breathe {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.03);
  }
}

/* Expanded State: Chat Window */
.chat-window {
  width: 380px;
  height: 520px;
  max-height: calc(100vh - 120px); /* Stay within viewport */
  background: #1a1a1a;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #333;
}

/* Header */
.chat-header {
  background: #1a1a1a;
  padding: 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #BED882;
  position: relative;
  border-bottom: 2px solid #BED882;
}

.chat-title {
  font-weight: 700;
  font-size: 1.1rem;
  color: #BED882;
  text-shadow: none;
  flex-shrink: 0;
}

.header-trashy-icon {
  width: 40px;
  height: 40px;
  object-fit: contain;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}


.close-button {
  background: none;
  border: none;
  color: white;
  font-size: 1.8rem;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background 0.2s ease;
}

.close-button:hover {
  background: #E79EAF;
}

/* Messages Container */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  background: #0a0a0a;
}

/* Scrollbar styling */
.chat-messages::-webkit-scrollbar {
  width: 8px;
}

.chat-messages::-webkit-scrollbar-track {
  background: #1a1a1a;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 4px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: #444;
}

/* Message Bubbles */
.message {
  display: flex;
  max-width: 85%;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message.user {
  align-self: flex-end;
}

.message.assistant {
  align-self: flex-start;
}

.message-content {
  padding: 0.75rem 1rem;
  border-radius: 12px;
  font-size: 0.9rem;
  line-height: 1.4;
  word-wrap: break-word;
  white-space: pre-wrap;
}

/* Thinking (collapsible inside message bubble) */
.thinking-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  margin-bottom: 0.4rem;
  user-select: none;
}

.thinking-toggle:hover .thinking-label {
  color: #bbb;
}

.thinking-arrow {
  font-size: 0.7rem;
  color: #666;
}

.thinking-label {
  font-size: 0.75rem;
  font-style: italic;
  color: #777;
  transition: color 0.15s;
}

.thinking-text {
  font-size: 0.78rem;
  font-style: italic;
  color: #888;
  line-height: 1.4;
  padding: 0.4rem 0.5rem;
  margin-top: 0.3rem;
  border-inline-start: 2px solid #444;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.thinking-no-answer {
  font-size: 0.8rem;
  font-style: italic;
  color: #999;
  margin-bottom: 0.3rem;
}

.message.user .message-content {
  background: #BED882;
  color: white;
  border-bottom-right-radius: 4px;
}

.message.assistant .message-content {
  background: #2a2a2a;
  color: #e0e0e0;
  border-bottom-left-radius: 4px;
}

.message.greeting .message-content {
  background: #2a3a2a;
  border: 1px solid #BED882;
  color: #d4edb8;
  font-style: italic;
}

/* Loading State */
.message.loading .message-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: #2a2a2a;
  color: #999;
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(190, 216, 130, 0.3);
  border-top-color: #BED882;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-text {
  font-size: 0.85rem;
}

/* Input Container */
.chat-input-container {
  padding: 1rem;
  background: #1a1a1a;
  border-top: 1px solid #333;
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
}

.chat-input-container textarea {
  flex: 1;
  background: #0a0a0a;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 0.75rem;
  color: white;
  font-family: inherit;
  font-size: 0.9rem;
  resize: none;
  max-height: 80px;
  transition: border-color 0.2s ease;
}

.chat-input-container textarea:focus {
  outline: none;
  border-color: #BED882;
}

.chat-input-container textarea:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.send-button {
  width: 40px;
  height: 40px;
  background: #BED882;
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 1.2rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.send-button:hover:not(:disabled) {
  background: #E79EAF;
  transform: translateY(-2px);
}

.send-button:disabled {
  background: #333;
  color: #666;
  cursor: not-allowed;
  transform: none;
}

/* Mobile Responsiveness */
@media (max-width: 768px) {
  .chat-window {
    width: calc(100vw - 2rem);
    height: 60vh;
  }
}
</style>
