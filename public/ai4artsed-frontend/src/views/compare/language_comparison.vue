<template>
  <div class="lab-page lang-compare">
    <ShellRun
      :ready="canGenerate && !isGenerating"
      :running="isGenerating"
      :title="t('compare.generateAll')"
      :label="t('latentLab.runLine.image')"
      :count="done"
      :total="running ? expected : 0"
      @run="startComparison"
    />

    <!-- The asking column at the left, the raster beside it: the page skeleton
         of a raster instrument (`assets/flow-stage.css`), the one Cultural
         (Un)Known stands on two tabs over. Until 2026-09-21 this surface stood
         on the comparison stage (`assets/compare-stage.css`) with one column box
         per language, wrapping at four; since the models became ROWS it is a
         raster, and a raster stands on the screen at once, so several rows
         can be compared directly. -->
    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <section class="lab-prep lab-col col-fold-host" :class="{ folded }">
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
              :preset-busy="isEnriching"
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

            <label class="lab-pick-label">{{ t('compare.languagesLabel') }}</label>
            <LanguageChipSelector v-model="selectedLanguages" :max="4" :disabled="isGenerating" />

            <!-- The image models as fields, several at once: every one that is
                 on is a ROW of the raster. What the register knows about a
                 model - maker, year, how open the weights are - stands on its
                 card. Which models stand here is the surface's own list and is
                 unchanged; one of them at least stays on, because a raster of
                 no rows is nothing. -->
            <label class="lab-pick-label">{{ t('compare.modelsLabel') }}</label>
            <ChipSelect
              multiple
              :model-value="selectedModels"
              :options="modelChoices"
              :min-width="145"
              :disabled="isGenerating"
              @update:model-value="v => pickModels(v as string[])"
            />

            <p v-if="safetyError" class="lab-prep-err">{{ safetyError }}</p>

            <!-- Through which text parts each of the models that are on reads
                 the sentence, in the makers' own words, with the titles under
                 it: `.lab-note` at the foot of the preparing column, as on the
                 Model Comparison, and one paragraph per model that is on, so
                 the box never describes a row that is off screen. -->
            <aside v-if="noteParagraphs.length" class="lab-note">
              <h3>{{ t('compare.tabs.language') }}</h3>
              <p v-for="para in noteParagraphs" :key="para.id">{{ para.text }}</p>

              <LabReferences
                :title="t('compare.languageNote.referencesTitle')"
                :items="noteReferences"
                flat
              />
            </aside>
          </section>

          <section class="lab-plot">
            <!-- The starting number stands ABOVE the raster, as the surface's
                 own description says it does. It is one number for the whole
                 run, and it buys the same noise WITHIN a row: another model
                 works in another space, and one reached over an interface may
                 not use the number at all (see `Serienraster` in
                 docs/ELEMENT_STRUCTURE_REGISTRY.md). -->
            <p v-if="currentSeed !== null" class="cmp-seed">
              {{ t('compare.seedLabel') }}: {{ currentSeed }}
            </p>

            <!-- Rows are the models, columns are the languages: the platform's
                 raster (`.lab-grid`, assets/flow-stage.css), heads and series
                 in ONE grid so that a head wrapping to more lines - and every
                 head here carries a sentence - shortens no column on its own. -->
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
                  <div v-for="row in rows" :key="row.config" class="lab-grid-rowname">{{ row.label }}</div>
                </div>
              </div>

              <div v-for="col in columns" :key="col.langCode" class="lab-grid-col">
                <div class="lab-grid-head">
                  {{ col.langName }} <span class="lc-code">{{ col.langCode }}</span>
                  <!-- What actually went to the models of this column, and
                       under it its way back into the reader's language. It
                       stands in the HEAD because it belongs to the column: every
                       row of it was made from this sentence. Its box is the
                       platform's `.lab-case` (assets/flow-stage.css): a fixed
                       number of lines that scrolls inside, because a head that
                       grew with the prompt took the plot's height from the
                       pictures (four languages, a preset's long prompt). -->
                  <div v-if="col.translatedPrompt" class="lc-translation lab-case">
                    <div class="lc-sent">{{ col.translatedPrompt }}</div>
                    <div v-if="col.backTranslation" class="lc-back">&#x2192; {{ col.backTranslation }}</div>
                  </div>
                </div>
                <div class="lab-series">
                  <!-- The platform's cell for a generated medium
                       (components/MediaGridCell.vue), in the platform's square
                       surface (assets/instrument-surface.css). The card stands
                       while its run is out and shows the picture forming. -->
                  <div v-for="(cell, ri) in col.cells" :key="cell.key" class="instr-frame">
                    <div class="instr-stack">
                      <MediaGridCell
                        :url="cell.url"
                        media-type="image"
                        :is-executing="cellStreams[cell.key]?.isExecuting.value ?? false"
                        :progress="cellStreams[cell.key]?.generationProgress.value ?? 0"
                        :preview-image="cellStreams[cell.key]?.previewImage.value ?? null"
                        :run-id="cell.runId ?? null"
                        :prompt="col.translatedPrompt || userPrompt"
                        :config-id="rows[ri]?.config"
                        :created-at="cell.createdAt"
                        :model-meta="cell.modelMeta ?? null"
                        :duration-ms="cell.durationMs ?? 0"
                        :facts="cellFacts(cell, rows[ri]?.config)"
                        :is-favorited="!!(cell.runId && favorited[cell.runId])"
                        :note="cellNote(cell)"
                        @toggle-favorite="toggleCellFavorite(cell)"
                        @forward="forwardToPage(cell)"
                        @download="downloadCell(col, cell, rows[ri])"
                        @print="printCell(cell)"
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
import { ref, shallowRef, computed, watch, onBeforeUnmount } from 'vue'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { usePictureTemplate } from '@/composables/usePictureTemplate'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import { usePromptPresets } from '@/lib/promptPresets'
import MediaGridCell from '@/components/MediaGridCell.vue'
import ShellRun from '@/components/ShellRun.vue'
import ChipSelect from '@/components/ChipSelect.vue'
import LanguageChipSelector from '@/components/LanguageChipSelector.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import { failureKey, safetyBlockKey, useGenerationStream, type GenerationResult } from '@/composables/useGenerationStream'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { useFavoritesStore } from '@/stores/favorites'
import { useDeviceId } from '@/composables/useDeviceId'
import { useGridCellWidth } from '@/composables/useGridCellWidth'
import { useRasterRun, type RasterCell } from '@/composables/useRasterRun'
import { downloadMedia, mediaFileName, runStem } from '@/lib/downloadMedia'
import { postStreamedRun } from '@/services/directRun'
import { generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { useSafetyEventStore } from '@/stores/safetyEvent'
import { handOverImage } from '@/lib/handOverImage'
import { printMedia } from '@/lib/printMedia'
import { useModelRegister } from '@/composables/useModelRegister'
import { RASTER_IMAGE_MODELS, type RasterImageModel } from '@/data/rasterImageModels'
import { useModelAvailability } from '@/composables/useModelAvailability'
// The page skeleton, the raster and `.lab-pick-label` live here. Pulled in by
// name rather than through whichever component happens to import it today.
import { apiBase } from '@/services/labApi'

const { t, locale } = useI18n()
const router = useRouter()
const userPreferences = useUserPreferencesStore()
const favoritesStore = useFavoritesStore()
const deviceId = useDeviceId()
const register = useModelRegister()

// --- State ---
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
const selectedLanguages = ref<string[]>(['en', 'ar'])

/**
 * The image models this surface can put in a row: the platform's raster list
 * (`data/rasterImageModels.ts`, with its names), cut to the three this surface
 * offered when it ran one model at a time, plus SD 3.5 Large Turbo. Turbo
 * stands in no other raster and therefore not in the shared list; it stays
 * here because it reads the prompt through the same three text encoders as
 * SD 3.5 Large and still makes different pictures. These are OUTPUT CONFIG
 * ids, not model identifiers: which weights an id reaches is the config's
 * business.
 */
const TURBO: RasterImageModel = { id: 'sd35_large_turbo', label: 'SD 3.5 Large Turbo (fast)' }
const LANGUAGE_MODEL_IDS: readonly string[] = ['sd35_large', TURBO.id, 'flux2', 'gemini_3_pro_image']
const availableModels: RasterImageModel[] = LANGUAGE_MODEL_IDS.flatMap(id => {
  const m = id === TURBO.id ? TURBO : RASTER_IMAGE_MODELS.find(x => x.id === id)
  return m ? [m] : []
})

/**
 * Where the model runs behind an interface that takes no seed, the card back
 * names none: the Gemini chunk sends the prompt and a size and nothing else
 * (devserver/schemas/chunks/output_image_gemini_3_pro.json), so the number
 * drawn for the run never reached that picture.
 */
const NO_SEED: ReadonlySet<string> = new Set(['gemini_3_pro_image'])

/**
 * Which models run. They ARE the rows, in the order the list stands in and
 * not the order they were clicked, as on Cultural (Un)Known. It opens on the
 * two whose text parts differ in kind - SD 3.5 Large with its three encoders,
 * FLUX.2 with its language model - so that the first press already puts the
 * two ways of reading a sentence under each other. Gemini 3 Pro stands in no
 * preselection that a press multiplies, because of cost: a row of it is one
 * paid call per language.
 */
const OPENING_MODELS = ['sd35_large', 'flux2']
const selectedModels = ref<string[]>([...OPENING_MODELS])

/** A field goes on and off; the last one stays on. A raster of no rows is nothing. */
function pickModels(next: string[]) {
  if (next.length < 1) return
  selectedModels.value = next
}

const isGenerating = ref(false)
const currentSeed = ref<number | null>(null)
const showPresetOverlay = ref(false)
const isEnriching = ref(false)
const safetyError = ref('')
const safetyStore = useSafetyEventStore()

// Gemini 3 Pro runs through Mammouth AI and is switched off where that account
// holds no key or no credit (docs/DEVELOPMENT_DECISIONS.md); a
// choice that holds it lets it go further down, where the cells are.
const { askWhenShown, accountMissing, accountParams, leaveOutAccountMissing } = useModelAvailability()
askWhenShown()

/** The same list as fields, with the register's card on each of them. */
const modelChoices = computed(() =>
  availableModels.map(m => ({
    value: m.id,
    label: m.label,
    aside: register.sizeText(m.id, t, locale.value),
    // Switched off for want of an account, the field says so on hover, as in
    // the Flow, and carries no card: the two at once are one
    // hover too many (docs/ELEMENT_STRUCTURE_REGISTRY.md, ChipSelect).
    info: accountMissing(m.id) ? undefined : register.infoFor(m.id, m.label, t),
    title: accountMissing(m.id) ? t('x2xFlow.accountMissing', accountParams(m.id)) : undefined,
    disabled: accountMissing(m.id),
  })),
)

interface Row { config: string; label: string }

const rows = computed<Row[]>(() =>
  availableModels
    .filter(m => selectedModels.value.includes(m.id))
    .map(m => ({ config: m.id, label: m.label })),
)

/**
 * What the note box says about each row: through which text parts that model
 * reads the sentence, in its maker's words. One paragraph per model that is
 * on, in row order, so the box and the raster read the same way down.
 */
const noteParagraphs = computed(() =>
  rows.value.map(r => ({ id: r.config, text: t(`compare.languageNote.noteBody.${r.config}`) })),
)

/**
 * The publications the note rests on, per model: what the paragraph quotes or
 * reports from, and nothing else - ONLY TITLES THE NOTE ACTUALLY USES
 * (docs/ELEMENT_STRUCTURE_REGISTRY.md, LabReferences). Web sources carry their
 * host and date in `venue`, as the Model Comparison writes them.
 */
const NOTE_REFERENCES: Record<string, LabReference[]> = {
  sd35_large: [
    {
      authors: 'Radford, A., Kim, J. W., Hallacy, C. et al. (2021)',
      title: 'Learning Transferable Visual Models From Natural Language Supervision',
      venue: 'ICML 2021',
      doi: 'https://doi.org/10.48550/arXiv.2103.00020',
    },
    {
      authors: 'Cherti, M., Beaumont, R., Wightman, R. et al. (2023)',
      title: 'Reproducible scaling laws for contrastive language-image learning',
      venue: 'CVPR 2023',
      doi: 'https://doi.org/10.48550/arXiv.2212.07143',
    },
    {
      authors: 'Raffel, C., Shazeer, N., Roberts, A. et al. (2020)',
      title: 'Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer',
      venue: 'Journal of Machine Learning Research 21 (140)',
      doi: 'https://doi.org/10.48550/arXiv.1910.10683',
    },
    {
      authors: 'Esser, P., Kulal, S., Blattmann, A. et al. (2024)',
      title: 'Scaling Rectified Flow Transformers for High-Resolution Image Synthesis',
      venue: 'ICML 2024',
      doi: 'https://doi.org/10.48550/arXiv.2403.03206',
    },
  ],
  sd35_large_turbo: [
    {
      authors: 'Stability AI (2024)',
      title: 'Stable Diffusion 3.5 Large Turbo, model card',
      venue: 'huggingface.co/stabilityai/stable-diffusion-3.5-large-turbo',
    },
    {
      authors: 'Stability AI (2024)',
      title: 'Introducing Stable Diffusion 3.5',
      venue: 'stability.ai, 22 October 2024',
    },
  ],
  flux2: [
    {
      authors: 'Black Forest Labs (2025)',
      title: 'FLUX.2: Frontier Visual Intelligence',
      venue: 'bfl.ai, 25 November 2025',
    },
  ],
  gemini_3_pro_image: [
    {
      authors: 'Google (2025)',
      title: 'Introducing Nano Banana Pro',
      venue: 'blog.google, 20 November 2025',
    },
  ],
}

const noteReferences = computed<LabReference[]>(() => {
  const out: LabReference[] = []
  for (const r of rows.value) {
    for (const ref of NOTE_REFERENCES[r.config] ?? []) {
      if (!out.some(o => o.title === ref.title)) out.push(ref)
    }
  }
  return out
})

/**
 * What went to the models of a column and its way back, keyed by language.
 * Set per press: the sentence is translated afresh every run, so a column's
 * translation belongs to the run whose pictures stand under it.
 */
const translations = ref<Record<string, { sent: string; back: string }>>({})

/**
 * The run: what is in the cells, what the loop still has to compute, the
 * counter, and the drop of a run when the surface is left
 * (composables/useRasterRun.ts). What this surface keeps for itself is what
 * its rows and columns ARE, what a cell is keyed by, and how a cell is computed.
 */
const { cells, running, done, expected, start, live, recordImage, recordBlocked, recordFailed } = useRasterRun()

/**
 * A choice that holds a model switched off for want of an account lets it go
 * at the moments useModelAvailability names, where its row shows no picture of
 * the run on screen: a picture that has come keeps its row. A run does not
 * send it (runCell), and a press needs a row a run sends (canGenerate).
 */
leaveOutAccountMissing(selectedModels, OPENING_MODELS, {
  busy: () => isGenerating.value,
  showsPictures: rowShowsPicture,
})

/** Whether the row of a model shows a picture of the run on screen. */
function rowShowsPicture(id: string): boolean {
  const seed = currentSeed.value
  return seed != null && selectedLanguages.value.some(lang => !!cells.value[cellKey(id, lang, seed)]?.url)
}

/**
 * One stream per cell of the run that is out, keyed like the cell: the card
 * shows the picture forming from it. Created with the run, as this surface
 * always did per column. A SHALLOW ref: the streams keep their own refs, which
 * the template reads by `.value`, and the map is replaced whole at each press.
 */
const cellStreams = shallowRef<Record<string, ReturnType<typeof useGenerationStream>>>({})

/** Which pictures of this surface are in the favourites, by run. */
const favorited = ref<Record<string, boolean>>({})

/**
 * What identifies a cell: the model that made it, the language it was made in,
 * and the seed of the run. Not its place in the raster. The seed is drawn per
 * press, so a new press gives every cell a new key and the raster starts from
 * empty plates, as this surface always did.
 */
function cellKey(config: string, lang: string, seed: number | null): string {
  return `${config}|${seed ?? 'none'}|${lang}`
}

interface Column {
  langCode: string
  langName: string
  translatedPrompt: string
  backTranslation: string
  cells: RasterCell[]
}

const LANGUAGE_NAMES: Record<string, string> = {
  en: 'English', de: 'Deutsch', ar: 'العربية', he: 'עברית',
  tr: 'Türkçe', ko: '한국어', uk: 'Українська', fr: 'Français',
  es: 'Español', bg: 'Български', hsb: 'Hornjoserbšćina',
  dsb: 'Dolnoserbšćina', fry: 'Frysk', yo: 'Yorùbá', sw: 'Kiswahili',
  cy: 'Cymraeg', qu: 'Runasimi', hi: 'हिन्दी', ja: '日本語', zh: '中文',
}

/**
 * One column per chosen language, in the order they were chosen, each with
 * one cell per row. A cell that has no result yet is an empty plate.
 */
const columns = computed<Column[]>(() =>
  selectedLanguages.value.map(code => ({
    langCode: code,
    langName: LANGUAGE_NAMES[code] || code,
    translatedPrompt: translations.value[code]?.sent ?? '',
    backTranslation: translations.value[code]?.back ?? '',
    cells: rows.value.map(r => {
      const key = cellKey(r.config, code, currentSeed.value)
      return cells.value[key] ?? { key, seed: currentSeed.value ?? 0, url: '', blockedKey: '', failed: false }
    }),
  })),
)

/** What the cell says instead of a picture, in the reader's language. */
function cellNote(cell: RasterCell): string {
  if (cell.blockedKey) return t(cell.blockedKey)
  if (cell.failed) {
    return cell.failedKey ? t(cell.failedKey, cell.failedParams ?? {}) : (cell.failedText || t('generationError.unknown'))
  }
  return ''
}

/**
 * What tells two of these runs apart, on the back of the cell: the seed, the
 * size it came in, and how long the model computed. The last two used to
 * stand under the picture in expert mode and have a card back to live on
 * since 2026-08-25.
 */
function cellFacts(cell: RasterCell, config?: string): string[] {
  const out: string[] = []
  if ((cell.url || cell.blockedKey || cell.failed) && !(config && NO_SEED.has(config))) out.push(`seed ${cell.seed}`)
  const res = cell.modelMeta?.recommended_resolution
  if (res) out.push(String(res))
  const ms = cell.durationMs ?? 0
  if (ms) out.push(`${(ms / 1000).toFixed(1)} s`)
  return out
}

/**
 * A press needs a prompt, two languages and a row a run sends: a model
 * switched off for want of an account that stays chosen for its pictures is
 * not one.
 */
const canGenerate = computed(() => {
  return userPrompt.value.trim().length > 0 && selectedLanguages.value.length >= 2 &&
    rows.value.some(r => !accountMissing(r.config))
})

// --- Clipboard ---
function copyPrompt() { window.navigator.clipboard.writeText(userPrompt.value) }
async function pastePrompt() { userPrompt.value = await window.navigator.clipboard.readText() }
function clearPrompt() { userPrompt.value = '' }

/**
 * What this page can be asked, ready to pick. One entry so far: the prompt the
 * comparison pages have always shown behind their own field as the example.
 */
const promptExamples = usePromptPresets(['street'])

function applyExample(item: { fill: string[] }) {
  userPrompt.value = item.fill[0] ?? ''
}

// --- Cell actions (events from the cell) ---
async function toggleCellFavorite(cell: RasterCell) {
  if (!cell.runId) return
  const success = await favoritesStore.toggleFavorite(cell.runId, 'image', deviceId, 'anonymous', 'compare')
  if (success) {
    favorited.value = { ...favorited.value, [cell.runId]: !favorited.value[cell.runId] }
  }
}

function forwardToPage(cell: RasterCell) {
  if (!cell.url) return
  const runIdMatch = cell.url.match(/\/api\/.*\/(.+)$/)
  handOverImage(cell.url, runIdMatch ? runIdMatch[1] : null)
  router.push('/x2x-flow')
}

/** Printing goes the platform's way: the picture in its own window, which prints itself. */
function printCell(cell: RasterCell) {
  printMedia(cell.url)
}

/** The picture of one cell onto the disk, named after what identifies it here. */
function downloadCell(col: Column, cell: RasterCell, row: Row | undefined): void {
  if (!cell.url) return
  void downloadMedia(
    cell.url,
    mediaFileName('compare', [runStem(cell.runId), row?.config, col.langCode, `seed${cell.seed}`]),
  )
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

  isEnriching.value = true
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
    isEnriching.value = false
  }
}

// --- What Help is told ---
interface RanWith { prompt: string; langs: string[]; models: string[]; seed: number }
/** What the last run that went through all its cells was set up with: the
    prompt as it stood when the translations began, the languages, the models
    and the seed. */
const ranWith = shallowRef<RanWith | null>(null)

/** Of that run, the languages and models still chosen, in the order of the
    columns and the rows: the fields above stay writable, and a column or a row
    leaves with its language or its model. What Help is told about the run
    (`instrumentRuns`) is built from this and from the cells of the run while
    one of its languages and one of its models are chosen; a later run that
    goes through all its cells takes its place. */
const ranShown = computed<RanWith | null>(() => {
  const run = ranWith.value
  return run && {
    ...run,
    langs: selectedLanguages.value.filter(code => run.langs.includes(code)),
    models: run.models.filter(id => selectedModels.value.includes(id)),
  }
})

function buildContext(phase: string, run: RanWith): string {
  const langName = (code: string) => LANGUAGE_NAMES[code] || code
  const label = (id: string) => availableModels.find(m => m.id === id)?.label ?? id
  const langList = run.langs.map(code => `${langName(code)} (${code})`).join(', ')
  const modelList = run.models.map(label).join(', ')
  const all = run.langs.flatMap(lang => run.models.map(id => ({ lang, id, cell: cells.value[cellKey(id, lang, run.seed)] })))
  const results = all.filter(c => c.cell?.url).length
  const blocked = all
    .filter(c => c.cell?.blockedKey)
    .map(c => `${langName(c.lang)} · ${label(c.id)}`)
    .join(', ')
  return `[Language Comparison — ${phase}]\nPrompt: "${run.prompt}"\nLanguages: ${langList}\nModels: ${modelList}\nSeed: ${run.seed}\nImages generated: ${results}/${all.length}${blocked ? `\nBlocked: ${blocked}` : ''}`
}

const comparisonContext = computed(() => (ranShown.value ? buildContext('generation_complete', ranShown.value) : ''))

// --- Main generation flow ---
async function startComparison() {
  if (!canGenerate.value || isGenerating.value) return
  isGenerating.value = true
  safetyError.value = ''

  const baseUrl = apiBase()

  // Stage 2 Jugendschutz gate — check original prompt before translation/generation. The platform's perspective call,
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

  // The gate has passed. The translations come first, one cloud call per
  // language, and only when all of them are in does the run before give way:
  // a fresh seed gives every cell of this run a new key, so the raster stands
  // as empty plates until the pictures arrive. A translation that fails leaves
  // the run before standing and says so under the fields, with its cause.
  const langCodes = [...selectedLanguages.value]
  const runRows = [...rows.value]
  const ranPrompt = userPrompt.value
  const sentences: Record<string, { sent: string; back: string }> = {}
  const seed = Math.floor(Math.random() * 4294967296)

  try {
    // Step 1: Translate to ALL selected languages (no source detection —
    // user may type in any language; LLM auto-detects source)
    for (const lang of langCodes) {
      // Streamed, not awaited in one silent POST: each translation is one cloud
      // model call and they run one after another, and the edge in front of this
      // server cuts a request whose origin has sent nothing for about 100
      // seconds. Every status resolves, because the failure below is handled
      // HERE — it stops the run without reaching the outer catch, which does
      // something else.
      const res = await postStreamedRun('/api/schema/pipeline/translate', {
        text: userPrompt.value, target_language: lang,
      }, { baseUrl, validateStatus: () => true })
      if (res.status >= 400) {
        safetyError.value = t('compare.translationFailed', { lang: LANGUAGE_NAMES[lang] || lang, cause: `HTTP ${res.status}` })
        isGenerating.value = false
        return
      }
      const data = res.data
      if (data.status === 'success' && data.translated_text) {
        sentences[lang] = { sent: data.translated_text, back: '' }
      } else {
        safetyError.value = t('compare.translationFailed', { lang: LANGUAGE_NAMES[lang] || lang, cause: data.error || data.status || `HTTP ${res.status}` })
        isGenerating.value = false
        return
      }
    }
    translations.value = sentences
    currentSeed.value = seed

    // Back-translate to settings language (non-blocking)
    const uiLang = userPreferences.language
    for (const lang of langCodes) {
      const sent = translations.value[lang]?.sent ?? ''
      if (lang === uiLang) {
        translations.value = { ...translations.value, [lang]: { sent, back: sent } }
        continue
      }
      // Streamed for the same reason as the translation above, and left running
      // beside the generation exactly as before: nothing waits for it. It lands
      // only under the sentence it was made from — a later press has drawn new
      // sentences by the time a slow one comes back.
      postStreamedRun('/api/schema/pipeline/translate', {
        text: sent, target_language: uiLang,
      }, { baseUrl, validateStatus: () => true }).then(({ data }) => {
        if (data.status === 'success' && data.translated_text && translations.value[lang]?.sent === sent) {
          translations.value = { ...translations.value, [lang]: { sent, back: data.translated_text } }
        }
      }).catch(() => { /* non-critical */ })
    }

    // Comparison group ID for linking runs
    const groupId = `cmp_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`

    // Step 2: the plan, ROW BY ROW - one model at a time, its whole row - so a
    // model is loaded once and writes all its languages, instead of the card
    // loading and dropping the weights at every single picture. One stream
    // per cell, so the card shows each picture forming.
    const plan = runRows.flatMap(row => langCodes.map(lang => ({ row, lang })))
    cellStreams.value = Object.fromEntries(
      plan.map(step => [cellKey(step.row.config, step.lang, seed), useGenerationStream()]),
    )
    let n = 0
    await start(plan, step => runCell(step.row, step.lang, seed, groupId, baseUrl, n++))
    if (!live()) return

    // Nothing is described here any more. Every run used to be sent through a
    // VLM the moment it finished -- three readings per comparison, unasked --
    // and since 2026-08-23 it is known that the wording of that call came back
    // empty from the model every single time, so the agent beside the grid was
    // told about three pictures and given nothing of them. It reads them itself
    // now, and only when it is asked to.
    ranWith.value = { prompt: ranPrompt, langs: langCodes, models: runRows.map(r => r.config), seed }

    // POST comparison context to each successful run
    const allTranslations = langCodes.map(lang => ({
      language: lang,
      translated: translations.value[lang]?.sent ?? '',
      back_translation: translations.value[lang]?.back ?? '',
    }))
    for (const step of plan) {
      const cell = cells.value[cellKey(step.row.config, step.lang, seed)]
      if (!cell?.runId || !cell.url) continue
      fetch(`${baseUrl}/api/schema/pipeline/run/${cell.runId}/context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          comparison_context: {
            original_prompt: userPrompt.value,
            languages: langCodes,
            seed,
            model: step.row.config,
            models: runRows.map(r => r.config),
            this_language: step.lang,
            translated_prompt: translations.value[step.lang]?.sent ?? '',
            back_translation: translations.value[step.lang]?.back ?? '',
            all_translations: allTranslations,
          }
        })
      }).catch(() => { /* fire-and-forget */ })
    }
  } catch (e) {
    console.error('[COMPARE] Failed:', e)
  } finally {
    isGenerating.value = false
  }
}

/**
 * One cell: the sentence of its column, in that column's language, to the
 * model of its row, at the seed of the run - the same streamed path the flow
 * takes, with the translation to English switched off so that the language IS
 * what reaches the model.
 */
async function runCell(row: Row, lang: string, seed: number, groupId: string, baseUrl: string, n: number): Promise<void> {
  const key = cellKey(row.config, lang, seed)
  const stream = cellStreams.value[key]
  if (!stream) return
  // Switched off for want of an account, before the run or while it was out:
  // it is not sent. Its cell carries the sentence, and its row leaves when the
  // run ends unless a picture of the model keeps it there
  // (leaveOutAccountMissing above).
  if (accountMissing(row.config)) {
    recordFailed(key, seed, 'x2xFlow.accountMissing', undefined, accountParams(row.config))
    return
  }
  const sent = translations.value[lang]?.sent || userPrompt.value
  try {
    const result: GenerationResult = await stream.executeWithStreaming({
      prompt: sent,
      output_config: row.config,
      seed,
      skip_stage3_translation: true,
      device_id: `${deviceId}_cmp${n}`,
      source_view: 'compare',
      comparison_group_id: groupId,
      comparison_language: lang,
      comparison_original_prompt: userPrompt.value,
    })
    if (!live()) return

    if (result.status === 'success' && result.media_output?.url) {
      recordImage(key, seed, {
        media_output: { ...result.media_output, url: `${baseUrl}${result.media_output.url}` },
        run_id: result.run_id,
        model_meta: stream.modelMeta.value,
        duration_ms: stream.stage4DurationMs.value,
      })
    } else if (result.status === 'blocked') {
      // A refusal, at the cell it refused. `recordBlocked` reads the reason
      // out of the reply; a refusal that carries none still has to read as one,
      // so it lands with the platform's general sentence for a refused prompt.
      if (!recordBlocked(key, seed, result)) {
        recordFailed(key, seed, safetyBlockKey(result.blocked_reason, result.blocked_stage))
      }
    } else {
      // error, cancelled, busy, and a success that carried no picture: all
      // four are a hole in the row, and a cell left untouched would keep the
      // empty plate of one still to come while the count stayed short.
      recordFailed(key, seed, failureKey(result.status, result.error || '', result.busy))
    }
  } catch (e) {
    console.error(`[COMPARE] Generation for ${row.config} / ${lang} failed:`, e)
    if (!live()) return
    recordFailed(key, seed, failureKey('error', e instanceof Error ? e.message : String(e)))
  }
}

const { gridEl, cellPx } = useGridCellWidth(() => [columns.value.length, rows.value.length])

const pageContextStore = usePageContextStore()

/** What Help is told stands here: one line per finished picture, the language
 *  and the model it was made with and the run's id. Not the pictures — it
 *  opens one when somebody asks it to. */
const surfaceMedia = computed(() =>
  columns.value.flatMap(col =>
    col.cells.flatMap((cell, ri) =>
      cell.runId && cell.url
        ? [{ runId: cell.runId, label: `${col.langName} (${col.langCode}) · ${rows.value[ri]?.label ?? ''}` }]
        : [],
    ),
  ),
)

// Which of the tabs is open. The catalogue (platform_items.json) is keyed to
// this, and carries what this place says about its own technology.
const pageContext = computed<PageContext>(() => ({
  activeViewType: 'language_comparison',
  pageContent: {
    inputText: userPrompt.value,
    selectedConfig: selectedModels.value.join(', '),
    // The block that fed the column beside the grid until 2026-08-25 goes to
    // Help unchanged, in the field made for what a surface has produced.
    instrumentRuns: ranShown.value && ranShown.value.langs.length && ranShown.value.models.length
      ? [{
          label: `${ranShown.value.langs.join(', ')} · ${ranShown.value.models.join(', ')} · seed ${ranShown.value.seed}`,
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
/* The page skeleton — the column, the preparing side and its scrolling, the
   note at the foot of it, the error line, the plot that does not scroll — and
   the raster itself — heads, row names, the series and the cap on it — are
   shared and stand in assets/flow-stage.css (`.lab-page` / `.lab-prep` /
   `.lab-plot`, `.lab-grid` / `.lab-grid-col` / `.lab-grid-head` /
   `.lab-grid-rowname` / `.lab-series`), with the measurement that feeds
   `--lab-grid-cell` in composables/useGridCellWidth.ts. The cell is
   components/MediaGridCell.vue and its size the platform's square surface
   (`.instr-frame` / `.instr-stack`, assets/instrument-surface.css). The
   starting number is `.cmp-seed` from assets/compare-stage.css. What is left
   here is what fills a column head: the language's code beside its name, and
   the sentence that went to the models with its way back. */

/* The number stands over the raster and keeps its own line; the raster takes
   the rest of the plot. */
.lab-plot > .cmp-seed {
  flex: 0 0 auto;
  margin-bottom: 6px;
}

.lc-code {
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.35);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

/* A head is centred text; the sentence in it reads from its start. The box
   itself is `.lab-case` (assets/flow-stage.css), which counts its height in
   lines of its own text and scrolls what does not fit; its two variables are
   set on `.lab-col` and this block stands outside one, so they stand here. */
.lc-translation {
  --lab-case-lines: 4;
  --lab-case-pad: 0.35rem;
  margin-top: 4px;
  text-align: start;
}

.lc-sent {
  font-size: var(--flow-fs-body);
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.3;
  word-break: break-word;
}

.lc-back {
  font-size: var(--flow-fs-sub);
  color: rgba(255, 255, 255, 0.3);
  line-height: 1.3;
  margin-top: 0.15rem;
  word-break: break-word;
}

</style>
