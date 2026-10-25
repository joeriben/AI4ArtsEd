<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import FlowCard from '@/components/FlowCard.vue'
import MediaCardFront from '@/components/MediaCardFront.vue'
import MediaCardBack from '@/components/MediaCardBack.vue'
import MediaFullscreen from '@/components/MediaFullscreen.vue'
import { drawerBack, getMediaType, getOutputUrl } from '@/components/canvas/drawerBack'
import { useDeviceId } from '@/composables/useDeviceId'
import { downloadMedia, fileDateParts, mediaExtension, mediaFileName } from '@/lib/downloadMedia'
import { handOverImage } from '@/lib/handOverImage'
import { printMedia } from '@/lib/printMedia'
import { FAVORITE_DT } from '@/composables/useMaterialIntake'
import { isKeepableMedia, useFavoritesStore } from '@/stores/favorites'

const { t } = useI18n()
const router = useRouter()
const deviceId = useDeviceId()
const favoritesStore = useFavoritesStore()

/**
 * One box on the surface. Deliberately says nothing about where it came from:
 * this drawer was typed on Canvas' collector items (`nodeId`/`nodeType`/
 * `highlight-node`), which is why no other surface could use it without either
 * pretending to be a canvas or building a second drawer. A run of an instrument
 * has an identity and a name, and that is all this needs.
 */
export interface DrawerItem {
  /** Stable identity — what `highlightedId` matches and `select` reports. */
  id: string
  /**
   * Where a favourite made from this card says it came from, where the card
   * knows better than the surface: one component can serve several addresses
   * (the crossmodal lab holds takes from two of its tabs in one strip).
   */
  sourceView?: string
  /** The head of the comparison key in the card's bar. */
  label: string
  /** The second half of that key, dimmer. Canvas puts the node's short id there. */
  sub?: string
  /** Facts of the run, worded by the page. They stand on the card's BACK. */
  meta?: string[]
  /** `{ url, media_type }`, a plain string, or `{ text }`. */
  output: unknown
  error?: string | null
  /**
   * What the card's back side is made of. A page that knows the prompt gets a
   * two-faced card; one that does not gets a plain one, with no hold gesture on
   * it at all — see FlowCard. Nothing here is invented for the drawer: it is
   * what MediaCardBack renders on every other surface.
   */
  prompt?: string
  configId?: string
  createdAt?: number
  modelMeta?: Record<string, any> | null
  /** The run this came out of. Without it a piece cannot be kept. */
  runId?: string
}

/** Position and size of one card, in the strip's own pixels. */
interface BoxState {
  x: number
  y: number
  w: number
  h: number
}

const props = withDefaults(defineProps<{
  items: DrawerItem[]
  isCollapsed: boolean
  highlightedId?: string | null
  /** The strip's own name. Defaults to the one Canvas gave it. */
  title?: string
  emptyText?: string
  /** Open height in px. Canvas' 520 is half a screen; an instrument wants less. */
  defaultHeight?: number
  /** The size a card gets when it first appears. */
  boxWidth?: number
  boxHeight?: number
  /** Which surface a kept piece is recorded as coming from. */
  sourceView?: string
  /**
   * The words a saved piece's file name starts with. Canvas gives the name of
   * the workflow the run was started from, so a workflow and what it renders
   * lie together in a folder (lib/canvasFile.ts). Without it a piece is saved
   * as `output_<id>`, as it always was.
   */
  fileStem?: string
  /**
   * Whether the comparison key in a card's bar is a CONTROL. It is, where the
   * surface answers `select` by putting that run back on itself; where it does
   * not, the key is the run's name and nothing more. A key that looks clickable
   * and does nothing costs a reader more than a key that never offered.
   */
  selectable?: boolean
  /**
   * Asked before a run is kept, for a surface whose picture IS a reading of it.
   * Attention Cartography sets the plate its run is shown by from the map the
   * eye is on, and that has to be written before the favourite points at it.
   * Anything thrown here leaves the run unkept, and the star stays dark — a
   * favourite showing a reading other than the one on screen would be worse
   * than none.
   */
  beforeFavorite?: (item: DrawerItem) => Promise<void>
}>(), {
  highlightedId: null,
  title: '',
  emptyText: '',
  defaultHeight: 520,
  boxWidth: 360,
  boxHeight: 400,
  sourceView: 'canvas',
  fileStem: '',
  selectable: false,
  beforeFavorite: undefined,
})

const emit = defineEmits<{
  'toggle-collapse': []
  'select': [id: string]
  /** The × on a card. By POSITION, because two items may carry one id. */
  'remove': [index: number]
}>()

/**
 * The card standing large, or nothing. The ITEM, not its file: the layer shows
 * the card's back beside the picture, and what is pressed on it goes to the
 * same handlers as on the card (one click, one view, on every surface).
 */
const fullscreenItem = ref<DrawerItem | null>(null)
/**
 * The token of the card standing large: its place in the strip, which a saved
 * file is named by. Held by token, because the list is rebuilt while a run
 * streams in and two cards may carry one id (see `tokens` below).
 */
const fullscreenToken = ref<string | null>(null)

function openLarge(item: DrawerItem, index: number) {
  fullscreenItem.value = item
  fullscreenToken.value = tokens.value[index] ?? null
}

/** The place of the card standing large, counted from 1; 0 once it has left. */
function largePosition(): number {
  return fullscreenToken.value ? tokens.value.indexOf(fullscreenToken.value) + 1 : 0
}

/**
 * Show one run of the strip large, asked by the page: a surface whose main
 * picture IS the run standing in its strip (Encoder Fusion) opens the same view
 * the card would, back and all, instead of a second one without it. Answers
 * whether it could — a run that is not in the strip, or has no picture, is the
 * page's to show as before.
 */
function show(id: string): boolean {
  const index = props.items.findIndex(it => it.id === id || it.runId === id)
  const item = props.items[index]
  if (!item || item.error || !getOutputUrl(item)) return false
  openLarge(item, index)
  return true
}
defineExpose({ show })

//: Runs whose star is still waiting for its answer.
const pending = ref(new Set<string>())

/**
 * Geometry per card, and the turned/not-turned state inside FlowCard, hang off
 * a token rather than off the position or the id. The id cannot carry them: a
 * canvas node with two incoming edges executes twice and lands in the list
 * twice (services/canvas_executor.py). The position cannot either, now that a
 * card can be taken away — everything behind the gap would inherit the geometry
 * and the turned state of its neighbour.
 */
let tokenSeq = 0
const tokens = ref<string[]>([])
/** Which card each token was minted for, so a token can follow its card. */
const tokenOwners = ref<string[]>([])
const boxStates = ref<Map<string, BoxState>>(new Map())
const BOX_GAP = 16

/**
 * Tokens are matched to the cards BY IDENTITY, once per change of the list.
 *
 * Counting them was not enough. A strip whose contents are exchanged for
 * another set of the same size — the crossmodal lab does that when the reader
 * steps to another of its tabs — kept every token in place, and the incoming
 * cards inherited the positions and the turned sides of the ones that had
 * stood there. Matching by id also makes the trimming dance around the × and
 * around a host that replaces its list wholesale unnecessary: a card that is
 * still in the list keeps its token wherever it now stands, and a token whose
 * card has left takes its geometry with it.
 *
 * Where two cards carry one id (a canvas node with two incoming edges executes
 * twice, services/canvas_executor.py) the first unclaimed token wins, which is
 * the same card as before for as long as the list order holds.
 */
watch(() => props.items.map(item => item.id), (now) => {
  const nextTokens: (string | undefined)[] = []
  const claimed = new Set<number>()
  for (const id of now) {
    let at = -1
    for (let i = 0; i < tokenOwners.value.length; i++) {
      if (!claimed.has(i) && tokenOwners.value[i] === id) { at = i; break }
    }
    const held = at >= 0 ? tokens.value[at] : undefined
    if (held) claimed.add(at)
    nextTokens.push(held)
  }

  // What has LEFT goes first, before a single new card is placed. A surface can
  // exchange its whole list at once — the crossmodal lab shows one tab's takes
  // at a time — and placing the new cards while the old ones still hold their
  // ground would put them beyond the right edge of an empty strip: the badge
  // says two, the surface is blank, and every step to the next tab pushes them
  // further out.
  const kept = new Set(nextTokens.filter(Boolean))
  for (const tk of tokens.value) if (!kept.has(tk)) boxStates.value.delete(tk)

  for (let i = 0; i < nextTokens.length; i++) {
    if (nextTokens[i]) continue
    const tk = `b${tokenSeq++}`
    // Right of the rightmost card that REMAINS, so a new run never lands on top
    // of one that is still standing.
    let x = BOX_GAP
    for (const s of boxStates.value.values()) x = Math.max(x, s.x + s.w + BOX_GAP)
    boxStates.value.set(tk, { x, y: BOX_GAP, w: props.boxWidth, h: props.boxHeight })
    nextTokens[i] = tk
  }
  tokens.value = nextTokens as string[]
  tokenOwners.value = [...now]
}, { immediate: true })

function getBoxStyle(idx: number) {
  const tk = tokens.value[idx]
  const s = tk ? boxStates.value.get(tk) : undefined
  if (!s) return {}
  return { left: `${s.x}px`, top: `${s.y}px`, width: `${s.w}px`, height: `${s.h}px` }
}

/**
 * The list belongs to the page, so the card goes only if the page took it — and
 * the watcher above reconciles whatever the page did, by identity. A host that
 * keeps the item leaves everything as it stands.
 */
function removeAt(idx: number) {
  if (!tokens.value[idx]) return
  emit('remove', idx)
}

/**
 * The card last pressed lies on top. Without this the order is the order they
 * were made in, and a card pulled over another one buried it: the only surface
 * that still took a press was an 18px bar under someone else's picture, so the
 * covered card could not be moved, sized or closed again.
 */
const topToken = ref<string | null>(null)
function raise(idx: number) {
  topToken.value = tokens.value[idx] ?? null
}

// --- Move and size. The card emits, this decides what the gesture moves; on
//     this surface that is plain strip pixels, with no pan and no zoom. ---

const draggingToken = ref<string | null>(null)
let dragState: { tk: string; offsetX: number; offsetY: number } | null = null
let resizeState: { tk: string; startX: number; startY: number; startW: number; startH: number } | null = null

function startDrag(idx: number, e: PointerEvent) {
  const tk = tokens.value[idx]
  const s = tk ? boxStates.value.get(tk) : undefined
  if (!tk || !s) return
  dragState = { tk, offsetX: e.clientX - s.x, offsetY: e.clientY - s.y }
  draggingToken.value = tk
}

function startBoxResize(idx: number, e: PointerEvent) {
  const tk = tokens.value[idx]
  const s = tk ? boxStates.value.get(tk) : undefined
  if (!tk || !s) return
  resizeState = { tk, startX: e.clientX, startY: e.clientY, startW: s.w, startH: s.h }
}

function onPointerMove(e: PointerEvent) {
  if (dragState) {
    const s = boxStates.value.get(dragState.tk)
    if (!s) return
    s.x = Math.max(0, e.clientX - dragState.offsetX)
    s.y = Math.max(0, e.clientY - dragState.offsetY)
    return
  }
  if (resizeState) {
    const s = boxStates.value.get(resizeState.tk)
    if (!s) return
    s.w = Math.max(200, resizeState.startW + (e.clientX - resizeState.startX))
    s.h = Math.max(160, resizeState.startH + (e.clientY - resizeState.startY))
  }
}

function onPointerUp() {
  dragState = null
  resizeState = null
  draggingToken.value = null
}

onMounted(() => {
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerUp)
})

onUnmounted(() => {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
})

// --- The strip's own height, pulled by its top edge ---

const drawerHeight = ref(props.defaultHeight)
const isResizing = ref(false)
const MIN_HEIGHT = 200
const MAX_HEIGHT_RATIO = 0.7

function startDrawerResize(e: PointerEvent) {
  e.preventDefault()
  isResizing.value = true
  const startY = e.clientY
  const startHeight = drawerHeight.value

  function onMove(ev: PointerEvent) {
    const maxH = window.innerHeight * MAX_HEIGHT_RATIO
    drawerHeight.value = Math.max(MIN_HEIGHT, Math.min(maxH, startHeight + (startY - ev.clientY)))
  }
  function onUp() {
    isResizing.value = false
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

// --- Reading an item (the file, its kind and the record: components/canvas/drawerBack.ts) ---

/**
 * The picture a CARD shows: the stored miniature where the platform has one.
 *
 * A card stands 240 px wide and was drawing the full render into it — measured
 * 2.36 MB for one Attention Cartography run, every card at once, so opening the
 * strip pulled tens of megabytes before the first comparison could be made. The
 * miniature is the same answer the favourites strip has been given since
 * 2026-08-25 (media_routes.get_image_thumbnail, 160 px, built once and cached);
 * this is that answer read on the client for a run's own image URL.
 *
 * Everything that hands the picture ON — the big view, download, forward,
 * print — keeps `getOutputUrl`, the full file.
 *
 * At the size the CARD actually draws, not the plate size the favourites strip
 * asks for. This strip is where two runs are held against each other, and what
 * is compared can be a heat map whose colour edges are the whole finding — a
 * copy blown up to card size would take exactly that away. So the card's width
 * in DEVICE pixels decides: a card on a tablet at three device pixels per CSS
 * pixel needs three times what its style says, and a card dragged past what the
 * server will build a miniature of gets the file itself rather than a
 * magnified copy of a small one.
 */
const RUN_IMAGE = /^(\/api\/media\/image\/[^/?#]+\/\d+)(\?.*)?$/
//: The sizes the server builds (services/thumbnails.THUMBNAIL_SIZES), smallest first.
const THUMB_SIZES = [160, 512]

function getPreviewUrl(item: DrawerItem, idx: number): string | null {
  const url = getOutputUrl(item)
  if (!url || getMediaType(item) !== 'image') return url
  const match = RUN_IMAGE.exec(url)
  if (!match) return url
  const tk = tokens.value[idx]
  const width = (tk ? boxStates.value.get(tk)?.w : 0) || props.boxWidth
  const needed = width * (typeof devicePixelRatio === 'number' ? devicePixelRatio : 1)
  const px = THUMB_SIZES.find(size => size >= needed)
  if (!px) return url
  const query = match[2] ? `${match[2]}&px=${px}` : `?px=${px}`
  return `${match[1]}/thumb${query}`
}

function getTextOutput(item: DrawerItem): string | null {
  if (typeof item.output === 'string') return item.output
  const output = item.output as Record<string, unknown> | null
  if (output && typeof output === 'object' && 'text' in output) return output.text as string
  return null
}

/** Is there a record to turn to? Prompt, config, time or any fact will do. */
function hasBack(item: DrawerItem): boolean {
  return !!(item.prompt || item.configId || item.createdAt || item.meta?.length || item.modelMeta)
}

/**
 * Whether the card turns. Since 2026-08-25 a medium alone is reason enough: the
 * row of things one can do with it stands on that side, so a card with a
 * picture and no record of its run must still be turnable — otherwise keeping
 * and saving it would have no place left.
 */
function showsBack(item: DrawerItem): boolean {
  return hasBack(item) || !!(!item.error && getOutputUrl(item))
}

/** The comparison key in the bar: what tells two runs of the same thing apart. */
function keyText(item: DrawerItem): string {
  return item.sub ? `${item.label} · ${item.sub}` : item.label
}

// --- Actions of the card's front ---

/** `position`: the card's place in the strip, counted from 1; 0 where unknown. */
async function handleDownload(item: DrawerItem, position: number) {
  const url = getOutputUrl(item)
  if (!url) return
  const ext = mediaExtension(getMediaType(item))
  // The stem, the minute the piece was made, its model, and its place in the
  // strip: two generation nodes of one run may share a model.
  const filename = props.fileStem
    ? mediaFileName(
        props.fileStem,
        [...fileDateParts(item.createdAt ?? Date.now()), item.configId, position || null],
        ext,
      )
    : `output_${item.id}.${ext}`
  await downloadMedia(url, filename)
}

function handleForward(item: DrawerItem) {
  const url = getOutputUrl(item)
  if (!url || getMediaType(item) !== 'image') return
  const runIdMatch = url.match(/\/api\/media\/image\/(.+)$/)
  handOverImage(url, runIdMatch ? runIdMatch[1] : null)
  router.push('/x2x-flow')
}

/**
 * A run leaves the strip whole: run id and kind, which is all a receiver needs
 * to ask the server for the rest. Called from the card's FACE - the strip's own
 * gestures sit on the bar (move), the corner (size) and the hold (turn), so the
 * face was free.
 */
function onCarry(e: DragEvent, item: DrawerItem) {
  // A picture inside the card is draggable by itself, whatever the card says.
  // Without this, a card with no run id was still carried away — as a bare
  // image URL that no receiver on this platform reads, with no cursor and no
  // word to say that nothing would come of it.
  if (!item.runId) {
    e.preventDefault()
    return
  }
  // And where there IS a run, the browser has already filled the drag with the
  // picture's URL as text, html and uri-list. Those ride along into anything
  // outside the app and paste a raw link. What travels is the run.
  e.dataTransfer?.clearData()
  e.dataTransfer?.setData(
    FAVORITE_DT,
    JSON.stringify({ run_id: item.runId, media_type: getMediaType(item) })
  )
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy'
}

function handlePrint(item: DrawerItem) {
  printMedia(getOutputUrl(item))
}

/**
 * Keeping a piece. The card's BACK carries the platform's action row (since
 * 2026-08-25), so the star is on it whether or not this surface answers — it is wired here rather
 * than left dead. Without a run id there is nothing to keep, and the store says
 * so by not changing.
 */
async function handleFavorite(item: DrawerItem) {
  if (!item.runId) return
  const type = getMediaType(item)
  // The same list that decides whether the star is DRAWN (MediaActionBar).
  // Two hand-kept lists drifted the moment one of them grew, and the star then
  // stood on a card where pressing it did nothing at all.
  if (!isKeepableMedia(type)) return
  // Keeping a run takes a moment — a surface that shows a reading writes that
  // reading first, and that is a picture going over the wire. Nothing on the
  // card says so, so a second press arrives while the first is still in flight,
  // sees an unlit star, and keeps the run a second time; when both answers come
  // back the second reads the run as kept and takes it away again. The run is
  // held while its own answer is outstanding.
  if (pending.value.has(item.runId)) return
  pending.value.add(item.runId)
  try {
    // The plate first, the favourite second: a surface that shows a reading of
    // its run writes the reading that stands, and only then does the favourite
    // point at it. Where that write fails the run is NOT kept — a star that
    // stays dark says the reading was not kept, while a lit one over the
    // previous reading says something false about what is in the picture.
    if (props.beforeFavorite && !favoritesStore.isFavorited(item.runId)) {
      await props.beforeFavorite(item)
    }
    await favoritesStore.toggleFavorite(
      item.runId,
      type,
      deviceId,
      'anonymous',
      // A surface can serve more than one address - the crossmodal lab holds
      // takes from two of its tabs in one strip. Where a card knows which one it
      // was made at, that is where it came from; the surface's own address is for
      // the cards that do not.
      item.sourceView || props.sourceView
    )
  } catch (err) {
    console.error('[OutputDrawer] The run was not kept:', err)
  } finally {
    pending.value.delete(item.runId)
  }
}
</script>

<template>
  <div
    dir="ltr"
    class="output-drawer"
    :style="isCollapsed ? { height: '40px' } : { height: `${drawerHeight}px` }"
    :class="{ collapsed: isCollapsed }"
  >
    <div v-if="!isCollapsed" class="resize-handle" @pointerdown="startDrawerResize">
      <div class="resize-grip" />
    </div>

    <div class="drawer-header" @click="emit('toggle-collapse')">
      <div class="header-left">
        <span class="header-title">{{ title || t('canvas.outputDrawer.title') }}</span>
        <span v-if="items.length > 0" class="item-count">{{ items.length }}</span>
      </div>
    </div>

    <div v-if="!isCollapsed" class="drawer-content">
      <div v-if="items.length === 0" class="empty-state">
        {{ emptyText || t('canvas.outputDrawer.emptyState') }}
      </div>

      <div v-else class="boxes-area">
        <!-- The platform's card — the one the flow throws its output into and
             Together and Contesting carry. It brings the bar with its grip and
             its ×, the corner, and the turn to its back; this surface only says
             where a card sits and what the gestures move.
             Keyed by the token, not by the item's id: two items may carry one
             id, and a card that is taken away must not hand its geometry and
             its turned state to its neighbour. -->
        <FlowCard
          v-for="(item, idx) in items"
          :key="tokens[idx]"
          class="run-card"
          :class="{
            highlighted: item.id === highlightedId,
            failed: !!item.error,
            dragging: draggingToken === tokens[idx],
            top: topToken === tokens[idx],
          }"
          :style="getBoxStyle(idx)"
          @pointerdown="raise(idx)"
          bar
          closable
          resizable
          scroll
          :close-title="t('canvas.outputDrawer.remove')"
          :resize-title="t('x2xFlow.resize')"
          :hold-title="showsBack(item) ? t('resonaMediaCard.flipToBack') : undefined"
          @grip-down="startDrag(idx, $event)"
          @resize-down="startBoxResize(idx, $event)"
          @close="removeAt(idx)"
        >
          <template #bar>
            <span
              class="run-key"
              :class="{ acts: selectable }"
              :title="keyText(item)"
              @pointerdown="selectable && $event.stopPropagation()"
              @click.stop="selectable && emit('select', item.id)"
            >
              {{ keyText(item) }}
            </span>
          </template>

          <!-- Carrying a run out of the strip: the same payload the favourites
               bar writes, so every place that already takes a favourite takes
               this one - a board lays it down, a field takes the one thing it
               is. Until now the only way out of here was the star, which meant
               keeping a run in order to move it. -->
          <MediaCardFront
            v-if="!item.error && getOutputUrl(item)"
            :draggable="!!item.runId"
            @dragstart="onCarry($event, item)"
            :output-url="getPreviewUrl(item, idx)"
            :media-type="getMediaType(item)"
            :run-id="item.runId ?? null"
            :is-executing="false"
            :progress="0"
            :model-meta="item.modelMeta ?? null"
            :is-favorited="!!item.runId && favoritesStore.isFavorited(item.runId)"
            @image-click="openLarge(item, idx)"
          />
          <div
            v-else-if="!item.error && getTextOutput(item)"
            class="box-text"
            :draggable="!!item.runId"
            @dragstart="onCarry($event, item)"
          >
            {{ getTextOutput(item) }}
          </div>
          <div v-else-if="item.error" class="box-text error-text">{{ item.error }}</div>

          <!-- A back wherever there is something to put on it. A canvas run from
               before the collector carried its prompt still has a config, a seed
               and a time — and those are what tell two of its outputs apart. The
               record is `drawerBack`'s, the same one the enlarged view stands
               beside the picture below. -->
          <template v-if="showsBack(item)" #back="{ flipped }">
            <MediaCardBack
              v-bind="drawerBack(item, !!item.runId && favoritesStore.isFavorited(item.runId))"
              :active="flipped"
              @toggle-favorite="handleFavorite(item)"
              @forward="handleForward(item)"
              @download="handleDownload(item, idx + 1)"
              @print="handlePrint(item)"
            />
          </template>
        </FlowCard>
      </div>
    </div>
  </div>

  <!-- The platform's one fullscreen layer (components/MediaFullscreen.vue), with
       the card's back beside the picture and the card's own handlers behind
       its row. -->
  <MediaFullscreen
    :src="fullscreenItem ? getOutputUrl(fullscreenItem) : null"
    :back="
      fullscreenItem
        ? drawerBack(fullscreenItem, !!fullscreenItem.runId && favoritesStore.isFavorited(fullscreenItem.runId))
        : null
    "
    @close="fullscreenItem = null"
    @toggle-favorite="fullscreenItem && handleFavorite(fullscreenItem)"
    @forward="fullscreenItem && handleForward(fullscreenItem)"
    @download="fullscreenItem && handleDownload(fullscreenItem, largePosition())"
    @print="fullscreenItem && handlePrint(fullscreenItem)"
  />
</template>

<style scoped>
.output-drawer {
  background: var(--bg-base);
  border-top: 1px solid var(--shell-line, var(--surface-4));
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: height 0.2s ease;
  overflow: hidden;
}

.output-drawer.collapsed { height: 40px !important; }

.resize-handle {
  height: 6px;
  cursor: ns-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  touch-action: none;
}
.resize-handle:hover { background: rgba(59, 130, 246, 0.2); }
.resize-grip { width: 40px; height: 2px; background: var(--surface-4); border-radius: 1px; }

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  cursor: pointer;
  flex-shrink: 0;
  user-select: none;
}
.drawer-header:hover { background: rgba(255, 255, 255, 0.03); }
.header-left { display: flex; align-items: center; gap: 0.5rem; }
.header-title {
  font-size: 0.8125rem;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.item-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  background: #3b82f6;
  border-radius: 10px;
  font-size: 0.6875rem;
  font-weight: 700;
  color: white;
}

.drawer-content { flex: 1; min-height: 0; overflow: hidden; }

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #475569;
  font-size: 0.875rem;
}

/* Where the cards stand. Position and size are this surface's business; the
   card itself carries no geometry — see FlowCard. */
.boxes-area { position: relative; width: 100%; height: 100%; overflow: auto; }
.run-card { position: absolute; z-index: 10; }
.run-card.top { z-index: 15; }
.run-card.dragging { z-index: 20; }
.run-card.highlighted { border-color: #3b82f6; box-shadow: 0 0 12px rgba(59, 130, 246, 0.3); }
.run-card.failed { border-color: rgba(239, 68, 68, 0.4); }

/* The comparison key, in the bar the card already has: what tells two runs of
   the same instrument apart. The record — prompt, model, config, seed, time —
   is on the back, where it can be read at length. */
.run-key {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 6px;
  font-family: 'SF Mono', ui-monospace, monospace;
  font-size: 10px;
  font-weight: 400;
  color: #b9b2e0;
  cursor: default;
}
.run-key.acts { cursor: pointer; }
.run-key.acts:hover { color: #e9e6fb; }

.box-text {
  padding: 0.75rem;
  font-size: var(--flow-fs-body);
  color: #e2e8f0;
  line-height: 1.5;
  white-space: pre-wrap;
}
.error-text { color: #ef4444; }
</style>
