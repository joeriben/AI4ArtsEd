<template>
  <div class="cmp-page voice-compare">
    <!-- Five columns since 2026-09-18 (four until Piper came back): what is asked, and the machines it is asked of.
         Each machine keeps what it made IN its own column - which is how the
         other comparison surfaces are built (`model_comparison`,
         `language_comparison`: one column per system, its result in it), and
         it gives the machine columns back the width a separate result column took
         from them. `--vc-cols` counts the machines this installation has, plus
         the asking column; written here rather than in the stylesheet because
         only the page knows how many answered. -->
    <div
      class="cmp-stage vc-stage"
      :style="{ '--vc-cols': availableSystems.length + 1 }"
    >
    <!-- The asking column, at the left and as tall as the four it asks.
         It holds the sentence, and in its corner the four small
         ones: copy, paste, a perspective, English. Nothing on the WAY changes it
         - what stands in the field is spoken exactly as it stands, and each
         column says for itself what it does with the language it is in. The last
         two of the four are changes to the field itself, made by hand and
         visible in it: both overwrite the sentence, which is why the note about
         where a chosen one came from goes as soon as they do. The box around
         such a field is dropped (chrome="bare"), so the four exist once, in
         MediaInputBox, and not a second time here - including the quick check it
         runs when a prompt field is left or pasted into. -->
    <section ref="rootEl" class="cmp-column vc-column vc-ask">
      <!-- No head over it. The four machines carry their name on the first
           row; this column would need a word invented for it, and the
           drop-down's own label already says what the field is.

           This column lays ITSELF out and does not take the machines' rows.
           It did, and then dragging the field taller moved all four columns:
           the field sat in a shared row, so its height was every column's
           height, and the columns moved when the box in the left column was
           enlarged. Now the field can be pulled to any size and nothing
           outside this column moves - what does not fit scrolls here. -->
      <div class="vc-ask-body">
        <p v-if="unavailable" class="vc-warn">{{ unavailable }}</p>

        <!-- The sentences whose construction criterion is documented, for the
             language being spoken, in the platform's own drop-down: it closes on
             the choice, and its options stand over the row rather than under it.
             Grouped by axis, blank at the top for none of them. Writing your own
             is possible and is not the starting point: a sentence that seems to
             assert nothing usually asserts something, and then the comparison
             measures the sentence rather than the voice. -->
        <PromptExamples
          :items="offeredSentences"
          :current="utterance"
          :label="t('compare.voice.sentences.label')"
          @pick="applySentence"
          @update:chosen="chosenSentence = $event"
        />

        <MediaInputBox
          icon=""
          label=""
          ref="sentenceBox"
          chrome="bare"
          :value="utterance"
          :rows="4"
          show-preset-button
          :preset-busy="presetPending"
          @update:value="utterance = $event"
          @copy="copySentence"
          @paste="pasteSentence"
          @open-preset-selector="openPerspectives"
        />

        <p v-if="chosenSource" class="vc-note">{{ chosenSource }}</p>

        <p v-if="error" class="cmp-err">{{ error }}</p>
      </div>

      <!-- What the four machines are, at the foot of the asking column - one
           box for the surface, where each column once carried its own. With
           the boxes out of the columns there is room for the generated
           results.

           The long form of the same descriptions did not fall away with
           the boxes; it stands in the documentation now (Compare guide,
           section Voices), which held nothing on this surface at all. -->
      <aside class="lab-note vc-about">
        <h3>{{ t('compare.voice.about.title') }}</h3>
        <p>{{ t('compare.voice.about.body') }}</p>
      </aside>
    </section>

    <!-- One column per synthesiser: what can be asked of it, and what came
         back. The columns are not alike, and the difference between them is
         the thing to be heard.

         Each carries a colour of its own, taken from the
         palette the flow's nodes already draw from (`types/canvas.ts`) and
         chosen to stand well clear of the two tones that MEAN something inside
         a column - green for chosen, amber for the other side of a
         distinction. The colour is the column's name, its edge and its
         trigger, and it stops there: it never reaches into the chips, or a
         reader would have five colours to tell apart in one box. -->
      <section
        v-for="s in availableSystems"
        :key="s"
        class="cmp-column vc-column vc-machine"
        :style="{ '--vc-tone-rgb': TONES[s].rgb, '--vc-tone-lit': TONES[s].lit }"
      >
        <!-- The name plain, as the other comparison surfaces write their column
             heads — in this column's colour, which is the only place besides
             the trigger where it is said. The recordings under it are its own,
             so the tag that named the machine on every card is gone with the
             mixed list it existed for. -->
        <div class="cmp-column-head">
          <span class="vc-col-name">
            {{ t(`compare.voice.systems.${s}`) }}
            <span class="vc-year">{{ YEARS[s] }}</span>
          </span>
          <span v-if="hzText(s)" class="vc-hz">{{ hzText(s) }} Hz</span>
        </div>

        <div class="vc-column-body">

          <!-- Supertonic: the ten voices the model ships, each with what it
               was heard to be and where it was measured (catalogue of
               2026-08-08). A continuous field over four of them stood here and
               is gone: four of ten were reachable, they carried no names but
               their preset ids, and the same catalogue found the mixture is not
               monotone - halfway between a 191 Hz voice and a 122 Hz one lands
               on 122, so a field promises an evenness this model does not
               keep. -->
          <template v-if="s === 'supertonic'">
            <label class="vc-inst-label">{{ t('compare.voice.supertonic.voiceLabel') }}</label>
            <!-- What choosing several does, said in the column, above the
                 chips: the ten fill the column body, and a line under them
                 scrolls out of sight. The shares are equal (`bodyFor`). -->
            <p class="vc-note">{{ t('compare.voice.supertonic.mixNote') }}</p>
            <ChipSelect
              :model-value="presets"
              :options="presetOptions"
              :columns="2"
              :disabled="isRunning(s)"
              multiple
              @update:model-value="onPresets($event as string[])"
            />
          </template>

          <!-- VoxCPM2: the speaker described in words, and the description
               travels inside the sentence. There is no parameter to set, so
               the asking is writing — and the writing has to be English,
               because English is what the model was shown. Three choosers
               carry that: their labels are in the language being read, their
               values are the English being sent.

               The field under them, in which a description could be written by
               hand, is gone: the model answers to the three rows and does not
               answer to a description freely written (it does not react to
               'voice of an elephant', 'of a robot' and the like). A field
               that takes anything and changes nothing
               teaches the wrong thing about what this model can be asked. What
               the rows write still goes to the model as a description; it is
               composed now instead of typed. Its label
               (`compare.voice.voxcpm.label`) is read by nobody and is left
               standing, like every other name this platform has stopped
               saying. -->
          <template v-else-if="s === 'voxcpm'">
            <label class="vc-inst-label">{{ t('compare.voice.voxcpm.genderLabel') }}</label>
            <ChipSelect
              :model-value="activePhrases"
              :options="genderOptions"
              :disabled="isRunning(s)"
              multiple
              @update:model-value="onPhrases($event as string[])"
            />

            <label class="vc-inst-label">{{ t('compare.voice.voxcpm.ageLabel') }}</label>
            <ChipSelect
              :model-value="activePhrases"
              :options="ageOptions"
              :disabled="isRunning(s)"
              multiple
              @update:model-value="onPhrases($event as string[])"
            />

            <label class="vc-inst-label">{{ t('compare.voice.voxcpm.emotionLabel') }}</label>
            <ChipSelect
              :model-value="activePhrases"
              :options="emotionOptions"
              :disabled="isRunning(s)"
              multiple
              @update:model-value="onPhrases($event as string[])"
            />
          </template>

          <!-- eSpeak NG: twelve settings of the same formant machinery. Not
               twelve voices and not twelve people - there is no recording
               anywhere in this column. A second click on the lit field gives
               the language's plain voice back. -->
          <template v-else-if="s === 'espeak'">
            <template v-if="espeakVariants.length">
              <label class="vc-inst-label">{{ t('compare.voice.espeak.voiceLabel') }}</label>
              <ChipSelect
                :model-value="espeakVariant"
                :options="espeakVariantOptions"
                :columns="3"
                :disabled="isRunning(s)"
                clearable
                @update:model-value="espeakVariant = $event as string"
              />

              <div v-if="espeakEngine" class="vc-model-info">
                <p class="vc-inst-label">{{ t('compare.voice.espeak.selected') }}</p>
                <p class="vc-note">{{ espeakVoiceName }}</p>
                <p class="vc-note">{{ t('compare.voice.espeak.engineMeta', espeakEngine) }}</p>
              </div>
            </template>

            <p v-else class="vc-none">{{ t('compare.voice.espeak.missing') }}</p>
          </template>

          <!-- Piper: which recording speaks, chosen in the three steps that
               Piper's own sample page (four selects: Language, Voice,
               Quality, Speaker; rhasspy.github.io/piper-samples, read
               2026-09-19) and Home Assistant's Wyoming integration (the
               voices of a language, each named "name (quality)"; the speaker
               as an option - `wyoming_piper/__main__.py`,
               `homeassistant/components/wyoming/tts.py`, read the same day)
               take. First the language, as chips for all languages with the
               system language preselected, carrying the code, the name in
               the hover card:
               the column body measures 149 px with the rail open at
               1210 x 834, and ten language names do not read at that width;
               then the voices of that language, one chip per row, named by
               their dataset with the region beside them, the file and its
               quality level on hover; then, in the German corpus
               file alone, one of its 236 speakers in the platform's
               drop-down, each entry as the sample page names it (number and
               index) and, where the corpus's metainfo lies beside the model,
               what the corpus documents (gender, recorded minutes); what
               those two are is said in the page's note box. Under the choice
               stands one line: whoever was recorded - a studio professional
               and a volunteer are both here - where the dataset says it.
               A stack of notes once stood there (the rubric
               "Selected model" with the file's name, its export version,
               sample rate and quality level, its speaker count, what the
               drop-down's entries carry, and what a file of another language
               does with the sentence). The stack broke the layout and was
               too long, so it is gone and the speaker info stands in the
               info box. What a file of another
               language makes of the sentence is heard, or refused with the
               cause in the column. The column of 08fea5fa (2026-08-14), back
               since 2026-09-18. -->
          <template v-else>
            <template v-if="piperVoices.length">
              <label class="vc-inst-label">{{ t('compare.voice.piper.languageLabel') }}</label>
              <ChipSelect
                :model-value="piperLanguage"
                :options="piperLanguageOptions"
                :min-width="44"
                :disabled="isRunning(s)"
                @update:model-value="piperLanguage = $event as string"
              />

              <template v-if="piperVoiceOptions.length">
                <label class="vc-inst-label">{{ t('compare.voice.piper.voiceLabel') }}</label>
                <ChipSelect
                  :model-value="piperVoice"
                  :options="piperVoiceOptions"
                  :columns="1"
                  :disabled="isRunning(s)"
                  @update:model-value="piperVoice = $event as string"
                />
              </template>

              <template v-if="piperSpeakerOptions.length > 1">
                <label class="vc-inst-label" :for="`vc-piper-speaker-${s}`">
                  {{ t('compare.voice.piper.speakerLabel') }}
                </label>
                <select
                  :id="`vc-piper-speaker-${s}`"
                  class="vc-select"
                  :value="piperSpeaker"
                  :title="piperSpeakerChosen"
                  :disabled="isRunning(s)"
                  @change="piperSpeaker = ($event.target as HTMLSelectElement).value"
                >
                  <option v-for="o in piperSpeakerOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
                </select>
              </template>

              <p v-if="piperOrigin" class="vc-note">{{ piperOrigin }}</p>
            </template>

            <p v-else-if="systemsLoaded" class="vc-none">{{ t('compare.voice.piper.noneInstalled') }}</p>
          </template>

          <p v-if="gapFor(s)" class="vc-gap warn">{{ gapFor(s) }}</p>
        </div>

        <!-- Directly under the settings it acts on, and the
             platform's own trigger rather than a button of this page's making:
             same triangle, same run colour, same three states as the one in
             the bar - which cannot serve here, because four machines are
             four runs. -->
        <FlowRunButton
          :ready="canSpeak && !isRunning(s)"
          :running="isRunning(s)"
          :label="t('compare.voice.speak')"
          @click="speakOne(s)"
        />

        <!-- What a column says about its last run: that it was refused, or
             that another language spoke than was asked for. A running column
             once also said "waiting..." here; that is gone: the
             trigger above already carries the running state, and a second word
             for the same thing under it takes a line to say nothing. -->
        <div
          v-if="results[s] && (results[s]?.refusal || substituted(s))"
          class="vc-column-out"
        >
          <p
            v-if="results[s]?.refusal"
            class="vc-gap warn clamp"
            :title="results[s]?.refusal"
          >{{ results[s]?.refusal }}</p>
          <p v-else-if="substituted(s)" class="vc-gap warn">{{ substituted(s) }}</p>
        </div>

        <!-- What this machine has said, newest first, in its own column and
             scrolling inside it. It stood in a fourth column
             for all three together, which took a quarter of the width from the
             three that do the work and made every card carry a tag naming which
             machine it came from. Here the column IS the tag. Kept in this tab
             only: the server stores none of it.

             `preload="none"`: Safari's default on the desktop is `auto`, so
             every player fetches and decodes its whole recording the moment it
             is mounted. A column grows with every run of a session, so after a
             workshop that is dozens of decoded 48 kHz recordings held at once -
             which is a browser brought to its knees, not a slow page. Nothing
             is loaded until play is pressed. -->
        <div class="vc-list">
          <article v-for="rec in samplesFor(s)" :key="rec.id" class="vc-sample">
            <header>
              <span class="vc-origin" :class="{ platform: rec.platform }">
                {{ rec.platform ? t('compare.voice.samples.platformOrigin', { name: rec.label }) : rec.label }}
              </span>
              <span v-if="rec.f0" class="vc-hz">{{ rec.f0.toFixed(0) }} Hz</span>
            </header>
            <audio
              :src="rec.url"
              controls
              preload="none"
              controlsList="nodownload"
              @play="solo"
              @contextmenu.prevent
            ></audio>
            <p class="vc-said">{{ rec.text }}</p>
          </article>
        </div>
      </section>
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import { useI18n } from 'vue-i18n'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import { sentencesFor, type TestAxis, type TestSentence } from '@/data/voiceTestSentences'
import {
  GENDERS,
  AGES,
  EMOTIONS,
  EMODB_EMOTIONS,
  ALL_DESCRIPTORS,
  hasPhrase,
  addPhrase,
  removePhrase,
} from '@/data/voiceDescriptors'
import { SUPERTONIC_PRESETS } from '@/data/supertonicPresets'
import ChipSelect, { type ChipOption } from '@/components/ChipSelect.vue'
import FlowRunButton from '@/components/FlowRunButton.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useSafetyEventStore } from '@/stores/safetyEvent'
import { generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { apiBase } from '@/services/labApi'

const { t, te, locale } = useI18n()

type SystemId = 'supertonic' | 'voxcpm' | 'espeak' | 'piper'

interface Sample {
  id: number
  url: string
  label: string
  text: string
  f0: number | null
  platform: boolean
  system: SystemId
}

const utterance = ref('')
const language = ref('en')

/** Which of the offered sentences is in the field, or none if it was typed. */
const chosenSentence = ref<{ source?: string } | null>(null)

/** What is on offer for the language being spoken. Empty for six of the ten. */
const offered = computed(() => sentencesFor(language.value))

/**
 * The offer, as the platform's own list takes it (`PromptExamples`, which was
 * generalised from exactly this list).
 *
 * The two axes first, in the order they are meant to be heard: a sentence that
 * carries no feeling, so that everything audible comes from the machine, then one
 * that carries a feeling, so that what the machine does with it stands out
 * against the first. The long texts last and ungrouped, named rather than shown —
 * a tale has no first line short enough to be a row in a list, and what is
 * offered there is the work, not a sentence out of it.
 *
 * Each entry carries who built it and to what criterion, and whether it is quoted
 * or only modelled on that source. The German ones are modelled: sentences were
 * dropped and one was changed, so calling them a quotation would be a false
 * citation.
 */
const offeredSentences = computed(() => {
  const asEntry = (s: TestSentence) => ({
    id: s.id,
    label: s.title ? t('compare.voice.sentences.tale', { title: s.title }) : s.text,
    fill: [s.text],
    source: s.after ? t('compare.voice.sentences.after', { source: s.source }) : s.source,
    group: s.title ? undefined : t(`compare.voice.sentences.axis.${s.axis}`),
  })
  const axes = (['neutral', 'emotional'] as TestAxis[]).flatMap((axis) =>
    offered.value.filter((s) => s.axis === axis && !s.title).map(asEntry)
  )
  return [...axes, ...offered.value.filter((s) => s.title).map(asEntry)]
})

/** Who built the sentence that is in the field, shown under it. */
const chosenSource = computed(() => chosenSentence.value?.source ?? '')

// Choosing puts the sentence in the field. Editing it afterwards is the point of
// the field being a field, and the list lets go of the choice by itself then.
function applySentence(item: { fill: string[] }) {
  utterance.value = item.fill[0] ?? ''
}

/** The platform's own clipboard, so a sentence can travel between the pages. */
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const safetyStore = useSafetyEventStore()
const sentenceBox = ref<InstanceType<typeof MediaInputBox> | null>(null)

function copySentence() {
  copyToClipboard(utterance.value)
}

/**
 * Nothing in the clipboard means nothing to paste - not an empty sentence. The
 * field carries no clear button on purpose, and a paste that wipes what stands
 * there would be that button under another name. What IS pasted goes through
 * the same check as typed text: the button never focuses the field, so no blur
 * follows it.
 */
function pasteSentence() {
  const pasted = pasteFromClipboard()
  if (!pasted) return
  utterance.value = pasted
  nextTick(() => sentenceBox.value?.checkSafety())
}

const showPresetOverlay = ref(false)
const presetPending = ref(false)

/**
 * A perspective works ON the sentence, so an empty field has nothing to offer
 * it. Rather than open a full-screen chooser whose choice would then do
 * nothing, the cursor goes where the sentence belongs.
 */
function openPerspectives() {
  if (!utterance.value.trim()) {
    sentenceBox.value?.textareaRef?.focus()
    return
  }
  error.value = ''
  showPresetOverlay.value = true
}

/**
 * A perspective, run over the sentence in the field, replacing it. Destructive
 * on purpose: what is written here is what will be spoken, so there is no
 * second place for the transformed text to go, and the sentence's source note
 * disappears with it because the text is no longer that sentence.
 */
async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  const text = utterance.value.trim()
  if (!text || presetPending.value) return

  presetPending.value = true
  error.value = ''
  try {
    // No device id from this surface, as before; the reader's language goes
    // along, so the perspective writes in it.
    const outcome = await interceptPrompt(payload.configId, text, null, { userLanguage: locale.value })
    // A refusal by the checks arrives with its own explanation, and it is the
    // one answer that must not disappear: it goes where every other block on
    // this platform goes, so it is explained rather than looking like a
    // machine that did nothing.
    if ('refusedKey' in outcome) {
      safetyStore.reportBlock(outcome.blockedAtStage || 1, outcome.reason || t('mediaInput.contentBlocked'), [])
      return
    }
    // The interception alone, never the adaptation to an image model: this text
    // is spoken, and only a string can be. A two-part prompt would be read out
    // with its braces and key names.
    if ('written' in outcome && !outcome.structured && outcome.written.trim()) {
      utterance.value = outcome.written.trim()
      // Written by a model, and on its way to being spoken: the check that runs
      // over typed text runs over this too. Stage 2 checks what went IN, and
      // there is no Stage 3 on this path.
      await nextTick()
      sentenceBox.value?.checkSafety()
    } else if ('written' in outcome) {
      error.value = perspectiveFailureText(t, { empty: true })
    } else {
      error.value = perspectiveFailureText(t, outcome)
    }
  } catch (e) {
    error.value = generationErrorFor(t, e)
  } finally {
    presetPending.value = false
  }
}

/**
 * Which of the ten Supertonic voices speak — any number of them, mixed. F3 to
 * begin with: of the five named female it sits lowest but one, and it is one
 * of the four the catalogue of 2026-08-08 found closest to no side at all.
 */
const presets = ref<string[]>(['F3'])

/**
 * The ten as rows to tick. Each carries what it was heard to be and where it
 * was measured; the floor of one is held by the list itself, because an empty
 * selection is not a quiet voice, it is no voice, and the server refuses it.
 */
/**
 * A mixture of nothing is not a voice, so the last one lit stays lit. Above
 * one, any number of them: that is what this column is for, and the floor sits
 * here rather than in the component because it is this column's condition and
 * not a property of fields you can click.
 */
function onPresets(next: string[]) {
  if (next.length) presets.value = next
}

const presetOptions = computed(() =>
  SUPERTONIC_PRESETS.map((p) => ({
    value: p.id,
    label: t(`compare.voice.supertonic.presets.${p.id}`),
    aside: `${p.id} · ${p.hz} Hz`,
    // The distinction the model itself draws and offers no third term for:
    // five named female, five named male. Colouring it is not endorsing it -
    // it is the reason the platform's own voice is a mixture and never one of
    // these, and a mixture is only legible once the two sides are.
    tone: p.id.startsWith('F') ? ('green' as const) : ('amber' as const),
  }))
)
/** Which of the twelve settings speaks, or '' for the plain voice. */
const espeakVariant = ref('')
/** Which installed Piper voice speaks, by file stem. Filled from the status. */
const piperVoice = ref('')
const voiceDescription = ref('')

/**
 * The three rows of buttons over that description. They exist because this
 * model has no parameter for any property of a voice — gender, age and feeling
 * are all language, written into the utterance in English — and a workshop
 * cannot assume that of a twelve-year-old. See data/voiceDescriptors.ts.
 *
 * There is no state here beyond the field itself. A button is lit when its
 * phrase stands in the description, pressing it puts that phrase in, pressing
 * it again takes that phrase out, and nothing else in the field is touched —
 * not another button's phrase, and not a word typed by hand. Any number can be
 * lit at once.
 */
const genderOptions = computed(() =>
  GENDERS.map((g) => ({ value: g.en, label: t(`compare.voice.voxcpm.gender.${g.id}`) }))
)

const ageOptions = computed(() =>
  AGES.map((a) => ({ value: a.en, label: t(`compare.voice.voxcpm.age.${a.id}`) }))
)

const emotionOptions = computed(() =>
  EMOTIONS.map((e) => ({
    value: e.en,
    label: t(`compare.voice.voxcpm.emotions.${e.id}`),
    // Green for the seven of EmoDB, amber for the five ways of speaking. The
    // two are not the same kind of thing to ask for, and the row would read as
    // twelve of one kind without it.
    tone: EMODB_EMOTIONS.has(e.id) ? ('green' as const) : ('amber' as const),
  }))
)

/** The phrases standing in the description right now - what is lit. */
const activePhrases = computed(() =>
  ALL_DESCRIPTORS.map((d) => d.en).filter((phrase) => hasPhrase(voiceDescription.value, phrase))
)

/**
 * A row reports its new set. Exactly one button changed, so the difference
 * between before and after names the phrase to put in or take out - and only
 * that phrase is written, which is what keeps a hand-written description
 * intact under a button press.
 */
function onPhrases(next: string[]) {
  const before = activePhrases.value
  const added = next.find((phrase) => !before.includes(phrase))
  if (added) {
    voiceDescription.value = addPhrase(voiceDescription.value, added)
    return
  }
  const dropped = before.find((phrase) => !next.includes(phrase))
  if (dropped) voiceDescription.value = removePhrase(voiceDescription.value, dropped)
}
/**
 * Which synthesisers are speaking right now. Per system, never one flag for
 * the page: a run in one column is no reason to freeze the other two, the
 * sentence or the choosers - what is in flight was sent already.
 */
const running = ref<Record<string, boolean>>({})

function isRunning(s: SystemId): boolean {
  return running.value[s] === true
}

function setRunning(s: SystemId, state: boolean) {
  running.value = { ...running.value, [s]: state }
}
const error = ref('')
const unavailable = ref('')
/**
 * Whether the status has answered. Until it has, a column knows nothing
 * about its machine and says nothing about it: „No Piper voice is
 * installed." is a statement about the installation and must never stand in
 * for a request that is still running or has failed. What a failed request
 * means is said once, in the asking column (`unavailable`).
 */
const systemsLoaded = ref(false)
const samples = ref<Sample[]>([])
const rootEl = ref<HTMLElement | null>(null)

/**
 * One run of the same sentence through every synthesiser on the page. Held
 * apart from `samples` because it is one act and reads as one: replaced whole
 * on the next run, never appended to.
 */
interface TrioCard {
  system: SystemId
  url: string
  label: string
  f0: number | null
  /** What was asked for, and what actually came back - not always the same. */
  asked: string
  spoken: string
  refusal: string
  done: boolean
}

const trio = ref<TrioCard[]>([])

/** The card belonging to each column, so a column can find its own result. */
const results = computed<Partial<Record<SystemId, TrioCard>>>(() => {
  const out: Partial<Record<SystemId, TrioCard>> = {}
  for (const card of trio.value) out[card.system] = card
  return out
})

const maxChars = ref(4000)
const systems = ref<Record<string, any>>({})
/** The platform's own languages, as the server lists them. */
const languagePool = ref<string[]>([])

let nextId = 1

/**
 * eSpeak NG, then Supertonic, then VoxCPM2 — ascending by what can be asked of
 * them at all. eSpeak NG has no model to ask: rules make phonemes out of the
 * letters and the phonemes are played as resonances, and what can be set are
 * numbers on that machinery. Supertonic's voice is a vector among ten that can
 * be mixed, so which voice can be chosen but nothing about how it feels.
 * VoxCPM2's is whatever can be said in a sentence.
 *
 * The order is also the order they speak in, so a run walks the same way.
 *
 * Piper stands second. It stood first originally, was removed for a time, and
 * was added back to the Latent Lab voices. Its voice is
 * one recording trained into one file, and the file is what can be chosen:
 * more than eSpeak NG's numbers on a machinery, less than Supertonic's
 * mixtures. The same order the years give (1995, 2022, 2026, 2026).
 */
const availableSystems = computed<SystemId[]>(() =>
  (['espeak', 'piper', 'supertonic', 'voxcpm'] as SystemId[]).filter((s) => systems.value[s]?.enabled)
)

/**
 * A colour per column, so that a column, its trigger and what
 * it made are one thing to the eye and four columns are not one grey field.
 * Taken from the palette the flow already draws its node types from
 * (`types/canvas.ts`): cyan, indigo, pink. Green and amber are left out on
 * purpose — inside a column they MEAN something, chosen and the other side of a
 * distinction (`ChipSelect`), and a column-wide green would say "chosen" about
 * a whole machine.
 *
 * Two values because the border wants the colour thinned and the writing wants
 * it lit: text at the full node colour is too dark to read on this ground.
 */
/**
 * The year each of them comes from, beside its name - because
 * three decades stand in this row and nothing else on the surface says so.
 *
 * eSpeak NG is dated by its LINEAGE, not by its version: the binary here is
 * 1.51.1, and its own README dates the program to 1995, written as `speak` for
 * Acorn/RISC OS by Jonathan Duddington, rewritten as eSpeak in 2007 and forked
 * to eSpeak NG in late 2015. The box at the foot of the asking column says
 * that in full; the head has room for the year only.
 */
const YEARS: Record<SystemId, string> = {
  espeak: '1995',
  supertonic: '2026',
  voxcpm: '2026',
  // Begun 2022 for the Rhasspy project, over VITS (2021). The binary here is
  // piper-tts 1.6.0; the voice files carry their own versions, 0.2.0 to 1.5.0.
  piper: '2022',
}

/**
 * The fourth tone is purple, from the same palette (`types/canvas.ts`): the
 * one hue left there that neither means something inside a column (green,
 * amber) nor sits on the platform's warm red for what went wrong (red,
 * orange), nor on the cyan already taken (sky, teal). Text at the full node
 * colour is too dark on this ground, so the lit value is the tint above it,
 * as for the other three.
 */
const TONES: Record<SystemId, { rgb: string; lit: string }> = {
  espeak: { rgb: '6 182 212', lit: '#67e8f9' },
  supertonic: { rgb: '99 102 241', lit: '#a5b4fc' },
  voxcpm: { rgb: '236 72 153', lit: '#f9a8d4' },
  piper: { rgb: '139 92 246', lit: '#c4b5fd' },
}

/** What the binary itself reports: its version and the rate it writes at. */
const espeakEngine = computed<{ version: string; hz: number } | null>(() => {
  const engine = (systems.value.espeak as any)?.engine
  if (!engine?.version) return null
  return { version: String(engine.version), hz: Number(engine.sample_rate ?? 0) }
})

/** The twelve settings this installation has, in the order the server sends. */
const espeakVariants = computed<string[]>(() =>
  (((systems.value.espeak as any)?.engine?.variants ?? []) as any[]).map(String)
)

/**
 * The same two colours the Supertonic column carries, and for the same
 * distinction: five named female, seven named male. Here they are settings of
 * one machine rather than ten trained voices, which is exactly what the two
 * columns are there to be heard against each other for.
 */
const espeakVariantOptions = computed(() =>
  espeakVariants.value.map((v) => ({
    value: v,
    label: v,
    tone: v.startsWith('f') ? ('green' as const) : ('amber' as const),
  }))
)

/** What will speak: the language's voice, and the setting if one is lit. */
const espeakVoiceName = computed<string>(() =>
  espeakVariant.value ? `${language.value} + ${espeakVariant.value}` : language.value
)

/**
 * Every installed Piper voice, in every language, as chips for all languages
 * with the system language preselected. Formerly the column listed
 * the sentence's language alone and the backend refused a file of another;
 * now any file can be asked to read the sentence, and what its phonemiser
 * makes of it is heard, or refused with the cause (piper_backend.py, module
 * docstring). A studio professional and a volunteer reader are both
 * offered; where the dataset says who was recorded, the copy carries it
 * (`compare.voice.piper.recordings`, keyed by the `dataset` the voice file
 * names) and the one line under the choice shows it. Silence there says
 * "not documented", never "amateur".
 */
interface PiperVoice {
  key: string
  language: string
  /** The region the catalogue folds into its language code: 'DE', 'GB', 'US', 'MX' ... */
  region: string
  dataset: string
  /** Piper's own quality level as the sidecar names it: x_low, low, medium or high. */
  quality: string
  /** The file's own speaker names in the dataset's order; [] for one speaker. */
  speakers: string[]
  /** What the corpus documents per speaker, where its metainfo lies beside the model; {} otherwise. */
  speakerInfo: Record<string, { gender: string; minutes: number }>
}
const piperVoices = computed<PiperVoice[]>(() =>
  ((systems.value.piper?.voices ?? []) as any[]).map((v) => ({
    key: String(v?.key ?? ''),
    language: String(v?.language ?? ''),
    region: String(v?.region ?? ''),
    dataset: String(v?.dataset ?? ''),
    quality: String(v?.quality ?? ''),
    speakers: Array.isArray(v?.speakers) ? v.speakers.map(String) : [],
    speakerInfo: v?.speaker_info && typeof v.speaker_info === 'object' ? v.speaker_info : {},
  }))
)

/**
 * The choice runs in the three steps of Piper's own sample page
 * (rhasspy.github.io/piper-samples, four selects: Language, Voice, Quality,
 * Speaker) and of Home Assistant's Wyoming integration (the voices of a
 * language; the speaker as an option), both read 2026-09-19: the language
 * first, then the voices of that language, then the speaker of a
 * multi-speaker file. The language row is chips for all languages, the system
 * language preselected, in the order of their codes like
 * the page's own language list; each carries its code and its name in the
 * reader's language in the hover card, because the column body measures
 * 149 px with the rail open at 1210 x 834 and ten language names do not read
 * at that width. The fields are measured (`minWidth`) rather than counted
 * per row, so a longer code takes the room it needs.
 */
const piperLanguage = ref('')
const piperLanguageOptions = computed<ChipOption[]>(() =>
  [...new Set(piperVoices.value.map((v) => v.language))]
    .sort()
    .map((code) => ({ value: code, label: code.toUpperCase(), title: languageLabel(code) }))
)

/**
 * The voices of the lit language in the order of the names on the chips, as
 * Home Assistant lists them, one per row: the dataset's own name, the region
 * beside it (the three Spanish voices stand one under the other, Mexico,
 * Argentina and Spain by their names), the file and the sidecar's quality
 * level on hover.
 */
const piperVoiceOptions = computed<ChipOption[]>(() =>
  piperVoices.value
    .filter((v) => v.language === piperLanguage.value)
    .sort((a, b) => (a.dataset || a.key).localeCompare(b.dataset || b.key))
    .map((v) => ({
      value: v.key,
      label: v.dataset || v.key,
      aside: v.region,
      title: t('compare.voice.piper.voiceTitle', { file: v.key, quality: v.quality }),
    }))
)

/** The file that is lit. */
const piperChosen = computed<PiperVoice | undefined>(() =>
  piperVoices.value.find((v) => v.key === piperVoice.value)
)

/**
 * The speakers of the lit file, in the dataset's order - 236 for the German
 * research corpus, none listed for a single-speaker file. They are not a
 * mixture: this is a multi-speaker VITS model, one embedding per speaker, and
 * Piper speaks with exactly one of them per utterance. Which one goes to the
 * API under `emotion`, the historical name of the parameter
 * (`resolve_speaker` in piper_backend.py). Mixing happens in the Supertonic
 * column, and that is the difference between the two.
 */
const piperSpeakers = computed<string[]>(() => piperChosen.value?.speakers ?? [])
/** Which of them speaks; '' for a single-speaker file, which is sent none. */
const piperSpeaker = ref('')

/**
 * The drop-down's entries: each speaker as Piper's sample page names it (its
 * name and its index in the file) and, where the corpus's metainfo lies
 * beside the model, what the corpus documents - gender as it records it (F
 * or M) and the minutes recorded, summed per speaker by the backend. What
 * the two are is said in the page's note box (`compare.voice.about.body`),
 * where the speaker info belongs.
 */
const piperSpeakerOptions = computed<{ value: string; label: string }[]>(() => {
  const chosen = piperChosen.value
  if (!chosen) return []
  return chosen.speakers.map((name, index) => {
    const info = chosen.speakerInfo[name]
    const parts = [`${name} (${index})`]
    if (info) {
      if (info.gender === 'F' || info.gender === 'M') {
        parts.push(t(`compare.voice.piper.gender.${info.gender}`))
      }
      const minutes = Number(info.minutes)
      if (Number.isFinite(minutes)) parts.push(recordedText(minutes))
    }
    return { value: name, label: parts.join(' · ') }
  })
})
/** The whole entry of the speaker that is lit: the closed control clips it at this width. */
const piperSpeakerChosen = computed<string>(() =>
  piperSpeakerOptions.value.find((o) => o.value === piperSpeaker.value)?.label ?? ''
)
/** The corpus's minutes in the unit the amount is read in: hours from one hour, seconds under a minute. */
function recordedText(minutes: number): string {
  if (minutes >= 60) return t('compare.voice.piper.recorded.h', { n: Math.round(minutes / 60) })
  if (minutes >= 1) return t('compare.voice.piper.recorded.min', { n: Math.round(minutes) })
  return t('compare.voice.piper.recorded.s', { n: Math.round(minutes * 60) })
}

/** The file and, in a multi-speaker file, the speaker - as the server names what spoke. */
const piperVoiceName = computed<string>(() =>
  piperSpeaker.value ? `${piperVoice.value} / ${piperSpeaker.value}` : piperVoice.value
)

/**
 * What the dataset says about the voice that will speak, from the copy, keyed
 * by the dataset the file names. Nothing for a dataset the copy has no entry
 * for; the English stands in until a language has its own line.
 */
const piperOrigin = computed<string>(() => {
  const dataset = piperChosen.value?.dataset
  if (!dataset) return ''
  const key = `compare.voice.piper.recordings.${dataset}`
  return te(key) || te(key, 'en') ? t(key) : ''
})

// The language row follows the interface, and the list arrives with the
// status: whenever either changes, the interface's language is lit where a
// file exists for it, else nothing - then no voice is sent and the server
// says what is missing. A language chosen by hand stays lit until the
// interface's language changes.
watch([piperVoices, language], ([list, code]) => {
  piperLanguage.value = list.some((v) => v.language === code) ? code : ''
}, { immediate: true })

// The voice follows the language row: the file the server names as its
// default for that language (`default_voices`), else the first of the
// language's voices as the chips order them, else none. A voice chosen by
// hand stays lit while its language is.
watch(piperVoiceOptions, (options) => {
  if (options.some((o) => o.value === piperVoice.value)) return
  const preset = String(systems.value.piper?.default_voices?.[piperLanguage.value] ?? '')
  piperVoice.value = options.some((o) => o.value === preset) ? preset : (options[0]?.value ?? '')
}, { immediate: true })

// A file's first speaker is the one the server takes unasked (the lowest id,
// or a speaker named "neutral" where a file has one; `resolve_speaker`), so
// what the drop-down shows is what speaks; a single-speaker file has none and
// sends none.
watch(piperSpeakers, (names) => {
  if (!names.includes(piperSpeaker.value)) piperSpeaker.value = names[0] ?? ''
}, { immediate: true })

/**
 * Every language this platform has - not the selected system's. A language is
 * a property of the sentence, not of the machine, and the point of the mode is
 * to hear what each machine does with one it has no voice for.
 */
const platformLanguages = computed<string[]>(() => {
  const all = new Set<string>(languagePool.value)
  for (const entry of Object.values(systems.value)) {
    const list = (entry as any)?.languages
    if (Array.isArray(list)) list.forEach((code: string) => all.add(code))
  }
  return all.size ? [...all].sort() : ['en']
})

/**
 * What the selected system will do with a language it has no voice for, said
 * before it is asked. Both halves are read from the server: which languages it
 * has, and whether it substitutes English or refuses.
 */
function gapFor(s: SystemId): string {
  const entry: any = systems.value[s]
  const list = entry?.languages
  if (!Array.isArray(list) || list.includes(language.value)) return ''
  const params = {
    system: t(`compare.voice.systems.${s}`),
    language: languageLabel(language.value),
  }
  return entry?.english_fallback === false
    ? t('compare.voice.gap.refuses', params)
    : t('compare.voice.gap.english', params)
}

/** What a column reports when it was asked for one language and spoke another. */
function substituted(s: SystemId): string {
  const card = results.value[s]
  if (!card?.spoken || card.spoken === card.asked) return ''
  return t('compare.voice.trio.substituted', {
    asked: languageLabel(card.asked),
    spoken: languageLabel(card.spoken),
  })
}

function hzText(s: SystemId): string {
  const f0 = results.value[s]?.f0
  return typeof f0 === 'number' ? f0.toFixed(0) : ''
}


const described = computed(() => voiceDescription.value.trim())

/**
 * Equal shares over whatever is selected — addition and normalisation, which is
 * what the backend does with the two style tensors: (F1 + M4)/2 for two, a
 * third each for three. One selected voice is that same weighting with one
 * entry, so nothing special happens at the edges.
 *
 * The shares are worked out here as well as on the server so that what is shown
 * beside a sample is the weighting that produced it.
 */
function weightsFor(_s: SystemId): Record<string, number> {
  const chosenPresets = presets.value
  const share = Number((1 / chosenPresets.length).toFixed(4))
  const out: Record<string, number> = {}
  for (const id of chosenPresets) out[id] = share
  return out
}

const canSpeak = computed(
  () => !unavailable.value && utterance.value.trim().length > 0
)

function describeMix(mix: Record<string, number> | undefined): string {
  if (!mix) return ''
  return Object.entries(mix)
    .sort((a, b) => b[1] - a[1])
    .map(([preset, share]) => `${preset} ${Math.round(share * 100)}`)
    .join(' / ')
}

/**
 * One voice at a time. Three players side by side are there to be heard
 * against each other, and two of them at once is not a comparison - so
 * starting one stops every other on the page.
 */
function solo(e: Event) {
  const started = e.target as HTMLAudioElement
  const page = rootEl.value?.closest('.voice-compare') ?? document
  page.querySelectorAll('audio').forEach((other) => {
    if (other !== started) other.pause()
  })
}

function languageLabel(code: string): string {
  const key = `compare.voice.languages.${code}`
  const label = t(key)
  return label === key ? code.toUpperCase() : label
}

// The language is never moved for anyone. Each column says for itself what
// it will do with a language it has no voice for, and that saying is the
// comparison the mode exists for.
//
// It does follow the interface, though, and not only at load: this page speaks
// in the language it is being read in, and switching the interface halfway
// through otherwise left German sentences under an English page.
watch(locale, (next) => {
  const code = String(next || '').toLowerCase()
  if (code && code !== language.value && platformLanguages.value.includes(code)) {
    language.value = code
  }
})

// --- speaking -------------------------------------------------------------

/**
 * What a synthesiser is asked for, with the settings as they stand. One place,
 * because the single button and the four-way run have to send the same thing
 * - otherwise the row would compare two different questions.
 */
function bodyFor(s: SystemId, shared: Record<string, unknown>): Record<string, unknown> {
  // VoxCPM2 composes the description into the utterance itself. Sent empty
  // means empty: nothing is asked, and the model reads the delivery off the
  // sentence — which is a question this page asks on purpose.
  if (s === 'voxcpm') {
    const body: Record<string, unknown> = { ...shared, system: 'voxcpm' }
    if (described.value) body.voice_description = described.value
    return body
  }
  // eSpeak NG is asked for one of twelve settings and nothing else. It needs
  // its own branch because falling through would hand it Supertonic's mixture.
  if (s === 'espeak') {
    const body: Record<string, unknown> = { ...shared, system: 'espeak' }
    if (espeakVariant.value) body.variant = espeakVariant.value
    return body
  }
  // Piper is asked for a recording and, in the corpus file, for one of its
  // speakers - no mixture, no description, no setting. It needs its own
  // branch because falling through would hand it Supertonic's mixture.
  if (s === 'piper') {
    const body: Record<string, unknown> = { ...shared, system: 'piper' }
    if (piperVoice.value) body.voice = piperVoice.value
    // The API's name for the speaker parameter (piper_backend.py). Sent only
    // where the drop-down stands, which is where the file has more than one
    // speaker: a choice nobody was offered is not made on their behalf, and
    // the backend takes the file's first speaker itself.
    if (piperSpeaker.value && piperSpeakerOptions.value.length > 1) {
      body.emotion = piperSpeaker.value
    }
    return body
  }
  return { ...shared, mix: weightsFor('supertonic') }
}

/** What to call it before the server says what actually spoke. */
function labelFor(s: SystemId): string {
  if (s === 'voxcpm') return described.value
  if (s === 'espeak') return espeakVoiceName.value
  if (s === 'piper') return piperVoiceName.value
  return describeMix(weightsFor('supertonic'))
}

/** A fresh, empty card for one column. */
function blankCard(s: SystemId): TrioCard {
  return {
    system: s,
    url: '',
    label: labelFor(s),
    f0: null,
    asked: language.value,
    spoken: '',
    refusal: '',
    done: false,
  }
}

/**
 * One column again, with its settings as they now stand. The card is replaced
 * rather than added to: a column shows what it last said, and the row of
 * everything heard keeps the rest.
 */
async function speakOne(s: SystemId) {
  const text = utterance.value.trim()
  if (!text || isRunning(s)) return
  const shared = { text: text.slice(0, maxChars.value), language: language.value }
  const card = blankCard(s)
  const at = trio.value.findIndex((c) => c.system === s)
  if (at >= 0) trio.value.splice(at, 1, card)
  else trio.value.push(card)

  error.value = ''
  setRunning(s, true)
  try {
    await speakInto(card, shared)
  } finally {
    setRunning(s, false)
  }
}

/** One card of the row. Fills itself in; a refusal is a result, not an error. */
async function speakInto(card: TrioCard, shared: Record<string, unknown>) {
  try {
    const response = await fetch(`${apiBase()}/api/speech`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bodyFor(card.system, shared)),
    })

    if (!response.ok) {
      let reason = ''
      try {
        const data = await response.json()
        reason = data?.error || ''
      } catch {
        reason = ''
      }
      card.refusal = reason || t('compare.voice.failed', { status: response.status })
      return
    }

    card.label = response.headers.get('X-Speech-Voice') || card.label
    card.spoken = (response.headers.get('X-Speech-Language') || '').toLowerCase()
    const hz = Number.parseFloat(response.headers.get('X-Speech-F0') || '')
    card.f0 = Number.isFinite(hz) ? hz : null
    card.url = URL.createObjectURL(await response.blob())

    // The same object URL in both places: the column shows the latest, the row
    // below keeps every one of them, and only leaving the page revokes them
    // (`onBeforeUnmount`); nothing clears a column since 2026-09-19.
    samples.value.unshift({
      id: nextId++,
      url: card.url,
      label: card.label,
      text: String(shared.text ?? ''),
      f0: card.f0,
      platform: false,
      system: card.system,
    })
  } catch {
    card.refusal = t('compare.voice.unreachable')
  } finally {
    card.done = true
  }
}

/**
 * What one column has heard, newest first. `samples` stays one list for all of
 * them because a run writes into it and the revoking on unmount reads it; the
 * columns take their own out of it.
 */
function samplesFor(s: SystemId): Sample[] {
  return samples.value.filter((x) => x.system === s)
}

onMounted(async () => {
  try {
    const response = await fetch(`${apiBase()}/api/speech/status`)
    const data = await response.json()

    if (!data?.available) {
      unavailable.value = data?.reason
        ? t('compare.voice.unavailableWith', { reason: data.reason })
        : t('compare.voice.unavailable')
    }

    systems.value = data?.systems ?? {}
    systemsLoaded.value = true
    if (typeof data?.max_chars === 'number') maxChars.value = data.max_chars
    languagePool.value = [
      ...(Array.isArray(data?.voiced_languages) ? data.voiced_languages : []),
      ...(Array.isArray(data?.unvoiced_languages) ? data.unvoiced_languages : []),
    ]

    // Start in the language the interface is in. All ten are offered now, so
    // this holds for every one of them.
    const ui = String(locale.value || 'en').toLowerCase()
    language.value = platformLanguages.value.includes(ui)
      ? ui
      : (platformLanguages.value[0] ?? 'en')
  } catch {
    unavailable.value = t('compare.voice.unreachable')
  }
})

onBeforeUnmount(() => {
  samples.value.forEach((s) => URL.revokeObjectURL(s.url))
})
const pageContextStore = usePageContextStore()

// Which of the tabs is open. The catalogue (platform_items.json) is keyed to
// this, and carries what this place says about its own technology.
const pageContext = computed<PageContext>(() => ({
  activeViewType: 'voice_comparison',
  pageContent: {},
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onBeforeUnmount(() => {
  pageContextStore.clearContext()
})
</script>

<style scoped>
/* The page frame, the column box, the head row and the error line stand in
   `assets/compare-stage.css` since 2026-09-07 and are shared with AI Language
   Understanding. What is here is this surface's own: the five rows the four
   machines line up in. */

.vc-warn {
  margin: 0;
  font-size: 0.8rem;
  color: #e0a355;
}

.vc-note {
  font-size: 0.78rem;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.45);
  margin: 0 0 0.6rem;
}

/* --- field --- */

/* --- the written instruction --- */

/* The sentence field reads exactly as it did: MediaInputBox is used here in its
   bare form, so what it brings is the four symbols in the corner, not the heavy
   box that marks a prompt field elsewhere. Only the inline-end padding is left
   to the component - it knows how much room its own symbols take. */
.vc-ask :deep(.bubble-textarea) {
  background-color: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding-block: 0.6rem;
  padding-inline-start: 0.7rem;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1.5;
}

/* Focus, said once and unambiguously. The rule above and the component's own
   :focus rule carry the same weight, and they are built into two separate
   stylesheets - so which of them draws the border of a focused field would be
   decided by load order, and in one of the two orders nothing at all would be
   drawn: the component turns the browser's own ring off. */
.vc-ask :deep(.bubble-textarea:focus) {
  border-color: rgba(102, 126, 234, 0.8);
}

/* No icon and no frame: the sentence field carries the four symbols and
   nothing else that would make it a second box inside the column it stands
   in. */
.vc-ask :deep(.bubble-icon) {
  display: none;
}

.vc-ask :deep(.media-input-box) {
  border: 0;
  background: transparent;
  padding: 0;
}

/* The head of that field is empty of writing - `label=""` - and holds only the
   four symbols. Its 0.75 rem of air under a line that says nothing is room
   this column needs. */
.vc-ask :deep(.bubble-header) {
  margin: 0 0 0.35rem;
}

/* What the four machines are, in the lab's note box (`.lab-note`, which
   brings the border, the radius and the type step). `pre-line` because the
   four entries are parted by blank lines and without it they would run
   together into one paragraph. It scrolls in itself rather than growing the
   column. */
.vc-about {
  min-height: 0;
  overflow-y: auto;
}

.vc-about p {
  white-space: pre-line;
  margin: 0;
  font-size: var(--flow-fs-hint);
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.45);
}

/* Set off from the fields above it: this is what was chosen, not another
   thing to choose. The gap is the column's own - the same 0.9rem that
   .vc-inst-label puts over every heading here. */
.vc-model-info {
  margin-top: 0.9rem;
}

.vc-model-info .vc-inst-label {
  margin-top: 0;
}

/* The lab's heading over a control (`.lab-pick-label`), so this column keeps
   the rhythm the instruments beside it keep. */
.vc-inst-label {
  display: block;
  margin: 0.9rem 0 0.35rem;
  font-size: var(--flow-fs-sub);
  color: rgba(255, 255, 255, 0.5);
}

/* --- controls --- */

.vc-gap {
  margin: 1rem 0 0;
  font-size: 0.78rem;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.45);
  border-left: 2px solid rgba(255, 255, 255, 0.12);
  padding-left: 0.7rem;
}

.vc-gap.warn {
  border-left-color: rgba(224, 122, 95, 0.5);
}

/* --- samples --- */

/* A backend can hand back a whole memory-allocation report. It is kept - it
   says something concrete failed - but it stops before it makes one column six
   times the height of the two beside it, which would be the wrong thing to
   compare. The full text stays in the title. */
.vc-column-out .vc-gap.clamp {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* A machine's own recordings, in the one elastic row of the grid: a session
   adds one per run and never drops one, so this is what reaches the bottom
   edge first, and it scrolls in itself rather than growing the surface. */
.vc-list {
  display: grid;
  align-content: start;
  overflow-y: auto;
  min-height: 0;
}

/* One recording under the next, parted by a line. No box around each: the
   column IS the box, and a bordered card inside a bordered column is the
   panel-on-a-panel this surface just stopped being. */
/* A grid item is `min-width: auto` by default, so it grows to whatever its
   widest content asks for. With the one-line text below set to `nowrap` a
   recording of a tale made this box fifteen thousand pixels wide: the text
   was clipped by the list instead of ending in an ellipsis, and the list
   grew a sideways scrollbar. Zero lets the box take the column's width, and
   the text is cut where it should be. */
.vc-sample {
  min-width: 0;
}

.vc-sample + .vc-sample {
  margin-top: 0.8rem;
  padding-top: 0.8rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.vc-sample header {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.vc-origin {
  font-size: 0.8rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.8);
}

.vc-origin.platform {
  color: #63a88c;
}

.vc-hz {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.55);
  font-variant-numeric: tabular-nums;
  margin-left: auto;
}


.vc-sample audio {
  width: 100%;
  height: 34px;
  /* Native controls, drawn dark. Left alone they arrive as a white bar on a
     black page and read as the loudest thing on it. */
  color-scheme: dark;
}

/* One line, cut with an ellipsis. A tale runs to dozens of
   lines under every recording and pushed the players apart; what the line is
   for is telling two recordings apart, and the first few words do that. The
   whole text stands in the field above. */
.vc-said {
  margin: 0.5rem 0 0;
  font-size: 0.75rem;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.4);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* --- the columns --- */

/* One grid, one column per machine plus the asking one, all of equal weight and equal height: what is asked, and
   the machines it is asked of. Six rows, and only ONE of them is elastic
   - so the heads, the triggers and the notes at the foot all stand on the same
   lines across the surface while what a column holds changes underneath them.
   Never a sideways scroller: two of the four off-screen is not a
   comparison. */
/* The stage itself is the shared one (`assets/compare-stage.css`); what is
   here is how THIS surface divides it — one column per machine plus the
   asking column, and the five rows they line up in. */
.vc-stage {
  grid-template-columns: repeat(var(--vc-cols, 5), minmax(0, 1fr));
  /* A machine column's five parts: name, what can be set, the trigger, what
     the last run still says, and what it has said so far. The settings
     (row 2) always take exactly their own content height and never more - a
     share of the leftover space here once inflated all three columns' rows
     together the moment ANY one machine produced a first recording, dragging
     every trigger down at once even in columns nobody had touched yet.
     What does not fit in the settings scrolls inside
     them (`.vc-column-body` keeps its own `overflow-y: auto`) rather than
     pushing the trigger.

     The recordings (row 5) keep a floor no short window can take away: a
     player plus the sentence under it measures about 95 px. 140 px stands
     whole regardless of what row 2 asks for, and grows into whatever is left
     once row 2 has taken its own height - which is MORE than it had under the
     old split, since row 2 no longer competes with it for a share. */
  grid-template-rows: auto minmax(0, auto) auto auto minmax(140px, 1fr);
}

/* Too narrow for the columns to be read side by side: one under the other, and
   THIS is the exception where the surface scrolls as a whole. Measured on the
   work area, not the window. */
@container (max-width: 900px) {
  /* `max-content` on the rows, and it is not a detail: the stage keeps the
     height of the work area, and auto rows in a box of fixed height share that
     height out equally between them. Five columns then get a fifth each and
     every one of them is crushed to a few lines with its contents lying on top
     of one another. Each column takes the height it needs here, and the stage
     is the thing that scrolls. */
  .vc-stage {
    grid-template-columns: 1fr;
    grid-template-rows: none;
    grid-auto-rows: max-content;
    overflow-y: auto;
  }

  /* Two classes deep, because the rules these undo are one class deep and
     stand further down the sheet - at equal weight the later one would win. */
  .vc-stage .vc-column {
    grid-row: auto;
    grid-template-rows: none;
    display: flex;
    flex-direction: column;
    min-height: auto;
  }

  /* Nothing scrolls inside a column here - the whole surface does, and a
     scroller inside a scroller is a trap on a touch screen. The asking column
     included: stacked, its box simply follows the field. */
  .vc-stage .vc-ask,
  .vc-stage .vc-ask-body,
  .vc-stage .vc-column-body,
  .vc-stage .vc-list,
  .vc-stage .vc-about {
    overflow: visible;
    min-height: auto;
  }

  .vc-stage .vc-ask > .lab-note { margin-top: 0.6rem; }
}

/* Rows the columns share, so that what differs between them - a longer note, a
   third chip row, one recording more - moves nothing on the lines beside it.
   The tallest sets the row and all five begin at the same height. The asking
   column takes the same class and the same rows: its head on the shared first
   line, its field under it, and the rows below it left empty on purpose.

   The cell of the lab, not a card: `--surface-2` on a 6 px radius behind one
   hairline, the measure Representation Engineering and the census columns are
   drawn to. */
.vc-column {
  display: grid;
  grid-template-rows: subgrid;
  grid-row: 1 / -1;
  gap: 0.6rem;
}

/* Placed by hand, because one of the five is conditional: a column that has
   not run carries no `.vc-column-out`, and auto-placement would then pull
   everything below it up a row and no two columns would close on the same
   line. */
.vc-column > .cmp-column-head { grid-row: 1; }
.vc-column > .vc-column-body { grid-row: 2; }
.vc-column > .fl-run { grid-row: 3; }
.vc-column > .vc-column-out { grid-row: 4; }
.vc-column > .vc-list { grid-row: 5; }

/* The asking column stands OUTSIDE the shared rows and lays itself out: field
   at the top, the box about the four machines at the foot. It shared the rows
   until 2026-08-26, and then the field's own resize handle moved every column
   on the surface - a field in a shared row sets that row for all five. Now
   only this column changes when the field is pulled, and what stops fitting
   scrolls above the box. */
.vc-ask {
  grid-template-rows: none;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* The room goes to the field, the box takes what its text needs: the field
   may be large here because a fairy tale goes in, and the box stands at the
   foot of the column as everywhere, taller here because of its long text.
   The other way round it was the box that grew, so three
   paragraphs of hint stood over a long empty stretch while the field holding
   a 2986-character fairy tale kept its four rows.

   `.lab-note` reaches the foot by itself - `margin-top: auto` in
   flow-stage.css, the same anchor it has on every other surface - as soon as
   it stops eating the free space. It is as tall as its own text, which is
   taller here than anywhere else on the platform: 680 pixels in a column that
   is 709 on a 900-pixel screen. So the field holds a floor and nothing more.
   Above roughly 1010 pixels of column both fit - the box entire, the field
   growing into everything left over. Below it the box gives way first and
   scrolls in itself, because the box is read once and the field is worked in.
   A share of the column would be the wrong measure here: it would go on
   taking room from the box on a tall screen, where the box has a size it
   actually wants. */
.vc-ask-body {
  flex: 1 1 auto;
  min-height: 20rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

/* The field fills what the body was given, instead of standing at its row
   count with air underneath. Its drag handle keeps working: a pulled height
   is the basis it grows from, and past the body's edge the body scrolls. */
.vc-ask-body :deep(.media-input-box) {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.vc-ask-body :deep(.bubble-textarea) {
  flex: 1 1 auto;
  min-height: 0;
}

.vc-ask > .lab-note {
  flex: 0 1 auto;
}

/* The colour of a machine, on the three places that belong to
   it alone: the edge of its column, its name, and the trigger that makes it
   speak. Everything inside keeps the greys, because green and amber are said
   in the chips and mean something there. The asking column has no machine and
   keeps the plain hairline. */
.vc-machine {
  border-color: rgb(var(--vc-tone-rgb) / 0.4);
}

.vc-machine > .cmp-column-head .vc-col-name {
  color: var(--vc-tone-lit);
}

.vc-machine > .fl-run {
  --fl-run-tone-rgb: var(--vc-tone-rgb);
  --fl-run-tone-lit: var(--vc-tone-lit);
}

/* The head of a column, at the step the lab writes its column heads in
   (`.dc-col-head`): quiet, unbolded, one size below the reading text. */
.vc-col-name {
  flex: 1;
  font-size: var(--flow-fs-label);
  color: rgba(255, 255, 255, 0.75);
}

/* Its own row, and it starts at the same height in all four machine columns because
   the row above is shared. The one elastic row of the grid, so a column with
   more to set than fits scrolls HERE — its trigger stays on screen, on the
   same line as the other two. */
.vc-column-body {
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
}

.vc-column-out {
  padding-top: 0.6rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.vc-column-out .vc-gap {
  margin-top: 0.6rem;
}

/* The platform's drop-down (registry: Klapplisten), formed like
   `.preset-select` in system_prompt_comparison.vue: the 236 speakers of the
   German corpus file, a list no row of fields could hold. */
.vc-select {
  width: 100%;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 0.25rem 0.4rem;
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.75rem;
  outline: none;
}

.vc-select option {
  background: var(--surface-2);
  color: rgba(255, 255, 255, 0.85);
}

/* Said where a language has no voice with a documented speaker. */
.vc-none {
  margin: 0;
  padding: 2.5rem 0;
  text-align: center;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.35);
}
</style>
