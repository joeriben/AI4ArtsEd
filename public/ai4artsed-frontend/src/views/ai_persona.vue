<template>
  <div class="persona-page" ref="pageEl">
    <!-- What this surface makes lands in the platform's card — the same one the
         flow throws its output into and the workshop board carries. It brings
         its own bar, its own corner and its own back; this page only says where
         it sits and what the gestures move. -->
    <FlowCard
      v-for="box in mediaBoxes"
      :key="box.id"
      class="floating-media-box"
      :style="nodeStyle(box.id)"
      bar
      closable
      resizable
      scroll
      :resize-title="t('x2xFlow.resize')"
      :hold-title="t('resonaMediaCard.flipToBack')"
      @grip-down="startBoxDrag($event, box.id)"
      @resize-down="startBoxResize($event, box.id)"
      @close="removeBox(box.id)"
    >
      <MediaCardFront
        :output-url="box.outputUrl"
        :media-type="box.mediaType"
        :run-id="box.runId"
        :is-executing="box.stream.isExecuting.value"
        :progress="box.stream.generationProgress.value"
        :preview-image="box.stream.previewImage.value"
        :is-favorited="box.isFavorited"
        :model-meta="box.stream.modelMeta.value"
        :stage4-duration-ms="box.stream.stage4DurationMs.value"
        @image-click="showBox(box)"
      />
      <template #back="{ flipped }">
        <MediaCardBack
          v-bind="backOf(box)"
          :active="flipped"
          @toggle-favorite="toggleFavorite(box.id)"
          @forward="forwardToI2I(box)"
          @download="downloadBoxMedia(box)"
          @print="printMedia(box)"
        />
      </template>
    </FlowCard>

    <!-- The platform's one fullscreen layer (components/MediaFullscreen.vue), with
         the card's back beside the picture and the card's own handlers behind
         its row. -->
    <MediaFullscreen
      :src="fullscreenImage"
      :back="fullscreenBox ? backOf(fullscreenBox) : null"
      @close="closeFullscreen"
      @toggle-favorite="fullscreenBox && toggleFavorite(fullscreenBox.id)"
      @forward="fullscreenBox && forwardToI2I(fullscreenBox)"
      @download="fullscreenBox && downloadBoxMedia(fullscreenBox)"
      @print="fullscreenBox && printMedia(fullscreenBox)"
    />

    <!-- The turn, standing on the page.

         No card and no button that wakes it. What this page IS gets said by
         the platform voice when somebody arrives here for the first time, and
         writing is what wakes the machine. A framed box in the middle of the
         screen was a second thing to read before anything could happen. -->
    <div class="chat-area">
      <!-- Only the active turn stands — the machine's latest line with the
           human's answer beneath it — in the same treatment the platform
           speaks in everywhere else. The dialogue itself is not lost with the
           log: it lives on in the store (that is what the machine is sent and
           what is saved), and the new-dialog button in the speak-line is still
           what ends it.
           The reply is read while it is being written: `streamingId` names
           the line that is still growing. What may STAND is a sentence that is
           finished AND, where this turn is spoken, one whose clip has begun to
           sound — here as in the workshop, the writing and the voice keep step
           rather than running side by side. -->
      <div ref="voiceBodyEl" class="voice-body">
        <ResonaVoice
          :trail="voiceTrail"
          :streaming-id="streamingId ?? undefined"
          :spot="voiceSpot"
          :speak="speakState"
          :coupling="voiceCoupling"
          :line-empty="!userInput && !isLoading"
          :words="true"
          :sounding="isSounding"
          :preparing="isPreparing"
          :blocked="isBlocked"
          :can-replay="canReplay"
          :replay-label="replayLabel"
          :tap-label="t('persona.tapToHear')"
          @replay="onVoiceReplay"
        >
          <template #speakline>
            <!-- The open line: the human's own line of this exchange, before
                 it is sent. No box around it, nothing written in it beforehand
                 and no button beside it — the Enter key is the entry. -->
            <textarea
              ref="pageInputRef"
              v-model="userInput"
              class="write-line"
              rows="1"
              :disabled="isLoading"
              @keydown.enter.exact.prevent="sendMessage"
            ></textarea>
          </template>
        </ResonaVoice>
      </div>
    </div>

    <!-- What this surface is set to, out of the exchange: here that is the one
         decision to end a dialogue and begin another. -->
    <SurfaceGear
      v-if="personaChat.hasConversation"
      class="fixture-gear"
      :title="t('persona.surfaceSettings')"
    >
      <button class="gear-action" @click="startNewDialog">{{ t('persona.newDialog') }}</button>
    </SurfaceGear>

    <PlatformVoice ref="platformVoice" :anchors="voiceAnchors" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref, shallowRef, triggerRef, onMounted, onUnmounted, onBeforeUnmount, watch } from 'vue'
import MediaFullscreen from '@/components/MediaFullscreen.vue'
import type { MediaBack } from '@/components/mediaBack'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useFavoritesStore } from '@/stores/favorites'
import { usePersonaChatStore } from '@/stores/personaChat'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { sseEvents } from '@/lib/sseStream'
import { useDeviceId } from '@/composables/useDeviceId'
import { useSpeech, useSpokenTurn, primeSpeech, splitForSpeech, type SpeechKey } from '@/composables/useSpeech'
import { useGenerationStream } from '@/composables/useGenerationStream'
import FlowCard from '@/components/FlowCard.vue'
import MediaCardFront from '@/components/MediaCardFront.vue'
import MediaCardBack from '@/components/MediaCardBack.vue'
import { usePanZoom, type BoardItem } from '@/composables/usePanZoom'
import { useDirectWriting, growWriteLine } from '@/composables/useDirectWriting'
import SurfaceGear from '@/components/SurfaceGear.vue'
import { findFreeSpot, type Rect } from '@/composables/useFreeSpot'
import PlatformVoice, { type PlatformVoiceHandle, type VoiceAnchor } from '@/components/PlatformVoice.vue'
import ResonaVoice from '@/components/ResonaVoice.vue'
import type { VoiceUtterance, SpeakState } from '@/components/ResonaVoice.vue'
import { apiBase } from '@/services/labApi'
import { handOverImage } from '@/lib/handOverImage'
import { downloadMedia, mediaExtension } from '@/lib/downloadMedia'
import { printMedia as printPicture } from '@/lib/printMedia'

const { t, locale } = useI18n()
const router = useRouter()
const userPreferences = useUserPreferencesStore()
const favoritesStore = useFavoritesStore()
const personaChat = usePersonaChatStore()
const deviceId = useDeviceId()
const pageContextStore = usePageContextStore()

// ---------- Platform voice: where a sentence about this page may dock ----------
const voiceAnchors: VoiceAnchor[] = [
  // The line the human writes in (present once the persona is activated)
  { id: 'compose', selector: '.write-line', words: ['eingabe', 'input', 'schreib', 'textfeld', 'frage'] },
  // The running conversation — where Persona's line stands (the scrolling log
  // it used to dock onto is gone; a sentence about the dialogue docks onto the
  // voice that carries it)
  { id: 'dialogue', selector: '.voice-body', words: ['dialog', 'gespräch', 'conversation', 'antwort', 'reply', 'nachricht', 'message'] },
  // A floating media box (present once the persona decided to generate)
  { id: 'media', selector: '.floating-media-box', words: ['generier', 'generat', 'erzeug', 'bilder'] },
]

// ---------- Fullscreen ----------

const fullscreenImage = ref<string | null>(null)
/**
 * The box standing large, so its back stands beside the picture (one click,
 * one view, on every surface).
 * Shallow, as the list of boxes is: a box carries its generation stream.
 */
const fullscreenBox = shallowRef<MediaBox | null>(null)

function showBox(box: MediaBox) {
  if (!box.outputUrl) return
  fullscreenBox.value = box
  fullscreenImage.value = box.outputUrl
}

function closeFullscreen() {
  fullscreenBox.value = null
  fullscreenImage.value = null
}

/** The record of a box: on its card's back and beside its picture, one object. */
function backOf(box: MediaBox): MediaBack {
  return {
    mediaType: box.mediaType,
    runId: box.runId,
    mediaUrl: box.outputUrl || undefined,
    isFavorited: box.isFavorited,
    prompt: box.prompt,
    configId: box.configId,
    createdAt: box.createdAt,
    modelMeta: box.stream.modelMeta.value,
  }
}

// ---------- Chat state ----------

interface ContentPart {
  type: 'text' | 'prompt' | 'generate'
  text: string
  configId?: string
}

const { messages } = storeToRefs(personaChat)
/** Which line is still being written, by store id. */
const streamingId = ref<number | null>(null)
const userInput = ref('')
const isLoading = ref(false)
/** Whether the machine has already been addressed. It gates the OPENING LINE
 *  and nothing else — not the page: the line one speaks in stands from the
 *  first moment, so somebody can simply begin. Writing is what opens it, and
 *  then there is nothing left to open. */
const hasOpened = ref(false)

// ---------- Page context: what this page is, and what stands in the line now ----------
// The same spine every other view registers on (setPageContext -> formatForLLM).
// Independent of buildDraftContext() further down, which is what this page
// tells Persona; this is what a voice asked ABOUT the page is told.
const pageContext = computed<PageContext>(() => ({
  activeViewType: 'ai_persona',
  pageDescription:
    'Diese Seite: ästhetische Ideen werden hier bestritten, im Sprechen mit einer Maschine, kein Assistent — sie macht nicht, was man ihr sagt, und sie kann nein sagen. Während des Gesprächs entscheidet sie selbst, ob sie ein Bild, einen Klang, Musik, ein Video oder ein 3D-Objekt erzeugt; jede Erzeugung erscheint als frei verschiebbarer Kasten auf der Seite. Es steht immer nur der laufende Zug auf der Seite: der letzte Satz der Maschine, darunter die eigene Antwort; der nächste Zug ersetzt ihn. Vorgeschlagene Prompts stehen als anklickbare Schaltflächen über der Eingabezeile, und der stehende Zug kann die Stimme der Plattform bekommen. Die Eingabezeile steht von Anfang an; die Maschine selbst sagt nichts, bis man anfängt zu schreiben.',
  pageContent: {
    inputText: userInput.value,
  },
}))

watch(
  pageContext,
  (ctx) => {
    pageContextStore.setPageContext(ctx)
  },
  { immediate: true, deep: true }
)

onUnmounted(() => {
  pageContextStore.clearContext()
})

// ---------- Speaking (Supertonic 3 via /api/speech) ----------
const {
  isAvailable: speechAvailable,
  speakingKey,
  pendingKey,
  blockedKey,
  soundingPiece,
  loadStatus: loadSpeechStatus,
  toggle: toggleSpeech,
  stop: stopSpeech,
  resume: resumeSpeech,
  isSpeakable,
  speaksInFallback,
} = useSpeech()

/** The utterance this surface has ASKED to be spoken — set before the request
 *  and unset when it has settled, one way or the other. */
const askedKey = ref<SpeechKey | null>(null)

/** What Persona says, without its markers: only the prose stands on the page
 *  and only the prose is spoken. The markers themselves render nothing. */
function spokenText(content: string): string {
  // A marker still being written has no closing bracket yet. It is cut off at
  // its opening, so that neither the words nor the voice carry the inside of a
  // marker while the rest of it arrives.
  return parseContent(content.replace(/\[(?:PROMPT|GENERATE):[^\]]*$/, ''))
    .filter(part => part.type === 'text')
    .map(part => part.text)
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** The click is the gesture; the sound arrives long after it. */
function onSpeakPress(msg: { id: SpeechKey; content: string }) {
  primeSpeech()
  toggleSpeech(spokenText(msg.content), locale.value, msg.id)
}

function speakTitle(id: SpeechKey): string {
  if (blockedKey.value === id) return t('persona.tapToHear')
  if (speakingKey.value === id || pendingKey.value === id) return t('persona.stopSpeaking')
  return speaksInFallback(locale.value) ? t('persona.spokenInEnglish') : t('persona.speak')
}

// ---------- The voice: one active turn, no chat log ----------
// What Persona says gets the treatment the platform speaks in everywhere (see
// ResonaVoice and @/lib/voiceText): standing sentences, one turn at a time,
// replaced by the next. Nothing is thrown away with the bubbles — messages[]
// keeps the full dialogue, which is what Persona is sent and what is saved.

/** Persona's latest line. The speaker, its label and the suggested prompts all
 *  hang on this one message, so they always belong to the same turn. */
const lastAssistant = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i]
    if (msg?.role === 'assistant') return msg
  }
  return null
})

// Read-only render copy; messages[] is never touched here. A reply that only
// generated something strips to an empty line — it is left out so it cannot
// take the turn away from the last words Persona actually said.
const voiceTrail = computed<VoiceUtterance[]>(() => {
  const out: VoiceUtterance[] = []
  for (const msg of messages.value) {
    const text = msg.role === 'assistant' ? spokenText(msg.content) : msg.content
    if (!text) continue
    out.push({ id: msg.id, role: msg.role, text, liftable: false })
  }
  return out
})

// The wait has no bubble of its own any more: while Persona is thinking, the
// standing turn breathes.
const speakState = computed<SpeakState>(() => (isLoading.value ? 'listening' : 'idle'))

// ---------- Where the turn stands ----------
// The voice's own CSS fallback puts the words a quarter of the surface down —
// measured for a board that fills the window, not for a card of 520px. Inside
// this card that left about three short sentences before the bottom guard cut
// the rest away, and Persona's replies are longer than that. So the card names
// the resting place itself: its body's top-left corner, a little inside it.
//
// The point is read in SCREEN space and asked for anew on every frame, which is
// what the voice expects — it subtracts its own base rect and writes the point
// as the turn's top left, so the words follow the card when the window resizes.
const voiceBodyEl = ref<HTMLElement | null>(null)
function voiceSpot(): { x: number; y: number } | null {
  const el = voiceBodyEl.value
  if (!el) return null
  const r = el.getBoundingClientRect()
  return { x: r.left + 28, y: r.top + 20 }
}

// One speaker for the standing turn, in place of the one per bubble.
const canReplay = computed(
  () => speechAvailable.value && !!lastAssistant.value && isSpeakable(spokenText(lastAssistant.value.content))
)
const isSounding = computed(() => !!lastAssistant.value && speakingKey.value === lastAssistant.value.id)
const isPreparing = computed(() => !!lastAssistant.value && pendingKey.value === lastAssistant.value.id)
const isBlocked = computed(() => !!lastAssistant.value && blockedKey.value === lastAssistant.value.id)
const replayLabel = computed(() => (lastAssistant.value ? speakTitle(lastAssistant.value.id) : ''))

// ---------- The open line ----------
//
// Nothing in the corner stands for this machine. It is present in what it says,
// in the voice that says it and in what it makes on the page: no
// representation, only presentation in the action. The mask in the app
// overlay is help, exactly as on every other page.
const pageInputRef = ref<HTMLTextAreaElement | null>(null)

// The open line wraps as it is written in, and a wrapping line has to be told
// its own height. Hung on the model rather than on the keystroke, so it also
// holds for the ways in that never touch the keyboard: writing from anywhere on
// the surface, and the line cleared on send.
watch(userInput, () => { void nextTick(() => growWriteLine(pageInputRef.value)) })

// A keystroke anywhere lands in the open line, which stands in the exchange
// itself (composables/useDirectWriting, components/ResonaVoice.vue).
useDirectWriting({
  text: userInput,
  focus: () => void nextTick(() => pageInputRef.value?.focus()),
  paused: () => !!fullscreenImage.value,
})

// ---------- What this page says about itself ----------
//
// It is HELP that says it, in help's panel, on the first arrival and on every
// click on the mask afterwards — exactly as on every other page of the
// platform (components/ChatOverlay.vue, stores/pageAddress.ts). The text
// appears in Help as on every page, and no longer on the surface.
//
// It stood on the surface itself before, put there by the platform voice,
// because this page owned its mask and had no panel to open. It has one now.
// The voice stays mounted and stays askable — what goes is this page pushing
// its own address into it.
const platformVoice = ref<PlatformVoiceHandle | null>(null)

// The voice sets the pace of the words, exactly as in the workshop: a sentence
// stands up when its piece begins to sound, so what is read and what is heard
// are the same sentence. Without it a reply arrives as a block of sentences all
// at once, with the voice running along underneath it saying something else.
//
// The fields are ACCESSORS, not the values they had when this object was made.
// The turn's words are handed to the voice component in a render, and the key
// that says "this is being spoken" is set after that render — a snapshot would
// reach the words one render too late, every time, and the whole reply would
// already be standing before the coupling could hold anything back.
const voiceCoupling = computed(() => {
  if (!speechAvailable.value) return null
  return {
    get piece() { return soundingPiece.value },
    get askedKey() { return askedKey.value },
    get pendingKey() { return pendingKey.value },
    get speakingKey() { return speakingKey.value },
    get blockedKey() { return blockedKey.value },
    // The words must be cut the way the audio was cut, or sentence and piece
    // are not the same thing.
    segment: splitForSpeech,
  }
})

/** Restored history is a record, not a turn: what was said in an earlier
 *  session is not read out again on arrival. Only what arrives from here on. */
const speakFromIdx = ref(Number.POSITIVE_INFINITY)

// A new turn is spoken by itself. It has to be: the words follow the voice, so
// a voice that is never asked for leaves them nothing to follow.
//
// Watched together with the writing: the line is put up empty and grows, so
// the object no longer changes when the turn becomes speakable. What says the
// turn is whole is the writing being over.
watch([lastAssistant, streamingId], ([msg, streaming]) => {
  // Whether a voice is coming is decided when the turn BEGINS, not when it is
  // finished. The words follow it sentence by sentence, and they can only do
  // that if they know from their first pass that one is on the way: a reply
  // that arrives while nothing has been asked stands complete before the first
  // clip exists, and voice and writing then run side by side.
  const speakable = !!msg && speechAvailable.value
    && messages.value.findIndex(m => m.id === msg.id) >= speakFromIdx.value
  if (streaming !== null) {
    if (speakable && msg && msg.id === streaming) askedKey.value = msg.id
    return
  }
  // Asked while it was arriving and not spoken after all: the words are
  // released rather than left waiting for a voice that never comes.
  const release = () => {
    spoken.end()
    if (msg && askedKey.value === msg.id) askedKey.value = null
  }
  if (!speakable || !msg) return release()
  const said = spokenText(msg.content)
  // Whether a text that arrives whole is short enough to be spoken at all is
  // the voice's rule (useSpeech().follow), the same for both surfaces.
  if (!said) return release()
  // Said here, one line before the asking, because the speech itself cannot say
  // it early enough: speak() may reach its own key only a microtask later, or
  // return before it ever sets one. This surface knows NOW that it is asking,
  // and the words that are to follow need that answer on the very pass that
  // stands the turn up.
  askedKey.value = msg.id
  spoken.hand(msg.id, said, true)
}, { flush: 'post' })

// ---- The voice follows the writing ----
//
// A sentence goes to the voice once the stream has begun the sentence after
// it, and the last one goes with the closing text. What
// waits, what is dropped with a text taken back, what goes on when the
// closing text differs, and what stays over is decided in one place for both
// speaking surfaces: useSpokenTurn / useSpeech().follow.
const spoken = useSpokenTurn(() => locale.value, askedKey)

// Watched on the writing itself: every token hands over what it has closed.
// Only for the turn this surface has asked to be spoken — that decision is
// made above, when the turn begins.
watch(
  () => {
    const s = streamingId.value
    if (s === null) return null
    return spokenText(messages.value.find(m => m.id === s)?.content ?? '')
  },
  text => {
    const id = streamingId.value
    if (id === null || text === null || askedKey.value !== id) return
    spoken.hand(id, text, false)
  },
  { flush: 'post' },
)

/** Hearing it again is a request, so it is spoken even where the automatic
 *  reading did not apply. Clicking while it is still sounding stops it. */
function onVoiceReplay(utterance: VoiceUtterance) {
  primeSpeech()
  // A held-back utterance goes first: this tap is the gesture it was missing.
  if (blockedKey.value !== null) { resumeSpeech(); return }
  if (speakingKey.value === utterance.id || pendingKey.value === utterance.id) {
    // Said here as well: the voice reports a stopped utterance as over and
    // the words are released through `over` (useSpeech().follow), but a
    // microtask later. Being asked for is over the moment it is stopped, on
    // this pass, and the rest of that turn's words stand.
    stopSpeech()
    askedKey.value = null
    return
  }
  const msg = messages.value.find(m => m.id === utterance.id)
  if (msg) onSpeakPress(msg)
}

// ---------- Floating media boxes ----------

interface MediaBox {
  id: string
  stream: ReturnType<typeof useGenerationStream>
  outputUrl: string | null
  mediaType: string
  runId: string | null
  isFavorited: boolean
  /** What was asked for, and of which model — the card's back side. */
  prompt: string
  configId: string
  createdAt: number
  /** Once somebody has pulled the card to a size, nothing sizes it again. */
  userSized?: boolean
}

const mediaBoxes = shallowRef<MediaBox[]>([])
const pageEl = ref<HTMLElement | null>(null)

// Geometry is kept beside the boxes, not in them: the list is a shallowRef (it
// carries generation streams, which must not be walked by deep reactivity), so
// a coordinate written into a box during a drag would never reach the screen.
// The workshop board keeps its geometry the same way, in the same shape the
// shared drag/resize engine reads.
const geom = reactive<Record<string, BoardItem>>({})
const { startItemDrag, startItemResize, bringToFront } = usePanZoom()

// What a card is worth in room, per medium. A player is a strip; a picture is a
// picture. Nothing here is fixed — it is only where the card starts.
const BOX_SIZE: Record<string, { w: number; h: number }> = {
  image: { w: 320, h: 340 },
  video: { w: 320, h: 250 },
  audio: { w: 320, h: 130 },
  music: { w: 320, h: 130 },
  '3d': { w: 320, h: 320 },
}
// Deliberately the LARGEST of the measures above: the room is reserved before
// the medium is known, and a card that grew afterwards would grow across the
// gap onto the card below it.
const BOX_START = { w: 320, h: 340 }
const BOX_GAP = 20
/** Height of the footer gallery, which is fixed over the bottom of every page. */
const FOOTER_CLEAR = 36

/**
 * The board engine counts z from 1 upwards, and an inline z beats the
 * stylesheet — so the first cards of a session would have been stacked BELOW
 * the layer the standing words live on (.chat-area, z-index 5), where nothing
 * can be clicked and nothing lifts them out again. The card layer starts above
 * that layer and the engine's order rides on top of it.
 */
const CARD_Z_FLOOR = 10
function nodeStyle(id: string) {
  const g = geom[id]
  if (!g) return {}
  return {
    left: g.x + 'px',
    top: g.y + 'px',
    width: g.w + 'px',
    height: g.h + 'px',
    zIndex: CARD_Z_FLOOR + (g.z ?? 0),
  }
}

/**
 * The rectangle the standing words occupy. They are not an element this page
 * owns — the voice places them per frame — so it is measured where it stands,
 * and only guessed at from the resting point before the first turn is there.
 */
function wordsRect(): Rect | null {
  const page = pageEl.value
  if (!page) return null
  const pr = page.getBoundingClientRect()
  const turn = page.querySelector('.turn') as HTMLElement | null
  const body = voiceBodyEl.value
  if (turn && body) {
    const r = turn.getBoundingClientRect()
    const b = body.getBoundingClientRect()
    if (r.width > 0 && r.height > 0) {
      // Down to the foot of the ground the words stand on, not to the foot of
      // what is written SO FAR: the sentences are revealed one after another
      // over several seconds, so the box measured here is still growing, and a
      // card set down just under it would be written over a moment later.
      return {
        x: r.left - pr.left,
        y: r.top - pr.top,
        w: r.width,
        h: Math.max(r.height, b.bottom - r.top),
      }
    }
  }
  const el = voiceBodyEl.value
  if (!el) return null
  const r = el.getBoundingClientRect()
  return {
    x: r.left - pr.left + 28,
    y: r.top - pr.top + 20,
    w: Math.min(590, pr.width * 0.4),
    h: 240,
  }
}

/** A new card lands on free ground — never on another card, never on the words. */
function placeBox(id: string, w: number, h: number) {
  const pr = pageEl.value?.getBoundingClientRect()
  const view: Rect = {
    x: 0,
    y: 0,
    w: pr?.width ?? window.innerWidth,
    h: (pr?.height ?? window.innerHeight) - FOOTER_CLEAR,
  }
  const occupied: Rect[] = Object.values(geom).map(g => ({ x: g.x, y: g.y, w: g.w, h: g.h }))
  const wr = wordsRect()
  if (wr) occupied.push(wr)
  const spot = findFreeSpot(view, occupied, w, h, { gap: BOX_GAP })
  const g: BoardItem = { id, x: Math.round(spot.x), y: Math.round(spot.y), w, h }
  // findFreeSpot's last resort continues the scene BELOW the view — right for a
  // board that pans, wrong here: this surface has no pan and no scroll, so a
  // card put down there is gone for good.
  clampIntoView(g)
  bringToFront(g)
  geom[id] = g
}

/** The medium is only known when the result arrives; give the card its measure then. */
function sizeBoxForMedium(box: MediaBox) {
  const g = geom[box.id]
  if (!g || box.userSized) return
  const size = BOX_SIZE[box.mediaType]
  if (!size) return
  g.w = size.w
  g.h = size.h
}

async function spawnGeneration(configId: string, prompt: string) {
  // The reply that asked for this card was added in the same synchronous block,
  // so the words on the page are still the PREVIOUS turn. Let them be written
  // first, or the card is placed clear of a sentence that is about to move.
  await nextTick()
  const stream = useGenerationStream()
  const box: MediaBox = {
    id: `gen-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    stream,
    outputUrl: null,
    mediaType: 'image',
    runId: null,
    isFavorited: false,
    prompt,
    configId,
    createdAt: Date.now(),
  }
  placeBox(box.id, BOX_START.w, BOX_START.h)
  mediaBoxes.value = [...mediaBoxes.value, box]

  try {
    const result = await stream.executeWithStreaming({
      prompt,
      output_config: configId,
      device_id: `${deviceId}_persona${Date.now()}`,
      source_view: 'persona',
    })
    if (result.status === 'success' && result.media_output) {
      const mo = result.media_output
      const runId = mo.run_id || result.run_id || null
      const mediaType = mo.media_type || 'image'
      const mediaIndex = mo.index ?? 0
      if (runId) {
        box.runId = runId
        box.mediaType = mediaType
        // Build the media URL from run_id + type (canonical pattern, mirrors
        // image_transformation/music_generation). Do NOT trust media_output.url:
        // the backend emits inconsistent url formats per media type and omits it
        // entirely on some audio paths, which produced empty boxes.
        box.outputUrl = mediaType === '3d'
          ? (mo.mesh_url || `/api/media/3d/${runId}`)
          : `/api/media/${mediaType}/${runId}/${mediaIndex}`
        sizeBoxForMedium(box)
        triggerRef(mediaBoxes)
        syncBoxToStore(box)
        // POST dialogue snapshot to this generation's run
        postDialogueToRun(runId)
      }
    }
  } catch (e) {
    console.error('[PERSONA] Generation failed:', e)
  }
}

function syncBoxToStore(box: MediaBox) {
  const g = geom[box.id]
  // The card was closed while its run was still going. Its geometry is gone, so
  // keeping it would resurrect it on the next visit — at (0, 0), on the words.
  if (!g) return
  personaChat.saveMediaBox({
    id: box.id,
    x: g.x,
    y: g.y,
    w: g.w,
    h: g.h,
    outputUrl: box.outputUrl, mediaType: box.mediaType,
    runId: box.runId, isFavorited: box.isFavorited,
    prompt: box.prompt, configId: box.configId, createdAt: box.createdAt,
  })
}

function removeBox(id: string) {
  delete geom[id]
  mediaBoxes.value = mediaBoxes.value.filter(b => b.id !== id)
  personaChat.removeMediaBox(id)
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
    syncBoxToStore(box)
  }
}

async function downloadBoxMedia(box: MediaBox) {
  if (!box.outputUrl) return
  const runIdMatch = box.outputUrl.match(/\/api\/media\/\w+\/(.+)$/)
  const runId = runIdMatch ? runIdMatch[1] : 'media'
  const ext = mediaExtension(box.mediaType)
  await downloadMedia(box.outputUrl, `ai4artsed_${runId}.${ext}`)
}

function forwardToI2I(box: MediaBox) {
  if (!box.outputUrl || box.mediaType !== 'image') return
  const runIdMatch = box.outputUrl.match(/\/api\/media\/image\/(.+)$/)
  handOverImage(box.outputUrl, runIdMatch ? runIdMatch[1] : null)
  router.push('/x2x-flow')
}

function printMedia(box: MediaBox) {
  printPicture(box.outputUrl)
}

// ---------- Moving and sizing a card ----------
//
// Both come from the platform's board engine (usePanZoom), unwrapped: this
// surface never pans and never zooms, so screen pixels and its own coordinates
// are the same thing. The page adds the two things the engine cannot know —
// that a card must stay reachable on a surface that does not pan, and that its
// place is worth keeping.

/** A surface without panning cannot fetch back what was pushed off its edge. */
function clampIntoView(g: BoardItem) {
  const pr = pageEl.value?.getBoundingClientRect()
  const w = pr?.width ?? window.innerWidth
  const h = (pr?.height ?? window.innerHeight) - FOOTER_CLEAR
  g.x = Math.round(Math.max(0, Math.min(Math.max(0, w - g.w), g.x)))
  g.y = Math.round(Math.max(0, Math.min(Math.max(0, h - g.h), g.y)))
}

/**
 * The one listener that closes a gesture. `pointercancel` counts as an ending —
 * a system gesture or a lost pointer capture ends the drag without ever
 * releasing — and only one can be outstanding, so a gesture that was never
 * closed cannot fire later at a place it has nothing to do with.
 */
let pendingGesture: (() => void) | null = null
function dropPendingGesture() {
  if (!pendingGesture) return
  window.removeEventListener('pointerup', pendingGesture)
  window.removeEventListener('pointercancel', pendingGesture)
  pendingGesture = null
}
function afterGesture(id: string, extra?: () => void) {
  dropPendingGesture()
  const done = () => {
    dropPendingGesture()
    extra?.()
    const box = mediaBoxes.value.find(b => b.id === id)
    if (box?.outputUrl) syncBoxToStore(box)
  }
  pendingGesture = done
  window.addEventListener('pointerup', done)
  window.addEventListener('pointercancel', done)
}

function startBoxDrag(e: PointerEvent, id: string) {
  const g = geom[id]
  if (!g) return
  startItemDrag(e, g)
  afterGesture(id, () => clampIntoView(g))
}

function startBoxResize(e: PointerEvent, id: string) {
  const g = geom[id]
  if (!g) return
  const box = mediaBoxes.value.find(b => b.id === id)
  if (box) box.userSized = true
  startItemResize(e, g, { mode: 'free', minW: 180, maxW: 1200, minH: 110, maxH: 1200 })
  afterGesture(id, () => clampIntoView(g))
}

onMounted(() => {
  loadSpeechStatus()
})

// ---------- Chat logic ----------

// ---------- Context persistence ----------

/** POST dialogue snapshot to an existing run */
function postDialogueToRun(runId: string) {
  if (!messages.value.length) return
  const baseUrl = apiBase()
  fetch(`${baseUrl}/api/schema/pipeline/run/${runId}/context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dialogue: {
        messages: messages.value.map(m => ({ role: m.role, content: m.content })),
      }
    })
  }).catch(() => { /* fire-and-forget */ })
}

/** Save dialogue to persona session run (lazy-init) */
async function savePersonaSession() {
  if (!messages.value.length) return
  const baseUrl = apiBase()
  if (!personaChat.sessionRunId) {
    try {
      const res = await fetch(`${baseUrl}/api/schema/pipeline/run/init`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config_name: 'persona_session',
          source_view: 'persona',
          device_id: deviceId,
        })
      })
      const data = await res.json()
      if (data.status === 'success' && data.run_id) {
        personaChat.sessionRunId = data.run_id
      }
    } catch {
      return // Can't persist — acceptable
    }
  }
  if (personaChat.sessionRunId) {
    postDialogueToRun(personaChat.sessionRunId)
  }
}

function buildAvailableConfigs(): string {
  // Provide the persona with available configs to choose from
  return [
    'sd35_large — Stable Diffusion 3.5 Large (image)',
    'flux2 — FLUX.2 (image)',
    'flux3 — FLUX 3 Image Klein (image)',
    'gemini_3_pro_image — Gemini 3 Pro image generation (cloud, EU, DSGVO via Mammouth)',
    'gemini_nano_banana_2_1 — Gemini Nano Banana 2.1 image generation (paid cloud call; cloud, EU, DSGVO via Mammouth)',
    'stableaudio_open — Stable Audio 3 (audio/sound)',
    'heartmula_standard — HeartMuLa (music, dual input: lyrics || tags, e.g. [GENERATE: heartmula_standard | [Verse] Hello world... || pop,upbeat,piano])',
'wan22_t2v_video_fast — Wan 2.2 video (video)',
    'ltx_video — LTX Video (video)',
    'hunyuan3d_text_to_3d — Hunyuan3D (3D object)',
  ].join('\n')
}

function buildDraftContext(): string {
  return `AVAILABLE GENERATION CONFIGS (use these config_ids in [GENERATE: config_id | prompt]):\n${buildAvailableConfigs()}`
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

function addMessage(role: 'user' | 'assistant', content: string) {
  personaChat.addMessage(role, content)
}

/**
 * One turn, read while it is written. `onToken` is handed each piece as it
 * lands; the whole reply comes back at the end, after the delivery filters the
 * pieces never saw.
 */
async function callChat(
  message: string,
  history: Array<{ role: string; content: string }>,
  onToken: (text: string) => void = () => {},
): Promise<string | null> {
  // Find the most recent generated image so Persona can see it
  const lastImageRunId = [...mediaBoxes.value]
    .reverse()
    .find(b => b.runId && b.mediaType === 'image' && b.outputUrl)
    ?.runId || undefined

  const body = {
      message,
      history,
      image_path: lastImageRunId,
      context: {
        persona_mode: true,
        language: userPreferences.language,
        device_id: deviceId,
        // This surface carries a voice, one per message. Said explicitly,
        // because the server cannot see which page called and defaults to
        // silence — see speech_availability.voice_state_sentence().
        //
        // Unless the voice is switched off in the main menu. The server cannot
        // see that either: it knows whether this installation CAN speak, not
        // whether this listener wants it to. Sent as it stands, the figure
        // would be told it is heard on request while nothing here would sound.
        // Same rule as the workshop's, which reads no speech as writing.
        voice_mode: speechAvailable.value ? 'on_request' : 'text',
      },
      draft_context: buildDraftContext(),
  }
  let done: any = null
  for await (const ev of sseEvents<any>(`${apiBase()}/api/chat/stream`, body)) {
    if (ev.type === 'token') onToken(ev.text || '')
    else if (ev.type === 'discard') onToken('\u0000')
    else if (ev.type === 'done') done = ev
    else if (ev.type === 'error') throw new Error(ev.details || ev.error || 'chat stream error')
  }
  // Half a sentence is not this surface's to present as an answer: it shows the
  // reply whole, with nowhere to say that it stopped. Ending the turn is what it
  // did before the server learned to hand a broken one over.
  if (done?.broke_off) throw new Error(done.broke_off)
  return done?.reply || null
}

async function sendMessage() {
  const text = userInput.value.trim()
  if (!text || isLoading.value) return

  // Somebody began by themselves. Then there is no opening left to make, and
  // reaching for the mask later must not throw one into a running conversation.
  hasOpened.value = true
  // The page's address is what stands at the door: it says what this surface is
  // before anything has happened on it. The moment somebody writes, it has been
  // read and the surface is in use — it goes, instead of standing under the
  // exchange with the words of both laid over each other.
  platformVoice.value?.clear()
  addMessage('user', text)
  userInput.value = ''
  isLoading.value = true

  const history = messages.value
    .slice(0, -1) // Exclude the just-added user message (it goes as 'message')
    .map(m => ({ role: m.role, content: m.content }))
  // The line is put up empty and grows: what the machine writes is read while
  // it is being written, here as on the workshop surface.
  const replyId = personaChat.addMessage('assistant', '')
  streamingId.value = replyId
  let round = ''
  const applyToken = (piece: string) => {
    if (piece === '\u0000') round = ''
    else round += piece
    personaChat.setContent(replyId, round)
  }

  try {
    const reply = await callChat(text, history, applyToken)
    personaChat.setContent(replyId, reply || '[No response]')
    // The generation markers are read off the whole reply, once, at the end:
    // half a marker is not a marker.
    if (reply) {
      for (const marker of extractGenerateMarkers(reply)) {
        spawnGeneration(marker.configId, marker.prompt)
      }
    }
  } catch {
    personaChat.setContent(replyId, t('persona.connectionError'))
  } finally {
    streamingId.value = null
    isLoading.value = false
  }
}

// ---------- Init ----------

function startNewDialog() {
  // Save dialogue before clearing
  savePersonaSession()
  personaChat.clearConversation()
  for (const k of Object.keys(geom)) delete geom[k]
  mediaBoxes.value = []
  hasOpened.value = false
}

function restoreMediaBoxes() {
  const stored = personaChat.mediaBoxes.filter(b => b.outputUrl)
  if (!stored.length) return
  mediaBoxes.value = stored.map(b => ({
    id: b.id,
    stream: useGenerationStream(),
    outputUrl: b.outputUrl,
    mediaType: b.mediaType,
    runId: b.runId,
    isFavorited: b.isFavorited,
    prompt: b.prompt ?? '',
    configId: b.configId ?? '',
    createdAt: b.createdAt ?? 0,
    userSized: true,
  }))
  for (const b of stored) {
    const size = BOX_SIZE[b.mediaType] ?? BOX_START
    const g: BoardItem = { id: b.id, x: b.x, y: b.y, w: b.w ?? size.w, h: b.h ?? size.h }
    // The window it was put down in is not the window it comes back to.
    clampIntoView(g)
    bringToFront(g)
    geom[b.id] = g
  }
}

onMounted(() => {
  restoreMediaBoxes()
  speakFromIdx.value = messages.value.length
  if (personaChat.hasConversation) {
    hasOpened.value = true
  }
  // else: the machine says nothing until it is written to (see sendMessage). No
  // model is called before somebody asks for one — but the line one speaks in
  // stands from the start.
})

// Save dialogue on page leave
onBeforeUnmount(() => {
  stopSpeech()

  savePersonaSession()
})
</script>

<style scoped>
/* The window minus the header, not the whole window: this page sits below the
   header, so 100vh made it 69px too tall and the bottom of it was simply not
   there. That went unnoticed while the conversation lived in a card in the
   middle; with the turn standing on the page itself, the line one speaks in
   sits at the bottom edge and fell straight out of the window. Same measure as
   the workshop page. */
.persona-page {
  position: relative;
  width: 100%;
  height: 100%;
  background: var(--bg-base);
  overflow: hidden;
}

/* ---------- The cards this surface makes ---------- */

/* Placement only. The box itself — frame, bar, grip, ×, the corner that sizes
   it, the back with the prompt — is FlowCard's, the same card the flow throws
   its output into. What stood here before was a re-drawing of half of it, and
   a set of overrides that forced the platform's page-width output frame into
   320px until it clipped everything it was asked to show. */
.floating-media-box {
  position: absolute;
  z-index: 10;
}

/* A card is small; the buttons in it are too. */
.floating-media-box :deep(.action-toolbar) {
  gap: 0.25rem;
}

.floating-media-box :deep(.action-btn) {
  width: 30px;
  height: 30px;
}

/* ---------- Where the turn stands ---------- */

/* The ground the standing turn is placed on: the page itself, with no frame of
   its own. It sits UNDER the floating media boxes (z-index 10), so a box can
   still be picked up and moved across it. It stops above the favourites bar,
   which is fixed to the bottom of the window across the whole platform — an
   absolute box measures from the padding box, so the page's padding would not
   have kept the speak-line clear of it. */
.chat-area {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  bottom: var(--footer-collapsed-height, 36px);
  display: flex;
  flex-direction: column;
  z-index: 5;
}

/* Ends the dialogue. It rides at the end of the line one speaks in, because
   that is what it acts on, and because there is no free corner left for it: the
   words stand from the top left downwards and the figure rests top right. In
   the row it cannot come to lie under a sentence at any window width. */

/* What the voice fills: the whole page below the header. ResonaVoice positions
   the standing turn absolutely inside it, so this is what decides how much room
   the words have. */
.voice-body {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

/* ---------- The input, in the voice's own speak-line ---------- */
/* The open line. It carries the setting of the human's line in the exchange,
   because it IS that line one moment earlier: white, sans, flush left, and no
   furniture around it. Nothing stands in it before it is written in, and
   nothing stands beside it — the Enter key is the entry. */
.write-line {
  display: block; width: 100%; margin: 0; padding: 0;
  background: transparent; border: none; outline: none;
  /* It WRAPS. A text area carries its own height, so it is given one after
     every change (growWriteLine); the scrollbar and the resize grip that come
     with the element are furniture and go. */
  resize: none; overflow: hidden;
  /* Written twice the size it is read at. Writing is what this surface is for,
     so what is being written is the largest thing on it — and it settles to
     reading size the moment it is sent (see .turn-answer.settling in
     components/ResonaVoice.vue). */
  font-family: var(--font-sans); font-size: 2rem; line-height: 1.3;
  color: #ffffff; caret-color: #FFB300; text-align: left;
}
.write-line:disabled { opacity: 0.5; }

/* The surface's one free fixture: what it is set to, at its foot, clear of the
   footer gallery. */
.fixture-gear {
  position: fixed; z-index: 62; pointer-events: auto;
  left: clamp(1rem, 4vw, 3rem);
  bottom: calc(var(--flow-footer-clear, 54px) + 0.4rem);
}
</style>
