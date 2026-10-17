<!--
  The Latent Lab, in the frame Canvas drew and assets/shell.css now holds.

  The two stacked bars this page used to wear — the three labs on top, each
  lab's instruments underneath — are one column on the left. Which lab an
  instrument belongs to is a group title in that column, so a visitor picks an
  instrument, not a lab and then an instrument.

  This page owns the choice. The three lab files keep their v-if chains exactly
  as they are and take the active instrument as a prop; they are not taken apart
  for this.
-->
<template>
  <div class="shell-page">
    <div class="shell-bar">
      <div class="shell-bar-left">
        <button class="shell-btn" :title="$t('canvas.toggleSidebar')" @click="showRail = !showRail">
          <img
            v-if="showRail"
            src="@/assets/icons/left_panel_close_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg"
            alt=""
            class="shell-icon"
          />
          <img
            v-else
            src="@/assets/icons/left_panel_open_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg"
            alt=""
            class="shell-icon"
          />
        </button>
        <!-- Where an instrument hangs its own switch, directly beside this one
             (top left, next to the left panel switch). Named,
             so the instrument does not have to guess a position inside the bar:
             appended to .shell-bar-left it would land after the titles. -->
        <span class="shell-bar-slot"></span>
        <!-- The instrument, and nothing above it. The lab's own name stood here
             once and said twice what the column on the left already says by
             which entry is lit; the instrument's name stays because with the
             column folded away it is the only thing naming where a visitor
             stands. -->
        <span class="bar-instrument">{{ activeLabel }}</span>
      </div>

      <!-- The middle of the bar: where an instrument hangs the trigger that
           starts its run. Empty for the instruments that still carry a band.
           The overview has no run to start and says in the middle what the
           surface under it is. -->
      <div class="shell-bar-center">
        <span v-if="activeInstrument === 'overview'" class="bar-note">
          {{ t('latentLab.flowLogic.barNote') }}
        </span>
        <span v-else class="shell-bar-run"></span>
      </div>

      <!-- Which model this device has running, and where it runs. The right of
           the bar is also what makes the middle the MIDDLE: .shell-bar-left and
           .shell-bar-right both take flex: 1, so without a counterweight on the
           right the centre is pushed against it — with nothing running the
           group stands empty and still holds its side. The middle stays the
           trigger's alone. -->
      <div class="shell-bar-right">
        <span v-if="runPlace" class="bar-place" :title="placeTitle">
          <span class="bar-place-model">{{ runPlace.name }}</span>
          <template v-if="runPlace.place">
            <span class="bar-place-sep"> · </span>
            <span class="bar-place-where">{{ runPlace.place }}</span>
          </template>
        </span>
      </div>
    </div>

    <div class="shell-body">
      <div v-if="showRail" class="shell-rail">
        <ModulePalette
          ref="palette"
          :groups="railGroups"
          :active-id="activeInstrument"
          :highlight-ids="lit"
          heading=""
          hint=""
          @select="setInstrument"
        />
      </div>

      <div class="shell-work">
        <!-- Until an instrument is laid out in columns it is the page it has
             always been, and it scrolls inside the work area rather than moving
             the whole window. -->
        <div ref="mainEl" class="shell-main lab-scroll">
          <FlowLogic
            v-if="activeInstrument === 'overview'"
            :labels="instrumentLabels"
            @highlight="lit = $event"
            @reveal="reveal"
          />
          <!-- Mean Images stands in Cultural Knowledge & Stereotypes since
               2026-09-10 and is called by name: the category's own file is the
               comparison hub, which does not know this instrument. -->
          <MeanImages v-else-if="activeInstrument === 'mean'" />
          <CompareLab v-else-if="activeGroup === 'compare'" :tab="activeInstrument" />
          <InterceptionModels v-else-if="activeInstrument === 'interception-models'" />
          <PerspectivesTemplate v-else-if="activeInstrument === 'interception-template'" />
          <AestheticPoles v-else-if="activeInstrument === 'interception-poles'" />
          <ImageLab v-else-if="activeGroup === 'image'" :tab="activeInstrument" />
          <LatentTextLab v-else-if="activeGroup === 'textlab'" :tab="activeInstrument" />
          <CoverBand v-else-if="activeInstrument === 'reenactment'" />
          <CrossmodalLab v-else-if="activeGroup === 'crossmodal'" :tab="activeInstrument" />
          <LoraReach v-else-if="activeInstrument === 'reach'" />
          <TrainingStudio v-else-if="activeGroup === 'lora'" />
        </div>

        <!-- The strip of runs, for an instrument that is still a page in the
             narrow measure and has no bottom edge of its own. The instruments
             that fill the work area lay their own along their bottom edge; this
             is the same strip in the same shape, standing in the frame. -->
        <OutputDrawer
          v-if="labRuns"
          :items="labRuns.runs.value"
          :is-collapsed="labRunsCollapsed"
          :title="t('latentLab.shared.runsTitle')"
          :empty-text="t('latentLab.shared.runsEmpty')"
          :default-height="300"
          :box-width="240"
          :box-height="260"
          :source-view="labRunsSourceView"
          :selectable="!!labRuns.onSelect"
          @toggle-collapse="labRunsCollapsed = !labRunsCollapsed"
          @select="labRuns.onSelect?.($event)"
          @remove="labRuns.onRemove?.($event)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { provide, ref, shallowRef, computed, nextTick, onMounted, unref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import ModulePalette, { type RailGroup } from '@/components/canvas/ModulePalette.vue'
import OutputDrawer from '@/components/canvas/OutputDrawer.vue'
import { LAB_RUNS_HOST, type LabRunsPublication } from '@/composables/useInstrumentRuns'
import ImageLab from './latent_lab/image_lab.vue'
import MeanImages from './latent_lab/mean_images.vue'
import LatentTextLab from './latent_lab/latent_text_lab.vue'
import CrossmodalLab from './latent_lab/crossmodal_lab.vue'
import CoverBand from './cover_band.vue'
import CompareLab from './compare_hub.vue'
import FlowLogic from './latent_lab/flow_logic.vue'
import TrainingStudio from './TrainingView.vue'
import LoraReach from './latent_lab/lora_reach.vue'
import InterceptionModels from './latent_lab/interception_models.vue'
import PerspectivesTemplate from './latent_lab/perspectives_template.vue'
import AestheticPoles from './latent_lab/aesthetic_poles.vue'
import { useRunPlace } from '@/composables/useRunPlace'
import { llmPlace, localPlace, type ModelPlace } from '@/lib/modelPlace'
import { apiBase } from '@/services/labApi'

const { t } = useI18n()

/**
 * The open instrument's runs, if it hands them here. Only one instrument stands
 * in the frame at a time, so this holds one publication; it goes when the
 * instrument goes.
 */
// shallow: a deep ref would unwrap the publication's own `runs` ref into a
// plain array and the strip would stop following it.
const labRuns = shallowRef<LabRunsPublication | null>(null)
const labRunsCollapsed = ref(true)
const labRunsSourceView = computed(() => unref(labRuns.value?.sourceView ?? ''))
provide(LAB_RUNS_HOST, {
  publish: (publication: LabRunsPublication) => { labRuns.value = publication },
  withdraw: (publication: LabRunsPublication) => {
    if (labRuns.value === publication) labRuns.value = null
  },
})

type GroupId =
  | 'overview'
  | 'compare'
  | 'interception'
  | 'image'
  | 'textlab'
  | 'crossmodal'
  | 'lora'

/**
 * The twenty-two instruments, under the category each belongs to. The ids are
 * the ones the lab files already switch on, so their v-if chains are untouched;
 * `reenactment` is the one entry whose instrument was a page of its own.
 *
 * Compare stands first because it is the way in that asks least of a visitor,
 * and LoRA Training last because it asks most: it takes the graphics card for
 * one to three hours and nothing else can generate while it runs.
 */
/**
 * The four media marks. Every entry but the overview carries one or two of
 * them, in ONE slot ahead of its label: which media that instrument takes in
 * or puts out (image, text, voice, audio).
 *
 * The picture file is the one the Canvas palette already hangs on its image
 * node (types/canvas.ts), so the column and the workspace say picture with the
 * same mark instead of two.
 */
// Three of the four are COMPOSED files, not plain downloads, and their names
// say so: Material Symbols' voice mark carries no frame at all, its audio mark
// is the one wide rectangle among four squares, and its picture mark is drawn
// on a 720 grid where the rest are 840, so it stood visibly smaller than its
// neighbours. All three now use the square frame that text already has, with
// only their contents scaled into it, which keeps every stroke in the family
// identical. The mouth in the voice mark is drawn; the set has none.
const TEXT_ICON = 'font_download_120dp_E3E3E3_FILL0_wght400_GRAD0_opsz48.svg'
const IMAGE_ICON = 'media-mark-image.svg'
const VOICE_ICON = 'media-mark-voice.svg'
const AUDIO_ICON = 'media-mark-audio.svg'

const GROUPS: { id: GroupId; items: { id: string; i18n?: string; root?: string; icons?: string[] }[] }[] = [
  {
    // Not a category and deliberately without a title in the column: one entry
    // that is about all twenty-two of the others — where in a run each of them
    // reaches in. A heading over it would have to name a category for a single
    // item, and would put the overview on the same level as the five labs.
    id: 'overview',
    items: [{ id: 'overview', i18n: 'latentLab.flowLogic.tab' }],
  },
  {
    // Labels here are flat strings under `compare.tabs`, not the `.label` /
    // `.short` pair the labs use — hence the per-item key on every entry.
    //
    // Cultural (Un)Known came over from the Image Lab, where it was called
    // Default Census. Guidance and Temperature is gone with its file: that
    // surface had failed and was removed. It was the surface Randomness had
    // become and it lasted a day.
    //
    // Within each category below, the instruments follow the order of an
    // inference run rather than an arbitrary list. The marks do NOT set it:
    // a mark says which media an entry touches, and nothing about where it
    // stands.
    id: 'compare',
    items: [
      // The order, with the category's name: Stereotype Analysis first, and
      // Mean Images third, in from the Diffusion Lab.
      { id: 'census', i18n: 'compare.tabs.census', icons: [IMAGE_ICON] },
      { id: 'model', i18n: 'compare.tabs.model', icons: [IMAGE_ICON] },
      // The one entry here whose name and whose line under it stay where the
      // instrument was built, under `latentLab.imageLab.tabs`. It carries that
      // root instead of a key of its own, so the move costs it neither.
      { id: 'mean', root: 'latentLab.imageLab.tabs', icons: [IMAGE_ICON] },
      { id: 'language', i18n: 'compare.tabs.language', icons: [IMAGE_ICON] },
      // Ein Bild geht hinein, Text kommt heraus. Zuvor stand dafuer das
      // Sprachsymbol allein, weil das Instrument keine Bilder macht; jetzt
      // stehen beide Marken in der Richtung des Laufs: Bild, dann Text.
      { id: 'vlm-analysis', i18n: 'compare.tabs.vlm-analysis', icons: [IMAGE_ICON, TEXT_ICON] },
      { id: 'voice', i18n: 'compare.tabs.voice', icons: [VOICE_ICON] },
    ],
  },
  {
    // Eight from 2026-08-23, when Default Census went to Comparison and was
    // renamed there, and seven since 2026-09-19, when the Decomposition left
    // the platform. Its keys under `latentLab.imageLab.tabs.census` are read
    // by nobody now and are left standing: they are a name in ten languages,
    // and deleting them is a decision about the name, not about this list.
    // Mean Images went the same way, into Cultural Knowledge &
    // Stereotypes. Its name under `latentLab.imageLab.tabs.mean` stays
    // here and is read from there, so the move costs it neither its name nor
    // the line under it.
    id: 'image',
    items: [
      { id: 'fusion', icons: [IMAGE_ICON] }, { id: 'workbench', icons: [IMAGE_ICON] },
      { id: 'probing', icons: [IMAGE_ICON] }, { id: 'algebra', icons: [IMAGE_ICON] },
      { id: 'archaeology', icons: [IMAGE_ICON] },
      { id: 'attention', icons: [IMAGE_ICON] },
      { id: 'composable', icons: [IMAGE_ICON] },
    ],
  },
  {
    id: 'textlab',
    // The order follows the run: System Prompts and the Tokenizer act on what
    // goes INTO the model; Bias Research 1/2 and Representation Engineering
    // read what is already learned inside it. Bias Research 1 and 2 carry
    // one name with a number: both ask a model what it brings with it, the
    // first by having it answer questions that cannot be decided, the second
    // by swapping a pronoun.
    items: [
      { id: 'systemprompt', icons: [TEXT_ICON] },
      // Text geht hinein, Text kommt heraus - und nichts davon laeuft auf der
      // Grafikkarte: die Zerlegung liest eine Vokabeldatei (2026-08-26).
      { id: 'tokens', icons: [TEXT_ICON] },
      { id: 'bias', icons: [TEXT_ICON] }, { id: 'coref', icons: [TEXT_ICON] },
      { id: 'repeng', icons: [TEXT_ICON] },
    ],
  },
  {
    id: 'crossmodal',
    items: [
      // Ein Prompt geht hinein, Klang kommt heraus.
      { id: 'synth', icons: [TEXT_ICON, AUDIO_ICON] },
      { id: 'reenactment', i18n: 'coverBand.modeTitle', icons: [AUDIO_ICON, TEXT_ICON] },
      { id: 'mmaudio', icons: [IMAGE_ICON, AUDIO_ICON] },
      { id: 'guidance', icons: [IMAGE_ICON, AUDIO_ICON] },
    ],
  },
  {
    // The platform's own central operation, put up as a repeatable series: one
    // line, one perspective, and the models that write it apart from one
    // another. In SHAPE it is a comparison, and it stood directly after Compare
    // for that reason until 2026-09-06. It stands here now, last before the
    // training, because it asks more of a visitor than the labs do: what it
    // varies is the step every other instrument runs through unseen, so it
    // presupposes them.
    id: 'interception',
    items: [
      // The picture beside a row is one image model's reading of the text,
      // not what is being examined — so this one carries the language mark
      // alone, like the VLM analysis above.
      { id: 'interception-models', icons: [TEXT_ICON] },
      // The same operation with the two axes exchanged: one template, and the
      // perspectives that write it apart from one another. It stands second
      // because the first is the one that shows WHAT the operation is.
      { id: 'interception-template', icons: [TEXT_ICON, IMAGE_ICON] },
      // The same operation asked about what a checklist calls beautiful and
      // ugly: one template, a checklist of properties set one by one, and a row
      // for every setting the series walks through, with the row it came from
      // above them. It stands third because it presupposes what the two before
      // it show.
      { id: 'interception-poles', icons: [TEXT_ICON, IMAGE_ICON] },
    ],
  },
  {
    id: 'lora',
    // Training first: it makes what the second instrument compares. Explorer
    // then puts a finished adapter through the four states of the protocol.
    items: [
      { id: 'lora', icons: [IMAGE_ICON] },
      { id: 'reach', icons: [IMAGE_ICON] },
    ],
  },
]

/**
 * Where a category's item labels live, for the categories that keep them in the
 * `.label` / `.short` shape. Compare does not: its five labels are flat strings,
 * so its items carry their own key and this table has no row for them.
 */
const I18N_ROOT: Partial<Record<GroupId, string>> = {
  interception: 'latentLab.interception.tabs',
  image: 'latentLab.imageLab.tabs',
  textlab: 'latentLab.textLab.tabs',
  crossmodal: 'latentLab.crossmodal.tabs',
  lora: 'latentLab.loraLab.tabs',
}

/**
 * What stands in the address bar, per instrument. The ids on the left are the
 * workshop shorthand the three lab files switch on; they stay untouched. The
 * names on the right go into handouts and bookmarks, so they are the ones a
 * person can read and type.
 *
 * The address carries NO category: the categories can change; the instruments are referenced directly. Which lab an instrument
 * belongs to is derived from the catalogue above and may be regrouped without
 * breaking a single link.
 */
const SLUGS: Record<string, string> = {
  overview: 'overview',
  model: 'model-comparison',
  language: 'language-understanding',
  'vlm-analysis': 'image-understanding',
  // The address survives the move to the Latent Text Lab untouched — it never
  // carried the category. `randomness` and `control` are both out of this table
  // now: Randomness was taken apart into Guidance and Temperature on
  // 2026-08-22, and that instrument was removed in turn a day later.
  systemprompt: 'system-prompts',
  voice: 'voices',
  // The name settled in three steps on 2026-08-23 and the address followed
  // each time; IDS below keeps every earlier one arriving here.
  census: 'cultural-un-known',
  // Built as LLM Cultural Understanding on 2026-09-03 and renamed on
  // 2026-09-04: the platform already has a surface of that name under Compare
  // (KI-Kulturverständnis), and this one is the general instrument for the
  // interception across models — a culture lost in the writing is one of the
  // cases that run on it. The earlier address keeps working through IDS.
  'interception-models': 'interception-across-models',
  'interception-template': 'perspectives-on-a-template',
  'interception-poles': 'aesthetic-poles',
  archaeology: 'denoising-archaeology',
  mean: 'mean-images',
  attention: 'attention-cartography',
  fusion: 'encoder-fusion',
  // Built as Feature Probing and renamed Dimension Explorer. The earlier
  // address keeps working through IDS.
  probing: 'dimension-explorer',
  algebra: 'concept-algebra',
  composable: 'composable-diffusion',
  workbench: 'fusion-workbench',
  repeng: 'representation-engineering',
  tokens: 'tokenization',
  bias: 'bias-archaeology',
  coref: 'coreference-test',
  synth: 'audio-synth',
  mmaudio: 'mmaudio',
  guidance: 'imagebind-guidance',
  reenactment: 're-enactment',
  lora: 'lora-sd35',
  reach: 'lora-explorer',
}
const IDS: Record<string, string> = {
  ...Object.fromEntries(Object.entries(SLUGS).map(([id, slug]) => [slug, id])),
  // The overview was reachable as /latent-lab/intro until 2026-08-23 and is
  // linked from handouts and from the platform's own knowledge base under that
  // address. It keeps working; only the address the page WRITES has changed.
  intro: 'overview',
  // Three earlier addresses of ONE instrument. It was built as Default
  // Census, renamed Cultural Bias, then renamed Cultural (Un)Known (German
  // „Kulturelles (Un-)Wissen"), after Dewey and Bentley's the known
  // (`Knowing and the Known`, 1949): not a stock of facts but what a
  // transaction constitutes as known, which is exactly what this surface
  // shows a model doing when a culture is named. `cultural-non-knowledge`
  // is in this table because it stood briefly and is in a commit.
  // It was renamed once more, this time into a family: the
  // four comparing surfaces all say WHO does the understanding, because that
  // is their subject - KI-Modell-Vergleich, KI-Sprachverständnis,
  // KI-Bildverständnis, KI-Kulturverständnis. The (Un-) is gone from the
  // name and Dewey and Bentley with it; what it carried alone now stands
  // written out in the surface's own note box. The ADDRESSES are untouched.
  'default-census': 'census',
  'cultural-bias': 'census',
  'cultural-non-knowledge': 'census',
  // LoRA Explorer was built as LoRA Reach and renamed the same day, before
  // the first address had been used anywhere. Kept working anyway, on the
  // same rule as the three above.
  'lora-reach': 'reach',
  // Interception across Models was built as LLM Cultural Understanding a day
  // earlier, on the same rule.
  'llm-cultural-understanding': 'interception-models',
  // Dimension Explorer was built as Feature Probing, on the same rule.
  'feature-probing': 'probing',
}

/** Where the page returns to when it is called without an instrument. */
const STORAGE_KEY = 'latent_lab_instrument'
/** What this page used to remember: the lab, and the Image Lab's instrument. */
const LEGACY_GROUP_KEY = 'latent_lab_tab'
const LEGACY_IMAGE_KEY = 'latent_lab_image_tab'

const allItems = computed(() => GROUPS.flatMap(g => g.items.map(i => ({ ...i, group: g.id }))))

const route = useRoute()
const router = useRouter()

// Where a visitor who has never been here lands: the overview of the whole lab.
// It asks least of all — nothing runs, nothing is generated — and it is the one
// entry that says what the other twenty-two are for.
const activeInstrument = ref<string>('overview')
const showRail = ref(true)
/**
 * The instruments the overview map is pointing at, lit in the column.
 *
 * The map's markers carry no names of their own any more; a marker says which
 * instruments reach into that place by lighting them where they already stand.
 * It stays lit after the pointer leaves the marker — otherwise the light would
 * go out on the way to the name it is meant to lead to.
 */
const lit = ref<string[]>([])
const palette = ref<{ focusHighlighted: () => void } | null>(null)

/**
 * A marker on the map was pressed: go to its instrument.
 *
 * ONE instrument at that place — open it. That is what a chip of the deleted
 * footnote did in one press, and asking for a second press to reach something
 * that has no alternative would be a step the map never used to ask for.
 *
 * SEVERAL — light them, put the column up if it was folded away (the marker
 * points AT the column, and a light in a column that is not on the surface is
 * no answer), and move the focus to the first one that can be opened. Three
 * instruments cannot all be opened at once; which one is the visitor's to say.
 * A single instrument this card has no VRAM for takes the same path, so its
 * entry is reached and its hover text says why it is barred.
 */
function reveal(hosts: string[]) {
  const only = hosts.length === 1 ? hosts[0] : undefined
  if (only && !isDisabled(only)) {
    setInstrument(only)
    return
  }
  lit.value = hosts
  showRail.value = true
  nextTick(() => palette.value?.focusHighlighted())
}

// Folding the column away takes the light with it. Left standing, it would be
// repainted on an entry the visitor never pointed at when the column comes back.
watch(showRail, on => { if (!on) lit.value = [] })
// And leaving the map takes it with it — by any door. `setInstrument` is not
// the only one: the address bar and the back button set the instrument straight,
// and a light left burning there sits on an instrument nobody pointed at.
watch(activeInstrument, () => { lit.value = [] })

/**
 * An instrument several levels down needs to know whether it stands in this
 * frame or on its own route — Encoder Fusion has both doors, and its switch for
 * the result surface belongs in THIS bar when it is here (top left, next to the left panel switch). Told, not sniffed from the DOM: a
 * querySelector in the child would render the button in the wrong place for one
 * frame and would silently be wrong if the bar ever moved.
 */
provide('shellFrame', true)
const mainEl = ref<HTMLElement | null>(null)

const activeGroup = computed<GroupId>(
  () => allItems.value.find(i => i.id === activeInstrument.value)?.group ?? 'compare'
)

function labelFor(groupId: GroupId, item: { id: string; i18n?: string; root?: string }): string {
  if (item.i18n) return t(item.i18n)
  const root = item.root ?? I18N_ROOT[groupId]
  return root ? t(`${root}.${item.id}.label`) : item.id
}

function shortFor(groupId: GroupId, item: { id: string; i18n?: string; root?: string }): string {
  if (item.i18n) return ''
  const root = item.root ?? I18N_ROOT[groupId]
  if (!root) return ''
  const key = `${root}.${item.id}.short`
  const text = t(key)
  return text === key ? '' : text
}

/**
 * The lab's own title stood in this bar until 2026-08-21, ahead of the
 * instrument's. It is gone, not moved: the column on the left carries every
 * instrument under its lab's heading, so the bar was repeating a fact the
 * visitor was already looking at, at the width of a whole sentence.
 *
 * The three keys it read — `latentLab.imageLab.headerTitle`,
 * `latentLab.textLab.headerTitle`, `latentLab.crossmodal.headerTitle` — are
 * READ BY NOBODY since then, in any of the ten language files. They are left
 * standing because they are the labs' own names in ten languages and this bar
 * is the only thing that has stopped saying them; deleting them is a decision
 * about the labs, not about the bar. Same for `canvas.ready`, which the Canvas
 * bar stopped saying on the same day.
 */
/**
 * What the LEFT of the bar over the work area says: the instrument's own name,
 * which is what the column on the left says too — with the column folded away
 * it is the only thing naming where a visitor stands. No exception for the
 * overview: it reads „Overview" there like everywhere else.
 * What the surface IS goes in the MIDDLE of the bar, see the template.
 */
const activeLabel = computed(() => {
  const item = allItems.value.find(i => i.id === activeInstrument.value)
  return item ? labelFor(item.group, item) : ''
})

// ---------------------------------------------------------------------------
// What this graphics card can carry. Two Image Lab instruments need more VRAM
// than the smaller cards have; the column greys them out and says why, which is
// what the tile they replaced did.
// ---------------------------------------------------------------------------
interface Capabilities {
  attention_cartography: boolean
  feature_probing: boolean
  total_vram_gb: number | null
  threshold_gb: number
  forced: boolean
  /** The backbone the raster instruments resolve to on this card. */
  latent_lab_model?: string
}

const capabilities = ref<Capabilities | null>(null)

const ITEM_CAPABILITY: Record<string, keyof Capabilities> = {
  attention: 'attention_cartography',
  probing: 'feature_probing',
}

function isDisabled(id: string): boolean {
  const capKey = ITEM_CAPABILITY[id]
  if (!capKey || !capabilities.value) return false
  return capabilities.value[capKey] === false
}

// ---------------------------------------------------------------------------
// Which model is running, and where. The flow says it station by station in its
// own band; an instrument here has no band, so the bar says it for whichever
// instrument is open.
// ---------------------------------------------------------------------------

const { place: atWork } = useRunPlace()

/**
 * What the bar says: what is AT WORK, and nothing where nothing is. The line
 * does not keep the last run standing: it appears with a run and goes with
 * it, and never states a prediction.
 */
const runPlace = computed<ModelPlace | null>(() => {
  const now = atWork.value
  if (!now) return null
  // Only the sender can say WHERE: an id says which service a model is reached
  // through, never whether it is reached at all.
  return now.local ? localPlace(now.model, t) : llmPlace(now.model, t)
})

/**
 * The hover: the identifier as it went out, unshortened, and where it went.
 * The place is left off where the id already carries it — a language step names
 * its service in the prefix, and „mammouth/glm-5.3 · mammouth" says it twice.
 */
const placeTitle = computed(() => {
  const p = runPlace.value
  if (!p) return ''
  if (!p.place || p.id.startsWith(`${p.place}/`)) return p.id
  return `${p.id} · ${p.place}`
})

function tooltipFor(id: string): string {
  if (!capabilities.value) return ''
  const threshold = capabilities.value.threshold_gb
  const vram = capabilities.value.total_vram_gb
  const vramStr = vram !== null ? `${vram.toFixed(0)} GB` : '?'
  const base = vram !== null
    ? t('latentLab.imageLab.vramGate.tooltip', { threshold, vram: vramStr })
    : t('latentLab.imageLab.vramGate.tooltipUnknown', { threshold })
  return `${base} ${t('latentLab.imageLab.vramGate.override')}`
}

/**
 * Instrument id -> its name, read off the same catalogue the column reads, so a
 * renamed instrument is renamed in both.
 *
 * The overview's markers carry no visible name; this is what one SAYS when it
 * is read aloud, and what it hands over when it is pressed.
 */
const instrumentLabels = computed<Record<string, string>>(() =>
  Object.fromEntries(
    GROUPS.filter(g => g.id !== 'overview').flatMap(g =>
      g.items.map(item => [
        item.id,
        // A category holding ONE instrument names it. In the column the entry
        // reads „Stable Diffusion 3.5 Large" under the heading „LoRA Training",
        // and the heading is half the name; on its own, away from the column, it
        // would say only which model, not what is done with it.
        g.items.length === 1 && item.id === g.id
          ? t(`latentLab.tabs.${g.id}`)
          : labelFor(g.id, item),
      ])
    )
  )
)

const railGroups = computed<RailGroup[]>(() =>
  GROUPS.map(g => ({
    id: g.id,
    label: g.id === 'overview' ? '' : t(`latentLab.tabs.${g.id}`),
    items: g.items.map(item => ({
      id: item.id,
      label: labelFor(g.id, item),
      title: isDisabled(item.id) ? tooltipFor(item.id) : shortFor(g.id, item),
      icons: item.icons,
      disabled: isDisabled(item.id),
    })),
  }))
)

function setInstrument(id: string, remember = true) {
  if (isDisabled(id)) return
  activeInstrument.value = id
  if (remember) localStorage.setItem(STORAGE_KEY, id)
  if (mainEl.value) mainEl.value.scrollTop = 0
  // The address follows the choice, so every instrument can be linked and the
  // back button walks the instruments. `replace` on the silent path (the
  // capability fallback), so a card that cannot run does not become a station
  // in the history.
  const slug = SLUGS[id]
  if (slug && route.params.instrument !== slug) {
    const to = { name: 'latent-lab', params: { instrument: slug } }
    remember ? router.push(to) : router.replace(to)
  }
}

async function loadCapabilities() {
  const baseUrl = apiBase()
  try {
    const resp = await axios.get(`${baseUrl}/api/latent-lab/capabilities`)
    capabilities.value = resp.data as Capabilities
    if (isDisabled(activeInstrument.value)) {
      const fallback = allItems.value.find(i => !isDisabled(i.id))
      if (fallback) setInstrument(fallback.id, false)
    }
  } catch (e) {
    console.warn('[latent_lab] Failed to load capabilities, defaulting to all enabled:', e)
    capabilities.value = null
  }
}

watch(activeInstrument, () => {
  // A reading of the card that FAILED is held for a minute on the server, and
  // what it answers in the meantime is the conservative model rather than the
  // one that will run. A page mounted inside that minute would go on saying it
  // for the rest of its life; asking again at a switch costs one request and
  // only where the card could not be read at all.
  if (capabilities.value && capabilities.value.total_vram_gb === null) void loadCapabilities()
})

onMounted(() => {
  const known = (id: string | null) => !!id && allItems.value.some(i => i.id === id)

  // An address names the instrument outright; only a bare /latent-lab asks the
  // memory where the visitor left off.
  const fromRoute: string | null = IDS[String(route.params.instrument || '')] ?? null
  if (fromRoute && known(fromRoute)) {
    activeInstrument.value = fromRoute
    localStorage.setItem(STORAGE_KEY, fromRoute)
    localStorage.removeItem(LEGACY_GROUP_KEY)
    localStorage.removeItem(LEGACY_IMAGE_KEY)
    loadCapabilities()
    return
  }

  const saved = localStorage.getItem(STORAGE_KEY)
  if (known(saved)) {
    activeInstrument.value = saved as string
  } else {
    // Two keys used to say together what one says now: which lab, and which of
    // the Image Lab's instruments. A visitor who left off in the Text Lab or the
    // Crossmodal Lab lands on its first instrument, which is where they were.
    //
    // The lab key was written only on a click in the lab bar, and the page
    // opened in the Image Lab — so no lab key means the Image Lab, which is
    // where most visitors were. Reading it as "nothing to migrate" would drop
    // seven of the eight Image Lab instruments back to the first one, and the
    // two removeItem calls below would take the evidence with them.
    const legacyGroup = localStorage.getItem(LEGACY_GROUP_KEY)
    const legacyImage = localStorage.getItem(LEGACY_IMAGE_KEY)
    if ((legacyGroup === null || legacyGroup === 'image') && known(legacyImage)) {
      activeInstrument.value = legacyImage as string
    } else if (legacyGroup === 'textlab' || legacyGroup === 'crossmodal') {
      const first = GROUPS.find(g => g.id === legacyGroup)?.items[0]
      if (first) activeInstrument.value = first.id
    } else if (known(legacyGroup)) {
      activeInstrument.value = legacyGroup as string
    }
    localStorage.setItem(STORAGE_KEY, activeInstrument.value)
  }
  localStorage.removeItem(LEGACY_GROUP_KEY)
  localStorage.removeItem(LEGACY_IMAGE_KEY)

  loadCapabilities()
  // A visit without an instrument still gets one in the address, so the page
  // can be shared from where it actually stands. The same for an address that
  // names an instrument the lab no longer has (/latent-lab/decomposition, gone
  // 2026-09-19): the surface shows the fallback, and the address says so.
  if (!route.params.instrument || !known(fromRoute)) setInstrument(activeInstrument.value, false)
})

// Someone pressing back, or pasting a second address into the same page: the
// address is the source, the surface follows it.
watch(() => route.params.instrument, (slug) => {
  const id: string | null = IDS[String(slug || '')] ?? null
  if (id && id !== activeInstrument.value && !isDisabled(id)) {
    activeInstrument.value = id
    localStorage.setItem(STORAGE_KEY, id)
    if (mainEl.value) mainEl.value.scrollTop = 0
  }
})
</script>

<style scoped>
/* Where a visitor stands, said once and quietly. It was 0.95 rem beside a lab
   title of the same size, which made the two together the loudest thing in the
   bar; alone it is a label, so it takes the step a label takes. */
.bar-note {
  font-size: 0.8125rem;
  font-weight: 400;
  letter-spacing: 0.01em;
  color: #b0bbca;
}

.bar-instrument {
  font-size: 0.8125rem;
  font-weight: 400;
  letter-spacing: 0.05em;
  color: #7d8da3;
  margin-inline-start: 0.25rem;
  /* The left group is capped at half the bar now, because the empty right group
     takes the other half to hold the centre in the centre. Left to wrap, the
     longest label — „Ingenierie des representations", 30 characters — would break
     into two lines under about 660 px and make the whole bar a line taller. It
     shortens instead, and only where there is genuinely no room. */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

/* The model bright, its place in #7f9ab5 — the one colour the flow's station
   band writes this same statement in (`FlowRunPanel`, .gr-n). All three values
   stood here until 2026-09-09 and come back unchanged. The line stands only
   while a run is out, so there is no half-lit state to tell a run apart from
   one that is over. */
.bar-place {
  font-size: 0.8125rem;
  font-weight: 400;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.bar-place-model { color: #c3cedb; }
.bar-place-sep { color: #55606d; }
.bar-place-where { color: #7f9ab5; }

.lab-scroll {
  overflow-y: auto;
}
</style>
