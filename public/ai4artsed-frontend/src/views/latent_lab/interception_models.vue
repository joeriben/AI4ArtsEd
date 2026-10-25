<!--
  Interception across Models — the first instrument of the Prompt Interception
  group, and the one place where the platform's own central operation is put up
  as a repeatable series: ONE line, ONE perspective, several writing models, and
  per model its own text with the picture made from it.

  What is examined here is the TEXT. The picture beside it is one image model's
  reading of that text and stands there as a reading aid, which is why there is
  one of it and not a set: a second and a third picture would put the image
  models up for comparison, and that comparison is the Model Comparison's
  (views/compare/model_comparison.vue). A culture named in the line and lost in
  the writing is the case this instrument was built on, and it is one case among
  the ones that run on it.

  What varies between two rows is the WRITING MODEL and nothing else. The line
  is the same, the perspective is the same, the starting number is the same, and
  every row is handed to an image model through the same adaption that model's
  output config carries — so a difference between two rows is the model that
  wrote, and cannot also have been the seed or a differently prepared prompt.

  The top row is the line AS WRITTEN, with no interception between it and the
  image models. It is what the other rows are read against, and it cannot be
  switched off; the same discipline as the unmarked first column of Cultural
  (Un)Known (views/latent_lab/default_census.vue), which is this instrument's
  sibling and whose frame, raster, cell and run loop it shares.

  The run itself — the two phases, the cells, the record — is
  `composables/useInterceptionSeries.ts` and the raster is
  `components/InterceptionSeriesGrid.vue`, both shared with the second
  instrument of this group (views/latent_lab/perspectives_template.vue), which
  varies the PERSPECTIVE instead. What stays here is what this instrument IS:
  its rows are writing models, and its heads say which model and which service.
-->
<template>
  <div class="lab-page">
    <ShellRun
      :ready="canRun"
      :running="series.busy.value"
      :title="t('latentLab.interception.models.generate')"
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

            <PromptExamples
              :items="promptExamples"
              :current="promptText"
              :disabled="series.busy.value"
              @pick="applyExample"
            />
            <MediaInputBox
              chrome="bare"
              :placeholder="t('mediaInput.freePromptPlaceholder')"
              v-model:value="promptText"
              input-type="text"
              :rows="3"
              :is-filled="!!promptText"
              :is-loading="readingPicture"
              :disabled="series.busy.value || readingPicture"
              :show-preset-button="true"
              @copy="copyPrompt"
              @paste="pastePrompt"
              @clear="clearPrompt"
              @open-preset-selector="showPresetOverlay = true"
              @image-uploaded="handlePicture"
              @image-removed="dropPicture"
            />
            <!-- The reading of a dropped picture, where it did not come back. -->
            <p v-if="readingFailedKey" class="lab-prep-err">{{ t(readingFailedKey) }}</p>

            <!-- The perspective STAYS in sight, because it works in every row.
                 Cultural (Un)Known writes its own into the field and shows
                 nothing of it afterwards; here the choice is a standing one.
                 The strip is the group's (`components/PerspectivePicks.vue`),
                 held to ONE: this surface varies the writing models, not the
                 perspectives, so there is nothing to add beside the one disc —
                 and until one is chosen the empty place stands for it. -->
            <label class="lab-pick-label">{{ t('latentLab.interception.models.perspectiveLabel') }}</label>
            <PerspectivePicks
              :picks="presetPicks"
              single
              :disabled="series.busy.value"
              :add-title="t('latentLab.interception.models.perspectiveAdd')"
              @add="showPresetOverlay = true"
            />

            <label class="lab-pick-label">{{ t('latentLab.interception.models.writingModelsLabel') }}</label>
            <!-- Three lineups, not every model the installation offers. Each
                 one asks a question and holds everything else still; the flat
                 list that stood here until 2026-09-04 asked none, and put a
                 coding model and the platform's own safety checker in front of
                 a class as things to compare. Which models a lineup stands for
                 is data, and a model stands under its own name: which service
                 it is reached through says nothing about what it writes. -->
            <ChipSelect
              :model-value="lineup"
              :options="lineupChoices"
              :min-width="145"
              :disabled="series.busy.value"
              @update:model-value="v => applyLineup(v as string)"
            />
            <!-- The list itself never arrived. Without this line the area
                 under the heading is empty and silent, which is also what it
                 looks like while the list is still on its way. -->
            <p v-if="!writersLoading && writersLoadFailed" class="lab-prep-err quiet">
              {{ t('latentLab.interception.models.modelsUnavailable') }}
            </p>
            <p v-if="gpuServiceUnreachable" class="lab-prep-err quiet">
              {{ t('latentLab.textLab.error.gpuUnreachable') }}
            </p>

            <label class="lab-pick-label">{{ t('latentLab.interception.models.imageModelLabel') }}</label>
            <!-- ONE, because the picture is the reading aid and not the
                 subject. -->
            <ChipSelect
              :model-value="imageModel"
              :options="imageChoices"
              :min-width="180"
              :disabled="series.busy.value"
              @update:model-value="v => (imageModel = v as string)"
            />

            <p v-if="series.errorMessage.value" class="lab-prep-err">{{ series.errorMessage.value }}</p>

            <aside class="lab-note">
              <h3>{{ t('latentLab.interception.tabs.interception-models.label') }}</h3>
              <p
                v-for="(para, i) in t('latentLab.interception.models.noteBody').split('\n\n')"
                :key="i"
              >{{ para }}</p>
              <LabReferences
                :title="t('latentLab.interception.models.referencesTitle')"
                :items="REFERENCES"
                flat
              />
            </aside>
          </section>

          <section class="lab-plot">
            <InterceptionSeriesGrid
              file-stem="interception"
              :rows="rows"
              :columns="series.gridColumns.value"
              :intercepted-label="t('latentLab.interception.models.interceptedLabel')"
              :not-yet-run-label="t('latentLab.interception.models.notYetRun')"
              :adapted="series.adapted.value"
              :note="series.cellNote"
              head-class="ilm-rowname"
            >
              <!-- Which model a row is, said once at its left end. The card
                   beside it says what that model is and where its text goes:
                   who made it, how open, how big, through which service, and
                   what the register records about that service. -->
              <template #row-head="{ row }">
                <span
                  class="ilm-rowname-label"
                  @pointerenter="onRowEnter(row, $event)"
                  @pointerleave="closeRowCard"
                  @pointerdown="onRowDown(row, $event)"
                  @pointerup="releaseRowCard"
                  @pointercancel="releaseRowCard"
                >{{ row.label }}</span>
              </template>
            </InterceptionSeriesGrid>
            <InfoCard :open="!!rowCard" :x="rowX" :y="rowY" :above="rowAbove">
              <InfoCardFacts v-if="rowCard" :info="rowCard" />
            </InfoCard>
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
import ColumnFold from '@/components/ColumnFold.vue'
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePictureTemplate } from '@/composables/usePictureTemplate'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import ShellRun from '@/components/ShellRun.vue'
import ChipSelect, { type ChipInfo } from '@/components/ChipSelect.vue'
import InfoCard from '@/components/InfoCard.vue'
import InfoCardFacts from '@/components/InfoCardFacts.vue'
import { useInfoCard } from '@/composables/useInfoCard'
import { providerName } from '@/data/providers'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import { usePromptPresets } from '@/lib/promptPresets'
import PerspectivePicks, { type PerspectivePick } from '@/components/PerspectivePicks.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import InterceptionSeriesGrid from '@/components/InterceptionSeriesGrid.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useChatModels, type ChatModelOption } from '@/composables/useChatModels'
import {
  markTerms,
  perspectiveTerms,
  useInterceptionSeries,
  type SeriesRow,
} from '@/composables/useInterceptionSeries'
import { useKeptPerspectivesStore, keptColor } from '@/stores/keptPerspectives'
import { RASTER_IMAGE_MODELS } from '@/data/rasterImageModels'
import { useModelAvailability } from '@/composables/useModelAvailability'
import { useModelRegister, lineupMembers } from '@/composables/useModelRegister'

const { t, locale } = useI18n()

/**
 * Seven models, one set of headlines, and the spread between them measured
 * against the human-written article under the same headline. The task there
 * is writing from a headline rather than writing through a perspective, which
 * is why the note gives the study its own sentence of setup.
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'Fang et al.',
    title:
      '"Bias of AI-generated content: an examination of news produced by '
      + 'large language models"',
    venue: 'Scientific Reports 14, 5224',
    doi: 'https://doi.org/10.1038/s41598-024-55686-2',
  },
]
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const kept = useKeptPerspectivesStore()
const register = useModelRegister()

/**
 * This surface is still the one the preselection belongs to. The run keeps its
 * own token (composables/useInterceptionSeries.ts); the preselection is a plain
 * call and needs this.
 */
let alive = true

// ---------------------------------------------------------------------------
// What is prepared: the line, the perspective, the two sets of models.
// ---------------------------------------------------------------------------

/**
 * The line that runs. The offer above it is the platform's own example, taken
 * from Attention Cartography rather than written again here: a second set of
 * example prompts is a second place for a bias to be introduced, and this one
 * names no place and no person.
 */
const promptText = ref<string>('')

/**
 * A picture dropped onto the prompt field is read as a description, and the
 * reading then stands in the field, where it can be worked on further
 * (`composables/usePictureTemplate.ts`). This way in belongs on every FREE
 * prompt field of the lab, and the hint over the field names it.
 */
const {
  reading: readingPicture,
  readingFailedKey,
  handlePicture,
  dropPicture,
} = usePictureTemplate(promptText)

const promptExamples = usePromptPresets(['house'])

function applyExample(item: { fill: string[] }): void {
  promptText.value = item.fill[0] ?? ''
}

function copyPrompt(): void { copyToClipboard(promptText.value) }
function pastePrompt(): void { promptText.value = pasteFromClipboard() }
function clearPrompt(): void { promptText.value = '' }

interface ChosenPreset {
  configId: string
  configName: string
  context: string
  previewId: string
  promptId: number | null
}

const preset = ref<ChosenPreset>({
  configId: '',
  configName: '',
  context: '',
  previewId: '',
  promptId: null,
})
const showPresetOverlay = ref(false)

/**
 * A SAVED perspective wears a colour and never a picture; a
 * given one wears the preview its config file carries and no colour.
 */
const presetColor = computed(() =>
  preset.value.promptId === null ? '' : keptColor(preset.value.promptId, kept.items),
)

/** The standing choice, as the strip reads it: one, or none yet. */
const presetPicks = computed<PerspectivePick[]>(() =>
  preset.value.configId
    ? [
        {
          configId: preset.value.configId,
          configName: preset.value.configName,
          previewId: preset.value.previewId,
          color: presetColor.value,
          prompt: preset.value.context,
        },
      ]
    : [],
)

function handlePresetSelected(payload: {
  configId: string
  context: string
  configName: string
  previewId?: string
  promptId?: number
}): void {
  showPresetOverlay.value = false
  preset.value = {
    configId: payload.configId,
    configName: payload.configName,
    context: payload.context || '',
    previewId: payload.previewId || '',
    promptId: typeof payload.promptId === 'number' ? payload.promptId : null,
  }
}

const {
  models: chatModels,
  loading: writersLoading,
  loadFailed: writersLoadFailed,
  gpuServiceUnreachable,
  refresh: refreshChatModels,
} = useChatModels()

/**
 * The list is fetched once per session and what came of it is kept — so a list
 * that never arrived stays missing until the page is reloaded, and this surface
 * cannot be worked with at all without it. Entering it asks again where the
 * last attempt failed, and only there: a list that arrived is not fetched a
 * second time.
 */
onMounted(() => {
  if (writersLoadFailed.value) void refreshChatModels()
})

/** Which models write. They ARE the rows, under the reference row. */
const chosenWriters = ref<string[]>([])

/**
 * The writing models, one under the other in the order the list arrives in, each
 * under the name it carries. A model the platform lists and this installation
 * has not installed stays in the list and cannot be picked: what else there is
 * has to stay in sight.
 *
 * WHERE a model is installed has nothing to do with the question this surface
 * asks. The chat route publishes a locally installed model as „<name> (local)"
 * (my_app/routes/chat_routes.py), which is the right thing to say where the
 * choice is about reaching a service, and here it would sort the list by an axis
 * that is not the subject. So that one suffix comes off — everywhere on this
 * surface, chips and row heads alike, or the same model would carry two names.
 * The maker is out of the name at its source (`gpu_service/services/
 * llm_backend.py`), so nothing has to be taken off here for it.
 */
const LOCAL_SUFFIX = / \(local\)$/

function writerName(label: string): string {
  return label.replace(LOCAL_SUFFIX, '')
}

const modelById = computed<Record<string, ChatModelOption>>(() =>
  Object.fromEntries(chatModels.value.map(m => [m.id, m])),
)

/**
 * The three lineups. Which models each one stands for is data
 * (devserver/config/model_register.json), and a lineup that names a model this
 * installation does not offer is short by that model rather than wrong: what
 * the platform cannot reach is not compared, and a stand-in would change the
 * question. Which models an installation CAN reach is what the backend lists
 * (chat_routes._cloud_chat_models_from_matrix): the register's models over
 * every provider it holds a key for, from the reach list
 * (devserver/config/model_providers.json) and the providers' cells
 * (devserver/hardware_matrix.json); what is recorded about a provider's data
 * path orders that list and travels with each entry. Before, the list was
 * the active provider's cells alone, and a lineup was as full as that one
 * provider's offer. Each entry carries the register's name (`register`),
 * which the lineups are written in.
 *
 * They are named the way Bias Archaeology names its own four: the bare noun
 * phrase for the group of models, the members by name in the chip's title.
 * The first two carry the difference the platform shows everywhere —
 * published weights against a model reachable only as a service — as two
 * lineups rather than as one gradient inside a single lineup, which is how it
 * stood before.
 *
 * Until 2026-09-04 every chat-capable model the installation holds stood here
 * as its own field — sixteen of them, among them the platform's own DSGVO
 * checker and a model made for writing code. Sixteen fields are a catalogue,
 * and a catalogue asks nothing.
 */
const LINEUPS = ['openWeights', 'closedWeights', 'family'] as const
const DEFAULT_LINEUP = 'openWeights'

const lineup = ref<string>('')

const lineupChoices = computed(() =>
  LINEUPS.map(id => ({
    value: id,
    label: t(`latentLab.interception.models.lineups.${id}`),
    title: t(`latentLab.interception.models.lineups.${id}Note`),
    disabled: membersOf(id).length === 0,
  })),
)

/** The models a lineup reaches on THIS installation, in the order it names
 *  them (`lineupMembers`, shared with the Canvas's ready-made workflow). */
function membersOf(id: string): string[] {
  return lineupMembers(id, chatModels.value)
}

function applyLineup(id: string) {
  const members = membersOf(id)
  if (!members.length) return
  lineup.value = id
  chosenWriters.value = members
}

/**
 * The writing models of the chosen lineup, in the lineup's own order. That
 * order is part of what a lineup says — the family runs from the smallest size
 * to the largest, and read top to bottom the rows are that gradient. Sorted by
 * name they would be three models in alphabetical order.
 */
const chosenWriterModels = computed<ChatModelOption[]>(() =>
  chosenWriters.value
    .map(id => modelById.value[id])
    .filter((m): m is ChatModelOption => !!m && m.available),
)

/**
 * What the surface opens on. The open-weights models, because they are the
 * ones a course can also run somewhere else; the other two stand beside them
 * and are one click away.
 *
 * Both the model list and the register arrive after the surface does, and the
 * lineup needs both — so this waits until a lineup can actually be filled, and
 * stops asking once one has been set by hand.
 */
watch(
  () => [chatModels.value.length, register.lineups.value] as const,
  () => {
    if (!alive || lineup.value) return
    if (membersOf(DEFAULT_LINEUP).length) applyLineup(DEFAULT_LINEUP)
  },
  { immediate: true },
)

/**
 * Which image model shows the rows to begin with. Flux 2 reads a long prompt to
 * its end, where SD 3.5 is anchored at CLIP's 77 tokens and shows what stands
 * early in the text — and what a writing model put where is exactly what is
 * being looked at here. It is a starting point and not a fixture; the list
 * stands open beside it.
 */
const IMAGE_MODEL_DEFAULT = 'flux2'

/**
 * Which image model shows the rows. It is the one column, and the reading takes
 * the width beside it.
 */
const imageModel = ref<string>(IMAGE_MODEL_DEFAULT)

// Gemini 3 Pro runs through Mammouth AI and is switched off where that account
// holds no key or no credit (docs/DEVELOPMENT_DECISIONS.md); a
// choice that holds it goes back to the one this surface opens with, further
// down, where the run is.
const { askWhenShown, accountMissing, accountParams, replaceAccountMissing } = useModelAvailability()
askWhenShown()

const imageChoices = computed(() =>
  RASTER_IMAGE_MODELS.map(m => ({
    value: m.id,
    label: m.label,
    aside: register.sizeText(m.id, t, locale.value),
    // Switched off for want of an account, the field says so on hover with the
    // same sentence as the Flow, and carries no card: the two at once are one
    // hover too many (docs/ELEMENT_STRUCTURE_REGISTRY.md, ChipSelect).
    info: accountMissing(m.id) ? undefined : register.infoFor(m.id, m.label, t),
    title: accountMissing(m.id) ? t('x2xFlow.accountMissing', accountParams(m.id)) : undefined,
    disabled: accountMissing(m.id),
  })),
)

const imageColumns = computed(() =>
  RASTER_IMAGE_MODELS.filter(m => m.id === imageModel.value).map(m => ({
    id: m.id,
    label: m.label,
  })),
)

// ---------------------------------------------------------------------------
// The rows: the line as written, then one per writing model.
// ---------------------------------------------------------------------------

/** A row of THIS instrument: the model that was asked, and the one that wrote. */
interface WriterRow extends SeriesRow {
  /** The model the chip asked for, which is not always the one that wrote. */
  requested: string
  /** The model that wrote, or the one asked for while nothing has. The card
   *  beside the head describes this one, because the head names it. */
  wrote: string
}

// ---------------------------------------------------------------------------
// The card beside a row head: what the writing model is, and where its text
// goes. The gesture and the card are the platform's own (useInfoCard,
// InfoCard); the lines are the same a model chip shows (InfoCardFacts), plus
// the size, which a chip carries in its aside, and the route, which the image
// models' chips have none of: their list (data/rasterImageModels.ts) names no
// service.
// ---------------------------------------------------------------------------

const {
  shown: rowCard,
  x: rowX,
  y: rowY,
  above: rowAbove,
  enter: enterRowCard,
  down: pressRowCard,
  up: releaseRowCard,
  close: closeRowCard,
} = useInfoCard<ChipInfo>()

/** What the card of a row says, or nothing for the line as written and for a
 *  model the list no longer carries. */
function writerInfo(row: WriterRow): ChipInfo | undefined {
  const m = row.wrote ? modelById.value[row.wrote] : undefined
  if (!m) return undefined
  const name = writerName(m.label)
  const facts = m.register || m.id
  const info = register.infoFor(facts, name, t) ?? { name }
  // No aside at a row head, so the size stands in the line here -- what is
  // known of it; the dash of the aside is for a list, not a card.
  const size = register.sizeWords(facts, t, locale.value)
  if (size) info.line = [info.line, size].filter(Boolean).join(' · ')
  if (m.service && m.service !== 'local') {
    info.route = { via: providerName(m.service), recorded: m.dsgvoRecorded }
  }
  // A card with nothing but the name repeats the head.
  return info.line || info.mark || info.route ? info : undefined
}

function onRowEnter(row: WriterRow, event: Event) { enterRowCard(writerInfo(row), event) }
function onRowDown(row: WriterRow, event: PointerEvent) { pressRowCard(writerInfo(row), event) }

/**
 * What identifies a row's work: the perspective, the line and the model that was
 * asked to write it. A line rewritten or another perspective chosen therefore
 * costs exactly what it changes, and a model taken off the list and put back
 * finds its text still there.
 */
function resultKey(modelId: string): string {
  // The reader's language belongs in here: the perspective's context reaches
  // the model in that language and travels with the request (`user_language`),
  // so a row written in one language is not the same work as the same row in
  // another. Without it a run made in German is handed back unchanged after the
  // reader switches to English.
  return `${preset.value.configId}|${locale.value}|${promptText.value.trim()}|${modelId}`
}

/**
 * The words of the perspective, where the perspective IS a list of words. A
 * perspective written as prose is an instruction and not a set of words, so
 * nothing is marked in that case.
 */
const presetTerms = computed<string[]>(() => perspectiveTerms(preset.value.context))

/**
 * A run this surface has made, frozen at what it was: its key holds the line,
 * the perspective and the language it ran under, so it goes on saying what it
 * said while the fields above it fill with the next question.
 */
interface MadeRun {
  key: string
  label: string
  requested: string
  /** The words of the perspective it ran under: the marking is that run's. */
  terms: string[]
}

/**
 * Every run this surface has made, the most recent first. A run is not deleted
 * : choosing another lineup moves what has run DOWN, and the
 * rows of the lineup now in force stand above it. The same holds when the line,
 * the perspective or the language changes, because a run is identified by all
 * four of them together (`resultKey`), and a row that no longer stands under
 * the question being asked is a row that has run.
 */
const madeRuns = ref<MadeRun[]>([])

/** What a press has made, put on top of what was made before it. */
function recordRuns(): void {
  const made: MadeRun[] = []
  for (const m of chosenWriterModels.value) {
    const key = resultKey(m.id)
    const r = series.results.value[key]
    // A refusal is a run too: on this surface it is a finding about that model,
    // and it is kept the way a written text is.
    if (!r) continue
    const ranModel = r.dispatched ? modelById.value[r.dispatched] : undefined
    made.push({
      key,
      label: ranModel ? writerName(ranModel.label) : (r.dispatched || writerName(m.label)),
      requested: m.id,
      terms: presetTerms.value,
    })
  }
  const fresh = new Set(made.map(r => r.key))
  madeRuns.value = [...made, ...madeRuns.value.filter(r => !fresh.has(r.key))]
}

const rows = computed<WriterRow[]>(() => {
  const line = promptText.value.trim()
  // The line as written, and what comes of it with no step in between. It is
  // what the rows under it are read against and cannot be switched off. The
  // reference row meets no perspective, so it is keyed by the line alone and is
  // not recomputed when another perspective is chosen.
  const out: WriterRow[] = [
    {
      key: `as-written|${line}`,
      reference: true,
      requested: '',
      wrote: '',
      label: t('latentLab.interception.models.asWritten'),
      request: null,
      text: line,
      // Nothing is marked here: this is the text the perspective never met.
      segments: markTerms(line, []),
      failedKey: '',
    },
  ]
  // What the rows of the lineup in force are keyed by. A run that stands there
  // is not repeated underneath.
  const standing = new Set<string>()
  for (const m of chosenWriterModels.value) {
    const key = resultKey(m.id)
    const r = series.results.value[key]
    // The head names the model that RAN. Where the engine routed the request to
    // another one than the chip asked for, that is what the row is.
    const ran = r?.dispatched || ''
    const ranModel = ran ? modelById.value[ran] : undefined
    standing.add(key)
    out.push({
      key,
      reference: false,
      requested: m.id,
      wrote: ran || m.id,
      label: ran ? (ranModel ? writerName(ranModel.label) : ran) : writerName(m.label),
      request: { schema: preset.value.configId, interceptionModel: m.id },
      text: r?.text ?? '',
      segments: markTerms(r?.text ?? '', presetTerms.value),
      failedKey: r?.failedKey ?? '',
    })
  }
  // Every run made before the one being asked for now, the most recent first.
  // They are read, not run: each carries the key of its own press, so it keeps
  // its text and its picture while the line, the perspective, the language or
  // the lineup above it changes.
  for (const r of madeRuns.value) {
    if (standing.has(r.key)) continue
    const res = series.results.value[r.key]
    out.push({
      key: r.key,
      reference: false,
      inert: true,
      requested: r.requested,
      wrote: res?.dispatched || r.requested,
      label: r.label,
      request: null,
      text: res?.text ?? '',
      segments: markTerms(res?.text ?? '', r.terms),
      failedKey: res?.failedKey ?? '',
    })
  }
  return out
})

// ---------------------------------------------------------------------------
// The run: the shared series, with this instrument's rows and columns.
// ---------------------------------------------------------------------------

const series = useInterceptionSeries({
  line: () => promptText.value,
  rows: () => rows.value,
  columns: () => imageColumns.value,
  sourceView: 'interception_models',
  // The model that was ASKED for. What actually wrote is recorded by the series
  // itself; where the two differ, the pair is the finding.
  context: row => ({ requested_model: (row as WriterRow).requested }),
})

/**
 * A choice switched off for want of an account goes back to the one this
 * surface opens with, at the moments useModelAvailability names, while its
 * column shows no picture: a picture that has come keeps its model's name over
 * it. A run does not send it (composables/useInterceptionSeries.ts).
 */
replaceAccountMissing(imageModel, IMAGE_MODEL_DEFAULT, {
  busy: () => series.busy.value,
  showsPictures: () => series.gridColumns.value.some(c => c.cells.some(cell => !!cell.url)),
})

onBeforeUnmount(() => {
  alive = false
  series.release()
  pageContextStore.clearContext()
})

const canRun = computed(
  () =>
    series.hasWork.value &&
    !!promptText.value.trim() &&
    !!preset.value.configId &&
    chosenWriterModels.value.length > 0 &&
    !!imageModel.value,
)

async function startRun(): Promise<void> {
  if (!canRun.value) return
  await series.startRun()
  if (!alive) return
  // What this press made goes into the record, so that the next question moves
  // it down instead of taking it off the surface.
  recordRuns()
}

// ---------------------------------------------------------------------------
// What Help is told stands here.
// ---------------------------------------------------------------------------
const pageContextStore = usePageContextStore()

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'interception_models',
  pageContent: {
    inputText: promptText.value,
    contextPrompt: preset.value.configName,
    // What Help is told about is what stands under the question being asked
    // now. A run that has moved down was made under another line, and would be
    // read as an answer to this one.
    surfaceMedia: series.gridColumns.value.flatMap(col =>
      col.cells.flatMap((cell, ri) =>
        cell.runId && cell.url && !rows.value[ri]?.inert
          ? [{ runId: cell.runId, label: `${rows.value[ri]?.label ?? ''} · ${col.label}` }]
          : [],
      ),
    ),
  },
  offer: series.gridColumns.value.some(col =>
    col.cells.some((cell, ri) => cell.url && !rows.value[ri]?.inert),
  )
    ? { label: t('compare.ask.sign') }
    : null,
}))

watch(pageContext, ctx => { pageContextStore.setPageContext(ctx) }, { immediate: true, deep: true })

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
</script>

<style scoped>
/* The page skeleton, the frame, the raster and the square cell are shared and
   stand in assets/flow-stage.css and assets/instrument-surface.css; the reading
   cell and the marked word are components/InterceptionSeriesGrid.vue. What is
   here is what this surface alone needs. */

/* The row's name, at the right end of its column and in the middle of the row.
   The element is the raster's (`head-class`), so the rule reaches into it. */
:deep(.ilm-rowname) {
  align-items: center;
  justify-content: flex-end;
}

.ilm-rowname-label {
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 132px;
}

/* A run that has moved down is another ROW, and the rows shared the height of
   the surface — so with every question the pictures and the texts got shorter
   and shorter. Where rows come
   with every press, the WIDTH leads the size of a cell and the height follows
   it: that is the platform's rule for a growing raster
   (docs/ELEMENT_STRUCTURE_REGISTRY.md, `Serienraster`), and the measure is the
   one the raster already caps itself at — the measured width of a picture
   column (`.lab-series` in assets/flow-stage.css,
   `composables/useGridCellWidth.ts`). Asked of the row as a floor as well, it
   makes a row exactly as tall as the square is wide, and a kept run costs a
   scroll instead of every picture on the surface.

   Everywhere else the whole raster stands on one screen and `.lab-plot` clips:
   this is the one surface that ACCUMULATES, and the shared rule leaves a
   surface's own scrolling with the surface. No HEIGHT is measured here —
   without a measurement there is no floor and the rows share the surface as
   they did, so no measurement comes to measure what it caused itself. */
.lab-plot {
  overflow-y: auto;
}

/* Every column carries the same floor and they all start at the same edge, so
   the rows stay level across the raster while it is scrolled. The 6px is the
   raster's own row gap. */
:deep(.lab-series) {
  min-height: calc(
    var(--lab-grid-rows) * var(--lab-grid-cell, 0px) + (var(--lab-grid-rows) - 1) * 6px
  );
}
</style>
