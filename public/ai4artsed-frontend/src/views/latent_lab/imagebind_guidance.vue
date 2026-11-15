<!--
  ImageBind Guidance — a picture and a text are put into ONE embedding space
  (Girdhar et al. 2023), and the sound is pulled towards the picture while it is
  being made. What comes back carries the cosine between the finished clip and
  the picture that guided it.

  Split out of views/latent_lab/crossmodal_lab.vue on 2026-09-05, where it stood
  with the Latent Audio Synth and MMAudio in one file. Until 2026-11-02 the
  surface was the one that file carried at a50054bc, one thing under another,
  in its own scoped style and from 2026-10-10 on the Crossmodal stage
  (assets/crossmodal-stage.css); a two-column frame was put here on 2026-09-05
  and taken out the same day.

  Since 2026-11-02 it stands in the frame of the instruments as MMAudio does
  (views/latent_lab/mmaudio.vue): the trigger in the bar; in the preparing
  column what a first run costs, the picture, the prompt, the two axes this
  instrument IS (how hard the picture pulls, and over how many of the steps)
  open, and the other numbers in the klappe; on the right one row per press, newest on top (`.lab-runrows`,
  assets/flow-stage.css), each with the picture that guided it, the sound in the
  platform's cell and the cosine the run came back with.

  The picture is the one MMAudio works on as well
  (composables/useCrossmodalPicture.ts), which is what the two shared refs of
  the old single file did.
-->
<template>
  <div class="lab-page">
    <ShellRun
      :ready="canRun"
      :running="generating"
      :title="t('latentLab.crossmodal.generate')"
      @run="runGuidance"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <section class="cmp-column lab-prep lab-col col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <!-- What a first run costs, in the platform's one amber and at the
                 head of the column (registry, `.ef-warn`): it answers a
                 condition of the RUN rather than of one field, so it stands
                 where the column begins and is read before a press. -->
            <p class="ef-warn">{{ t('latentLab.crossmodal.guidance.firstRunNotice') }}</p>

            <MediaInputBox
              chrome="bare"
              inputType="image"
              icon="image"
              :label="t('latentLab.crossmodal.guidance.imageUpload')"
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
              :items="guidanceExamples"
              :current="guidance.prompt"
              @pick="applyGuidanceExample"
            />
            <MediaInputBox
              chrome="bare"
              icon="lightbulb"
              :label="t('latentLab.crossmodal.guidance.prompt')"
              :placeholder="t('mediaInput.freePromptPlaceholder')"
              :value="guidance.prompt"
              @update:value="guidance.prompt = $event"
              :rows="2"
              :isEmpty="!guidance.prompt"
              :isFilled="!!guidance.prompt"
              :is-loading="readingPicture"
              :disabled="readingPicture"
              @copy="copyGuidancePrompt"
              @paste="pasteGuidancePrompt"
              @clear="clearGuidancePrompt"
              :show-preset-button="true"
              :preset-busy="enriching"
              @open-preset-selector="showPresetOverlay = true"
              @image-uploaded="handlePicture"
              @image-removed="dropPicture"
            />
            <!-- The reading of a dropped picture, where it did not come back. -->
            <p v-if="readingFailedKey" class="lab-prep-err">{{ t(readingFailedKey) }}</p>
            <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>

            <!-- The two axes this instrument IS stand open, not in the klappe
                 (registry, `Wahl, die den Lauf bestimmt`): the name of the axis
                 with its value over the frame's bare axis (`.lab-range`,
                 assets/flow-stage.css). -->
            <label class="lab-pick-label">
              {{ t('latentLab.crossmodal.guidance.lambda') }}
              <span class="ib-value">{{ guidance.lambda.toFixed(1) }}</span>
            </label>
            <input
              v-model.number="guidance.lambda"
              type="range"
              class="lab-range ib-range"
              min="0"
              max="10"
              step="0.1"
              :aria-label="t('latentLab.crossmodal.guidance.lambda')"
            />

            <label class="lab-pick-label">
              {{ t('latentLab.crossmodal.guidance.warmupSteps') }}
              <span class="ib-value">{{ guidance.warmupSteps }}</span>
            </label>
            <input
              v-model.number="guidance.warmupSteps"
              type="range"
              class="lab-range ib-range"
              min="1"
              :max="guidance.totalSteps"
              step="1"
              :aria-label="t('latentLab.crossmodal.guidance.warmupSteps')"
            />

            <!-- The other numbers of a run. Their ranges are the ones the fields
                 had on the Crossmodal stage. -->
            <details class="advanced-settings" :open="settingsOpen" @toggle="onSettingsToggle">
              <summary>{{ t('latentLab.crossmodal.guidance.advancedLabel') }}</summary>
              <div class="settings-grid">
                <label>
                  {{ t('latentLab.crossmodal.guidance.totalSteps') }}
                  <input v-model.number="guidance.totalSteps" type="number" min="4" max="20" step="1" class="setting-input setting-small" />
                </label>
                <label>
                  {{ t('latentLab.crossmodal.guidance.duration') }}
                  <input v-model.number="guidance.duration" type="number" min="1" max="30" step="1" class="setting-input setting-small" />
                </label>
                <label>
                  {{ t('latentLab.crossmodal.guidance.cfg') }}
                  <input v-model.number="guidance.cfg" type="number" min="0.5" max="3" step="0.1" class="setting-input setting-small" />
                </label>
                <SeedControl v-model:seed="guidance.seed" v-model:random="randomSeed" />
              </div>
            </details>

            <aside class="lab-note">
              <h3>{{ t('latentLab.crossmodal.tabs.guidance.label') }}</h3>
              <p
                v-for="(para, i) in t('latentLab.crossmodal.guidance.noteBody').split('\n\n')"
                :key="i"
              >{{ para }}</p>
              <LabReferences
                flat
                :title="t('latentLab.crossmodal.guidance.referencesTitle')"
                :items="GUIDANCE_REFERENCES"
              />
            </aside>
          </section>

          <!-- What came out: one row per press, NEWEST AT THE TOP, in the run
               rows of the lab (assets/flow-stage.css), as on MMAudio. The head
               says once what the run was made with; under it stand the picture
               that guided it, the sound, and the cosine between the two. A run
               that brought nothing back keeps its row and says why in the
               cell. Before the first press the row stands there dimmed, with
               the settings it would run with. The rows scroll in their own box,
               so this side is a plain side of `.lab-work` and not `.lab-plot`. -->
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
                    {{ t('latentLab.crossmodal.guidance.lambda') }}: <b>{{ row.lambda.toFixed(1) }}</b>
                  </span>
                  <span class="lab-runrow-meta">
                    {{ t('latentLab.crossmodal.guidance.warmupSteps') }}: <b>{{ row.warmup }} / {{ row.steps }}</b>
                  </span>
                  <span class="lab-runrow-meta">
                    {{ t('latentLab.crossmodal.guidance.duration') }}: <b>{{ row.duration }}</b>
                  </span>
                  <span class="lab-runrow-meta">
                    {{ t('latentLab.crossmodal.guidance.cfg') }}: <b>{{ row.cfg }}</b>
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
                    <!-- What this instrument measures stands on the row, not
                         only on the card's back. -->
                    <p v-if="row.cosine !== null" class="lab-runrow-meta ib-reading">
                      {{ t('latentLab.crossmodal.guidance.cosineSimilarity') }}: <b>{{ row.cosine.toFixed(4) }}</b>
                    </p>
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
import PromptExamples from '@/components/PromptExamples.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import { useDeviceId } from '@/composables/useDeviceId'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import { useDetailsState } from '@/composables/useDetailsState'
import { useFavoritesStore } from '@/stores/favorites'
import { useLabAuthStore } from '@/stores/labAuth'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useCrossmodalPicture } from '@/composables/useCrossmodalPicture'
import { useLatentLabRecorder, type InstrumentRun } from '@/composables/useLatentLabRecorder'
import { useSeedAutomatic, STANDARD_SEED } from '@/composables/useSeedAutomatic'
import { useInstrumentRuns } from '@/composables/useInstrumentRuns'
import type { DrawerItem } from '@/components/canvas/OutputDrawer.vue'

const { t } = useI18n()

/**
 * The shared space this instrument reads from is ImageBind's; classifier
 * guidance and its use with networks trained for other purposes are what the
 * guided steps do, and Stable Audio 3 is the model they steer.
 */
const GUIDANCE_REFERENCES: LabReference[] = [
  {
    authors: 'Girdhar et al. (2023)',
    title: '"ImageBind: One Embedding Space To Bind Them All"',
    venue: 'CVPR 2023',
    doi: 'https://doi.org/10.48550/arXiv.2305.05665',
  },
  {
    authors: 'Dhariwal & Nichol (2021)',
    title: '"Diffusion Models Beat GANs on Image Synthesis"',
    venue: 'NeurIPS 2021',
    doi: 'https://arxiv.org/abs/2105.05233',
  },
  {
    authors: 'Bansal et al. (2024)',
    title: '"Universal Guidance for Diffusion Models"',
    venue: 'ICLR 2024',
    doi: 'https://arxiv.org/abs/2302.07121',
  },
  {
    authors: 'Stability AI (2026)',
    title: '"Stable Audio 3.0"',
    venue: '2026, model release',
    doi: 'https://stability.ai/stable-audio',
  },
]

/**
 * The tool key stays `crossmodal_lab` after the split: the sitting ids live in
 * sessionStorage under `ai4artsed:lab-sittings:crossmodal_lab`, so a key of
 * this instrument's own would orphan every run a workshop has already made.
 * Which runs belong HERE is said by the run's own `tab`, the way it always was.
 */
const TOOL = 'crossmodal_lab'
const TAB = 'guidance'
const SOURCE_VIEW = 'latent-lab/imagebind-guidance'

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
/** The picture is what steers here, so a run needs one; and one at a time. */
const canRun = computed(() => !!imagePath.value && !generating.value)

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
const { isOpen: settingsOpen, onToggle: onSettingsToggle } = useDetailsState('ll_guidance_settings')

// ---------------------------------------------------------------------------
// The perspective in the field's corner — the platform's mandatory pair with a
// written field (registry, Rule #13; test_element_structure_policy.py, R3).
// Wired on 2026-10-10 (finding S-041 of the code review of 2026-10-10), when the policy began to see the three surfaces
// of the Crossmodal Lab.
// ---------------------------------------------------------------------------
const deviceId = useDeviceId()
const showPresetOverlay = ref(false)
// The perspective's failure stands under the field (`.lab-prep-err`), as on
// mean_images; the run's own error stands in its row's cell.
const perspectiveError = ref('')
const enriching = ref(false)

async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  const before = guidance.prompt
  if (!before.trim()) return
  enriching.value = true
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, before, deviceId)
    if ('written' in outcome) {
      // A perspective takes minutes; a run started meanwhile was sent the
      // wording that stood then.
      if (!generating.value) guidance.prompt = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (e) {
    perspectiveError.value = labErrorText(t, e)
  } finally {
    enriching.value = false
  }
}

const guidance = reactive({
  prompt: '',
  // Measured on the finished clip (ImageBind cosine against the guiding image):
  // 0.16 unguided, 0.21 at lambda 1, 0.23 at lambda 5, falling again from 20 on.
  // Below 1 the slider does nothing, so the old default of 0.1 guided nothing.
  lambda: 5,
  // The sampler mixes fresh noise into every step, so guidance on the first steps
  // alone is overwritten before the clip is finished: guide all of them.
  warmupSteps: 8,
  totalSteps: 8,
  duration: 10,
  cfg: 1.0,
  seed: STANDARD_SEED,
})
const randomSeed = ref(false)

/**
 * One press, as its row on the right: what the run went out with, read once at
 * the press (the fields stay open while it is out), and what came back. The
 * cell IS the run: its id carries the star and the back of the card.
 */
interface SoundRow {
  id: number
  preview?: boolean
  prompt: string
  lambda: number
  warmup: number
  steps: number
  duration: number
  cfg: number
  seed: number | null
  /** The picture that guided the run. */
  picture: string
  url: string
  /** Why the cell holds no sound: the run is out, or what it failed with. */
  note: string
  runId: string | null
  madeAt: number
  ms: number | null
  /** The cosine between the finished clip and the picture, as the run reports it. */
  cosine: number | null
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
  prompt: guidance.prompt,
  lambda: guidance.lambda,
  warmup: guidance.warmupSteps,
  steps: guidance.totalSteps,
  duration: guidance.duration,
  cfg: guidance.cfg,
  seed: null,
  picture: imagePath.value ? imagePreview.value : '',
  url: '',
  note: '',
  runId: null,
  madeAt: 0,
  ms: null,
  cosine: null,
  facts: [],
}])

const favoritesStore = useFavoritesStore()

async function toggleFavorite(row: SoundRow): Promise<void> {
  if (!row.runId) return
  // The address the runs bar files the same run under (useInstrumentRuns
  // below), so one run is one favourite whichever star was pressed.
  await favoritesStore.toggleFavorite(row.runId, 'audio', deviceId, 'anonymous', SOURCE_VIEW)
}

/**
 * Everything a run goes out with except its seed, as one key: what the seed
 * automatic compares the next press with.
 */
function inputsKey(): string {
  return JSON.stringify([guidance.prompt, guidance.lambda, guidance.warmupSteps,
    guidance.totalSteps, guidance.duration, guidance.cfg, imagePath.value])
}
// null: this instrument keeps none of its fields, so the yardstick starts afresh with them.
const seedAutomatic = useSeedAutomatic(toRef(guidance, 'seed'), randomSeed, null)

watch(() => guidance.totalSteps, (steps) => {
  if (guidance.warmupSteps > steps) guidance.warmupSteps = steps
})

const { addRun } = useInstrumentRuns(TOOL, cardFor, {
  shell: { sourceView: computed(() => SOURCE_VIEW) },
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
  const cosine = typeof results.cosine_similarity === 'number' ? results.cosine_similarity.toFixed(4) : ''
  return {
    id: run.run_id,
    label: head(params.prompt),
    // The strip shows this instrument's cards only (`shownWhen`), so the tab
    // would tell none of them apart; the card names its numbers as the
    // surface names them.
    sub: `${params.duration ?? ''}s`,
    meta: [
      `${t('latentLab.crossmodal.seed')}: ${results.seed ?? params.seed ?? ''}`,
      `${t('latentLab.crossmodal.guidance.lambda')}: ${params.lambda ?? ''}`,
      ...(cosine ? [`${t('latentLab.crossmodal.guidance.cosineSimilarity')}: ${cosine}`] : []),
    ],
    prompt: String(params.prompt ?? ''),
    configId: String(params.tab ?? ''),
    sourceView: SOURCE_VIEW,
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
} = usePictureTemplate(toRef(guidance, 'prompt'))

const guidanceExamples = computed(() => [
  {
    id: 'ambient',
    label: t('latentLab.crossmodal.guidance.promptExamples.ambient'),
    fill: [t('latentLab.crossmodal.guidance.promptExamples.ambient')],
  },
])

function applyGuidanceExample(item: { fill: string[] }) {
  guidance.prompt = item.fill[0] ?? ''
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

function copyGuidancePrompt() { copyToClipboard(guidance.prompt) }
function pasteGuidancePrompt() { guidance.prompt = pasteFromClipboard() }
function clearGuidancePrompt() { guidance.prompt = '' }

async function runGuidance() {
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
    prompt: guidance.prompt,
    lambda: guidance.lambda,
    warmup: guidance.warmupSteps,
    steps: guidance.totalSteps,
    duration: guidance.duration,
    cfg: guidance.cfg,
    seed: runSeed,
    picture: imagePreview.value,
    url: '',
    note: t('latentLab.crossmodal.generating'),
    runId: null,
    madeAt: 0,
    ms: null,
    cosine: null,
    facts: [],
  })
  // Written through the row the list holds, never through a local object: a
  // write to the raw object reaches the surface only when something else
  // redraws it (registry, `Textzelle und Zeilenkopf eines Laufrasters`).
  const row = () => rows.value.find(r => r.id === id)
  const sent = rows.value[0]!
  try {
    const result = await apiPost('/api/cross_aesthetic/image_guided_audio', {
      image_path: imagePath.value,
      prompt: sent.prompt,
      lambda_guidance: sent.lambda,
      warmup_steps: sent.warmup,
      total_steps: sent.steps,
      duration_seconds: sent.duration,
      cfg_scale: sent.cfg,
      seed: runSeed,
    })
    const r = row()
    if (result.success) {
      // This sound is now the one the next press is compared with.
      seedAutomatic.arrived(runInputs, result.seed ?? runSeed)
      if (r) {
        r.url = base64ToDataUrl(result.audio_base64, 'audio/wav')
        r.seed = result.seed ?? runSeed
        r.ms = result.generation_time_ms ?? null
        r.cosine = result.cosine_similarity ?? null
        r.madeAt = Date.now()
        r.note = ''
        r.facts = [
          `${t('latentLab.crossmodal.seed')}: ${r.seed}`,
          `${t('latentLab.crossmodal.guidance.lambda')}: ${r.lambda.toFixed(1)}`,
          `${t('latentLab.crossmodal.guidance.warmupSteps')}: ${r.warmup} / ${r.steps}`,
          `${t('latentLab.crossmodal.guidance.duration')}: ${r.duration}`,
          `${t('latentLab.crossmodal.guidance.cfg')}: ${r.cfg}`,
          ...(r.cosine !== null ? [`${t('latentLab.crossmodal.guidance.cosineSimilarity')}: ${r.cosine.toFixed(4)}`] : []),
          ...(r.ms ? [`${t('latentLab.crossmodal.generationTime')}: ${r.ms}ms`] : []),
        ]
      }

      void keepTake(
        { tab: TAB, prompt: sent.prompt,
          lambda: sent.lambda, warmup_steps: sent.warmup,
          total_steps: sent.steps, duration: sent.duration,
          cfg: sent.cfg, seed: runSeed, has_image: true },
        { seed: result.seed, generation_time_ms: result.generation_time_ms,
          cosine_similarity: result.cosine_similarity },
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
      r.note = generationErrorFor(result.error || 'Guided generation failed')
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
  void downloadMedia(row.url, `imagebind_${row.seed ?? 0}.wav`)
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
/* The page skeleton, the klappe, the bare axis, the amber line, the run rows
   and what a row of sound holds are shared and stand in
   assets/flow-stage.css. */

/* The cosine under the sound: the size and tone of the row's head, which the
   class it shares with the head (`.lab-runrow-meta`) does not carry by itself. */
.ib-reading {
  margin: 4px 0 0;
  font-size: var(--flow-fs-sub);
  color: rgba(255, 255, 255, 0.5);
}

/* The value beside the name of an axis. */
.ib-value {
  margin-inline-start: 6px;
  color: rgba(255, 255, 255, 0.75);
  font-variant-numeric: tabular-nums;
  direction: ltr;
  unicode-bidi: isolate;
}

/* The bare axis sets no width: across the column. */
.ib-range {
  width: 100%;
  margin: 0;
}

/* Narrow: the two sides stack, and the page scrolls in itself. Measured on the
   page, not the window, as in views/cover_band.vue: the instrument rail takes
   240 to 340 px of the window while it is open. At 640 px of page the
   preparing column is about 197 px wide. */
.lab-page { container: imagebind / inline-size; }
@container imagebind (max-width: 640px) {
  .lab-main { overflow-y: auto; }
  .lab-stage { flex: 0 0 auto; }
  .lab-work, .lab-work.folded { grid-template-columns: 1fr; grid-template-rows: auto; row-gap: 16px; }
}
</style>
