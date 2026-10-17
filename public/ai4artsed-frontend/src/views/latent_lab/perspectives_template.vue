<!--
  Perspectives on a Template — the second instrument of the Prompt Interception
  group, and the reverse of the first: there ONE perspective stood and the
  writing models made the rows; here ONE template is written by several
  perspectives and the writing model stands.

  What varies between two pictures is the PERSPECTIVE and nothing else. The
  template is the same, the writing model is the same, the starting number is
  the same, and every picture is handed to the image model through the same
  adaption that model's output config carries — so each picture can be read for
  what that one perspective does to the template.

  ONE image model runs. Twelve perspectives are twelve runs already, and every
  further model multiplies them; what this surface asks is what a perspective
  does, and the comparison of image models is its own instrument.

  The template can be written, or READ FROM A PICTURE: a picture dragged onto
  the SAME field is read, and the reading then stands in that field, where it
  can be worked on further. There is no picture field of its own here, and no
  invitation either — every field on this platform takes a picture that is
  dragged onto it; the route is the flow board's. New is only
  that the reading writes into the template line. It is read as a DESCRIPTION — the reading frames are a choice
  about how to interpret a picture, and here the picture is not being
  interpreted, it is being turned into a template that other pictures are made
  from. The interpretation is what the rows underneath do.

  The writing model is the platform's own. This surface makes no choice about
  it: it runs on the settings of the flow board, like every other surface that
  puts a perspective to work.

  The first picture is the template AS WRITTEN, with no interception between it
  and the image model. It is what the pictures beside it are read against, and
  it is marked as the ground rather than named as a case.

  The TEXTS step out of the raster: at twelve perspectives a reading column left
  the pictures at 110 px, and the pictures are what is looked at here. What a
  perspective wrote hangs on its disc instead — rest on it, or hold it on a
  touch screen. The written results are secondary on this surface and show
  only on hover over the symbols.

  The run is `composables/useInterceptionSeries.ts`, shared with the other two
  instruments of this group; the WALL it stands in
  (`components/InterceptionSeriesWall.vue`) is the sister of their raster and
  holds the same cell. What stays here is what this instrument IS: its rows are
  perspectives, and each wears the disc it is shown as.
-->
<template>
  <div class="lab-page">
    <ShellRun
      :ready="canRun"
      :running="series.busy.value"
      :title="t('latentLab.interception.template.generate')"
      :label="series.writing.value ? t('latentLab.runLine.text') : t('latentLab.runLine.image')"
      :count="series.writing.value ? series.writingDone.value : series.done.value"
      :total="series.writing.value ? series.writingTotal.value : series.expected.value"
      @run="startRun"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <section class="lab-prep lab-col col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <template v-if="!folded">
            <PromptExamples
              :items="promptExamples"
              :current="templateText"
              :disabled="series.busy.value || reading"
              @pick="applyExample"
            />
            <MediaInputBox
              chrome="bare"
              v-model:value="templateText"
              input-type="text"
              :placeholder="t('mediaInput.freePromptPlaceholder')"
              :rows="5"
              :is-filled="!!templateText"
              :is-loading="reading"
              :disabled="series.busy.value || reading"
              :show-preset-button="true"
              @copy="copyTemplate"
              @paste="pasteTemplate"
              @clear="clearTemplate"
              @open-preset-selector="showPresetOverlay = true"
              @image-uploaded="handlePicture"
              @image-removed="dropPicture"
            />

            <label class="lab-pick-label">{{ t('latentLab.interception.template.perspectivesLabel') }}</label>
            <!-- The chosen perspectives, each as the disc it is shown as on
                 this platform, in the order they were chosen — which is the
                 order of the rows. The chooser is the platform's own; a
                 category tree of thirty-five names laid out as chips would fill
                 this column before anything else in it could be seen. -->
            <PerspectivePicks
              :picks="chosenPicks"
              :disabled="series.busy.value"
              :add-title="t('latentLab.interception.template.perspectiveAdd')"
              :remove-title="t('latentLab.interception.template.perspectiveRemove')"
              @add="showPresetOverlay = true"
              @remove="removePreset"
            />

            <label class="lab-pick-label">{{ t('latentLab.interception.template.imageModelLabel') }}</label>
            <ChipSelect
              :model-value="chosenImageModel"
              :options="imageChoices"
              :min-width="145"
              :disabled="series.busy.value"
              @update:model-value="v => (chosenImageModel = v as string)"
            />

            <p v-if="notice" class="lab-prep-err">{{ notice }}</p>

            <aside class="lab-note">
              <h3>{{ t('latentLab.interception.tabs.interception-template.label') }}</h3>
              <p
                v-for="(para, i) in t('latentLab.interception.template.noteBody').split('\n\n')"
                :key="i"
              >{{ para }}</p>
              <LabReferences
                :title="t('latentLab.interception.template.referencesTitle')"
                :items="REFERENCES"
                flat
              />
            </aside>
            </template>
          </section>

          <section class="lab-plot">
            <InterceptionSeriesWall
              file-stem="perspectives"
              v-if="wallColumn"
              :rows="rows"
              :column="wallColumn"
              :lead="leadPicture"
              :not-yet-run-label="t('latentLab.interception.template.notYetRun')"
              :adapted="series.adapted.value"
              :note="series.cellNote"
            >
              <!-- What a picture on the wall IS: the disc of its perspective.
                   The row that holds the template as written wears none — it
                   met no perspective, and where the template was read from a
                   picture that picture stands first on the wall in its own
                   right and no longer on this row's foot. -->
              <template #row-face="{ row }">
                <PerspectiveBubble
                  v-if="row && !row.reference"
                  :preview-id="row.previewId"
                  :config-id="row.presetId"
                  :color="row.color"
                  :openable="false"
                />
              </template>
            </InterceptionSeriesWall>
          </section>
        </div>
      </div>
    </div>

    <InterceptionPresetOverlay
      :visible="showPresetOverlay"
      @close="showPresetOverlay = false"
      @preset-selected="handlePresetSelected"
    />
  </div>
</template>

<script setup lang="ts">
import ColumnFold from '@/components/ColumnFold.vue'
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import ShellRun from '@/components/ShellRun.vue'
import ChipSelect from '@/components/ChipSelect.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import { usePromptPresets } from '@/lib/promptPresets'
import PerspectiveBubble from '@/components/PerspectiveBubble.vue'
import PerspectivePicks, { type PerspectivePick } from '@/components/PerspectivePicks.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import InterceptionSeriesWall from '@/components/InterceptionSeriesWall.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { usePictureTemplate } from '@/composables/usePictureTemplate'
import {
  markTerms,
  perspectiveTerms,
  useInterceptionSeries,
  type SeriesRow,
} from '@/composables/useInterceptionSeries'
import { useKeptPerspectivesStore, keptColor } from '@/stores/keptPerspectives'
import {
  RASTER_IMAGE_MODELS,
  RASTER_IMAGE_MODELS_EFFECT_CHECK,
  RASTER_IMAGE_MODEL_SINGLE_DEFAULT,
} from '@/data/rasterImageModels'
import { useModelRegister } from '@/composables/useModelRegister'

const { t, locale } = useI18n()

/**
 * What is measured about wording. Palmini and Cetinic compare prompt groups on a
 * public platform - a correlation, not a controlled change; Bianchi et al. set
 * their prompts themselves, which is why their two examples read as they do.
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'De Rosa Palmini, Cetinic',
    title:
      '"Exploring Language Patterns of Prompts in Text-to-Image Generation '
      + 'and Their Impact on Visual Diversity"',
    venue: 'arXiv:2504.14125',
    doi: 'https://doi.org/10.48550/arXiv.2504.14125',
  },
  {
    authors: 'Bianchi et al.',
    title:
      '"Easily Accessible Text-to-Image Generation Amplifies Demographic '
      + 'Stereotypes at Large Scale"',
    venue: 'arXiv:2211.03759',
    doi: 'https://doi.org/10.48550/arXiv.2211.03759',
  },
]
const register = useModelRegister()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const kept = useKeptPerspectivesStore()

/**
 * This surface is still the one the reading and the preselection belong to. The
 * run keeps its own token (composables/useInterceptionSeries.ts); these are
 * plain calls and need this.
 */
let alive = true

// ---------------------------------------------------------------------------
// The template: written, or read from a picture.
// ---------------------------------------------------------------------------

/**
 * The line every row starts from. The offer above it is the platform's own
 * example, taken from Attention Cartography rather than written again here: a
 * second set of example prompts is a second place for a bias to be introduced,
 * and this one names no place and no person.
 */
const templateText = ref<string>('')

const promptExamples = usePromptPresets(['house'])

function applyExample(item: { fill: string[] }): void {
  templateText.value = item.fill[0] ?? ''
}

function copyTemplate(): void { copyToClipboard(templateText.value) }
function pasteTemplate(): void { templateText.value = pasteFromClipboard() }
function clearTemplate(): void { templateText.value = '' }

/**
 * The picture, and what reading it does to the template. Both instruments that
 * let a picture into their template field use the same one
 * (`composables/usePictureTemplate.ts`); what stays here is the field, the row
 * that draws the picture and the record of the run.
 */
const {
  picturePath,
  picturePreview,
  reading,
  readingFailedKey,
  templateOrigin,
  templateFromPicture,
  showsOriginPicture,
  handlePicture,
  dropPicture,
  FRAME,
} = usePictureTemplate(templateText)

/**
 * The picture the template was read from, first on the wall. It is there
 * only while the line in the field is still the reading of that picture -
 * `showsOriginPicture` is what knows that.
 */
const leadPicture = computed(() =>
  showsOriginPicture.value && picturePreview.value
    ? {
        url: picturePreview.value,
        label: t('latentLab.interception.template.sourcePicture'),
      }
    : null
)

// ---------------------------------------------------------------------------
// The perspectives: they ARE the rows.
// ---------------------------------------------------------------------------

/**
 * ONE chosen perspective, exactly as the platform's chooser hands it over
 * (`components/InterceptionPresetOverlay.vue`): what it is addressed by, what
 * it is called, the words it works with, the picture it wears, and — where it
 * is one of this person's own — the row it was saved as.
 */
interface ChosenPerspective {
  configId: string
  configName: string
  context: string
  previewId: string
  promptId: number | null
}

/**
 * The perspectives that run, in the order they were chosen. That order is the
 * order of the rows: what is picked first stands under the reference row, and a
 * reader who wants another order takes one away and chooses it again.
 *
 * Nothing is chosen to begin with: WHICH perspectives run is the whole question
 * of this surface.
 */
const chosenPresets = ref<ChosenPerspective[]>([])
const showPresetOverlay = ref(false)

/**
 * A SAVED perspective wears a colour of the platform's palette and never a
 * picture; a given one wears the preview its config file
 * carries and no colour.
 */
function colorOf(p: ChosenPerspective): string {
  return p.promptId === null ? '' : keptColor(p.promptId, kept.items)
}

/** The strip's own reading of them: the disc, its name, and that colour. */
const chosenPicks = computed<PerspectivePick[]>(() =>
  chosenPresets.value.map(p => ({
    configId: p.configId,
    configName: p.configName,
    previewId: p.previewId,
    color: colorOf(p),
    prompt: p.context,
  })),
)

/**
 * One perspective more. The same one twice would be two rows that cannot
 * differ, at the price of their pictures — so a perspective already standing is
 * left where it is rather than moved to the end: its row has its text and its
 * pictures, and moving it would recompute nothing but would renumber
 * everything.
 */
function handlePresetSelected(payload: {
  configId: string
  context: string
  configName: string
  previewId?: string
  promptId?: number
}): void {
  showPresetOverlay.value = false
  if (chosenPresets.value.some(p => p.configId === payload.configId)) return
  chosenPresets.value = [
    ...chosenPresets.value,
    {
      configId: payload.configId,
      configName: payload.configName,
      context: payload.context || '',
      previewId: payload.previewId || '',
      promptId: typeof payload.promptId === 'number' ? payload.promptId : null,
    },
  ]
}

function removePreset(configId: string): void {
  chosenPresets.value = chosenPresets.value.filter(p => p.configId !== configId)
}

// ---------------------------------------------------------------------------
// The image model: ONE, and it is the wall.
// ---------------------------------------------------------------------------

/**
 * Which model shows what the perspectives wrote. One, and the cheapest of the
 * ones that run on this platform's own cards stands first: a dozen perspectives
 * is a dozen pictures per model, so a second model would not add a column here,
 * it would double the run.
 */
// An empty list would leave nothing chosen, and nothing chosen runs nothing.
const chosenImageModel = ref<string>(RASTER_IMAGE_MODEL_SINGLE_DEFAULT)

const imageChoices = computed(() =>
  RASTER_IMAGE_MODELS.filter(m => RASTER_IMAGE_MODELS_EFFECT_CHECK.includes(m.id)).map(m => ({
    value: m.id,
    label: m.label,
    aside: register.sizeText(m.id, t, locale.value),
    info: register.infoFor(m.id, m.label, t),
  })),
)

const imageColumns = computed(() =>
  RASTER_IMAGE_MODELS.filter(m => m.id === chosenImageModel.value).map(m => ({
    id: m.id,
    label: m.label,
  })),
)

// ---------------------------------------------------------------------------
// The rows: the template as written, then one per perspective.
// ---------------------------------------------------------------------------

/** A row of THIS instrument: a perspective, and the disc it is shown as. */
interface PerspectiveRow extends SeriesRow {
  presetId: string
  previewId: string
  color: string
}

/**
 * What identifies a row's work: the perspective, the template and the language
 * the perspective reaches the model in. A template rewritten therefore costs
 * exactly what it changes, and a perspective taken off the list and put back
 * finds its text still there.
 */
const rows = computed<PerspectiveRow[]>(() => {
  const line = templateText.value.trim()
  // The template as written, and what comes of it with no step in between. It
  // meets no perspective, so it is keyed by the line alone and is not
  // recomputed when the perspectives change.
  const out: PerspectiveRow[] = [
    {
      key: `as-written|${line}`,
      reference: true,
      presetId: '',
      previewId: '',
      color: '',
      // Which of the two this row is depends on whether a picture stands
      // before it. When a picture is there, the picture is the reference;
      // translating it into a prompt and the image inference from it is the
      // first manipulation, just without a preset. Reference where the
      // template was typed; the first step, with no perspective on it, where
      // it was read from a picture.
      label: leadPicture.value
        ? t('latentLab.interception.template.withoutPerspective')
        : t('latentLab.interception.template.asWritten'),
      request: null,
      text: line,
      // Nothing is marked here: this is the text no perspective ever met.
      segments: markTerms(line, []),
      failedKey: '',
    },
  ]
  for (const p of chosenPresets.value) {
    // The reader's language belongs in the key: the perspective's context
    // reaches the model in that language and travels with the request
    // (`user_language`), so a row written in one language is not the same work
    // as the same row in another. The writing model is the platform's own and
    // stands in no key, because this surface never varies it.
    const key = `${p.configId}|${locale.value}|${line}`
    const r = series.results.value[key]
    out.push({
      key,
      reference: false,
      presetId: p.configId,
      previewId: p.previewId,
      color: colorOf(p),
      label: p.configName || p.configId,
      // No model is named: the platform writes with the one it is configured
      // to intercept with, as it does everywhere a perspective is put to work.
      request: { schema: p.configId },
      text: r?.text ?? '',
      segments: markTerms(r?.text ?? '', perspectiveTerms(p.context)),
      failedKey: r?.failedKey ?? '',
    })
  }
  return out
})

// ---------------------------------------------------------------------------
// The run: the shared series, with this instrument's rows and columns.
// ---------------------------------------------------------------------------

const series = useInterceptionSeries({
  line: () => templateText.value,
  rows: () => rows.value,
  columns: () => imageColumns.value,
  sourceView: 'perspectives_template',
  // Where the template was READ, the picture and the frame are part of what the
  // row was: the same line typed by hand is a different fact about the run. It
  // is the picture the LINE came from that is recorded, not the one that
  // happens to lie in the field — a picture taken away after the reading leaves
  // the reading standing.
  //
  // No model is recorded as asked for: this surface asks for none. What wrote
  // is recorded by the series itself.
  context: () =>
    templateFromPicture.value && templateOrigin.value
      ? {
          template_image_path: templateOrigin.value.imagePath,
          template_frame: templateOrigin.value.frame,
        }
      : {},
})

/** The one image model, as the run hands it over. */
const wallColumn = computed(() => series.gridColumns.value[0] ?? null)

/** Whether the controls are folded away. Only the handle moves this. */
const folded = ref(false)

onBeforeUnmount(() => {
  alive = false
  series.release()
  pageContextStore.clearContext()
})

const canRun = computed(
  () =>
    series.hasWork.value &&
    !reading.value &&
    !!templateText.value.trim() &&
    chosenPresets.value.length > 0 &&
    !!chosenImageModel.value,
)

async function startRun(): Promise<void> {
  if (!canRun.value) return
  readingFailedKey.value = ''
  await series.startRun()
}

/** The last thing that went wrong, whichever of the two it was. The sentence
 *  about a reading is cleared by everything that comes after it — a line
 *  written, a frame chosen, a run pressed — so what stands here is the newest
 *  of the two and never an old reading over a fresh run. */
const notice = computed(() =>
  readingFailedKey.value ? t(readingFailedKey.value) : series.errorMessage.value,
)

// ---------------------------------------------------------------------------
// What Help is told stands here.
// ---------------------------------------------------------------------------
const pageContextStore = usePageContextStore()

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'perspectives_template',
  pageContent: {
    inputText: templateText.value,
    contextPrompt: chosenPresets.value.map(p => p.configName || p.configId).join(', '),
    surfaceMedia: series.gridColumns.value.flatMap(col =>
      col.cells.flatMap((cell, ri) =>
        cell.runId && cell.url
          ? [{ runId: cell.runId, label: `${rows.value[ri]?.label ?? ''} · ${col.label}` }]
          : [],
      ),
    ),
  },
  offer: series.gridColumns.value.some(col => col.cells.some(cell => cell.url))
    ? { label: t('compare.ask.sign') }
    : null,
}))

watch(pageContext, ctx => { pageContextStore.setPageContext(ctx) }, { immediate: true, deep: true })
</script>

<style scoped>
/* The page skeleton, the frame and the square cell are shared and stand in
   assets/flow-stage.css and assets/instrument-surface.css; the wall, the badge
   on a picture and the marked word are components/InterceptionSeriesWall.vue.
   What is here is what this surface alone needs. */


</style>
