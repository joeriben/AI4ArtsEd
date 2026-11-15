<!--
  MMAudio — a picture is given to a sound model, and what comes back is what
  that model makes of it, with a prompt beside it.

  Split out of views/latent_lab/crossmodal_lab.vue on 2026-09-05, where it stood
  with the Latent Audio Synth and ImageBind Guidance in one file. Until
  2026-11-02 the surface was the one that file carried at a50054bc, one thing
  under another, in its own scoped style and from 2026-10-10 on the Crossmodal
  stage (assets/crossmodal-stage.css).

  Since 2026-11-02 it stands in the frame of the instruments
  (`.lab-main` / `.lab-stage` / `.lab-work`, assets/flow-stage.css): the trigger
  in the bar, the picture and the prompt in the preparing column with the
  four numbers in its klappe, and on the right one row per press, newest on
  top (`.lab-runrows`, assets/flow-stage.css): the row names once what its run
  was made with, and under that stand the picture it was given, if any, and
  the sound in the platform's cell (components/MediaGridCell.vue), whose back
  carries the favourite and the download. Rows, so that a run with a picture
  and one without can be heard against each other.

  Until 2026-11-03 a negative prompt stood under the prompt, MMAudio's own
  parameter, taken over with the first build of 2026-02-16 (80ce98ea). It
  left the surface on request; a run goes out without one, and the backend
  gives the model the empty string in its place.

  The picture is the one ImageBind Guidance works on as well
  (composables/useCrossmodalPicture.ts), which is what the two shared refs of
  the old single file did.
-->
<template>
  <div class="lab-page">
    <ShellRun
      :ready="canRun"
      :running="generating"
      :title="t('latentLab.crossmodal.generate')"
      @run="runMMAudio"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <section class="cmp-column lab-prep lab-col col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <MediaInputBox
              chrome="bare"
              inputType="image"
              icon="image"
              :label="t('latentLab.crossmodal.mmaudio.imageUpload')"
              :allow-sketch="true"
              value=""
              :initial-image="imagePreview"
              @image-uploaded="handleImageUpload"
              @image-removed="clearImage"
              @copy="copyImage"
              @paste="pasteImage"
              @clear="clearImage"
            />

            <PromptExamples
              :items="mmaudioExamples"
              :current="mmaudio.prompt"
              @pick="applyMMAudioExample"
            />
            <MediaInputBox
              chrome="bare"
              icon="lightbulb"
              :label="t('latentLab.crossmodal.mmaudio.prompt')"
              :placeholder="t('mediaInput.freePromptPlaceholder')"
              :value="mmaudio.prompt"
              @update:value="mmaudio.prompt = $event"
              :rows="2"
              :isEmpty="!mmaudio.prompt"
              :isFilled="!!mmaudio.prompt"
              :is-loading="readingPicture"
              :disabled="readingPicture"
              @copy="copyMMAudioPrompt"
              @paste="pasteMMAudioPrompt"
              @clear="clearMMAudioPrompt"
              :show-preset-button="true"
              :preset-busy="enriching"
              @open-preset-selector="showPresetOverlay = true"
              @image-uploaded="handlePicture"
              @image-removed="dropPicture"
            />
            <!-- The reading of a dropped picture, where it did not come back. -->
            <p v-if="readingFailedKey" class="lab-prep-err">{{ t(readingFailedKey) }}</p>
            <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>

            <!-- The four numbers of a run. Their ranges are the ones the fields
                 had on the Crossmodal stage. -->
            <details class="advanced-settings" :open="settingsOpen" @toggle="onSettingsToggle">
              <summary>{{ t('latentLab.crossmodal.mmaudio.advancedLabel') }}</summary>
              <div class="settings-grid">
                <label>
                  {{ t('latentLab.crossmodal.mmaudio.duration') }}
                  <input v-model.number="mmaudio.duration" type="number" min="1" max="8" step="1" class="setting-input setting-small" />
                </label>
                <label>
                  {{ t('latentLab.crossmodal.mmaudio.cfg') }}
                  <input v-model.number="mmaudio.cfg" type="number" min="1" max="15" step="0.5" class="setting-input setting-small" />
                </label>
                <label>
                  {{ t('latentLab.crossmodal.mmaudio.steps') }}
                  <input v-model.number="mmaudio.steps" type="number" min="10" max="50" step="5" class="setting-input setting-small" />
                </label>
                <SeedControl v-model:seed="mmaudio.seed" v-model:random="randomSeed" />
              </div>
            </details>

            <aside class="lab-note">
              <h3>{{ t('latentLab.crossmodal.tabs.mmaudio.label') }}</h3>
              <p
                v-for="(para, i) in t('latentLab.crossmodal.mmaudio.noteBody').split('\n\n')"
                :key="i"
              >{{ para }}</p>
              <LabReferences
                flat
                :title="t('latentLab.crossmodal.mmaudio.referencesTitle')"
                :items="REFERENCES"
              />
            </aside>
          </section>

          <!-- What came out: one row per press, NEWEST AT THE TOP, so the run
               just made is always in sight, in the run rows of the lab
               (assets/flow-stage.css). The head says once what the run was
               made with; under it stand the picture it was given, or the
               empty place of one, and the sound. A run that brought nothing
               back keeps its row and says why in the cell. Before the first
               press the row stands there dimmed, with the settings it would
               run with. The rows scroll in their own box, so this side is a
               plain side of `.lab-work` and not `.lab-plot`, which holds a
               raster that stands whole on the screen. -->
          <section>
            <div class="lab-runrows">
              <div
                v-for="row in displayRows"
                :key="row.id"
                class="lab-runrow"
                :class="{ 'is-preview': row.preview }"
              >
                <div class="lab-runrow-head">
                  <span v-if="row.prompt" class="lab-runrow-prompt">{{ row.prompt }}</span>
                  <span class="lab-runrow-meta">
                    {{ t('latentLab.crossmodal.mmaudio.duration') }}: <b>{{ row.duration }}</b>
                  </span>
                  <span class="lab-runrow-meta">
                    {{ t('latentLab.crossmodal.mmaudio.cfg') }}: <b>{{ row.cfg }}</b>
                  </span>
                  <span class="lab-runrow-meta">
                    {{ t('latentLab.crossmodal.mmaudio.steps') }}: <b>{{ row.steps }}</b>
                  </span>
                  <span class="lab-runrow-meta">
                    {{ t('latentLab.crossmodal.seed') }}: <b>{{ row.seed === null ? '—' : row.seed }}</b>
                  </span>
                </div>
                <div class="lab-runrow-media">
                  <div class="lab-runrow-pic" :class="{ none: !row.picture }">
                    <img v-if="row.picture" :src="row.picture" alt="" />
                  </div>
                  <div class="lab-runrow-sound">
                    <MediaGridCell
                      strip
                      :url="row.url"
                      media-type="audio"
                      :run-id="row.runId"
                      :prompt="row.prompt"
                      :config-id="TAB"
                      :created-at="row.madeAt"
                      :duration-ms="row.ms ?? 0"
                      :facts="row.facts"
                      :note="row.note"
                      :is-favorited="!!row.runId && favoritesStore.isFavorited(row.runId)"
                      @toggle-favorite="toggleFavorite(row)"
                      @download="downloadRow(row)"
                    />
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>

    <InterceptionPresetOverlay
      :visible="showPresetOverlay"
      single
      @close="showPresetOverlay = false"
      @preset-selected="handlePresetSelected"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onBeforeUnmount, toRef } from 'vue'
import { usePictureTemplate } from '@/composables/usePictureTemplate'
import { useI18n } from 'vue-i18n'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import {
  apiPost,
  base64ToDataUrl,
  generationErrorFor as labErrorText,
  interceptPrompt,
  perspectiveFailureText,
  refusalKeyOf,
  reportRefusal,
} from '@/composables/useLabRun'
import { downloadMedia } from '@/lib/downloadMedia'
import MediaInputBox from '@/components/MediaInputBox.vue'
import MediaGridCell from '@/components/MediaGridCell.vue'
import ColumnFold from '@/components/ColumnFold.vue'
import ShellRun from '@/components/ShellRun.vue'
import SeedControl from '@/components/SeedControl.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import { useDetailsState } from '@/composables/useDetailsState'
import { useFavoritesStore } from '@/stores/favorites'
import { useLabAuthStore } from '@/stores/labAuth'
import PromptExamples from '@/components/PromptExamples.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import { useDeviceId } from '@/composables/useDeviceId'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useCrossmodalPicture } from '@/composables/useCrossmodalPicture'
import { useLatentLabRecorder, type InstrumentRun } from '@/composables/useLatentLabRecorder'
import { useSeedAutomatic, STANDARD_SEED } from '@/composables/useSeedAutomatic'
import { useInstrumentRuns } from '@/composables/useInstrumentRuns'
import type { DrawerItem } from '@/components/canvas/OutputDrawer.vue'

const { t } = useI18n()

/**
 * The tool key stays `crossmodal_lab` after the split: the sitting ids live in
 * sessionStorage under `ai4artsed:lab-sittings:crossmodal_lab`, so a key of
 * this instrument's own would orphan every run a workshop has already made.
 * Which runs belong HERE is said by the run's own `tab`, the way it always was.
 */
const TOOL = 'crossmodal_lab'
const TAB = 'mmaudio'

/**
 * The model this surface runs, as its makers published it, and one of the
 * video sets it was trained on.
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'Cheng et al. (2025)',
    title: '"MMAudio: Taming Multimodal Joint Training for High-Quality Video-to-Audio Synthesis"',
    venue: 'CVPR 2025',
    doi: 'https://doi.org/10.48550/arXiv.2412.15322',
  },
  {
    authors: 'Chen et al. (2020)',
    title: '"VGGSound: A Large-scale Audio-Visual Dataset"',
    venue: 'ICASSP 2020',
    doi: 'https://arxiv.org/abs/2004.14368',
  },
]

const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const { imagePath, imagePreview, setPicture, clearPicture } = useCrossmodalPicture()
const { record: labRecord } = useLatentLabRecorder(TOOL)

/**
 * The reasons a run did not come back, in the reader's language. A refusal of
 * the platform's checks is said as one, and goes to the safety window.
 */
function generationErrorFor(failure: unknown): string {
  return reportRefusal(failure) ? t(refusalKeyOf(failure)) : labErrorText(t, failure)
}

const isRunning = ref(false)
/** The name the surface of yesterday uses; the state is one ref. */
const generating = computed(() => isRunning.value)
/** A run needs a prompt or a picture, and one at a time. */
const canRun = computed(() => (!!mmaudio.prompt || !!imagePath.value) && !generating.value)

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
const { isOpen: settingsOpen, onToggle: onSettingsToggle } = useDetailsState('ll_mmaudio_settings')

// ---------------------------------------------------------------------------
// The perspective in the field's corner — the platform's mandatory pair with a
// written field (registry, Rule #13; test_element_structure_policy.py, R3).
// Wired on 2026-10-10 (finding S-041 of the code review of 2026-10-10), when
// the policy began to see the three surfaces of the Crossmodal Lab.
// ---------------------------------------------------------------------------
const deviceId = useDeviceId()
const showPresetOverlay = ref(false)
// The perspective's failure stands under the field (`.lab-prep-err`), as on
// mean_images; the run's own error stands in its row's cell.
const perspectiveError = ref('')
const enriching = ref(false)

async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  const before = mmaudio.prompt
  if (!before.trim()) return
  enriching.value = true
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, before, deviceId)
    if ('written' in outcome) {
      // A perspective takes minutes; a run started meanwhile was sent the
      // wording that stood then.
      if (!generating.value) mmaudio.prompt = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (e) {
    perspectiveError.value = labErrorText(t, e)
  } finally {
    enriching.value = false
  }
}

/**
 * One press, as its row on the right: what the run went out with, read once at
 * the press (the fields stay open while it is out), and what came back.
 * The cell IS the run: its id carries the star and the back of the card.
 */
interface SoundRow {
  id: number
  preview?: boolean
  prompt: string
  duration: number
  cfg: number
  steps: number
  seed: number | null
  /** The picture the run was given, or '' for a run without one. */
  picture: string
  url: string
  /** Why the cell holds no sound: the run is out, or what it failed with. */
  note: string
  runId: string | null
  madeAt: number
  ms: number | null
  facts: string[]
}

const rows = ref<SoundRow[]>([])
let rowCounter = 0

// A participant's material goes when the participant does (stores/labAuth.ts
// puts the shared picture away on sign-out and on a change of course). The
// rows hold that picture again, with the prompts and the sounds made from it,
// and a workshop machine is handed on with this page still standing.
const labAuth = useLabAuthStore()
watch(() => [labAuth.user?.id ?? null, labAuth.activeCourseId], () => {
  rows.value = []
})

/** Before the first press: the row a press would make, from the fields as they stand. */
const displayRows = computed<SoundRow[]>(() => rows.value.length ? rows.value : [{
  id: 0,
  preview: true,
  prompt: mmaudio.prompt,
  duration: mmaudio.duration,
  cfg: mmaudio.cfg,
  steps: mmaudio.steps,
  seed: null,
  picture: imagePath.value ? imagePreview.value : '',
  url: '',
  note: '',
  runId: null,
  madeAt: 0,
  ms: null,
  facts: [],
}])

const favoritesStore = useFavoritesStore()

async function toggleFavorite(row: SoundRow): Promise<void> {
  if (!row.runId) return
  // The address the runs bar files the same run under (useInstrumentRuns
  // below), so one run is one favourite whichever star was pressed.
  await favoritesStore.toggleFavorite(row.runId, 'audio', deviceId, 'anonymous', 'latent-lab/mmaudio')
}

const mmaudio = reactive({
  prompt: '',
  duration: 8,
  cfg: 4.5,
  steps: 25,
  seed: STANDARD_SEED,
})
const randomSeed = ref(false)

/**
 * Everything a run goes out with except its seed, as one key: what the seed
 * automatic compares the next press with.
 */
function inputsKey(): string {
  return JSON.stringify([mmaudio.prompt, mmaudio.duration, mmaudio.cfg, mmaudio.steps,
    imagePath.value])
}
// null: this instrument keeps none of its fields, so the yardstick starts afresh with them.
const seedAutomatic = useSeedAutomatic(toRef(mmaudio, 'seed'), randomSeed, null)

const { addRun } = useInstrumentRuns(TOOL, cardFor, {
  shell: { sourceView: computed(() => 'latent-lab/mmaudio') },
  // Three instruments record into one strip, and a sound made here has nothing
  // to be compared with a sound made in another of them. Each card says which
  // one it came out of (`cardFor` puts the tab in `configId`).
  shownWhen: card => card.configId === TAB,
})

function cardFor(run: InstrumentRun): DrawerItem | null {
  const params = (run.parameters || {}) as Record<string, unknown>
  const results = (run.results || {}) as Record<string, unknown>
  const sound = (run.outputs || []).find(o => o.type === 'audio')
  if (!sound?.url) return null
  const head = (text: unknown) => String(text ?? '').trim().split(/\s+/).slice(0, 4).join(' ')
  return {
    id: run.run_id,
    label: head(params.prompt),
    sub: `${String(params.tab ?? '')} · ${params.duration ?? ''}s`,
    meta: [
      `seed: ${results.seed ?? params.seed ?? ''}`,
      `cfg: ${params.cfg ?? ''}`,
      `steps: ${params.steps ?? ''}`,
    ],
    prompt: String(params.prompt ?? ''),
    configId: String(params.tab ?? ''),
    sourceView: 'latent-lab/mmaudio',
    createdAt: Date.parse(run.timestamp || '') || Date.now(),
    modelMeta: null,
    runId: run.run_id,
    output: { url: sound.url, media_type: 'audio' },
    error: null,
  }
}

/** A take just made, laid as a card through the same reader that reads one back. */
async function keepTake(parameters: Record<string, unknown>, results: Record<string, unknown>, wavBase64: string): Promise<string | null> {
  const recorded = await labRecord({
    parameters,
    results,
    outputs: [{ type: 'audio', format: 'wav', dataBase64: wavBase64 }],
  })
  if (!recorded) return null
  addRun(cardFor({
    run_id: recorded,
    tool: TOOL,
    timestamp: new Date().toISOString(),
    parameters,
    results,
    outputs: [{ type: 'audio', format: 'wav', url: `/api/media/audio/${recorded}`, meta: {} }],
  }))
  return recorded
}


/**
 * A picture dropped onto the prompt field is read as a description, and the
 * reading then stands in the field (`composables/usePictureTemplate.ts`). This
 * way in belongs on every FREE prompt field of the lab, and the hint over the
 * field names it. The picture field ABOVE this one is a different
 * thing and keeps its own meaning: there a picture stays a picture.
 */
const {
  reading: readingPicture,
  readingFailedKey,
  handlePicture,
  dropPicture,
} = usePictureTemplate(toRef(mmaudio, 'prompt'))

const mmaudioExamples = computed(() => [
  {
    id: 'campfire',
    label: t('latentLab.crossmodal.mmaudio.promptExamples.campfire'),
    fill: [t('latentLab.crossmodal.mmaudio.promptExamples.campfire')],
  },
])

function applyMMAudioExample(item: { fill: string[] }) {
  mmaudio.prompt = item.fill[0] ?? ''
}

function handleImageUpload(data: { image_path: string; preview_url: string }) {
  setPicture(data)
}

function copyImage() { copyToClipboard(imagePreview.value) }
function pasteImage() {
  const content = pasteFromClipboard()
  if (content) imagePreview.value = content
}
function clearImage() { clearPicture() }

function copyMMAudioPrompt() { copyToClipboard(mmaudio.prompt) }
function pasteMMAudioPrompt() { mmaudio.prompt = pasteFromClipboard() }
function clearMMAudioPrompt() { mmaudio.prompt = '' }

async function runMMAudio() {
  if (!canRun.value) return
  isRunning.value = true
  // The seed automatic (composables/useSeedAutomatic): the same seed when
  // something changed since the newest sound was made, a new one when nothing
  // did, the field's when it was typed. The seed goes into the field.
  const runInputs = inputsKey()
  const runSeed = seedAutomatic.seedForRun(runInputs)
  const id = ++rowCounter
  rows.value.unshift({
    id,
    prompt: mmaudio.prompt,
    duration: mmaudio.duration,
    cfg: mmaudio.cfg,
    steps: mmaudio.steps,
    seed: runSeed,
    picture: imagePath.value ? imagePreview.value : '',
    url: '',
    note: t('latentLab.crossmodal.generating'),
    runId: null,
    madeAt: 0,
    ms: null,
    facts: [],
  })
  // Written through the row the list holds, never through a local object: a
  // write to the raw object reaches the surface only when something else
  // redraws it (registry, `Textzelle und Zeilenkopf eines Laufrasters`).
  const row = () => rows.value.find(r => r.id === id)
  const sent = rows.value[0]!
  try {
    const body: Record<string, unknown> = {
      prompt: sent.prompt,
      duration_seconds: sent.duration,
      cfg_strength: sent.cfg,
      num_steps: sent.steps,
      seed: runSeed,
    }
    if (imagePath.value) {
      body.image_path = imagePath.value
    }

    const result = await apiPost('/api/cross_aesthetic/mmaudio', body)
    const r = row()
    if (result.success) {
      // This sound is now the one the next press is compared with.
      seedAutomatic.arrived(runInputs, result.seed ?? runSeed)
      if (r) {
        r.url = base64ToDataUrl(result.audio_base64, 'audio/wav')
        r.seed = result.seed ?? runSeed
        r.ms = result.generation_time_ms ?? null
        r.madeAt = Date.now()
        r.note = ''
        r.facts = [
          `${t('latentLab.crossmodal.seed')}: ${r.seed}`,
          `${t('latentLab.crossmodal.mmaudio.duration')}: ${r.duration}`,
          `${t('latentLab.crossmodal.mmaudio.cfg')}: ${r.cfg}`,
          `${t('latentLab.crossmodal.mmaudio.steps')}: ${r.steps}`,
          ...(r.ms ? [`${t('latentLab.crossmodal.generationTime')}: ${r.ms}ms`] : []),
        ]
      }

      void keepTake(
        { tab: TAB, prompt: sent.prompt, duration: sent.duration, cfg: sent.cfg,
          steps: sent.steps, seed: runSeed, has_image: !!body.image_path },
        { seed: result.seed, generation_time_ms: result.generation_time_ms },
        result.audio_base64,
      ).then(recorded => {
        const rr = row()
        if (!rr || !recorded) return
        rr.runId = recorded
        // Kept, the sound is heard from the server's copy: the base64 copy of
        // every take would otherwise stay in the page for as long as it stands,
        // and the back of the card reads the AI-origin disclosure only from a
        // served file (composables/useMediaDisclosure.ts).
        rr.url = `/api/media/audio/${recorded}`
      })
    } else if (r) {
      r.note = generationErrorFor(result.error || 'MMAudio generation failed')
    }
  } catch (e) {
    const r = row()
    if (r) r.note = generationErrorFor(e)
  } finally {
    isRunning.value = false
  }
}

function downloadRow(row: SoundRow) {
  if (!row.url) return
  void downloadMedia(row.url, `mmaudio_${row.seed ?? 0}.wav`)
}

const pageContextStore = usePageContextStore()

// The catalogue (platform_items.json) is keyed to this, and carries what this
// place says about its own technology.
const pageContext = computed<PageContext>(() => ({
  activeViewType: `crossmodal_lab.${TAB}`,
  pageContent: {},
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onBeforeUnmount(() => {
  // Before, not after: the instrument taking over writes the page context in
  // its own setup, and setup runs ahead of a post-flush onUnmounted.
  pageContextStore.clearContext()
})
</script>

<style scoped>
/* The page skeleton, the klappe, the run rows and what a row of sound holds
   (the picture of the run beside the sound) are shared and stand in
   assets/flow-stage.css. */

/* Narrow: the two sides stack, and the page scrolls in itself. Measured on the
   page, not the window, as in views/cover_band.vue: the instrument rail takes
   240 to 340 px of the window while it is open. At 640 px of page the
   preparing column is about 197 px wide. */
.lab-page { container: mmaudio / inline-size; }
@container mmaudio (max-width: 640px) {
  .lab-main { overflow-y: auto; }
  .lab-stage { flex: 0 0 auto; }
  .lab-work, .lab-work.folded { grid-template-columns: 1fr; grid-template-rows: auto; row-gap: 16px; }
}
</style>
