<!--
  Denoising Archaeology — the second instrument laid out under the band.

  Two surfaces at 1 : 2.0467, and under them the result surface. What is studied
  here is not one image but the whole sequence — eleven to fifty-one frames,
  twenty-six of them where nothing is changed — and the sequence is looked at one
  frame at a time, in a square that wants every pixel of height the window has.

  The band of three nodes stood over these surfaces and is gone. It cost 156
  px of column height — the
  height of the band plus its gap — and on any 16:9 window height is the SHORT
  side of the square, so the whole of it came off the frame's edge. What the band
  said has a place already: the trigger is in the frame's bar (the middle of it,
  which stood empty), the finished image is the last station of the axis and the
  face of every run card, a failed run is the red line under the settings, and
  the net that denoises is chosen in this page's own left surface. The band stays
  in the flow and in Re-enactment, where it is a process display over a canvas.

  The right surface therefore carries ONE thing: the chosen frame, as large as
  the surface allows. The axis of the whole run, with the step numbers over it
  and the three sections as loose zones under it, stands in the LEFT column.
  Under the picture it took 91 px off the SHORT side of a square that is bound
  by height while its surface has width to spare — measured at 1512 x 900 the
  picture came out 578 px instead of 669, smaller than necessary.

  Two things stood here before and are gone. The filmstrip showed about eleven
  frames of a default run and scrolled sideways, so the sections lay outside the
  picture. The rows that replaced it showed all of them at once and were worse
  in a way that has nothing to do with layout: seeing the next step removes the
  reason to look at this one. Stepping along the axis, one frame at a time, is
  the instrument. Where the sections begin and end is NOT settled either - the
  platform's own text says so (`explainReadText` in i18n/en.ts: working
  coordinates, located by noise level and during training, not by step number in
  a generation run) - so the axis names them as zones without an edge, and
  vouches for nothing.

  What used to be here and is gone:
   - The page's own title and subtitle. The frame's bar carries the name.
   - „Forschungsgrundlagen" and the two explanation blocks. They belong to Help.
   - The „Generieren" button, the progress block and the empty state. The band
     says all three: the triangle runs it, the middle node pulses while it runs,
     the last node holds what came out.
   - The seed line and „Bild herunterladen". Every run is a card in the result
     surface now, with the seed on its back and download, favourite, forwarding
     and print in its own row.
-->
<template>
  <div class="da">
    <!-- The switch for the result surface, in the drawing Canvas gives it; it
         goes into the frame's bar where there is one, and stands on its own
         where there is not. Same as Encoder Fusion. -->
    <!-- `defer` is not optional here: a Teleport resolves its target against the
         live document, and on the app's FIRST render the whole tree is still
         detached, so `.shell-bar-slot` cannot be found. In a production build
         Vue then mounts nothing and says nothing — and the crash comes later,
         when the instrument is unmounted and Vue removes nodes that were never
         inserted (`parentNode` of null), which leaves the whole surface frozen
         on screen. Measured 2026-08-19: Denoising Archaeology is the Latent
         Lab's default instrument, so it is always in that first pass. -->
    <Teleport defer to=".shell-bar-slot" :disabled="!inShellFrame">
      <button
        class="shell-btn da-drawer-btn"
        :title="t('canvas.outputDrawer.title')"
        @click="drawerCollapsed = !drawerCollapsed"
      >
        <img
          v-if="!drawerCollapsed"
          src="@/assets/icons/bottom_panel_close_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg"
          alt=""
          class="shell-icon"
        />
        <img
          v-else
          src="@/assets/icons/bottom_panel_open_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg"
          alt=""
          class="shell-icon"
        />
      </button>
    </Teleport>

    <!-- The trigger, in the middle of the frame's bar. Same reasoning as the
         switch above, and the same `defer` for the same reason: on the app's
         first render the tree is still detached and the anchor cannot be found.
         It keeps breathing while a run is out — that was the middle node's job
         in the band, and a run here takes a minute and a half. -->
    <!-- The steps ARE the pictures here: this instrument captures every one of
         them, so the count in the bar says how much of the sequence already
         exists. Until the first answer from the GPU arrives, the divisor is the
         number of steps that were set - true, and it keeps the readout from
         opening as „0 / 0". -->
    <ShellRun
      :ready="canRun"
      :running="isGenerating"
      :title="t('latentLab.archaeology.generate')"
      :label="t('latentLab.runLine.step')"
      :count="runStep"
      :total="runTotalSteps || idleSteps"
      :note="runSettled ? t('latentLab.runLine.transfer') : undefined"
      @run="generate"
    />

    <div class="da-main">
      <div class="da-stage">
        <div class="da-work">
          <!-- The text and what sets the run. -->
          <section class="da-text">
            <!-- The combination Model Bias sets (views/compare/model_comparison.vue)
                 and every prompt-driven surface of the platform carries: the
                 ready-made prompts ABOVE the field they go into, and the field
                 itself with its four actions - copy, paste, perspective, English.
                 The list stood here until 2026-08-19 and went out silently with
                 the move under the band (f1279aff); its entry never left i18n. -->
            <PromptExamples
              :items="promptExamples"
              :current="promptText"
              :disabled="isGenerating"
              @pick="applyExample"
            />
            <!-- The field sits in a holder of ITS OWN, because a floor written on
                 the component root here would have to win a specificity war
                 with the component's own scoped CSS - and a zero-height flex
                 item does not clip its child, so the field rendered straight
                 over the group below (measured 2026-08-20 at 1100x820 with the
                 result surface open). The holder is this file's own element. -->
            <div class="da-field-slot">
            <MediaInputBox
              class="da-field"
              chrome="bare"
              :placeholder="t('mediaInput.freePromptPlaceholder')"
              v-model:value="promptText"
              input-type="text"
              resize-type="none"
              :is-filled="!!promptText"
              :is-loading="readingPicture"
              :disabled="isGenerating || readingPicture"
              :show-preset-button="true"
              :preset-busy="isEnriching"
              @copy="copyInputText"
              @paste="pasteInputText"
              @clear="clearInputText"
              @open-preset-selector="showPresetOverlay = true"
              @image-uploaded="handlePicture"
              @image-removed="dropPicture"
            />
            </div>
            <!-- The reading of a dropped picture, where it did not come back. -->
            <p v-if="readingFailedKey" class="lab-prep-err">{{ t(readingFailedKey) }}</p>
            <p v-if="perspectiveError" class="lab-prep-err">{{ perspectiveError }}</p>

            <!-- Which net denoises, and how its path is walked. It stands
                 under the field and above the settings drawer, because it is
                 not a setting of a run but the thing the run is OF: the two
                 nets denoise differently, and laying their sequences side by
                 side is what this instrument is for. -->
            <!-- Only the net is chosen here now. The scheduler stood beside it
                 and is gone: it was never explained anywhere on this surface,
                 and the methods it offered are history. A run now takes the
                 scheduler its own pipeline carries; the service keeps the
                 parameter, as it does for shift. -->
            <div class="da-engine">
              <span class="da-engine-title">{{ t('latentLab.archaeology.denoisingGroup') }}</span>

              <label class="lab-pick-label">{{ t('latentLab.archaeology.backboneLabel') }}</label>
              <ChipSelect
                v-model="backbone"
                :options="backboneOptions"
                :columns="2"
                :disabled="isGenerating"
              />


            </div>

            <details class="advanced-settings" :open="advancedOpen" @toggle="onAdvancedToggle">
              <summary>{{ t('latentLab.archaeology.advancedLabel') }}</summary>
              <div class="settings-grid">
                <label>
                  {{ t('latentLab.archaeology.negativeLabel') }}
                  <input v-model="negativePrompt" type="text" class="setting-input" />
                </label>
                <label>
                  {{ t('latentLab.archaeology.stepsLabel') }}
                  <input v-model.number="steps" type="number" :min="STEP_MIN" :max="STEP_MAX" class="setting-input setting-small" />
                </label>
                <label>
                  {{ t('latentLab.archaeology.cfgLabel') }}
                  <input v-model.number="cfgScale" type="number" min="1" max="20" step="0.5" class="setting-input setting-small" />
                </label>
                <SeedControl v-model:seed="seed" v-model:random="randomSeed" />
              </div>
            </details>

            <p v-if="errorMessage" ref="errLine" class="da-err">{{ errorMessage }}</p>

            <!-- The axis of the run. It stood UNDER the picture, where it took
                 91 px off the SHORT side of a square that is bound by height
                 while its surface has width to spare (measured at 1512 x 900:
                 the picture went 578 instead of 669). It reads the run, so it
                 stands under what sets the run and over the note box at the
                 foot of the column. -->
            <!-- Only once there IS a run. A greyed-out slider among controls
                 that all work reads as a fault, and it stood there through the
                 whole of the setting-up. Under the placeholder image, where it
                 stood before, the empty surface next to it said why it was
                 dead; in this column nothing says it. -->
            <!-- The step numbers over the bar, the three sections as zones
                 under it: a word under a line that runs out at both ends, no
                 edge between two. They stood over the bar with exact step
                 ranges, went, and are back in this form: approximate zones
                 carry no claim of a measured boundary. -->
            <div v-if="frames.length > 1" class="da-axis-slot">
              <label class="lab-pick-label da-live">{{ t('latentLab.archaeology.axisLabel') }}</label>
              <MarkedSlider
                class="da-axis"
                v-model="selectedIndex"
                :min="0"
                :max="frames.length - 1"
                :step="1"
                :marks="stepMarks"
                :zones="sectionZones"
                :aria-label="t('latentLab.archaeology.axisLabel')"
                :value-text="selectedCaption"
              />
            </div>

            <!-- What is the case on this surface, in the platform's own note box
                 at the foot of the preparing column, with the titles it stands
                 on open INSIDE it (docs/ELEMENT_STRUCTURE_REGISTRY.md,
                 `Erklaerkasten am Spaltenfuss`). Before, the titles stood here
                 alone, as a closed disclosure without the box around them. -->
            <aside class="lab-note">
              <h3>{{ t('latentLab.imageLab.tabs.archaeology.label') }}</h3>
              <p>{{ t('latentLab.archaeology.noteBody') }}</p>
              <LabReferences
                flat
                :title="t('latentLab.archaeology.referencesTitle')"
                :items="REFERENCES"
              />
            </aside>
          </section>

          <!-- The sequence: the chosen frame, as large as the surface allows.
               The axis it is read with stands in the left column since
               2026-08-31. -->
          <section class="da-view">
            <div class="da-frame instr-frame">
              <div v-if="frames.length" class="da-stack instr-stack">
                <div class="da-shot instr-square">
                  <!-- The frame opens full screen. It answers the keyboard too;
                       a click-only enlargement is closed to anyone who does not
                       use a pointer. -->
                  <img
                    class="da-frame-img"
                    :src="selectedSrc"
                    :alt="selectedCaption"
                    role="button"
                    tabindex="0"
                    @click="fullscreenImage = selectedSrc"
                    @keydown.enter.prevent="fullscreenImage = selectedSrc"
                    @keydown.space.prevent="fullscreenImage = selectedSrc"
                    @error="frameFailed"
                  />
                  <div class="da-frame-cap">{{ selectedCaption }}</div>
                </div>
              </div>
              <div v-else class="da-stack instr-stack da-stack-idle">
                <div class="da-shot instr-square">
                  <div class="da-frame-empty"></div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>

    <!-- One card per run. A click on its bar brings that run's whole sequence
         back into the view above, because a second run would otherwise take the
         first one's frames with it — and the series is what this instrument is
         for. The bar itself carries steps and CFG. -->
    <OutputDrawer
      :items="runs"
      :is-collapsed="drawerCollapsed"
      :title="t('latentLab.shared.runsTitle')"
      :empty-text="t('latentLab.shared.runsEmpty')"
      :default-height="340"
      :box-width="240"
      :box-height="260"
      source-view="latent-lab/denoising-archaeology"
      selectable
      @toggle-collapse="drawerCollapsed = !drawerCollapsed"
      @select="restoreRun"
      @remove="removeRun"
    />

    <InterceptionPresetOverlay
      :visible="showPresetOverlay"
      single
      @close="showPresetOverlay = false"
      @preset-selected="handlePresetSelected"
    />

    <!-- The enlarged frame carries its name and the way to take it home, in the
         shape views/latent_lab/fusion_workbench.vue gave that bar. It is here
         because a single step is what this instrument is about: the surface
         lost its own download button, the run card offers the finished image,
         and without this an intermediate step could not be saved at all. -->
    <!-- A frame large, with the record of its run beside it — and without the
         row: a frame is a look inside the run, not a medium of its own to keep
         or hand on. Its name and its download stay in the bar. -->
    <MediaFullscreen
      :src="fullscreenImage"
      :alt="fullscreenLabel"
      :back="fullscreenBack"
      @close="fullscreenImage = null"
    >
      <template #bar>
        <span class="da-fs-label">{{ fullscreenLabel }}</span>
        <a
          v-if="fullscreenImage"
          :href="fullscreenImage"
          :download="fullscreenFilename"
          class="da-fs-download"
        >
          {{ t('latentLab.archaeology.download') }}
        </a>
      </template>
    </MediaFullscreen>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, watch, nextTick, onUnmounted, toRaw } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePictureTemplate } from '@/composables/usePictureTemplate'
import { postDirectRun } from '@/services/directRun'
import { generationErrorFor, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import { usePromptPresets } from '@/lib/promptPresets'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import MediaFullscreen from '@/components/MediaFullscreen.vue'
import LabReferences, { type LabReference } from '@/components/LabReferences.vue'

import ChipSelect from '@/components/ChipSelect.vue'
import ShellRun from '@/components/ShellRun.vue'
import MarkedSlider, { type SliderMark, type SliderZone } from '@/components/MarkedSlider.vue'
import SeedControl from '@/components/SeedControl.vue'
import { useSeedAutomatic, STANDARD_SEED } from '@/composables/useSeedAutomatic'
import OutputDrawer, { type DrawerItem } from '@/components/canvas/OutputDrawer.vue'
import { drawerBack } from '@/components/canvas/drawerBack'
import type { MediaBack } from '@/components/mediaBack'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useDeviceId } from '@/composables/useDeviceId'
import { useDetailsState } from '@/composables/useDetailsState'
import { fetchInstrumentRun, useLatentLabRecorder, type InstrumentRun } from '@/composables/useLatentLabRecorder'
import { useInstrumentRuns } from '@/composables/useInstrumentRuns'
import { useFavoritesStore } from '@/stores/favorites'
import { blockedReason, safetyBlockKey } from '@/composables/useGenerationStream'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext, FocusHint } from '@/composables/usePageContext'
import { useGenerationSteps } from '@/composables/useGenerationSteps'
import { apiBase } from '@/services/labApi'

/**
 * Where the run's named sections come from. Choi et al. measured which part of
 * the schedule settles what - the reason this surface cuts the sequence where
 * it cuts it. Ho et al. is the denoising process itself.
 */
const REFERENCES: LabReference[] = [
  {
    authors: 'Choi et al. (2022)',
    title: '"Perception Prioritized Training of Diffusion Models"',
    venue: 'CVPR 2022',
    doi: 'https://doi.org/10.48550/arXiv.2204.00227',
  },
  {
    authors: 'Ho et al. (2020)',
    title: '"Denoising Diffusion Probabilistic Models"',
    venue: 'NeurIPS 2020',
    doi: 'https://doi.org/10.48550/arXiv.2006.11239',
  },
  // MMDiT is defined here, and so is the joint attention the note box contrasts
  // with the U-Net's cross-attention.
  {
    authors: 'Esser et al. (2024)',
    title: '"Scaling Rectified Flow Transformers for High-Resolution Image Synthesis"',
    venue: 'ICML 2024',
    doi: 'https://doi.org/10.48550/arXiv.2403.03206',
  },
]

const { t } = useI18n()
const pageContextStore = usePageContextStore()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const { isOpen: advancedOpen, onToggle: onAdvancedToggle } = useDetailsState('ll_archaeology_advanced')
const {
  record: labRecord,
  startSession: labStartSession,
  sessionId: labSessionId,
} = useLatentLabRecorder('denoising_archaeology')
const favoritesStore = useFavoritesStore()
const deviceId = useDeviceId()

/** Standing in the Latent Lab's frame, or on this instrument's own route. */
const inShellFrame = inject('shellFrame', false)

/**
 * The two nets that can do the denoising, one output config each. The config
 * carries the model SHEET as well as the model, so a run's card states the
 * architecture and the licence that actually ran; a field on the request would
 * have left the sheet claiming SD3.5 while SDXL computed.
 *
 * `cfg` is that backbone's own default, and switching moves the value only
 * while it still stands at the other one's - a hand-set number is not overruled.
 */
type Backbone = 'sd35' | 'sdxl'
interface BackboneOption { value: Backbone; label: string; aside: string; config: string; cfg: number }
const BACKBONES: BackboneOption[] = [
  { value: 'sdxl', label: 'SDXL (2023)', aside: 'U-Net', config: 'denoising_archaeology_sdxl_comfyui', cfg: 7.0 },
  { value: 'sd35', label: 'SD 3.5 (2024)', aside: 'MMDiT', config: 'denoising_archaeology_comfyui', cfg: 4.5 },
]

/**
 * The rules SDXL can be walked with. They are the loaded pipeline's own
 * `compatibles` (diffusers 0.36, read off the installed version): fifteen, of
 * which EDM Euler is left out because SDXL is not EDM-trained and its sigma
 * range is a different scale entirely.
 *
 * `order: 2` asks the net TWICE per step, so such a run returns 2n-1 frames
 * where n steps were set - measured: Heun at 12 steps returns 23 frames. That
 * is what those methods do, and the caption says so rather than hiding it.
 *
 * SD3.5 has no such list: rectified flow walks a straight path, and diffusers
 * reports exactly one compatible scheduler for it. Its own scheduler config
 * carries `shift: 3.0`, and that is what every SD 3.5 run here uses; the slider
 * that let it be set went on 2026-08-31.
 */
/** One captured frame as the generation route sends it. */
interface StepImage {
  step: number
  timestep: number
  image_base64: string
}

/**
 * One captured frame as the surface HOLDS it: where the picture is, and which
 * step of the run it belongs to. The address is the URL of a stored part for a
 * run the storage handed back (a run taken out of the Ablage, and since
 * 2026-09-22 a fresh one as well, because the server writes the record and
 * answers with the addresses, see `generate`), or a data URL where the answer
 * brought the bytes. Both are read the same way from here on.
 */
interface StepShot {
  /** 1-based step of the run. */
  step: number
  /** The corrector of a second-order method — the net's SECOND look at it. */
  second: boolean
  src: string
}

/** One frame of the run: a step, or the finished image at the end. */
interface Frame {
  src: string
  phase: 'early' | 'mid' | 'late' | 'final'
  /** 1-based step number; absent on the final image. */
  step?: number
  /** The corrector of a second-order method - the net's SECOND look at this step. */
  second?: boolean
}

// ============================================================================
// STATE
// ============================================================================

const promptText = ref('')

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
const negativePrompt = ref('')
/** The range the step field states. A number input does not enforce it, and an
 *  emptied field yields the empty string, so the run clamps the value itself. */
const STEP_MIN = 10
const STEP_MAX = 50
const steps = ref(25)
const cfgScale = ref(4.5)
const seed = ref(STANDARD_SEED)

/** Which net denoises, and how its path is walked. */
const backbone = ref<Backbone>('sd35')
/** How often the net was asked per step in the run now on the surface. Read off
 *  what came back, not off what was chosen - the service keeps its own scheduler
 *  when it does not know a name, and then the frames are first order after all. */
const schedulerOrder = ref(1)
const randomSeed = ref(false)

/**
 * Everything a run goes out with except its seed, as one key: what the seed
 * automatic compares the next press with.
 */
function inputsKey(): string {
  return JSON.stringify([promptText.value, negativePrompt.value, steps.value, cfgScale.value,
    backbone.value])
}
const seedAutomatic = useSeedAutomatic(seed, randomSeed, 'lat_lab_da_seed_yardstick')

const isGenerating = ref(false)
const errorMessage = ref('')

const stepShots = ref<StepShot[]>([])
const finalShot = ref('')
const totalSteps = ref(25)
const actualSeed = ref(0)
const selectedIndex = ref(0)

/**
 * The runs of this instrument, as its strip lays them. The cards come back
 * after a reload: every run of this tab's sittings lies complete on disk, and
 * `cardFor` below is how one of them becomes a card again.
 */
const { runs, removeRun: dropRun } = useInstrumentRuns('denoising_archaeology', cardFor)
/** Each run's frames, so a card can bring its sequence back. `inputs` and
 *  `madeSeed` are what the seed automatic compares with once the card's picture
 *  stands on the surface again: null where the run's inputs or seed are not
 *  known. */
const runFrames = ref<Map<string, {
  shots: StepShot[]; final: string; total: number; seed: number; order: number
  inputs: string | null; madeSeed: number | null
}>>(new Map())
/** Which run the surface is showing — so that taking its card away takes it. */
const currentRunId = ref<string | null>(null)
const drawerCollapsed = ref(true)
const fullscreenImage = ref<string | null>(null)

/** The perspective that rewrites the prompt, and the wait while it does. */
const showPresetOverlay = ref(false)
const isEnriching = ref(false)

const canRun = computed(() => !!promptText.value.trim() && !isGenerating.value)

const currentBackbone = computed<BackboneOption>(
  () => BACKBONES.find(b => b.value === backbone.value) ?? (BACKBONES[0] as BackboneOption),
)
const backboneOptions = computed(() =>
  BACKBONES.map(b => ({ value: b.value, label: b.label, aside: b.aside })),
)
/**
 * Switching the net moves CFG to that net's own default - but only while it is
 * still standing at the other one's. A number somebody set by hand belongs to
 * them and is not overruled by a switch.
 */
// `sync`, so the move happens AS the net is set, inside the caller, and not in
// the microtask after it. Under the default pre-flush the callback ran once
// with CFG already holding the number written AFTER the net, which is the
// reverse of the order both callers below set up: an SDXL reading of 4.5 came
// back as 7.0. For a stored run that is a guard, since none of the 42 stands at
// the other net's default. For the session it was a live loss: a 4.5 typed by
// hand under SDXL was moved to 7.0 on the first return, and the persistence
// watcher wrote the 7.0 back, so the number the user set was gone after one
// visit and the move never happened again.
watch(backbone, (now, before) => {
  const from = BACKBONES.find(b => b.value === before)
  const to = BACKBONES.find(b => b.value === now)
  if (from && to && cfgScale.value === from.cfg) cfgScale.value = to.cfg
}, { flush: 'sync' })

// ============================================================================
// THE SEQUENCE
// ============================================================================

/**
 * Which section a step falls in. The thresholds are the ones this instrument
 * has always used (0.33 / 0.67 of the run), so the same step keeps the same
 * section as before the surface changed.
 *
 * `step` is the model's own step number, not the frame's place in the array,
 * and the divisor is the number of steps ASKED FOR. The two differ as soon as
 * the backend drops a capture — it logs the failure and appends nothing
 * (`gpu_service/services/diffusers_backend.py`) — and then a position in the
 * array is no longer a step of the run.
 */
function phaseOf(step: number, total: number): 'early' | 'mid' | 'late' {
  if (total <= 0) return 'early'
  const ratio = (step - 1) / total
  if (ratio < 0.33) return 'early'
  if (ratio < 0.67) return 'mid'
  return 'late'
}

/**
 * Which step of the RUN a captured frame belongs to.
 *
 * A first-order method asks the net once per step, so the capture index is the
 * step. A second-order method asks twice - once at the step, once at the point
 * it is aiming for - and diffusers runs both as ordinary loop passes, so the
 * captures come in pairs: (0,1) is step 1, (2,3) is step 2, and the last step
 * has no partner. Measured 2026-08-20: Heun at 12 steps returns 23 frames.
 *
 * The index used here is the one the SERVICE counted, not the frame's place in
 * the array, because a capture that fails is logged and left out - and then the
 * position in the array is no longer the position in the run.
 */
function stepOfCapture(captureIndex: number): { step: number; second: boolean } {
  if (schedulerOrder.value < 2) return { step: captureIndex + 1, second: false }
  return { step: Math.floor(captureIndex / 2) + 1, second: captureIndex % 2 === 1 }
}

/**
 * The number the frames are counted against, „Step 3 / 25".
 *
 * One place, because three readers ask: the two captions and the phase of each
 * frame. The record names the number; where it names none, the frames it holds
 * are the count, so a caption never reads over 0.
 */
const framesTotal = computed(() => totalSteps.value || stepShots.value.length)

const frames = computed<Frame[]>(() => {
  const total = framesTotal.value
  const out: Frame[] = stepShots.value.map(shot => ({
    src: shot.src,
    phase: phaseOf(shot.step, total),
    step: shot.step,
    second: shot.second,
  }))
  if (finalShot.value) {
    out.push({ src: finalShot.value, phase: 'final' })
  }
  return out
})
const selectedSrc = computed(() => frames.value[selectedIndex.value]?.src ?? '')

const selectedCaption = computed(() => {
  const f = frames.value[selectedIndex.value]
  if (!f) return ''
  if (f.phase === 'final') return t('latentLab.archaeology.finalImageLabel')
  const evalWord = f.second ? ` · ${t('latentLab.archaeology.secondEvaluation')}` : ''
  return `${t('latentLab.archaeology.timelineLabel')} ${f.step} / ${framesTotal.value}${evalWord}`
})

/**
 * The places on the axis are the STEP NUMBERS, thinned so about six of them
 * stand however long the run is.
 *
 * Three named sections - Komposition, Semantik, Detail - stood here, each over
 * the stretch of axis it claimed, with the exact steps it covered under the
 * name („1–9" at the preset 25 steps). They went: this surface's own note box
 * states that they are rough orientations and no verified boundaries (Choi et
 * al. measure by noise level, during training), and a name printed over a
 * stretch of the axis with exact values says what is to be seen there before
 * anybody has looked. They now stand under the bar as zones without exact
 * values (`sectionZones`).
 */
const stepMarks = computed<SliderMark[]>(() => {
  const items = frames.value
  const n = items.length
  if (n < 2) return []
  const every = Math.max(1, Math.round((n - 1) / 5))
  const out: SliderMark[] = []
  items.forEach((f, idx) => {
    if (f.phase === 'final' || idx % every !== 0) return
    out.push({ value: f.step ?? idx + 1, pct: (idx / (n - 1)) * 100 })
  })
  return out
})

/**
 * The three sections as zones under the axis, loosely: each from half a step
 * before the first frame `phaseOf` puts in it to half a step after the last,
 * so neighbouring zones meet and a section left with a single frame (after
 * dropped captures) still has a length. The component draws each as a word
 * under a line that runs out at both ends, with no edge between two. Not a step
 * range and not a boundary - the thresholds are this instrument's working
 * coordinates, and the zones say roughly where, nothing more. Back in this form
 * because the objection was to exact values; approximate zones carry no such
 * claim. The finished image at the end of the axis belongs to no zone.
 */
const sectionZones = computed<SliderZone[]>(() => {
  const items = frames.value
  const n = items.length
  if (n < 2) return []
  const words: Record<'early' | 'mid' | 'late', string> = {
    early: t('latentLab.archaeology.phaseEarly'),
    mid: t('latentLab.archaeology.phaseMid'),
    late: t('latentLab.archaeology.phaseLate'),
  }
  const pct = (idx: number) => (Math.max(0, Math.min(n - 1, idx)) / (n - 1)) * 100
  return (['early', 'mid', 'late'] as const).flatMap(id => {
    const idxs = items.flatMap((f, idx) => (f.phase === id ? [idx] : []))
    const first = idxs[0]
    const last = idxs[idxs.length - 1]
    if (first === undefined || last === undefined) return []
    return [{ label: words[id], fromPct: pct(first - 0.5), toPct: pct(last + 0.5) }]
  })
})

/**
 * How many steps the next run will have. It is what the bar counts against
 * until the first answer from the GPU arrives - and it kept the readout from
 * opening as „0 / 0". The axis it also fed, standing dimmed under the empty
 * frame, went on 2026-08-31.
 */
const idleSteps = computed(() =>
  Math.min(STEP_MAX, Math.max(STEP_MIN, Math.round(Number(steps.value) || STEP_MIN))),
)
/**
 * The step a RUNNING pass is on, asked of the GPU service once a second while
 * one is out. It is the count of pictures this instrument already has: every
 * step is captured here, so the two numbers are the same number.
 */
const {
  step: runStep,
  totalSteps: runTotalSteps,
  settled: runSettled,
} = useGenerationSteps(isGenerating)

/** The frame currently standing full screen — a step, or the finished image. */
const fullscreenFrame = computed<Frame | null>(() => {
  if (!fullscreenImage.value) return null
  return frames.value.find(f => f.src === fullscreenImage.value) ?? null
})

/**
 * The record of the run the frame belongs to, as its card in the strip carries
 * it, read from the strip's own reading of the card (components/canvas/
 * drawerBack.ts) so the two cannot differ. Only while the frames on the surface
 * are the ones the card holds: while a run is being made, and after one that
 * failed past its frames, the surface shows new frames under the id of the run
 * before, and that run's record would stand beside them. The AI marking is
 * asked for where the frame's address is a served file of the run
 * (`/api/media/…`, the finished picture of a run read back from the storage);
 * a step, served as a part or held as a data URL, and a fresh run's picture,
 * held as a data URL, are never asked (`useMediaDisclosure`).
 */
const fullscreenBack = computed<MediaBack | null>(() => {
  const src = fullscreenImage.value
  const id = currentRunId.value
  if (!src || !id) return null
  const own = toRaw(runFrames.value.get(id)?.shots ?? null) === toRaw(stepShots.value)
  const item = own ? runs.value.find(r => r.id === id) : undefined
  if (!item) return null
  return { ...drawerBack(item, false), mediaType: undefined, mediaUrl: src }
})

const fullscreenLabel = computed(() => {
  const f = fullscreenFrame.value
  if (!f) return t('latentLab.archaeology.finalImageLabel')
  if (f.phase === 'final') return t('latentLab.archaeology.finalImageLabel')
  const evalWord = f.second ? ` · ${t('latentLab.archaeology.secondEvaluation')}` : ''
  return `${t('latentLab.archaeology.timelineLabel')} ${f.step} / ${framesTotal.value}${evalWord}`
})

/** The name the old surface saved under, kept so older files still sort with newer. */
const fullscreenFilename = computed(() => {
  const f = fullscreenFrame.value
  const s = actualSeed.value || seed.value
  // Two frames share a step number under a second-order method; without the
  // mark the corrector would overwrite the step it belongs to.
  if (f && f.phase !== 'final') {
    return `denoising_step_${f.step}${f.second ? '_eval2' : ''}_seed_${s}.jpg`
  }
  return `denoising_final_seed_${s}.png`
})

// ============================================================================
// THE RUN
// ============================================================================

/**
 * What this instrument can be asked, ready to pick. One entry: the prompt this
 * page has always shown as its example.
 */
const promptExamples = usePromptPresets()

function applyExample(item: { fill: string[] }) {
  promptText.value = item.fill[0] ?? ''
}

/**
 * A perspective rewrites the prompt, in the platform's one way: the interception
 * pipeline answers, and its answer replaces the text in the field. Written out
 * the same as Encoder Fusion (views/surrealizer.vue) - the two are the same
 * field with the same four actions.
 */
// What the ring in the corner of the field says when the perspective wrote
// nothing: a refusal, a failure with its status, an empty answer, or no
// connection (composables/useLabRun.ts). Until 2026-10-10 all four ended in
// the console here, and the ring spun and stopped in silence.
const perspectiveError = ref('')

async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  if (!promptText.value.trim()) return

  isEnriching.value = true
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, promptText.value, deviceId)
    if ('written' in outcome) {
      promptText.value = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (error) {
    perspectiveError.value = generationErrorFor(t, error)
  } finally {
    isEnriching.value = false
  }
}


function copyInputText() { copyToClipboard(promptText.value) }
function pasteInputText() { promptText.value = pasteFromClipboard() }
function clearInputText() { promptText.value = ''; sessionStorage.removeItem('lat_lab_da_prompt') }

/* Both surfaces scroll when the result surface takes their room, and this line
   is the last child of the left one — so it can sit below the visible edge with
   the settings drawer open. It fetches the eye when it appears. */
const errLine = ref<HTMLElement | null>(null)
watch(errorMessage, (msg) => {
  if (!msg) return
  nextTick(() => errLine.value?.scrollIntoView({ block: 'nearest' }))
})

async function generate() {
  if (!canRun.value) return

  const runSteps = Math.min(STEP_MAX, Math.max(STEP_MIN, Math.round(Number(steps.value) || STEP_MIN)))
  steps.value = runSteps

  isGenerating.value = true
  errorMessage.value = ''
  stepShots.value = []
  finalShot.value = ''
  selectedIndex.value = 0

  // The seed automatic (composables/useSeedAutomatic): the same seed when
  // something changed since the picture on the surface was made, a new one
  // when nothing did, the field's when it was typed, a new one on every run
  // under the tick. The seed goes into the field.
  const runInputs = inputsKey()
  const runSeed = seedAutomatic.seedForRun(runInputs)

  try {
    const baseUrl = apiBase()
    // The sitting is opened before the run, so the server can write the run
    // into it: the request names it under `record`, and the answer carries the
    // written run's id. Until 2026-09-22 the step frames and the picture went
    // back up from here as the record, after they had already been shown:
    // measured that day on lab6000, 64.5 s and 79 s of upload during which the
    // axis stood finished on the surface under „Waiting for transfer", with
    // the trigger locked. Without a sitting the request carries no `record`
    // and the record is written from here as before (`labRecord`, below). The
    // server side is services/denoising_archaeology_record.py.
    await labStartSession()
    const response = await postDirectRun({
      prompt: promptText.value,
      output_config: currentBackbone.value.config,
      seed: runSeed,
      negative_prompt: negativePrompt.value,
      steps: runSteps,
      cfg: cfgScale.value,
      ...(labSessionId.value
        ? {
            record: {
              session_id: labSessionId.value,
              // The sitting belongs to the device that opened it, and the
              // server checks that.
              device_id: deviceId,
              // What the server cannot know about this run: the seed the
              // automatic put into the field, with the tick that says whether
              // it was drawn regardless of what changed.
              seed: runSeed,
              random_seed: randomSeed.value,
            },
          }
        : {}),
    }, { baseUrl })

    // The surface asked for the record and the server refused it; the run is
    // answered with its bytes and recorded from here. A sitting the server no
    // longer knows (a restart in between) is opened again by the next record.
    const refused = response.data?.record_refused
    if (typeof refused === 'string') {
      console.warn('[DenoisingArchaeology] the server did not record the run:', refused)
      if (refused === 'no_open_sitting') labSessionId.value = null
    }

    if (response.data.status === 'success') {
      const archData = response.data.archaeology_data
      // The run as the storage hands it back, when the server wrote the record.
      const stored: InstrumentRun | null = response.data.instrument?.run_id
        ? response.data.instrument
        : null
      // A run can come back successful and empty: every per-step capture is
      // caught on its own in the backend, so a decode that runs out of memory
      // drops all of them. Without this the surface would simply stay blank
      // and a card would be laid down that restores nothing.
      const gotFrames = !!archData && (!!archData.step_images?.length || !!archData.image_base64)
      if (gotFrames) {
        totalSteps.value = archData.total_steps || runSteps
        // What the service actually ran with. A name it did not recognise leaves
        // its own scheduler in place, so believing the choice here would label
        // first-order frames as pairs. It stands BEFORE the frames are built:
        // which step a capture belongs to is read from it.
        schedulerOrder.value = archData.scheduler_order || 1
        const captures: StepImage[] = archData.step_images || []
        // The frames of a fresh run are the bytes of the answer, held here.
        // They were addresses for one build on 2026-09-22, and the axis lost
        // what it is for: a frame then had to travel (about 1 MB) at the moment
        // it was selected, so dragging the handle showed the frame before it
        // until the next one arrived. The record is written on the server
        // either way; only the picture the axis shows comes from here.
        stepShots.value = captures.map((img) => {
          const { step, second } = stepOfCapture(img.step)
          return { step, second, src: `data:image/jpeg;base64,${img.image_base64}` }
        })
        finalShot.value = archData.image_base64
          ? `data:image/png;base64,${archData.image_base64}`
          : ''
        // What the service reported, and null where it reported nothing. The
        // two are told apart because a run recorded at seed 0 is a run made at
        // seed 0 — the AI-Origin Disclosure of its picture names that number.
        const reported = typeof archData.seed === 'number' ? archData.seed
          : typeof response.data.media_output?.seed === 'number' ? response.data.media_output.seed
          : null
        actualSeed.value = reported ?? runSeed
        selectedIndex.value = 0
        // This picture is now the one the next press is compared with.
        seedAutomatic.arrived(runInputs, actualSeed.value)

        // The run goes into the platform's storage BEFORE its card is laid
        // down, and the card is then made under the stored run's own id. It was
        // the other way round first — card immediately, address moved when the
        // write returned — and in that window (twenty-five frames, some twenty
        // megabytes) the star stored the pipeline's run, which holds the picture
        // and nothing else. A card that cannot be stored correctly is not shown.
        //
        // Where the answer brought the stored run, the server has written it
        // already and its id is the address. Otherwise the record is written
        // from here, bytes and all.
        //
        // Should the write fail, the pipeline's run is the only address there
        // is: the picture stays reachable, the sequence does not.
        const labRunId = stored ? stored.run_id : await labRecord({
          parameters: {
            prompt: promptText.value,
            negative_prompt: negativePrompt.value,
            steps: runSteps,
            cfg: cfgScale.value,
            seed: runSeed,
            random_seed: randomSeed.value,
            backbone: backbone.value,
            // What ran, and where the other half of this generation lies: the
            // pipeline's own run carries the config, the safety level and the
            // served file. Without the two naming each other, a stored run
            // cannot be read back to either.
            output_config: currentBackbone.value.config,
            pipeline_run_id: response.data.run_id ?? null,
          },
          results: {
            ...(reported === null ? {} : { seed: reported }),
            total_steps: totalSteps.value,
            scheduler: archData.scheduler,
            scheduler_order: schedulerOrder.value,
          },
          outputs: archData.image_base64
            ? [{ type: 'image' as const, format: 'png', dataBase64: archData.image_base64 }]
            : undefined,
          // Each part says which step of the run it is, and whether it is the
          // second look of a second-order method. Read off the part on the way
          // back, so a restored run does not depend on this surface still
          // standing at the scheduler order that made it.
          steps: captures.map((img) => {
            const { step, second } = stepOfCapture(img.step)
            return { format: 'jpg', dataBase64: img.image_base64, meta: { step, second } }
          }),
        })

        const runId = labRunId || response.data.run_id || `da_${Date.now()}`
        currentRunId.value = runId
        // The card shows the served file, as every other card on the platform
        // does — favourite, forwarding and download all pass a URL on. The
        // viewer keeps the frames as they came, addresses or the base64 above.
        const mediaUrl = response.data.media_output?.url || finalShot.value
        runFrames.value.set(runId, {
          shots: stepShots.value,
          final: finalShot.value,
          total: totalSteps.value,
          seed: actualSeed.value,
          order: schedulerOrder.value,
          inputs: runInputs,
          madeSeed: actualSeed.value,
        })
        runs.value.push({
          id: runId,
          // In the card's bar: what tells two runs of this instrument apart.
          // In the card's bar: what tells two runs of this instrument apart, and
          // since there are two nets now, which one ran comes first.
          label: `${currentBackbone.value.label} · ${t('latentLab.archaeology.stepsLabel')} ${totalSteps.value}`,
          sub: `${t('latentLab.archaeology.cfgLabel')} ${cfgScale.value}`,
          // On its back, with the prompt and the model's sheet: the record.
          meta: [`${t('latentLab.archaeology.seedLabel')}: ${actualSeed.value}`],
          prompt: promptText.value,
          configId: currentBackbone.value.config,
          createdAt: Date.now(),
          modelMeta: response.data.model_meta ?? null,
          // The address the Ablage stores. It is the run the recorder wrote —
          // the whole object — wherever that write succeeded.
          runId,
          output: { url: mediaUrl, media_type: 'image' },
          error: null,
        })
      } else {
        errorMessage.value = t('generationError.unknown')
      }
    } else {
      // A blocked run is read as what it is and said in the reader's language;
      // the backend's own sentence is German and stays behind the reading.
      const blockedBody = blockedReason(response.data)
      errorMessage.value = blockedBody
        ? t(safetyBlockKey(blockedBody, response.data.stage))
        : generationErrorFor(t, response.data.error || response.data.message || '')
    }
  } catch (err: any) {
    const blocked = blockedReason(err)
    errorMessage.value = blocked
      ? t(safetyBlockKey(blocked, err.response?.data?.stage))
      : generationErrorFor(t, err)
  } finally {
    isGenerating.value = false
  }
}

/** A click on a card's bar brings that run's sequence back into the view. */
/**
 * One of this instrument's own runs, read off a card that came back with the
 * sitting: this tab never held its frames, and they lie on the server with the
 * rest of the run.
 */
function cardFor(run: InstrumentRun): DrawerItem | null {
  const params = (run.parameters || {}) as Record<string, unknown>
  const results = (run.results || {}) as Record<string, unknown>
  const image = (run.outputs || []).find(o => o.type === 'image')
  if (!image?.url) return null
  const bone = BACKBONES.find(b => b.value === params.backbone)
  const steps = results.total_steps ?? params.steps ?? ''
  return {
    id: run.run_id,
    // Joined over what the record actually names. Written as one string with a
    // separator in it, a run that names no net read „· Steps 25", with a
    // separator standing before nothing.
    label: [
      bone?.label,
      steps === '' ? '' : `${t('latentLab.archaeology.stepsLabel')} ${steps}`,
    ].filter(Boolean).join(' · '),
    sub: `${t('latentLab.archaeology.cfgLabel')} ${params.cfg ?? ''}`,
    meta: [`${t('latentLab.archaeology.seedLabel')}: ${results.seed ?? params.seed ?? ''}`],
    prompt: String(params.prompt ?? ''),
    // Six stored runs name their net and no config. The net decides the config
    // on this surface, so the card can say which one made the run instead of
    // leaving the line empty.
    configId: String(params.output_config ?? bone?.config ?? ''),
    createdAt: Date.parse(run.timestamp || '') || Date.now(),
    modelMeta: null,
    runId: run.run_id,
    output: { url: image.url, media_type: 'image' },
    error: null,
  }
}

/**
 * Which card the user last asked for. A restored card is read from disk, and
 * without this the answer to an earlier click landed on the surface after a
 * later one - or over a prompt the user had already begun to type.
 */
let wantedRun: string | null = null

async function restoreRun(id: string) {
  wantedRun = id
  const kept = runFrames.value.get(id)
  if (!kept) {
    // A card that came back with the sitting: the whole run, parts and all, is
    // read from where it has lain since it was made.
    const run = await fetchInstrumentRun(id)
    if (wantedRun !== id) return
    if (run) applyInstrumentRun(run)
    return
  }
  stepShots.value = kept.shots
  finalShot.value = kept.final
  totalSteps.value = kept.total
  actualSeed.value = kept.seed
  schedulerOrder.value = kept.order
  selectedIndex.value = 0
  currentRunId.value = id
  // The fields stay as they are; the next press is compared with this picture.
  seedAutomatic.laidBack(kept.inputs, kept.madeSeed)
}

/**
 * The frames of a stored run, read off its parts. Each part says which step of
 * the run it is and whether it is the second look of a second-order method,
 * written when it was recorded — by the server since 2026-09-22
 * (services/denoising_archaeology_record.py), by this surface before that.
 * A fresh run and one taken back out of the Ablage are read here alike.
 */
function shotsOf(obj: InstrumentRun): { shots: StepShot[]; final: string } {
  const shots = (obj.parts || [])
    .filter(part => part.kind === 'step')
    .map((part, idx) => {
      const meta = part.meta || {}
      // A part written before the step number travelled with it: the place in
      // the sequence is all there is, and the run's own order turns it back
      // into a step.
      const fallback = stepOfCapture(idx)
      return {
        step: Number.isFinite(Number(meta.step)) ? Number(meta.step) : fallback.step,
        second: meta.second === true,
        src: part.url,
      }
    })
  return { shots, final: obj.outputs?.find(o => o.type === 'image')?.url ?? '' }
}

/**
 * A frame the box could not show. The part route answers a missing part with
 * its own sentence and a 404; the sentence is fetched and put on the error
 * line, so the gap has a cause on the surface. A request that fails before
 * any answer carries the browser's word for it.
 */
async function frameFailed(): Promise<void> {
  const f = frames.value[selectedIndex.value]
  if (!f || f.src.startsWith('data:')) return
  let cause: string
  try {
    const res = await fetch(f.src)
    let said: unknown
    try {
      said = (await res.json())?.error
    } catch {
      said = undefined
    }
    cause = typeof said === 'string' && said.trim() ? said.trim() : `HTTP ${res.status}`
  } catch (err) {
    cause = err instanceof Error ? err.message : String(err)
  }
  errorMessage.value = t('latentLab.archaeology.frameFailed', {
    frame: f.phase === 'final'
      ? t('latentLab.archaeology.finalImageLabel')
      : `${t('latentLab.archaeology.timelineLabel')} ${f.step}`,
    m: cause,
  })
}

/**
 * A run taken back out of the Ablage.
 *
 * What arrives is the object the storage kept for this instrument: the
 * parameters the run was made with, its ordered parts, and what came out. The
 * parts are not pictures the surface has to interpret — each one says which
 * step of the run it is and whether it is the second look of a second-order
 * method, written when it was recorded. That is read, not recomputed: this
 * surface may stand at another scheduler by now.
 */
function applyInstrumentRun(obj: InstrumentRun) {
  const p = obj.parameters || {}
  const r = obj.results || {}

  // The net comes FIRST: switching it moves CFG to that net's default while
  // CFG still stands at the other one's, so a CFG set before the net would be
  // overwritten by the switch — an SDXL run recorded at 4.5 would come back
  // reading 7.0 while its own card says 4.5.
  //
  // Whether every input the run went out with is read back onto the surface.
  // Where one is not, the surface's settings are not the picture's, and the
  // seed automatic counts the next press as a change.
  let readWhole = true
  if (p.backbone === 'sd35' || p.backbone === 'sdxl') backbone.value = p.backbone
  else readWhole = false
  if (typeof p.prompt === 'string') promptText.value = p.prompt
  else readWhole = false
  if (typeof p.negative_prompt === 'string') negativePrompt.value = p.negative_prompt
  else readWhole = false
  if (Number.isFinite(Number(p.steps))) steps.value = Number(p.steps)
  else readWhole = false
  if (Number.isFinite(Number(p.cfg))) cfgScale.value = Number(p.cfg)
  else readWhole = false

  // The divisor under every frame („Step 3 / 25"), and it comes from the
  // record alone. Falling back to the steps box put the visitor's number under
  // a picture made at another one. Where the record names no total there is
  // none: the two runs in that state hold no frames either, so nothing is
  // captioned with it.
  totalSteps.value = Number(r.total_steps) || Number(p.steps) || 0
  schedulerOrder.value = Number(r.scheduler_order) || 1

  // The seed field shows the number that MADE this picture, not the one that
  // stood in the box: under „random variation" the box held nothing that
  // produced it. A run that drew its own seed says so by the two disagreeing —
  // the box went to the service as -1 and the service wrote back what it drew.
  // Numbers, read as numbers: `Number(null)` and `Number('')` are both 0, and a
  // 0 taken for a seed would show under a picture that was made at another one.
  const boxSeed = typeof p.seed === 'number' && Number.isFinite(p.seed) ? p.seed : NaN
  // The seed that made the picture stands in the result, and a run that
  // reported none records no seed at all — 0 there is the seed 0, which runs
  // like any other. „No seed" is therefore null here and never a falsy number.
  // The box may hold -1, which is this surface's sign for „random variation"
  // and no seed at all.
  const madeSeed = typeof r.seed === 'number' && Number.isFinite(r.seed) ? r.seed : NaN
  const knownSeed = Number.isFinite(madeSeed) ? madeSeed
    : Number.isFinite(boxSeed) && boxSeed !== -1 ? boxSeed
    : null
  actualSeed.value = knownSeed ?? 0
  // Which of the two the run was made under is restored with it, so the next
  // run behaves as that one did — where the record says so. 24 of the 42 stored
  // runs of this instrument were made before the tick itself was written down:
  // 11 of them drew their seed, 11 kept the number in the box, and 2 hold no
  // parameters at all and leave the tick where the user put it. Writing `false`
  // for all 24 turned the user's tick off by itself, invisible while the
  // session read came afterwards and put it back, and the last word now that it
  // does not.
  if (typeof p.random_seed === 'boolean') randomSeed.value = p.random_seed
  else if (Number.isFinite(boxSeed) && Number.isFinite(madeSeed) && madeSeed !== boxSeed) {
    randomSeed.value = true
  } else if (boxSeed === -1) {
    // The box held the sentinel and the run kept no result to compare it with:
    // the -1 is by itself what the tick was set to. No stored run is in this
    // state, both that hold the -1 hold their drawn seed as well.
    randomSeed.value = true
  } else if (knownSeed !== null) randomSeed.value = false
  // The automatic writes the seed into the field and compares the next press
  // with this picture.
  const readInputs = readWhole ? inputsKey() : null
  seedAutomatic.laidBack(readInputs, knownSeed)

  const recorded = shotsOf(obj)
  stepShots.value = recorded.shots
  finalShot.value = recorded.final
  selectedIndex.value = 0

  // It stands on the surface AS a run: with its card, so it can be stepped
  // away from and come back, exactly like one just made.
  const id = obj.run_id
  currentRunId.value = id
  runFrames.value.set(id, {
    shots: stepShots.value,
    final: finalShot.value,
    total: totalSteps.value,
    seed: actualSeed.value,
    order: schedulerOrder.value,
    inputs: readInputs,
    madeSeed: knownSeed,
  })
  if (!runs.value.some(x => x.id === id)) {
    // `cardFor`, the same card the sitting builds for a stored run, and for the
    // same reason: it reads the record. Built here from the surface it named
    // the visitor's net, step count, CFG and prompt over a run that had none of
    // them. 22 of the 42 stored runs carry no parameters at the top level of
    // their record, and 18 of those were made before the second net existed, so
    // the card offered SDXL for a run that could only have been SD 3.5.
    const card = cardFor(obj)
    if (card) runs.value.push(card)
  }
}

/*
 * Session persistence — read HERE, in the setup body, and deliberately not in
 * onMounted, and deliberately BEFORE the restore watcher below.
 *
 * That watcher is registered `immediate: true`, so a run arriving with the
 * navigation is written into the fields while setup runs, before any onMounted
 * hook fires. From an onMounted these lines therefore landed on top of it, and
 * a restored run showed the previous run's prompt, negative prompt, steps, CFG,
 * seed, random-variation tick and net — every field the session keeps.
 *
 * Standing before it, they are the ground the record is laid on: where the
 * record speaks it overwrites them, where it is silent the page keeps where the
 * user left it.
 */
{
  const sa = sessionStorage
  const s = (k: string) => sa.getItem(k)
  // The net first, for the reason applyInstrumentRun sets it first: switching
  // it moves CFG to that net's default, and a CFG read before the net is open
  // to being moved by the switch. A session standing at SDXL with CFG on 4.5
  // came back reading 7.0 on the first return, because at the moment of the
  // switch the number matched the net being left; the persistence watcher then
  // wrote the 7.0 back, and from the second return on there was nothing left to
  // move. The order carries this only together with the
  // `sync` on that watcher: under a pre-flush the callback runs after both
  // lines whichever way round they stand.
  const bb = s('lat_lab_da_backbone')
  if (bb && BACKBONES.some(b => b.value === bb)) backbone.value = bb as Backbone
  if (s('lat_lab_da_prompt')) promptText.value = s('lat_lab_da_prompt')!
  if (s('lat_lab_da_negative')) negativePrompt.value = s('lat_lab_da_negative')!
  if (s('lat_lab_da_steps')) steps.value = parseFloat(s('lat_lab_da_steps')!) || 25
  if (s('lat_lab_da_cfg')) cfgScale.value = parseFloat(s('lat_lab_da_cfg')!) || 4.5
  // parseInt, not `|| 123456789`: a seed of 0 is a seed.
  const keptSeed = parseInt(s('lat_lab_da_seed') || '')
  if (Number.isInteger(keptSeed) && keptSeed >= 0) seed.value = keptSeed
  if (s('lat_lab_da_random_seed')) randomSeed.value = s('lat_lab_da_random_seed') === 'true'
}

/**
 * The way back in from the platform's storage. The gallery sets the restore
 * data and then navigates here, so this has to look once on arrival as well as
 * on every later change — hence `immediate`.
 *
 * Only runs this instrument made are taken: another instrument's object would
 * name parts this surface cannot read.
 */
watch(() => favoritesStore.pendingRestoreData, (restoreData) => {
  const instrument = restoreData?.instrument
  if (!instrument || instrument.tool !== 'denoising_archaeology') return
  applyInstrumentRun(instrument)
  favoritesStore.setRestoreData(null)
}, { immediate: true })

/** The × on a card takes exactly that run off the surface. */
function removeRun(index: number) {
  const gone = runs.value[index]
  // Through the strip's own memory, so the card stays gone after a reload.
  dropRun(index)
  if (!gone) return
  runFrames.value.delete(gone.id)
  // Its card was the only way back to it. Leaving the sequence standing would
  // leave a run on the surface that nothing can restore and nothing names.
  if (currentRunId.value === gone.id) {
    stepShots.value = []
    finalShot.value = ''
    totalSteps.value = steps.value
    actualSeed.value = 0
    schedulerOrder.value = 1
    selectedIndex.value = 0
    currentRunId.value = null
  }
}

// ============================================================================
// SESSION
// ============================================================================

// `immediate`: the restore watcher above writes a run's fields during setup,
// before these exist, and they would otherwise keep the session's old values
// until the next change, the seed the automatic wrote into the field among them.
watch(promptText, v => sessionStorage.setItem('lat_lab_da_prompt', v), { immediate: true })
watch([negativePrompt, steps, cfgScale, seed, randomSeed, backbone], () => {
  sessionStorage.setItem('lat_lab_da_negative', negativePrompt.value)
  sessionStorage.setItem('lat_lab_da_steps', String(steps.value))
  sessionStorage.setItem('lat_lab_da_cfg', String(cfgScale.value))
  sessionStorage.setItem('lat_lab_da_seed', String(seed.value))
  sessionStorage.setItem('lat_lab_da_random_seed', String(randomSeed.value))
  sessionStorage.setItem('lat_lab_da_backbone', backbone.value)
}, { immediate: true })

// ============================================================================
// PAGE CONTEXT
// ============================================================================

const trashyFocusHint = computed<FocusHint>(() => {
  if (isGenerating.value || frames.value.length > 0) {
    return { x: 95, y: 85, anchor: 'bottom-right' }
  }
  return { x: 8, y: 95, anchor: 'bottom-left' }
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'denoising_archaeology',
  pageContent: { inputText: promptText.value },
  focusHint: trashyFocusHint.value,
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onUnmounted(() => {
  pageContextStore.clearContext()
})
</script>

<style scoped>
/* ============================================================================
   The page: two surfaces, result surface. No vertical page scroll — each surface
   carries its own overflow, so a long sequence never pushes the result surface
   off the screen.
   ============================================================================ */

.da {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  /* Through its own route this instrument is the whole page and has to keep the
     favourites strip's room free itself; in the Latent Lab's frame the page
     already does (assets/shell.css). */
  padding-bottom: calc(var(--footer-collapsed-height, 36px) + 1px);
  box-sizing: border-box;
  background: var(--bg-base);
  color: #e2e8f0;
}

.shell-page .da {
  padding-bottom: 0;
}

.da > .da-drawer-btn { align-self: flex-start; margin: 8px 0 2px 4px; }
/* The same, for the trigger, on the route where there is no bar to teleport
   into. Inside the frame both stand in the bar and this never applies. */
.da > :deep(.fl-run) { align-self: flex-start; margin: 8px 0 2px 4px; }

.da-main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 12px 16px;
}

.da-stage {
  width: 100%;
  margin: 0;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* --------------------------------------------------------------------------
   The two surfaces. The measure is Encoder Fusion's, and it comes from what
   the things need: a prompt is a paragraph and wants 45-75 characters to the
   line, the sequence wants room for eight or nine frames abreast.
   -------------------------------------------------------------------------- */
.da-work {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 2.0467fr;
  /* Without a floor on the row, a tall surface makes the row taller than the
     grid and the page clips it — see views/latent_lab/coreference_test.vue. */
  grid-template-rows: minmax(0, 1fr);
  column-gap: 1.509434%;
}

.da-text,
.da-view {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.da-text {
  gap: 12px;
  /* The same fallback the other surface has: when the result surface is pulled
     far open, the open settings drawer and the error line stay reachable
     instead of being clipped by the page's own `overflow: hidden`. */
  overflow-y: auto;
}

/* The floor lives on the holder, not on the component - see the template.

   A HEIGHT, not a share of what is left. With `flex: 1` the field took every
   pixel the settings below it did not want — around 550 px on a 1080p window
   for a prompt of one or two lines. Six or seven lines is what a prompt is; what the
   column does not use stays empty under the settings, which is what an empty
   column looks like. */
.da-field-slot {
  flex: 0 0 auto;
  height: 168px;
  display: flex;
  flex-direction: column;
}

.da-field {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* The field's own box has a fixed height of its own; this lets it follow the
   surface (same rule as views/surrealizer.vue). */
.da-field :deep(.bubble-textarea) {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.da-err {
  flex: 0 0 auto;
  margin: 0;
  font-size: var(--flow-fs-sub);
  line-height: 1.45;
  color: #f87171;
}

.da-view {
  gap: 10px;
  /* The fallback that keeps frame and axis reachable when the result surface
     is pulled far open. */
  overflow-y: auto;
}

/* The chosen frame gets the whole surface bar the axis, and its width follows
   its height — a step image is square. The rows of thumbnails that stood here
   are gone: they added nothing, took room, and took away the chance to
   imagine the denoising of the next step oneself. The step in view is what is
   looked at; what the next step will be is the question the instrument asks,
   and a row of answers standing next to it takes the question away. */
/* Die Flaeche misst sich selbst und traegt das Quadrat: .instr-frame /
   .instr-stack / .instr-square in assets/instrument-surface.css, wo auch steht,
   warum es ohne die Selbstmessung in beide Richtungen schiefging. Hier steht
   nur, was DIESE Flaeche davon abweichend braucht. */
.da-frame {
  /* Unter 200 px ist der Schritt nicht mehr zu lesen; dann darf die Spalte
     scrollen statt das Bild weiter zu schrumpfen. */
  min-height: 200px;
}

/* Im Stapel steht nur noch das Bild, also nimmt das Quadrat die volle Hoehe der
   Flaeche: `--instr-reserve` bleibt bei 0 (assets/instrument-surface.css). Bis
   zum 2026-08-31 standen hier 91 px fuer die Achse, und die gingen dem Quadrat
   vorher ab. */
.da-stack {
  gap: 10px;
}

/* Der Kasten IST das Bild: die Unterschrift sitzt an seinem unteren Rand,
   wo immer der liegt. */
.da-shot {
  position: relative;
}

.da-frame-img {
  /* Inline gesetzt haengt unter dem Bild die Unterlaenge der Zeile: gemessen
     7 px, um die der Stapel dann ueber die Flaeche hinausstand. */
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 8px;
  cursor: zoom-in;
}

/* The empty frame IS the shot's box now: the stack around it carries the size,
   so the axis under it stands on the frame's own edges. */
.da-frame-empty {
  width: 100%;
  height: 100%;
  border-radius: 8px;
  background: var(--surface-2);
}

/* Before the first run: the axis stands and can be read, but not moved - the
   same 0.35 the older surface dimmed its idle state with. */
.da-stack-idle {
  opacity: 0.35;
  pointer-events: none;
}

.da-frame-cap {
  position: absolute;
  bottom: 6px;
  left: 50%;
  transform: translateX(-50%);
  font-size: var(--flow-fs-sub);
  color: rgba(255, 255, 255, 0.75);
  background: rgb(var(--surface-1-rgb) / 0.75);
  padding: 2px 9px;
  border-radius: 11px;
  white-space: nowrap;
  pointer-events: none;
}

/* Die Achse steht in der linken Spalte, an der Stelle, an der bis zum
   2026-08-31 der Shift-Regler stand. */
.da-axis-slot {
  flex: 0 0 auto;
}

.da-axis {
  flex: 0 0 auto;
}

/* Der Erklaerkasten steht am FUSS der vorbereitenden Spalte - das `margin-top:
   auto` aus assets/flow-stage.css, das ihn dorthin stellt, gilt hier wie
   ueberall (docs/ELEMENT_STRUCTURE_REGISTRY.md, `Erklaerkasten am
   Spaltenfuss`). Was diese Flaeche dazutut, ist nur die Hoehe: `flex: 0 1 auto`
   gibt ihm die Hoehe seines Textes statt der ganzen Restspalte, und wo die
   Spalte ihn nicht traegt, schrumpft er und scrollt in sich (`min-height: 0`
   plus `overflow-y`), statt mitten im Wort am Spaltenende abgeschnitten zu
   stehen; gemessen am 2026-08-31 bei 1512 x 900 fehlten ihm dort rund 80 px. */
.da-text :deep(.lab-note) {
  flex: 0 1 auto;
  min-height: 0;
  overflow-y: auto;
}

/* The axis gets NO padding of its own. MarkedSlider positions its words
   against the padding box and the handle against the content box; they only
   coincide while the two boxes are the same. A 4 % padding here put the
   „Composition" notch about twenty pixels from the handle position it names. */

/* --------------------------------------------------------------------------
   The settings that are rarely touched — the platform's own drawer
   (docs/ELEMENT_STRUCTURE_REGISTRY.md, details.advanced-settings). Its shape
   stands in assets/flow-stage.css since 2026-09-05; what is here are this
   surface's own metrics, and every property the shared block sets is said again
   so that the two do not mix.
   -------------------------------------------------------------------------- */
/* The bar of the enlarged frame: its name at the left, the way to take it home
   at the right — the arrangement MediaFullscreen's own comment describes. */
.da-fs-label {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}

.da-fs-download {
  flex: 0 0 auto;
  padding: 5px 12px;
  border: 1px solid var(--surface-4);
  border-radius: 6px;
  background: rgb(var(--surface-1-rgb) / 0.6);
  color: #e2e8f0;
  font-size: var(--flow-fs-sub);
  text-decoration: none;
}

.da-fs-download:hover {
  border-color: rgba(255, 255, 255, 0.35);
}

/* Which net, and how its path is walked. Above the settings drawer and open,
   because it is not a setting of the run but what the run IS. */
.da-engine {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding-top: 10px;
  border-top: 1px solid var(--surface-3);
}

/* Die Achse traegt den Namen der Sache und steht deshalb in Weiss, waehrend die
   Beschriftung des Netzes darueber leise bleibt. */
.lab-pick-label.da-live { color: rgba(255, 255, 255, 0.92); }

.da-engine-title {
  font-size: 10.5px;
  letter-spacing: 0.11em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.35);
}


.advanced-settings {
  flex: 0 0 auto;
  margin-top: 0;
  font-size: var(--flow-fs-sub);
  color: rgba(255, 255, 255, 0.5);
}

.advanced-settings summary {
  cursor: pointer;
  padding: 4px 0;
  color: rgba(255, 255, 255, 0.5);
  font-size: var(--flow-fs-sub);
}

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 10px;
  margin-top: 0;
  padding: 6px 0 2px;
}

.settings-grid label {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: var(--flow-fs-hint);
  color: rgba(255, 255, 255, 0.4);
}

.setting-input {
  background: rgb(var(--surface-1-rgb) / 0.6);
  border: 1px solid var(--surface-4);
  border-radius: 5px;
  padding: 4px 7px;
  color: #e2e8f0;
  font-size: var(--flow-fs-sub);
  width: 100%;
}

/* Every property the shared klappe sets on this class is said again here, so
   that what this field measures does not depend on which rule happened to
   outrank which. `width` was the one left unsaid: it read 90 px only because
   `.setting-input` above (scoped, and so the heavier selector) set `100%` and
   this cap held it, while assets/flow-stage.css's `.setting-small` asks for
   72 px. */
.setting-small {
  width: 100%;
  max-width: 90px;
}

/* Under 640 px the columns stand one under the other and the page scrolls as a
   column again. Until 2026-08-21 this breakpoint followed the band's own
   unstacking; the band is gone, the width at which two columns stop being two
   columns is not. */
@media (max-width: 640px) {
  .da {
    height: auto;
    overflow: visible;
  }

  .da-main {
    flex: 0 0 auto;
  }

  .da-work {
    grid-template-columns: 1fr;
    row-gap: 16px;
  }

  .da-text,
  .da-view {
    overflow: visible;
  }
}
</style>
