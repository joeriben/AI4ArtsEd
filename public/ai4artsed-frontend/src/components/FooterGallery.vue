<template>
  <div class="footer-gallery" :class="{ expanded: isExpanded }">
    <!-- Toggle Bar -->
    <div class="toggle-bar" @click="toggleGallery">
      <div class="toggle-content">
        <span class="toggle-icon">
          <svg v-if="!isExpanded" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M480-528 296-344l-56-56 240-240 240 240-56 56-184-184Z"/>
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M480-344 240-584l56-56 184 184 184-184 56 56-240 240Z"/>
          </svg>
        </span>
        <span class="toggle-text">
          {{ $t('gallery.title') }}
          <span v-if="totalFavorites > 0" class="badge">{{ totalFavorites }}</span>
        </span>

        <!-- View Mode Toggle (per-user favorites, 2-Feld-Switch) -->
        <div class="view-mode-switch" @click.stop>
          <button
            class="switch-option"
            :class="{ active: viewMode === 'per_user' }"
            @click="setViewModePerUser"
            :title="$t('gallery.viewMine')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" height="14" width="14" viewBox="0 -960 960 960">
              <path
                d="M480-480q-66 0-113-47t-47-113q0-66 47-113t113-47q66 0 113 47t47 113q0 66-47 113t-113 47ZM160-160v-112q0-34 17.5-62.5T224-378q62-31 126-46.5T480-440q66 0 130 15.5T736-378q29 15 46.5 43.5T800-272v112H160Z"
              />
            </svg>
            <span>{{ $t('gallery.mine') }}</span>
          </button>
          <button
            class="switch-option"
            :class="{ active: viewMode === 'global' }"
            @click="setViewModeGlobal"
            :title="$t('gallery.viewAll')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" height="14" width="14" viewBox="0 -960 960 960">
              <path
                d="M0-240v-63q0-43 44-70t116-27q13 0 25 .5t23 2.5q-14 21-21 44t-7 48v65H0Zm240 0v-65q0-32 17.5-58.5T307-410q32-20 76.5-30t96.5-10q53 0 97.5 10t76.5 30q32 20 49 46.5t17 58.5v65H240Zm540 0v-65q0-26-6.5-49T754-397q11-2 22.5-2.5t23.5-.5q72 0 116 26.5t44 70.5v63H780Z"
              />
            </svg>
            <span>{{ $t('gallery.all') }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Gallery Content -->
    <Transition name="gallery-slide">
      <div v-if="isExpanded" class="gallery-content">
        <!-- Loading State -->
        <div v-if="isLoading" class="gallery-loading">
          <span class="spinner"></span>
          {{ $t('common.loading') }}
        </div>

        <!-- Empty State -->
        <div v-else-if="favorites.length === 0" class="gallery-empty">
          <span class="empty-icon">
            <svg xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" fill="currentColor">
              <path d="m480-120-58-52q-101-91-167-157T150-447.5Q111-500 95.5-544T80-634q0-94 63-157t157-63q52 0 99 22t81 62q34-40 81-62t99-22q94 0 157 63t63 157q0 46-15.5 90T810-447.5Q771-395 705-329T538-172l-58 52Z"/>
            </svg>
          </span>
          <p>{{ $t('gallery.empty') }}</p>
        </div>

        <!-- Favorites Grid -->
        <div v-else class="gallery-grid" ref="galleryGridRef">
          <div
            v-for="favorite in favorites"
            :key="favorite.run_id"
            class="gallery-item"
            :class="{ 'not-found': !favorite.exists }"
            draggable="true"
            @dragstart="onFavDragStart($event, favorite)"
          >
            <!-- Thumbnail -->
            <div class="thumbnail-container" @click="openRun(favorite)">
              <!-- The directive OWNS the src (composables/useLazyMedia.ts), so
                   there is no `:src` here. -->
              <!-- Only where there is a picture to draw. A kept run whose piece
                   the platform can no longer serve drew the browser's own
                   broken-image mark and the word "Favorite" next to it. -->
              <img
                v-if="favorite.media_type === 'image' && favorite.exists"
                v-lazy-media="favorite.thumbnail_url"
                :alt="favorite.input_preview || 'Favorite'"
                class="thumbnail"
                draggable="false"
              />
              <div v-else class="thumbnail-placeholder">
                <span class="media-icon">{{ getMediaIcon(favorite.media_type) }}</span>
              </div>

              <!-- Overlay with info -->
              <div class="thumbnail-overlay">
                <span v-if="favorite.input_preview" class="preview-text">
                  {{ favorite.input_preview }}
                </span>
              </div>

              <!-- Letting go of a kept run, on the plate itself - the one thing
                   about a plate that must not need the large view first. Only
                   on one's own: in the `global` view the strip shows everyone's
                   and the server refuses a foreign delete (favorites_routes
                   `_may_change`), so a mark there would make a plate vanish and
                   come straight back. -->
              <RemoveBadge
                v-if="canRemove(favorite)"
                :title="$t('gallery.unfavorite')"
                @remove="handleRemove(favorite)"
              />
            </div>

          </div>
        </div>
      </div>
    </Transition>

    <!-- One kept run, large: the picture as big as the window allows, and
         beside it what the run WAS — the instrument or config it came from, the
         prompt, the parameters it ran with, when it was made, the marking its
         file carries — on the platform's own panel, with the platform's row of
         things one can do with a made thing (stage 3 of „one click, one view";
         before that the strip had composed all of that itself, in its own
         wording, under the picture).

         Before that the plates carried three hand-rolled buttons. Two of them
         could not say what they would do (the strip is 100 px wide), and the
         third promised a restore that most runs cannot give. -->
    <MediaFullscreen
      :src="shownSrc"
      :kind="shownKind"
      :code="shownCode"
      :code-kind="shownCodeKind"
      :alt="shown?.input_preview || undefined"
      :width="shownShot?.width"
      :height="shownShot?.height"
      :poster="shownShot?.poster"
      :back="shownBack"
      @close="closeRun"
      @toggle-favorite="removeShown"
      @restore="openWhereItWasMade"
      @download="downloadShown"
      @print="printShown"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useFavoritesStore, type FavoriteItem, type RestoreData } from '@/stores/favorites'
import { useDeviceId } from '@/composables/useDeviceId'
import { asSeed } from '@/composables/useSeedAutomatic'
import { FAVORITE_DT } from '@/composables/useMaterialIntake'
import { vLazyMedia } from '@/composables/useLazyMedia'
import MediaFullscreen from '@/components/MediaFullscreen.vue'
import type { MediaBack } from '@/components/mediaBack'
import RemoveBadge from '@/components/RemoveBadge.vue'
import { downloadMedia, mediaExtension } from '@/lib/downloadMedia'
import { printMedia } from '@/lib/printMedia'
import { fusionSettingLabel, recordedFactors, recordedNumber } from '@/lib/fusionSetting'
import {
  canvasModels,
  canvasPrompt,
  givenName,
  saveCanvasFile,
  toCanvasWorkflow,
} from '@/lib/canvasFile'
import type { CanvasWorkflow } from '@/types/canvas'

const { t, locale } = useI18n()
const router = useRouter()
const favoritesStore = useFavoritesStore()
const galleryGridRef = ref<HTMLElement | null>(null)

// Computed from store
const favorites = computed(() => favoritesStore.favorites)
const totalFavorites = computed(() => favoritesStore.totalFavorites)
const isLoading = computed(() => favoritesStore.isLoading)
const isExpanded = computed(() => favoritesStore.isGalleryExpanded)
const viewMode = computed(() => favoritesStore.viewMode)

const currentDeviceId = ref(useDeviceId())

/**
 * How the pictures get here, and why NOT with `loading="lazy"`.
 *
 * The strip holds every favourite the device knows — 73 on this machine — and
 * each plate is 100 px wide. `loading="lazy"` looked like the answer and was
 * the bug (the miniatures sometimes appeared only on mouse-over): the plates
 * are mounted while the strip is still CLOSED — the slide transition opens
 * from `max-height: 0` — so Chrome defers every one of them and asks again
 * only on a real interaction. Measured with the strip open and ten plates
 * standing in the window: ten lazy images, none loaded, still none seconds
 * later; the same picture switched to `eager` was there at once.
 *
 * `v-lazy-media` is the platform's own answer to exactly this (it carries the
 * session table of the settings area) and it keeps WATCHING: an
 * IntersectionObserver per element, and a queue three wide so the first plates
 * are there while the rest wait their turn. What it needs is that the element
 * has its own identity per row, which the `:key` on the item gives it.
 */

function onFavDragStart(e: DragEvent, favorite: FavoriteItem) {
  e.dataTransfer?.setData(
    FAVORITE_DT,
    JSON.stringify({ run_id: favorite.run_id, media_type: favorite.media_type })
  )
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy'
}

// Actions
function toggleGallery() {
  favoritesStore.toggleGallery()
}

// Set view mode handlers
function setViewModePerUser() {
  if (viewMode.value !== 'per_user') {
    favoritesStore.setViewMode('per_user', currentDeviceId.value)
  }
}

function setViewModeGlobal() {
  if (viewMode.value !== 'global') {
    favoritesStore.setViewMode('global', currentDeviceId.value)
  }
}

function getMediaIcon(mediaType: string): string {
  const icons: Record<string, string> = {
    image: 'IMG',
    video: 'VID',
    audio: 'AUD',
    music: 'MUS',
    '3d': '3D',
    composition: 'A/V',
    midi: 'MID',
    p5: 'P5',
    tonejs: 'TON',
    sonicpi: 'SPI',
    text: 'TXT',
    canvas: 'CNV'
  }
  return icons[mediaType] || '—'
}

// ============================================================================
// One kept run, large
// ============================================================================

/** The plate that was tapped, and what the server knows about that run. */
const shown = ref<FavoriteItem | null>(null)
const shownData = ref<RestoreData | null>(null)

/**
 * Whether an output of a run is of the kind a favourite was kept as - THE one
 * rule in this file, asked wherever a run's outputs are searched.
 *
 * Sound is one thing on this platform under two names: a run of a music config
 * records `output_music`, one of a sound config `output_audio`, and a favourite
 * carries whichever name the surface it was starred on used. The store pairs
 * them (favorites_routes `_entity_types_for`), so a run kept as music counts as
 * kept - and the strip has to pair them too, or such a run falls through to
 * "the first thing that is not a sketch" and a player is handed a picture.
 */
function sameKind(a: string, b: string): boolean {
  const sound = (k: string) => (k === 'music' ? 'audio' : k)
  return sound(a) === sound(b)
}

/** Which open is the current one; a later tap makes an earlier one give up. */
let openSeq = 0

async function openRun(favorite: FavoriteItem) {
  if (!favorite.exists) return
  const seq = ++openSeq
  const isSketch = favorite.media_type === 'p5' || favorite.media_type === 'tonejs'
  if (!isSketch) {
    shown.value = favorite
    shownData.value = null
    shownCode.value = ''
    const data = await favoritesStore.getRestoreData(favorite.run_id)
    if (seq === openSeq) shownData.value = data
    return
  }
  // A sketch opens WITH its source or not at all. Shown first and read after,
  // the layer stood there as a black rectangle for as long as the file took —
  // and stayed one, silently, where the file could not be read at all. The
  // source is fetched here rather than in the layer, which shows what it is
  // given and asks nothing of the server.
  const data = await favoritesStore.getRestoreData(favorite.run_id)
  const url = (data?.media_outputs || []).find(
    (o) => sameKind(o.type || '', favorite.media_type) && !!o.url
  )?.url
  let code = ''
  try {
    if (url) {
      const res = await fetch(url)
      code = res.ok ? await res.text() : ''
    }
  } catch {
    /* an unreadable source: the run stays closed */
  }
  if (seq !== openSeq || !code) return
  shown.value = favorite
  shownData.value = data
  shownCode.value = code
}

function closeRun() {
  openSeq += 1
  shown.value = null
  shownData.value = null
  shownCode.value = ''
}

/** The runtimes that record under their own name; their file is no picture. */
const RUNTIME_KINDS = ['p5', 'tonejs', 'sonicpi', 'midi']

/**
 * Where the kept piece itself lies, known without waiting for the run's record.
 *
 * NOT `thumbnail_url`: for a picture the strip is answered with a 160 px copy
 * (favorites_routes rewrites the field for the plates), and the layer draws
 * what it is handed at that picture's own size - so the large view stood at
 * 160 px on black until the record arrived and named the real one. The picture
 * has an address of its own, the same one the record names. Every other kind is
 * served whole from the one address the field already carries.
 *
 * The cost, paid on the first open only (the full picture is answered
 * `no-cache` with an ETag, so every open after it is a 304): until the picture
 * is there the ground stays empty. The small copy cannot stand in for it - laid
 * out by its own size it is the 160 px stamp again, and laid out by the box it
 * would be enlarged past what the picture will occupy, so the picture would
 * jump when it arrives. The measurements that would settle it are in no record.
 */
function fullSrc(f: FavoriteItem): string {
  return f.media_type === 'image' ? `/api/media/image/${f.run_id}/0` : f.thumbnail_url
}

/**
 * A kept Canvas workflow has no medium. What stands in its place is the mark the
 * Canvas carries on the entrance page (LandingView), in its colour — as the flow
 * puts the Wikipedia mark where a looked-up source has no picture.
 */
const CANVAS_MARK = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 24 24" fill="#4CAF50">' +
  '<path d="M22 11V3h-7v3H9V3H2v8h7V8h2v10h4v3h7v-8h-7v3h-2V8h2v3z"/></svg>'
)}`

/**
 * The workflow the run brings along: the board itself where a workflow was
 * kept, the board that made it where an output of a Canvas run was kept.
 */
const shownCanvas = computed<CanvasWorkflow | null>(() => {
  const stored = shownData.value?.canvas_workflow
  if (!stored) return null
  try {
    return toCanvasWorkflow(stored)
  } catch {
    return null
  }
})

const shownSrc = computed(() => {
  if (!shown.value) return null
  if (shown.value.media_type === 'canvas') return CANVAS_MARK
  const outs = (shownData.value?.media_outputs || []).filter((o) => !!o.url)
  // The output of the kind that was kept. A run that recorded a sketch AND a
  // still holds two, and the first is not always the one that was starred.
  const out =
    outs.find((o) => sameKind(o.type || '', shown.value?.media_type || '')) ||
    outs.find((o) => !RUNTIME_KINDS.includes(o.type || ''))
  return out?.url || fullSrc(shown.value)
})

/**
 * What the layer needs to hold the picture's place: its measurements and the
 * plate's own small copy, which is already in the browser because the strip
 * drew it. Sounds, films and sketches have nothing of the sort.
 *
 * Handed over only once the run's RECORD is in, though both are known earlier.
 * The panel beside the picture is drawn from the record, and the room left for
 * the picture is what stands next to it, so a place held before the record
 * lands would be held too generously and the copy would step down under the
 * eye. The record is one short answer; the picture is megabytes, and it is
 * still travelling when the place is finally right.
 */
const shownShot = computed(() => {
  if (!shownData.value || shown.value?.media_type !== 'image') return null
  return {
    width: shown.value.width,
    height: shown.value.height,
    poster: shown.value.thumbnail_url,
  }
})

/** What the layer has to draw. The platform's music is a sound file. */
const shownKind = computed<'image' | 'video' | 'audio' | '3d' | 'code'>(() => {
  const type = shown.value?.media_type
  if (type === 'video') return 'video'
  if (type === 'audio' || type === 'music') return 'audio'
  // A composition is delivered as an mp4 and plays like any other film.
  if (type === 'composition') return 'video'
  if (type === '3d') return '3d'
  // A sketch is read and run, not looked at: its source is what the run holds.
  if (type === 'p5' || type === 'tonejs') return 'code'
  return 'image'
})

const shownCodeKind = computed<'p5js' | 'tonejs'>(() =>
  shown.value?.media_type === 'tonejs' ? 'tonejs' : 'p5js'
)

/**
 * The source of the sketch being looked at. The run serves it as a file, so it
 * is read once the run is opened; a run that is not a sketch leaves it empty.
 */
const shownCode = ref('')

/** The instrument that made it, or the config it ran under. */
const shownName = computed(() => shownData.value?.instrument?.tool || shownData.value?.schema || shown.value?.schema || '')

const shownPrompt = computed(
  () => shownData.value?.input_text || shownData.value?.transformed_text || shown.value?.input_preview || ''
)

const shownWhen = computed(() => {
  const stamp = shownData.value?.timestamp || shown.value?.timestamp || shown.value?.added_at
  if (!stamp) return ''
  const when = new Date(stamp)
  return isNaN(when.getTime()) ? '' : when.toLocaleString(locale.value)
})

/**
 * What the run ran with. An instrument keeps its own parameters; a run from the
 * pipelines carries the models it passed through. Values that are themselves
 * structures say nothing in one line and stay out. The prompt stands out too
 * where it is the text of the block above — an instrument keeps it among its
 * parameters, and it stood on the panel twice. What is long and NOT that text
 * is cut to a line rather than dropped: a negative prompt is a setting, and a
 * setting that disappears at the length it happens to have is worse than one
 * that ends in an ellipsis. Where a run has no prompt block at all — feature
 * probing, concept algebra and representation engineering write `prompt_a`,
 * `prompt_b` and `test_text`, and the storage builds the block out of `prompt`
 * alone (favorites_routes.py) — every value stands whole: the parameter is the
 * only text such a run has, and its terms are what tell two runs apart.
 */
const PARAM_LINE = 60

const shownParams = computed<Array<{ k: string; v: string }>>(() => {
  const source = shownData.value?.instrument?.parameters || shownData.value?.models_used
  if (!source) return []
  const above = shownPrompt.value
  return Object.entries(source as Record<string, unknown>)
    .filter(([, v]) => v !== null && v !== undefined && v !== '' && typeof v !== 'object')
    .map(([k, v]) => ({ k, v: String(v) }))
    .filter(({ v }) => !above || v !== above)
    .map(({ k, v }) =>
      above && v.length > PARAM_LINE ? { k, v: `${v.slice(0, PARAM_LINE).trimEnd()}…` } : { k, v }
    )
    .slice(0, 8)
})

/**
 * The record of the run standing large, as the platform's panel reads it
 * (`MediaBack`, components/mediaBack.ts; the panel is `MediaCardBack`, the same
 * one every card turns over to). Its row of actions is this strip's: the star
 * takes the run out of the favourites, and right after it stands the way back
 * into the instrument that made the run, where that instrument reads a run
 * back (`backTo`). Handing on is not offered here, since a plate is dragged
 * from the favourites straight into a field (`FAVORITE_DT`); the copy button
 * stood where the way back now stands. With it went the only button that put
 * a run into the platform's hand; since 2026-10-10 the hand carries text alone.
 *
 * The time stands among the facts rather than in the panel's own time slot,
 * which names the hour and the minute: a kept run is weeks old as often as
 * minutes, and the day it was made is half of what the line says here.
 */
const shownBack = computed<MediaBack | null>(() => {
  const favorite = shown.value
  if (!favorite) return null
  if (favorite.media_type === 'canvas') {
    // The workflow's record: its name, the prompt it starts from, how many
    // nodes it has and which models it generates with.
    const workflow = shownCanvas.value
    return {
      mediaType: 'canvas',
      runId: favorite.run_id,
      mediaUrl: CANVAS_MARK,
      active: !!shownData.value,
      isFavorited: true,
      keepDisabled: !canRemove(favorite),
      canRestore: !!backTo.value,
      prompt: canvasPrompt(workflow),
      configId: givenName(workflow) || t('canvas.title'),
      facts: [
        shownWhen.value,
        workflow ? `${workflow.nodes.length} ${t('canvas.nodes')}` : '',
        ...canvasModels(workflow),
      ].filter(Boolean),
    }
  }
  return {
    mediaType: favorite.media_type || 'image',
    runId: favorite.run_id,
    // The file itself, so the AI marking is read out of the very copy that is
    // standing on the screen — and only once the RECORD is in, because until
    // then the address of anything but a picture is the plate's own, which
    // names no output of the run (`fullSrc`): the marking would be read off
    // the last file of that kind instead of the one being looked at.
    mediaUrl: shownSrc.value || undefined,
    active: !!shownData.value,
    isFavorited: true,
    keepDisabled: !canRemove(favorite),
    canForward: false,
    canRestore: !!backTo.value,
    prompt: shownPrompt.value,
    setting: shownSetting.value,
    configId: shownName.value,
    facts: [shownWhen.value, ...shownParams.value.map((p) => `${p.k} ${p.v}`)].filter(Boolean),
  }
})

/**
 * Instruments that take a run of theirs BACK - they keep their own record of
 * it, so the whole setting can be stood up again. Everywhere else the run is
 * still fully usable: its prompt and its picture are dragged into a field.
 * What no page can do is rebuild a board out of a single kept product, and a
 * button that says it will is worse than no button.
 */
const TAKES_A_RUN_BACK: Record<string, string> = {
  denoising_archaeology: '/latent-lab/denoising-archaeology',
  mean_images: '/latent-lab/mean-images',
  surrealizer: '/latent-lab/encoder-fusion'
}

const backTo = computed<string | null>(() => {
  const data = shownData.value
  if (!data) return null
  // A kept workflow, or an output kept in the Canvas: the run brings the board
  // along, and the Canvas opens it (views/canvas_workflow.vue). Resona's
  // apparatus run the same way and carry a board too, but they were made in
  // Resona, and the Canvas is not where they come back to.
  if (data.canvas_workflow && (shown.value?.media_type === 'canvas' || data.target_view === 'canvas')) {
    return '/canvas'
  }
  const tool = data.instrument?.tool
  if (tool) return TAKES_A_RUN_BACK[tool] || null
  // From before the instruments kept their own record: the encoder fusion still
  // takes its own back from the plain restore data.
  if (data.target_view === 'surrealizer' && data.input_text) return TAKES_A_RUN_BACK.surrealizer ?? null
  return null
})

function openWhereItWasMade() {
  const target = backTo.value
  if (!target || !shownData.value) return
  favoritesStore.setRestoreData(shownData.value)
  const to = target
  closeRun()
  router.push(to)
}

/**
 * The setting the run went out with, in one line under the prompt, as the
 * instrument lays it back when the run is opened there. So far the Encoder
 * Fusion alone: its three factors, layout and pooled vector, read with the
 * instrument's own reader and worded as on its run cards (lib/fusionSetting),
 * then the CFG under the label of its field and the seed under the word its
 * field shows, the seed by the rule the restore lays it back with (`asSeed`)
 * and from the same picture (views/surrealizer.vue). A record whose factors the instrument cannot read
 * (an alpha from before the three factors under a strategy it has no reading
 * for, the sphere) keeps its sliders on the surface where they stand, and the
 * line then names only the CFG and the seed. The negative prompt is laid back
 * too and stands on no line here.
 */
const shownSetting = computed(() => {
  const data = shownData.value
  if (!data || backTo.value !== TAKES_A_RUN_BACK.surrealizer) return ''
  const state = data.current_state || {}
  const parts: string[] = []
  const factors = recordedFactors(state)
  if (factors) {
    parts.push(fusionSettingLabel(factors.a, factors.b, factors.c, factors.rows, factors.pooled, locale.value))
  }
  const cfg = recordedNumber(state.cfg)
  if (cfg !== null) {
    parts.push(`${t('surrealizer.cfgLabel')} ${new Intl.NumberFormat(locale.value, { maximumFractionDigits: 2 }).format(cfg)}`)
  }
  const picture = (data.media_outputs || []).find((o) => o.type === 'image' && o.url)
  const seed = asSeed(picture?.metadata?.seed)
  if (seed !== null) parts.push(`${t('surrealizer.seedLabel')} ${seed}`)
  return parts.join(' · ')
})

async function downloadShown() {
  if (!shown.value) return
  if (shown.value.media_type === 'canvas') {
    // The workflow as a `.atcanvas` file, dated by when it was kept: the same
    // kept workflow is the same file, however often it is saved.
    const workflow = shownCanvas.value
    if (!workflow) return
    const stamp = shownData.value?.timestamp || shown.value.added_at
    const when = stamp ? new Date(stamp) : new Date()
    saveCanvasFile(workflow, isNaN(when.getTime()) ? new Date() : when)
    return
  }
  const url = shownSrc.value
  if (!url) return
  const ext = mediaExtension(shown.value.media_type)
  await downloadMedia(url, `${shown.value.run_id}.${ext}`)
}

function printShown() {
  printMedia(shownSrc.value)
}

/** The star on a kept run means letting go of it. */
async function removeShown() {
  const favorite = shown.value
  if (!favorite || !canRemove(favorite)) return
  closeRun()
  await handleRemove(favorite)
}

/**
 * Whose favourite is this? Mirrors `_may_change` in favorites_routes.py:
 * one without an owner predates per-user favourites and stays removable.
 */
function canRemove(favorite: FavoriteItem): boolean {
  return !favorite.device_id || favorite.device_id === currentDeviceId.value
}

async function handleRemove(favorite: FavoriteItem) {
  await favoritesStore.removeFavorite(favorite.run_id, currentDeviceId.value)
}

// Load favorites on mount (pass device_id)
onMounted(() => {
  favoritesStore.loadFavorites(currentDeviceId.value)
})
</script>

<style scoped>
/* ============================================================================
   Footer Gallery Container
   ============================================================================ */

.footer-gallery {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 950;
  background: rgb(var(--bg-base-rgb) / 0.99);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  transition: transform 0.3s ease;
}

/* ============================================================================
   Toggle Bar
   ============================================================================ */

.toggle-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: var(--footer-collapsed-height);
  padding: 0 1rem;
  cursor: pointer;
  transition: background 0.2s ease;
}

.toggle-bar:hover {
  background: rgba(255, 255, 255, 0.05);
}

.toggle-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.875rem;
}

.toggle-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.toggle-icon svg {
  width: 20px;
  height: 20px;
  fill: currentColor;
}

.toggle-text {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.badge {
  background: rgba(76, 175, 80, 0.3);
  color: #4CAF50;
  padding: 0.125rem 0.5rem;
  border-radius: 10px;
  font-size: 0.75rem;
  font-weight: 700;
}

/* View Mode Switch (2-Feld-Switch) */
.view-mode-switch {
  display: flex;
  gap: 0;
  margin-left: auto;
  background: rgb(var(--bg-base-rgb) / 0.3);
  border-radius: 6px;
  padding: 2px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.switch-option {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.switch-option:hover {
  color: rgba(255, 255, 255, 0.8);
  background: rgba(255, 255, 255, 0.05);
}

.switch-option.active {
  background: rgba(102, 126, 234, 0.4);
  color: rgba(255, 255, 255, 1);
  font-weight: 700;
}

.switch-option svg {
  fill: currentColor;
  flex-shrink: 0;
}

.switch-option span {
  font-weight: inherit;
}

/* ============================================================================
   Gallery Content
   ============================================================================ */

.gallery-content {
  max-height: 140px; /* Reduziert von 180px um weniger Output zu verdecken */
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0.5rem 1rem 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

/* Loading & Empty States */
.gallery-loading,
.gallery-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  color: rgba(255, 255, 255, 0.5);
  gap: 0.75rem;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: #4CAF50;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-icon svg {
  fill: rgba(255, 255, 255, 0.3);
}

.gallery-empty p {
  margin: 0;
  font-size: 0.875rem;
}

/* ============================================================================
   Gallery Grid (Horizontal Scroll)
   ============================================================================ */

.gallery-grid {
  display: flex;
  gap: 0.75rem;
  padding-bottom: 0.5rem;
}

/* Gallery Item */
.gallery-item {
  flex: 0 0 auto;
  width: 100px; /* Reduziert von 120px */
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.gallery-item.not-found {
  opacity: 0.5;
}

/* Thumbnail Container */
.thumbnail-container {
  position: relative;
  width: 100px; /* Reduziert von 120px */
  height: 70px; /* Reduziert von 90px */
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  background: rgb(var(--surface-2-rgb) / 0.8);
  border: 2px solid rgba(255, 255, 255, 0.1);
  transition: all 0.2s ease;
}

.thumbnail-container:hover {
  border-color: rgba(102, 126, 234, 0.5);
  transform: translateY(-2px);
}

.thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumbnail-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(var(--surface-3-rgb) / 0.9);
}

.media-icon {
  font-size: 2rem;
}

/* Thumbnail Overlay */
.thumbnail-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 0.25rem 0.5rem;
  background: linear-gradient(transparent, rgb(var(--bg-base-rgb) / 0.8));
  opacity: 0;
  transition: opacity 0.2s ease;
}

.thumbnail-container:hover .thumbnail-overlay {
  opacity: 1;
}

.preview-text {
  font-size: 0.625rem;
  color: rgba(255, 255, 255, 0.9);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ============================================================================
   Animations
   ============================================================================ */

.gallery-slide-enter-active,
.gallery-slide-leave-active {
  transition: all 0.3s ease;
}

.gallery-slide-enter-from,
.gallery-slide-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}

/* ============================================================================
   Responsive
   ============================================================================ */

@media (max-width: 768px) {
  .footer-gallery {
    left: 0;
  }

  .gallery-content {
    max-height: 120px;
    padding: 0.5rem;
  }

  .gallery-item {
    width: 80px;
  }

  .thumbnail-container {
    width: 80px;
    height: 60px;
  }
}
</style>
