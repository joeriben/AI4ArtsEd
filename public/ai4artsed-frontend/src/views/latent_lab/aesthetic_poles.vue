<!--
  Aesthetic Poles — the third instrument of the Prompt Interception group: one
  template, and what becomes of it when a model rewrites it by an aesthetic
  checklist that is set property by property.

  It is Guo et al.'s own step, section 3.1: the template and a set of properties
  go to a model, and the model writes a new prompt out of them. Each property
  reaches the model as the source's own line — the property's name and the word
  the slider stands at.

  ONE SLIDER, ONE HANDLE, ONE PROMPT. Every property of the
  checklist is a scale in VisionReward's tables (Xu et al., Tables 15/16) — ten
  of the eleven — and the tables give ONE ordered list per property and ONE
  position on it, never two. So the surface gives one handle per property, the
  eleven together are one setting, and one setting is one prompt. Where a handle
  stands at the word the source calls neutral, the property is not written at
  all: a line reading „ordinary" is not an instruction.

  THE ROWS GROW WITH THE SERIES. Row one is the checklist at its NEUTRAL word
  throughout — an interception like every other row's, and the reference the
  rows under it are read against; an interception happens either way, so
  blocking the neutral one would gain nothing. It stays.
  Every run adds a row for the setting it was run with, so what a session leaves
  behind is the walk through the checklist and not a single picture. A setting
  already in the series does not become a second row, and the neutral setting is
  never one: it IS row one.

  THE IMAGE MODELS ARE THE COLUMNS, chosen on the left. The writing model is the
  platform's own: what is compared down a column is the setting, so the model
  that writes has to be the same in every row.

  The two presets are still both read: they give a property's two ENDS, which is
  where „best" and „worst" put it. The frame text they share is what the
  properties are written into.

  Nothing is marked in the texts here — the green marking of the first
  instrument holds where a perspective IS a word list, and these are prose.

  The run and the raster are `composables/useInterceptionSeries.ts` and
  `components/InterceptionSeriesGrid.vue`, shared with the two other instruments
  of this group. Each property is ONE LINE: its name, its bar and the word the
  handle stands at. A marked axis cannot be one line — its layer of named places
  over the bar IS its height — and the words of these scales are too long to
  stand side by side at the column's width, so the bar carries no labels and the
  set word is read at the end of the row.
-->
<template>
  <div class="lab-page">
    <ShellRun
      :ready="canRun"
      :running="series.busy.value"
      :title="t('latentLab.interception.poles.generate')"
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
              :current="templateText"
              :disabled="series.busy.value || reading"
              @pick="applyExample"
            />
            <MediaInputBox
              chrome="bare"
              v-model:value="templateText"
              input-type="text"
              :placeholder="t('mediaInput.freePromptPlaceholder')"
              :rows="3"
              :is-filled="!!templateText"
              :is-loading="reading"
              :disabled="series.busy.value || reading"
              @copy="copyTemplate"
              @paste="pasteTemplate"
              @clear="clearTemplate"
              @image-uploaded="handlePicture"
              @image-removed="dropPicture"
            />

            <!-- The checklist. One property, one scale, one handle — and the
                 words of the scale over the bar, because what is set here IS a
                 word and not a number. -->
            <label class="lab-pick-label">{{ t('latentLab.interception.poles.dimensionsLabel') }}</label>
            <!-- The whole checklist at once. A level is one place on EVERY scale
                 — the best of them, the worst, the word the source calls
                 neutral, or halfway to either end — and from there each property
                 is moved on its own. -->
            <ChipSelect
              class="ap-levels"
              :model-value="activeLevel"
              :options="levelChoices"
              :min-width="78"
              :disabled="series.busy.value"
              @update:model-value="v => applyLevel(v as Level)"
            />
            <div class="ap-props">
              <div v-for="key in rankableKeys" :key="key" class="ap-prop">
                <span class="ap-prop-name">{{ key }}</span>
                <input
                  type="range"
                  class="lab-range ap-range"
                  :min="0"
                  :max="Math.max(0, scaleWords(key).length - 1)"
                  step="1"
                  :value="markAt(key)"
                  :disabled="series.busy.value"
                  :aria-label="key"
                  :aria-valuetext="wordAt(key)"
                  @input="onSlide(key, $event)"
                />
                <span class="ap-prop-word" :class="{ silent: markAt(key) === neutralIndex(key) }">{{
                  wordAt(key)
                }}</span>
              </div>
            </div>
            <p v-if="checklistPending" class="lab-prep-err quiet">
              {{ t('latentLab.interception.poles.checklistLoading') }}
            </p>
            <p v-else-if="!checklistArrived" class="lab-prep-err quiet">
              {{ t('latentLab.interception.poles.checklistUnavailable') }}
            </p>
            <p v-else-if="!checklistLoaded" class="lab-prep-err quiet">
              {{ t('latentLab.interception.poles.tooFewProperties') }}
            </p>

            <!-- ONE image model. What is compared here is the SETTING, so the
                 model is held still and every picture on the wall comes out of
                 the same one. -->
            <label class="lab-pick-label">{{ t('latentLab.interception.poles.imageModelLabel') }}</label>
            <ChipSelect
              :model-value="chosenImageModel"
              :options="imageChoices"
              :columns="2"
              :disabled="series.busy.value"
              @update:model-value="v => (chosenImageModel = v as string)"
            />

            <p v-if="notice" class="lab-prep-err">{{ notice }}</p>

            <aside class="lab-note">
              <h3>{{ t('latentLab.interception.tabs.interception-poles.label') }}</h3>
              <p
                v-for="(para, i) in t('latentLab.interception.poles.noteBody').split('\n\n')"
                :key="i"
              >{{ para }}</p>
              <LabReferences
                :title="t('latentLab.interception.poles.referencesTitle')"
                :items="REFERENCES"
                flat
              />
            </aside>
          </section>

          <section class="lab-plot">
            <!-- A PICTURE COMPARISON, as in Perspectives, so this surface stands on
                 the same wall its neighbour does: one image model, one picture
                 per run, large enough to be looked at, and the writing hanging
                 on the badge rather than taking a column. -->
            <InterceptionSeriesWall
              file-stem="poles"
              v-if="wallColumn"
              :rows="rows"
              :column="wallColumn"
              :lead="leadPicture"
              :not-yet-run-label="t('latentLab.interception.poles.notYetRun')"
              :adapted="series.adapted.value"
              :intercepted-label="t('latentLab.interception.poles.interceptedLabel')"
              :note="series.cellNote"
            >
              <!-- No row wears a face here: a setting has none of its own, its
                   name carries it, and the card behind it says what was set and
                   what the model wrote from it. Where the template was read from
                   a picture, that picture stands FIRST on the wall in its own
                   right, as the reference the rows are read against. -->
              <template #row-card="{ row }">
                <span v-for="line in row?.lines ?? []" :key="line">{{ line }}</span>
              </template>
            </InterceptionSeriesWall>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import ColumnFold from '@/components/ColumnFold.vue'
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import ShellRun from '@/components/ShellRun.vue'
import ChipSelect from '@/components/ChipSelect.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import { usePromptPresets } from '@/lib/promptPresets'
import InterceptionSeriesWall from '@/components/InterceptionSeriesWall.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import {
  markTerms,
  useInterceptionSeries,
  type SeriesRow,
} from '@/composables/useInterceptionSeries'
import { usePictureTemplate } from '@/composables/usePictureTemplate'
import { useConfigSelectionStore } from '@/stores/configSelection'
import {
  RASTER_IMAGE_MODELS,
  RASTER_IMAGE_MODEL_SINGLE_DEFAULT,
} from '@/data/rasterImageModels'
import { useModelAvailability } from '@/composables/useModelAvailability'
import { useModelRegister } from '@/composables/useModelRegister'

const { t, locale } = useI18n()
const register = useModelRegister()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()

/**
 * The research this rests on: the paper the PROMPT CONSTRUCTION is built after
 * and whose eleven properties these are, and the tables their scales are
 * printed in. The question asked HERE is this platform's own — what models make
 * of a normed scale — and stating it as Guo et al.'s was wrong (2026-09-05).
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'Guo et al.',
    title: '"Position: Universal Aesthetic Alignment Narrows Artistic Expression"',
    venue: 'arXiv:2512.11883',
    doi: 'https://doi.org/10.48550/arXiv.2512.11883',
  },
  {
    authors: 'Xu et al.',
    title:
      '"VisionReward: Fine-Grained Multi-Dimensional Human Preference Learning ' +
      'for Image and Video Generation"',
    venue: 'arXiv:2412.21059',
    doi: 'https://doi.org/10.48550/arXiv.2412.21059',
  },
]

/**
 * The two presets the checklist comes out of, in the order they stand. They are
 * no longer two rows: what they give this surface is a property's two ENDS —
 * the word the affirmed checklist stands at and the word its negation stands at
 * — and the frame text, which both of them print identically. Everything
 * between those two ends is on the scale as well and is set by hand.
 */
const PRESET_IDS = ['aesthetic', 'anti_aesthetic'] as const
type PresetId = (typeof PRESET_IDS)[number]

// ---------------------------------------------------------------------------
// The template.
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
 * The template can also be READ FROM A PICTURE, the same way as on Perspectives
 * on a Template and with the same composable: a picture laid in the strip at
 * the foot of the field is read as a description, and the reading stands in the
 * field, where it can be worked on further.
 */
const {
  picturePreview,
  reading,
  readingFailedKey,
  templateOrigin,
  templateFromPicture,
  showsOriginPicture,
  handlePicture,
  dropPicture,
} = usePictureTemplate(templateText)

/**
 * The picture the template was read from, first on the wall and the reference
 * every row is read against.
 *
 * When a picture is there, the picture is the reference; translating the
 * picture into a prompt and the image inference from it is the first
 * manipulation, just without a preset. So a picture
 * puts one picture MORE on the surface than a written template does, and the row
 * under it is named by the step it skipped rather than as the reference.
 *
 * It is there only while the line in the field is still the reading of that
 * picture - `showsOriginPicture` is what knows that.
 */
const leadPicture = computed(() =>
  showsOriginPicture.value && picturePreview.value
    ? {
        url: picturePreview.value,
        label: t('latentLab.interception.poles.sourcePicture'),
      }
    : null
)

// ---------------------------------------------------------------------------
// The checklist and the scales its properties are set on.
// ---------------------------------------------------------------------------

const configStore = useConfigSelectionStore()

onMounted(() => {
  if (configStore.availableConfigs.length === 0) void configStore.loadConfigs()
})

/** A multilingual field in the reader's language, with English as the fallback. */
function say(field: unknown): string {
  if (typeof field === 'string') return field
  const map = (field || {}) as Record<string, string>
  return map[locale.value] || map.en || ''
}

/** The two presets as they arrived from the config list, in their fixed order. */
const presetConfigs = computed(() =>
  PRESET_IDS.map(id => configStore.availableConfigs.find(c => c.id === id)),
)

function configOf(id: PresetId) {
  return presetConfigs.value[PRESET_IDS.indexOf(id)]
}

/** One property's scale at one preset, as the source prints it. */
interface Scale {
  scale: string[]
  neutral: string
  option: string
}

function scalesOf(id: PresetId): Record<string, Scale> {
  return configOf(id)?.dimension_scales ?? {}
}

/**
 * The order the checklist is READ in, as the preset writes it — and as a list,
 * because that is the only way it arrives. The route serialises a JSON object
 * with its keys sorted, so the order of an object does not survive the wire.
 */
function orderOf(id: PresetId): string[] {
  return configOf(id)?.dimension_order ?? []
}

/**
 * Whether a handle can be put on a property at all. Three things have to hold:
 *
 *   1. its scale has at least two places, or there is nothing to set;
 *   2. its words are DISTINCT. Two places printing the same word are one place
 *      as far as a prompt is concerned: the handle would move and the line
 *      would not change.
 *   3. BOTH presets' own option words stand on that scale, and on different
 *      places. They are where „best" and „worst" put the property, and a word
 *      that is not on the scale would send that level back to the neutral
 *      place — where it writes nothing, while the surface still shows a handle
 *      and counts the property as set.
 *
 * `Main object` fails all three of the last two at once — its scale reads
 * prominent · ordinary · prominent, so its negative end is missing and this
 * repository's own word for it (`unclear main subject`) stands nowhere on it.
 * The preset records that under `scale_note` as a defect to be re-read against
 * the table. It is the only one of the eleven that fails, and the surface names
 * it rather than letting it disappear. Condition 3 is what keeps the other two
 * from being the only thing holding this: correcting the duplicate word alone
 * would let the property back in with two levels that quietly write nothing.
 */
function settable(key: string): boolean {
  const s = scalesOf(PRESET_IDS[0])[key]
  if (!s || !Array.isArray(s.scale) || s.scale.length < 2) return false
  if (s.scale.indexOf(s.neutral) < 0) return false
  if (new Set(s.scale).size !== s.scale.length) return false
  const good = s.scale.indexOf(scalesOf(PRESET_IDS[0])[key]?.option ?? '')
  const bad = s.scale.indexOf(scalesOf(PRESET_IDS[1])[key]?.option ?? '')
  return good >= 0 && bad >= 0 && good !== bad
}

/**
 * The frame text the setting is written into, in ENGLISH whichever language the
 * surface is read in. It is an instruction to the writing model and reaches no
 * reader; the pipeline takes its context in English, and a German frame sent as
 * it stands would either be translated back by a model (a second reading of the
 * platform's own words) or run tagged as English. What the reader's language
 * does decide is the language the interception is WRITTEN in, and that travels
 * with every row as `user_language`.
 */
function frameOf(id: PresetId): string {
  const frame = configOf(id)?.context_frame
  if (typeof frame === 'string') return frame
  return (frame || {}).en || say(frame)
}

/**
 * Whether the two presets print the SAME scale for a property. One scale is
 * drawn and both presets' words are read off it as its two ends, so this is the
 * assumption that carries — and it is a fact about two files that are edited by
 * hand, not a guarantee. Today all eleven agree word for word. If one is ever
 * reordered or shortened on one side alone, the property leaves the checklist
 * here instead of putting an end at a word that is no longer under it.
 */
function sameScale(key: string): boolean {
  const a = scalesOf(PRESET_IDS[0])[key]
  const b = scalesOf(PRESET_IDS[1])[key]
  if (!a || !b) return false
  if (a.neutral !== b.neutral) return false
  if (a.scale.length !== b.scale.length) return false
  return a.scale.every((word, i) => word === b.scale[i])
}

/** The properties a handle can be put on, in checklist order. */
const rankableKeys = computed<string[]>(() =>
  orderOf(PRESET_IDS[0]).filter(key => sameScale(key) && settable(key)),
)

/** The scale a property is set on, as the source prints it. */
function scaleWords(key: string): string[] {
  return scalesOf(PRESET_IDS[0])[key]?.scale ?? []
}

/** The place on it the source calls neutral. A handle there writes no line. */
function neutralIndex(key: string): number {
  const s = scalesOf(PRESET_IDS[0])[key]
  if (!s) return 0
  const i = s.scale.indexOf(s.neutral)
  return i < 0 ? 0 : i
}

/**
 * Where a preset itself puts one property — as an index into the scale THIS
 * SURFACE draws, not into the preset's own copy of it. The two are the same
 * array as long as `sameScale` holds, and looking the word up in the drawn one
 * means a handle can never point at a place that is not on the bar.
 */
function presetIndex(id: PresetId, key: string): number {
  const option = scalesOf(id)[key]?.option
  const i = option ? scaleWords(key).indexOf(option) : -1
  return i < 0 ? neutralIndex(key) : i
}

/**
 * Where the handles stand, property by property. A property missing from this
 * map stands at its neutral word — which is to say it is not part of the run.
 */
const marks = ref<Record<string, number>>({})

/**
 * A handle held inside the scale it belongs to. An index outlives the scale it
 * was set on: a preset edited to a shorter scale would otherwise leave a handle
 * pointing past the end, which draws at the last place, prints no word, and
 * quietly writes no line while the surface still counts the property as set.
 */
function markAt(key: string): number {
  const n = scaleWords(key).length
  if (n <= 0) return 0
  const v = marks.value[key]
  if (v === undefined) return neutralIndex(key)
  return Math.max(0, Math.min(n - 1, v))
}

/** The word a property's handle stands at. */
function wordAt(key: string): string {
  return scaleWords(key)[markAt(key)] ?? ''
}

function onSlide(key: string, e: Event): void {
  setMark(key, Number((e.target as HTMLInputElement).value))
}

function setMark(key: string, index: number): void {
  marks.value = { ...marks.value, [key]: index }
}

/**
 * The five levels the whole checklist can be put at in one move. They are this
 * platform's own words and not the source's — VisionReward names the places of
 * each scale and no level across them — so they are shown in quotation marks.
 *
 * Where a scale has no room between its end and its neutral word, „better"
 * falls on „best" or „worse" on „worst". That is the scale saying it has no such
 * place, and not a rounding: it happens on the three-place scales on both sides,
 * on `Background` and `Lighting Distinction` on the bad side alone, and on
 * `Detail realism` on the good side — that last one has five places, but its
 * neutral word stands SECOND, which the preset's `scale_note` records. Across
 * the ten properties „best" and „better" still part on six of them and „worse"
 * and „worst" on five, so the five fields are five settings.
 */
const LEVELS = ['best', 'better', 'neutral', 'worse', 'worst'] as const
type Level = (typeof LEVELS)[number]

const levelChoices = computed(() =>
  LEVELS.map(l => ({ value: l, label: t(`latentLab.interception.poles.level.${l}`) })),
)

/**
 * Where one level puts one property. The two ENDS are not read off the array —
 * they are where the two presets themselves stand, the affirmed checklist and
 * its negation, so „best" and „worst" mean what the presets mean and not what
 * the order of a list happens to be. The two steps between are halfway to that
 * end, rounded away from neutral: a step landing back on the neutral word would
 * be a level that writes nothing.
 */
function levelIndex(key: string, level: Level): number {
  const n = neutralIndex(key)
  if (level === 'neutral') return n
  const best = level === 'best' || level === 'better'
  const end = presetIndex(PRESET_IDS[best ? 0 : 1] as PresetId, key)
  if (level === 'best' || level === 'worst') return end
  return end > n ? n + Math.ceil((end - n) / 2) : n - Math.ceil((n - end) / 2)
}

function applyLevel(level: Level): void {
  const out: Record<string, number> = {}
  for (const key of rankableKeys.value) out[key] = levelIndex(key, level)
  marks.value = out
}

/** Which level the checklist is standing at, if it is standing at one at all. */
const activeLevel = computed<string>(() => {
  const keys = rankableKeys.value
  if (!keys.length) return ''
  const hit = LEVELS.find(l => keys.every(key => markAt(key) === levelIndex(key, l)))
  return hit ?? ''
})

/** A property that can no longer be set cannot stay set. */
watch(rankableKeys, keys => {
  const kept = Object.fromEntries(
    Object.entries(marks.value).filter(([key]) => keys.includes(key)),
  )
  if (Object.keys(kept).length !== Object.keys(marks.value).length) marks.value = kept
})

/**
 * The lines the current setting writes, in checklist order: the property's name
 * and the word its handle stands at, both as VisionReward's tables print them.
 * A handle at the neutral word writes NOTHING — the property is then not part
 * of what this run says, and a line reading „ordinary" would be an instruction
 * where the reader meant silence.
 */
const currentLines = computed<string[]>(() => {
  const out: string[] = []
  for (const key of rankableKeys.value) {
    const at = markAt(key)
    if (at === neutralIndex(key)) continue
    const word = scaleWords(key)[at]
    if (word) out.push(`${key} — ${word}`)
  }
  return out
})

/**
 * The whole checklist at the word the source calls neutral. This is what the
 * REFERENCE row runs with: an interception like every other row's, asking of
 * each property what VisionReward's neutral option asks — „ordinary". The words
 * are the tables' own; nothing is written here that the source does not print.
 */
const neutralLines = computed<string[]>(() =>
  rankableKeys.value.flatMap(key => {
    const word = scaleWords(key)[neutralIndex(key)]
    return word ? [`${key} — ${word}`] : []
  }),
)

/**
 * The perspective a setting runs with: the preset's frame text, with the
 * properties written into the place it keeps for them. The two presets print
 * that frame identically — what separates two runs here is their property
 * lines, and nothing else — so it is read off the first of them.
 *
 * A setting that writes no line of its own runs the checklist at neutral. The
 * frame is built around its property block and says „work the following
 * properties into the description"; handing it an empty block would leave a
 * sentence pointing at nothing. And there is nothing to keep back: an
 * interception happens either way, so the row worth reading the others against
 * is the one where every property stands at its neutral word.
 */
function contextFor(lines: string[]): string {
  const frame = frameOf(PRESET_IDS[0])
  if (!frame) return ''
  const block = lines.length ? lines : neutralLines.value
  return frame.replace('{PROPERTIES}', block.join('\n'))
}

// ---------------------------------------------------------------------------
// The image models: they are the columns.
// ---------------------------------------------------------------------------

/**
 * WHICH image model. One, and only one: what is read down this wall is what the
 * checklist does, so the model is the thing held still. SD 3.5 Large is the
 * platform's single default.
 */
const chosenImageModel = ref<string>(RASTER_IMAGE_MODEL_SINGLE_DEFAULT)

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
  RASTER_IMAGE_MODELS.filter(m => m.id === chosenImageModel.value).map(m => ({
    id: m.id,
    label: m.label,
  })),
)

/** The one image model, as the run hands it over. */
const wallColumn = computed(() => series.gridColumns.value[0] ?? null)

// ---------------------------------------------------------------------------
// The rows: the template as written, then one per setting the series has run.
// ---------------------------------------------------------------------------

/** A row of THIS instrument: the checklist lines it was run with. */
interface TrialRow extends SeriesRow {
  lines: string[]
}

/**
 * The settings this series has walked through, in the order they were run. A
 * row is added when a run starts and stays; the same setting run twice is the
 * same row.
 */
const trials = ref<string[][]>([])

/**
 * What identifies a row's work: the template it was run from and the lines its
 * setting writes. A row that did not change does not run again.
 *
 * The reader's LANGUAGE is deliberately not in here. It travels with the
 * request as `user_language`, so it does decide what a row is written in — but
 * a language switch would re-key every row of a running series, and the
 * pictures already computed would vanish while the ones still coming were filed
 * under a key nothing renders. A row that has been written keeps the text it
 * was written with; that is the honest half of the trade.
 */
function trialKey(line: string, lines: string[]): string {
  return `${line}|${lines.join('¶')}`
}

/** The setting the sliders are standing at, as a row of the series would be. */
const currentKey = computed(() => trialKey(templateText.value.trim(), currentLines.value))

/**
 * Whether it is a setting the series has not walked through yet. The empty
 * setting is never one: it IS the reference row, which stands in the series
 * from the start, and a second row under the same key would be that row's work
 * claimed twice.
 */
const settingIsNew = computed(
  () =>
    currentLines.value.length > 0 &&
    !trials.value.some(had => trialKey(templateText.value.trim(), had) === currentKey.value),
)

/**
 * A series belongs to ONE template. Change the template and every row under the
 * first would stand for a comparison that was never made — and, since a row is
 * keyed by its template, one press would re-write and re-compute all of them at
 * once. So the walk starts over.
 */
watch(
  () => templateText.value.trim(),
  () => { if (trials.value.length) trials.value = [] },
)

const rows = computed<TrialRow[]>(() => {
  const line = templateText.value.trim()
  // The checklist at neutral: the reference the rows under it are read against.
  // It is keyed by the empty setting, which is the setting no run can add, so
  // it is this row and can be no other. It cannot be switched off.
  const refKey = trialKey(line, [])
  const ref = series.results.value[refKey]
  const out: TrialRow[] = [
    {
      key: refKey,
      reference: true,
      lines: [],
      label: leadPicture.value
        ? t('latentLab.interception.poles.withoutSetting')
        : t('latentLab.interception.poles.asWritten'),
      request: { schema: PRESET_IDS[0], contextPrompt: contextFor([]) },
      text: ref?.text ?? '',
      segments: markTerms(ref?.text ?? '', []),
      failedKey: ref?.failedKey ?? '',
    },
  ]
  trials.value.forEach((lines, i) => {
    const key = trialKey(line, lines)
    const r = series.results.value[key]
    out.push({
      key,
      reference: false,
      lines,
      label: t('latentLab.interception.poles.trialLabel', { n: i + 1 }),
      request: { schema: PRESET_IDS[0], contextPrompt: contextFor(lines) },
      text: r?.text ?? '',
      // Nothing is marked on this surface: the frame text is prose, not a word
      // list.
      segments: markTerms(r?.text ?? '', []),
      failedKey: r?.failedKey ?? '',
    })
  })
  return out
})

// ---------------------------------------------------------------------------
// The run: the shared series, with this instrument's rows and columns.
// ---------------------------------------------------------------------------

const series = useInterceptionSeries({
  line: () => templateText.value,
  rows: () => rows.value,
  columns: () => imageColumns.value,
  sourceView: 'aesthetic_poles',
  // The lines the setting wrote. The word at a place is what a reading months
  // later needs, and recomputing it would need the tables again. Which preset
  // supplied the frame is already recorded by the series as
  // `interception_config`, and no model is recorded as asked for: this surface
  // asks for none, and what wrote is recorded by the series itself.
  context: row => {
    const r = row as TrialRow
    // Where the template was READ, the picture and the frame are part of what
    // every row was: the same line typed by hand is a different fact about the
    // run. It is the picture the LINE came from that is recorded, not the one
    // that happens to lie in the field.
    const read =
      templateFromPicture.value && templateOrigin.value
        ? {
            template_image_path: templateOrigin.value.imagePath,
            template_frame: templateOrigin.value.frame,
          }
        : {}
    if (!r.lines.length) return read
    return { ...read, dimension_lines: r.lines }
  },
})

/**
 * A choice switched off for want of an account goes back to the one this
 * surface opens with, at the moments useModelAvailability names, while its
 * column shows no picture: a picture that has come keeps its model's name over
 * it. A run does not send it (composables/useInterceptionSeries.ts).
 */
replaceAccountMissing(chosenImageModel, RASTER_IMAGE_MODEL_SINGLE_DEFAULT, {
  busy: () => series.busy.value,
  showsPictures: () => series.gridColumns.value.some(c => c.cells.some(cell => !!cell.url)),
})

onBeforeUnmount(() => {
  series.release()
  pageContextStore.clearContext()
})

/** The last thing that went wrong, whichever of the two it was. */
const notice = computed(() =>
  readingFailedKey.value ? t(readingFailedKey.value) : series.errorMessage.value,
)

/**
 * The checklist is there, with what a run needs from it: the scales and the
 * frame text the properties are written into.
 */
const checklistArrived = computed(() => PRESET_IDS.every(id => !!frameOf(id)))

/**
 * And whether the fetch that brings them is still out. Without this the two are
 * one: the presets are absent for as long as the request is in flight, so the
 * line saying the checklist is missing stood on every fresh load of the page,
 * before anything could have gone wrong (2026-09-05).
 */
const checklistPending = computed(
  () =>
    configStore.isLoading ||
    (configStore.availableConfigs.length === 0 && !configStore.error),
)

/**
 * And a property that can be set. This is a SECOND fact and not the same one:
 * the presets can be here in full while an edit to their scales leaves nothing
 * that can be set.
 */
const checklistLoaded = computed(
  () => checklistArrived.value && rankableKeys.value.length > 0,
)

const canRun = computed(
  () =>
    // A setting the series has not walked through yet is work it cannot see:
    // the rows are what `hasWork` reads, and a slider moves none of them until
    // a run puts its setting among them. Without this, the trigger went dead
    // after the first run that computed everything, and no second setting could
    // ever become a row.
    (series.hasWork.value || settingIsNew.value) &&
    // A dropped picture is still being described. The template it will put in
    // the field is not there yet, so a run started now would be written from
    // the old line, filed under the old line's key, and then dropped when the
    // description lands and the series starts over on the new template. The
    // sibling surface with a picture field (perspectives_template.vue) holds
    // the trigger for the same reason.
    !reading.value &&
    checklistLoaded.value &&
    !!templateText.value.trim() &&
    imageColumns.value.length > 0,
)

/**
 * A run adds the setting it runs with to the series, unless the series already
 * holds it — a setting run a second time is the row it already is, and a second
 * row with the same key would be the same work claimed twice.
 */
async function startRun(): Promise<void> {
  if (!canRun.value) return
  const lines = currentLines.value
  const key = currentKey.value
  const added = settingIsNew.value
  if (added) trials.value = [...trials.value, lines]
  await series.startRun()
  // A run that wrote nothing — the safety gate refused it, the writing model
  // answered with an error or with no text, the request never arrived. The row
  // it would have been is taken back out: left standing, it would be re-sent to
  // the writing model on every later press, which is what it is there to
  // prevent. The series files an entry on every one of those exits, so what
  // says a row was written is its TEXT and never the entry.
  if (added && !series.results.value[key]?.text) {
    trials.value = trials.value.filter(had => trialKey(templateText.value.trim(), had) !== key)
  }
}

// ---------------------------------------------------------------------------
// What Help is told stands here.
// ---------------------------------------------------------------------------
const pageContextStore = usePageContextStore()

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'aesthetic_poles',
  pageContent: {
    inputText: templateText.value,
    contextPrompt: currentLines.value.join('; '),
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

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
</script>

<style scoped>
/* The page skeleton, the frame, the raster and the square cell are shared and
   stand in assets/flow-stage.css and assets/instrument-surface.css; the reading
   cell is components/InterceptionSeriesGrid.vue. What is here is what this
   surface alone needs. */

/* The checklist, one property under another. */
.ap-props {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ONE LINE per property: its name, its bar, and the word the
   handle stands at. The bar keeps a floor so it stays draggable when the two
   texts are long; the texts give way instead, and end in a point rather than
   taking a second line. */
.ap-prop {
  display: grid;
  grid-template-columns: minmax(0, auto) minmax(84px, 1fr) minmax(0, auto);
  align-items: center;
  gap: 8px;
}

/* The bar is the platform's bare axis (`.lab-range` in assets/flow-stage.css).
   What is this row's own is that it runs the full width of its track: there is
   no layer of named places to keep clear of the ends — that layer IS the
   height a marked axis takes, and this row is one line. */
.ap-range {
  width: 100%;
  margin: 0;
}

.ap-prop-name {
  min-width: 0;
  font-size: var(--flow-fs-hint);
  color: rgba(255, 255, 255, 0.55);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* The word that is set. At the neutral place it is quieter: the property is
   then not written into the prompt at all. */
.ap-prop-word {
  flex: none;
  /* Without this the item's automatic minimum is its longest word, which beats
     `max-width` and pushes the row past the column's clipped edge — the set
     word, the one thing this row exists to show, lost its tail. */
  min-width: 0;
  text-align: end;
  font-size: var(--flow-fs-hint);
  color: rgba(255, 255, 255, 0.85);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ap-prop-word.silent {
  color: rgba(255, 255, 255, 0.35);
}

/* The whole checklist at once, over the bars it sets. */
.ap-levels {
  margin-bottom: 2px;
}

</style>
