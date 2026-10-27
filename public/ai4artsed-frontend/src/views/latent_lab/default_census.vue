<!--
  Cultural (Un)Known — what the model shows when little is said, and what it
  puts in the place of knowledge when a culture IS named. The name cites
  Dewey and Bentley (`Knowing and the Known`, 1949): the known is not
  a stock of facts but what a transaction constitutes as known. That is the
  right pole for this surface, because the model never returns a blank — it
  returns something, confidently, and the columns show what.

  Built as Default Census and later moved to Comparison. The file keeps the
  name it was built with, because the id `census` does too.

  One line, and the same line with a culture or a nation put INTO it at the
  star: `a * wedding` is a Yoruba wedding, not a wedding held in a Yoruba
  context. Each of them runs on the models that were picked, so a column is not
  one picture but what several models make of the same words.

  Pick ONE model and the rows are DRAWS of it instead: five times the same
  words, five different numbers. That is the other question — how narrow one
  model's range stays when the same words are asked again (Turk, "How AI reduces
  the world to stereotypes", Rest of World 2023, 3.000 pictures over 5 prompts x
  6 countries). Which of the two questions the surface asks is the count of
  chosen models and nothing else; there is no switch for it.

  The first column is the line WITHOUT a reference and cannot be switched off.
  That is the instrument: the unmarked case is not neutral, it is already
  somebody's breakfast. Our own empty-prompt census measured the same slant at
  the other end of the scale (24:4 western-iconographic, skin tone light 22 /
  dark 1).

  A column's prompt is CONSTRUCTED and never written out: the base line with one
  reference in the place of its star, and the first column that same line with
  the star cut out. So a further column really does put one word in and change
  nothing else, which is the claim the surface makes about itself. Both of them are
  fields: the drop-down over each offers ready ones, a line written by hand runs
  just as well, and the list of references is the SAME under every base line.

  A ROW HOLDS ITS NUMBER and its model, in both modes. Two pictures side by
  side therefore differ in the reference and in nothing else — that is the
  Compare discipline, and it is what the columns are read across. ACROSS the
  rows: with several models the number is the same number everywhere and can be
  checked afterwards, but it is not the same noise — another model works in
  another space, and one reached over an interface may not use the number at
  all; what holds a column together across models is the prompt and nothing
  else. With one model the numbers differ ON PURPOSE, and there the difference
  between two rows IS the draw.

  A press computes what has no picture YET. A cell is identified by its prompt,
  its model and its seed rather than by its place, so a reference added after a
  run costs that one column and leaves everything already there standing.

  The prompts are ENGLISH and stay English: that is what the model is given, and
  the route passes the prompt through verbatim (no Prompt Interception, see
  /api/schema/pipeline/legacy). The reading in the surface's language stands
  UNDER the case and does not replace it — the same arrangement the Bias
  Archaeology uses for BBQ's sentences.

  Why a grid here, when a grid of small pictures was built and removed on
  2026-08-19 (`SegmentedFrames`, see docs/ELEMENT_STRUCTURE_REGISTRY.md): that
  removal is about a sequence in TIME, where showing every step takes away the
  question of what comes next. A series over seeds has no time direction — its
  simultaneity IS the statement, and no cell is the answer to another. The
  registry marks this case as open and to be put up separately; this is that
  case. The cells are therefore sized to be read, not thumbnails, and a click
  opens the one picture full size.
-->
<template>
  <div class="lab-page">
    <!-- `defer` is not optional: a Teleport resolves its target against the live
         document, and on the app's FIRST render the tree is still detached, so
         `.shell-bar-run` cannot be found. -->
    <ShellRun
      :ready="canRun"
      :running="running"
      :title="t('latentLab.census.generate')"
      :label="t('latentLab.runLine.image')"
      :count="done"
      :total="expected"
      @run="startRun"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <section class="lab-prep lab-col col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <!-- The platform's standard pair, twice over: the drop-down offers
                 ready ones, the field under it holds what runs and stays
                 writable — a line of one's own is a case like any other. -->
            <label class="lab-pick-label">{{ t('latentLab.census.templateLabel') }}</label>
            <PromptExamples
              :items="baseExamples"
              :current="baseLine"
              :disabled="running"
              @pick="applyBaseLine"
            />
            <!-- Three lines, not two: the symbols in the field's corner are cut
                 out of the TEXT, so the first line and a half run short and a
                 line of five words comes out on three of them in a column this
                 narrow (measured at 1000x640). The box can be pulled taller. -->
            <MediaInputBox
              chrome="bare"
              v-model:value="baseLine"
              input-type="text"
              :rows="3"
              :is-filled="!!baseLine"
              :disabled="running"
              :show-preset-button="true"
              :preset-busy="enriching === 'base'"
              @copy="copyBaseLine"
              @paste="pasteBaseLine"
              @clear="clearBaseLine"
              @open-preset-selector="openPreset('base')"
            />

            <!-- Directly under the field, never in its place: what is generated
                 is always the English above. -->
            <div v-if="needsTranslation" class="lab-tr">
              <p>{{ baseTr }}</p>
            </div>

            <!-- The same pair for the references, and the offer in it is FIXED:
                 the same references stand under every base line, so what a
                 column adds never depends on the line above it. Picking one
                 APPENDS a line instead of replacing the field, because a run
                 compares several of them at once. -->
            <label class="lab-pick-label">{{ t('latentLab.census.stepsLabel') }}</label>
            <PromptExamples
              :items="contextExamples"
              :current="contexts"
              :disabled="running"
              @pick="appendContext"
            />
            <MediaInputBox
              chrome="bare"
              v-model:value="contexts"
              input-type="text"
              :rows="5"
              :is-filled="!!contexts"
              :disabled="running"
              :show-preset-button="true"
              :preset-busy="enriching === 'contexts'"
              @copy="copyContexts"
              @paste="pasteContexts"
              @clear="clearContexts"
              @open-preset-selector="openPreset('contexts')"
            />

            <!-- Which models run. They are the ROWS, at most three; the
                 columns never change with this. Reached, the ceiling makes the
                 fields that are not on unselectable rather than invisible. -->
            <!-- The two ready sets, over the row they write into, as on the
                 Model Comparison. A set lights up again whenever the row below
                 happens to hold exactly it. -->
            <label class="lab-pick-label">{{ t('compare.setsLabel') }}</label>
            <ChipSelect
              :model-value="activeSet ?? ''"
              :options="setChoices"
              :columns="2"
              :disabled="running"
              @update:model-value="v => applySet(v as SetKey)"
            />

            <label class="lab-pick-label">{{ t('latentLab.census.modelsLabel') }}</label>
            <ChipSelect
              multiple
              :model-value="chosenModels"
              :options="modelChoices"
              :columns="2"
              :disabled="running"
              @update:model-value="v => (chosenModels = v as string[])"
            />

            <p v-if="errorMessage" class="lab-prep-err">{{ errorMessage }}</p>
            <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>

            <!-- Ohne Text kein Kasten: eine Ueberschrift ueber nichts sieht aus
                 wie ein Fehler. -->
            <aside v-if="noteText" class="lab-note">
              <h3>{{ t('latentLab.imageLab.tabs.census.label') }}</h3>
              <p>{{ noteText }}</p>
            </aside>
          </section>

          <section class="lab-plot">
            <div
              ref="gridEl"
              class="lab-grid labelled"
              :style="{
                '--lab-grid-cols': columns.length,
                '--lab-grid-rows': rows.length,
                '--lab-grid-cell': cellPx ? `${cellPx}px` : '',
              }"
            >
              <!-- Which model a row is, said once at its left end. -->
              <div class="lab-grid-col">
                <div class="lab-grid-head"></div>
                <div class="lab-series">
                  <div v-for="row in rows" :key="row.key" class="lab-grid-rowname">{{ row.label }}</div>
                </div>
              </div>
              <div v-for="col in columns" :key="col.key" class="lab-grid-col">
                <div class="lab-grid-head" :class="{ bare: !col.head }">
                  {{ col.head || (contextLines.length ? t('latentLab.census.unmarked') : '') }}
                </div>
                <div class="lab-series">
                  <!-- The platform's cell for a generated medium: the flow's
                       card with all of its functions, held to turn it over, and
                       none of the window handle (components/MediaGridCell.vue).
                       The back carries the composed prompt and the seed.

                       It stands in the platform's square surface
                       (assets/instrument-surface.css): the frame measures its
                       own grid area and the stack takes the SMALLER of its two
                       sides, so the cell is a square in a narrow column just as
                       it is in a wide one. -->
                  <div
                    v-for="(cell, ri) in col.cells"
                    :key="cell.key"
                    class="instr-frame"
                  >
                    <div class="instr-stack">
                      <MediaGridCell
                        :url="cell.url"
                        :run-id="cell.runId ?? null"
                        :prompt="col.prompt"
                        :config-id="rows[ri]?.config"
                        :created-at="cell.createdAt"
                        :model-meta="cell.modelMeta ?? null"
                        :duration-ms="cell.durationMs ?? 0"
                        :facts="[`seed ${cell.seed}`]"
                        :note="cellNote(cell)"
                        :label="rows[ri]?.label"
                        @download="downloadCell(col, cell, rows[ri])"
                      />
                    </div>
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
import ColumnFold from '@/components/ColumnFold.vue'
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { postDirectRun, postStreamedRun, serverSentence } from '@/services/directRun'
import { generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { failureKey } from '@/composables/useGenerationStream'
import ShellRun from '@/components/ShellRun.vue'
import ChipSelect from '@/components/ChipSelect.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import MediaGridCell from '@/components/MediaGridCell.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useDeviceId } from '@/composables/useDeviceId'
import { useGridCellWidth } from '@/composables/useGridCellWidth'
import { useRasterRun, uniqueLines, type RasterCell } from '@/composables/useRasterRun'
import { downloadMedia, mediaFileName, runStem } from '@/lib/downloadMedia'
import {
  RASTER_IMAGE_MODELS,
  RASTER_IMAGE_MODELS_DEFAULT,
  RASTER_IMAGE_MODEL_SETS,
} from '@/data/rasterImageModels'
import { useModelAvailability } from '@/composables/useModelAvailability'
import { useModelRegister } from '@/composables/useModelRegister'

import { STANDARD_SEED } from '@/composables/useSeedAutomatic'
import { apiBase } from '@/services/labApi'
const { t, locale } = useI18n()
const register = useModelRegister()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const deviceId = useDeviceId()

/**
 * The seed every picture is made with. It is THE PLATFORM'S number — the one
 * that stands as the default in the generation chunks
 * themselves (`schemas/chunks/output_image_sd35_large.json` and its siblings).
 * An instrument that made up its own would compare its pictures against nothing
 * anybody else can reproduce.
 *
 * ONE number, and the same one everywhere:
 * a column differs from its neighbour in the reference and in nothing else, and
 * a cell can be made again afterwards; the same seed number is what makes a
 * cell controllable.
 *
 * What it does NOT buy across the rows is shared noise — another model has
 * another latent space and another sampler, and a model behind an interface may
 * not use the number at all. The note beside the grid says so in as many words,
 * because a surface that let that pass would claim a control it does not have.
 *
 * This number is the one every row takes AS LONG AS the rows are models. Where
 * ONE model is chosen the rows are draws again (`DRAW_SEEDS`) and it goes first,
 * with four other numbers under it — a repetition series, read for how narrow
 * one model's range stays (four is the count at which a repeated fault stops
 * reading as a slip: CULTURALFRAMES re-ran its problem prompts four times and
 * found the same cultural fault in at least three of four, Nayak et al.,
 * Findings of EMNLP 2025, A.6; the fifth row is this number, which is what ties
 * the series back to the model comparison).
 */
const SEED = STANDARD_SEED

/**
 * The models this surface can put in a row, taken VERBATIM from the Model
 * Comparison instrument (views/compare/model_comparison.vue) — both of its
 * sets, in one list, each model once. This is deliberately not a second list:
 * if that instrument's
 * models change, this one follows it rather than drifting beside it.
 *
 * Having the SD generations in the same list as the current models asks the
 * sharper question — if SD 1.5, SDXL and SD 3.5 all take the desk away from the
 * same person, that is not one model's quirk.
 *
 * The path to a picture stays the platform's ordinary one and not a Latent Lab
 * configuration: what this instrument shows is what comes out of the path
 * everything else takes when a line says little, and a model chosen especially
 * for the Lab would answer a question nobody asked. It therefore does NOT go
 * through get_latent_lab_model_id() either — that resolver belongs to the
 * chunks that hold extra tensors, and this one holds none.
 *
 * SHARED (`data/rasterImageModels.ts`): the list stood here as a literal, and
 * when Interception across Models needed the same five for its columns a third
 * copy would have been the parallel structure docs/ELEMENT_STRUCTURE_REGISTRY.md
 * forbids. The list, the reasoning above it and the preselection went there
 * unchanged.
 */
const MODELS = RASTER_IMAGE_MODELS

/**
 * Which models run. They ARE the rows: one model, one row, in the order the
 * list stands in and not the order they were clicked. The CEILING of three
 * went, together with the three-model lock on the chips, when the rows
 * stopped taking their height from the surface: a row is now as
 * tall as the square is wide, so a fourth and a fifth model cost nothing where
 * the column is the narrower side, and shorten the pictures where it is not.
 *
 * It opens on the three that run on the house's own cards. Gemini 3 Pro is
 * preselected nowhere a press can multiply it: every column here is one more
 * paid call, and a run is as many calls as there are contexts plus one. The
 * ONE place where it may stand preselected is the Model Comparison, where a
 * press is one picture per model. Here it stays one click away, and its chip
 * carries the € that says what it costs.
 */
const chosenModels = ref<string[]>([...RASTER_IMAGE_MODELS_DEFAULT])

/**
 * The two ready sets over the model row, the same two the Model Comparison
 * offers. Gemini 3 Pro is taken out of them here: one press on this surface is
 * one paid call per model AND per context, which is the multiplication the note
 * over `chosenModels` names. It stays one click away in the row itself.
 */
type SetKey = keyof typeof RASTER_IMAGE_MODEL_SETS
const SETS = Object.fromEntries(
  (Object.keys(RASTER_IMAGE_MODEL_SETS) as SetKey[]).map(key => [
    key,
    RASTER_IMAGE_MODEL_SETS[key].filter(id => id !== 'gemini_3_pro_image'),
  ]),
) as Record<SetKey, string[]>

const setChoices = computed(() =>
  (Object.keys(SETS) as SetKey[]).map(key => ({
    value: key,
    label: t(`compare.presets.${key}`),
    // Which models a set holds stands in the row underneath as soon as it is
    // taken; until then it is here, so nobody has to press to find out.
    title: SETS[key]
      .map(id => MODELS.find(m => m.id === id)?.label)
      .filter(Boolean)
      .join(' \u00b7 '),
  })),
)

/** The set the row currently holds, where it holds one exactly. */
const activeSet = computed<SetKey | null>(() => {
  const now = [...chosenModels.value].sort().join('|')
  for (const key of Object.keys(SETS) as SetKey[]) {
    if ([...SETS[key]].sort().join('|') === now) return key
  }
  return null
})

function applySet(key: SetKey) {
  chosenModels.value = [...SETS[key]]
}

// Gemini 3 Pro runs through Mammouth AI and is switched off where that account
// holds no key or no credit (docs/DEVELOPMENT_DECISIONS.md); a
// choice that holds it lets it go further down, where the raster is.
const { askWhenShown, accountMissing, accountParams, leaveOutAccountMissing } = useModelAvailability()
askWhenShown()

const modelChoices = computed(() =>
  MODELS.map(m => ({
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

interface Row { key: string; label: string; seed: number; config: string }

/**
 * The five draws a single chosen model runs down. With several models the rows
 * ARE the models and they all take the platform's seed, so that what differs
 * between two rows is the model alone. With ONE model that comparison has
 * nothing left to compare, and the rows go back to what they were before the
 * models took them: the same model, the same prompt, another random number in
 * every row.
 *
 * The platform's own number stands first, so the top row is the picture the
 * model comparison shows for that model — going from three models down to one
 * keeps it and generates the four below it (cellKey holds the seed). Those
 * four are the draws this surface ran when it still had a draws mode, kept
 * rather than invented anew.
 */
const DRAW_SEEDS = [SEED, 11, 23, 47, 89]

const rows = computed<Row[]>(() => {
  const chosen = MODELS.filter(m => chosenModels.value.includes(m.id))
  if (chosen.length !== 1) {
    return chosen.map(m => ({ key: m.id, label: m.label, seed: SEED, config: m.id }))
  }
  const only = chosen[0]!
  return DRAW_SEEDS.map(s => ({
    key: `${only.id}|${s}`,
    // The number alone says nothing beside a picture, so the label reads
    // `Seed: <number>`. The word is the platform's own and reads the same in
    // every language it is set in.
    label: `${t('compare.control.seedLabel')}: ${s}`,
    seed: s,
    config: only.id,
  }))
})

/** What the note says about the rows holds for one mode each. */
/**
 * The note box states the MATTER, and the matter does not change with the row
 * mode: what the training was thin on is filled from what it was thick on. How
 * the rows and columns are built is a handling question and stands in the help
 * entry: the info box presents matters of fact and, where applicable, research
 * questions and findings, and handling explanations belong in Help. One text
 * serves both modes, so `noteBodyDraws` is gone.
 */
const noteText = computed(() => t('latentLab.census.noteBody'))

/**
 * The lines the upper drop-down offers ready-made. Each one is a whole prompt
 * and names NO culture and no country — that is what the second field adds, and
 * a base line that carried one of its own would make the columns incomparable.
 * None of them names a person category either: no occupation, no ethnicity, no
 * gender. `a person` asks for the least specified figure there is and lets the
 * model supply all of that by itself, which is the point: what a person is by
 * default, and what work is by default, are answers nobody asked for. Nothing
 * here is measured or scored, so no machine ever reads a demography off these
 * pictures — generated figures have no reference subject to be right or wrong
 * about (Luccioni et al. 2023), and what gets sorted gets sorted in the
 * conversation, which is where it belongs.
 *
 * The first line asks for the first meal of the day by DESCRIPTION, not by
 * name: the word "breakfast" carries a meal order that is not everywhere, and
 * an answer from one culture could then be blamed on the prompt. Here it
 * cannot — the model has to decide by itself what that is.
 *
 * The wedding lines run from the bare occasion to a NAMED practice. A reference
 * on its own only swaps the scenery, and a thoughtless line earns a cliché;
 * what the literature actually measures needs a named practice. CULTURALFRAMES
 * finds cultural expectations missed 44 % of the time on such prompts, and the
 * EXPLICIT ones — what the line literally says — 68 % (Nayak et al., Findings
 * of EMNLP 2025). Its 4-of-4 case is a couple receiving the parents' blessing
 * with no parents in the picture: the model shows the pair and drops the third
 * party the scene is about. The third line is that case; it was the last
 * column of the old wedding template until the columns stopped carrying
 * prompts of their own.
 *
 * `traditional clothing` is one adjective and it asks a whole question: whose
 * clothing counts as a costume, and whose counts as clothes.
 *
 * The three DRESS CODES carry the names English actually gives them — business
 * attire, formal attire, casual wear — because a dress code is
 * a thing with a name, and `business clothing` is only a paraphrase of one. The
 * two lines above it stay vague on purpose: `traditional` against `typical` is
 * the question this surface asks, and an idiom would answer it before the model
 * does. `first meal of the day` is the same rule the other way round — there
 * the idiom is AVOIDED, because `breakfast` brings an order of meals with it.
 * So the rule is not "sharper": it is precise where the thing has a name, and
 * open where the naming is what is being asked.
 *
 * `seasons in January` needs no reference at all to show itself, and answers
 * every one of them the same way (Shin et al. 2024 measured 0/50 for Stable
 * Diffusion and 0/52 for Firefly, all northern-hemisphere winter).
 *
 * The LONGER lines are written for models that take detailed prompts, Flux 3
 * Klein among them, whose model card asks for a prompt upsampler in front of
 * it; this platform leaves that upsampler out. Each longer line puts the
 * reference in more than one place, so the person, the place and what happens
 * there are asked of the same culture. `typical` stays the open word in every
 * longer line, as in the short ones.
 *
 * What a practice actually requires is NOT decided here. The surface scores
 * nothing and names no right answer; what is missing is for the people who know
 * it to say (Qadri et al. 2023).
 */
const BASE_LINES: string[] = [
  '* first meal of the day',
  '* first meal of the day, as it is typically prepared and eaten in a typical * household on an ordinary day, showing the food, the dishes and the place where it is eaten',
  'a * wedding',
  "a * wedding, groom greeting the bride's parents",
  "a * wedding, the couple in typical * wedding clothing, the groom greeting the bride's parents, at the place where a * wedding is typically held",
  'a * person',
  'a * person at work',
  'a * person at work, doing typical * work at a typical * workplace',
  'a * person in traditional clothing',
  'a * person in typical clothing',
  'a * person in typical clothing in a typical * environment',
  'a * person in typical clothing, standing in a typical * neighbourhood on an ordinary day, with the buildings and the people of the place around them',
  'a * person in casual wear',
  'a * person in formal attire',
  'a * person in business attire',
  '* seasons in January',
  'a person feeling *',
]

/**
 * The references, and each is the WORD that goes into the base line at its
 * star — `Yoruba`, `Kenyan`, `Franconian`. They carried the form
 * `in a … context` until the star took over the place and the base line took
 * over the grammar around it: the research asks a model for `a Nigerian
 * person`, and a phrase hung on the end asks it for something else.
 *
 * The list is FIXED and does not change with the line chosen above, so the same
 * references stand under every base line and a column always adds the same
 * thing. Nations and cultures stand beside one another on purpose: a state is
 * a political container and not a cultural one, and what the model does with
 * either kind of name is exactly what is on show here. Asking for a Nigerian
 * first meal of the day asks for an
 * average over practices that share no form — that is a finding of the surface, not a
 * fault in the list.
 *
 * It spans world regions rather than a handful of well-known nations, because
 * the slant this instrument is about IS a slant in coverage. Two entries are
 * this house's own — Franconian its region, German its country — and they are
 * in as the CONTROL: if a picture under one of them looks like the picture
 * under the bare line, then the bare line was already German.
 *
 * The region a group is listed under is read in the surface's language; the
 * entries themselves are not, because they go to the model verbatim.
 */
const CONTEXT_GROUPS: { region: string; entries: string[] }[] = [
  {
    region: 'westAfrica',
    entries: [
      'Yoruba',
      'Nigerian',
      'Akan',
      'Wolof',
    ],
  },
  {
    region: 'eastAfrica',
    entries: [
      'Swahili',
      'Amhara',
      'Kenyan',
      'Somali',
    ],
  },
  {
    region: 'southernAfrica',
    entries: ['Zulu', 'Shona', 'Malagasy'],
  },
  {
    region: 'northAfricaWestAsia',
    entries: [
      'Amazigh',
      'Egyptian',
      'Levantine',
      'Persian',
      'Turkish',
    ],
  },
  {
    region: 'centralAsia',
    entries: ['Kazakh', 'Uzbek', 'Mongolian'],
  },
  {
    region: 'southAsia',
    entries: [
      'Tamil',
      'Bengali',
      'Punjabi',
      'Nepali',
    ],
  },
  {
    region: 'southeastAsia',
    entries: [
      'Javanese',
      'Thai',
      'Vietnamese',
      'Filipino',
    ],
  },
  {
    region: 'eastAsia',
    entries: [
      'Han Chinese',
      'Uyghur',
      'Korean',
      'Japanese',
    ],
  },
  {
    region: 'oceania',
    entries: [
      'Māori',
      'Samoan',
      'Aboriginal Australian',
      'Papuan',
    ],
  },
  {
    region: 'northAmerica',
    entries: [
      'Diné',
      'Inuit',
      'Nahua',
      'Mexican',
    ],
  },
  {
    region: 'southAmerica',
    entries: [
      'Quechua',
      'Aymara',
      'Mapuche',
      'Brazilian',
      'Haitian',
    ],
  },
  {
    region: 'europe',
    entries: [
      'Franconian',
      'German',
      'Sámi',
      'Basque',
      'Romani',
    ],
  },
  /**
   * The emotions, and they are a different kind of word from every group above
   * them: what a culture names is a group of people, what these name is a state
   * a single person is in. Both are put in the same place of the same line, and
   * that is the point — the surface asks what a model attaches to a word that
   * says more about a person.
   *
   * The six basic emotions of Ekman & Friesen 1971, named in that order in
   * Golan, Baron-Cohen & Hill, `The Cambridge Mindreading (CAM) Face-Voice
   * Battery`, Journal of Autism and Developmental Disorders 36 (2006), 169-183,
   * p. 169, as the ones `that are recognised cross-culturally`. The words
   * themselves are the matching groups of the emotion taxonomy of Baron-Cohen,
   * Golan, Wheelwright & Hill 2004 (ibid., Fig. 1, p. 171), which the teaching
   * software `Mind Reading: The Interactive Guide to Emotions` is built on and
   * which people with autism spectrum conditions learn to tell emotions apart
   * by. That taxonomy holds 24 such groups; these six are the selection, and
   * the eighteen complex ones are left out — every one of them can be typed
   * into the field.
   *
   * `afraid` does not stand in front of `person`, which is what the base line
   * `a person feeling *` is in the list above for.
   */
  {
    region: 'emotions',
    entries: ['happy', 'sad', 'angry', 'afraid', 'surprised', 'disgusted'],
  },
]

/**
 * What stands in the references field when the instrument opens. Left empty it
 * would show the bare line alone, which is the one thing this surface cannot
 * say anything with. These two were the meal template's columns until
 * 2026-08-24.
 */
const OPENING_CONTEXTS = ['Yoruba', 'Franconian']

/**
 * What runs: one field for the base line, one for the references. Both are
 * written in, both are filled by the drop-down above them, and neither is a
 * closed list — a line of one's own runs like any other.
 */
const baseLine = ref<string>(BASE_LINES[0]!)
const contexts = ref<string>(OPENING_CONTEXTS.join('\n'))

/**
 * What is in the cells and the loop that fills them — the same driver LoRA Explorer
 * runs on (composables/useRasterRun.ts). It was built here and gathered there on
 * 2026-08-29, when the second raster instrument arrived.
 */
const {
  cells: grid,
  running,
  done,
  expected,
  start,
  recordImage,
  recordBlocked,
  recordFailed,
} = useRasterRun()

const errorMessage = ref('')

/**
 * The offer of the upper list: the base lines themselves, untranslated. A
 * translated label would name something other than what runs — the prompt goes
 * to the model verbatim, and the reading in the surface's language stands under
 * the field instead.
 */
const baseExamples = computed(() => BASE_LINES.map(x => ({ id: x, label: x, fill: [x] })))

/** The offer of the lower list, each entry under its world region. */
const contextExamples = computed(() =>
  CONTEXT_GROUPS.flatMap(g =>
    g.entries.map(x => ({
      id: x,
      label: x,
      fill: [x],
      group: t(`latentLab.census.regions.${g.region}`),
    }))
  )
)

/** One reference per line — and each becomes a column. */
const contextLines = computed<string[]>(() => uniqueLines(contexts.value))

function applyBaseLine(item: { fill: string[] }): void {
  baseLine.value = item.fill[0] ?? ''
}

/**
 * A pick APPENDS a line, it does not replace the field: the
 * field holds every reference a run is to compare, and the list is the way to
 * add one of them without typing it.
 */
function appendContext(item: { fill: string[] }): void {
  const line = item.fill[0] ?? ''
  if (!line) return
  const held = contexts.value.replace(/\s+$/, '')
  contexts.value = held ? `${held}\n${line}` : line
}

function copyBaseLine(): void { copyToClipboard(baseLine.value) }
function pasteBaseLine(): void { baseLine.value = pasteFromClipboard() }
function clearBaseLine(): void { baseLine.value = '' }
function copyContexts(): void { copyToClipboard(contexts.value) }
function pasteContexts(): void { contexts.value = pasteFromClipboard() }
function clearContexts(): void { contexts.value = '' }

/**
 * The perspective in the field's corner. A ready list over a written field and
 * the perspective in it are the platform's mandatory combination for an
 * instrument surface (docs/ELEMENT_STRUCTURE_REGISTRY.md, Rule #13). ONE
 * overlay serves both fields; which one opened it decides where the answer is
 * written back.
 */
type Field = 'base' | 'contexts'

const showPresetOverlay = ref(false)
const enriching = ref<Field | ''>('')
let presetTarget: Field = 'base'

function openPreset(which: Field): void {
  presetTarget = which
  showPresetOverlay.value = true
}

// What the ring in the corner of the field says when the perspective wrote
// nothing: a refusal, a failure with its status, an empty answer, or no
// connection (composables/useLabRun.ts). Until 2026-10-10 all four ended in
// the console here, and the ring spun and stopped in silence.
const perspectiveError = ref('')

async function handlePresetSelected(
  payload: { configId: string; context: string; configName: string }
): Promise<void> {
  showPresetOverlay.value = false
  const which = presetTarget
  const field = which === 'base' ? baseLine : contexts
  if (!field.value.trim()) return

  enriching.value = which
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, field.value, deviceId)
    if ('written' in outcome) {
      field.value = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (error) {
    perspectiveError.value = generationErrorFor(t, error)
  } finally {
    enriching.value = ''
  }
}

/**
 * The columns of a run: the base line alone first and always, then that same
 * line with ONE reference appended, one column per reference. The first is not
 * a choice — it is what the others are read against.
 *
 * The prompt of a further column is CONSTRUCTED here and never written out by
 * hand. Written ones drifted: the old wedding template dropped `in Nigeria`
 * again in its third column, added `traditional Yoruba` and turned the word
 * order around, so the surface's own sentence — every further column adds a
 * part — was false at the place it mattered most.
 */
interface Column { key: string; head: string; prompt: string; cells: RasterCell[] }

/**
 * What identifies a cell: the prompt it was made from, the model that made it,
 * and the seed. NOT its place in the grid. That is what lets a
 * press compute only what is missing — a reference added after a run gives its
 * column new keys and leaves every other cell exactly where it is, a reference
 * written again changes only its own column, and one taken away and put back
 * finds its pictures still there.
 */
function cellKey(prompt: string, config: string, seed: number): string {
  return `${config}|${seed}|${prompt}`
}

/**
 * Which indefinite article the word put in takes. The SOUND decides and not the
 * letter, which is why `Uyghur` is the one entry in the list where the two part
 * ways: `an Amhara`, `an Uzbek`, but `a Uyghur`.
 */
function article(term: string): string {
  return /^[aeiou]/i.test(term) && !/^uy/i.test(term) ? 'an' : 'a'
}

/**
 * The reference goes INTO the line, at the star, and the line around it carries
 * the grammar: `a * wedding` is a Yoruba wedding and not a wedding held in a
 * Yoruba context — the first is the thing the research asks
 * for, the second only moves the scenery. The article directly in front of the
 * star travels with the substitution.
 *
 * A line may hold the star more than once. Every star takes the same
 * reference, and every article directly in front of one travels with it.
 *
 * A line WITHOUT a star has no such place, so there is nothing to put a
 * reference into: the line then stands on its own, the further columns are not
 * built, and the run is not offered.
 */
function withReference(base: string, term: string): string {
  const ref = term.trim()
  if (!ref || !base.includes('*')) return base
  return base
    .replace(/(?:\b([Aa])n?(\s+))?\*/g, (_m, a: string | undefined, gap: string | undefined) => {
      if (!a) return ref
      const art = article(ref)
      return (a === 'A' ? art.charAt(0).toUpperCase() + art.slice(1) : art) + gap + ref
    })
    .replace(/\s{2,}/g, ' ')
    .trim()
}

/** The first column: the same line with the star cut out of it. */
function withoutReference(base: string): string {
  if (!base.includes('*')) return base
  return base.replace(/\*/g, '').replace(/\s{2,}/g, ' ').trim()
}

const columns = computed<Column[]>(() => {
  const base = baseLine.value.trim()
  const unmarked = withoutReference(base)
  // A column is keyed by the prompt it stands for, and so is every cell in it.
  // So a changed line does not have to empty the surface: what no longer
  // belongs stops being shown, and what is written back comes back with it.
  const out: Column[] = [{ key: unmarked, head: '', prompt: unmarked, cells: [] }]
  for (const line of base.includes('*') ? contextLines.value : []) {
    const prompt = withReference(base, line)
    out.push({ key: prompt, head: line, prompt, cells: [] })
  }
  return out.map(c => ({
    ...c,
    cells: rows.value.map(r => {
      const key = cellKey(c.prompt, r.config, r.seed)
      return grid.value[key] ?? { key, seed: r.seed, url: '', blockedKey: '', failed: false }
    }),
  }))
})

/**
 * A choice that holds a model switched off for want of an account lets it go
 * at the moments useModelAvailability names, where no picture of it stands in
 * the raster: a picture that has come keeps its row. A run does not send it
 * (runCell). The one model a choice of two keeps then stands in five rows of
 * its own seeds, as one chosen model always does, and the next run computes
 * the four that are new.
 */
leaveOutAccountMissing(chosenModels, RASTER_IMAGE_MODELS_DEFAULT, {
  busy: () => running.value,
  showsPictures: id =>
    columns.value.some(c => c.cells.some((cell, i) => rows.value[i]?.config === id && !!cell.url)),
})

/**
 * What stands in a cell instead of a medium. The refusal is carried as a KEY
 * until here, so a surface switched to another language after the run does not
 * keep this one cell in the old one; the reasons themselves are German
 * developer strings and are never shown raw. A failure stands as the keyed
 * cause where the platform's classifier knows the state (the queue is full,
 * the service is unreachable, the model is not installed), else as the
 * sentence the run answered with, in the wording of the route; the house
 * sentence only where the reply carried no sentence at all.
 */
function cellNote(cell: RasterCell): string {
  if (cell.blockedKey) return t(cell.blockedKey)
  if (cell.failed) {
    return cell.failedKey ? t(cell.failedKey, cell.failedParams ?? {}) : (cell.failedText || t('latentLab.census.cellFailed'))
  }
  return ''
}

/**
 * What a press would have to compute: every cell that holds no picture. A cell
 * that was refused or that nothing came back from holds none either, so it goes
 * again — a failure is not a result.
 *
 * Row by row, and the row is one model: going down the columns first would
 * change the model at every single picture and make the card load and drop the
 * weights once per cell. This way a model is loaded once and writes its whole
 * row. Where a result lands is untouched by the order — the key is prompt,
 * model and seed.
 */
const pending = computed<{ col: Column; row: Row }[]>(() =>
  rows.value.flatMap(r =>
    columns.value
      .filter(c => !grid.value[cellKey(c.prompt, r.config, r.seed)]?.url)
      .map(c => ({ col: c, row: r }))
  )
)

/**
 * A line without a star names no place for the culture, so it is not a case
 * this surface can run: every column would carry the same words, and the
 * comparison the grid is read for would be one line against itself. The
 * label over the field is where the star is asked for. A cell whose model is
 * switched off for want of an account is no work: a press would only mark it
 * (runCell).
 */
const canRun = computed(
  () =>
    !running.value &&
    !!baseLine.value.trim() &&
    baseLine.value.includes('*') &&
    pending.value.some(p => !accountMissing(p.row.config))
)

// ---------------------------------------------------------------------------
// The reading in the surface's language. It is ordered once per template and
// stands under the case; a missing translation is not a failed run.
// ---------------------------------------------------------------------------
const baseTr = ref('')
const needsTranslation = computed(() => !locale.value.startsWith('en') && !!baseTr.value)

/**
 * Which order a translation was asked in. Two quick changes of line or language
 * put two requests in the air, and the slower one may land last — with the
 * reading of a line that is no longer in the field.
 */
let trSeq = 0

async function loadTranslation(): Promise<void> {
  const seq = ++trSeq
  baseTr.value = ''
  if (locale.value.startsWith('en')) return
  const phrase = baseLine.value.trim()
  if (!phrase) return
  try {
    const baseUrl = apiBase()
    // No `cache_scope`: the permanent store keeps only the scopes named in
    // services/translation_cache.py (bbq, winobias), and a scope it does not
    // know is dropped server-side. Sending one anyway would be a value that
    // travels only to be discarded — and later read as if it had taken effect.
    // Streamed, not awaited in one silent POST: the translation is one cloud
    // model call, and the edge in front of this server cuts a request whose
    // origin has sent nothing for about 100 seconds. No `validateStatus`,
    // because the transport throws on a non-2xx exactly as `axios.post` did and
    // the catch below — which leaves the English standing — is written for that.
    const res = await postStreamedRun('/api/schema/pipeline/translate', {
      texts: [phrase],
      target_language: locale.value,
    }, { baseUrl })
    const list = res.data?.translated_texts
    if (Array.isArray(list) && typeof list[0] === 'string' && seq === trSeq) {
      baseTr.value = list[0]
    }
  } catch {
    // The English stands. Nothing is invented in its place.
  }
}

/**
 * The line is written in now, so the reading cannot be ordered at every
 * keystroke — it follows the field once the typing has come to rest.
 */
let trTimer: ReturnType<typeof setTimeout> | undefined

watch([baseLine, locale], () => {
  if (trTimer) clearTimeout(trTimer)
  trTimer = setTimeout(() => { void loadTranslation() }, 600)
})

onMounted(loadTranslation)

// ---------------------------------------------------------------------------
// The run. One cell at a time, in reading order, so a column fills as it is
// looked at and the graphics card is asked for one picture at a time.
// ---------------------------------------------------------------------------
const { gridEl, cellPx } = useGridCellWidth(() => [columns.value.length, rows.value.length])

onBeforeUnmount(() => {
  if (trTimer) clearTimeout(trTimer)
  pageContextStore.clearContext()
})

const pageContextStore = usePageContextStore()

/**
 * What Help is told stands here. The view name is what the catalogue
 * (platform_items.json) is keyed to, so the entry for this instrument reaches
 * the answer; the pictures travel as a directory of runs, one line per cell
 * that came back, and Help opens one when it is asked to.
 */
const pageContext = computed<PageContext>(() => ({
  activeViewType: 'default_census',
  pageContent: {
    inputText: baseLine.value,
    contextPrompt: contextLines.value.join(' · '),
    surfaceMedia: columns.value.flatMap((col, ci) =>
      col.cells.flatMap((cell, ri) =>
        cell.runId && cell.url
          ? [{
              runId: cell.runId,
              label: `${ci === 0 ? t('latentLab.census.unmarked') : col.head} · ${rows.value[ri]?.label ?? ''}`,
            }]
          : [],
      ),
    ),
  },
  // The same sign as the comparisons, and on the same condition: only once a
  // picture stands here.
  offer: columns.value.some(col => col.cells.some(cell => cell.url))
    ? { label: t('compare.ask.sign') }
    : null,
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

async function startRun(): Promise<void> {
  if (!canRun.value) return
  errorMessage.value = ''
  // Only what is missing, in the order `pending` puts it: one model at a time,
  // its whole row. What is already there is left alone.
  await start(pending.value, step => runCell(step.col, step.row))
}

async function runCell(col: Column, row: Row): Promise<void> {
  const seed = row.seed
  const key = cellKey(col.prompt, row.config, seed)
  // Switched off for want of an account, before the run or while it was out:
  // it is not sent. Its cell carries the sentence, and its row leaves when the
  // run ends unless a picture of the model keeps it there
  // (leaveOutAccountMissing above).
  if (accountMissing(row.config)) {
    recordFailed(key, seed, 'x2xFlow.accountMissing', undefined, accountParams(row.config))
    return
  }
  try {
    const baseUrl = apiBase()
    const res = await postDirectRun({
      prompt: col.prompt,
      output_config: row.config,
      seed,
    }, { baseUrl })
    if (!recordImage(key, seed, res.data)) {
      recordFailed(key, seed)
      return
    }
    errorMessage.value = ''
  } catch (err: unknown) {
    if (recordBlocked(key, seed, err)) return
    // Not a refusal, so nothing came through. That lands in its cell as well —
    // otherwise the hole it leaves looks exactly like a cell that has not run.
    // The cell carries the cause: the platform's keyed sentence where the
    // classifier knows the state, else the sentence the run answered with (a
    // ComfyUI node that failed, a missing model file). `unknown` is the
    // classifier's own house sentence and is not a cause, so it is not passed
    // on. The run does NOT stop: the remaining cells are worth having, and the
    // line underneath names the last reason and goes as soon as a picture
    // arrives.
    const e = err as { message?: string }
    const said = serverSentence(err)
    const why = failureKey('error', said ?? e?.message ?? '')
    recordFailed(key, seed, why === 'generationError.unknown' ? undefined : why, said)
    errorMessage.value = t('latentLab.census.runFailed', { m: generationErrorFor(t, err) })
  }
}

/** The picture of one cell onto the disk, named after what identifies it here. */
function downloadCell(col: Column, cell: RasterCell, row: Row | undefined): void {
  if (!cell.url) return
  void downloadMedia(
    cell.url,
    mediaFileName('census', [runStem(cell.runId), row?.config, col.prompt, `seed${cell.seed}`]),
  )
}

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
</script>

<style scoped>
/* The page skeleton — the column, the preparing side and its scrolling, the
   note at the top of what it explains, the error line, the plot that does not
   scroll — is shared and stands in assets/flow-stage.css (`.lab-page` /
   `.lab-prep` / `.lab-prep-err` / `.lab-plot`). It was carried here and in
   LoRA Explorer under two prefixes until 2026-08-29. Nothing of this instrument's
   own is left in this block. */

/* The raster itself — heads, row names, the series and the cap on it — is
   shared and stands in assets/flow-stage.css (`.lab-grid` / `.lab-grid-col` /
   `.lab-grid-head` / `.lab-grid-rowname` / `.lab-series`), with the measurement
   that feeds `--lab-grid-cell` in composables/useGridCellWidth.ts. It was built
   here and moved out on 2026-08-29, when LoRA Explorer needed the same thing. The
   cell is components/MediaGridCell.vue and its size the platform's square
   surface (`.instr-frame` / `.instr-stack`, assets/instrument-surface.css). */
</style>
