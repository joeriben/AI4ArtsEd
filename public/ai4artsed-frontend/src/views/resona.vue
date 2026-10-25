<template>
  <!-- Root-level guards: a drag released over an overlay island (memo card,
       speak dock) must not trigger the browser's default file-drop
       navigation — that would discard the un-persisted board. -->
  <div class="resona-page" @dragover.prevent @drop.prevent>
    <!-- The workshop surface: a zoomable board. Every product Resona makes is a
         free node in one pannable/zoomable world (the Miro metaphor; x2x-flow is
         the template). The world moves and scales; the voice text now scales
         with it too (see ResonaVoice's zoom prop) so it reads as part of the
         same scene, not screen-fixed chrome. Only the input/chrome dock stays
         screen-scale. -->
    <div ref="canvasEl" class="canvas" @pointerdown="onCanvasDown" @wheel="onWheelZoom"
         @dragover.prevent @drop.prevent="onBoardDrop">
      <div class="world" :style="worldStyle">
        <!-- Media: provocations Resona generates -->
        <FlowCard
          v-for="box in mediaBoxes"
          :key="box.id"
          :ref="el => setBoxEl(box.id, el)"
          class="board-node"
          :class="{ selected: selectedId === box.id }"
          :style="nodeStyle(box.id)"
          bar
          resizable
          scroll
          :resize-title="t('resona.resize')"
          :hold-title="t('resonaMediaCard.flipToBack')"
          @grip-down="startBoardDrag($event, box.id)"
          @resize-down="startBoardResize($event, box.id)"
          @wheel="onNodeWheel"
        >
          <MediaCardFront
            :output-url="box.outputUrl"
            :media-type="box.mediaType"
            :run-id="box.runId"
            :error="box.error"
            :is-executing="box.stream?.isExecuting.value ?? false"
            :progress="box.stream?.generationProgress.value ?? 0"
            :preview-image="box.stream?.previewImage.value ?? null"
            :model-meta="box.stream?.modelMeta.value ?? null"
            :stage4-duration-ms="box.stream?.stage4DurationMs.value ?? null"
            :is-favorited="box.isFavorited"
            @image-click="showBox(box)"
          />
          <template #back="{ flipped }">
            <MediaCardBack
              v-bind="backOf(box)"
              :active="flipped"
              @toggle-favorite="toggleFavorite(box)"
              @download="downloadBoxMedia(box)"
            />
          </template>
        </FlowCard>

        <!-- Apparatus runs: Canvas graphs Resona authored -->
        <FlowCard
          v-for="box in graphBoxes"
          :key="box.id"
          :ref="el => setBoxEl(box.id, el)"
          class="board-node"
          :class="{ selected: selectedId === box.id }"
          :style="nodeStyle(box.id)"
          bar
          resizable
          scroll
          :resize-title="t('resona.resize')"
          @grip-down="startBoardDrag($event, box.id)"
          @resize-down="startBoardResize($event, box.id)"
          :hold-title="t('resonaGraphCard.flipToBack')"
          @wheel="onNodeWheel"
        >
          <ResonaGraphCard :box="box" @image-click="fullscreenImage = $event" />
          <template #back>
            <ResonaGraphCardBack :box="box" />
          </template>
        </FlowCard>

        <!-- Post-production: Bild+Ton compositions -->
        <FlowCard
          v-for="box in compositionBoxes"
          :key="box.id"
          :ref="el => setBoxEl(box.id, el)"
          class="board-node"
          :class="{ selected: selectedId === box.id }"
          :style="nodeStyle(box.id)"
          bar
          resizable
          scroll
          :resize-title="t('resona.resize')"
          @grip-down="startBoardDrag($event, box.id)"
          @resize-down="startBoardResize($event, box.id)"
          :hold-title="t('resonaCompositionCard.flipToBack')"
          @wheel="onNodeWheel"
        >
          <ResonaCompositionCard
            :url="box.url"
            :run-id="box.runId"
            :operation="box.operation"
            :composed-from="box.composedFrom"
          />
          <template #back>
            <ResonaCompositionCardBack
              :operation="box.operation"
              :motivation="box.motivation"
              :composed-from="box.composedFrom"
              :created-at="box.createdAt"
            />
          </template>
        </FlowCard>

        <!-- Plans Resona proposed: copy OR lift into a memo -->
        <FlowCard
          v-for="p in planCards"
          :key="p.id"
          :ref="el => setBoxEl(p.id, el)"
          class="board-node plan-node"
          :class="{ selected: selectedId === p.id }"
          :style="nodeStyle(p.id)"
          bar
          resizable
          scroll
          :resize-title="t('resona.resize')"
          @grip-down="startBoardDrag($event, p.id)"
          @resize-down="startBoardResize($event, p.id)"
          @wheel="onNodeWheel"
        >
          <div class="plan-object">
            <div class="plan-card-header">
              <span v-if="p.title" class="plan-card-title">{{ p.title }}</span>
              <div class="plan-actions">
                <button class="plan-copy-btn" @click="copyPlan(p, p.id)">
                  {{ copiedPlanKey === p.id ? t('resona.planCopied') : t('resona.planCopy') }}
                </button>
                <button class="plan-copy-btn" @click="liftPlan(p)">{{ t('resona.lift') }}</button>
                <button class="plan-x" @click="dismissPlan(p.id)" :aria-label="t('resona.removeMemo')">×</button>
              </div>
            </div>
            <p v-if="p.purpose" class="plan-purpose">{{ p.purpose }}</p>
            <ol v-if="p.steps.length" class="plan-steps">
              <li v-for="(sx, i) in p.steps" :key="i">{{ sx }}</li>
            </ol>
            <p v-for="(x, i) in p.extra" :key="'x' + i" class="plan-extra">{{ x }}</p>
          </div>
        </FlowCard>

        <!-- Anchors: what the room worked out, beside what it made -->
        <FlowCard
          v-for="c in entityCards"
          :key="c.id"
          :ref="el => setBoxEl(c.id, el)"
          class="board-node"
          :class="{ selected: selectedId === c.id }"
          :style="nodeStyle(c.id)"
          bar
          closable
          resizable
          scroll
          :resize-title="t('resona.resize')"
          :close-title="t('resonaEntityCard.remove')"
          :hold-title="t('resonaEntityCard.flipToBack')"
          @grip-down="startBoardDrag($event, c.id)"
          @resize-down="startBoardResize($event, c.id)"
          @close="removeEntity(c.id)"
          @wheel="onNodeWheel"
        >
          <ResonaEntityCard :kind="c.kind" :name="c.name" />
          <template #back>
            <ResonaEntityCardBack :detail="c.detail" :facts="c.facts" />
          </template>
        </FlowCard>
      </div>

      <div v-if="speechAvailable" class="voice-mode-switch" @pointerdown.stop>
        <button
          :class="{ on: voiceMode === 'voice' }"
          :title="t('resona.modeVoice')"
          :aria-label="t('resona.modeVoice')"
          @click="setVoiceMode('voice')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="6.4" />
          </svg>
        </button>
        <button
          :class="{ on: voiceMode === 'both' }"
          :title="t('resona.modeBoth')"
          :aria-label="t('resona.modeBoth')"
          @click="setVoiceMode('both')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="8" cy="12" r="4.4" />
            <path d="M15 9h6M15 12.5h6M15 16h4" />
          </svg>
        </button>
        <button
          :class="{ on: voiceMode === 'text' }"
          :title="t('resona.modeText')"
          :aria-label="t('resona.modeText')"
          @click="setVoiceMode('text')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h11" />
          </svg>
        </button>
      </div>

      <div class="view-tools" @pointerdown.stop>
        <button title="+" @click="zoomBy(1.2)">+</button>
        <button title="-" @click="zoomBy(1 / 1.2)">-</button>
        <button class="vt-reset" title="1:1" @click="resetView">1:1</button>
      </div>
    </div>
    <!-- /together board -->

    <!-- The platform's one fullscreen layer; see components/MediaFullscreen.vue. -->
    <!-- A medium with its card's back beside it; a graph as the picture alone. -->
    <MediaFullscreen
      :src="fullscreenImage"
      :back="fullscreenBox ? backOf(fullscreenBox) : null"
      @close="closeFullscreen"
      @toggle-favorite="fullscreenBox && toggleFavorite(fullscreenBox)"
      @download="fullscreenBox && downloadBoxMedia(fullscreenBox)"
    />


    <div class="voice-overlay">
    <!-- The reply is read while it is being written: /api/chat/stream hands
         every piece over as it comes and `streamingId` names the line that is
         still growing. What may STAND is a sentence that is finished AND, where
         this turn is spoken, one whose clip has begun to sound — the writing
         and the voice keep step, they do not race. `cadence` stays unused. -->
    <ResonaVoice
      :trail="voiceTrail"
      :streaming-id="streamingIdx ?? undefined"
      :speak="speakState"
      :anchors="voiceAnchors"
      :lift-label="t('resona.lift')"
      :zoom="zoom"
      :words="showWords"
      :sounding="isSounding"
      :preparing="isPreparing"
      :blocked="isBlocked"
      :tap-label="t('resona.tapToHear')"
      :can-replay="voiceMode !== 'text'"
      :replay-label="t('resona.hearAgain')"
      :coupling="voiceCoupling"
      :line-empty="!userInput && !isLoading"
      @lift="onVoiceLift"
      @replay="onVoiceReplay"
      @reveal-done="onRevealDone"
    >
      <template #speakline>
        <div class="speak-col">
          <div v-if="attachedImagePreview" class="attachment-row">
            <div class="attachment-thumb">
              <img :src="attachedImagePreview" alt="" />
              <button class="attachment-remove" :title="t('resona.removeImage')" @click="removeAttachment">&times;</button>
            </div>
          </div>

          <!-- The open line: the human's own line of this exchange, before it
               is sent. No box around it, nothing written in it beforehand and
               no button beside it — the Enter key is the entry. -->
          <textarea
            ref="pageInputRef"
            v-model="userInput"
            class="write-line"
            rows="1"
            :disabled="isLoading"
            @keydown.enter.exact.prevent="sendMessage"
          ></textarea>
          <input ref="fileInputRef" type="file" accept="image/*" class="hidden-file-input" @change="onFileSelected" />
        </div>
      </template>
    </ResonaVoice>

      <!-- What a decision looks like when this surface asks for one. It stands
           over the surface rather than in the gear, because Resona can raise it
           herself (extractAction) — behind a closed fixture it would be a
           question nobody is shown. -->
      <!-- Not mid-turn for the dropping path: a remember() still in flight
           would land after the purge, stamped with an id the next journal may
           be given back. The gate sits on the acting button. -->
      <SurfaceConfirm
        v-if="pendingAction"
        :text="confirmText"
        :yes="confirmYes"
        :cancel="t('resona.cancel')"
        :danger="pendingAction === 'delete_conversation'"
        :disabled="pendingAction === 'delete_conversation' && isLoading"
        @confirm="runPendingAction()"
        @cancel="pendingAction = null"
      />

      <!-- The two free fixtures of this surface. They lie ON it, at its foot,
           and belong to no bar — there is none any more. What brings material
           in invites (green, breathing); what the surface is set to waits
           (grey, still). -->
      <IntakePlus class="fixture fixture-plus" :disabled="isLoading || isUploading" @pick="fileInputRef?.click()" />
      <SurfaceGear class="fixture fixture-gear" :title="t('resona.surfaceSettings')">
        <div class="journal-notice-row">
          <span class="journal-notice-text">
            {{ journalPaused ? t('resona.journalPaused') : t('resona.journalNotice') }}
          </span>
        </div>
        <button class="journal-toggle-btn" @click="toggleJournalPause">
          {{ journalPaused ? t('resona.journalResume') : t('resona.journalPause') }}
        </button>
        <button class="journal-toggle-btn" @click="pendingAction = 'clear_surface'">
          {{ t('resona.surfaceClear') }}
        </button>
        <!-- Not mid-turn: a remember() still in flight would land after the
             purge and stamp this dropped dialog onto the next one. The record is
             written by the chat call itself, so the request being in flight —
             isLoading — is exactly that window. -->
        <button
          class="journal-toggle-btn journal-delete-btn"
          :disabled="isLoading"
          @click="pendingAction = 'delete_conversation'"
        >
          {{ t('resona.journalNewDialog') }}
        </button>
      </SurfaceGear>
    </div>
    <!-- Lifted memos: free-floating, draggable, resizable; the button in the
         corner folds one to its title and opens it again -->
    <div class="memo-layer" ref="memoLayerRef">
      <div
        v-for="m in memoCards"
        :key="m.id"
        class="memo-card"
        :class="{ collapsed: m.collapsed }"
        :style="m.collapsed
          ? { left: m.x + 'px', top: m.y + 'px', zIndex: m.z }
          : { left: m.x + 'px', top: m.y + 'px', width: m.w + 'px', height: m.h + 'px', zIndex: m.z }"
        @pointerdown="onMemoPointerDown($event, m)"
      >
        <button
          class="memo-fold"
          @pointerdown.stop
          @click.stop="toggleMemoFold(m)"
          :title="m.collapsed ? t('resona.unfoldMemo') : t('resona.foldMemo')"
          :aria-label="m.collapsed ? t('resona.unfoldMemo') : t('resona.foldMemo')"
        >{{ m.collapsed ? '+' : '–' }}</button>
        <button class="memo-x" @pointerdown.stop @click.stop="dismissMemo(m.id)" :aria-label="t('resona.removeMemo')">×</button>
        <template v-if="!m.collapsed">
          <!-- A note the room writes itself is written IN the card: the same
               paper, the same size, no field drawn around it — what is being
               written looks like what has been written, as on the open line.
               It takes the pointer back from the card, or every click into it
               would start a drag or fold the note shut. -->
          <textarea
            v-if="m.source === 'mine'"
            class="memo-text memo-write"
            :data-note="m.id"
            :value="m.text"
            @input="onNoteInput(m, $event)"
            @pointerdown.stop
          ></textarea>
          <p v-else class="memo-text">{{ m.text }}</p>
          <span v-if="m.source !== 'mine'" class="memo-attr">{{ m.source === 'brought' ? t('resona.broughtAttr') : '— Resona' }}</span>
          <div class="memo-resize" :title="t('resona.resize')" @pointerdown="onMemoResizeDown($event, m)"></div>
        </template>
        <span v-else class="memo-title">{{ m.title }}</span>
      </div>
    </div>

    <PlatformVoice ref="platformVoice" :anchors="platformVoiceAnchors" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, shallowReactive, shallowRef, triggerRef, watch } from 'vue'
import MediaFullscreen from '@/components/MediaFullscreen.vue'
import type { MediaBack } from '@/components/mediaBack'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useFavoritesStore } from '@/stores/favorites'
import { useLabAuthStore } from '@/stores/labAuth'
import { sseEvents } from '@/lib/sseStream'
import { useDeviceId } from '@/composables/useDeviceId'
import { useGenerationStream } from '@/composables/useGenerationStream'
import { startCanvasRun, fetchCanvasPartial, type CanvasRunHandle } from '@/composables/useCanvasRunStream'
import { usePanZoom, type BoardItem } from '@/composables/usePanZoom'
import {
  useMaterialIntake,
  uploadImageFile,
  uploadImageFromUrl,
  quickImageSafetyCheck,
  quickTextSafetyCheck,
  type QuickSafetyResult,
} from '@/composables/useMaterialIntake'
import type { AsmItem } from '@/composables/useAssemblageBoard'
import { useSafetyEventStore } from '@/stores/safetyEvent'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { findFreeSpot as findFreeSpotIn, type Rect } from '@/composables/useFreeSpot'
import { readBoard, writeBoard, forgetBoard, type BoardPayload } from './resona_board_memory'
import IntakePlus, { type IntakeKind } from '@/components/IntakePlus.vue'
import SurfaceGear from '@/components/SurfaceGear.vue'
import SurfaceConfirm from '@/components/SurfaceConfirm.vue'
import { useDirectWriting, growWriteLine } from '@/composables/useDirectWriting'
import FlowCard from '@/components/FlowCard.vue'
import ResonaEntityCard from '@/components/ResonaEntityCard.vue'
import ResonaEntityCardBack from '@/components/ResonaEntityCardBack.vue'
import MediaCardFront from '@/components/MediaCardFront.vue'
import MediaCardBack from '@/components/MediaCardBack.vue'
import ResonaGraphCard from '@/components/ResonaGraphCard.vue'
import ResonaGraphCardBack from '@/components/ResonaGraphCardBack.vue'
import ResonaCompositionCard from '@/components/ResonaCompositionCard.vue'
import ResonaCompositionCardBack from '@/components/ResonaCompositionCardBack.vue'
import type { GraphRunBox, GraphProgressRow, GraphResultItem } from './resona_graph_types'
import ResonaVoice from '@/components/ResonaVoice.vue'
import { useSpeech, useSpokenTurn, speechTrace, primeSpeech, splitForSpeech } from '@/composables/useSpeech'
import type { VoiceUtterance, VoiceAnchor, SpeakState } from '@/components/ResonaVoice.vue'
import PlatformVoice, {
  type PlatformVoiceHandle,
  type VoiceAnchor as PlatformVoiceAnchor,
} from '@/components/PlatformVoice.vue'
import { apiBase } from '@/services/labApi'
import { downloadMedia, mediaExtension } from '@/lib/downloadMedia'

const { t, locale } = useI18n()
const route = useRoute()
const userPreferences = useUserPreferencesStore()
const favoritesStore = useFavoritesStore()
const labAuth = useLabAuthStore()
const deviceId = useDeviceId()
const pageContextStore = usePageContextStore()

// ---------- Platform voice: where a sentence about this page may dock ----------
// Chrome that always stands on this view. Nothing inside .world is used as an
// anchor - the workshop board pans and zooms, its nodes leave the viewport.
const platformVoiceAnchors: PlatformVoiceAnchor[] = [
  // The line the workshop writes in: attach, camera, text field, send
  { id: 'compose', selector: '.write-line', words: ['eingabe', 'input', 'schreib', 'textfeld', 'frage'] },
  // Werkstatt-Journal notice with its pause / new-dialog buttons
  { id: 'journal', selector: '.fixture-gear', words: ['journal', 'aufzeichnung', 'mitschrift', 'protokoll'] },
  // Voice / both / text switch on the right edge
  { id: 'speech-mode', selector: '.voice-mode-switch', words: ['stimme', 'sprachausgabe', 'gesprochen', 'voice', 'spoken', 'speech'] },
  // Zoom and 1:1 controls of the workshop board
  { id: 'view-tools', selector: '.view-tools', words: ['zoom', 'maßstab', 'massstab', 'vergrößer', 'verkleiner'] },
]

interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
  /** Drafts this turn wrote and then took back on its own evidence duty. They
   *  STAY on the surface, struck through, with the checked version under them:
   *  a model correcting itself against what it has actually read is one of the
   *  few places where the difference this platform argues for is visible. */
  withdrawn?: string[]
  /** What this platform has to say about the turn — that nothing came, that the
   *  reply broke off, that the connection failed. It stands under the line and
   *  reads like any other sentence there, and it stays OUT of the history: a
   *  notice handed back to the model as its own previous utterance is a
   *  sentence the model then imitates. On 2026-09-09 a whole turn came back as
   *  "The answer did not arrive. Please send it again." — the line above it
   *  said exactly that, and the model read it as the house style. */
  notice?: string
}

/** Put a platform notice on a line, under whatever already stands there. */
function note(line: ChatMsg | undefined, text: string) {
  if (!line) return
  line.notice = line.notice ? line.notice + '\n\n' + text : text
}

const messages = ref<ChatMsg[]>([])
const userInput = ref('')
const isLoading = ref(false)

// ---------- Page context: what this page is, and what stands in the line now ----------
// The same spine every other view registers on (setPageContext -> formatForLLM).
// Without it the platform voice is handed a route path and nothing else.
const pageContext = computed<PageContext>(() => ({
  activeViewType: 'resona',
  pageDescription:
    'Die Werkstatt-Seite mit Resona, einer Begleitung für Workshops. Ein verschieb- und zoombares Brett trägt, was im Gespräch entsteht: Medien, die Resona erzeugt, Läufe von Canvas-Graphen, die sie selbst geschrieben hat, Bild-Ton-Kompositionen und Pläne, die sie vorschlägt; aus Gesagtem lassen sich Notizzettel auf das Brett heben. Resona spricht auf dem Brett selbst, nicht in einem Chatfenster; die Sprachausgabe steht wahlweise auf Stimme, auf Stimme und Text oder nur auf Text. Unten steht die Schreibzeile mit Bildanhang und Kamera, darüber der Hinweis auf das Werkstatt-Journal, das mitschreibt und pausiert oder verworfen werden kann.',
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

// ---------- Werkstatt-Journal (R1/J1): restore on mount, opt-out recording ----------

const JOURNAL_HISTORY_CAP = 40 // addendum D2: request history capped; UI still shows all
const journalId = ref<string | null>(null)
const pendingAction = ref<'new_conversation' | 'delete_conversation' | 'clear_surface' | null>(null)
const confirmText = computed(() =>
  pendingAction.value === 'delete_conversation' ? t('resona.newDialogConfirm')
    : pendingAction.value === 'clear_surface' ? t('resona.surfaceClearConfirm')
      : t('resona.newConfirm'))
const confirmYes = computed(() =>
  pendingAction.value === 'delete_conversation' ? t('resona.newDialogConfirmYes')
    : pendingAction.value === 'clear_surface' ? t('resona.surfaceClearConfirmYes')
      : t('resona.newConfirmYes'))
function runPendingAction() {
  if (pendingAction.value === 'delete_conversation') void deleteConversation()
  else if (pendingAction.value === 'clear_surface') clearSurface()
  else startNewConversation()
}
const journalPaused = ref(localStorage.getItem('resona_journal_paused') === '1')

function toggleJournalPause() {
  journalPaused.value = !journalPaused.value
  localStorage.setItem('resona_journal_paused', journalPaused.value ? '1' : '0')
}

async function restoreJournal() {
  try {
    // Resume the ACTIVE journal (localStorage pointer survives "new conversation"
    // and delete); fall back to ensure(device_id) for a first/again-empty session.
    let jid: string | null = null
    let eventCount = 0
    const activeId = localStorage.getItem('resona_active_journal')
    if (activeId) {
      const metaRes = await fetch(`${apiBase()}/api/resona/journal/${activeId}?offset=0&limit=1`)
      if (metaRes.ok) {
        const md = await metaRes.json()
        jid = md?.meta?.journal_id || activeId
        eventCount = md?.meta?.event_count || 0
      } else {
        localStorage.removeItem('resona_active_journal') // stale/deleted
      }
    }
    if (!jid) {
      const ensureRes = await fetch(`${apiBase()}/api/resona/journal/ensure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: deviceId }),
      })
      if (!ensureRes.ok) return
      const ensureData = await ensureRes.json()
      jid = ensureData?.journal_id || null
      eventCount = ensureData?.event_count || 0
    }
    if (!jid) return
    journalId.value = jid
    localStorage.setItem('resona_active_journal', jid)

    // Restore the MOST RECENT window, not the oldest: offset from event_count.
    const restoreOffset = Math.max(0, eventCount - 500)
    const readRes = await fetch(`${apiBase()}/api/resona/journal/${jid}?offset=${restoreOffset}&limit=500`)
    if (!readRes.ok) return
    const readData = await readRes.json()
    const events: Array<{ type: string; payload: { role?: string; content?: string } }> = readData?.events || []
    const restored: ChatMsg[] = events
      .filter(e => e.type === 'dialog' && (e.payload?.role === 'user' || e.payload?.role === 'assistant'))
      .map(e => ({ role: e.payload.role as 'user' | 'assistant', content: e.payload.content || '' }))
    if (restored.length) {
      messages.value = restored
      await nextTick()
    }
  } catch (e) {
    console.error('[RESONA] Journal restore failed:', e)
  }
}

function resetConversationView() {
  stopSpeech()
  // A new conversation starts at zero, so its first reply is a turn again.
  speakFromIdx.value = 0
  // The board is cleared under her; give the turn a fresh place to stand
  // rather than leaving it on a point chosen for the old scene.
  placeVoiceSpot()
  messages.value = []
  planCards.value = []
  memoCards.value = []
  mediaBoxes.value = []
  graphBoxes.value = []
  compositionBoxes.value = []
  entityCards.value = []
  lastAnchor.value = null
  // Anything staged but not yet sent belonged to the old conversation too —
  // otherwise it rides along into the first turn of the new one.
  userInput.value = ''
  removeAttachment()
  clearBoard()
  // The page's own words stood ON this scene — the address, or an answer the
  // platform voice gave about it. With the board emptied under them they are
  // grey text about nothing, so they go with it.
  platformVoice.value?.clear()
}

// ---------- What the surface keeps across a reload ----------
//
// The items on the area survive a reload of the page and a leaving of it.
// What is written down here is the decision about WHAT survives; the envelope
// around it — the key, the version, the device stamp, the failures it
// swallows — is in resona_board_memory.ts.
//
// Two kinds do not come back, because they cannot: a generation still on the
// wire and an apparatus still running. Both hang on a stream that dies with the
// page, and a card that came back saying "running" would say it forever.

/** A media box as it is kept: everything but the stream, which is not a value. */
type StoredMediaBox = Omit<MediaBox, 'stream'>
/** An apparatus card as it is kept. The live progress list goes: it is what was
 *  happening, and by the time it is read again nothing is. */
type StoredGraphBox = Omit<GraphRunBox, 'progress'>

function boardSnapshot(): BoardPayload {
  return {
    geom: JSON.parse(JSON.stringify(geom)),
    pan: { x: pan.x, y: pan.y },
    zoom: zoom.value,
    media: mediaBoxes.value
      .filter(b => b.brought || b.outputUrl !== null || b.error)
      .map(({ stream: _stream, ...rest }) => rest),
    compositions: compositionBoxes.value,
    graphs: graphBoxes.value
      .filter(g => g.status !== 'running')
      .map(({ progress: _progress, ...rest }) => rest),
    entities: entityCards.value,
    memos: memoCards.value,
    plans: planCards.value,
    // Without these the closing payload of the last turn would spawn a second
    // card for everything the restored board already carries (firstSighting).
    intents: [...spawnedIntents],
  }
}

/** One past the highest `<prefix><n>` among ids already in use. */
function nextSeq(ids: string[], prefix: string): number {
  let top = -1
  for (const id of ids) {
    if (!id.startsWith(prefix)) continue
    const n = Number(id.slice(prefix.length))
    if (Number.isInteger(n) && n > top) top = n
  }
  return top + 1
}

function restoreBoard() {
  const b = readBoard(deviceId)
  if (!b) return
  try {
    for (const [id, item] of Object.entries((b.geom ?? {}) as Record<string, BoardItem>)) {
      geom[id] = { ...item }
    }
    const p = b.pan as { x: number; y: number } | undefined
    if (p && typeof p.x === 'number' && typeof p.y === 'number') { pan.x = p.x; pan.y = p.y }
    if (typeof b.zoom === 'number') zoom.value = b.zoom
    mediaBoxes.value = ((b.media ?? []) as StoredMediaBox[]).map(m => ({ ...m, stream: null }))
    compositionBoxes.value = (b.compositions ?? []) as CompositionBox[]
    graphBoxes.value = ((b.graphs ?? []) as StoredGraphBox[]).map(g => ({ ...g, progress: [] }))
    entityCards.value = (b.entities ?? []) as EntityCard[]
    memoCards.value = (b.memos ?? []) as MemoCard[]
    planCards.value = (b.plans ?? []) as PlanCard[]
    for (const id of (b.intents ?? []) as string[]) spawnedIntents.add(id)
    // The counters hand out ids; restarting them at zero would hand out ones
    // that are already on the board. It is the HIGHEST number in use plus one,
    // not the count: cards get taken away, and after two removals a count walks
    // straight back onto an id that is still standing.
    memoSeq = nextSeq(memoCards.value.map(m => m.id), 'memo-')
    planSeq = nextSeq(planCards.value.map(c => c.id), 'plan-')
  } catch (e) {
    console.error('[RESONA] Board restore failed:', e)
  }
}

let boardSaveTimer: ReturnType<typeof setTimeout> | null = null
function saveBoardNow() {
  if (boardSaveTimer) { clearTimeout(boardSaveTimer); boardSaveTimer = null }
  writeBoard(deviceId, boardSnapshot())
}
function scheduleBoardSave() {
  if (boardSaveTimer) clearTimeout(boardSaveTimer)
  boardSaveTimer = setTimeout(saveBoardNow, 700)
}

/** Everything lying on the surface goes. The dialogue and the journal stay —
 *  this is the surface being cleared, not the record being dropped. */
function clearSurface() {
  for (const h of graphRunHandles) h.cancel()
  graphRunHandles.clear()
  mediaBoxes.value = []
  compositionBoxes.value = []
  graphBoxes.value = []
  entityCards.value = []
  memoCards.value = []
  planCards.value = []
  spawnedIntents.clear()
  lastAnchor.value = null
  clearBoard()
  // The page's own words stood ON this scene; with it emptied they are grey
  // text about nothing (same reasoning as resetConversationView).
  platformVoice.value?.clear()
  forgetBoard()
  pendingAction.value = null
}

// A turn sent without a journal writes memory that no later "new dialog" can
// ever drop (the record lands unattributed), so the send path insists on one
// rather than trusting that mount-time restore succeeded.
async function ensureJournal(): Promise<void> {
  try {
    const res = await fetch(`${apiBase()}/api/resona/journal/ensure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: deviceId }),
    })
    if (!res.ok) return
    const d = await res.json()
    if (!d?.journal_id) return
    journalId.value = d.journal_id
    localStorage.setItem('resona_active_journal', d.journal_id)
  } catch (e) {
    console.error('[RESONA] ensure journal failed:', e)
  }
}

async function startNewConversation() {
  pendingAction.value = null
  try {
    const res = await fetch(`${apiBase()}/api/resona/journal/new`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: deviceId }),
    })
    if (!res.ok) return
    const d = await res.json()
    if (!d?.journal_id) return
    journalId.value = d.journal_id
    localStorage.setItem('resona_active_journal', d.journal_id)
    resetConversationView()
  } catch (e) {
    console.error('[RESONA] new conversation failed:', e)
  }
}

// "New dialog": the old journal AND the working notes Resona made in it go.
// The server does both halves (resona_routes.journal_delete) — a client that
// only dropped the journal would leave the memory digest to reappear in the
// next turn's prompt, which is what this path exists to stop.
async function deleteConversation() {
  pendingAction.value = null
  const jid = journalId.value
  if (jid) {
    let ok = false
    try {
      const res = await fetch(`${apiBase()}/api/resona/journal/${jid}`, { method: 'DELETE' })
      ok = res.ok
    } catch (e) {
      console.error('[RESONA] new dialog (delete) failed:', e)
    }
    // Nothing was dropped, so nothing is cleared: the group keeps the dialog
    // in front of them instead of an empty board over data still on the server.
    if (!ok) return
  }
  // The board is cleared and the pointer dropped BEFORE the new journal is
  // asked for. If that request fails, the group is left with an empty board and
  // no journal — not with the dropped dialog still on screen, silently writing
  // into an id the server no longer knows.
  journalId.value = null
  localStorage.removeItem('resona_active_journal')
  resetConversationView()
  await startNewConversation()
}

// ---------- Plan blocks (C0) ----------

// Parse [[PLAN: title]] ... [[/PLAN]] out of assistant messages and render
// them as structured cards. Raw text stays untouched in messages/history/
// journal — parsing happens only at render time.
interface PlanSegment {
  type: 'plan'
  title: string
  purpose: string | null
  steps: string[]
  extra: string[]
}
interface TextSegment {
  type: 'text'
  text: string
}
type MsgSegment = PlanSegment | TextSegment

const PLAN_BLOCK_RE = /\[\[PLAN:\s*([^\]\n]*)\]\]([\s\S]*?)\[\[\/PLAN\]\]/g
// [[ACTION: new_conversation|delete_conversation]] — Resona SURFACES a reset/delete
// for the group to confirm; she never executes it (the human presses the chip).
const ACTION_BLOCK_RE = /\[\[ACTION:\s*(new_conversation|delete_conversation)\s*\]\]/i

function parsePlanBody(title: string, body: string): PlanSegment {
  const steps: string[] = []
  const extra: string[] = []
  let purpose: string | null = null
  for (const rawLine of body.split('\n')) {
    const line = rawLine.trim()
    if (!line) continue
    const stepMatch = line.match(/^\d+[.)]\s+(.*)$/)
    if (stepMatch) {
      steps.push(stepMatch[1] ?? '')
      continue
    }
    const purposeMatch = line.match(/^(zweck|purpose)\s*:\s*(.*)$/i)
    if (purposeMatch && purpose === null) {
      purpose = purposeMatch[2] ?? ''
      continue
    }
    extra.push(line)
  }
  return { type: 'plan', title: title.trim(), purpose, steps, extra }
}

// plan blocks are pulled into persistent objects (extractPlans); the voice gets plain prose

const copiedPlanKey = ref<string | null>(null)
let copiedResetTimer: ReturnType<typeof setTimeout> | null = null

function copyPlan(seg: PlanSegment, key: string) {
  const lines: string[] = []
  if (seg.title) lines.push(seg.title)
  if (seg.purpose) lines.push(`Zweck: ${seg.purpose}`)
  seg.steps.forEach((s, i) => lines.push(`${i + 1}. ${s}`))
  lines.push(...seg.extra)
  navigator.clipboard
    ?.writeText(lines.join('\n'))
    .then(() => {
      copiedPlanKey.value = key
      if (copiedResetTimer) clearTimeout(copiedResetTimer)
      copiedResetTimer = setTimeout(() => {
        copiedPlanKey.value = null
      }, 1500)
    })
    .catch(() => {
      /* clipboard unavailable (insecure context) — stay silent */
    })
}

// ---------- Board (zoomable planning canvas) ----------
// The workshop is a Miro-style board: every product Resona makes is a free,
// draggable/resizable node in one pannable, zoomable world. usePanZoom is the
// shared engine (Rule #13); x2x-flow is the template. Geometry lives in a
// reactive map keyed by node id, kept SEPARATE from the shallowRef content
// arrays so streaming's triggerRef pattern stays intact: the engine mutates
// geometry (reactive -> the node re-renders), the stream mutates content.
const {
  pan,
  zoom,
  worldStyle,
  zoomBy,
  reset: resetView,
  startPan,
  onWheelZoom,
  selectedId,
  bringToFront,
  startItemDrag,
  startItemResize,
} = usePanZoom({ initialPan: { x: 40, y: 40 }, minZoom: 0.4, maxZoom: 2 })

const canvasEl = ref<HTMLElement | null>(null)
function onCanvasDown(e: PointerEvent) {
  // Pan only when the gesture starts on the empty board, never on a node.
  if (e.target === canvasEl.value) {
    selectedId.value = null
    startPan(e)
  }
}
// The canvas wheel handler pans the world and calls preventDefault(), so a
// wheel bubbling out of a node cancelled that node's own scroll: a card taller
// than its box could only be read by dragging the scrollbar thumb. Same defect
// x2x-flow had (46cb0e72), same guard — but conditional, because a board node
// is not a textarea: only a body that can still take the scroll swallows the
// event, so wheeling over a card that fits, or past its end, keeps panning the
// board as before.
// A node holds two scrollers, not one: the body of the face that is up, and —
// while the card is turned — the body of its back. Both are FlowCard's now, one
// drawing of them for the whole platform. So walk from what was actually under
// the pointer up to the card.
function onNodeWheel(e: WheelEvent) {
  if (e.deltaY === 0) return // sideways wheel pans the board, as it always did
  const outer = e.currentTarget as HTMLElement
  let el: HTMLElement | null = e.target as HTMLElement | null
  while (el) {
    const room = el.scrollHeight - el.clientHeight
    if (room > 0 && getComputedStyle(el).overflowY !== 'visible') {
      const spent = e.deltaY < 0 ? el.scrollTop <= 0 : el.scrollTop >= room - 1
      if (!spent) {
        e.stopPropagation()
        return
      }
    }
    if (el === outer) return
    el = el.parentElement
  }
}

const geom = reactive<Record<string, BoardItem>>({})
// A new product lands on a FREE spot in the current view — never on top of an
// existing node, and never under the standing words (the voice is part of the
// scene). Scan the visible world top-left -> bottom-right; if the view is full,
// continue just below its lowest occupant.
const NODE_GAP = 28
type WorldRect = Rect
function viewWorldRect(): WorldRect {
  const el = canvasEl.value
  const cw = el?.clientWidth ?? 1280
  const ch = el?.clientHeight ?? 800
  return { x: -pan.x / zoom.value, y: -pan.y / zoom.value, w: cw / zoom.value, h: ch / zoom.value }
}
// The scan itself is shared with the contesting surface (useFreeSpot); what
// stays here is what only this board knows: which rectangles are occupied, and
// that the standing words are one of them.
function findFreeSpot(w: number, h: number, avoidVoice = true): { x: number; y: number } {
  const rects: WorldRect[] = Object.values(geom).map(g => ({ x: g.x, y: g.y, w: g.w, h: g.h }))
  if (avoidVoice) {
    const vr = voiceSpotRect()
    if (vr) rects.push(vr)
  }
  return findFreeSpotIn(viewWorldRect(), rects, w, h, { gap: NODE_GAP })
}
function placeNode(id: string, w: number, h: number) {
  const s = findFreeSpot(w, h)
  const g: BoardItem = { id, x: Math.round(s.x), y: Math.round(s.y), w, h }
  bringToFront(g)
  geom[id] = g
}
/** Place a node centered under a deliberate human drop point (world coords). */
function placeNodeAt(id: string, at: { x: number; y: number }, w: number, h: number) {
  const g: BoardItem = { id, x: Math.round(at.x - w / 2), y: Math.round(at.y - h / 2), w, h }
  bringToFront(g)
  geom[id] = g
}
function dropNode(id: string) {
  delete geom[id]
}
function clearBoard() {
  for (const k of Object.keys(geom)) delete geom[k]
}
function nodeStyle(id: string) {
  const g = geom[id]
  if (!g) return {}
  return { left: g.x + 'px', top: g.y + 'px', width: g.w + 'px', height: g.h + 'px', zIndex: g.z }
}
function startBoardDrag(e: PointerEvent, id: string) {
  if (geom[id]) startItemDrag(e, geom[id])
}
function startBoardResize(e: PointerEvent, id: string) {
  if (geom[id]) startItemResize(e, geom[id], { mode: 'free', minW: 180, maxW: 920, minH: 120, maxH: 1200 })
}

// ---------- Plan objects (C0): persistent — copy or lift into a memo ----------
interface PlanCard extends PlanSegment { id: string }
const planCards = ref<PlanCard[]>([])
let planSeq = 0
function extractPlans(content: string): string[] {
  const created: string[] = []
  if (!content.includes('[[PLAN:')) return created
  PLAN_BLOCK_RE.lastIndex = 0
  let m: RegExpExecArray | null
  while ((m = PLAN_BLOCK_RE.exec(content)) !== null) {
    const seg = parsePlanBody(m[1] ?? '', m[2] ?? '')
    const planId = 'plan-' + (planSeq++)
    placeNode(planId, 300, 210)
    planCards.value = [...planCards.value, { ...seg, id: planId }].slice(-12)
    created.push(planId)
  }
  return created
}
function liftPlan(p: PlanCard) {
  const lines: string[] = []
  if (p.title) lines.push(p.title)
  if (p.purpose) lines.push(p.purpose)
  p.steps.forEach((step, i) => lines.push(`${i + 1}. ${step}`))
  p.extra.forEach(x => lines.push(x))
  liftToMemo(lines.join('\n'))
}
function dismissPlan(id: string) { planCards.value = planCards.value.filter(p => p.id !== id); dropNode(id) }

// ---------- Fullscreen ----------

const fullscreenImage = ref<string | null>(null)
/**
 * The media box standing large, so its back stands beside the picture (one
 * click, one view, on every surface). A
 * graph card opens the picture alone and leaves this empty. Shallow, as the
 * list of boxes is: a box carries its generation stream.
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
    motivation: box.motivation,
    prompt: box.prompt,
    configId: box.configId,
    createdAt: box.createdAt,
    modelMeta: box.stream?.modelMeta.value ?? null,
  }
}

// ---------- Media boxes (Resona's generate_media provocations) ----------

interface MediaBox {
  id: string
  /** null while nothing is on the wire: brought material has never had one, and
   *  a box restored after a reload cannot get its own back. */
  stream: ReturnType<typeof useGenerationStream> | null
  /** Brought in by a human (dropped favourite / OS file) rather than generated
   *  here. Until 2026-09-10 this was read off `stream === null`, which held
   *  only as long as the board died with the page: a restored generated box
   *  has no stream either, and would have been reported to Resona as material
   *  somebody carried in. */
  brought: boolean
  outputUrl: string | null
  mediaType: string
  runId: string | null
  error: boolean
  isFavorited: boolean
  // J2 provenance — carried from the generate_media intent to the card back.
  // null also marks brought material — the journal reporters skip it
  // (journal governance; since the 2026-07-17 grant Resona perceives drops
  // via context.brought_items instead — never via the journal).
  intentId: string | null
  motivation: string | null
  prompt: string
  configId: string
  createdAt: number
}

const mediaBoxes = shallowRef<MediaBox[]>([])

// ---------- Composition boxes (Resona's post-production — Bild+Ton) ----------
// A compose_media call returns a FINISHED artifact (server-side ffmpeg mux via
// post_production_service), so unlike mediaBoxes/graphBoxes there is nothing to
// execute client-side: we hold the url + provenance and render it as a still you
// can play. No stream, no abort — the work is already done when the box appears.
interface ComposedSource {
  role: string
  run_id: string
  type: string
}
interface GeneratedComposition {
  intent_id?: string | null
  operation: string
  url: string
  run_id?: string | null
  media_type?: string
  motivation?: string | null
  composed_from: ComposedSource[]
}
interface CompositionBox {
  id: string
  url: string
  runId: string | null
  operation: string
  motivation: string | null
  composedFrom: ComposedSource[]
  createdAt: number
}
const compositionBoxes = shallowRef<CompositionBox[]>([])

// A turn announces what it built TWICE by design: once the moment the tool
// returns, so that a closing sentence cut mid-word cannot take the built thing
// with it, and once again in the closing payload — for the blocking mouth of
// the chat endpoint, and for a surface that was opened after the event went
// past. The second sighting is dropped here, by the intent id the server
// minted, so the board carries one card per built thing.
const spawnedIntents = new Set<string>()
function firstSighting(intentId: string | null | undefined): boolean {
  if (!intentId) return true
  if (spawnedIntents.has(intentId)) return false
  spawnedIntents.add(intentId)
  return true
}

function addComposition(c: GeneratedComposition) {
  if (!firstSighting(c.intent_id)) return
  const compId = `comp-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
  placeNode(compId, 280, 240)
  compositionBoxes.value = [...compositionBoxes.value, {
    id: compId,
    url: c.url,
    runId: c.run_id ?? null,
    operation: c.operation,
    motivation: c.motivation ?? null,
    composedFrom: c.composed_from || [],
    createdAt: Date.now(),
  }]
}

// ---------- Graph boxes (Resona's apparatus runs — authored Canvas graphs) ----------
// Each generated_graphs[] entry becomes an apparatus card: we execute its
// executor-ready workflow via /api/canvas/execute-stream and render progress
// then the pedagogically relevant outputs. shallowRef + triggerRef mirrors
// mediaBoxes (boxes mutate in place during the stream).
const graphBoxes = shallowRef<GraphRunBox[]>([])
// Handles for in-flight graph run streams, cancelled on unmount.
const graphRunHandles = new Set<CanvasRunHandle>()

interface GeneratedMediaIntent {
  config_id: string
  prompt: string
  motivation?: string | null
  intent_id?: string | null
}

async function spawnGeneration(intent: GeneratedMediaIntent) {
  if (!firstSighting(intent.intent_id)) return
  const stream = useGenerationStream()
  const box: MediaBox = {
    id: `gen-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    stream,
    brought: false,
    outputUrl: null,
    mediaType: 'image',
    runId: null,
    error: false,
    isFavorited: false,
    intentId: intent.intent_id || null,
    motivation: intent.motivation || null,
    prompt: intent.prompt,
    configId: intent.config_id,
    createdAt: Date.now(),
  }
  placeNode(box.id, 280, 300)
  mediaBoxes.value = [...mediaBoxes.value, box]

  let resultStatus: 'completed' | 'blocked' | 'error' | 'cancelled' = 'error'
  try {
    const result = await stream.executeWithStreaming({
      prompt: intent.prompt,
      output_config: intent.config_id,
      device_id: `${deviceId}_resona${Date.now()}`,
      source_view: 'resona',
    })
    if (result.status === 'blocked' || result.status === 'cancelled') {
      resultStatus = result.status
    }
    if (result.status === 'success' && result.media_output) {
      const mo = result.media_output
      const runId = mo.run_id || result.run_id || null
      const mediaType = mo.media_type || 'image'
      const mediaIndex = mo.index ?? 0
      if (runId) {
        box.runId = runId
        box.mediaType = mediaType
        // Build the media URL from run_id + type (canonical pattern, mirrors persona).
        // Do NOT trust media_output.url: the backend emits inconsistent url formats
        // per media type and omits it entirely on some audio paths.
        box.outputUrl = mediaType === '3d'
          ? (mo.mesh_url || `/api/media/3d/${runId}`)
          : `/api/media/${mediaType}/${runId}/${mediaIndex}`
        resultStatus = 'completed'
        triggerRef(mediaBoxes)
      }
    }
    if (!box.outputUrl) {
      // No usable result (error status, blocked, or missing run_id) — show it.
      box.error = true
      triggerRef(mediaBoxes)
    }
  } catch (e) {
    console.error('[RESONA] Generation failed:', e)
    box.error = true
    triggerRef(mediaBoxes)
  }
  reportMediaResult(box, resultStatus)
}

// J2 provenance: report how a generate_media intent ended back into the
// Werkstatt-Journal (media_result event). Best effort — never blocks the UI;
// respects the journal pause (K1). For blocked results only the generic
// status is recorded, never safety details.
async function reportMediaResult(box: MediaBox, status: 'completed' | 'blocked' | 'error' | 'cancelled') {
  if (!box.intentId || !journalId.value || journalPaused.value) return
  try {
    await fetch(`${apiBase()}/api/resona/journal/${journalId.value}/media`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        intent_id: box.intentId,
        status,
        run_id: box.runId,
        media_type: box.mediaType,
        media_url: box.outputUrl,
        seed: typeof box.stream?.modelMeta.value?.seed === 'number' ? box.stream.modelMeta.value.seed : null,
        device_id: deviceId,
      }),
    })
  } catch (e) {
    console.warn('[RESONA] media_result journal write failed (non-fatal):', e)
  }
}

// ---------- Apparatus runs: execute Resona-authored Canvas graphs ----------

interface GeneratedGraph {
  title: string
  motivation?: string | null
  intent_id?: string | null
  workflow: { nodes: unknown[]; connections: unknown[] }
  summary: string
}

// Node types whose output is a pedagogically relevant text result.
const TEXT_RESULT_TYPES = new Set(['evaluation', 'comparison_evaluator', 'interception', 'translation'])

// Walk complete.results in execution order and keep only the outputs that matter
// pedagogically: every generation node's image/media, every evaluation/comparison/
// interception/translation node's text. seed/resolution/quality/input/collector/
// display are ignored.
function extractGraphResults(
  results: Record<string, unknown>,
  executionOrder: string[],
): GraphResultItem[] {
  const items: GraphResultItem[] = []
  const order = executionOrder.length ? executionOrder : Object.keys(results)
  for (const nodeId of order) {
    const r = results[nodeId] as Record<string, unknown> | undefined
    if (!r) continue
    const nodeType = String(r.type ?? '')
    if (nodeType === 'generation') {
      const output = r.output as Record<string, unknown> | null
      const url = output && typeof output === 'object' ? (output.url as string | undefined) : undefined
      if (!url) continue
      const mediaType = output && typeof output === 'object' ? (output.media_type as string | undefined) : undefined
      items.push({
        nodeId,
        nodeType,
        kind: !mediaType || mediaType === 'image' ? 'image' : 'media',
        url,
        meta: (r.metadata as GraphResultItem['meta']) ?? undefined,
      })
    } else if (TEXT_RESULT_TYPES.has(nodeType)) {
      // evaluation stores commentary under outputs.commentary; the rest use output.
      const outputs = r.outputs as Record<string, unknown> | undefined
      const text =
        (typeof r.output === 'string' ? r.output : undefined) ??
        (outputs && typeof outputs.commentary === 'string' ? (outputs.commentary as string) : undefined)
      if (!text || !text.trim()) continue
      items.push({ nodeId, nodeType, kind: 'text', text })
    }
  }
  return items
}

async function spawnGraphRun(g: GeneratedGraph) {
  if (!firstSighting(g.intent_id)) return
  // REACTIVE, and that is the whole reason this card ever showed anything but
  // its first moment. The card takes the box as ONE prop (`:box="box"`), unlike
  // the media card, which takes its fields one by one. A plain object mutated
  // in place keeps its identity, so Vue compares the child's props, finds them
  // unchanged and skips the child — no matter how often the array around it is
  // triggered. Every apparatus therefore stood at "wird aufgebaut" for the
  // whole of its run and past the end of it, while the run itself completed on
  // the server and wrote its images to disk.
  const box: GraphRunBox = shallowReactive({
    id: `graph-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    intentId: g.intent_id || null,
    title: g.title,
    motivation: g.motivation || null,
    summary: g.summary || '',
    workflow: {
      nodes: (g.workflow?.nodes || []) as Array<Record<string, unknown>>,
      connections: (g.workflow?.connections || []) as Array<Record<string, unknown>>,
    },
    status: 'running',
    progress: [],
    results: [],
    lastEventIndex: -1,
    recovered: [],
    startedAt: Date.now(),
  })
  placeNode(box.id, 320, 320)
  graphBoxes.value = [...graphBoxes.value, box]

  // Pull the finished pieces of a torn run off disk and show them as PARTIAL.
  // Reuses the server's partial endpoint, whose URLs point at the same media
  // serve path a completed run uses. Returns true if anything was recovered.
  // (Image filter + box mapping are consumer policy; the fetch lives in the
  // shared client.)
  async function recoverPartial(opts: { keepError?: boolean } = {}): Promise<boolean> {
    if (!box.runId) return false
    const body = await fetchCanvasPartial(box.runId, apiBase())
    if (!body) return false
    const imgs = (body.items || []).filter((it) => it.kind === 'image' && it.url)
    if (!imgs.length) return false
    box.recovered = imgs.map((it) => ({
      kind: 'image' as const, url: it.url, index: it.index, nodeLabel: it.node_label,
    }))
    box.recoveredPending = body.prompts_pending ?? 0
    // A torn connection leaves a PARTIAL run. A node that failed leaves a
    // FAILED one — that stays said. Either way the finished pieces are shown.
    if (!opts.keepError) box.status = 'partial'
    box.finishedAt = Date.now()
    return true
  }

  // The shared client owns transport, SSE framing, the `?after=` cursor and
  // the reconnect/status loop; this view owns every box mutation.
  const handle = startCanvasRun(
    {
      nodes: box.workflow.nodes,
      connections: box.workflow.connections,
      device_id: deviceId,
      lang: locale.value,
    },
    {
      baseUrl: apiBase(),
      reconnect: true,
      onEvent: (event) => {
        // Mirror the core cursor onto the box (GraphRunBox contract unchanged).
        if (typeof event.id === 'number' && event.id > box.lastEventIndex) {
          box.lastEventIndex = event.id
        }
        switch (event.type) {
          case 'run_started': {
            const d = event.data as { run_id?: string }
            if (d.run_id) box.runId = d.run_id
            break
          }
          case 'progress': {
            const d = event.data as { node_id: string; node_type: string; message?: string }
            const row: GraphProgressRow = { nodeId: d.node_id, nodeType: d.node_type, message: d.message }
            box.progress = [...box.progress, row]
            break
          }
          case 'node_complete': {
            const d = event.data as {
              node_id: string
              node_type: string
              output_preview?: { type?: string; url?: string; preview?: string } | null
            }
            const preview = d.output_preview
            if (preview) {
              for (let i = box.progress.length - 1; i >= 0; i--) {
                const row = box.progress[i]
                if (row && row.nodeId === d.node_id) {
                  if (preview.type === 'image' && preview.url) row.previewUrl = preview.url
                  else if (preview.type === 'text' && preview.preview) row.previewText = preview.preview
                  break
                }
              }
              box.progress = [...box.progress]
            }
            break
          }
          case 'complete': {
            const d = event.data as {
              results: Record<string, unknown>
              executionOrder: string[]
              exportPath?: string
              run_id?: string
            }
            box.results = extractGraphResults(d.results || {}, d.executionOrder || [])
            if (d.run_id) box.runId = d.run_id
            else if (d.exportPath) {
              const parts = d.exportPath.split('/').filter(Boolean)
              box.runId = parts.length ? parts[parts.length - 1] : box.runId
            }
            box.status = 'complete'
            box.finishedAt = Date.now()
            break
          }
          case 'error': {
            const d = event.data as { message?: string }
            box.status = 'error'
            box.error = d.message || 'Execution failed'
            box.finishedAt = Date.now()
            break
          }
        }
      },
    },
  )
  graphRunHandles.add(handle)
  const outcome = await handle.done
  graphRunHandles.delete(handle)

  let reportStatus: 'completed' | 'error' = 'error'
  switch (outcome.kind) {
    case 'aborted':
      return  // silent: no error card, no journal write (pre-refactor behavior)
    case 'complete':
      reportStatus = 'completed'
      break
    case 'server_error':
      // The run failed and stays failed, but what it rendered before failing is
      // not lost with it: same recovery the torn path uses, error line kept.
      await recoverPartial({ keepError: true })
      reportStatus = 'error'  // box already set to error inside onEvent
      break
    case 'torn': {
      // error present = thrown network tear (Safari "Load failed" / Chrome
      // "Failed to fetch"); absent = clean EOF after exhausted reconnects.
      // Either way, try to recover finished pieces by run_id first.
      if (outcome.error) console.error('[RESONA] Graph run failed:', outcome.error)
      const recovered = await recoverPartial()
      if (!recovered) {
        box.status = 'error'
        box.error = outcome.error
          ? t('resonaGraphCard.connectionLost')
          : (box.error || t('resonaGraphCard.connectionLost'))
        box.finishedAt = Date.now()
      }
      reportStatus = 'error'  // provenance: the run did not finish cleanly
      break
    }
    case 'transport_error': {
      console.error('[RESONA] Graph run failed:', outcome.error)  // raw thrown value, as before
      // outcome.error is the raw thrown value: re-derive rawMsg exactly as the
      // legacy outer catch did, so non-Error throws surface 'Network error'.
      const rawMsg = outcome.error instanceof Error ? outcome.error.message : ''
      box.status = 'error'
      box.error = rawMsg || 'Network error'
      box.finishedAt = Date.now()
      reportStatus = 'error'
      break
    }
  }
  reportGraphResult(box, reportStatus)
}

async function reportGraphResult(box: GraphRunBox, status: 'completed' | 'error') {
  if (!box.intentId || !journalId.value || journalPaused.value) return
  try {
    await fetch(`${apiBase()}/api/resona/journal/${journalId.value}/media`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        intent_id: box.intentId,
        status,
        run_id: box.runId ?? null,
        media_type: 'canvas',
        device_id: deviceId,
      }),
    })
  } catch (e) {
    console.warn('[RESONA] graph media_result journal write failed (non-fatal):', e)
  }
}

async function downloadBoxMedia(box: MediaBox) {
  if (!box.outputUrl) return
  const runIdMatch = box.outputUrl.match(/\/api\/media\/\w+\/(.+)$/)
  const runId = runIdMatch ? runIdMatch[1] : 'media'
  const ext = mediaExtension(box.mediaType)
  await downloadMedia(box.outputUrl, `ai4artsed_${runId}.${ext}`)
}

async function toggleFavorite(box: MediaBox) {
  if (!box.runId) return
  // The global gallery view can surface foreign favorites. Since 2026-08-29
  // the backend refuses a foreign delete (favorites_routes `_may_change`), so
  // this is no longer the only thing standing in the way — it stays because a
  // dropped foreign favorite is view-only, and a toggle that can only come
  // back as a 403 is not worth offering.
  const rec = favoritesStore.favorites.find(f => f.run_id === box.runId)
  if (rec && rec.device_id && rec.device_id !== deviceId) return
  const success = await favoritesStore.toggleFavorite(
    box.runId,
    box.mediaType as 'image' | 'video' | 'audio' | 'music' | '3d',
    deviceId,
    'anonymous',
    'resona'
  )
  if (success) {
    box.isFavorited = !box.isFavorited
    triggerRef(mediaBoxes)
  }
}

// ---------- Material intake (human gesture: favorites drag-in + OS file drop) ----------
// Shared implementation: useMaterialIntake (Rule #13). Resona only adapts the
// results onto its own board structures. PERCEPTION GRANT 2026-07-17: drops
// now enter /api/chat as context.brought_items (ids + capped text excerpts,
// built in callChat via buildBroughtItems). Brought images are auto-perceived
// server-side (a short caption inline), with view_favorite / view_upload for a
// full look; the deliberate tool act adds detail, it is no longer the only
// way she sees. Unchanged governance:
// drops write NO Werkstatt-Journal events (intentId stays null), the voice
// anchor pick still skips brought boxes (she speaks only at her own
// products), and the paperclip attach flow stays untouched.

const safetyStore = useSafetyEventStore()

// Per-type node sizes for brought material on the board.
const DROP_NODE_SIZES: Record<string, { w: number; h: number }> = {
  image: { w: 280, h: 300 },   // matches generated MediaBox default (spawnGeneration)
  video: { w: 280, h: 220 },
  audio: { w: 280, h: 140 },
  music: { w: 280, h: 140 },   // music favorites keep mediaType 'music' but render the slim audio player
}

/** A favorite record this device owns (the global view can hold foreign favorites). */
function isOwnFavorite(runId: string): boolean {
  const rec = favoritesStore.favorites.find(f => f.run_id === runId)
  return !!rec && (!rec.device_id || rec.device_id === deviceId)
}

/** Screen -> world through the live pan/zoom (inverse of voiceSpot's mapping). */
function worldPoint(e: { clientX: number; clientY: number }): { x: number; y: number } | null {
  const el = canvasEl.value
  if (!el) return null
  const r = el.getBoundingClientRect()
  return { x: (e.clientX - r.left - pan.x) / zoom.value, y: (e.clientY - r.top - pan.y) / zoom.value }
}

/** A box comes off the board, with its node. */
function removeBroughtBox(id: string) {
  mediaBoxes.value = mediaBoxes.value.filter(b => b.id !== id)
  dropNode(id)
}

function addBroughtBox(
  mediaType: string,
  outputUrl: string | null,
  runId: string | null,
  meta: AsmItem['meta'],
  at: { x: number; y: number } | null,
): MediaBox {
  const box: MediaBox = {
    id: `drop-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    stream: null,                 // nothing on the wire
    brought: true,
    outputUrl,
    mediaType,
    runId,
    error: false,
    isFavorited: runId ? isOwnFavorite(runId) : false,
    intentId: null,               // governance: journal reporters must skip this box
    motivation: null,
    prompt: meta?.prompt ?? '',
    configId: meta?.config ?? '',
    createdAt: Date.now(),
  }
  const size = DROP_NODE_SIZES[box.mediaType] ?? DROP_NODE_SIZES.image!
  if (at) placeNodeAt(box.id, at, size.w, size.h)
  else placeNode(box.id, size.w, size.h)
  mediaBoxes.value = [...mediaBoxes.value, box]
  return box
}

/**
 * Adapter handle for a brought media box. The intake mutates AsmItem fields
 * AFTER the adder returns (drop-centering, upload resolving — the
 * useAssemblageBoard protocol). mediaBoxes is a shallowRef and geometry lives
 * in `geom`, so the handle forwards writes to the box (+ triggerRef) and to
 * the node's BoardItem.
 */
function broughtBoxHandle(box: MediaBox, kind: AsmItem['kind']): AsmItem {
  return {
    id: box.id,
    kind,
    get x() { return geom[box.id]?.x ?? 0 },
    set x(v: number) { const g = geom[box.id]; if (g) g.x = Math.round(v) },
    get y() { return geom[box.id]?.y ?? 0 },
    set y(v: number) { const g = geom[box.id]; if (g) g.y = Math.round(v) },
    get w() { return geom[box.id]?.w ?? 0 },
    set w(v: number) { const g = geom[box.id]; if (g) g.w = v },
    get h() { return geom[box.id]?.h ?? 0 },
    set h(v: number) { const g = geom[box.id]; if (g) g.h = v },
    get src() { return box.outputUrl ?? undefined },
    set src(v: string | undefined) { box.outputUrl = v ?? null; triggerRef(mediaBoxes) },
    get runId() { return box.runId ?? undefined },
    set runId(v: string | undefined) {
      box.runId = v ?? null
      box.isFavorited = v ? isOwnFavorite(v) : false
      triggerRef(mediaBoxes)
    },
    get failed() { return box.error },
    set failed(v: boolean | undefined) { box.error = !!v; triggerRef(mediaBoxes) },
    // The preview is already visible on the card — no spinner state for brought material.
    uploading: false,
    imageId: undefined,
    path: undefined,
  }
}

/**
 * A memo brought from elsewhere, judged after it is laid down. It goes again if
 * the check refuses it or could not run — the same hand a refused picture gets.
 */
async function holdUnlessChecked(card: MemoCard, text: string) {
  const safety = await quickTextSafetyCheck(text, locale.value)
  if (safety.safe) return
  if (!memoCards.value.some(c => c.id === card.id)) return
  memoCards.value = memoCards.value.filter(c => c.id !== card.id)
  safetyStore.reportBlock(1, safety.errorMessage || '', [], undefined, safety.operational)
}

/** World -> memo-layer coords (memos live in a screen-space layer). */
function worldToMemoLayer(wx: number, wy: number): { x: number; y: number } {
  let x = 90, y = 96
  const canvas = canvasEl.value
  const layer = memoLayerRef.value
  if (canvas && layer) {
    const cr = canvas.getBoundingClientRect()
    const lr = layer.getBoundingClientRect()
    // world -> screen -> memo-layer space (layers share the page origin today;
    // the rect delta keeps this correct if that ever changes)
    x = Math.max(0, Math.min(layer.clientWidth - 48, Math.round(cr.left - lr.left + pan.x + wx * zoom.value)))
    y = Math.max(0, Math.min(layer.clientHeight - 40, Math.round(cr.top - lr.top + pan.y + wy * zoom.value)))
  }
  return { x, y }
}

/**
 * Dropped text becomes a memo (the workshop's kept-text element) with the
 * "brought along" attribution. The intake sets `.text` AFTER the adder
 * returns (useAssemblageBoard protocol), so the handle creates the memo
 * lazily on the first non-empty write — an empty text favorite leaves the
 * board unchanged.
 */
function broughtTextHandle(wx: number, wy: number): AsmItem {
  const p = worldToMemoLayer(wx, wy)
  let card: MemoCard | null = null
  return {
    id: `memo-drop-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    kind: 'text',
    x: p.x, y: p.y, w: 300, h: 190,
    get text() { return card?.text ?? '' },
    set text(v: string | undefined) {
      const trimmed = (v ?? '').trim()
      if (!trimmed) return
      if (card) {
        card.text = trimmed
        card.title = memoTitle(trimmed)
        return
      }
      const next: MemoCard = {
        id: 'memo-' + memoSeq++, text: trimmed, title: memoTitle(trimmed),
        x: p.x, y: p.y, w: 300, h: 190, collapsed: false, z: ++memoZ, source: 'brought',
      }
      memoCards.value = [...memoCards.value, next].slice(-16)
      card = next
      // Brought text is text that reaches the model: every turn puts this memo
      // into `brought_items`, and it carries the level of the session that
      // wrote it, which need not be the level of this room. The typed line into
      // the same conversation has been checked all along; this one was not.
      void holdUnlessChecked(next, trimmed)
    },
  }
}

// The intake needs a file-input ref only for its pickImage()/onFilePick()
// surface; Resona renders none and never calls either. The paperclip input
// (attach flow) is deliberately NOT handed over: that channel is the one
// human-initiated way an image reaches Resona, and drops must not reuse it.
const intakeFileInput = ref<HTMLInputElement | null>(null)

const { onDrop: intakeDrop } = useMaterialIntake({
  fileInput: intakeFileInput,
  adapter: {
    toWorldPoint: worldPoint,
    // Text favorites / held prompts land as memos at the drop point.
    addText: (x = 80, y = 80) => broughtTextHandle(x, y),
    // OS-file images: box first (data-URL preview); the intake then centers
    // it, uploads, runs the quick input check and swaps src to the served URL.
    addImage: (src, x, y) => {
      const box = addBroughtBox('image', src, null, undefined, null)
      const g = geom[box.id]
      if (g && x !== undefined && y !== undefined) { g.x = Math.round(x); g.y = Math.round(y) }
      return broughtBoxHandle(box, 'image')
    },
    // ARTIFACT_DT drag-in (audio/video by run): free spot, then the intake centers.
    addMedia: (kind, src, runId, x, y) => {
      const box = addBroughtBox(kind, src, runId, undefined, null)
      const g = geom[box.id]
      if (g && x !== undefined && y !== undefined) { g.x = Math.round(x); g.y = Math.round(y) }
      return broughtBoxHandle(box, kind)
    },
    // A safety-blocked upload comes off the surface entirely.
    removeItem: (id) => removeBroughtBox(id),
    // Restored favorites: the VIEW owns placement — centered under the pointer
    // or on a free spot.
    //
    // The board shows brought material, and what it shows TRAVELS: every turn
    // puts the box into `brought_items`, and the server reads the picture with
    // a vision model to caption it. So a favourite dropped here is checked like
    // any other picture that enters this surface — it carries the level of the
    // session that made it, which need not be the level of this room, and
    // Stage 3 checks an image at kids and youth level only. It went unchecked
    // until 2026-09-04, on the reading that nothing here feeds a pipeline,
    // while the file drop beside it was checked all along.
    placeArtifactImage: async (runId, url, meta, at) => {
      // The box goes down where the hand let go, and the check runs under it —
      // the same order the file drop beside it has always used. Waiting for the
      // verdict first left the board blank for as long as a vision model takes,
      // which in a room reads as a dropped gesture and is dropped again.
      const box = addBroughtBox('image', url, runId, meta, at)
      try {
        const up = await uploadImageFromUrl(url, `${runId || 'favorite'}.png`)
        const safety = await quickImageSafetyCheck(up.path)
        // The board may have moved on: the box taken away by hand, or this page
        // left. Then this answer belongs to nothing.
        if (!mediaBoxes.value.some(b => b.id === box.id)) return
        if (safety.safe) {
          if (safety.vlmDescription) safetyStore.reportAnalysis(safety.vlmDescription, true)
          return
        }
        removeBroughtBox(box.id)
        safetyStore.reportBlock(
          'vlm_input',
          safety.errorMessage || '',
          [],
          safety.vlmDescription,
          safety.operational,
        )
      } catch {
        // The picture could not be got as far as a verdict — its run cleaned up,
        // the upload refused, the connection gone. Unjudged is unjudged, and the
        // box travels in every turn of this conversation, so it comes off.
        removeBroughtBox(box.id)
        safetyStore.reportBlock('vlm_input', '', [], undefined, true)
      }
    },
    placeArtifactMedia: (kind, src, runId, meta, at) => {
      // meta.mediaType keeps 'music' on the card (download extension + favorite type).
      addBroughtBox(meta?.mediaType ?? kind, src, runId, meta, at)
    },
    artifactDragSource: () => null,  // the workshop board has no drag-out node
    // Safety surface = the platform-global safetyEvent store -> ChatOverlay.
    // That overlay is Träshy, a different agent — nothing reaches Resona.
    reportSafetyBlocked: (r: QuickSafetyResult) =>
      safetyStore.reportBlock(
        'vlm_input',
        r.errorMessage || t('safetyBlocked.inputImage'),
        [],
        r.vlmDescription,
        // Whether the check judged the picture or could not run at all. The
        // window says a different sentence for each, and it must not have to
        // read that out of the wording.
        r.operational,
      ),
    reportSafetyAnalysis: (d: string) => safetyStore.reportAnalysis(d, true),
  },
})

function onBoardDrop(e: DragEvent) {
  intakeDrop(e)
}

// ---------- Image input (attach + camera) ----------

const fileInputRef = ref<HTMLInputElement | null>(null)
const attachedImagePath = ref<string | null>(null)
const attachedImagePreview = ref<string | null>(null)
const isUploading = ref(false)


/**
 * A picture attached to the conversation, from the file button or the camera.
 *
 * It goes through the platform's own intake — upload, then the image check —
 * like every other picture that enters a surface. Until 2026-09-04 this
 * function posted the file itself and put the path straight into the composer,
 * so a photograph taken here reached the vision model with nobody having looked
 * at it; the board intake of this same view was checked all along.
 */
async function uploadImageBlob(blob: Blob, filename: string) {
  isUploading.value = true
  try {
    const up = await uploadImageFile(new File([blob], filename, { type: blob.type || 'image/jpeg' }))
    const safety = await quickImageSafetyCheck(up.path)
    if (!safety.safe) {
      safetyStore.reportBlock(
        'vlm_input',
        safety.errorMessage || t('safetyBlocked.inputImage'),
        [],
        safety.vlmDescription,
        safety.operational,
      )
      return
    }
    if (safety.vlmDescription) safetyStore.reportAnalysis(safety.vlmDescription, true)
    attachedImagePath.value = up.path
    attachedImagePreview.value = up.servedUrl
  } catch (e) {
    console.error('[RESONA] Image upload failed:', e)
  } finally {
    isUploading.value = false
  }
}

function onFileSelected(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) uploadImageBlob(file, file.name)
  input.value = ''
}

function removeAttachment() {
  attachedImagePath.value = null
  attachedImagePreview.value = null
}

function saveBoardOnLeave() { saveBoardNow() }

onMounted(async () => {
  loadSpeechStatus()
  // Before anything else: the surface comes back as it was left.
  restoreBoard()
  window.addEventListener('pagehide', saveBoardOnLeave)
  // The turn needs a resting place from the start — before, and independently
  // of, anything being said.
  placeVoiceSpot()
  await restoreJournal()
  // From here on, replies are turns and are spoken.
  speakFromIdx.value = messages.value.length
})

onUnmounted(() => {
  window.removeEventListener('pagehide', saveBoardOnLeave)
  saveBoardNow()
  stopSpeech()
  // Cancel any in-flight apparatus run streams so their readers don't leak.
  for (const h of graphRunHandles) h.cancel()
  graphRunHandles.clear()
})


// ---------- Ambient voice: state fed to the shared <ResonaVoice> ----------
//
// The reply arrives as a stream (/api/chat/stream, `streamingIdx`), and the
// words and the voice follow it as it grows. The token cadence that was once
// simulated on top of a whole reply is gone; the stream itself is the pace.

// [[PLAN:]] blocks are pulled into persistent plan-objects (see extractPlans),
// never spoken in the fading voice. Raw content stays in messages[] untouched.
function stripPlans(content: string): string {
  return content
    .replace(PLAN_BLOCK_RE, '')
    // Any action marker, whichever action: a marker is never prose, and one
    // this surface has no chip for stands nowhere.
    .replace(/\[\[ACTION:[^\]]*\]\]/gi, '')
    // A block still being written — `[[PLAN:` with no `[[/PLAN]]` yet, or the
    // first characters of its marker at the very end of the text — is not
    // prose either. It is cut off at its opening, so that neither the words
    // nor the voice carry half a plan while the rest of it arrives. A block
    // that never closes (a reply that broke off inside it) goes with it: what
    // a plan says is on its card, and a card needs the block whole. A `[[`
    // in prose that is none of the markers stands.
    .replace(/\[\[(?:PLAN|ACTION|\/PLAN)\b[\s\S]*$/i, '')
    .replace(/\[\[[A-Za-z\/]{0,6}$/, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

// The words are SPOKEN. Markdown scaffolding (bold marks, backticks, headers)
// is document syntax — it never reaches the standing line.
function stripSpoken(content: string): string {
  return stripPlans(content)
    // Unpaired as well as paired: while the text is arriving, the closing
    // marks are not there yet, and a sentence that went to the voice with its
    // asterisks would no longer be the sentence that stands once they close.
    // Asterisks inside a code span go with them (`**kwargs` stands as kwargs);
    // this surface is a workshop, and code is read nowhere on it.
    .replace(/\*\*/g, '')
    .replace(/`/g, '')
    .replace(/^#{1,6}\s+/gm, '')
    // The evidence duty's own notation, `[src: …]` and `[own]`, taken off the
    // way evidence_duty.strip_markers takes it off the closing reply. The
    // pieces of the stream never pass that filter, and a sentence goes to the
    // voice before the closing reply exists.
    .replace(/[ \t]*\[\s*(?:src\s*:\s*[^\]]*?|own)\s*\]\s*(?=[.,;:!?])/gi, '')
    .replace(/[ \t]*\[\s*(?:src\s*:\s*[^\]]*?|own)\s*\]/gi, '')
    // A marker still open at the end of the arriving text — `[src: Die Stadt`
    // with its `]` not there yet, or the first letters of one — stays out too:
    // a full stop inside it would otherwise close a sentence for the voice
    // that the closing text, marker gone, does not have.
    .replace(/[ \t]*\[\s*(?:s(?:r(?:c(?:\s*:[^\]]*)?)?)?|o(?:w(?:n)?)?)$/i, '')
}

// Resona surfaces reset/delete as a confirm chip (she never runs it herself).
function extractAction(content: string) {
  const m = content.match(ACTION_BLOCK_RE)
  if (m) pendingAction.value = m[1] as 'new_conversation' | 'delete_conversation'
}

// ---- Faden anchors: the object boxes an utterance can thread to ----
const boxEls = new Map<string, HTMLElement>()
function setBoxEl(id: string | number, el: unknown) {
  const k = String(id)
  // A node is a FlowCard now, so the ref hands over a component instance and
  // not an element. The voice draws its thread to the box's rectangle — without
  // reaching through to $el the map stayed empty and the thread had nothing to
  // hold on to.
  const node = el instanceof HTMLElement ? el : (el as { $el?: unknown } | null)?.$el
  if (node instanceof HTMLElement) boxEls.set(k, node)
  else boxEls.delete(k)
}
// The most recent reply that produced an object, and which object; voiceTrail
// turns this into an anchorId so ResonaVoice can draw the thread.
const lastAnchor = ref<{ msgIdx: number; boxId: string } | null>(null)
const voiceAnchors = computed<VoiceAnchor[]>(() => {
  const rect = (id: string) => () => boxEls.get(id)?.getBoundingClientRect() ?? null
  const out: VoiceAnchor[] = []
  for (const b of mediaBoxes.value) out.push({ id: String(b.id), getRect: rect(String(b.id)) })
  for (const b of graphBoxes.value) out.push({ id: String(b.id), getRect: rect(String(b.id)) })
  for (const b of compositionBoxes.value) out.push({ id: String(b.id), getRect: rect(String(b.id)) })
  for (const b of planCards.value) out.push({ id: String(b.id), getRect: rect(String(b.id)) })
  return out
})

// Where the voice STANDS when there is no object to stand at: a free point ON
// the board (world coords), chosen per turn and collision-checked against the
// nodes, so the words pan and zoom with the scene instead of sticking to the
// glass. Situated — the screen-fixed corner is only the last-resort fallback.
const voiceSpotWorld = ref<{ x: number; y: number } | null>(null)
function voiceTurnWorldSize() {
  const cw = canvasEl.value?.clientWidth ?? 1280
  // Voice only: a row of chips with the human's line beneath it, not a
  // standing paragraph. Reserving the paragraph's footprint is what pushed that
  // small block into the corner of a box three times its size.
  if (!showWords.value) return { w: Math.min(360, cw * 0.28), h: 150 }
  // ~ .turn width min(56ch, 40vw) at 1.12rem, plus a few standing lines.
  const px = Math.min(590, cw * 0.4)
  // The turn scales with the board (ResonaVoice's zoom prop), so its screen size
  // is px * zoom and its WORLD footprint is constant. Do not divide by zoom —
  // that was right only while the words stayed screen-scale, and would now
  // mis-size the collision rect (nodes landing on the words at zoom > 1).
  return { w: px, h: 200 }
}
function voiceSpotRect(): WorldRect | null {
  const s = voiceSpotWorld.value
  if (!s) return null
  const d = voiceTurnWorldSize()
  return { x: s.x, y: s.y, w: d.w, h: d.h }
}
let voiceSpotRetries = 0
function placeVoiceSpot() {
  // The first turn is placed while the board is still being laid out. With a
  // canvas of width 0 every measurement below collapses to the corner — which
  // is exactly where the voice kept ending up. Wait for a real size.
  if (!canvasEl.value?.clientWidth) {
    if (voiceSpotRetries++ < 60) requestAnimationFrame(placeVoiceSpot)
    return
  }
  voiceSpotRetries = 0
  const d = voiceTurnWorldSize()
  // The exchange stands in the MIDDLE of the view. The two sides only read as
  // opposed -- agent's words to the right edge, the human's line to the left --
  // in a column that has a middle to be measured from. This point is the
  // column's top left; the rect it spans is what the board's free-spot search
  // keeps new cards out of (voiceSpotRect), which is where "if there is room"
  // now does its work: the cards give way, not the exchange.
  const view = viewWorldRect()
  voiceSpotWorld.value = {
    x: view.x + Math.max(0, (view.w - d.w) / 2),
    y: view.y + Math.max(0, (view.h - d.h) / 2),
  }
}

// A fresh assistant line that stands free (no anchor) gets a fresh spot; runs
// post-flush so nodes spawned by the same reply are already placed and avoided.
const lastSaidIdx = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i]!.role === 'assistant') return i
  }
  return -1
})
watch(lastSaidIdx, idx => {
  if (idx < 0) return
  if (lastAnchor.value?.msgIdx === idx) return
  placeVoiceSpot()
}, { flush: 'post' })
// The opening turn already stands while Resona is still thinking (ResonaVoice
// raises the listening state as soon as the human has spoken). Give it a spot
// right then, or those first words would appear in the CSS fallback corner and
// only jump onto the board once the reply lands.
watch(() => messages.value.length, () => {
  if (lastSaidIdx.value >= 0 || voiceSpotWorld.value) return
  if (messages.value.some(m => m.role === 'user')) placeVoiceSpot()
}, { flush: 'post' })

// Read-only render copy for the voice. messages[] is never mutated here — how
// the words stand up and give way is ResonaVoice's job, and purely visual.
const voiceTrail = computed<VoiceUtterance[]>(() => {
  const out: VoiceUtterance[] = []
  messages.value.forEach((msg, idx) => {
    const said = msg.role === 'assistant' ? stripSpoken(msg.content) : msg.content
    const text = msg.notice ? (said ? said + '\n\n' + msg.notice : msg.notice) : said
    // An empty line is nothing to stand up — except while it is being written,
    // where it is the line about to carry the answer.
    if (!text && !(msg.withdrawn?.length) && idx !== streamingIdx.value) return
    out.push({
      id: idx,
      role: msg.role,
      text,
      anchorId: lastAnchor.value && lastAnchor.value.msgIdx === idx ? lastAnchor.value.boxId : undefined,
      liftable: msg.role === 'assistant',
      withdrawn: msg.withdrawn?.map(stripSpoken).filter(Boolean),
    })
  })
  return out
})

// Listening while the request is out, idle once the reply stands. The written
// line is its own liveness while it grows; 'speaking' belongs to the acoustic
// voice and is set by the coupling, not here.
const speakState = computed<SpeakState>(() => (isLoading.value ? 'listening' : 'idle'))

/** Which line is still being written, by index into messages. */
const streamingIdx = ref<number | null>(null)

// ---------- How Resona is present: heard, read, or both ----------
//
// Voice only is the default: nothing of hers is written and what she says is
// heard. In that mode she is present as sound and as what she makes, and
// nothing else — the turn keeps only the way back to the line and the way to
// keep it (see ResonaVoice).
// Where a platform language has no voice in the model it is
// spoken in English, so voice only would leave nothing at all in the workshop's
// own language — there the default is writing instead. Since the move to
// Supertonic 3 (2026-08-08) that is Hebrew alone; before it, it was five
// languages. Which ones is never written down here: the default asks
// `speaksInFallback()`, which reads /api/speech/status, so swapping the model
// moves the line by itself. The choice is the human's either way and is
// remembered per browser.
type VoiceMode = 'voice' | 'both' | 'text'
const VOICE_MODE_KEY = 'resona_voice_mode'

const {
  isAvailable: speechAvailable,
  speakingKey,
  pendingKey,
  blockedKey,
  soundingPiece,
  loadStatus: loadSpeechStatus,
  speak: speakAloud,
  stop: stopSpeech,
  resume: resumeSpeech,
  speaksInFallback,
} = useSpeech()

const chosenVoiceMode = ref<VoiceMode | null>(
  (localStorage.getItem(VOICE_MODE_KEY) as VoiceMode | null) || null
)
const voiceMode = computed<VoiceMode>(() => {
  if (!speechAvailable.value) return 'text'
  return chosenVoiceMode.value ?? (speaksInFallback(locale.value) ? 'text' : 'voice')
})
function setVoiceMode(mode: VoiceMode) {
  // Choosing to be spoken to is itself the gesture that opens the ear.
  if (mode !== 'text') primeSpeech()
  chosenVoiceMode.value = mode
  localStorage.setItem(VOICE_MODE_KEY, mode)
  if (mode === 'text') stopSpeech()
}
const showWords = computed(() => voiceMode.value !== 'voice')
// ---------- The open line ----------
//
// Nothing in the corner stands for this agent. It is present in what it says,
// in the voice that says it and in what it makes on the board: no
// representation, only presentation in the action. The mask in the app
// overlay is help, exactly as on every other page.
const pageInputRef = ref<HTMLTextAreaElement | null>(null)

// The open line wraps as it is written in, and a wrapping line has to be told
// its own height. Hung on the model rather than on the keystroke, so it also
// holds for the ways in that never touch the keyboard: writing from anywhere on
// the surface, and the line cleared on send.
watch(userInput, () => { void nextTick(() => growWriteLine(pageInputRef.value)) })

// ---------- Writing is the default way in ----------
//
// A keystroke anywhere lands in the open line, which stands in the exchange
// itself (composables/useDirectWriting, components/ResonaVoice.vue).
function focusCompose() {
  void nextTick(() => pageInputRef.value?.focus())
}

useDirectWriting({
  text: userInput,
  focus: focusCompose,
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

const isSounding = computed(() => speakingKey.value !== null)
/** Being synthesized — a different thing from being audible, and much longer. */
const isPreparing = computed(() => pendingKey.value !== null)
/** Synthesized, but the browser wants a tap before it sounds. */
const isBlocked = computed(() => blockedKey.value !== null)

/** The utterance this surface has ASKED to be spoken — set before the request
 *  and unset when it has settled, one way or the other. See the speak watcher. */
const askedKey = ref<number | null>(null)

// The voice sets the pace of the words: where Resona is heard AND read, a
// sentence stands up when its piece begins to sound. Being read alone has no
// voice to follow and being heard alone writes nothing, so both hand over
// nothing and the words keep the rhythm they have always had.
//
// The fields are ACCESSORS, not the values they had when this object was made.
// The turn's own words are handed to the voice component in a render, and the
// key that says "this is being spoken" is set after that render, by the watcher
// below — so a snapshot would reach the words one render too late, every time,
// and the whole reply would already be standing before the coupling could hold
// anything back. Read live, the words are held from the very first pass. That
// the object then never changes is worth having on a board this size: a piece
// starting to sound no longer re-renders the entire workshop.
const voiceCoupling = computed(() => {
  if (voiceMode.value !== 'both') return null
  return {
    get piece() { return soundingPiece.value },
    get askedKey() { return askedKey.value },
    get pendingKey() { return pendingKey.value },
    get speakingKey() { return speakingKey.value },
    get blockedKey() { return blockedKey.value },
    // The words must be cut the way the audio was cut, or sentence and piece
    // are not the same thing. The component is given the cutter because it must
    // stay usable where nothing is spoken at all.
    segment: splitForSpeech,
  }
})

// Restored history is a record, not a turn: Resona does not read the journal
// back to the room on page load. Only what is said from here on is spoken.
const speakFromIdx = ref(Number.POSITIVE_INFINITY)

// Switching modes changes the voice's footprint; without this the chip row
// keeps the paragraph's box (or the other way round) until the next turn.
watch(showWords, () => { if (voiceSpotWorld.value) placeVoiceSpot() }, { flush: 'post' })

// Watched together with the writing: the line is pushed empty and grows, so
// its INDEX no longer changes when the turn becomes speakable. What says the
// turn is whole is the writing being over.
watch([lastSaidIdx, streamingIdx], ([idx, streaming]) => {
  // Whether a voice is coming is decided when the turn BEGINS, not when it is
  // finished. The words follow it sentence by sentence, and they can only do
  // that if they know from their first pass that one is on the way: a reply
  // that arrives while nothing has been asked stands complete before the first
  // clip exists, and voice and writing then run side by side, which is wrong:
  // the sentences must not arrive in parallel.
  const speakable =
    idx >= 0 && idx >= speakFromIdx.value && voiceMode.value !== 'text' && speechAvailable.value
  if (streaming !== null) {
    if (speakable && idx === streaming) askedKey.value = idx
    return
  }
  speechTrace(`Resona-Zug ${idx}: mode=${voiceMode.value}, ab=${speakFromIdx.value}, `
    + `gewaehlt=${chosenVoiceMode.value ?? '—'}, verfuegbar=${speechAvailable.value}`)
  // Asked while it was arriving and not spoken after all: the words are
  // released rather than left waiting for a voice that never comes.
  const stay = (why: string) => {
    speechTrace('  still: ' + why)
    spoken.end()
    if (askedKey.value === idx) askedKey.value = null
  }
  if (idx < 0 || idx < speakFromIdx.value) {
    return stay('aelter als der Sitzungsanfang (wiederhergestellt)')
  }
  if (voiceMode.value === 'text') return stay('Schreib-Modus')
  const msg = messages.value[idx]
  if (!msg) return stay('kein Zug an diesem Platz')
  const said = stripSpoken(msg.content)
  if (!said) return stay('nichts Gesprochenes in diesem Zug')
  // Said here, one line before the asking, because the speech itself cannot say
  // it early enough: speak() may reach its own key only a microtask later, or
  // return before it ever sets one (nothing to say, no voice available, too
  // long a text). This surface knows NOW that it is asking, and the words that
  // are to follow this voice need that answer on the very pass that stands the
  // turn up. It is unsaid again the moment the asking is over, however it
  // ended — a voice that is over is one the words no longer have to follow.
  askedKey.value = idx
  spoken.hand(idx, said, true)
}, { flush: 'post' })

// ---- The voice follows the writing ----
//
// A sentence goes to the voice once the stream has begun the sentence after
// it, and the last one goes with the closing text: the first sentence is
// readable after two or three seconds, and the reply takes ten or twenty
// more. What waits, what is dropped with a text taken back, what
// goes on when the closing text differs, and what stays over is decided in
// one place for both speaking surfaces: useSpokenTurn / useSpeech().follow.
const spoken = useSpokenTurn(() => locale.value, askedKey)

// Watched on the writing itself: every token hands over what it has closed.
// Only for the turn this surface has asked to be spoken — that decision is
// made above, when the turn begins.
watch(
  () => {
    const s = streamingIdx.value
    return s === null ? null : stripSpoken(messages.value[s]?.content ?? '')
  },
  text => {
    const idx = streamingIdx.value
    if (idx === null || text === null || askedKey.value !== idx) return
    spoken.hand(idx, text, false)
  },
  { flush: 'post' },
)

// Nothing here waits for the words to finish arriving any more. The handler
// stays because the component still declares the signal — with no streaming-id
// passed it never fires, and if one is ever passed again this end is honest.
function onRevealDone() { /* no-op */ }
function onVoiceLift(u: VoiceUtterance) { liftToMemo(u.text) }

// Hearing it again is a request, so it is spoken even when the automatic
// reading did not apply — restored history included. Clicking while it is
// still sounding stops it.
function onVoiceReplay(u: VoiceUtterance) {
  if (voiceMode.value === 'text') return
  // A held-back utterance goes first: this tap is the gesture it was missing.
  if (blockedKey.value !== null) { resumeSpeech(); return }
  if (speakingKey.value === u.id || pendingKey.value === u.id) {
    // Said here as well: the voice reports a stopped utterance as over and
    // the words are released through `over` (useSpeech().follow), but a
    // microtask later. Being asked for is over the moment it is stopped, on
    // this pass, and the rest of that turn's words stand.
    stopSpeech()
    askedKey.value = null
    return
  }
  if (u.text) void speakAloud(u.text, locale.value, u.id)
}

// ---------- Memos: lift an utterance out to keep it ----------

interface MemoCard { id: string; text: string; title: string; x: number; y: number; w: number; h: number; collapsed: boolean; z: number; source: 'resona' | 'brought' | 'mine' }
const memoCards = ref<MemoCard[]>([])

// ---------- Anchors: what the room worked out ----------
//
// The produced media were once the only entities on the board, and a
// strategy the group kept, a note Resona wrote and a passage she opened left no
// trace. A small square card each — a name on the front, an excerpt on the back
// (services/resona_entities.py decides what the excerpt is, per kind).

interface EntityCard {
  id: string
  /** The entity's own identity, from the server: one card per thing, however
   *  often a turn touches it and however often the turn announces it. */
  key: string
  kind: string
  name: string
  detail: string
  facts: string[]
}

const entityCards = shallowRef<EntityCard[]>([])
const ENTITY_NODE = 150

function spawnEntity(e: {
  kind?: string; key?: string; name?: string; detail?: string; facts?: string[]
} | null | undefined) {
  if (!e || !e.key || !e.name) return
  if (entityCards.value.some(c => c.key === e.key)) return
  const card: EntityCard = {
    id: `entity-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    key: e.key,
    kind: e.kind || '',
    name: e.name,
    detail: e.detail || '',
    facts: Array.isArray(e.facts) ? e.facts : [],
  }
  placeNode(card.id, ENTITY_NODE, ENTITY_NODE)
  entityCards.value = [...entityCards.value, card]
}

function removeEntity(id: string) {
  entityCards.value = entityCards.value.filter(c => c.id !== id)
  dropNode(id)
}
const memoLayerRef = ref<HTMLElement | null>(null)
let memoSeq = 0
let memoZ = 1
const MEMO_MIN_W = 140, MEMO_MIN_H = 72, MEMO_MAX_W = 680, MEMO_MAX_H = 560

function memoTitle(text: string): string {
  const clean = text.replace(/\s+/g, ' ').trim()
  if (clean.length <= 46) return clean
  const cut = clean.slice(0, 46)
  const lastSpace = cut.lastIndexOf(' ')
  return (lastSpace > 20 ? cut.slice(0, lastSpace) : cut).trimEnd() + '…'
}
function liftToMemo(content: string) {
  const text = stripPlans(content)
  if (!text) return
  const n = memoSeq++
  const step = (n % 6) * 26
  memoCards.value = [
    ...memoCards.value,
    { id: 'memo-' + n, text, title: memoTitle(text), x: 90 + step, y: 96 + step, w: 300, h: 190, collapsed: false, z: ++memoZ, source: 'resona' as const },
  ].slice(-16)
}
/* A note the room writes itself. Formerly the plus offered `text` and
   focused the open line, which carries the caret anyway — the way did nothing
   that was not already happening. What it opens now is a card on the
   surface, lying next to what was worked on, and it travels with the next turn
   like every other text on this board (buildBroughtItems). */
function onNoteInput(m: MemoCard, e: Event) {
  m.text = (e.target as HTMLTextAreaElement).value
  m.title = memoTitle(m.text)
}
function dismissMemo(id: string) {
  memoCards.value = memoCards.value.filter(mc => mc.id !== id)
}
function bringMemoFront(m: MemoCard) { m.z = ++memoZ }
function toggleMemoFold(m: MemoCard) { m.collapsed = !m.collapsed }

/**
 * Drag to move; the corner handle resizes; the button in the corner folds.
 *
 * Folding answered to a HOLD until 2026-09-22, which made this the one place
 * on the platform where the gesture changed a thing's state instead of showing
 * what lies behind it. A gesture with two meanings cannot be learnt, so this
 * one gave it up and took a control of its own (composables/useHold.ts).
 */
function onMemoPointerDown(e: PointerEvent, m: MemoCard) {
  if (e.button !== 0) return
  const startX = e.clientX, startY = e.clientY
  const origX = m.x, origY = m.y
  let dragging = false
  const move = (ev: PointerEvent) => {
    const dx = ev.clientX - startX, dy = ev.clientY - startY
    if (!dragging && Math.hypot(dx, dy) > 5) { dragging = true; bringMemoFront(m) }
    if (dragging) {
      const b = memoLayerRef.value
      const maxX = b ? b.clientWidth - 48 : 4000
      const maxY = b ? b.clientHeight - 40 : 4000
      m.x = Math.max(0, Math.min(maxX, origX + dx))
      m.y = Math.max(0, Math.min(maxY, origY + dy))
    }
  }
  const up = () => cleanup()
  function cleanup() {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', up)
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', up)
}
function onMemoResizeDown(e: PointerEvent, m: MemoCard) {
  e.stopPropagation(); e.preventDefault()
  const startX = e.clientX, startY = e.clientY
  const origW = m.w, origH = m.h
  bringMemoFront(m)
  const move = (ev: PointerEvent) => {
    m.w = Math.round(Math.min(MEMO_MAX_W, Math.max(MEMO_MIN_W, origW + (ev.clientX - startX))))
    m.h = Math.round(Math.min(MEMO_MAX_H, Math.max(MEMO_MIN_H, origH + (ev.clientY - startY))))
  }
  const up = () => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', up)
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', up)
}

// ---------- Brought material -> chat perception (grant 2026-07-17) ----------
// Compact directory of what the group placed on the board, sent as
// context.brought_items with every Resona chat call — ids + capped text
// excerpts only, never paths or file contents. The server re-validates
// everything; this builder only selects and shapes. Brought images are
// auto-perceived server-side (a short caption inline), with view_favorite /
// view_upload for the full look.

// Anti-abuse ceiling on the untrusted brought-items payload — NOT a perception
// limit; a real board never approaches it. Kept in sync with the server
// (chat_routes.RESONA_BROUGHT_MAX).
const BROUGHT_ITEMS_MAX = 64
// Mirrors the server cap (chat_routes.RESONA_BROUGHT_EXCERPT_MAX) — keep in sync.
const BROUGHT_EXCERPT_MAX = 200

interface BroughtItem {
  kind: 'favorite' | 'upload' | 'text'
  media_type?: string
  run_id?: string
  upload_id?: string
  excerpt?: string
}

function buildBroughtItems(): BroughtItem[] {
  const items: BroughtItem[] = []
  // Media boxes: only brought material, newest first — generated boxes are
  // excluded by definition.
  const broughtBoxes = mediaBoxes.value.filter(b => b.brought)
  for (let i = broughtBoxes.length - 1; i >= 0; i--) {
    const box = broughtBoxes[i]
    if (!box) continue
    if (box.runId) {
      items.push({ kind: 'favorite', media_type: box.mediaType, run_id: box.runId })
      continue
    }
    // OS-file drop: the upload_id only ever comes from the served-URL shape —
    // a data-URL (upload still in flight) or a missing URL skips the item.
    const uploadId = box.outputUrl?.match(/\/api\/media\/uploads\/([^/?#]+)$/)?.[1]
    if (uploadId) items.push({ kind: 'upload', media_type: box.mediaType, upload_id: uploadId })
  }
  // The texts lying on the board, newest first: what was brought in, and what
  // the room wrote itself on a note (source 'mine'). Memos carry no timestamp,
  // so cross-list order is media-before-text by design.
  const broughtMemos = memoCards.value.filter(mc => mc.source === 'brought' || mc.source === 'mine')
  for (let i = broughtMemos.length - 1; i >= 0; i--) {
    const excerpt = (broughtMemos[i]?.text ?? '').trim().replace(/\s+/g, ' ')
    if (excerpt) items.push({ kind: 'text', excerpt: excerpt.slice(0, BROUGHT_EXCERPT_MAX) })
  }
  return items.slice(0, BROUGHT_ITEMS_MAX)
}

// ---------- Chat logic ----------

/**
 * One turn, read while it is written.
 *
 * `onToken` is handed each piece as it lands, `onWithdraw` the draft the turn
 * took back on its own evidence duty. The whole payload — media intents,
 * graphs, compositions — comes back at the end exactly as it always did, so
 * everything after this call stayed as it was.
 */
async function callChat(
  message: string,
  history: Array<{ role: string; content: string }>,
  imagePath: string | null | undefined,
  onToken: (text: string) => void,
  onWithdraw: (draft: string) => void,
): Promise<any> {
  const cappedHistory = history.slice(-JOURNAL_HISTORY_CAP)
  const broughtItems = buildBroughtItems()
  const body = {
      message,
      history: cappedHistory,
      ...(imagePath ? { image_path: imagePath } : {}),
      context: {
        resona_mode: true,
        language: userPreferences.language,
        device_id: deviceId,
        // Whether this turn will be heard or read. Chosen here, per browser,
        // so the server cannot know it otherwise — and GIVEN VOICE states it
        // as a fact rather than guessing.
        voice_mode: voiceMode.value,
        // Active course as factual context for Resona (P-R). The server
        // is authoritative: for participants it ignores this and uses the
        // session-pinned course; for educators it validates leadership.
        ...(labAuth.activeCourseId != null ? { course_id: labAuth.activeCourseId } : {}),
        // The journal is named even while paused, and the pause is stated
        // separately: pausing stops the RECORDING (K1), it does not make the
        // conversation unknown. A record that did not know which dialog it was
        // made in could never be dropped with that dialog again.
        ...(journalId.value ? { journal_id: journalId.value } : {}),
        ...(journalPaused.value ? { journal_paused: true } : {}),
        // Perception grant 2026-07-17: compact directory of brought material
        // (ids + capped text excerpts only — never paths). Server re-validates.
        ...(broughtItems.length ? { brought_items: broughtItems } : {}),
      },
  }
  let done: any = null
  for await (const ev of sseEvents<any>(`${apiBase()}/api/chat/stream`, body)) {
    if (ev.type === 'token') onToken(ev.text || '')
    else if (ev.type === 'discard') onToken('\u0000')  // see applyToken: the round was a tool call
    else if (ev.type === 'withdraw') onWithdraw(ev.text || '')
    // An apparatus reaches the board the moment it exists, ahead of the
    // sentence Resona writes about it. What follows can break; this cannot be
    // taken back by that.
    else if (ev.type === 'graph') { if (ev.graph) spawnGraphRun(ev.graph) }
    // An anchor for something the turn is finished with, sent when the tool
    // returns — for the same reason the apparatus goes early.
    else if (ev.type === 'entity') { spawnEntity(ev.entity) }
    else if (ev.type === 'done') done = ev
    else if (ev.type === 'error') {
      // A failed turn still hands over what it managed to build. That work is
      // finished and paid for, and losing it means having it built again.
      for (const m of ev.generated_media || []) spawnGeneration(m)
      for (const g of ev.generated_graphs || []) spawnGraphRun(g)
      for (const c of ev.generated_compositions || []) addComposition(c)
      for (const w of ev.worked_entities || []) spawnEntity(w)
      throw new Error(ev.details || ev.error || 'chat stream error')
    }
  }
  if (!done) throw new Error('the reply stream ended without a reply')
  return done
}

async function sendMessage() {
  const text = userInput.value.trim()
  const imagePath = attachedImagePath.value
  // A picture still being judged is not a picture this turn may carry. The
  // camera closes at the shutter and the check runs on afterwards, so without
  // this the turn could go with the attachment missing or unjudged.
  if ((!text && !imagePath) || isLoading.value || isUploading.value) return
  // Speaking to her is the gesture that lets her answer be heard: the reply
  // sounds seconds from now, far outside this click, and without this the
  // browser refuses it.
  if (voiceMode.value !== 'text') primeSpeech()

  // The page's address is what stands at the door: it says what this surface is
  // before anything has happened on it. The moment somebody writes, it has been
  // read and the surface is in use — it goes, instead of standing across the
  // ground the exchange stands on.
  platformVoice.value?.clear()

  messages.value.push({ role: 'user', content: text || (imagePath ? '🖼️' : '') })
  userInput.value = ''
  removeAttachment()
  isLoading.value = true
  if (!journalId.value && !journalPaused.value) await ensureJournal()

  // The line that will carry the reply is put up EMPTY and grows: what the
  // model writes is read in the room while it is being written, instead of the
  // group waiting for a block they read slower than it arrives.
  messages.value.push({ role: 'assistant', content: '' })
  const replyIdx = messages.value.length - 1
  streamingIdx.value = replyIdx
  // What the current round has written. A round that turns out to be a tool
  // call takes its own preamble back (the NUL marker above), and the standing
  // text falls back to what the rounds before it had already said.
  let settled = ''
  let round = ''
  const applyToken = (piece: string) => {
    const line = messages.value[replyIdx]
    if (!line) return
    if (piece === '\u0000') round = ''
    else round += piece
    line.content = settled + round
  }

  try {
    const history = messages.value
      .slice(0, -2)
      .filter(m => m.role === 'user' || m.content.trim())
      .map(m => ({ role: m.role, content: m.content }))
    const data = await callChat(text, history, imagePath, applyToken, (draft) => {
      const line = messages.value[replyIdx]
      if (!line) return
      // Struck through and left standing; the checked version starts fresh
      // underneath it.
      line.withdrawn = [...(line.withdrawn || []), draft]
      settled = ''
      round = ''
      line.content = ''
    })
    let newPlanIds: string[] = []
    const line = messages.value[replyIdx]!
    if (data?.reply) {
      // The stream is a reading pace; what the turn actually SAID is what the
      // closing payload carries — it has been through the delivery filters the
      // pieces never saw.
      line.content = data.reply
      newPlanIds = extractPlans(data.reply)
      extractAction(data.reply)
    } else {
      note(line, t('resona.noResponse'))
    }
    // The reply stream was cut and the turn shipped what it had. Said the same
    // way a lost connection is said — under what was already read, in the
    // room's language — so that half a sentence goes unread as a whole answer.
    if (data?.broke_off) {
      note(line, t('resona.replyBrokeOff'))
    }
    for (const m of data?.generated_media || []) spawnGeneration(m)
    for (const g of data?.generated_graphs || []) spawnGraphRun(g)
    for (const c of data?.generated_compositions || []) addComposition(c)
    for (const w of data?.worked_entities || []) spawnEntity(w)
    // Thread the reply to the object it produced (Faden anchor). Plans count:
    // a reply that lays a plan on the board speaks AT that plan.
    const produced = (data?.generated_media?.length || 0) + (data?.generated_graphs?.length || 0) + (data?.generated_compositions?.length || 0) + newPlanIds.length
    if (replyIdx >= 0 && produced > 0) {
      // Brought material is never hers to speak at (governance).
      const gen = mediaBoxes.value.filter(b => !b.brought)
      const lm = gen[gen.length - 1]
      const lg = graphBoxes.value[graphBoxes.value.length - 1]
      const lc = compositionBoxes.value[compositionBoxes.value.length - 1]
      const boxId = lm?.id ?? lg?.id ?? lc?.id ?? newPlanIds[newPlanIds.length - 1]
      if (boxId != null) lastAnchor.value = { msgIdx: replyIdx, boxId: String(boxId) }
    } else if (replyIdx >= 0 && data?.reply) {
      // No new object — but if she names a plan already on the board, her words
      // stand at that plan (longest title match; short titles are too ambiguous).
      const spoken = data.reply.toLowerCase()
      let hit: string | null = null
      let hitLen = 0
      for (const pc of planCards.value) {
        const ti = (pc.title || '').trim().toLowerCase()
        if (ti.length >= 6 && ti.length > hitLen && spoken.includes(ti)) { hit = pc.id; hitLen = ti.length }
      }
      if (hit) lastAnchor.value = { msgIdx: replyIdx, boxId: hit }
    }
  } catch (e) {
    // What stands on the board is for the people in the room, and the name of a
    // JavaScript exception is not something anyone there can do anything with.
    // The technical detail is not lost — it goes where it is of use, with the
    // stack that comes with it.
    const line = messages.value[replyIdx]
    // Whatever had already been read stays; the trouble is said under it.
    note(line, t('resona.connectionError'))
    console.error('[RESONA] callChat failed:', e)
  } finally {
    streamingIdx.value = null
    isLoading.value = false
  }
}
// Everything the surface carries, written back a moment after it settles. It
// stands at the FOOT of this block on purpose: the sources it names are
// declared further down, and a watch is evaluated where it is written.
watch(
  [mediaBoxes, compositionBoxes, graphBoxes, entityCards, memoCards, planCards, geom, pan, zoom],
  scheduleBoardSave,
  { deep: true },
)

</script>

<style scoped>
.resona-page {
  position: relative;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  padding-bottom: var(--footer-collapsed-height, 36px);
  background: var(--bg-base);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ---------- Workshop board (zoomable canvas; x2x-flow is the template) ---------- */
.canvas {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: var(--bg-base);
  cursor: grab;
  touch-action: none;
}
.canvas:active { cursor: grabbing; }
.world { position: absolute; left: 0; top: 0; transform-origin: 0 0; }

/* Placement only. The box itself — background, border, radius, the bar with
   the grip, the corner that sizes it — is FlowCard's, the same card x2x-flow
   throws its output into. Stating any of it a second time here is exactly what
   this change removed: no parallel structures
   (docs/ELEMENT_STRUCTURE_REGISTRY.md). */
.board-node {
  position: absolute;
  box-sizing: border-box;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
}
.board-node.selected {
  border-color: rgba(255, 179, 0, 0.5);
  box-shadow: 0 0 0 1px rgba(255, 179, 0, 0.35), 0 6px 20px rgba(0, 0, 0, 0.5);
}

/* How Resona is present: on the edge, legible when looked for, otherwise
   almost not there. Same z-band as the view tools. */
.voice-mode-switch {
  position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
  z-index: 55; display: flex; flex-direction: column; gap: 4px;
  opacity: 0.32; transition: opacity 0.3s ease;
}
.voice-mode-switch:hover { opacity: 1; }
.voice-mode-switch button {
  width: 26px; height: 26px; padding: 0; border-radius: 7px;
  background: transparent; border: 1px solid transparent;
  color: rgba(255, 255, 255, 0.55); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.voice-mode-switch button svg {
  width: 16px; height: 16px;
  fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round;
}
.voice-mode-switch button:hover { color: #ffb300; }
.voice-mode-switch button.on {
  color: #ffb300;
  border-color: rgba(255, 179, 0, 0.32);
  background: rgb(var(--surface-1-rgb) / 0.7);
}

.view-tools { position: absolute; right: 12px; bottom: 12px; z-index: 55; display: flex; gap: 6px; } /* above ambient voice band (z:50); below memo layer (z:60) */
.view-tools button {
  min-width: 30px; height: 30px; padding: 0 8px; border-radius: 8px;
  background: rgb(var(--surface-1-rgb) / 0.85); color: #e8e8e8;
  border: 1px solid rgba(255, 255, 255, 0.12);
  font-size: 0.9rem; line-height: 1; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.view-tools button:hover { border-color: rgba(255, 179, 0, 0.45); color: #ffb300; }

/* The ambient voice + its thread float over the board in screen space, so the
   thread's getBoundingClientRect anchors stay true under pan/zoom.
   pointer-events pass through to the board; the input re-enables them. */
/* INTERIM until the footer gallery becomes a real layout row platform-wide:
   the page reserves the strip via padding, but an absolute inset:0 layer
   ignores parent padding, so this overlay must consume the token itself —
   otherwise the composer sits under the Favoriten bar. DELETE once the footer
   is a layout row. */
.voice-overlay { position: absolute; inset: 0; bottom: var(--footer-collapsed-height, 36px); z-index: 50; pointer-events: none; }
.speak-col { pointer-events: auto; }

.memo-layer { position: absolute; inset: 0; pointer-events: none; z-index: 60; }
.memo-card {
  position: absolute; pointer-events: auto; box-sizing: border-box;
  display: flex; flex-direction: column;
  background: var(--surface-1); border: 1px solid rgba(255, 179, 0, 0.22); border-radius: 10px;
  padding: 0.85rem 1rem 0.7rem; user-select: none;
  cursor: grab; touch-action: none; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
}
.memo-card:active { cursor: grabbing; }
.memo-text {
  margin: 0; flex: 1 1 auto; min-height: 0; overflow-y: auto;
  font-family: var(--font-sans);
  font-size: 0.95rem; line-height: 1.5; color: #e6ddcc; scrollbar-width: thin;
}
/* The note the room writes: the memo's own paper, with nothing drawn around
   the writing. */
.memo-write {
  border: 0; background: transparent; resize: none; padding: 0;
  width: 100%; user-select: text; cursor: text;
  font-family: inherit; font-size: inherit; line-height: inherit; color: inherit;
  caret-color: rgba(255, 179, 0, 0.9);
}
.memo-write:focus { outline: none; }
.memo-attr {
  flex: 0 0 auto; margin-top: 0.5rem;
  font-size: 0.7rem; letter-spacing: 0.04em; color: rgba(255, 255, 255, 0.3);
}
.memo-card.collapsed {
  /* Wide enough for the two buttons in the corner: a memo written and not yet
     named folds to an empty title, and the card would shrink out from under
     the one button that opens it again. */
  flex-direction: row; align-items: center; max-width: 22rem; min-width: 7rem;
  padding: 0.4rem 0.9rem; background: var(--surface-1); border-color: rgba(255, 179, 0, 0.42);
}
.memo-title {
  font-family: var(--font-sans); font-size: 0.9rem; line-height: 1.3;
  color: #f0e4c8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.memo-x {
  position: absolute; top: -8px; right: -8px; z-index: 2;
  width: 20px; height: 20px; border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: var(--surface-2); color: rgba(255, 255, 255, 0.5);
  font-size: 0.75rem; line-height: 1; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.memo-x:hover { background: rgba(200, 80, 80, 0.4); color: #fff; }
/* Folding and discarding stand side by side in the same corner, the same
   drawing, so that the one that only folds is plainly not the one that removes. */
.memo-fold {
  position: absolute; top: -8px; right: 16px; z-index: 2;
  width: 20px; height: 20px; border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: var(--surface-2); color: rgba(255, 255, 255, 0.5);
  font-size: 0.75rem; line-height: 1; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.memo-fold:hover { background: rgba(255, 179, 0, 0.35); color: #fff; }
.memo-resize {
  position: absolute; right: 0; bottom: 0; width: 16px; height: 16px;
  cursor: nwse-resize; touch-action: none;
  background: linear-gradient(135deg, transparent 50%, rgba(255, 179, 0, 0.5) 50%);
}
.memo-resize:hover { background: linear-gradient(135deg, transparent 50%, rgba(255, 179, 0, 0.9) 50%); }


.plan-card-header { display: flex; align-items: baseline; justify-content: space-between; gap: 0.6rem; margin-bottom: 0.4rem; }
.plan-card-title { font-weight: 700; font-size: 1.02em; }
.plan-copy-btn {
  flex-shrink: 0; padding: 0.2rem 0.6rem; background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px;
  color: rgba(230, 230, 230, 0.6); font-size: 0.7rem; cursor: pointer; transition: all 0.15s ease;
}
.plan-copy-btn:hover { border-color: rgba(255, 255, 255, 0.35); color: rgba(230, 230, 230, 0.9); }
.plan-purpose, .plan-extra { opacity: 0.85; font-size: 0.92em; margin: 0.2rem 0 0.4rem; }
.plan-steps { margin: 0.3rem 0; padding-left: 1.4rem; }
.plan-steps li { margin-bottom: 0.4rem; line-height: 1.5; }

/* ---------- Speak row ---------- */
/* The open line. It carries the setting of the human's line in the exchange,
   because it IS that line one moment earlier: white, sans, flush left, and no
   furniture around it. Nothing stands in it before it is written in, and
   nothing stands beside it -- the Enter key is the entry. */
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

/* ---------- The surface's free fixtures ---------- */
/* They lie ON the surface at its foot, clear of the footer gallery, and belong
   to no bar. Their centres are level with each other, which is why the smaller
   one is lifted by half the difference of the two steps. */
.fixture { position: fixed; z-index: 62; pointer-events: auto; }
.fixture-plus {
  left: clamp(1rem, 4vw, 3rem);
  bottom: calc(var(--flow-footer-clear, 54px) + 0.4rem);
}
/* The other corner, and lifted clear of the zoom cluster that sits in it: the
   two fixtures do different things and the arc of the plus needs its side of
   the surface free. */
.fixture-gear {
  right: clamp(0.75rem, 2vw, 1.5rem);
  bottom: calc(var(--flow-footer-clear, 54px) + 2.4rem);
}
.hidden-file-input { display: none; }

/* ---------- Journal notice ---------- */
/* Inside the gear now: a sentence, not a bar. */
.journal-notice-row { font-size: 0.72rem; line-height: 1.45; }
.journal-notice-text { color: rgba(230, 230, 230, 0.32); }
.journal-toggle-btn {
  padding: 0.15rem 0.55rem; background: transparent; border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px; color: rgba(230, 230, 230, 0.5); font-size: 0.66rem; cursor: pointer;
}
.journal-toggle-btn:hover { color: #e6e6e6; }
.journal-delete-btn { color: rgba(230, 120, 120, 0.5); }
.journal-delete-btn:hover { color: #e06b6b; }
/* ---------- Attachment ---------- */
.attachment-row { flex: 0 0 auto; padding: 0.5rem clamp(1rem, 6vw, 5rem) 0; }
.attachment-thumb {
  position: relative; width: 64px; height: 64px; border-radius: 8px;
  overflow: hidden; border: 1px solid rgba(255, 255, 255, 0.15);
}
.attachment-thumb img { width: 100%; height: 100%; object-fit: cover; }
.attachment-remove {
  position: absolute; top: 2px; right: 2px; width: 18px; height: 18px; border: none;
  border-radius: 50%; background: rgba(0, 0, 0, 0.7); color: #fff; font-size: 0.9rem;
  line-height: 1; cursor: pointer; display: flex; align-items: center; justify-content: center;
}

/* ---------- Camera modal ---------- */

/* ---------- Camera modal ---------- */
.modal-fade-enter-active, .modal-fade-leave-active { transition: opacity 0.2s ease; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
/* ---------- The open line, inside the exchange ---------- */
.speak-col { display: flex; flex-direction: column; gap: 0.3rem; width: 100%; min-width: 0; }
.speak-col .attachment-row { padding: 0.2rem 0 0; }

.plan-object {
  height: 100%;
  background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 179, 0, 0.25);
  border-radius: 10px; padding: 0.8rem 1rem;
  font-family: var(--font-sans, system-ui); font-size: 0.9rem; color: #e6e6e6;
}
.plan-actions { display: flex; align-items: center; gap: 0.4rem; flex-shrink: 0; }
.plan-x { padding: 0 0.35rem; background: transparent; border: none; color: rgba(230, 230, 230, 0.5); font-size: 1rem; line-height: 1; cursor: pointer; }
.plan-x:hover { color: #fff; }
</style>
