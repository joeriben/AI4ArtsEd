<!--
  Re-enactment (Crossmodal Lab). A recording goes through four machines in a
  row and comes back sung: two rankers sort it against a fixed list, a
  transcriber writes down words, a language model writes lyrics from both, and
  one of four sound machines performs them (devserver/my_app/services/
  parrot_service.py, docs/ARCHITECTURE PART 38 - Cover-Band.md).

  The page stands in the instrument frame of the Latent Lab
  (assets/flow-stage.css, `.lab-main` / `.lab-stage` / `.lab-work`) with one
  deviation no other instrument has: the SONG stands in the preparing column,
  under the recording. The three columns on the right are the steps in
  between, and among them the song could not be told apart from them
  (docs/DEVELOPMENT_DECISIONS.md, 2026-11-02). Recording at the top, song below it: the original and the
  re-enactment in one column.

  Until 2026-11-02 the page was the flow's band (FlowHeader, with the run panel
  in its middle node) over a board the boxes were thrown onto.
-->
<template>
  <div class="lab-page cover">
    <ShellRun
      :ready="canRun"
      :running="busy"
      :title="t('coverBand.run.start')"
      :label="t('latentLab.runLine.step')"
      :count="stepNow"
      :total="ORDER.length"
      @run="startChain"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <section class="cmp-column lab-prep lab-col col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <!-- Where the recording is made, and where it lies once it exists:
                 the box this platform takes material in, with audio as its
                 third kind (components/MediaInputBox.vue,
                 components/AudioRecordWidget.vue).

                 The trash in it is the whole reason the chain does not start by
                 itself: a recording can be listened to and discarded before it
                 has cost a song. It is also the ONLY way back, so it hides only
                 while the machines are working, and it takes the song and the
                 three columns with it (reset()).

                 So the box is NOT disabled after the run: its trash is disabled
                 with it (components/MediaInputBox.vue, since 2026-08-23), and
                 until 2026-11-02 that left the page with no way back after a
                 run. Recording straight over a finished take cannot happen
                 anyway: the widget takes no click while a take lies in it
                 (AudioRecordWidget, onZoneClick). -->
            <label class="lab-pick-label">{{ t('coverBand.record.name') }}</label>
            <MediaInputBox
              chrome="bare"
              input-type="audio"
              value=""
              :audio-src="takeUrl"
              :max-seconds="MAX_SECONDS"
              :disabled="busy || uploading"
              :is-filled="!!takeUrl"
              :show-clear="!!takeUrl && !busy && !uploading"
              @audio-recorded="onTake"
              @mic-error="error = t('coverBand.errors.noMic')"
              @clear="reset()"
            />
            <!-- Directly under the box that causes it. "No microphone" changes
                 nothing else on the page — the box simply does not start. -->
            <p v-if="error" class="lab-prep-err">{{ error }}</p>

            <!-- The four machines the last station can end on, in the order of
                 the routing table. None is chosen before a run, and that is the
                 true state: which one runs is decided by what the first station
                 HEARS (music and text, music alone, speech alone, neither). A
                 hand-pick beats the table and holds across runs; a second click
                 gives it back. Which machine ran is named under the song. -->
            <label class="lab-pick-label">{{ t('coverBand.sung.pick') }}</label>
            <ChipSelect
              :model-value="heldSinger ?? ''"
              :options="singerOptions"
              :columns="2"
              clearable
              :disabled="busy || launched"
              @update:model-value="heldSinger = ($event as string) || null"
            />

            <!-- The song: the last station's card, in the column of the
                 recording it re-enacts. It cannot be kept: the player offers no
                 download, and the file is gone with the page (abandon()). -->
            <div class="cb-out-head" :class="{ 'is-idle': status.sung === 'idle' && !waitWord('sung') }">
              <label class="lab-pick-label">{{ t('coverBand.sung.name') }}</label>
              <span v-if="waitWord('sung')" class="lab-readcol-wait">{{ waitWord('sung') }}</span>
              <!-- The machine at work, named while it works: the song takes
                   minutes, and nothing else names it until it is there. Once it
                   is, the line under the player does. -->
              <span v-if="stationModel.sung && !sungUrl" class="cb-machine">{{ stationModel.sung }}</span>
            </div>
            <FlowCard
              :key="cardGen"
              class="station cb-out"
              :class="[stationClass('sung'), { 'is-idle': status.sung === 'idle' }]"
            >
              <template v-if="sungUrl">
                <audio
                  class="cb-audio"
                  :src="sungUrl"
                  controls
                  controlsList="nodownload noplaybackrate"
                  @contextmenu.prevent
                ></audio>
                <div v-if="stationModel.sung" class="cb-by">
                  {{ t('coverBand.sung.madeBy', {
                    model: stationModel.sung,
                    s: (stationMs.sung / 1000).toFixed(1),
                  }) }}
                </div>
              </template>
              <p v-else-if="status.sung === 'failed'" class="err">{{ t('coverBand.stationFailed') }}</p>

              <template v-if="shown('sung')" #back>
                <div class="im-head">{{ t('coverBand.back.head') }}</div>
                <div v-for="r in backRows('sung')" :key="r.k" class="im-row">
                  <span class="im-k">{{ r.k }}</span>
                  <span class="im-v">{{ r.v }}</span>
                </div>
              </template>
            </FlowCard>

            <!-- The explanation box at the foot of the preparing column, the
                 platform's `.lab-note` (docs/ELEMENT_STRUCTURE_REGISTRY.md). Its
                 heading is the menu title of this surface, its text is
                 `coverBand.noteBody`, cut into paragraphs at the blank line,
                 and the titles it cites stand under it in LabReferences. -->
            <aside class="lab-note">
              <h3>{{ t('coverBand.modeTitle') }}</h3>
              <p
                v-for="(para, i) in t('coverBand.noteBody').split('\n\n')"
                :key="i"
              >{{ para }}</p>
              <LabReferences
                :title="t('coverBand.referencesTitle')"
                :items="REFERENCES"
                flat
              />
            </aside>
          </section>

          <!-- The three steps between the recording and the song, one column
               each, in the order of the chain (`.lab-readcol` on the raster
               `.lab-grid`, assets/flow-stage.css). Before a run their cards stand
               darkened under heads that say they wait; a column fills when its
               station answers, and its card scrolls in itself. Held, a card turns to what its station
               got and what it cost. -->
          <section class="lab-plot">
            <div class="lab-grid" :style="{ '--lab-grid-cols': READ.length }">
              <div
                v-for="s in READ"
                :key="s"
                class="lab-grid-col lab-readcol"
                :class="{
                  'is-waiting': status[s] === 'idle' && !!waitWord(s),
                  'is-preview': status[s] === 'idle' && !waitWord(s),
                }"
              >
                <div class="lab-readcol-head cb-head">
                  <span class="lab-readcol-name">{{ t(`coverBand.${s}.name`) }}</span>
                  <span v-if="stationMs[s]" class="lab-readcol-time">
                    {{ t('coverBand.run.took', { s: (stationMs[s] / 1000).toFixed(1) }) }}
                  </span>
                  <span v-else-if="waitWord(s)" class="lab-readcol-wait">{{ waitWord(s) }}</span>
                  <span v-if="machineFor(s)" class="cb-machine">{{ machineFor(s) }}</span>
                </div>

                <FlowCard :key="cardGen" class="station" :class="stationClass(s)" scroll>
                  <!-- What the machine of this station is, for an answer and for
                       a station that did not answer alike. -->
                  <p v-if="status[s] === 'done' || status[s] === 'failed'" class="st-note">
                    {{ s === 'ranked'
                      ? t('coverBand.ranked.note', { model: rankingModel })
                      : t(`coverBand.${s}.note`) }}
                  </p>
                  <template v-if="s === 'ranked' && status.ranked === 'done'">
                    <ol v-if="ranking.length" class="ranking">
                      <li v-for="entry in rankingHead" :key="entry.label">
                        <span class="score">{{ fmt(entry.score) }}</span>
                        <span class="label">{{ entry.label }}</span>
                      </li>
                    </ol>
                    <p v-if="rankingTail" class="tail">
                      {{ t('coverBand.ranked.last') }}
                      <span class="score">{{ fmt(rankingTail.score) }}</span>
                      <span class="label">{{ rankingTail.label }}</span>
                    </p>

                    <div v-if="secondHead.length" class="second">
                      <p class="hint">{{ t('coverBand.ranked.secondMachine', { model: secondModel }) }}</p>
                      <ol class="ranking">
                        <li v-for="entry in secondHead" :key="entry.label">
                          <span class="score">{{ fmt(entry.score) }}</span>
                          <span class="label">{{ entry.label }}</span>
                        </li>
                      </ol>
                      <p class="hint">{{ t('coverBand.ranked.secondWhy') }}</p>
                    </div>
                    <p v-else-if="secondFailed" class="err">
                      {{ t('coverBand.ranked.secondFailed', secondFailed) }}
                    </p>

                    <p v-if="ranking.length" class="hint">
                      {{ t('coverBand.ranked.ourList', { n: ranking.length }) }}
                    </p>
                    <p v-if="ranking.length" class="hint context">
                      {{ t('coverBand.ranked.culturalLimit', { model: rankingModel }) }}
                      <a
                        class="src"
                        href="https://transactions.ismir.net/articles/10.5334/tismir.341"
                        target="_blank"
                        rel="noopener noreferrer"
                      >{{ t('coverBand.ranked.culturalLimitSource') }}</a>
                    </p>
                  </template>

                  <template v-else-if="s === 'words' && status.words === 'done'">
                    <p v-if="words" class="transcript">{{ words }}</p>
                    <p v-else class="transcript none">{{ t('coverBand.words.returnedNothing') }}</p>

                    <!-- A warning here would be defensive. The word "recognised"
                         in the head does the work, and this line states what the
                         machine does rather than what it does not prove. -->
                    <p v-if="words" class="hint">{{ t('coverBand.words.notProof') }}</p>

                    <p v-if="wordsRead" class="transcript reading">{{ wordsRead }}</p>
                    <p v-if="wordsRead" class="hint">{{ t('coverBand.words.inReadingLanguage') }}</p>
                    <!-- Not only under words: an empty transcription is the
                         empty-room case this page invites, and the language the
                         machine invented before it chose a single word is the
                         most legible thing it produces there. -->
                    <p v-if="heardLanguage" class="hint">
                      {{ t('coverBand.words.whichLanguage', { language: heardLanguage }) }}
                    </p>
                  </template>

                  <template v-else-if="s === 'written' && status.written === 'done'">
                    <template v-if="lyrics">
                      <p class="tags"><span class="k">{{ t('coverBand.written.tagsLabel') }}</span> {{ tags }}</p>
                      <pre class="lyrics">{{ lyrics }}</pre>
                      <p class="hint">{{ t('coverBand.written.readAlong') }}</p>
                    </template>
                  </template>

                  <p v-else-if="status[s] === 'failed'" class="err">{{ t('coverBand.stationFailed') }}</p>

                  <template v-if="shown(s)" #back>
                    <div class="im-head">{{ t('coverBand.back.head') }}</div>
                    <div v-for="r in backRows(s)" :key="r.k" class="im-row">
                      <span class="im-k">{{ r.k }}</span>
                      <span class="im-v">{{ r.v }}</span>
                    </div>
                  </template>
                </FlowCard>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watchEffect } from 'vue'
import ChipSelect from '@/components/ChipSelect.vue'
import ColumnFold from '@/components/ColumnFold.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'
import FlowCard from '@/components/FlowCard.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import ShellRun from '@/components/ShellRun.vue'
import { usePageContextStore } from '@/stores/pageContext'
import { useI18n } from 'vue-i18n'
import { refusalKeyOf, reportRefusal } from '@/composables/useLabRun'

const { t, locale } = useI18n()

/**
 * The titles the explanation box cites: the two rankers, the speech recogniser
 * the transcriber refines and a measurement of what it invents, and the three
 * generators the last station can end on.
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'Wu et al. (2023)',
    title: '"Large-Scale Contrastive Language-Audio Pretraining with Feature Fusion and Keyword-to-Caption Augmentation"',
    venue: 'ICASSP 2023',
    doi: 'https://arxiv.org/abs/2211.06687',
  },
  {
    authors: 'Zhu et al. (2025)',
    title: '"MuQ: Self-Supervised Music Representation Learning with Mel Residual Vector Quantization"',
    venue: 'arXiv:2501.01108',
    doi: 'https://arxiv.org/abs/2501.01108',
  },
  {
    authors: 'Radford et al. (2023)',
    title: '"Robust Speech Recognition via Large-Scale Weak Supervision"',
    venue: 'ICML 2023, PMLR 202, 28492–28518',
    doi: 'https://arxiv.org/abs/2212.04356',
  },
  {
    authors: 'Koenecke et al. (2024)',
    title: '"Careless Whisper: Speech-to-Text Hallucination Harms"',
    venue: 'FAccT 2024',
    doi: 'https://doi.org/10.1145/3630106.3658996',
  },
  {
    authors: 'Yang et al. (2026)',
    title: '"HeartMuLa: A Family of Open Sourced Music Foundation Models"',
    venue: 'arXiv:2601.10547',
    doi: 'https://arxiv.org/abs/2601.10547',
  },
  {
    authors: 'Zhou et al. (2026)',
    title: '"VoxCPM2 Technical Report"',
    venue: 'VoxCPM Team, OpenBMB; arXiv:2606.06928',
    doi: 'https://arxiv.org/abs/2606.06928',
  },
  {
    authors: 'Stability AI (2026)',
    title: '"Stable Audio 3.0"',
    venue: '2026, model release',
    doi: 'https://stability.ai/stable-audio',
  },
]

// The explanation takes no fixed space on the page; Träshy offers it on a
// symbolic act. So the
// page hands over the QUESTION and Träshy answers it from what it already knows
// — its use report describes this page, and every station's state is in the
// context below. Nothing about the chain is written out twice.
const pageContext = usePageContextStore()

type Station = 'ranked' | 'words' | 'written' | 'sung'
type Status = 'idle' | 'running' | 'done' | 'failed'
type Ranked = { label: string; score: number }

// Two waits, not one. `uploading` is the recording being handed over, `busy` is
// the chain running — and between them sits the moment the page now has: a
// recording that exists, has been listened to, and has not been sent anywhere.
const uploading = ref(false)
const busy = ref(false)
/** The take itself, playable where it lies. Local only; nothing is uploaded twice. */
const takeUrl = ref('')
const error = ref('')

const recordingId = ref<string | null>(null)

// The four machines station 5 can end on, in the order of the routing
// table. The ids are output configs, so a change to one of those files
// reaches here. Must stay in step with SOUND_CONFIGS in
// devserver/my_app/services/parrot_service.py — that is the side that decides;
// this side only names and offers.
const SINGERS = [
  { id: 'heartmula_standard', label: 'HeartMuLa' },
  { id: 'stableaudio_music', label: 'SA3 Music' },
  { id: 'stableaudio_sfx', label: 'SA3 SFX' },
  { id: 'voxcpm_standard', label: 'VoxCPM2' },
]

/** A hand-pick. Null until somebody makes one; then it holds across runs. */
const heldSinger = ref<string | null>(null)

/** The four as chips. The one picked by hand says on its title that it is the one that runs. */
const singerOptions = computed(() =>
  SINGERS.map(s => ({
    value: s.id,
    label: s.label,
    title: s.id === heldSinger.value ? t('coverBand.sung.held') : undefined,
  }))
)

const status = ref<Record<Station, Status>>({
  ranked: 'idle', words: 'idle', written: 'idle', sung: 'idle',
})
const ranking = ref<Ranked[]>([])
const rankingModel = ref('')
// The second machine is shown, not hidden behind a toggle: the disagreement is
// the point, and a disagreement nobody opens is not one.
const secondModel = ref('')
const secondRanking = ref<Ranked[]>([])
// The second machine that did not answer, and the reason it gave.
const secondFailed = ref<{ model: string; cause: string } | null>(null)
const words = ref<string | null>(null)
const heardLanguage = ref('')
// Which machine, and how long the station took. Both come off the chain's own
// events; the heads of the columns and the line under the song say them.
//
// What the number is, so nobody reads more into it than it holds: wall time for
// the whole station, measured in parrot_service. It INCLUDES loading the model
// if it was not already resident, so the same station can differ by an order of
// magnitude between a cold and a warm box; the sorting box covers two machines,
// not one; and the singing scales with the recording, because the song comes
// back as long as the recording did. Four numbers in a row invite a comparison
// between the machines, and only the roughest one — seconds against minutes —
// is one the numbers can carry.
const stationModel = ref<Record<Station, string>>({
  ranked: '', words: '', written: '', sung: '',
})
const stationMs = ref<Record<Station, number>>({
  ranked: 0, words: 0, written: 0, sung: 0,
})
// Present only where the transcriber named a language and it is not the one
// selected for the platform. The words above stay exactly as they came back;
// this is an aid, not a correction — and it names its own machine, because on
// this page every machine that produces text is named.
const wordsRead = ref('')
const readModel = ref('')
const tags = ref('')
const lyrics = ref('')
const sungUrl = ref('')

// The head is what the group reads and what the writing station was given —
// deliberately the same slice, so the page does not show one thing and feed
// the model another.
const rankingHead = computed(() => ranking.value.slice(0, 8))
// The last place is not decoration. Which word a model puts at the bottom,
// every single time, is the most legible thing on this page.
const rankingTail = computed(() => ranking.value.length ? ranking.value[ranking.value.length - 1] : null)

const secondHead = computed(() => secondRanking.value.slice(0, 5))

const fmt = (n: number) => (n >= 0 ? '+' : '') + n.toFixed(2)

const ORDER: Station[] = ['ranked', 'words', 'written', 'sung']

/** The three that can be read, one column each, in the order of the chain. */
const READ: Station[] = ['ranked', 'words', 'written']

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)

/** A station is on the page once it has answered — or once it has not. */
function shown(s: Station) {
  return status.value[s] === 'done' || status.value[s] === 'failed'
}

/**
 * What a head says while its station has nothing to show: "waiting" before it
 * starts, "working…" while it runs. A station that answered says how long it
 * took instead, and one that did not answer says so in its card. After a chain
 * that broke off, the stations it never reached say nothing: they are not
 * waiting for anything.
 */
function waitWord(s: Station): string {
  if (status.value[s] === 'running') return t('coverBand.working')
  if (status.value[s] === 'idle' && (busy.value || !launched.value)) return t('coverBand.waiting')
  return ''
}

/**
 * The line beside the trigger while the chain runs: the station at work, or
 * the next one in the short gap between two.
 */
const stepNow = computed(() =>
  Math.min(ORDER.length, ORDER.filter(s => status.value[s] === 'done').length + 1)
)

/**
 * Counts the takes the cards have served. FlowCard keeps its own turned state,
 * and the cards now stay on the page across a reset: a card left turned to its
 * back would take the next run's result onto its hidden front. A new count is a
 * new card.
 */
const cardGen = ref(0)

function machineFor(s: Station) {
  // Both rankers, because both of them answered and the page says so everywhere
  // else it mentions them.
  if (s === 'ranked') {
    return [stationModel.value.ranked, secondModel.value].filter(Boolean).join(' · ')
  }
  return stationModel.value[s]
}


/**
 * A box's back: which machine, what it was given, what it cost. The same three
 * rows the flow puts on the back of a piece of material — perspective, model,
 * the prompt that was submitted (views/x2x_flow.vue). It is written once for
 * all four boxes so that the four backs cannot drift apart.
 */
const GOT: Record<Station, string> = {
  ranked: 'coverBand.back.gotRecording',
  words: 'coverBand.back.gotRecording',
  written: 'coverBand.back.gotStations',
  sung: 'coverBand.back.gotWritten',
}
function backRows(s: Station): { k: string; v: string }[] {
  const rows: { k: string; v: string }[] = []
  const machine = s === 'ranked' ? machineFor('ranked') : stationModel.value[s]
  if (machine) rows.push({ k: t('coverBand.back.machine'), v: machine })
  // A station that did not answer made nothing. The machine was asked, so it
  // can be named; "it got" and "it took" would be the back of the card
  // asserting a provenance for a result the front says does not exist.
  if (status.value[s] === 'failed') return rows
  if (s === 'words' && readModel.value) {
    rows.push({ k: t('coverBand.back.translation'), v: readModel.value })
  }
  rows.push({ k: t('coverBand.back.got'), v: t(GOT[s]) })
  if (stationMs.value[s]) {
    rows.push({
      k: t('coverBand.back.took'),
      v: t('coverBand.back.seconds', { s: (stationMs.value[s] / 1000).toFixed(1) }),
    })
  }
  return rows
}

// Only `failed` is a state of its own. A box that answered is simply the flow's
// card, with the flow's border; giving `done` a border here would be the page
// restating the card a second time.
function stationClass(s: Station) {
  return { failed: status.value[s] === 'failed' }
}

// --- the take --------------------------------------------------------------
// The microphone, the clock, the ceiling and the conversion to wav belong to
// AudioRecordWidget now — to the box that takes the recording, not to this
// page. What is left here is the page's own part: what happens to a finished
// wav.

// Recordings are capped at 240 s. The same number the
// song tops out at (SONG_MAX_MS in parrot_service), so the recording cannot run
// past what can be sung back. The box is handed the number and holds to it.
const MAX_SECONDS = 240

/** Set when the page is left, and read across every await below. */
let left = false

async function onTake(wav: Blob) {
  // Nothing should reach this line while a take is already lying here — the box
  // refuses to record over one. But the cost if it did is a recording on the
  // server that nobody holds the id of any more, and the staging sweep only
  // runs when the next person records.
  if (recordingId.value) {
    abandon()
    recordingId.value = null
  }
  releaseTake()
  uploading.value = true
  error.value = ''
  try {
    const form = new FormData()
    form.append('file', wav, 'recording.wav')
    const res = await fetch('/api/parrot/recording', { method: 'POST', body: form })
    // A proxy answers a body it will not carry with a 413 and an HTML page, not
    // with this route's JSON. Read the status first, or the actionable answer
    // ("that is longer than four minutes") is lost in the generic one.
    if (!res.ok) {
      error.value = t(res.status === 413 ? 'coverBand.errors.tooLong' : 'coverBand.errors.upload')
      uploading.value = false
      return
    }
    const data = await res.json()
    if (!data.success) {
      // The one failure the group can do something about, now that nothing
      // stops the recording for them.
      error.value = t(data.code === 'too_long'
        ? 'coverBand.errors.tooLong'
        : 'coverBand.errors.upload')
      uploading.value = false
      return
    }
    // The page can be gone by now: three awaits stand between the recording
    // ending and this line, and `left` was last read before the first of them.
    // Nobody would be holding this id, and the staging sweep only runs when the
    // next person records — so the recording this page promises to delete would
    // have sat there for the rest of the day.
    if (left) {
      void fetch(`/api/parrot/discard/${data.recording_id}`, {
        method: 'POST',
        keepalive: true,
      }).catch(() => {})
      return
    }
    recordingId.value = data.recording_id
    takeUrl.value = URL.createObjectURL(wav)
    uploading.value = false
  } catch {
    error.value = t('coverBand.errors.upload')
    uploading.value = false
  }
}

// --- the chain -------------------------------------------------------------
let source: EventSource | null = null

/**
 * Whether this recording has been let go. Not derived from the stations: the
 * server deletes the uploaded wav when the stream ends, whatever ended it
 * (parrot_routes.py, the stream route's finally), so a recording can be sent
 * exactly once and a second ▶ could only ever answer "recording not found".
 *
 * Reading it off the stations instead had it both ways and both were wrong: a
 * chain that broke at a station left the ▶ dead over a recording that still
 * looked usable, and a chain that died BEFORE its first station left every
 * status at idle — so the ▶ lit up again, over a file that was already gone,
 * and invited the same press for as long as anyone kept pressing.
 */
const launched = ref(false)
const canRun = computed(
  () =>
    !!recordingId.value &&
    !uploading.value &&
    !busy.value &&
    !launched.value
)

function startChain() {
  const id = recordingId.value
  if (!id || !canRun.value) return
  launched.value = true
  busy.value = true
  runChain(id)
}

function runChain(id: string) {
  source?.close()
  // The language of the page, so an unreadable transcription can be read.
  // This is not handed to the transcriber — see parrot_service.run_chain.
  source = new EventSource(
    `/api/parrot/stream/${id}?reading=${encodeURIComponent(locale.value)}` +
      (heldSinger.value ? `&config=${encodeURIComponent(heldSinger.value)}` : '')
  )
  source.onmessage = event => {
    const e = JSON.parse(event.data)
    // Arrives after the words themselves and only sometimes — see run_chain.
    // It is not a station: nothing on the strip waits for it.
    if (e.station === 'reading') {
      // A reading the platform's checks refused is not shown. The refusal goes
      // to the safety window, and the chain goes on without it.
      if (reportRefusal(e)) return
      wordsRead.value = e.text || ''
      readModel.value = e.model || ''
      return
    }

    if (e.station === 'chain') {
      if (e.status === 'complete') { busy.value = false; source?.close(); source = null }
      if (e.status === 'failed') {
        // NOT e.error: a station's failure carries a sentence written for
        // people, but this one carries str(exception) from the route's except
        // branch — a Python message, in English, on a page for children.
        error.value = t('coverBand.errors.chain')
        stopRunning()
      }
      return
    }

    const station = e.station as Station
    if (station in status.value) status.value[station] = e.status
    // On the running event too: the box says which machine is at work, and the
    // one that takes minutes is the one that most needs naming while it does.
    if (e.model && station in stationModel.value) stationModel.value[station] = e.model
    if (station === 'ranked' && e.first) rankingModel.value = e.first

    if (e.status === 'done') {
      stationModel.value[station] = e.model || ''
      stationMs.value[station] = e.ms || 0
      if (station === 'ranked') {
        ranking.value = e.ranking || []
        rankingModel.value = e.model || ''
        secondModel.value = e.second?.model || ''
        secondRanking.value = e.second?.ranking || []
        secondFailed.value = e.second_failed
          ? { model: e.second_failed.model || '', cause: e.second_failed.error || '' }
          : null
      }
      if (station === 'words') {
        words.value = e.text ?? ''
        heardLanguage.value = e.language || ''
        wordsRead.value = ''
        readModel.value = ''
      }
      if (station === 'written') { tags.value = e.tags || ''; lyrics.value = e.lyrics || '' }
      if (station === 'sung') sungUrl.value = `/api/parrot/sung/${id}?t=${Date.now()}`
    }
    // A station the platform's checks refused carries the block message and
    // none of the refused text: the refusal goes to the safety window, and the
    // line says it in the reader's language.
    if (e.status === 'failed' && reportRefusal(e)) error.value = t(refusalKeyOf(e))
    else if (e.status === 'failed' && e.error) error.value = e.error
  }
  source.onerror = () => {
    source?.close(); source = null
    if (busy.value) { error.value = t('coverBand.errors.chain'); busy.value = false }
    stopRunning()
  }
}

/**
 * A station the chain will never come back to. Without this the status stayed
 * 'running' after a chain-level break, and its column read as working for
 * good, next to the line saying it had broken off.
 */
function stopRunning() {
  for (const s of ORDER) {
    if (status.value[s] === 'running') status.value[s] = 'failed'
  }
}

// --- leaving ---------------------------------------------------------------
function reset() {
  // Unconditionally, and this used to take a flag. startRecording passed false,
  // so pressing Record straight after a song — rather than "record something
  // else" — dropped the previous id without telling the server, and that song
  // sat in staging until the next sweep. The page promises the opposite. There
  // is no case where this discards a live run: the button is disabled while
  // one is on.
  abandon()
  source?.close(); source = null
  recordingId.value = null
  cardGen.value++
  status.value = { ranked: 'idle', words: 'idle', written: 'idle', sung: 'idle' }
  stationModel.value = { ranked: '', words: '', written: '', sung: '' }
  stationMs.value = { ranked: 0, words: 0, written: 0, sung: 0 }
  ranking.value = []
  rankingModel.value = ''
  secondModel.value = ''
  secondRanking.value = []
  secondFailed.value = null
  words.value = null
  heardLanguage.value = ''
  wordsRead.value = ''
  readModel.value = ''
  tags.value = ''
  lyrics.value = ''
  sungUrl.value = ''
  error.value = ''
  launched.value = false
  releaseTake()
}

/**
 * Restored from the back/forward cache. `pagehide` discarded the recording on
 * the way out, but the page itself was kept whole — so without this the group
 * comes back to a take card with a working player, a line saying how long the
 * recording is, and a ▶ over a file the server deleted.
 */
function onPageShow(e: PageTransitionEvent) {
  if (e.persisted) reset()
}
window.addEventListener('pageshow', onPageShow)

/** The take's object URL. Held only while the take is on the page. */
function releaseTake() {
  if (!takeUrl.value) return
  URL.revokeObjectURL(takeUrl.value)
  takeUrl.value = ''
}

// Nothing outlives the visit — and the visit ends in more ways than one.
// onBeforeUnmount covers navigating inside the app; it does NOT run on a tab
// close or a reload, and the staging sweep only runs when the next person
// records, so without this the song sat on disk indefinitely.
function abandon() {
  const id = recordingId.value
  if (!id) return
  const url = `/api/parrot/discard/${id}`
  // sendBeacon is optional-chained everywhere else in this file, which means a
  // browser without it kept the song. keepalive is the same guarantee.
  if (navigator.sendBeacon) navigator.sendBeacon(url)
  else void fetch(url, { method: 'POST', keepalive: true }).catch(() => {})
}
window.addEventListener('pagehide', abandon)

// The context is set once and then follows the run, so what Träshy is asked
// about is the page as it stands at that moment and not as it loaded.
watchEffect(() => {
  pageContext.setPageContext({
    activeViewType: 'cover_band',
    // Nothing here is kept, and that has to hold for what Träshy is told as
    // well: the transcription and the lyrics go into the question's context.
    ephemeral: true,
    pageContent: {
      inputText: words.value ?? '',
      interceptionResult: lyrics.value,
      // NOT selectedConfig: that field renders to Help as "Modell/Config",
      // and these are the style words the writing station produced, not a model.
      selectedCategory: tags.value || null,
    },
    offer: {
      label: t('coverBand.ask.sign'),
      question: t('coverBand.ask.question'),
    },
  })
})

onBeforeUnmount(() => {
  pageContext.clearContext()
  // The box stops its own microphone and refuses to hand anything over after
  // an unmount. This flag is the page's half of the same guarantee: an upload
  // already in flight must not end up holding an id nobody can discard.
  left = true
  releaseTake()
  abandon()
  window.removeEventListener('pagehide', abandon)
  window.removeEventListener('pageshow', onPageShow)
  source?.close()
})
</script>

<style scoped>
/* The frame, the proportion, the counter, the labels, the scrolling preparing
   column and the three reading columns are shared — assets/flow-stage.css,
   `.lab-page` / `.lab-main` / `.lab-stage` / `.lab-work` / `.lab-prep` /
   `.lab-pick-label` / `.lab-prep-err` / `.lab-grid` / `.lab-readcol-*`. What stands here is
   what only this instrument does. */

/* The song's label carries its station's state at its right end, the way a
   column head does. */
.cb-out-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0 8px; }

/* A column head here has a second line: the machine, or the two machines, that
   answered. */
.cb-head { flex-wrap: wrap; }
.cb-machine {
  flex-basis: 100%;
  order: 3;
  font-size: var(--flow-fs-sub);
  color: rgba(255, 255, 255, 0.42);
  overflow-wrap: anywhere;
}

/* The box is FlowCard — the same one x2x_flow's nodes throw their output into.
   What is left here is what this page adds to it: room to read in, a height
   the column cell gives it rather than its content, and the one state the
   flow's cards do not have, a station that did not answer. */
.station { min-height: 0; padding: clamp(0.7rem, 1.4vw, 1.1rem); }
/* The failed border the flow already has, in both of its shared components
   (FlowHeader .nd.failed, FlowRunPanel .gr-st.failed). */
.station.failed { border-color: #a04040; }

/* The song's card never gives way. The preparing column is a flex column that
   scrolls, and a single-faced FlowCard carries overflow:hidden, which sets its
   automatic minimum height to zero: without this it was the one box that could
   be squeezed when the column runs long. */
.cb-out { flex: 0 0 auto; }
/* Before its station starts, the song stands back as the columns do: the
   card dimmed under a head that says it waits (`.lab-readcol.is-waiting`), the
   head dimmed too where nothing waits any more (`.lab-readcol.is-preview`). */
.cb-out.is-idle { opacity: 0.5; }
.cb-out-head.is-idle { opacity: 0.45; }

/* The player of the flow's own out node (.out-audio in views/x2x_flow.vue). */
.cb-audio { display: block; width: 100%; height: 34px; }
.cb-by { margin-top: 6px; font-size: var(--flow-fs-hint); color: rgba(255, 255, 255, 0.66); }

/* The provenance rows the flow puts on the back of its own material
   (views/x2x_flow.vue) — its shape and its two colours, not a
   second drawing of them. The heading is this page's addition: the flow's
   backs carry one kind of thing, these carry a station. */
.im-head { font-size: var(--flow-fs-sub); color: #8a8a8a; margin-bottom: 0.45rem; }
.im-row { display: flex; flex-direction: column; gap: 2px; font-size: var(--flow-fs-sub); line-height: 1.5; }
.im-k { color: #8a84a8; }
.im-v { color: #cfc9f2; overflow-wrap: anywhere; }

/* What a station says about itself, at the top of its card. */
.st-note { margin: 0 0 0.55rem; font-size: var(--flow-fs-hint); color: #9a948a; line-height: 1.45; }

.hint.context { border-top: 1px solid rgba(255, 255, 255, 0.09); margin-top: 0.6rem; padding-top: 0.5rem; }
.hint.context .src { color: inherit; text-decoration: underline; text-underline-offset: 2px; white-space: nowrap; }
.ranking { list-style: none; margin: 0; padding: 0; }
.second { margin-top: 0.9rem; padding-top: 0.7rem; border-top: 1px dashed rgba(255, 255, 255, 0.14); }
.second .ranking { margin: 0.35rem 0 0.5rem; opacity: 0.82; }
.ranking li { display: flex; gap: 0.7rem; padding: 0.12rem 0; font-size: var(--flow-fs-sub); }
.score { font-variant-numeric: tabular-nums; color: #8fa88f; min-width: 3.6rem; }
.tail { margin: 0.5rem 0 0; padding-top: 0.45rem; border-top: 1px dashed var(--surface-4); display: flex; gap: 0.5rem; align-items: baseline; flex-wrap: wrap; font-size: var(--flow-fs-sub); color: #b0a898; }
.tail .score { color: #a8776f; }

.transcript { margin: 0; font-size: var(--flow-fs-body); line-height: 1.55; }
.transcript.none { color: #8a857c; font-style: italic; }
.transcript.reading {
  color: #a49d92;
  /* Logical, not physical: ar and he render right-to-left. */
  border-inline-start: 2px solid rgba(255, 255, 255, 0.11);
  padding-inline-start: 0.7rem;
  margin-top: 0.55rem;
}

.tags { margin: 0 0 0.5rem; font-size: var(--flow-fs-sub); color: #b0a898; }
.tags .k { color: #8a857c; }
/* Written material gets the voice font wherever this platform shows it — the
   flow's .asm-ta, .hp-text and .pe-text all stand in it. The one page whose
   product IS a text was rendering it in the UI font. */
.lyrics { margin: 0; white-space: pre-wrap; font-family: var(--font-sans);
  font-size: var(--flow-fs-body); line-height: 1.5; }

.hint { margin: 0.5rem 0 0; font-size: var(--flow-fs-hint); color: #857f76; line-height: 1.45; max-width: 72ch; }
/* The flow's own error colour (.gi-err in views/x2x_flow.vue). */
.err { margin: 0.5rem 0 0; color: #e0568a; font-size: var(--flow-fs-hint); }

/* Narrow: the two sides stack, the three columns stack under them, the cards
   take the height of what they hold, and the page scrolls in itself. Measured
   on the page, not the window: the instrument rail takes 240 to 340 px of the
   window while it is open. At 900 px of page a reading column is about 185 px
   wide; below that a ranking label has hardly any room beside its score. */
.cover { container: cover / inline-size; }
@container cover (max-width: 900px) {
  .lab-main { overflow-y: auto; }
  .lab-stage { flex: 0 0 auto; }
  .lab-work, .lab-work.folded { grid-template-columns: 1fr; grid-template-rows: auto; row-gap: 16px; }
  .lab-grid { grid-template-columns: 1fr; grid-template-rows: none; grid-auto-flow: row; }
  .lab-grid-col + .lab-grid-col > .lab-readcol-head { margin-top: 14px; }
}
</style>
