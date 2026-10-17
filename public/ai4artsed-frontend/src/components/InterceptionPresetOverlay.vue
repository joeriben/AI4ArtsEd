<template>
  <BubbleRingFrame :visible="visible" @close="emit('close')">
    <!-- Category Bubbles (PropertyBubble reuse) -->
    <PropertyBubble
      v-for="category in categories"
      :key="category"
      data-ring-bubble
      :property="category"
      :color="getCategoryColor(category)"
      :is-selected="selectedCategory === category"
      :x="categoryPositions[category]?.x ?? 50"
      :y="categoryPositions[category]?.y ?? 50"
      :symbol-data="getSymbolData(category)"
      @toggle="handleCategoryToggle"
      @dblclick="takeWholeCategory(category)"
      @update-position="handleUpdatePosition"
      @mouseenter="onCategoryHover(category)"
      @mouseleave="onClusterLeave"
    />

    <!-- Config Bubbles around selected category -->
    <transition-group name="config-fade" v-if="selectedCategory && visibleConfigs.length > 0">
      <div
        v-for="(config, index) in visibleConfigs"
        :key="config.id"
        class="config-bubble"
        data-ring-bubble
        :style="getConfigStyle(config, index)"
        @click="onTileClick(config)"
        @pointerdown="onTilePress($event, config)"
        @pointerup="onTileRelease($event)"
        @pointerleave="onTileRelease($event)"
        @pointercancel="onTileRelease($event)"
        @mouseenter="cancelClose"
        @mouseleave="onClusterLeave"
      >
        <div class="config-content">
          <div
            v-if="config.keptItem"
            class="kept-face"
            :style="{ background: keptColor(config.keptItem.id, kept.items) }"
          ></div>
          <div
            v-else
            class="preview-image"
            :class="{ 'is-here': hasArrived(previewOf(config)) }"
            :style="{ backgroundImage: `url(${previewOf(config)})` }"
          ></div>
          <CircleTitle :text="getConfigName(config)" :revealed="heldId === config.id" />
        </div>
        <RemoveBadge
          v-if="config.keptItem"
          :title="$t('presetOverlay.mineDrop')"
          @remove="dropKept(config.keptItem)"
        />
      </div>
    </transition-group>
  </BubbleRingFrame>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BubbleRingFrame from './BubbleRingFrame.vue'
import PropertyBubble from './PropertyBubble.vue'
import RemoveBadge from './RemoveBadge.vue'
import CircleTitle from './CircleTitle.vue'
import { useHold } from '@/composables/useHold'
import { useConfigSelectionStore, type SymbolData } from '@/stores/configSelection'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { getConfigContext } from '@/services/api'
import { localized } from '@/i18n'
import {
  useKeptPerspectivesStore, readPromptText, keptPreviewId, keptColor,
  type KeptPerspective,
} from '@/stores/keptPerspectives'
import { useI18n } from 'vue-i18n'
import { usePerspectiveCatalog } from '@/composables/usePerspectiveCatalog'
import { ringPositions, bloomDistancePct, bloomPosition } from '@/composables/useBubbleRing'

interface Props {
  visible: boolean
  /**
   * The surface behind this takes ONE perspective. Taking a whole category then
   * has nothing to hand it: every one of them is loaded, each replaces the one
   * before it, and the choice ends on whichever came last. So the gesture is
   * not offered there. Where the pick rewrites a field, the category also
   * started one interception per perspective on the same text at once, and
   * which answer kept the field depended on the surface and on the order of
   * arrival.
   */
  single?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
  'preset-selected': [payload: {
    configId: string
    context: string
    configName: string
    previewId?: string
    promptId?: number
  }]
}>()

// Stores
const configStore = useConfigSelectionStore()
const userPreferences = useUserPreferencesStore()
const kept = useKeptPerspectivesStore()
const { t } = useI18n()

/**
 * Where a person's own saved perspectives hang: in the ring of the centre
 * bubble (P3). They are written, and the centre is the pencil — so they stand
 * beside the two given perspectives that are also written here, rather than in
 * a category of their own.
 */
const CENTRE = 'freestyle'

/**
 * WHICH configs are perspectives, and how a course narrows them: the platform's
 * one derivation (`composables/usePerspectiveCatalog.ts`). It lived here until
 * the second instrument of Prompt Interception needed the same list and copied
 * two of its three filters (a parallel structure, see
 * docs/ELEMENT_STRUCTURE_REGISTRY.md).
 */
const { perspectives: presetConfigs, loadCoursePalette, ensureConfigs } =
  usePerspectiveCatalog()

const currentLanguage = computed(() => userPreferences.language)

// State
const selectedCategory = ref<string | null>(null)
const isLoadingPreset = ref(false)

// Categories that actually have presets after filtering, plus one's own
const categories = computed(() => {
  const cats = new Set<string>()
  presetConfigs.value.forEach(config => {
    config.properties?.forEach(p => cats.add(p))
  })
  // What this person saved hangs at the centre. Should a course have narrowed
  // the given ones away from there, the centre bubble is still needed — else
  // the saved ones would have nowhere to hang.
  if (kept.items.length > 0) cats.add(CENTRE)
  return Array.from(cats)
})

/** A saved perspective, dressed as a config so the same bubble can draw it. */
function asConfig(p: KeptPerspective) {
  return {
    id: p.style_key,          // custom:<id> — what a run is addressed with
    name: p.name,
    previewId: keptPreviewId(p),
    keptItem: p,
  }
}

// Filter configs for selected category — given perspectives and saved ones side
// by side, so `any` here as everywhere else this file touches a config object.
/** What hangs in one category, in the order it hangs there. ONE derivation:
 *  the ring around the opened circle and the whole-category double click have
 *  to be the same set, or taking all of them would take something the ring
 *  never showed. */
function configsOf(category: string): any[] {
  const given = presetConfigs.value.filter(config =>
    config.properties?.includes(category)
  )
  if (category !== CENTRE) return given
  return [...given, ...kept.items.map(asConfig)]
}

const visibleConfigs = computed<any[]>(() =>
  selectedCategory.value ? configsOf(selectedCategory.value) : []
)

/** The picture a GIVEN perspective wears. A saved one has none — it wears a
 *  colour of the palette instead, so it is never mistaken for the preset it
 *  was written over. */
function previewOf(config: any): string {
  return `/config-previews/${config.previewId || config.id}.webp`
}

/**
 * A picture drawn straight into a background paints its rows as they arrive,
 * so a large one builds up the circle from the top down. Here it is fetched
 * and decoded first and only then shown, over a fifth of a second.
 *
 * A picture decoded once is remembered for as long as the chooser lives, so
 * opening the ring a second time has it there at once and nothing fades.
 */
const decodedPreviews = new Set<string>()
const arrivedPreviews = ref<Record<string, boolean>>({})

function hasArrived(url: string): boolean {
  return decodedPreviews.has(url) || arrivedPreviews.value[url] === true
}

function fetchPreview(url: string) {
  if (decodedPreviews.has(url)) return
  const img = new Image()
  img.src = url
  const done = () => {
    decodedPreviews.add(url)
    arrivedPreviews.value = { ...arrivedPreviews.value, [url]: true }
  }
  // A picture that never arrives is still let through: the circle then shows
  // whatever the background load manages, rather than staying blank.
  if (typeof img.decode === 'function') void img.decode().then(done, done)
  else {
    img.onload = done
    img.onerror = done
  }
}

/**
 * The wording of a given perspective in the reader's language: what a pick
 * hands over as `context`. It is asked for when a category opens, together with
 * its pictures, so that a click has it at hand. Until 2026-09-28 the click
 * itself asked, twice (the whole catalogue again, then the wording), and the
 * ring stood unchanged until both answers were in: on a slow line for seconds,
 * with every further click swallowed. Held from one opening of the chooser to
 * the next, so that each opening reads the wording anew. `wordings` holds the
 * answers that have arrived, so that a click can tell at once whether it has one.
 */
const contexts = new Map<string, Promise<string>>()
const wordings = new Map<string, string>()

function wordingKey(configId: string, language: string): string {
  return `${configId}|${language}`
}

function contextOf(configId: string): Promise<string> {
  const language = currentLanguage.value
  const key = wordingKey(configId, language)
  const held = contexts.get(key)
  if (held) return held
  const asked: Promise<string> = getConfigContext(configId).then(({ context }) => {
    const text = typeof context === 'string' ? context : localized(context, language)
    if (contexts.get(key) === asked) wordings.set(key, text)
    return text
  })
  // A failed answer is not held: the next click asks again. Only this request
  // is let go, not one that a later opening has put under the same key.
  asked.catch(() => {
    if (contexts.get(key) === asked) contexts.delete(key)
  })
  contexts.set(key, asked)
  return asked
}

/**
 * Counts the openings of the chooser. A wording that arrives after the chooser
 * was dismissed or opened again belongs to a pick nobody is waiting for.
 */
let openings = 0
/** The opening in which a single pick is waiting for its wording. */
let waitingIn: number | null = null

// Category color map (same as PropertyCanvas)
const categoryColorMap: Record<string, string> = {
  semantics: '#2196F3',
  aesthetics: '#9C27B0',
  arts: '#E91E63',
  critical_analysis: '#4CAF50',
  research: '#00BCD4',
  attitudes: '#FF6F00',
  freestyle: '#FFC107',
  technical_imaging: '#607D8B',
}

// Category positions (percentage-based circle layout)
type CategoryPosition = { x: number; y: number }
const categoryPositions = ref<Record<string, CategoryPosition>>({})

function calculateCategoryPositions() {
  const positions: Record<string, CategoryPosition> = {}
  const all = categories.value

  if (all.includes('freestyle')) {
    positions.freestyle = { x: 50, y: 50 }
  }

  const others = all.filter(c => c !== 'freestyle')
  if (others.length === 0) {
    categoryPositions.value = positions
    return
  }

  // `others[index]` is typed `string | undefined` (noUncheckedIndexedAccess),
  // never absent: the ring has exactly as many points as there are categories.
  ringPositions(others.length, 35).forEach((pos, index) => {
    const category = others[index]
    if (category !== undefined) positions[category] = pos
  })

  categoryPositions.value = positions
}

function getCategoryColor(category: string): string {
  return categoryColorMap[category] ?? '#888888'
}

function getSymbolData(property: string): SymbolData | undefined {
  return configStore.getSymbolData(property)
}

function getConfigName(config: any): string {
  if (typeof config.name === 'string') return config.name
  return config.name[currentLanguage.value] || config.name.en || ''
}

function getConfigStyle(config: any, index: number) {
  const categoryPos = categoryPositions.value[selectedCategory.value!]
  if (!categoryPos) return { left: '50%', top: '50%' }

  // The ring widens with what stands in it. At the fixed 14 % the pieces began
  // to cover each other from six on — and since the saved perspectives moved to
  // the centre, that ring is the one that grows. A piece is 14.5 % of the
  // square wide, so the ring needs at least that much room between neighbours;
  // beyond 30 % it would leave the surface, and there it stops growing.
  const count = visibleConfigs.value.length
  const pos = bloomPosition(categoryPos, count, bloomDistancePct(count, 14.5, 14, 30), index)

  return { left: `${pos.x}%`, top: `${pos.y}%` }
}

/**
 * Hold a perspective for a moment and its name comes forward — the gesture the
 * flow already carries under a medium glyph. A touch surface has no hover, so
 * this is the way to read a name there without picking it.
 */
const heldId = ref<string | null>(null)
const { start: startHold, cancel: cancelHold, consumeHeld } = useHold<string>((id) => {
  heldId.value = id
})

/**
 * Which pointer is holding. Without it a second finger on a second circle would
 * end the first circle's hold — and the release of the first would then read as
 * a plain tap and pick a perspective nobody chose.
 */
let holdPointer: number | null = null

function onTilePress(e: PointerEvent, config: any) {
  // Only the first finger, and only the primary button: a second contact
  // neither starts a hold nor disturbs the one that is running.
  if (!e.isPrimary || e.button !== 0) return
  holdPointer = e.pointerId
  startHold(config.id)
}

function onTileRelease(e: PointerEvent) {
  if (holdPointer !== null && e.pointerId !== holdPointer) return
  holdPointer = null
  cancelHold()
  heldId.value = null
}

/** The click that follows a hold belongs to the hold: it was a look, not a pick. */
function onTileClick(config: any) {
  if (consumeHeld()) return
  void selectPreset(config)
}

/**
 * A category opens under the pointer. Reaching its ring meant clicking first
 * and clicking again to be rid of it; the ring is one move away now.
 *
 * Only where there is a pointer to hover with. A finger produces a mouseenter
 * of its own after a tap, and acting on that would open a category the person
 * only meant to touch, so the query is asked at every event rather than once.
 */
function canHover(): boolean {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(hover: hover) and (pointer: fine)').matches
}

/**
 * Held open after the pointer has left, because somebody clicked it. Hovering
 * a DIFFERENT category still takes over: the pointer says which one is open,
 * the click only says that this one stays.
 */
const pinnedCategory = ref(false)

/**
 * A category and its ring do not touch — about ten pixels of ground lie
 * between them, and more between one perspective and the next. Closing waits
 * a moment so that crossing that ground is not leaving.
 */
const CLOSE_AFTER_MS = 280
let closeTimer: ReturnType<typeof setTimeout> | null = null

function cancelClose() {
  if (closeTimer) {
    clearTimeout(closeTimer)
    closeTimer = null
  }
}

function onCategoryHover(category: string) {
  if (!canHover()) return
  cancelClose()
  if (selectedCategory.value === category) return
  selectedCategory.value = category
  pinnedCategory.value = false
}

function onClusterLeave() {
  if (!canHover() || pinnedCategory.value) return
  cancelClose()
  closeTimer = setTimeout(() => {
    closeTimer = null
    selectedCategory.value = null
  }, CLOSE_AFTER_MS)
}

function handleCategoryToggle(property: string) {
  cancelClose()
  if (selectedCategory.value !== property) {
    selectedCategory.value = property
    pinnedCategory.value = true
    return
  }
  // Already open. The first click on what the pointer opened keeps it — closing
  // there would fight the pointer, which is still on the same circle. A click
  // on one that is already held closes it, and so does a tap without hover.
  if (pinnedCategory.value || !canHover()) {
    selectedCategory.value = null
    pinnedCategory.value = false
  } else {
    pinnedCategory.value = true
  }
}

function handleUpdatePosition(category: string, x: number, y: number) {
  const centerX = 50
  const centerY = 50
  const radiusPercent = 35
  const dx = x - centerX
  const dy = y - centerY
  const dist = Math.sqrt(dx * dx + dy * dy)

  if (dist > radiusPercent) {
    const angle = Math.atan2(dy, dx)
    x = centerX + Math.cos(angle) * radiusPercent
    y = centerY + Math.sin(angle) * radiusPercent
  }

  categoryPositions.value = {
    ...categoryPositions.value,
    [category]: { x, y },
  }
}

async function selectPreset(config: any) {
  // Only while the chooser is shown. After a pick it fades out over three
  // tenths of a second, and a second click in that time would hand the same
  // perspective over again.
  if (!props.visible || isLoadingPreset.value || waitingIn === openings) return

  // One's own is already here — there is nothing to fetch, and `custom:<id>` is
  // not a config file the preset loader could open.
  const own: KeptPerspective | undefined = config.keptItem
  if (own) {
    emit('preset-selected', {
      configId: own.style_key,
      context: readPromptText(own.context_text, currentLanguage.value),
      configName: own.name,
      previewId: keptPreviewId(own),
      promptId: own.id,
    })
    emit('close')
    return
  }

  // The wording is usually here already, asked for when the category opened;
  // then the pick is handed over and the chooser closes at once. Otherwise the
  // chooser stays until the wording arrives. Closing before it had arrived let
  // the pick land after the chooser had been opened again for another field.
  const known = wordings.get(wordingKey(config.id, currentLanguage.value))
  if (known !== undefined) {
    emit('preset-selected', {
      configId: config.id,
      context: known,
      configName: getConfigName(config),
    })
    emit('close')
    return
  }

  const opening = openings
  waitingIn = opening
  try {
    const context = await contextOf(config.id)
    if (!props.visible || opening !== openings) return
    emit('preset-selected', {
      configId: config.id,
      context,
      configName: getConfigName(config),
    })
    emit('close')
  } catch (error) {
    console.error('[PresetOverlay] Error loading preset:', error)
  } finally {
    if (waitingIn === opening) waitingIn = null
  }
}

/**
 * A double click on a category shuts the chooser and takes EVERYTHING in it,
 * one after another, behind it.
 *
 * Picking eight perspectives out of one category meant opening the chooser
 * eight times, and the chooser closes on every pick. The circles are already
 * the group of a category; taking the group is the gesture that was missing.
 *
 * Each one is handed over exactly as a single pick hands it over, so nothing
 * downstream has to know this happened: a surface that holds several collects
 * them. A surface that holds one sets `single` and never gets here. One after
 * another, in the order they hang in the ring.
 *
 * The two clicks that make up the double click have already opened the category
 * and closed it again by the time this runs; the category comes with the event
 * rather than from that state, so it does not matter which way it ended up.
 */
async function takeWholeCategory(category: string) {
  if (props.single || isLoadingPreset.value) return
  const configs = configsOf(category)
  if (!configs.length) return

  // The chooser goes FIRST, before anything is fetched. Taking eight
  // perspectives is eight requests, and the chooser stood there through
  // all of them with nothing to show for it — on the flow board it stayed up
  // afterwards as well, so the gesture read as one that had done nothing.
  // Going at once IS the acknowledgement, and the
  // perspectives then arrive one after another behind it. Every surface holds
  // this component through `visible` rather than `v-if`, so it stays alive and
  // keeps handing them over after it has closed.
  emit('close')

  isLoadingPreset.value = true
  try {
    for (const config of configs) {
      const own: KeptPerspective | undefined = config.keptItem
      if (own) {
        emit('preset-selected', {
          configId: own.style_key,
          context: readPromptText(own.context_text, currentLanguage.value),
          configName: own.name,
          previewId: keptPreviewId(own),
          promptId: own.id,
        })
        continue
      }
      emit('preset-selected', {
        configId: config.id,
        context: await contextOf(config.id),
        configName: getConfigName(config),
      })
    }
  } catch (error) {
    // What was handed over before it broke stays handed over; what follows it
    // does not arrive, and the surface shows how far it got.
    console.error('[PresetOverlay] Error loading a category:', error)
  } finally {
    isLoadingPreset.value = false
  }
}

/** Delete a saved perspective. It is asked for once — this cannot be undone,
 *  and the versions behind it go with it. */
async function dropKept(p: KeptPerspective) {
  if (!window.confirm(t('presetOverlay.mineDropConfirm', { name: p.name }))) return
  await kept.remove(p.id)
  // Only close the ring when the last thing in it is gone — the centre still
  // carries the given perspectives after one's own has been deleted.
  if (visibleConfigs.value.length === 0) selectedCategory.value = null
}

// Load configs when overlay becomes visible
watch(() => props.visible, async (isVisible) => {
  // Ask what is actually missing — the given perspectives — not whether any
  // category exists: the centre can be there on account of saved perspectives
  // alone, and asking about categories left the given ones unloaded forever.
  // The asking itself is the catalogue's, so that the one derivation is loaded
  // the one way (docs/ELEMENT_STRUCTURE_REGISTRY.md); the guard and the load
  // are what stood here.
  if (isVisible) {
    openings += 1
    contexts.clear()
    wordings.clear()
  }
  if (isVisible) await ensureConfigs()
  // Every picture of the chooser is fetched as it opens, so that a category
  // opened under the pointer has its pictures at once.
  if (isVisible) presetConfigs.value.forEach((config) => fetchPreview(previewOf(config)))
  // What this person kept, and what their course carries, can have changed on
  // another surface since the last opening — both are read again rather than
  // cached for the session.
  if (isVisible) {
    await kept.ensureSession()
    await Promise.all([kept.load(), loadCoursePalette()])
    calculateCategoryPositions()
  }
  if (isVisible) {
    calculateCategoryPositions()
  }
  if (!isVisible) {
    cancelClose()
    pinnedCategory.value = false
    selectedCategory.value = null
    holdPointer = null
    cancelHold()
    heldId.value = null
  }
})

// Recalculate when categories change
watch(categories, () => calculateCategoryPositions())

// Fetch the pictures of the ring that is opening, so each one is ready to be
// painted whole by the time its circle is there. The wording each one hands
// over is asked for at the same moment.
watch(
  visibleConfigs,
  (configs) => {
    configs.forEach((config) => {
      if (config.keptItem) return
      fetchPreview(previewOf(config))
      void contextOf(config.id)
    })
  },
  { immediate: true },
)

</script>

<style scoped>
/* PropertyBubble needs pointer-events within overlay */
.property-bubble {
  pointer-events: all;
}

/* Config bubbles: calc(--square-size * 0.145) für width UND height = Kreis */
/* The circle is cut by .config-content, which holds the picture and the band.
   Here it must NOT be cut: the remove mark sits in the corner of the box, and a
   round clip at this level took all but a fifth of a pixel of it away — which
   is why the mark has never been reachable, on any device. */
.config-bubble {
  position: absolute;
  width: calc(var(--square-size) * 0.145);
  height: calc(var(--square-size) * 0.145);
  border-radius: 50%;
  /* The centring lives in `translate`, not in `transform`. A transition-group
     writes an inline `transform` onto every child whose place it believes has
     changed, and an inline transform replaces the property whole. With the
     centring inside it, each piece stood half its own width down and to the
     right for one paint and then slid back over three tenths of a second --
     the flicker that appeared whenever a picture arrived late enough to cause
     a second render. `translate` is applied before `transform`, so both can
     hold at once. */
  translate: -50% -50%;
  cursor: pointer;
  pointer-events: all;
  transition: all 0.3s ease;
  font-size: calc(var(--square-size) * 0.02);
  /* A hold is a hold: no text selection, no callout, no double-tap delay. */
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
  touch-action: manipulation;
}

.config-bubble:hover {
  transform: scale(1.1);
  z-index: 10;
  /* Read by CircleTitle: under the pointer the name comes forward. */
  --circle-title-opacity: 0.8;
}

.config-content {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  overflow: hidden;
  background: white;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
}


.preview-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  background-color: #f0f0f0;
  /* Held back until the picture can be painted in one go (see hasArrived). */
  opacity: 0;
  transition: opacity 0.22s ease;
}

.preview-image.is-here {
  opacity: 1;
}

/* A saved perspective has no picture: the palette colour fills the circle. */
.kept-face {
  position: absolute;
  inset: 0;
}

/* Transitions */
.config-fade-enter-active,
.config-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.config-fade-enter-from {
  opacity: 0;
  transform: scale(0.8);
}

.config-fade-leave-to {
  opacity: 0;
  transform: scale(0.8);
}

</style>
