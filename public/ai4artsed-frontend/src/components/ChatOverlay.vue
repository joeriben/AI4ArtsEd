<!--
  The one mask, and the conversation that belongs to it where that conversation
  exists.

  There is exactly ONE mask per page and it stands here — app level, draggable,
  in the top right corner (or wherever that page leaves it room). It is HELP, on
  every page.

  Two surfaces had claimed it for themselves: the workshop and the contesting
  surface declared the mask to BE their agent, put it in the middle of the page
  and had no panel at all. Those masks are the normal help mask now, because an
  agent is what it does on the page, in text, voice and the things it makes, and
  a figure standing in for it is a second and emptier claim about the same thing.

  What follows from that:
    - The mask is drawn on every page and in every state, open or closed. It is
      the one place the agent's state is shown, and closing over it with its own
      panel would take that away exactly while something is running.
    - The panel opens AT the mask — beside or below it, following it when it is
      dragged — because it is that mask's utterance opening up and not a second
      thing that happens to sit in the same corner.
-->
<template>
  <!-- The mask GLIDES (transition on .chat-overlay below). The sign is clamped
       to the viewport against where the mask actually stands, so it is placed
       again whenever that glide comes to rest. -->
  <div class="chat-overlay" :style="overlayPositionStyle" @transitionend="placeSign">
    <!-- The mask. Draggable, double-click resets its place. -->
    <button
      ref="maskRef"
      class="chat-toggle-icon"
      :class="{ 'is-dragging': isDragging }"
      data-figure-corner
      @mousedown="startDrag"
      @click="onIconClick"
      @dblclick="resetPosition"
      :title="maskName"
      :aria-label="maskName"
    >
      <!-- The figure takes neither the pointer nor a name of its own: this
           button already carries the click, the drag, the double-click reset
           and the accessible name — which says WHICH agent stands here. -->
      <FigureMask :size="iconSize" :state="figureState" :interactive="false" />
    </button>

    <!-- The sign. A page hands over a question, not an answer, so what the
         figure says is drawn from what it already knows about the page. It
         exists only while the conversation is closed — once it is open the sign
         has done its work — and only where there is a conversation to open. -->
    <button
      v-if="!isExpanded && pageContextStore.offer?.label && !isLoading"
      ref="signRef"
      class="trashy-sign"
      :class="{ below: signBelow }"
      :style="{ '--sign-shift': `${signShift}px` }"
      :title="pageContextStore.offer.question || pageContextStore.offer.label"
      :aria-label="pageContextStore.offer.question || pageContextStore.offer.label"
      @click="takeOffer"
    >
      {{ pageContextStore.offer.label }}
    </button>

    <!-- The conversation (resizable), standing at the mask.
         v-if, not v-else: v-else binds to the nearest preceding v-if sibling,
         and the sign above is one. Written as v-else this rendered the panel on
         every page that has no sign. -->
    <!-- The panel belongs to help. It opens on a page that owns its agent for
         ONE thing: a refused upload, which is explained here and nowhere else
         on the platform. Without that exception the workshop board holds a
         child's picture back and says nothing at all — the panel was gated on
         help alone until 2026-09-04, while the watcher below already believed
         it opened everywhere. What stands there is the explanation and nothing
         else: no line to write in, no address, no greeting. -->
    <div v-if="isExpanded" class="chat-window" :style="chatWindowStyle">
      <!-- Resize handles at corners -->
      <div class="resize-handle resize-nw" @mousedown.prevent="startResize('nw', $event)"></div>
      <div class="resize-handle resize-ne" @mousedown.prevent="startResize('ne', $event)"></div>
      <div class="resize-handle resize-sw" @mousedown.prevent="startResize('sw', $event)"></div>
      <div class="resize-handle resize-se" @mousedown.prevent="startResize('se', $event)"></div>
      <!-- Header -->
      <!-- No figure in here: the one mask stands outside the panel and stays
           visible while it is open, which is where the state is read. -->
      <!-- The panel is dragged by its own head. The mask carries the same
           drag, but it stands BESIDE the panel and not on it, so a hand that
           wants to move the window reaches for the title bar and found nothing
           there until now. Both feed the same startDrag: what moves is the box
           that holds mask and panel together. -->
      <div class="chat-header" @mousedown="startDragFromHeader">
        <span class="chat-title">{{ t('trashy.title') }}</span>
        <div class="header-right">
          <!-- The address, on request. Once a conversation has been held here
               it no longer comes up by itself, and a request needs somewhere to
               be made: the arrow inside the greeting goes away with the greeting
               the moment there are messages, which is exactly when that rule
               takes effect. So the handle stands in the head, where it is there
               whatever else the panel is holding. Only on pages that say
               something about themselves - elsewhere there is nothing to turn
               over. -->
          <button
            v-if="pageHasAddress"
            class="address-handle"
            :aria-expanded="shownAddress ? 'true' : 'false'"
            :title="t('trashy.addressTooltip')"
            @click="toggleAddress"
          >{{ shownAddress ? '\u25BE' : '\u25B8' }}</button>
          <button class="close-button" @click="collapse" :title="t('trashy.closeTooltip')">×</button>
        </div>
      </div>

      <!-- Messages Container -->
      <div class="chat-messages" ref="messagesContainer">
        <!-- What the page says about itself: authored text, put up unchanged,
             the page speaking and never an answer. It is shaped so it cannot be
             mistaken for one — no bubble, full width, the page's own agent
             colour down its side. It comes up by itself the first time this
             machine opens help here; after that it is only ever shown on
             request, and the request is the line below. -->
        <button
          v-if="shownAddress"
          class="page-address"
          aria-expanded="true"
          @click="toggleAddress"
        >
          <span class="address-arrow" aria-hidden="true">&#9662;</span>
          <span class="address-halves">
            <span class="address-half"><EmphasisText :text="t(shownAddress.storyKey)" /></span>
            <span class="address-half"><EmphasisText :text="t(shownAddress.purposeKey)" /></span>
            <span v-if="shownAddress.noteKey" class="address-half">
              <EmphasisText :text="t(shownAddress.noteKey)" />
            </span>
          </span>
        </button>

        <!-- Initial greeting (only if no messages) -->
        <div v-if="messages.length === 0 && !shownAddress" class="message assistant greeting">
          <div class="message-content">
            <!-- On a page that has an address, this line is also where it is
                 found again. The arrow is the whole affordance and the greeting
                 is the button's own name: the address gets no control of its
                 own, because one already stands where it would go. -->
            <button
              v-if="pageHasAddress"
              class="address-turn"
              aria-expanded="false"
              @click="toggleAddress"
            >
              <span class="address-arrow" aria-hidden="true">&#9656;</span>{{ t('trashy.greeting') }}
            </button>
            <template v-else>{{ openingLine }}</template>
          </div>
        </div>

        <!-- Message History -->
        <div
          v-for="msg in messages"
          :key="msg.id"
          :class="['message', msg.role]"
        >
          <div class="message-content">
            <MarkdownLiteText v-if="msg.content && msg.role === 'assistant'" :text="msg.content" />
            <div v-else-if="msg.content">{{ msg.content }}</div>
            <div v-else-if="msg.thinking" class="thinking-no-answer">{{ t('trashy.noResponse') }}</div>
            <div v-if="msg.thinking" class="thinking-toggle" @click="toggleThinking(msg.id)">
              <span class="thinking-arrow">{{ expandedThinking.has(msg.id) ? '\u25BE' : '\u25B8' }}</span>
              <span class="thinking-label">{{ t('trashy.internalInference') }}</span>
            </div>
            <MarkdownLiteText
              v-if="msg.thinking && expandedThinking.has(msg.id)"
              :text="msg.thinking"
              class="thinking-text"
            />
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

      <!-- Input Container. Only where this conversation is the page's: on a
           page that brings its own agent the panel stands open for one
           explanation, and a line to write in would put a second conversation
           beside the one the page holds. -->
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
import { usePageAddressStore, type PageAddress } from '../stores/pageAddress'
import EmphasisText from './EmphasisText.vue'
import MarkdownLiteText from './MarkdownLiteText.vue'
import { usePageContextStore } from '../stores/pageContext'
import { useSafetyEventStore } from '../stores/safetyEvent'
import { useAnalysisEventStore } from '../stores/analysisEvent'
import { useUiModeStore } from '../stores/uiMode'
import { useI18n } from 'vue-i18n'
import FigureMask, { FIGURE_MASK_OVERHANG_RATIO, type FigureState } from './FigureMask.vue'
import { useSpeech, primeSpeech } from '../composables/useSpeech'
import { safetyBlockKeyForEvent } from '../composables/useGenerationStream'
import { chatTurn } from '../lib/chatTurn'
import { usePageFigureStore } from '../stores/pageFigure'

interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  thinking?: string | null
}

const props = withDefaults(
  defineProps<{
    /** The mask's name, already translated — its accessible name and tooltip. */
    figureLabel?: string
  }>(),
  { figureLabel: '' },
)

const { t, locale } = useI18n()

const pageFigure = usePageFigureStore()

/** Never empty: a button that opens a conversation has to have an accessible
 *  name even where a host forgot to pass one. */
const maskName = computed(() => props.figureLabel || t('figure.help'))

// State
const isExpanded = ref(false)
const isLoading = ref(false)
const inputMessage = ref('')
const messages = ref<Message[]>([])
let messageIdCounter = 0
const expandedThinking = ref(new Set<number>())

/**
 * Help speaks its answers, when the voice is switched on in the main menu.
 *
 * Not on request, per answer, the way Persona offers it: this is a
 * conversation, and a conversation that has to be clicked into sound is a text
 * with a button. `isAvailable` already carries the switch, so there is nothing
 * to ask here beyond it.
 */
const {
  speak,
  stop: stopSpeaking,
  isAvailable: voiceAvailable,
  loadStatus: loadVoiceStatus,
  speakingKey,
  pendingKey,
  blockedKey,
} = useSpeech()
void loadVoiceStatus()

/**
 * What the one mask shows.
 *
 * Speaking is part of it now that help speaks. The three speech keys are the
 * platform's single mechanism for that (composables/useSpeech, read the same way
 * resona.vue reads them); waiting for an ANSWER still comes from this
 * component's own loading flag, and the platform voice's waiting reaches it too
 * — an address that takes seconds must not leave the figure sitting idle.
 */
const figureState = computed<FigureState>(() => {
  if (speakingKey.value !== null) return 'uttering'
  if (blockedKey.value !== null) return 'held'
  if (isLoading.value || pendingKey.value !== null || pageFigure.voiceWaiting) return 'waiting'
  return 'idle'
})

// Closing the panel ends the voice with it. Anything else would leave a
// sentence being spoken by a window that is no longer there.
watch(isExpanded, open => { if (!open) stopSpeaking() })

function toggleThinking(messageId: number) {
  const s = new Set(expandedThinking.value)
  if (s.has(messageId)) s.delete(messageId)
  else s.add(messageId)
  expandedThinking.value = s
}

// Drag state
const isDragging = ref(false)
const userPosition = ref<{ right: number; bottom: number } | null>(null)

// Resize state
const RESIZE_STORAGE_KEY = 'trashy-size'
const chatSize = ref({ width: 380, height: 520 })
const MIN_WIDTH = 300
const MIN_HEIGHT = 350
const MAX_WIDTH = 700
const MAX_HEIGHT = 900
const isResizing = ref(false)

const savedSize = localStorage.getItem(RESIZE_STORAGE_KEY)
if (savedSize) {
  try {
    const parsed = JSON.parse(savedSize)
    chatSize.value = {
      width: Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, parsed.width || 380)),
      height: Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, parsed.height || 520))
    }
  } catch { /* ignore */ }
}

/** How far the panel stands off the mask. Small on purpose: they are one thing,
 *  and a wide gap makes them read as two objects that happen to be near each
 *  other. */
const PANEL_GAP = 8

/** What the panel would measure if nothing stood in its way: its stored size,
 *  held inside the viewport so it can never be cut off at an edge. What it
 *  ACTUALLY measures is panelBox, which may take it down further to keep it off
 *  the mask. */
const panelSize = computed(() => ({
  w: Math.min(chatSize.value.width, viewportWidth.value - 2 * CHAT_MIN_MARGIN),
  h: Math.min(chatSize.value.height, viewportHeight.value - 120),
}))

/**
 * The mask's box in viewport coordinates, derived from the very offsets the
 * overlay is positioned with — so the panel is placed against where the mask
 * ACTUALLY is: dragged, resting, or sent somewhere by the page's own focusHint.
 * The overlay shrink-wraps the mask, so its top-left corner IS this point.
 */
const maskRect = computed(() => {
  const size = iconSize.value
  return {
    left: viewportWidth.value - collapsedRight.value - size,
    top: viewportHeight.value - collapsedBottom.value - size,
    size,
  }
})

/**
 * Where the panel stands, as an offset from the mask's own top-left corner.
 *
 * It is a child of the overlay, so this offset is all it needs and the two move
 * as one: a drag moves the overlay and carries the panel with it, with no frame
 * in which they are apart.
 *
 * Below the mask by default, left-aligned with it; above it when there is no
 * room below; beside it when there is room on neither. The panel never covers
 * the mask — the mask is where its state is shown, and it has to stay readable
 * while the panel is open. Only the axis that is NOT holding the two together
 * is clamped into the viewport, so clamping slides the panel ALONG the mask and
 * can never detach it.
 */
/** Which side of the mask the panel is laid on. */
type Side = 'below' | 'above' | 'right' | 'left'

const panelBox = computed(() => {
  const m = maskRect.value
  const vw = viewportWidth.value
  const vh = viewportHeight.value

  // The four strips of free room around the mask, each already minus the gap it
  // keeps to the mask and the margin it keeps to the viewport edge.
  const strip = {
    below: vh - CHAT_MIN_MARGIN - (m.top + m.size + PANEL_GAP),
    above: m.top - PANEL_GAP - CHAT_MIN_MARGIN,
    right: vw - CHAT_MIN_MARGIN - (m.left + m.size + PANEL_GAP),
    left: m.left - PANEL_GAP - CHAT_MIN_MARGIN,
  }

  /** The panel laid into one strip, taken down to what that strip holds. */
  function lay(side: Side) {
    const vertical = side === 'below' || side === 'above'
    const w = vertical ? panelSize.value.w : Math.min(panelSize.value.w, strip[side])
    const h = vertical ? Math.min(panelSize.value.h, strip[side]) : panelSize.value.h
    // Only the axis that is NOT holding the two together is slid along, so
    // sliding can move the panel BESIDE the mask but can never detach it.
    const alongL = Math.max(CHAT_MIN_MARGIN, Math.min(vw - w - CHAT_MIN_MARGIN, m.left))
    const alongT = Math.max(CHAT_MIN_MARGIN, Math.min(vh - h - CHAT_MIN_MARGIN, m.top))
    if (side === 'below') return { w, h, left: alongL, top: m.top + m.size + PANEL_GAP }
    if (side === 'above') return { w, h, left: alongL, top: m.top - PANEL_GAP - h }
    if (side === 'right') return { w, h, left: m.left + m.size + PANEL_GAP, top: alongT }
    return { w, h, left: m.left - PANEL_GAP - w, top: alongT }
  }

  // Below by default, then above, then beside — the order a hand reads in. The
  // first side that holds the panel WHOLE wins.
  const order: Side[] = ['below', 'above', 'right', 'left']
  const fits = (side: Side) =>
    (side === 'below' || side === 'above' ? panelSize.value.h : panelSize.value.w) <= strip[side]
  const whole = order.find(fits)

  // Nowhere holds it whole. The panel is then made smaller — it is NOT laid over
  // the mask. The mask is the one place the machine's state is shown, and it has
  // to stay readable while the panel is open; a panel that covers it takes that
  // away exactly while something is running. Of the four sides, the one that
  // leaves the largest panel wins.
  const side: Side = whole ?? order.reduce<Side>((best, s) => {
    const a = lay(s), b = lay(best)
    return a.w * a.h > b.w * b.h ? s : best
  }, 'below')

  const box = lay(side)
  return {
    w: Math.max(0, box.w),
    h: Math.max(0, box.h),
    left: box.left - m.left,
    top: box.top - m.top,
    side,
  }
})

const chatWindowStyle = computed(() => ({
  width: `${panelBox.value.w}px`,
  height: `${panelBox.value.h}px`,
  left: `${panelBox.value.left}px`,
  top: `${panelBox.value.top}px`,
}))

let resizeCorner = ''
let resizeStart = { x: 0, y: 0, w: 0, h: 0 }

function startResize(corner: string, event: MouseEvent) {
  isResizing.value = true
  resizeCorner = corner
  resizeStart = { x: event.clientX, y: event.clientY, w: chatSize.value.width, h: chatSize.value.height }
  document.body.style.cursor = corner === 'nw' || corner === 'se' ? 'nwse-resize' : 'nesw-resize'
  window.addEventListener('mousemove', onResize)
  window.addEventListener('mouseup', endResize)
}

function onResize(event: MouseEvent) {
  const dx = event.clientX - resizeStart.x
  const dy = event.clientY - resizeStart.y

  let newW = resizeStart.w
  let newH = resizeStart.h

  if (resizeCorner.includes('e')) newW = resizeStart.w + dx
  if (resizeCorner.includes('w')) newW = resizeStart.w - dx
  if (resizeCorner.includes('s')) newH = resizeStart.h + dy
  if (resizeCorner.includes('n')) newH = resizeStart.h - dy

  chatSize.value = {
    width: Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, newW)),
    height: Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, newH))
  }
}

function endResize() {
  isResizing.value = false
  document.body.style.cursor = ''
  localStorage.setItem(RESIZE_STORAGE_KEY, JSON.stringify(chatSize.value))
  window.removeEventListener('mousemove', onResize)
  window.removeEventListener('mouseup', endResize)
}

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

// How far down the top-left corner is already taken, in viewport pixels. What
// stands there is .app-header — the shell's own header, with the UNESCO Chair
// logo and the platform title, present on every page — and the figure rests
// below it.
//
// The platform voice's origin used to be measured here as well and no longer
// exists: that origin IS this mask now, so there is nothing left in the corner
// for it to yield to.
//
// Queried rather than keyed to a list of routes, and 0 when the header is not
// there, which puts the figure at the plain resting margin.
const occupiedTop = ref(0)

/** Where the figure rests, as the top left corner of its box in the viewport.
 *  A corner where it is help; the middle of the page where the page's own agent
 *  is what it is. */
const restingLeft = ref(0)
const restingTop = ref(0)

function measureOccupiedTop(): void {
  const el = document.querySelector('.app-header')
  let top = el ? el.getBoundingClientRect().bottom : 0
  // And below any further band that runs the whole width beneath it. The canvas
  // hangs its own toolbar there, and a band spanning the screen leaves NEITHER
  // corner free — a figure that only ever chose between two corners would sit
  // on it whichever it picked. Asked at the middle of the screen, because that
  // is what "the whole width" means, and repeated so a second band under the
  // first is found too. Three is a bound, not a belief about layouts.
  for (let i = 0; i < 3; i++) {
    const band = document
      .elementsFromPoint(viewportWidth.value / 2, top + 4)
      .find((e) => {
        if (e.closest('.chat-overlay, .pvl-layer, .resona-voice')) return false
        const b = e.getBoundingClientRect()
        return b.width > viewportWidth.value * 0.9 && b.height <= 220 && b.top <= top + 4
      })
    if (!band) break
    const bottom = band.getBoundingClientRect().bottom
    if (bottom <= top) break
    top = bottom
  }
  occupiedTop.value = top
  const spot = restingSpot()
  restingLeft.value = spot.left
  restingTop.value = spot.top
}

/**
 * Where the resting figure stands: the top right corner, unless the page
 * already has something there.
 *
 * The right corner is the platform owner's choice and the default. It is not
 * free everywhere, though — the canvas puts its run and batch buttons there,
 * the comparison page a card — and a figure sitting on a page's own controls is
 * worse than a figure in the other corner. So both candidate boxes are tested
 * against what the page actually renders, and the right one wins only if it is
 * clear. Failing that, the search walks down the right edge, then down the
 * left, and only then gives up and takes the right corner regardless: the
 * figure is draggable, and "the same place unless the page has taken it" is a
 * rule a person can learn.
 *
 * Asked at five points of the candidate box rather than by walking the page.
 * Document order is no guide to what is in a corner — the canvas has its whole
 * module list before its toolbar — so a scan has to be bounded by node count to
 * stay cheap and is then wrong on exactly the pages that need it. Five hit
 * tests are bounded by construction.
 *
 * What a hit has to be to count: not this overlay, not spoken words (the voices
 * place their sentences in whatever ground a page leaves free, and the figure
 * they are drawn from must not be chased out of a corner by them), not ground
 * — a surface the size of the page is what a page is MADE of, and the workshop
 * board carries the platform's own background colour — and something that
 * actually paints: a control, a coloured or pictured surface, or text with
 * nothing else inside it.
 *
 * Tested against the figure's own box, not against what its widest state
 * paints. The brackets are thin arcs that exist only while it speaks, and an
 * edge strip clipping nine pixels of the outermost one is no reason to move the
 * figure across the screen. The mask itself sitting on a control is.
 */
function restingSpot(): { left: number; top: number } {
  const vw = viewportWidth.value
  const vh = viewportHeight.value
  const size = iconSize.value
  const overhang = Math.ceil(size * FIGURE_MASK_OVERHANG_RATIO)
  const base = occupiedTop.value + RESTING_MARGIN
  const isControl = (el: Element): boolean =>
    el.matches('button, a, input, select, textarea, [role="button"]')
  const paints = (el: Element): boolean => {
    if (el.matches('button, a, input, select, textarea, img, video, [role="button"]')) return true
    const cs = getComputedStyle(el)
    if (cs.visibility === 'hidden' || cs.opacity === '0') return false
    if (cs.backgroundImage !== 'none') return true
    const bg = cs.backgroundColor
    if (bg && bg !== 'transparent' && !bg.startsWith('rgba(0, 0, 0, 0')) return true
    // A drawn border makes a box, and a box is furniture even when nothing is
    // filled in behind it — the comparison page's help card is exactly that,
    // and without this the figure lands in the middle of its text.
    if (cs.borderTopStyle !== 'none' && parseFloat(cs.borderTopWidth) > 0) return true
    return el.childElementCount === 0 && (el.textContent || '').trim().length > 0
  }
  /** How many of the five probe points are taken. `controlsOnly` asks the
   *  weaker question: not "is this spot free" but "is anything here that a hand
   *  reaches for". Counted rather than answered yes/no, because a page can be
   *  full everywhere and the figure still has to stand somewhere — then the
   *  fewest taken points is what makes the least-bad place findable. */
  const blocked = (left: number, top: number, controlsOnly = false): number => {
    const inset = 8
    const probes: [number, number][] = [
      [left + inset, top + inset],
      [left + size - inset, top + inset],
      [left + inset, top + size - inset],
      [left + size - inset, top + size - inset],
      [left + size / 2, top + size / 2],
    ]
    let taken = 0
    for (const [x, y] of probes) {
      for (const el of document.elementsFromPoint(x, y)) {
        if (el === document.body || el === document.documentElement) continue
        if (el.closest('.chat-overlay, .pvl-layer, .resona-voice')) continue
        const b = el.getBoundingClientRect()
        if (b.width > vw * 0.7 && b.height > vh * 0.5) continue
        if (controlsOnly ? !isControl(el) : !paints(el)) continue
        taken++
        break
      }
    }
    return taken
  }
  const clear = (left: number, top: number, controlsOnly = false): boolean =>
    blocked(left, top, controlsOnly) === 0
  // Down the right edge first, then down the left, in steps, as far down as the
  // figure still fits. A corner is the goal, but it is not always to be had: the
  // comparison page fills both of them with cards, and a figure that insists on
  // a corner then sits on somebody's text. Below the cards, still at the edge,
  // is a better place than either corner — and it is still the SAME place every
  // time, which is what makes it findable.
  //
  // The walk used to stop at half the screen. On the flow logic map at 1280 both
  // edge columns run from under the header to past that half, so it found
  // nothing, and every later walk failed too — the figure ended up in the give-up
  // corner, which on that page IS the top right box. The edge is free further
  // down, below the map. A place lower at the edge with nothing drawn on it
  // beats a place higher with text under it, which is the order the three walks
  // below already express.
  const rightEdge = vw - RESTING_MARGIN - overhang - size
  const leftEdge = RESTING_MARGIN + overhang
  const limit = Math.max(base, vh - RESTING_MARGIN - size)
  // Which end of the edge the walks below start from — see RESTING_FROM_BOTTOM.
  // Only the ORDER changes here; every clearance test still decides.
  const tops: number[] = []
  for (let t = base; t <= limit; t += 32) tops.push(t)
  if (RESTING_FROM_BOTTOM.has(route.path)) tops.reverse()
  for (const left of [rightEdge, leftEdge]) {
    for (const t of tops) {
      if (clear(left, t)) return { left, top: t }
    }
  }
  // Nothing free at all - the comparison page at a narrow window is full to both
  // edges. The corner taken regardless used to be the answer here, and on the
  // page whose field sits high that corner IS the field: the figure then stood
  // over its symbols and took their clicks, which is the one thing this search
  // exists to prevent. So the walk runs a second time asking only about what a
  // hand reaches for. Standing on a line of text is a poorer place, not a broken
  // one; standing on a control is broken.
  // While that walk runs, the emptiest place it passes is remembered, so that a
  // page which is full everywhere still gets a considered answer instead of the
  // corner (see the give-up below).
  let sparest: { left: number; top: number; taken: number } | null = null
  const remember = (left: number, top: number, taken: number) => {
    if (!sparest || taken < sparest.taken) sparest = { left, top, taken }
  }
  for (const left of [rightEdge, leftEdge]) {
    for (const t of tops) {
      const taken = blocked(left, t, true)
      if (taken === 0) return { left, top: t }
      remember(left, t, taken)
    }
  }
  // And then INWARD from each edge, because a page can be full at both edges and
  // still have a clear strip a little further in. The flow logic page is exactly
  // that: three columns of boxes across a map a thousand pixels wide, centred in
  // a work area two hundred wider, so the strip between the left rail and the
  // first column is free the whole way down while both edge columns are boxes
  // from top to bottom. Every box there carries `role="button"`, so the two
  // walks above reject the whole height and the give-up corner puts the figure
  // on the top right box — a hundred-pixel square taking that box's presses,
  // which is the fault of boxes not opening on every press all over again with
  // the sign reversed.
  //
  // Bounded to a quarter of the width and stepped coarsely, and it asks the
  // STRONG question: a place this far from an edge is only worth taking if
  // nothing at all is drawn there.
  const inward = Math.round(vw * 0.25)
  const inwardLefts: number[] = []
  for (let d = 40; d <= inward; d += 40) inwardLefts.push(rightEdge - d, leftEdge + d)
  for (const left of inwardLefts) {
    for (const t of tops) {
      if (clear(left, t)) return { left, top: t }
    }
  }
  // Inward once more, now with the weaker question. At 1024 the map fills both
  // edges from the header to the legend and the legend's own chips are buttons
  // too, so nothing on either edge is free of controls; the strip between the
  // rail and the first column is, and it only carries the rail's edge — drawn,
  // but nothing a hand reaches for.
  for (const left of inwardLefts) {
    for (const t of tops) {
      const taken = blocked(left, t, true)
      if (taken === 0) return { left, top: t }
      remember(left, t, taken)
    }
  }
  // Full everywhere. Then the emptiest of everything walked, and only if not one
  // spot was even looked at, the corner. The corner alone used to be the answer
  // here, and on a page whose boxes reach it that is the one outcome this whole
  // search exists to prevent.
  const spot = sparest as { left: number; top: number; taken: number } | null
  return spot ? { left: spot.left, top: spot.top } : { left: rightEdge, top: base }
}

function onWindowResize() {
  viewportWidth.value = window.innerWidth
  viewportHeight.value = window.innerHeight
  searchExhausted = false
  // A new width is a new page as far as the corners are concerned: what fitted
  // beside the figure may not any more, and the other corner may have come free.
  measureOccupiedTop()

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

/**
 * Measure the corner again while the page is filling it.
 *
 * Which corner is free depends on what the VIEW renders, and a view renders in
 * its own time: the canvas builds its toolbar after its editor is up, the
 * comparison page its card, the workshop its board. Measured once at the next
 * frame, the figure decides against an empty page and stays in a corner that is
 * about to be taken; measured only late, it stands in the wrong one until then.
 * So: at the next frame, and again on a few beats while the page settles. The
 * test itself is five hit tests, so repeating it costs almost nothing, and the
 * last beat is late enough for an editor that builds its toolbar after itself.
 */
/**
 * And again once the page has been scrolled under it.
 *
 * The figure is fixed and the page is not, so a corner that was clear when it
 * was measured is a box a moment later — every search above tests what stands
 * there NOW, and nothing tested it again once the content moved. On the flow
 * logic page that is a hundred-pixel square resting on one of the four boxes of
 * a band, and the boxes are `role="button"`, so `clear()` would have rejected
 * that spot outright had it been asked. The symptom was boxes opening
 * irregularly, not on every click, sometimes only on the third or fourth:
 * whichever box the figure happened to be lying on was the one that did not
 * answer. Measured after the scrolling stops, not during it, and in the capture
 * phase because the page scrolls in its own container and not in the window.
 */
/**
 * When to look again after the ground has moved: once as soon as it has come to
 * rest, and once more well after that.
 *
 * The second beat is not caution, it is a measurement. A press can start an
 * ANIMATION — the flow boxes take 0.42 s to fold back — and at 160 ms what
 * stands under the figure is a box halfway between two places. The search then
 * picks a spot that is clear for that one moment and is a box when the movement
 * ends, which is precisely the fault it exists to prevent. 720 ms is past the
 * longest of those movements.
 */
const SETTLE_AT = [160, 720]
let settleTimers: ReturnType<typeof setTimeout>[] = []

/**
 * Whether the figure is standing on something a hand reaches for, right now.
 *
 * The weaker of the two questions the search above asks, at the five points it
 * asks them, and asked of where the figure ACTUALLY is. It is the whole
 * condition for moving after a scroll: a figure that re-ran the full search on
 * every scroll would keep walking back up to its preferred corner and away
 * again, and a figure that moves while nothing is wrong is worse company than
 * one that stays.
 */
function standsOnAControl(): boolean {
  const size = iconSize.value
  const left = viewportWidth.value - collapsedRight.value - size
  const top = viewportHeight.value - collapsedBottom.value - size
  const inset = 8
  const probes: [number, number][] = [
    [left + inset, top + inset],
    [left + size - inset, top + inset],
    [left + inset, top + size - inset],
    [left + size - inset, top + size - inset],
    [left + size / 2, top + size / 2],
  ]
  for (const [x, y] of probes) {
    for (const el of document.elementsFromPoint(x, y)) {
      if (el.closest('.chat-overlay, .pvl-layer, .resona-voice')) continue
      if (el.matches('button, a, input, select, textarea, [role="button"]')) return true
    }
  }
  return false
}

function afterScrollSettles(): void {
  // Where a person has put it, it stays. Stepping aside is the platform's rule
  // for its own resting place, not a licence to undo a drag.
  if (userPosition.value) return
  if (searchExhausted) return
  if (!standsOnAControl()) return
  const wasLeft = restingLeft.value
  const wasTop = restingTop.value
  measureOccupiedTop()
  // Came back with the place it was already standing in, while that place is
  // occupied: this layout has nothing better, and asking again on every press
  // would run the whole walk twice per press for the rest of the page's life.
  if (restingLeft.value === wasLeft && restingTop.value === wasTop) searchExhausted = true
}

/** Cleared by anything that can change the answer: a new page, a new width. */
let searchExhausted = false

/**
 * Scrolled, or pressed anywhere.
 *
 * A press is the other way the ground under a fixed figure moves: the Latent
 * Lab folds its column of instruments away with one button and everything to
 * the right of it slides over, a tab exchanges a page's whole content without
 * touching the route, a panel opens. None of that is a scroll, a resize or a
 * route change, so nothing asked again — and on the overview map, folding the
 * column away slides the map left until it is under the figure, whose hundred
 * pixels then take one box's presses. The test is five hit tests, so asking
 * after every press costs nothing worth counting, and it only ever MOVES the
 * figure when it is standing on something a hand reaches for.
 */
function onAnyScroll(): void {
  settleTimers.forEach(clearTimeout)
  settleTimers = SETTLE_AT.map(ms => setTimeout(afterScrollSettles, ms))
}

const REMEASURE_AT = [300, 900, 2000, 3500]
let remeasureTimers: ReturnType<typeof setTimeout>[] = []
function remeasureSoon(): void {
  searchExhausted = false
  requestAnimationFrame(() => measureOccupiedTop())
  remeasureTimers.forEach(clearTimeout)
  remeasureTimers = REMEASURE_AT.map((ms) => setTimeout(measureOccupiedTop, ms))
}

onMounted(() => {
  measureOccupiedTop()
  void nextTick(remeasureSoon)
  window.addEventListener('resize', onWindowResize)
  document.addEventListener('scroll', onAnyScroll, { capture: true, passive: true })
  document.addEventListener('click', onAnyScroll, { capture: true })
  // The page loaded into is a first call too. Without this the rule would only
  // start working at the first route CHANGE, and the page somebody actually
  // arrives on — the one they were sent a link to — would say nothing.
  greetPage(route.path)
})
onUnmounted(() => {
  if (signSettle) clearTimeout(signSettle)
  remeasureTimers.forEach(clearTimeout)
  window.removeEventListener('resize', onWindowResize)
  document.removeEventListener('scroll', onAnyScroll, { capture: true })
  document.removeEventListener('click', onAnyScroll, { capture: true })
  settleTimers.forEach(clearTimeout)
})

// Refs
const messagesContainer = ref<HTMLElement | null>(null)
const inputTextarea = ref<HTMLTextAreaElement | null>(null)

// Session context
const { currentSession } = useCurrentSession()

// Page context (Träshy knows about current page state)
// Using Pinia store instead of inject (works across component tree siblings)
const pageContextStore = usePageContextStore()
const route = useRoute()

// A new page can lay out the header differently (it wraps at narrow widths), so
// the corner is re-measured after the incoming view has rendered — nextTick for
// the DOM, one frame for its layout. Declared here because the watcher reads
// `route` immediately.
watch(
  () => route.path,
  async () => {
    await nextTick()
    remeasureSoon()
  },
)

// A tab inside a page is a new page as far as the corners are concerned. The
// comparison hub exchanges its whole content without changing the route, so the
// watcher above never fires there: the figure kept the spot it had found for the
// tab before, and on the tab whose input field sits high that spot is the field
// - and with it, since 2026-08-17, the four symbols in the field's corner, whose
// clicks the figure then takes. What the incoming content says about itself is
// the signal that it IS other content.
watch(
  () => pageContextStore.activeViewType,
  async () => {
    await nextTick()
    remeasureSoon()
  },
)

// ---------- What the page says about itself ----------
//
// The address is AUTHORED text, held as two i18n keys in stores/pageAddress and
// put on screen unchanged. Nothing here sends it anywhere: it is not a message,
// it never enters `messages`, and it therefore never reaches /api/chat and is
// never spoken — the speaking in this component happens to replies alone, in
// sendMessage.
const pageAddress = usePageAddressStore()

/** The address standing at the top of this panel, or null.
 *
 *  Held rather than derived from the route, because it is a thing that has been
 *  turned ON — by the first opening of the panel on a page that still owes its
 *  address, or by a hand afterwards — and the route alone cannot say which. */
const shownAddress = ref<PageAddress | null>(null)

/** Whether this page says anything about itself at all. Where it does not,
 *  nothing about this panel changes: no arrow, nothing to turn over. */
const pageHasAddress = computed(() => pageAddress.addressFor(route.path) !== null)

function toggleAddress() {
  shownAddress.value = shownAddress.value ? null : pageAddress.addressFor(route.path)
}

/** What the panel opens with on a page that says nothing about itself.
 *
 *  The platform's greeting stood there, and it reads as though the place had
 *  been covered — of the 37 places of the platform eleven carry an address
 *  (stores/pageAddress.ts), so it stood in for one nearly everywhere. The panel
 *  now says which of the two it is. The greeting stays on the start page only. */
const openingLine = computed(() =>
  route.path === '/' ? t('trashy.greeting') : t('trashy.noPageInfo'),
)

// An address belongs to the page that says it. Left standing across a route
// change it would introduce the page the visitor has just left.
watch(() => route.path, () => { shownAddress.value = null })

/**
 * What help does when a page comes up.
 *
 * A page this machine has not been on before opens the panel by itself with
 * what that page says about itself. A page it has been on does not — and if the
 * panel was standing open from the page before, it closes, because what was in
 * it belonged to that page.
 *
 * The one exception is an answer still coming in. Closing the panel on a route
 * change would cut a running request off mid-sentence and leave no trace of it,
 * which is a worse thing than a panel that stays open one page too long.
 */
function greetPage(path: string): void {
  if (pageAddress.unseenAddressFor(path)) {
    void expand()
    return
  }
  if (isExpanded.value && !isLoading.value) collapse()
}

// Declared after the watcher that clears the address, so it runs after it: Vue
// calls watchers in the order they were set up, and this one puts the new page's
// address in place.
watch(() => route.path, path => greetPage(path))

// Safety event store — auto-expand Träshy when safety blocks occur
const safetyStore = useSafetyEventStore()

// Analysis event store — expand Träshy with reflection when image analysis completes
const analysisEventStore = useAnalysisEventStore()
const uiModeStore = useUiModeStore()

// Build draft context string for LLM
const draftContextString = computed(() => {
  return pageContextStore.formatForLLM(route.path)
})

/** The runs this page is holding, named so the model can ask for one. A
 *  surface that produces several at once (the comparisons) names them itself;
 *  everywhere else it is the one run of the current session. */
const surfaceMedia = computed(() => {
  if (pageContextStore.ephemeral) return []
  const named = pageContextStore.pageContent.surfaceMedia ?? []
  if (named.length) return named.map(m => ({ run_id: m.runId, label: m.label }))
  const runId = currentSession.value.runId || ''
  if (!runId) return []
  const label = pageContextStore.pageContent.selectedConfig
    || pageContextStore.activeViewType
    || 'this page'
  return [{ run_id: runId, label }]
})

// Chat window dimensions (reactive — chatSize is resizable)
const CHAT_MIN_MARGIN = 10 // Minimum margin from viewport edges
const ICON_SIZE = 66 // Maximum icon size (clamp max), see iconSize

/** Blank space the resting figure keeps to the top and right edges. Measured to
 *  what the figure PAINTS, not to its layout box — see restingPlace. */
const RESTING_MARGIN = 32

/**
 * Routes whose walk down an edge runs the other way — from the bottom up.
 *
 * Top-down is right almost everywhere: a figure high at an edge is the one the
 * eye finds. It is wrong on a page whose content hangs from the top and leaves
 * the ground under it free. There the first free point from ABOVE is whatever
 * gap the layout happens to leave between two boxes, so the same page at a
 * different window height puts the figure somewhere else each time — and often
 * on a box: the flow logic map at 1180 x 760 put it across „Block" and „Klang zu
 * Text zu Klang", and at 1440 x 900 in the clear ground below the map. Searched
 * from below, that ground is the FIRST hit and the place is the same at every
 * size. On this route that free ground is where Help is sent preferentially.
 *
 * A property of the route and not a coordinate: nothing here says WHERE the
 * figure stands, only which end of the edge is looked at first.
 */
const RESTING_FROM_BOTTOM = new Set(['/latent-lab/overview'])

// What the icon actually measures. FigureMask takes its size in px, so the
// clamp is computed here instead — off the reactive viewport width, so it
// still follows a window resize.
//
// The step of the free signs on the board, --flow-glyph-fixture in
// assets/flow-stage.css: clamp(3rem, 2.4vw + 1.6rem, 4.125rem), i.e. 48 to
// 66 px, the same size in every mode. At clamp(75px, 10vw, 100px), and still
// at 1.25 x this step, it covered too much of the page.
// That sheet is loaded only by the pages that use it, so the step is restated
// here in px.
const iconSize = computed(() =>
  Math.floor(Math.max(48, Math.min(ICON_SIZE, viewportWidth.value * 0.024 + 25.6))),
)

// Where the figure rests when nobody has moved it: top left, below whatever
// already stands in that corner, and far enough in that even its widest state
// is not cut off. Expressed in the right/bottom offsets this has always
// positioned with, so every position already stored under 'trashy-position'
// keeps exactly the meaning it was written with and the clamps below stay the
// ones that were written for it.
//
// The margin is kept to what the figure PAINTS. An uttering figure's brackets
// reach FIGURE_MASK_OVERHANG_RATIO × size past the layout box on each side, and
// the box never signals it — a figure placed 32px in by its box would have its
// outer bracket clipped at x = 0 the moment it spoke. The overhang is asked of
// the component rather than assumed here, so a change to the glyph's viewBox
// moves this with it.
//
// Pixels, not a focusHint: the hint is a percentage of the viewport, and a
// percentage cannot hold a constant margin at an edge — clamping flattens it
// into the corner.
//
// Unconditional: this is where the figure rests on EVERY page. A dozen views
// still publish a focusHint, which used to move the figure next to whatever
// that view was pointing at — a percentage of the viewport, so it carried no
// margin and no knowledge of the overhang, and on the canvas it put the figure
// on top of the module list with its outer bracket 41px off the left edge. The
// figure now has one resting place and is moved by hand or not at all; the
// hints are left in the pages, unread by this.
// Top RIGHT where the figure is help: the corner the platform owner chose after
// seeing both — or the left one, or lower down the edge, where the page already
// stands in it. The MIDDLE of the page where the page brings its own agent, so
// that the machine one is speaking to is where one is looking. Both come from
// restingSpot, which is what keeps the margin to what the figure PAINTS: the
// overhang belongs in it, or the outer bracket is cut off at the viewport edge
// the moment the figure speaks.
const restingPlace = computed(() => ({
  right: viewportWidth.value - iconSize.value - restingLeft.value,
  bottom: viewportHeight.value - iconSize.value - restingTop.value,
}))

// How far the COLLAPSED icon sits from the right and bottom edges, clamped.
// Their own computeds because the style, the sign hanging over the icon and the
// start of a drag all have to agree on where the icon is, and two clamps for
// one position is how they end up disagreeing.
const collapsedRight = computed(() => {
  const vw = viewportWidth.value
  const maxRight = vw - ICON_SIZE - CHAT_MIN_MARGIN
  const requested = userPosition.value ? userPosition.value.right : restingPlace.value.right
  return Math.max(CHAT_MIN_MARGIN, Math.min(maxRight, requested))
})

const collapsedBottom = computed(() => {
  const vh = viewportHeight.value
  const maxBottom = vh - ICON_SIZE - CHAT_MIN_MARGIN
  const requested = userPosition.value ? userPosition.value.bottom : restingPlace.value.bottom
  return Math.max(CHAT_MIN_MARGIN, Math.min(maxBottom, requested))
})

/** Height the sign needs over the icon; under that it hangs below instead. */
const SIGN_CLEARANCE = 44

/** Träshy dragged to the top of the screen has nothing above to hold up. */
const signBelow = computed(
  () => viewportHeight.value - collapsedBottom.value - ICON_SIZE < SIGN_CLEARANCE,
)

/**
 * The sign is centred over the mask, and the mask stands at an edge. A sign
 * wider than the room beside it would be cut off there, so it is moved back in
 * — the lean and the wave stay, only the centre moves.
 *
 * Both places are MEASURED and not derived from collapsedRight: a page that
 * sets a focusHint puts the mask somewhere that computed does not describe, and
 * the sign then moved the wrong way.
 */
const signRef = ref<HTMLElement | null>(null)
const maskRef = ref<HTMLElement | null>(null)
const signShift = ref(0)

function placeSign() {
  const sign = signRef.value
  const mask = maskRef.value
  if (!sign || !mask) {
    signShift.value = 0
    return
  }
  const m = mask.getBoundingClientRect()
  const centre = m.left + m.width / 2
  const half = sign.offsetWidth / 2
  const overLeft = centre - half - CHAT_MIN_MARGIN
  const overRight = centre + half - (viewportWidth.value - CHAT_MIN_MARGIN)
  signShift.value = overLeft < 0 ? -overLeft : overRight > 0 ? -overRight : 0
}

/** The mask GLIDES to a new place over 0.6s (the transition on .chat-overlay),
 *  so measuring at nextTick clamps the sign against the place it is leaving. */
let signSettle: ReturnType<typeof setTimeout> | null = null

function schedulePlaceSign() {
  void nextTick(placeSign)
  if (signSettle) clearTimeout(signSettle)
  signSettle = setTimeout(placeSign, 650)
}

watch(
  () => [
    pageContextStore.offer?.label,
    isExpanded.value,
    viewportWidth.value,
    collapsedRight.value,
    collapsedBottom.value,
    isDragging.value,
  ] as const,
  schedulePlaceSign,
  { immediate: true },
)

// Where the MASK stands, open or closed — dragged position, resting place or
// page hint, all three and their clamping in the two computeds above. The panel
// no longer has a place of its own: it is a child of this box and is placed
// against it by panelOffset, so it follows the mask wherever the mask goes and
// a page that sets a focusHint still decides for both.
const overlayPositionStyle = computed(() => ({
  right: `${collapsedRight.value}px`,
  left: 'auto',
  bottom: `${collapsedBottom.value}px`,
  top: 'auto',
}))

// Double-click to reset to default position
function resetPosition() {
  userPosition.value = null
  localStorage.removeItem(STORAGE_KEY)
}

// Drag handlers - track if we actually dragged (vs just clicked)
let dragStartMouse = { x: 0, y: 0 }
let dragStartPosition = { right: 0, bottom: 0 }
let hasDragged = false

// Draggable open as well as closed: the panel is a child of this box, so it
// travels with the mask, and a conversation you cannot move out of the way is
// the reason people close one.
/** The same drag, taken at the panel's title bar. A mousedown that starts on a
 *  control in the header belongs to that control, not to the drag. */
function startDragFromHeader(event: MouseEvent) {
  if ((event.target as HTMLElement).closest('button')) return
  startDrag(event)
}

function startDrag(event: MouseEvent) {
  hasDragged = false
  isDragging.value = true

  // Store mouse start position
  dragStartMouse = { x: event.clientX, y: event.clientY }

  // Store current icon position — read from the same computeds the style uses,
  // so a figure that has never been dragged does not jump to a different place
  // the moment it is grabbed.
  dragStartPosition = { right: collapsedRight.value, bottom: collapsedBottom.value }

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
// Taking the sign asks the page's question in the visitor's name, so the answer
// arrives as an answer and not as a text the page was hiding.
async function takeOffer() {
  if (isLoading.value) return
  const asked = pageContextStore.offer?.question
  // A sign without a question opens the conversation and says nothing in the
  // visitor's name: there are no prepared lines to click.
  if (!asked) {
    await expand()
    return
  }

  // Somebody who typed something and then took the sign meant to keep both.
  const draft = inputMessage.value.trim()

  // Assigned BEFORE expanding: expand() awaits loadChatHistory(), which has no
  // timeout — a stalled history request left the window open, the sign gone and
  // the question never asked.
  inputMessage.value = draft ? `${draft}\n\n${asked}` : asked
  await expand()
  await sendMessage()
}

/**
 * The one click on the one mask: it opens and closes help's conversation, which
 * stands at the mask. On every page.
 */
function onIconClick(event: MouseEvent) {
  if (hasDragged) {
    event.preventDefault()
    event.stopPropagation()
    return
  }
  if (isExpanded.value) collapse()
  else expand()
}

// Computed
const canSend = computed(() => {
  return inputMessage.value.trim().length > 0 && !isLoading.value
})

// Methods
async function expand() {
  isExpanded.value = true

  // What the panel opens with is what the page says about itself, the first
  // time and every time after. From the second visit to a page on, clicking
  // Help shows that same orientation text and not the standard sentence.
  //
  // It stops coming up by itself once somebody has actually talked here: from
  // then on it is only ever fetched by hand, and the arrow in the head is where
  // that hand reaches.
  //
  // The standard sentence is therefore left with exactly the pages that say
  // nothing about themselves, the start page among them. Marked seen at the
  // moment of opening and not when it is read: what is being remembered is
  // that the page has already introduced itself here.
  // Decided anew at every opening, in both directions. Only setting it would
  // leave an address that was turned over by hand standing through the next
  // opening, and "only on request" would quietly stop holding.
  shownAddress.value = pageAddress.hasTalked(route.path)
    ? null
    : pageAddress.addressFor(route.path)
  pageAddress.markSeen(route.path)

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

  } catch (error) {
    console.error('[ChatOverlay] Error loading chat history:', error)
    // Don't show error to user - just start with empty chat
  }
}

async function sendMessage() {
  if (!canSend.value) return

  // From here on this page HAS a conversation, and its address stops coming up
  // by itself. It stays reachable through the arrow in the head.
  pageAddress.markTalked(route.path)

  // Spend this gesture on opening the ear. The answer arrives seconds later,
  // long after the click, and by then the browser would refuse to sound it.
  primeSpeech()

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
    const data = await chatTurn('/api/chat/stream', {
      message: userMessage,  // Original message without context prefix
      // Not on a page that keeps nothing: run_id is what makes the backend
      // write this conversation into exports/<run>/chat_history.json, and the
      // id here would be a leftover from an earlier page in the same visit.
      run_id: pageContextStore.ephemeral ? undefined : (currentSession.value.runId || undefined),
      // What this page has made, as a listing — not as a picture. Until
      // 2026-08-23 the run's image travelled with EVERY message here: ten
      // questions about one picture cost ten transfers of it, or ten local
      // readings where the model cannot see, whether or not a single one of
      // them was about what the picture shows. The look is a tool now
      // (view_run), and the conversation reaches for it when it needs it.
      surface_media: surfaceMedia.value,
      may_open_media: true,
      draft_context: draftContextString.value || undefined,  // Always send current page state
      history: historyForBackend,
      language: locale.value,
    })

    const assistantReply = data.reply
    const assistantThinking = data.thinking || null

    // Add assistant response to UI
    const replyId = messageIdCounter++
    messages.value.push({
      id: replyId,
      role: 'assistant',
      content: assistantReply,
      thinking: assistantThinking
    })
    if (voiceAvailable.value) void speak(assistantReply, locale.value, replyId)

    // Scroll to bottom
    await nextTick()
    scrollToBottom()

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
    // If run_id changed (and not just initialized), reload history.
    // NOT while something is being said: on a board a run finishes beside an
    // open conversation, and reloading would replace what is on screen with
    // that run's history — which for a fresh run is empty. The next opening
    // picks it up.
    if (newRunId !== oldRunId && isExpanded.value) {
      if (newRunId) {
        if (messages.value.length > 0) return
        await loadChatHistory()
      } else {
        // Session cleared
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


    // Build pedagogical explanation based on block type
    let explanation: string
    const reason = event.reason || ''

    // Which block this is — the same reading every surface uses
    // (composables/useGenerationStream.ts). What the image AI said it saw is
    // added here, because only this conversation has room for it.
    const blockKey = safetyBlockKeyForEvent({
      reason,
      stage: event.stage,
      operational: event.operational,
    })
    explanation = t(blockKey)
    if (event.vlmDescription && (blockKey === 'safetyBlocked.inputImage' || blockKey === 'safetyBlocked.vlm')) {
      explanation += `\n\n*${t('safetyBlocked.vlmSaw')}: "${event.vlmDescription}"*`
    }

    // While the check is unreachable it fails on every blur, every dropped file
    // and every second field. The same sentence stacked ten times reports a
    // fault of the platform as an insistence about the reader, so a repeat of a
    // standing operational message is not written twice — but only the WRITING
    // is dropped. A closed panel opens again either way: material was taken off
    // the surface again, and on the workshop board this window is the only
    // thing that says so at all.
    const standing = messages.value[messages.value.length - 1]
    const repeat = event.operational
      && standing?.role === 'assistant'
      && standing.content === explanation

    // Detect if this is an age-appropriate block (kids/youth)
    const isAgeBlock = reason.includes('Kids-Filter') || reason.includes('Kinder-Schutzfilter')
      || reason.includes('Youth-Filter') || reason.includes('Jugendschutzfilter')

    // A blocked upload is explained HERE and nowhere else on the platform — the
    // workshop reports its own image blocks into this store (views/resona.vue)
    // and shows nothing itself. Suppressed, a child would have their picture
    // refused in silence.
    if (!isExpanded.value) {
      isExpanded.value = true
      await nextTick()
    }
    if (repeat) {
      // Nothing new to write, but this IS a new refusal: the panel may have
      // been reopened onto an older line, and the sentence that belongs to what
      // just happened is the last one.
      await nextTick()
      scrollToBottom()
      return
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

    const data = await chatTurn('/api/chat/stream', {
      message: suggestionPrompt
    })

    // Replace loading message in-place
    const msg = messages.value.find(m => m.id === loadingId)
    if (msg) {
      msg.content = data.reply
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

// Watch for image analysis events — expand Träshy, call /api/chat with image, show result
watch(
  () => analysisEventStore.pendingReflection,
  async (pending) => {
    if (!pending) return

    const event = analysisEventStore.consume()
    if (!event || !event.runId) return


    // Auto-expand Träshy
    if (!isExpanded.value) {
      isExpanded.value = true
      await nextTick()
    }

    // Show loading
    const loadingId = messageIdCounter++
    messages.value.push({
      id: loadingId,
      role: 'assistant',
      content: t('trashy.analysisReflectionLoading')
    })
    await nextTick()
    scrollToBottom()

    try {
      // Build process-oriented prompt using page context
      const userInput = pageContextStore.pageContent.inputText
        || pageContextStore.pageContent.contextPrompt
        || ''
      const prompt = buildImageAnalysisPrompt(userInput, uiModeStore.mode)

      const data = await chatTurn('/api/chat/stream', {
        message: prompt,
        image_path: event.runId,
        draft_context: draftContextString.value || undefined,
        language: locale.value,
      })

      const msg = messages.value.find(m => m.id === loadingId)
      if (msg) {
        msg.content = data.reply || t('trashy.analysisReflectionError')
      }
    } catch (error) {
      console.error('[ChatOverlay] Image analysis failed:', error)
      const msg = messages.value.find(m => m.id === loadingId)
      if (msg) {
        msg.content = t('trashy.analysisReflectionError')
      }
    }

    await nextTick()
    scrollToBottom()
  }
)

function buildImageAnalysisPrompt(userInput: string, mode: string): string {
  const formatRule = 'CRITICAL: Your response is shown directly to the user. Start with the first sentence of your analysis. FORBIDDEN: "Okay", "Let me", "I need to", thinking out loud, meta-commentary, restating the task.'

  if (mode === 'easy') {
    return `${formatRule}

Look at this image. The user typed: "${userInput || '(no text)'}"

Write a short, friendly response (3-4 sentences):
1. What do you see?
2. Does it match what the user wanted?
3. What could they try next?

Use the user's language. Be encouraging.`
  }

  if (mode === 'medium') {
    return `${formatRule}

Look at this image. The user's input was: "${userInput || '(no text)'}"

Write a process-oriented reflection (5-8 sentences):
1. What do you see? Key visual elements, composition, mood.
2. How does it relate to the input? What was preserved, what did the AI add?
3. Any unexpected or interesting qualities?
4. One concrete suggestion for what to try next.

Use the user's language. Be warm but push the user to think critically.`
  }

  return `${formatRule}

Look at this image. The user's input was: "${userInput || '(no text)'}"

Write an analytical reflection (6-10 sentences):
1. Visual elements, composition, mood, technical qualities.
2. How does the result relate to the prompt chain? What survived, what is the AI's contribution?
3. Critical reading: hidden assumptions, aesthetic defaults, biases.
4. Concrete directions to explore.

Use the user's language. Be direct and intellectually honest.`
}
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

/* Collapsed State. The button shrink-wraps the figure, which sizes itself from
   the iconSize prop; the idle movement belongs to the figure now. */
.chat-toggle-icon {
  background: transparent;
  border: none;
  box-shadow: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

/* Under the icon when the icon is at the top of the screen. Same lean, mirrored
   so it still reads as held rather than dropped. */
.trashy-sign.below {
  bottom: auto;
  top: calc(100% + 6px);
  transform-origin: top center;
  animation-name: trashy-sign-wave-below;
}
@keyframes trashy-sign-wave-below {
  0%, 100% { transform: translateX(calc(-50% + var(--sign-shift, 0px))) rotate(4deg); }
  50% { transform: translateX(calc(-50% + var(--sign-shift, 0px))) rotate(-2deg); }
}

/* Held up, not pinned to a corner: it sits above Träshy and leans, so it reads
   as something being offered rather than a button the page grew. */
.trashy-sign {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(calc(-50% + var(--sign-shift, 0px))) rotate(-4deg);
  transform-origin: bottom center;
  white-space: nowrap;
  padding: 0.3rem 0.7rem;
  border-radius: 6px;
  border: 1px solid #7a6a3a;
  background: #2a2418;
  color: #e8dfc6;
  font-size: 0.82rem;
  cursor: pointer;
  animation: trashy-sign-wave 3.6s ease-in-out infinite;
}
.trashy-sign:hover { background: #3a3222; border-color: #a08a4a; }
@keyframes trashy-sign-wave {
  0%, 100% { transform: translateX(calc(-50% + var(--sign-shift, 0px))) rotate(-4deg); }
  50% { transform: translateX(calc(-50% + var(--sign-shift, 0px))) rotate(2deg); }
}

.chat-toggle-icon:hover {
  transform: scale(1.1);
}

.chat-toggle-icon.is-dragging {
  cursor: grabbing;
  transform: scale(1.05);
}

/* The idle drift settles under the pointer and stops entirely while the figure
   is carried — a figure that keeps drifting under the cursor reads as fighting
   it. The movement lives inside FigureMask now, so reaching it takes :deep().
   Scoped to `is-idle` on purpose: the waiting pulse says something is being
   computed, and freezing that because a pointer went past would make the sign
   say something untrue. */
.chat-toggle-icon:hover :deep(.figure-mask.is-idle) {
  animation-play-state: paused;
}

.chat-toggle-icon.is-dragging :deep(.figure-mask.is-idle) {
  animation: none;
}

/* The conversation, placed against the mask: absolute inside the overlay box,
   which IS the mask's box, with its offset written by panelOffset. It therefore
   moves with the mask by construction — the drag moves one element, and there
   is no frame in which the two are apart. Dimensions and offset both come from
   the :style binding. */
.chat-window {
  position: absolute;
  background: var(--surface-2);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--surface-4);
}

/* Resize handles at corners */
.resize-handle {
  position: absolute;
  width: 14px;
  height: 14px;
  z-index: 10;
}
.resize-nw { top: 0; left: 0; cursor: nwse-resize; }
.resize-ne { top: 0; right: 0; cursor: nesw-resize; }
.resize-sw { bottom: 0; left: 0; cursor: nesw-resize; }
.resize-se { bottom: 0; right: 0; cursor: nwse-resize; }

/* Header */
.chat-header {
  background: var(--surface-2);
  cursor: move;
  user-select: none;
  padding: 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--figure-tint, #5c8cb0);
  position: relative;
  border-bottom: 2px solid var(--figure-tint, #5c8cb0);
}

.chat-title {
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--figure-tint, #5c8cb0);
  text-shadow: none;
  flex-shrink: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}


/* The address handle. Quieter than the close button beside it: it turns
   something over, it does not end anything. */
.address-handle {
  background: none;
  border: none;
  color: var(--figure-tint, #5c8cb0);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  opacity: 0.75;
  transition: opacity 0.2s ease, background 0.2s ease;
}

.address-handle:hover {
  opacity: 1;
  background: rgb(var(--surface-4-rgb) / 0.6);
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
  background: var(--bg-base);
}

/* Scrollbar styling */
.chat-messages::-webkit-scrollbar {
  width: 8px;
}

.chat-messages::-webkit-scrollbar-track {
  background: var(--surface-2);
}

.chat-messages::-webkit-scrollbar-thumb {
  background: var(--surface-4);
  border-radius: 4px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: var(--surface-4);
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

/* The inference process, collapsible inside the message bubble. What a model sends
   alongside its answer -- not a thought, and not named as one. */
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
  display: block;
  font-size: 0.78rem;
  font-style: italic;
  color: #888;
  line-height: 1.4;
  padding: 0.4rem 0.5rem;
  margin-top: 0.3rem;
  border-inline-start: 2px solid var(--surface-3);
  word-wrap: break-word;
}

.thinking-no-answer {
  font-size: 0.8rem;
  font-style: italic;
  color: #999;
  margin-bottom: 0.3rem;
}

.message.user .message-content {
  background: var(--figure-tint, #5c8cb0);
  color: white;
  border-bottom-right-radius: 4px;
}

.message.assistant .message-content {
  background: var(--surface-3);
  color: #e0e0e0;
  border-bottom-left-radius: 4px;
}

.message.greeting .message-content {
  background: color-mix(in srgb, var(--figure-tint, #5c8cb0) 16%, transparent);
  border: 1px solid var(--figure-tint, #5c8cb0);
  color: #d4edb8;
  font-style: italic;
}

/* The page's own address. Everything here exists to keep it from reading as a
   reply: no bubble, no bubble colour, the full width of the panel instead of a
   message's 85%, and the page's agent colour down its side — the same
   --figure-tint the mask outside this panel is painted in, inherited from the
   app root, so the block is visibly the page speaking and not the conversation.
   It is a button because clicking it turns it back into the greeting; the words
   it carries are its accessible name. */
.page-address {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  width: 100%;
  padding: 0.1rem 0 0.4rem;
  padding-inline-start: 0.75rem;
  border: none;
  border-inline-start: 2px solid var(--figure-tint, #5c8cb0);
  background: transparent;
  color: #cfcabf;
  font: inherit;
  font-size: 0.86rem;
  line-height: 1.5;
  text-align: start;
  cursor: pointer;
  animation: fadeIn 0.3s ease;
}

.page-address:hover {
  color: #e6e1d6;
}

.address-halves {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

/* The one visible sign that there is a state here — the same two glyphs the
   thinking disclosure in this panel already turns over. */
.address-arrow {
  flex-shrink: 0;
  font-size: 0.7rem;
  font-style: normal;
  line-height: 1.9;
  color: #666;
}

/* The way back to the address, riding on the line the panel has always opened
   with. Bare on purpose: how it looks is the greeting's business. */
.address-turn {
  display: block;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: start;
  cursor: pointer;
}

/* Loading State */
.message.loading .message-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--surface-3);
  color: #999;
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid color-mix(in srgb, var(--figure-tint, #5c8cb0) 30%, transparent);
  border-top-color: var(--figure-tint, #5c8cb0);
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
  background: var(--surface-2);
  border-top: 1px solid var(--surface-4);
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
}

.chat-input-container textarea {
  flex: 1;
  background: var(--bg-base);
  border: 1px solid var(--surface-4);
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
  border-color: var(--figure-tint, #5c8cb0);
}

.chat-input-container textarea:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.send-button {
  width: 40px;
  height: 40px;
  background: var(--figure-tint, #5c8cb0);
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
  background: var(--surface-4);
  color: #666;
  cursor: not-allowed;
  transform: none;
}

/* No width rule for narrow screens here. The panel's width and height are
   written inline by panelSize, and an inline style outranks a stylesheet rule —
   a media query for them could never have taken effect. Fitting the viewport is
   done where the numbers are, in panelSize. */
</style>
