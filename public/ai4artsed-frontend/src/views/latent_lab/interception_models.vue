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
          <section class="cmp-column lab-prep lab-col col-fold-host" :class="{ folded }">
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
                 it is reached through says nothing about what it writes.
                 Beside them, since 2026-11-02, Custom: the models chosen one
                 by one, a drop-down each. -->
            <ChipSelect
              :model-value="lineup"
              :options="lineupChoices"
              :min-width="134"
              :disabled="series.busy.value"
              @update:model-value="v => pickLineup(v as string)"
            />
            <!-- Custom: a drop-down per writing model, in the order they were
                 added, out of what the settings offer (`offeredWriters`). The
                 row is the platform's drop-down row (`.cmp-pick-row`,
                 assets/compare-stage.css), as in the Model Comparison of the
                 Transformers Lab, here without a name in front: the heading
                 above names them all. A row is keyed by its place, so a
                 changed model keeps the drop-down and its focus; a model is
                 added by the button, so stepping through a closed drop-down
                 with the arrow keys adds nothing. -->
            <div v-if="lineup === CUSTOM" class="ilm-custom">
              <div v-for="(name, idx) in customWriters" :key="idx" class="cmp-pick-row cmp-pick-fluid">
                <select
                  :value="name"
                  :disabled="series.busy.value"
                  :aria-label="t('latentLab.interception.models.writingModelsLabel')"
                  @change="replaceCustom(idx, ($event.target as HTMLSelectElement).value)"
                >
                  <!-- A model this list holds and the settings do not offer
                       now: the drop-down names it rather than standing blank
                       over it, and the line under the list says so. -->
                  <option v-if="!offersName(name)" :value="name">{{ labelOf(name) }}</option>
                  <option
                    v-for="m in offeredWriters"
                    :key="m.id"
                    :value="writerName(m)"
                    :disabled="writerName(m) !== name && customWriters.includes(writerName(m))"
                  >{{ modelLabel(m) }}</option>
                </select>
                <button
                  type="button"
                  class="mini-btn"
                  :disabled="series.busy.value"
                  @click="removeCustom(idx)"
                >{{ t('latentLab.interception.models.lineups.customRemove') }}</button>
              </div>
              <button
                v-if="addableWriters.length"
                type="button"
                class="mini-btn ilm-custom-add"
                :disabled="series.busy.value"
                @click="addCustom"
              >{{ t('latentLab.interception.models.lineups.customAdd') }}</button>
              <p v-if="customUnreached.length" class="lab-prep-err quiet">
                {{ t('latentLab.interception.models.lineups.customNotOffered', { models: customUnreached.join(', ') }) }}
              </p>
            </div>
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
                   beside it says what that model is: who made it, how open,
                   how big. Which service it goes through the settings say. -->
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
import { ref, shallowRef, computed, watch, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePictureTemplate } from '@/composables/usePictureTemplate'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import ShellRun from '@/components/ShellRun.vue'
import ChipSelect, { type ChipInfo } from '@/components/ChipSelect.vue'
import InfoCard from '@/components/InfoCard.vue'
import InfoCardFacts from '@/components/InfoCardFacts.vue'
import { useInfoCard } from '@/composables/useInfoCard'
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
import { useModelRegister, lineupMembers, fillableLineup, bareName, isLocalModel } from '@/composables/useModelRegister'

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
  chosenModels: chatModels,
  models: everyModel,
  loading: writersLoading,
  loadFailed: writersLoadFailed,
  gpuServiceUnreachable,
  modelLabel,
} = useChatModels()

/** Which models write. They ARE the rows, under the reference row. */
const chosenWriters = ref<string[]>([])

/**
 * Each writing model stands under the line every list of language models on the
 * platform gives it (useChatModels.modelLabel): name, maker's country and year,
 * size -- at the row heads and on their card alike, or the same model would
 * carry two names. WHERE a model is installed is not in that line; it has
 * nothing to do with the question this surface asks.
 */

/**
 * The list the rows are read off: the one offered, taken over by `followList`
 * whenever no run is open. While one is, a list that arrives -- the settings
 * applied in between, an install completed -- names other ids, and rows looked
 * up in it would drop out of the run they are part of.
 */
const listInForce = shallowRef<readonly ChatModelOption[]>([])

/** The whole list beside it, for naming what ran (`knownById`), held alike. */
const everyInForce = shallowRef<readonly ChatModelOption[]>([])

/**
 * The language the rows are keyed by (`resultKey`), held alike: a language
 * switched in the header while a run is open would move every row to keys the
 * run writes nothing under, and what it wrote would not be recorded.
 */
const localeInForce = ref(locale.value)

const modelById = computed<Record<string, ChatModelOption>>(() =>
  Object.fromEntries(listInForce.value.map(m => [m.id, m])),
)

/**
 * Every model the platform lists, for naming the model that RAN: it can be
 * another than the one asked for (`dispatched`), and need not be one the
 * offered list carries, and a row is named by what wrote it. What the surface
 * offers is `modelById`.
 */
const knownById = computed<Record<string, ChatModelOption>>(() =>
  Object.fromEntries([...everyInForce.value, ...listInForce.value].map(m => [m.id, m])),
)

/** A model's line, also for one no list carries: the register's name for its id. */
/** The word a model of this platform's own machines carries at the end. */
function localWord(id: string): string {
  return isLocalModel(id) ? t('compare.shared.localModel') : ''
}

function labelOf(id: string): string {
  const m = knownById.value[id]
  return m ? modelLabel(m) : register.modelLabel(id, bareName(id), locale.value, localWord(id))
}

/**
 * The three lineups. Which models each one stands for is data
 * (devserver/config/model_register.json), and a lineup that names a model this
 * installation does not offer is short by that model rather than wrong: what
 * the platform cannot reach is not compared, and a stand-in would change the
 * question. Which models an installation CAN reach is what the settings choose
 * (useChatModels.chosenModels, since 2026-10-27): this machine's models and
 * the register's models the chosen provider reaches, through it
 * (chat_routes._chosen_chat_models). From 2026-09-12 until then it was the
 * register's models over every provider holding a key, and a lineup was
 * filled through providers nobody had chosen. Each entry carries the
 * register's name (`register`), which the lineups are written in.
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

/**
 * The fourth chip, beside the three lineups: the writing models chosen one by
 * one, a drop-down per model (2026-11-02, docs/DEVELOPMENT_DECISIONS.md). The
 * drop-downs offer the models of the list in force that can write now
 * (`listInForce`, what the settings choose); a local model still to be downloaded is not among them. A model
 * stands in one drop-down at a time, because a row is keyed by its model
 * (`resultKey`). The list opens on the lineup that was in force, and is kept
 * while another lineup is chosen.
 *
 * The list holds what a lineup holds: the register's name of a model
 * (`writerName`), not its id. An id names the provider it goes through, and
 * after a provider switch in the settings the same model is another id; the
 * list is read off the list in force again each time it arrives
 * (`resolveCustom`, `followList`), as a lineup is (`lineupMembers`).
 */
const CUSTOM = 'custom'
const customWriters = ref<string[]>([])

/** The name a model stands under in the list: the register's for a model of a
 *  provider, the id for one of this machine, which no provider switch moves
 *  and which a provider's copy of the same model must not stand in for. */
function writerName(m: ChatModelOption): string {
  return isLocalModel(m.id) ? m.id : (m.register || m.id)
}

/** What a drop-down offers: the models of the list in force that can write now. */
const offeredWriters = computed<ChatModelOption[]>(() =>
  listInForce.value.filter(m => m.available),
)

function offersName(name: string): boolean {
  return offeredWriters.value.some(m => writerName(m) === name)
}

/** What the button adds from: what no drop-down holds yet, the first of it. */
const addableWriters = computed<ChatModelOption[]>(() =>
  offeredWriters.value.filter(m => !customWriters.value.includes(writerName(m))),
)

/** The ids the list reaches in the list in force, in its order. */
function resolveCustom(names: readonly string[]): string[] {
  return names
    .map(name => offeredWriters.value.find(m => writerName(m) === name)?.id)
    .filter((id): id is string => !!id)
}

/** The models of the list that the list in force does not offer: they write no
 *  row, and the line under the list names them. */
const customUnreached = computed<string[]>(() =>
  customWriters.value.filter(name => !offersName(name)).map(name => labelOf(name)),
)

function setCustom(names: string[]): void {
  customWriters.value = names
  chosenWriters.value = resolveCustom(names)
}

function replaceCustom(idx: number, name: string): void {
  const names = [...customWriters.value]
  names[idx] = name
  setCustom(names)
}

function removeCustom(idx: number): void {
  setCustom(customWriters.value.filter((_, i) => i !== idx))
}

function addCustom(): void {
  const m = addableWriters.value[0]
  if (m) setCustom([...customWriters.value, writerName(m)])
}

const lineup = ref<string>('')

const lineupChoices = computed(() => [
  ...LINEUPS.map(id => ({
    value: id,
    label: t(`latentLab.interception.models.lineups.${id}`),
    title: t(`latentLab.interception.models.lineups.${id}Note`),
    disabled: membersOf(id).length === 0,
  })),
  {
    value: CUSTOM,
    label: t('latentLab.interception.models.lineups.custom'),
    title: t('latentLab.interception.models.lineups.customNote'),
    disabled: offeredWriters.value.length === 0,
  },
])

/** The models a lineup reaches on THIS installation, in the order it names
 *  them (`lineupMembers`, shared with the Canvas's ready-made workflow). */
function membersOf(id: string): string[] {
  return lineupMembers(id, listInForce.value)
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
 * and are one click away. Where the provider the settings choose reaches none
 * of them, the first lineup it can fill: otherwise the surface would open on
 * the line as written alone.
 *
 * Both the model list and the register arrive after the surface does, and the
 * lineup needs both — so this waits until a lineup can actually be filled. It
 * chooses again with every list that arrives, until a lineup is set by hand:
 * the list is asked for again whenever the surface is entered and after the
 * settings were applied (useChatModels), and the surface opens on the list
 * from before, which may be another provider's. A lineup set by hand stays,
 * and its members are read again off every list: an id names the provider it
 * goes through, so after a provider switch the same lineup is other ids.
 *
 * Not while a run is open: the run reads its rows to the end, and a row
 * exchanged in between would lose what was written for it -- nor before what
 * it made is recorded (`recordRuns`), which reads the rows too. The list that
 * arrived meanwhile is read once the run is closed; the watch stands under the
 * series, below.
 */
let lineupByHand = false

/** From the press until what it made is recorded (`startRun`). */
const runOpen = ref(false)

function pickLineup(id: string) {
  lineupByHand = true
  if (id === CUSTOM) {
    lineup.value = CUSTOM
    setCustom(customWriters.value.length
      ? customWriters.value
      : chosenWriters.value.map(id => (modelById.value[id] ? writerName(modelById.value[id]!) : id)))
    return
  }
  applyLineup(id)
}

function followList() {
  if (!alive || series.busy.value || runOpen.value) return
  listInForce.value = chatModels.value
  everyInForce.value = everyModel.value
  localeInForce.value = locale.value
  // A list chosen by hand keeps its models and is read off the list in force
  // again, as a lineup is; one the list does not offer writes no row, and the
  // line under the list names it (`customUnreached`).
  if (lineupByHand && lineup.value === CUSTOM) {
    const ids = resolveCustom(customWriters.value)
    if (ids.join('\n') !== chosenWriters.value.join('\n')) chosenWriters.value = ids
    return
  }
  const id = lineupByHand ? lineup.value : fillableLineup(DEFAULT_LINEUP, listInForce.value, LINEUPS)
  const members = id ? membersOf(id) : []
  if (id === lineup.value && members.join('\n') === chosenWriters.value.join('\n')) return
  lineup.value = id
  chosenWriters.value = members
}

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

// A cloud model is switched off where its provider holds no key or no credit
// (services/provider_account.py); a choice that holds it goes back to the one
// this surface opens with, further down, where the run is.
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
  /** The register's name for that model, where the row keeps it (a past run):
   *  its id names a route, and after a provider switch the lists carry the
   *  same model under another id, or none. */
  facts?: string
}

// ---------------------------------------------------------------------------
// The card beside a row head: what the writing model is. The gesture and the
// card are the platform's own (useInfoCard, InfoCard); the lines are the same a
// model chip shows (InfoCardFacts), plus the size, which a chip carries in its
// aside. Until 2026-10-27 it carried the route as well, the provider and its
// data-path mark; every model here now goes through the one provider the
// settings choose, and the settings show it.
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
 *  model the register does not know. */
function writerInfo(row: WriterRow): ChipInfo | undefined {
  if (!row.wrote) return undefined
  const m = knownById.value[row.wrote]
  const facts = row.facts || (m ? (m.register || m.id) : row.wrote)
  // The model's own name: the head says country, year and size, and the
  // card's line says them again.
  const name = register.factsFor(facts)?.name || row.label
  const info = register.infoFor(facts, name, t) ?? { name }
  // No aside at a row head, so the size stands in the line here -- what is
  // known of it; the dash of the aside is for a list, not a card.
  const size = register.sizeWords(facts, t, locale.value)
  if (size) info.line = [info.line, size].filter(Boolean).join(' · ')
  // A card with nothing but the name repeats the head.
  return info.line || info.mark ? info : undefined
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
  // reader switches to English. The language the rows are in force under, not
  // the header's: one switched while a run is open reaches the rows once the
  // run is recorded (`followList`).
  return `${preset.value.configId}|${localeInForce.value}|${promptText.value.trim()}|${modelId}`
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
  requested: string
  /** The register's name for the model that wrote it (`WriterRow.facts`). */
  facts: string
  /** The list's own name for it, for a model the register does not know. */
  listed: string
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
    // No label is kept: a run is named like every other word on the page, in
    // the language it is read in now -- the language it was WRITTEN in is in
    // its key. What is kept is what the name is made from, and no route.
    const wrote = r.dispatched || m.id
    const known = knownById.value[wrote]
    made.push({
      key,
      requested: m.id,
      facts: known ? (known.register || known.id) : wrote,
      listed: known ? known.label : bareName(wrote),
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
    standing.add(key)
    out.push({
      key,
      reference: false,
      requested: m.id,
      wrote: ran || m.id,
      label: ran ? labelOf(ran) : modelLabel(m),
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
      facts: r.facts,
      label: register.modelLabel(r.facts, r.listed, locale.value, localWord(res?.dispatched || r.requested)),
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

// The lineup follows the list (`followList`, above), and waits for a run to
// be closed: this series is the run.
watch(
  () => [chatModels.value, register.lineups.value, locale.value, series.busy.value, runOpen.value] as const,
  followList,
  { immediate: true },
)

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
  runOpen.value = true
  try {
    await series.startRun()
    if (!alive) return
    // What this press made goes into the record, so that the next question
    // moves it down instead of taking it off the surface.
    recordRuns()
  } finally {
    runOpen.value = false
  }
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

/* The whole line, wrapped: its end -- the size, and 'lokal' -- tells the
   rows apart, and an ellipsis cut exactly that. */
.ilm-rowname-label {
  max-width: 132px;
  min-width: 0;
  white-space: normal;
  overflow-wrap: break-word;
  text-align: right;
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

/* The drop-downs of Custom, one under another, the button that adds one
   under them at its own width. A select that may shrink is `.cmp-pick-fluid`
   (assets/compare-stage.css). */
.ilm-custom {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.ilm-custom-add {
  align-self: flex-start;
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
