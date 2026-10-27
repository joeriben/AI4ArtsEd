<template>
  <div class="cmp-page">
    <ShellRun
      :ready="canGenerate && !isGenerating"
      :running="isGenerating"
      :title="t('compare.generateAll')"
      :label="t('latentLab.runLine.image')"
      :count="done"
      :total="MODELS.length"
      @run="startComparison"
    />

    <!-- The preparing column at the left, the models beside it. Page frame,
         column box, head row, name, queue badge and starting number are the
         platform's own (`assets/compare-stage.css`); the ORDER of the columns
         is this surface's, as it is on every comparison surface. -->
    <div class="cmp-stage cmp-work" :class="{ folded }">
      <section class="cmp-column cmp-ask col-fold-host" :class="{ folded }">
        <ColumnFold v-model:folded="folded" />

        <PromptExamples
          :items="promptExamples"
          :current="userPrompt"
          @pick="applyExample"
        />
        <MediaInputBox
          chrome="bare"
          :placeholder="t('mediaInput.freePromptPlaceholder')"
          v-model:value="userPrompt"
          input-type="text"
          :rows="4"
          :is-filled="!!userPrompt"
          :is-loading="readingPicture"
          :disabled="readingPicture"
          :show-preset-button="true"
          :preset-busy="enriching"
          @copy="copyPrompt"
          @paste="pastePrompt"
          @clear="clearPrompt"
          @open-preset-selector="showPresetOverlay = true"
          @image-uploaded="handlePicture"
          @image-removed="dropPicture"
        />
        <!-- The reading of a dropped picture, where it did not come back. -->
        <p v-if="readingFailedKey" class="lab-prep-err">{{ t(readingFailedKey) }}</p>
        <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>

        <!-- Two ready sets of three, each field carrying the models of its
             set — word for word what two hand-rolled buttons here carried until
             2026-09-07; they were a copy of `components/ChipSelect.vue` in the
             same green, without its card, its keyboard role and its per-option
             `disabled`. A set writes its three into the row below.

             It stands UNDER the prompt: the pages generally start with the
             prompt(s). -->
        <label class="lab-pick-label">{{ t('compare.setsLabel') }}</label>
        <ChipSelect
          :model-value="activePreset ?? ''"
          :options="presetChoices"
          :columns="2"
          :disabled="isGenerating"
          @update:model-value="v => applyPreset(v as PresetKey)"
        />

        <!-- The free choice: two to five models, in catalogue order. -->
        <label class="lab-pick-label">{{ t('compare.modelsLabel') }}</label>
        <ChipSelect
          :model-value="selected"
          :options="modelChoices"
          multiple
          :max="MAX_MODELS"
          :min-width="118"
          :disabled="isGenerating"
          @update:model-value="v => pickModels(v as string[])"
        />

        <p v-if="safetyError" class="cmp-err">{{ safetyError }}</p>

        <!-- What the makers themselves publish about the three models that are
             running. `.lab-note` at the foot of the preparing column with the
             titles under it, as on the Latent Lab instruments: running text
             in the explanation box, references only, titles with DOI under
             them. The text follows the chosen set, so it never describes
             models that are off screen. -->
        <aside v-if="notePreset" class="lab-note">
          <h3>{{ t('compare.tabs.model') }}</h3>
          <p
            v-for="(para, i) in t(`compare.modelNote.noteBody.${notePreset}`).split('\n\n')"
            :key="i"
          >{{ para }}</p>

          <LabReferences
            :title="t('compare.modelNote.referencesTitle')"
            :items="noteReferences"
            flat
          />
        </aside>

      </section>

      <!-- The starting number stands ABOVE the columns, as the surface's own
           description says it does: all three models are given the same noise,
           which is what leaves the model as the only difference between two
           pictures. -->
      <p v-if="currentSeed !== null" class="cmp-seed">
        {{ t('compare.seedLabel') }}: {{ currentSeed }}
      </p>

      <!-- What came out, and under it what already existed. ONE scroller for
           both, so a found picture keeps its place under the generated one. -->
      <div class="cmp-results">
        <div class="mc-models" :style="{ '--mc-cols': String(MODELS.length) }">
          <section
            v-for="(model, idx) in MODELS"
            :key="model.id"
            class="cmp-column mc-model"
          >
            <div class="cmp-column-head">
              <span class="cmp-name">{{ model.label }}</span>
              <span
                v-if="slots[idx] && slots[idx].queuePosition > 0 && !slotStreams[idx]?.isExecuting && !slots[idx]?.outputUrl"
                class="cmp-queue"
              >{{ slots[idx]?.queuePosition }}/{{ MODELS.length }}</span>
            </div>
            <!-- The platform's cell for a generated medium
                 (components/MediaGridCell.vue): the picture whole rather than
                 cropped, no header line of metadata, and everything one can do
                 with it on the back, behind a long press. -->
            <MediaGridCell
              :url="slots[idx]?.outputUrl ?? ''"
              media-type="image"
              :is-executing="slotStreams[idx]?.isExecuting ?? false"
              :progress="slotStreams[idx]?.generationProgress ?? 0"
              :preview-image="slotStreams[idx]?.previewImage ?? null"
              :run-id="slots[idx]?.runId ?? null"
              :prompt="slots[idx]?.prompt"
              :config-id="slots[idx]?.configId"
              :created-at="slots[idx]?.createdAt ?? undefined"
              :model-meta="slotStreams[idx]?.modelMeta ?? null"
              :duration-ms="slotStreams[idx]?.stage4DurationMs ?? 0"
              :facts="slotFacts(idx)"
              :is-favorited="slots[idx]?.isFavorited ?? false"
              :note="slotNote(slots[idx])"
              @toggle-favorite="slots[idx] && toggleSlotFavorite(slots[idx]!)"
              @forward="slots[idx] && forwardToPage(slots[idx]!)"
              @download="slots[idx] && downloadSlotImage(slots[idx]!)"
              @print="slots[idx] && printSlotImage(slots[idx]!)"
            />
          </section>
        </div>

        <!-- Pictures that already existed, for the same prompt -->
        <WikimediaFoundRow
          :state="foundState"
          :term="foundTerm"
          :images="foundImages"
        />
      </div>
    </div>

    <!-- Interception Preset Overlay -->
    <InterceptionPresetOverlay
      :visible="showPresetOverlay"
      single
      @close="showPresetOverlay = false"
      @preset-selected="handlePresetSelected"
    />
  </div>
</template>

<script setup lang="ts">
import ColumnFold from '@/components/ColumnFold.vue'
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { usePictureTemplate } from '@/composables/usePictureTemplate'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import { usePromptPresets } from '@/lib/promptPresets'
import MediaGridCell from '@/components/MediaGridCell.vue'
import ChipSelect from '@/components/ChipSelect.vue'
import { useModelAvailability } from '@/composables/useModelAvailability'
import ShellRun from '@/components/ShellRun.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import WikimediaFoundRow, { type FoundImage, type FoundState } from '@/components/WikimediaFoundRow.vue'
import { failureKey, safetyBlockKey, useGenerationStream, type GenerationResult } from '@/composables/useGenerationStream'
import { useFavoritesStore } from '@/stores/favorites'
import { useDeviceId } from '@/composables/useDeviceId'
import { postStreamedRun } from '@/services/directRun'
import { generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { useSafetyEventStore } from '@/stores/safetyEvent'
import { handOverImage } from '@/lib/handOverImage'
import { downloadMedia } from '@/lib/downloadMedia'
import { printMedia } from '@/lib/printMedia'
import { apiBase } from '@/services/labApi'

const { t } = useI18n()
const router = useRouter()
const favoritesStore = useFavoritesStore()
const deviceId = useDeviceId()

// --- Model presets ---
const PRESETS = {
  history: ['sd15', 'sdxl', 'sd35_large'],
  current: ['sd35_large', 'flux2', 'gemini_3_pro_image'],
} as const

type PresetKey = keyof typeof PRESETS

/**
 * Every model this surface offers, in the order the free row shows them — and
 * the order the columns then stand in, so a set keeps the order it is written
 * in above.
 *
 * Which models a surface offers is a didactic decision and not a catalogue
 * listing, so nothing is added here without one. Every entry but two stands
 * in a set above. CommonCanvas XL C is one exception, ordered after SDXL,
 * whose architecture it shares: it is
 * trained on ~70 million Creative Commons-licensed images and on nothing
 * else (CommonCatalog, arXiv:2310.16825), where the SDXL beside it is not.
 * Flux 3 Klein is the other, ordered after Flux 2: FLUX 3 Image Klein, Black
 * Forest Labs' model of 2026, offered since 2026-10-18 wherever Flux 2 stands
 * in the Latent Lab, with Flux 2 kept beside it.
 */
const CATALOGUE: { id: string; label: string }[] = [
  { id: 'sd15', label: 'SD 1.5 (2022)' },
  { id: 'sdxl', label: 'SDXL (2023)' },
  { id: 'commoncanvas_xl_c', label: 'CommonCanvas XL C (2023)' },
  { id: 'sd35_large', label: 'SD 3.5 Large (2024)' },
  { id: 'flux2', label: 'Flux 2' },
  { id: 'flux3', label: 'Flux 3 Klein' },
  { id: 'gemini_3_pro_image', label: 'Gemini 3 Pro (\u20AC)' },
]

/** How many columns the stage carries. */
const MAX_MODELS = 5
/** Two is what there is to compare. A field that would go below it stays on. */
const MIN_MODELS = 2


// --- State ---
// One press runs every model of the active preset — here that is ONE picture
// per model, and this is the single place on the platform where Gemini 3 Pro
// may stand in a preselection (it is only one picture each). Everywhere
// else it is chosen by hand,
// because everywhere else a press multiplies it — the census alone runs it once
// per context. Its name carries the € all the same.
//
// The surface opens with the HISTORICAL row, which is also the
// upper of the two fields: three years of one family, all of them weights this
// installation holds, and no cost on the first press.
//
// The SET is the shortcut, the row of models below the prompt is the general
// case: a field there toggles on its own, up to five, and the sets simply write
// their three into it: the chips at the top are presets, for a free
// selection below.
const selected = ref<string[]>([...PRESETS.history])

/**
 * A set as it can run here. Gemini 3 Pro stands in the current set and runs
 * through Mammouth AI; where that account holds no key or no
 * credit (docs/DEVELOPMENT_DECISIONS.md) it is switched off, and the set writes
 * the two it has left. A selection that holds it lets it go further down,
 * where the columns are.
 */
const { askWhenShown, accountMissing, accountParams, leaveOutAccountMissing } = useModelAvailability()
askWhenShown()
function presetModels(key: PresetKey): string[] {
  return PRESETS[key].filter(id => !accountMissing(id))
}

/** Which set the current selection IS, or none while it is the reader's own. */
const activePreset = computed<PresetKey | null>(() => {
  const now = [...selected.value].sort().join('|')
  for (const key of Object.keys(PRESETS) as PresetKey[]) {
    if (presetModels(key).sort().join('|') === now) return key
  }
  return null
})

/**
 * The set whose note stands under the fields. The note describes every model
 * of its set and stays away while one of them is switched off.
 */
const notePreset = computed<PresetKey | null>(() =>
  activePreset.value && PRESETS[activePreset.value].every(id => !accountMissing(id))
    ? activePreset.value
    : null,
)

function applyPreset(key: PresetKey) {
  selected.value = presetModels(key)
}

/**
 * A field goes on and off; below MIN_MODELS the last one stays on, because a
 * comparison of one is not one and an empty stage says nothing about why.
 */
function pickModels(next: string[]) {
  if (next.length < MIN_MODELS) return
  selected.value = next
}

/**
 * The publications the note rests on: for each model in a set, the paper that
 * describes it and, where the note quotes or reports from it, the model card.
 * ONLY TITLES THE NOTE ACTUALLY USES - a paper nobody read for this text stays
 * out (docs/ELEMENT_STRUCTURE_REGISTRY.md, LabReferences).
 */
const REFERENCES: Record<PresetKey, LabReference[]> = {
  history: [
    {
      authors: 'Rombach, R., Blattmann, A., Lorenz, D., Esser, P. & Ommer, B. (2022)',
      title: 'High-Resolution Image Synthesis with Latent Diffusion Models',
      venue: 'CVPR 2022',
      doi: 'https://doi.org/10.48550/arXiv.2112.10752',
    },
    {
      authors: 'Podell, D., English, Z., Lacey, K. et al. (2023)',
      title: 'SDXL: Improving Latent Diffusion Models for High-Resolution Image Synthesis',
      doi: 'https://doi.org/10.48550/arXiv.2307.01952',
    },
    {
      authors: 'Esser, P., Kulal, S., Blattmann, A. et al. (2024)',
      title: 'Scaling Rectified Flow Transformers for High-Resolution Image Synthesis',
      venue: 'ICML 2024',
      doi: 'https://doi.org/10.48550/arXiv.2403.03206',
    },
  ],
  current: [
    {
      authors: 'Stability AI (2024)',
      title: 'Stable Diffusion 3.5 Large, model card',
      venue: 'huggingface.co/stabilityai/stable-diffusion-3.5-large',
    },
    {
      authors: 'Stability AI (2024)',
      title: 'Introducing Stable Diffusion 3.5',
      venue: 'stability.ai, 22 October 2024',
    },
    {
      authors: 'Black Forest Labs (2025)',
      title: 'FLUX.2: Frontier Visual Intelligence',
      venue: 'bfl.ai, 25 November 2025',
    },
    {
      authors: 'Google (2025)',
      title: 'Introducing Nano Banana Pro',
      venue: 'blog.google, 20 November 2025',
    },
  ],
}
const noteReferences = computed(() => (notePreset.value ? REFERENCES[notePreset.value] : []))

/**
 * The two sets, as fields to pick from. A field carries the three models its set
 * stands for, which is what stood on the button it replaced. The sets have
 * names in here and those names are not written on screen — they never were.
 */
const presetChoices = computed(() =>
  (Object.keys(PRESETS) as PresetKey[]).map(key => ({
    value: key,
    label: t(`compare.presets.${key}`),
    // Which models a set holds stands in the row underneath as soon as it is
    // taken; until then it is here, so nobody has to press to find out.
    title: presetModels(key)
      .map(id => CATALOGUE.find(m => m.id === id)?.label)
      .filter(Boolean)
      .join(' · '),
  })),
)
const MODELS = computed(() => CATALOGUE.filter(m => selected.value.includes(m.id)))

/** The models to pick from, in catalogue order. One switched off for want of
 *  an account says so on hover, as it does in the Flow. */
const modelChoices = computed(() =>
  CATALOGUE.map(m => ({
    value: m.id,
    label: m.label,
    disabled: accountMissing(m.id),
    title: accountMissing(m.id) ? t('x2xFlow.accountMissing', accountParams(m.id)) : undefined,
  })),
)
const userPrompt = ref('')

/**
 * A picture dropped onto the prompt field is read as a description, and the
 * reading then stands in the field, where it can be worked on further
 * (`composables/usePictureTemplate.ts`). This way in belongs on
 * every FREE prompt field of the lab, and the hint over the field names it.
 */
const {
  reading: readingPicture,
  readingFailedKey,
  handlePicture,
  dropPicture,
} = usePictureTemplate(userPrompt)
const isGenerating = ref(false)
const currentSeed = ref<number | null>(null)
const comparisonContext = ref('')

/**
 * A press runs a comparison: a prompt, and at least MIN_MODELS models a run
 * sends. A model switched off for want of an account that stays selected for
 * its picture is not one of them.
 */
const canGenerate = computed(() =>
  !!userPrompt.value.trim() && MODELS.value.filter(m => !accountMissing(m.id)).length >= MIN_MODELS,
)

/** What Help is told stands here: one line per finished run, the model's own
 *  name and the run's id. Not the pictures — it opens one when somebody asks
 *  it to. */
const surfaceMedia = computed(() =>
  slots.value
    .filter(s => s.runId && s.outputUrl)
    .map(s => ({ runId: s.runId as string, label: s.label })),
)
const showPresetOverlay = ref(false)
// The perspective is at work on the prompt: the symbol that was pressed pulses.
const enriching = ref(false)
const safetyError = ref('')
const safetyStore = useSafetyEventStore()

interface ModelSlot {
  configId: string
  label: string
  outputUrl: string | null
  runId: string | null
  queuePosition: number
  /**
   * A refusal, as an i18n KEY. The service answers in German developer wording,
   * and a cell that showed it raw would put that in front of a visitor in every
   * language — `safetyBlockKey()` turns it into something the page can say.
   */
  blockedKey: string | null
  /** Nothing came back. A hole in a comparison must read as a hole, not as a cell still to come. */
  failed: boolean
  /**
   * WHY it stayed empty, as an i18n key. A queue that is full, a service that
   * is silent and a model that is absent ask three different things of
   * whoever is looking — and the last of them is what tells a deployment
   * fault from a platform fault (Rule #12).
   */
  failedKey: string | null
  /** The values the sentence of `failedKey` names (a provider, say). */
  failedParams?: Record<string, string>
  isFavorited: boolean
  /** What ran, held at the moment it ran — the field above stays writable. */
  prompt: string
  seed: number | null
  createdAt: number | null
}

/** What the cell says instead of a picture, in the reader's language. */
function slotNote(slot: ModelSlot | undefined): string {
  if (!slot) return ''
  if (slot.blockedKey) return t(slot.blockedKey)
  if (slot.failed) return t(slot.failedKey || 'generationError.unknown', slot.failedParams ?? {})
  return ''
}

/**
 * What tells two of these runs apart, on the back of the cell: the seed, the
 * size it came in, and how long the model computed. The last two used to
 * stand under the picture in expert mode and have a card back to live on
 * since 2026-08-25.
 */
function slotFacts(idx: number): string[] {
  const slot = slots.value[idx]
  const stream = slotStreams.value[idx]
  const out: string[] = []
  if (slot?.seed != null) out.push(`seed ${slot.seed}`)
  const res = stream?.modelMeta?.recommended_resolution
  if (res) out.push(String(res))
  const ms = stream?.stage4DurationMs ?? 0
  if (ms) out.push(`${(ms / 1000).toFixed(1)} s`)
  return out
}

/**
 * Whether the slots on screen belong to the run that is out NOW. Between the
 * press and the answer of the Stage-2 gate, several seconds pass in which the
 * old slots still stand; counting those would let the bar report a finished
 * run while the new one has yet to begin, and a refused prompt would leave
 * „6 / 6“ standing as its last word.
 */
const gatePassed = ref(false)

/** How many of the models have answered — what the bar counts while a run is out. */
const done = computed(() =>
  gatePassed.value ? slots.value.filter(s => s.outputUrl || s.blockedKey || s.failed).length : 0,
)

const slots = ref<ModelSlot[]>([])
const slotStreams = ref<ReturnType<typeof useGenerationStream>[]>([])

/**
 * A selection that holds a model switched off for want of an account lets it
 * go at the moments useModelAvailability names, where its column shows no
 * picture: a picture that has come keeps its name over it. A selection that
 * would keep one model goes back to the history set, since the comparison runs
 * no fewer than MIN_MODELS, unless a column shows a picture; the model then
 * stays selected, its field lit until another model or a set is picked, a run
 * does not send it, and a press waits for MIN_MODELS models a run sends
 * (canGenerate).
 */
leaveOutAccountMissing(selected, PRESETS.history, {
  min: MIN_MODELS,
  busy: () => isGenerating.value,
  showsPictures: id => !!slots.value.find(s => s.configId === id)?.outputUrl,
})

// --- Clipboard ---
function copyPrompt() { window.navigator.clipboard.writeText(userPrompt.value) }
async function pastePrompt() { userPrompt.value = await window.navigator.clipboard.readText() }
function clearPrompt() { userPrompt.value = '' }

/**
 * What this page can be asked, ready to pick. One entry so far: the prompt the
 * comparison pages have always shown behind their own field as the example.
 */
const promptExamples = usePromptPresets()

function applyExample(item: { fill: string[] }) {
  userPrompt.value = item.fill[0] ?? ''
}

// --- Slot actions ---
async function toggleSlotFavorite(slot: ModelSlot) {
  if (!slot.runId) return
  const success = await favoritesStore.toggleFavorite(slot.runId, 'image', deviceId, 'anonymous', 'compare')
  if (success) {
    slot.isFavorited = !slot.isFavorited
  }
}

function forwardToPage(slot: ModelSlot) {
  if (!slot.outputUrl) return
  const runIdMatch = slot.outputUrl.match(/\/api\/.*\/(.+)$/)
  handOverImage(slot.outputUrl, runIdMatch ? runIdMatch[1] : null)
  router.push('/x2x-flow')
}

/** Printing goes the platform's way: the picture in its own window, which prints itself. */
function printSlotImage(slot: ModelSlot) {
  printMedia(slot.outputUrl)
}

async function downloadSlotImage(slot: ModelSlot) {
  if (!slot.outputUrl) return
  const runIdMatch = slot.outputUrl.match(/\/api\/.*\/(.+)$/)
  const runId = runIdMatch ? runIdMatch[1] : 'media'
  await downloadMedia(slot.outputUrl, `ai4artsed_model_${slot.configId}_${runId}.png`)
}

// --- Context Enrichment: Interception Preset ---
// What the ring in the corner of the field says when the perspective wrote
// nothing: a refusal, a failure with its status, an empty answer, or no
// connection (composables/useLabRun.ts). Until 2026-10-10 all four ended in
// the console here, and the ring spun and stopped in silence.
const perspectiveError = ref('')

async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  if (!userPrompt.value.trim()) return

  enriching.value = true
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, userPrompt.value, deviceId)
    if ('written' in outcome) {
      userPrompt.value = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (error) {
    perspectiveError.value = generationErrorFor(t, error)
  } finally {
    enriching.value = false
  }
}

// --- Found pictures (Wikimedia Commons) ---
// Runs beside the generation, not before it: the row is an addition to the
// comparison and must never hold a model back or fail it.
const foundState = ref<FoundState>('idle')
const foundTerm = ref<string | null>(null)
const foundImages = ref<FoundImage[]>([])

// Which run a lookup belongs to. The row is slower than the grid whenever a
// provider is slow, so without this an earlier, slower answer lands after a
// later one and the row shows the previous prompt underneath the current
// pictures — with the heading still reading "Found for this prompt".
let foundRunToken = 0

function clearFoundRow() {
  foundRunToken += 1
  foundState.value = 'idle'
  foundTerm.value = null
  foundImages.value = []
}

// The heading names THIS prompt. The moment the prompt is edited, the row below
// it is about something else, so it goes.
watch(userPrompt, () => {
  if (foundState.value !== 'idle') clearFoundRow()
})

/**
 * A changed set is a changed comparison. The columns take their NAMES from
 * `MODELS` and their contents from `slots`, and those two are the same thing
 * only as long as nothing is switched underneath them: pick the other set after
 * a run and the new names would stand over the old pictures — with the old
 * seed, the old durations, the old download names and the old favourites behind
 * them, and the bar reporting the new set as finished. So what stood there goes
 * with the switch, and the three columns are empty and correctly named again.
 * The pictures themselves are not lost: a favourite outlives the surface.
 *
 * One change keeps the columns: a model switched off for want of an account
 * leaves with its own column, taken away by leaveOutAccountMissing above where
 * the column shows no picture, or deselected by the reader, and the others keep
 * theirs, since names and contents still stand in the same order. What Help is
 * told is then built again from the columns that stay.
 */
watch(selected, (now, before) => {
  const gone = before.filter(id => !now.includes(id))
  if (gone.length && gone.every(id => accountMissing(id)) && now.every(id => before.includes(id))) {
    const stays = slots.value.map(s => now.includes(s.configId))
    slots.value = slots.value.filter((_, i) => stays[i])
    slotStreams.value = slotStreams.value.filter((_, i) => stays[i])
    if (comparisonContext.value && slots.value.length) comparisonContext.value = buildContext('generation_complete')
    return
  }
  slots.value = []
  slotStreams.value = []
  currentSeed.value = null
  gatePassed.value = false
  clearFoundRow()
})

async function lookupFoundImages(prompt: string) {
  const token = ++foundRunToken
  foundState.value = 'loading'
  foundTerm.value = null
  foundImages.value = []
  const baseUrl = apiBase()
  try {
    // Streamed, not awaited in one silent POST, and this is the longest such
    // POST on the platform: at the kids and youth levels the lookup works
    // through up to nine candidate pictures and each of them costs two model
    // calls, on top of the one that turns the prompt into a search term — every
    // one of them queueing for the shared card. The edge in front of this
    // server cuts a request whose origin has sent nothing for about 100
    // seconds, so the row was found, checked and thrown away. Every status
    // resolves, because the row below reads the OUTCOME out of the body and the
    // status is checked here exactly as `res.ok` was.
    const res = await postStreamedRun('/api/commons/lookup', { prompt },
                                      { baseUrl, validateStatus: () => true })
    if (token !== foundRunToken) return
    if (res.status >= 400) { foundState.value = 'error'; return }
    const data = res.data
    foundTerm.value = data.term ?? null
    foundImages.value = Array.isArray(data.images) ? data.images : []
    foundState.value = (data.state === 'ok' || data.state === 'no_motif' ||
                        data.state === 'nothing_found') ? data.state : 'error'
  } catch (e) {
    if (token !== foundRunToken) return
    console.error('[MODEL-COMPARE] Commons lookup failed:', e)
    foundState.value = 'error'
  }
}

// --- What Help is told ---
// With the prompt the columns were set up with, which their card backs name:
// the field above stays writable.
function buildContext(phase: string): string {
  const prompt = slots.value[0]?.prompt ?? userPrompt.value
  const modelList = slots.value.map(s => s.label).join(', ')
  const results = slots.value.filter(s => s.outputUrl).length
  const blocked = slots.value.filter(s => s.blockedKey).map(s => s.label).join(', ')
  return `[Model Comparison — ${phase}]\nPrompt: "${prompt}"\nModels: ${modelList}\nSeed: ${currentSeed.value}\nImages generated: ${results}/${slots.value.length}${blocked ? `\nBlocked: ${blocked}` : ''}`
}

// --- Main generation flow ---
async function startComparison() {
  if (!canGenerate.value || isGenerating.value) return
  isGenerating.value = true
  gatePassed.value = false
  safetyError.value = ''
  // Before the gate, not after it: a refused prompt never reaches the lookup and
  // would otherwise leave the previous run's pictures under the refusal.
  clearFoundRow()

  const baseUrl = apiBase()

  // Stage 2 Jugendschutz gate — check before generating any images. The platform's perspective call,
  // on the passthrough perspective and without an adaptation: a refusal
  // arrives as the block it is (status blocked, stage 2) and goes where every
  // block on this platform goes; an answer that wrote nothing says so under
  // the field. Until 2026-10-10 this matched the refusal sentence's wording
  // itself, from a copy of the backend's constant (finding S-015 of the code review of 2026-10-10).
  try {
    const outcome = await interceptPrompt('user_defined', userPrompt.value, null, { skipOptimization: true })
    if ('refusedKey' in outcome) {
      safetyStore.reportBlock(outcome.blockedAtStage || 2, outcome.reason || t('mediaInput.contentBlocked'), [])
      isGenerating.value = false
      return
    }
    if (!('written' in outcome) || !outcome.written.trim()) {
      safetyError.value = perspectiveFailureText(t, 'written' in outcome ? { empty: true } : outcome)
      isGenerating.value = false
      return
    }
  } catch (e) {
    safetyError.value = generationErrorFor(t, e)
    isGenerating.value = false
    return
  }

  // The prompt has passed the gate, so it may be looked up. Deliberately not
  // awaited — the pictures arrive whenever they arrive.
  void lookupFoundImages(userPrompt.value)

  // Initialize slots + streams
  // Fixed seed for all
  const seed = Math.floor(Math.random() * 4294967296)
  currentSeed.value = seed

  const ranPrompt = userPrompt.value
  gatePassed.value = true
  slots.value = MODELS.value.map((m, idx) => ({
    configId: m.id,
    label: m.label,
    outputUrl: null,
    runId: null,
    queuePosition: idx + 1,
    blockedKey: null,
    failed: false,
    failedKey: null,
    isFavorited: false,
    prompt: ranPrompt,
    seed,
    createdAt: null,
  }))
  slotStreams.value = MODELS.value.map(() => useGenerationStream())

  // Comparison group ID for linking runs
  const groupId = `cmp_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`

  try {
    // Sequential generation — one model at a time
    for (let i = 0; i < slots.value.length; i++) {
      const slot = slots.value[i]!
      const stream = slotStreams.value[i]!

      for (let j = i + 1; j < slots.value.length; j++) {
        slots.value[j]!.queuePosition = j - i
      }

      // Switched off for want of an account, before the run or while it was
      // out: it is not sent. Its column carries the sentence, and it leaves
      // when the run ends unless the selection keeps the model
      // (leaveOutAccountMissing above).
      if (accountMissing(slot.configId)) {
        slot.failed = true
        slot.failedKey = 'x2xFlow.accountMissing'
        slot.failedParams = accountParams(slot.configId)
        slot.queuePosition = 0
        continue
      }

      try {
        const result: GenerationResult = await stream.executeWithStreaming({
          prompt: userPrompt.value,
          output_config: slot.configId,
          seed,
          device_id: `${deviceId}_cmp${i}`,
          source_view: 'compare',
          comparison_group_id: groupId,
          comparison_original_prompt: userPrompt.value,
        })

        if (result.status === 'success' && result.media_output?.url) {
          slot.outputUrl = `${baseUrl}${result.media_output.url}`
          slot.runId = result.run_id || null
          slot.createdAt = Date.now()
        } else if (result.status === 'blocked') {
          slot.blockedKey = safetyBlockKey(result.blocked_reason, result.blocked_stage)
        } else {
          // error, cancelled, busy, and a success that carried no picture: all
          // four are a hole in the row, and a cell left untouched would keep the
          // empty plate of one still to come while the count stayed short.
          slot.failed = true
          slot.failedKey = failureKey(result.status, result.error || '', result.busy)
        }
        // The badge counts what is still ahead; this one is behind us.
        slot.queuePosition = 0
      } catch (e) {
        console.error(`[MODEL-COMPARE] Generation for ${slot.configId} failed:`, e)
        slot.failed = true
        slot.failedKey = failureKey('error', e instanceof Error ? e.message : String(e))
        slot.queuePosition = 0
      }
    }

    // Nothing is described here any more. Every run used to be sent through a
    // VLM the moment it finished -- three readings per comparison, unasked --
    // and since 2026-08-23 it is known that the wording of that call came back
    // empty from the model every single time, so the agent beside the grid was
    // told about three pictures and given nothing of them. It reads them itself
    // now, and only when it is asked to.
    const successfulSlots = slots.value.filter(s => s.runId && s.outputUrl)
    comparisonContext.value = buildContext('generation_complete')

    // POST comparison context to each successful run
    for (const slot of successfulSlots) {
      if (!slot.runId) continue
      fetch(`${baseUrl}/api/schema/pipeline/run/${slot.runId}/context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          comparison_context: {
            original_prompt: userPrompt.value,
            models: slots.value.map(s => s.configId),
            seed,
            this_model: slot.configId,
          }
        })
      }).catch(() => { /* fire-and-forget */ })
    }
  } catch (e) {
    console.error('[MODEL-COMPARE] Failed:', e)
  } finally {
    isGenerating.value = false
  }
}

const pageContextStore = usePageContextStore()

// Which of the tabs is open. The catalogue (platform_items.json) is keyed to
// this, and carries what this place says about its own technology.
const pageContext = computed<PageContext>(() => ({
  activeViewType: 'model_comparison',
  pageContent: {
    inputText: userPrompt.value,
    // The block that fed the column beside the grid until 2026-08-25 goes to
    // Help unchanged, in the field made for what a surface has produced.
    instrumentRuns: comparisonContext.value
      ? [{
          label: `${slots.value.map(s => s.label).join(', ')} · seed ${currentSeed.value ?? '—'}`,
          text: comparisonContext.value,
        }]
      : [],
    surfaceMedia: surfaceMedia.value,
  },
  // Held up as a sign while the conversation is closed, and only once the
  // surface has something to interpret — before the first run
  // it would be taken with nothing standing there.
  offer: comparisonContext.value ? { label: t('compare.ask.sign') } : null,
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onBeforeUnmount(() => {
  pageContextStore.clearContext()
})


/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
</script>

<style scoped>
/* The page frame, the column box, the head row, the name, the queue badge, the
   starting number, the error line and the whole order — preparing column at the
   left, results at the right, and how the two stack on a narrow work area — all
   come from `assets/compare-stage.css`. What is left here is what FILLS the
   results.

   Until 2026-09-07 this surface was a scrolling page of its own and carried the
   entire frame itself (`.compare-page`, `.comparison-grid`, `.comparison-slot`,
   `.slot-header`, `.seed-display` with a hardwired `Seed:`, `.safety-error`,
   and a hand-rolled row of preset buttons) — the same structure Language
   Understanding had given up the same day. */

/* One row, one column per model, and it wraps for nothing: three pictures that
   cannot be seen at once are not a comparison, which is why this is not the
   wrapping wall Language Understanding runs, where four languages are read two
   at a time.

   The width is what it is. Measured at the reference device (1210 x 834, work
   area 970): 197 px of column and 171 px of picture, against 302 px while the
   surface was a scrolling page across the full width. A tap opens a picture at
   full size, and folding the instrument column hands its whole 241 px to this
   side — measured, 277 px of column and 251 px of picture.

   `align-items: start` so a column is as tall as what stands in it rather than
   stretching over whatever height the row happens to have. */
.mc-models {
  display: grid;
  grid-template-columns: repeat(var(--mc-cols), minmax(0, 1fr));
  gap: 1rem;
  align-items: start;
}

.mc-model {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

/* The row gives up and stacks only where three columns stop being readable:
   under 470 px of work area a picture falls below 120 px.

   NOT at the 900 px where the stage puts the preparing column on top — there
   the results get the WHOLE width, which is 196 px of picture at a 628 px work
   area, MORE than the wide order leaves them. The old surface stacked at a
   WINDOW width of 900; the same number read against the work area is a window
   of about 1172 with the instrument column open, so three models would have
   become one per row on an ordinary laptop. */
@container (max-width: 470px) {
  .mc-models {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
