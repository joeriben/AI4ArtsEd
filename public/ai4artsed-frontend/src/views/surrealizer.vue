<!--
  Encoder Fusion — the first instrument laid out under the band.

  The band is the run: what is prepared, the run itself, what came out. It is
  the flow's own band (views/x2x_flow.vue) down to its names and its symbols —
  media glyphs and the model in the first node, nothing but the triangle in the
  middle one, the produced image filling the last. The boxes take the names
  from Flow, and the symbols with them.

  Under it, TWO surfaces, not three columns: the text, and the setting. The
  drawing of the conditioning table, the three factors under it and the token
  table are one thing being handled, so they share one surface: columns are
  pulled together where they form ONE functional unit. Each takes the
  surface's full width, and what is subordinate is a line rather than a card.

  Since 2026-09-15 the setting is the three factors on the conditioning table
  SD 3.5 reads: a on
  the CLIP block, b for T5's rows 0..76 added into that block cell by cell,
  c on the T5 block; since 2026-09-16 and 2026-09-17 two switches beside
  them, the layout of the T5 block (line of c) and the pooled vector (line of
  a). One prompt goes to all three encoders. The drawing over the sliders
  shows the table under the three factors and the two switches; the table
  under them shows which piece of the prompt stands in which row at CLIP and
  at T5.

  The widths come from what the things need, not from the band's arithmetic:
  a prompt is a paragraph and wants 45-75 characters to the line; the drawing
  and the three axes stand at the column's width. That is why the first surface
  is one part and the second two, and why the stage has no width cap on the
  WORK surfaces — the flow's --flow-map-w held this page at 1000px on a 1920px
  screen and left the text 111px. The band above them keeps it: its size is
  the flow's template.

  What used to be here and is gone:
   - The switch „Prompt für T5 erweitern" and the machine-written expansion
     behind it. T5 expands destructively. What makes a text
     longer comes from the perspectives in the field now — visible, checked like
     any other prompt — and a warning under a very short text points at them.
   - The α slider's staging: the violet→blue→pink gradient, the 48×48 handle and
     the five scale words. The field map shows what the setting does; the
     control does not have to act it out.
   - The result column and its MediaOutputBox. The image stands in the band's
     third node and the runs lie in the surface below, where several can be put
     side by side — which is what this instrument is for. Favouriting and image
     analysis lost their control with it; they have no home on this surface yet.
   - The dozen explanation blocks. They belong to Help, which knows them.
   - The alpha axis with its five marks, the field map under it and the switch
     „Same prompt" / „Adapted prompts" (2026-09-15). One alpha stood for a
     line through the space of the three factors (lib/fusionWeights: a 1 and
     b 1 at 0, one of them fading to 0 at the anchors ±1, past them a + b = 1;
     c 1, with T5's rows 77.. alone under the block), and the adapted
     prompts sent a
     different text to each encoder. lib/fusionWeights keeps the arithmetic
     for the stored runs, whose cards still carry their alpha and their
     position.
-->
<template>
  <div class="ef">
    <!-- The trigger, in the middle of the frame's bar, with the per-cent of the
         run beside it. `defer` is not optional: a Teleport resolves its target
         against the live document, and on the app's FIRST render the tree is
         still detached, so `.shell-bar-run` cannot be found. -->
    <!-- No count here: a run returns ONE picture, so how far it has come is all
         there is to say. -->
    <ShellRun
      :ready="canRun"
      :running="isExecuting"
      :title="isExecuting ? t('surrealizer.executingButton') : t('surrealizer.executeButton')"
      :percent="generationProgress"
      @run="executeWorkflow"
    />
    <!-- The switch that opens and closes the result surface, in the drawing
         Canvas gives it. Where it STANDS depends on the door: inside the Latent
         Lab it belongs in that frame's bar, next to the switch for the left
         column (top left, next to the left panel switch), so it
         is teleported there. On this instrument's own route there is no frame
         and no bar, and it stands at the top left of the page itself. One
         button either way. -->
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
        class="shell-btn ef-drawer-btn"
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

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <!-- LEFT: everything a run is prepared with. RIGHT: what came out of
               it. That is the Latent Lab's proportion and its meaning, not this
               page's invention — `Seitengeruest eines Messinstruments` in
               docs/ELEMENT_STRUCTURE_REGISTRY.md, carried by Bias Archaeology,
               the Coreference Test, Cultural (Un)Known and Denoising
               Archaeology.
               The diagram goes together with its slider into the left column,
               the result picture into the right.

               ONE surface for the setting, not two columns: columns are pulled
               together where they form one functional unit. The drawing and
               the axes take the full
               width because they are the setting; the token table stands under
               them on the same width and takes the height that is left; what
               is subordinate is a line, not a card.

               The price is measured and it is the table's: with the field, the
               drawing (168 px) and three compact axes (3 x 67 px) the column of
               the reference device (603 px at 1210 x 834) is over-full before
               the table, so the column scrolls by ~300 px and the table keeps
               its floor (see .ef-tokens). Only taking something out of this
               column would buy that back, and everything in it prepares the
               run. -->
          <section class="ef-set col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <!-- The combination Model Bias sets (views/compare/model_comparison.vue):
                 the ready-made prompts ABOVE the field they go into, and the
                 field itself with its four actions. The entry is the platform's
                 own example, the one Denoising Archaeology and Model Bias offer.
                 It is SHORT on purpose - the line under the field then says what
                 a short text costs here and points at the perspective in the
                 field, which is the step this instrument wants taken next. -->
            <PromptExamples
              :items="promptExamples"
              :current="inputText"
              :disabled="isExecuting"
              @pick="applyExample"
            />
            <div class="ef-field-slot">
            <MediaInputBox
              class="ef-field"
              chrome="bare"
              :placeholder="t('mediaInput.freePromptPlaceholder')"
              v-model:value="inputText"
              input-type="text"
              resize-type="none"
              :is-filled="!!inputText"
              :is-loading="readingPicture"
              :disabled="readingPicture"
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

            <!-- What came out. It filled the band's third node until 2026-08-21
                 and had no other place on this surface; with the band gone it
                 gets one of its own, and the room the band took is most of what
                 it stands in. NOTHING stands under the picture: the medium
                 glyph and the model name are gone, because which SD3.5 the
                 backend picks is not a setting of this surface, and the line
                 only took the picture's height.

                 The earlier objection to a result surface here was that it
                 would show the same image twice and stand empty until the first
                 run. The first half is gone with the band. The second is the
                 shape every result surface of the platform has, and the empty
                 frame says where the image will be. -->

            <!-- The table SD 3.5 conditions on, as it stands under the three
                 factors below: components/ConditioningTable.vue. Rows 0..76
                 are the CLIP block (columns 0..2047 CLIP-L and CLIP-G, the
                 rest zero), under it the T5 block, rows 0..511 or, as the
                 fields in the line of c have it, rows 77..511 alone; over
                 the CLIP block the bar of the pooled vector, filled or, as
                 the fields in the line of a have it, empty for zeros.
                 Under the head the named points of the space as fields
                 (PRESETS): a click puts the three factors, the layout and the
                 pooled vector there, and the field whose point all of them
                 stand on is lit; Standard, a 1, b 0, c 1 on rows 0..511 with
                 the pooled vector, is the setting SD 3.5 runs on its own. -->
            <div class="ef-set-head ef-table-head">
              <span>{{ t('surrealizer.tableLabel') }}</span>
            </div>
            <ChipSelect
              class="ef-presets"
              :model-value="activePreset"
              :options="presetOptions"
              :columns="2"
              @update:model-value="applyPreset"
            />
            <ConditioningTable class="ef-table" :a="factorA" :b="factorB" :c="factorC" :t5-rows="t5Rows" :pooled="pooled" />

            <!-- The three factors. a and b run on the axis the alpha of this
                 page ran on (lib/fusionWeights: linear inside ±1, logarithmic
                 out to ±75, whole numbers hold the handle); c runs 0..1 in
                 steps of 0.05. Over each axis its line: the letter of the
                 drawing, the name of the block, in the lines of a and c the
                 two fields of a switch, the number. The axis is
                 components/MarkedSlider.vue, compact, so that three of them
                 fit the column. -->
            <div class="ef-factor">
              <div class="ef-factor-line">
                <b>a</b><span>{{ t('surrealizer.factorA') }}</span>
                <!-- The pooled vector, the fifth setting; the bar over the
                     drawing follows it. As CLIP-L and CLIP-G compute it, or
                     zeros in its place, which ComfyUI itself puts there when
                     no CLIP encoder runs. Two fields, as in the line of c. -->
                <ChipSelect
                  class="ef-switch"
                  :model-value="pooled"
                  :options="pooledOptions"
                  :columns="2"
                  @update:model-value="setPooled"
                />
                <output class="ef-factor-val" aria-live="off">{{ fmt(factorA) }}</output>
              </div>
              <MarkedSlider
                class="ef-track"
                compact
                v-model="posA"
                :min="ALPHA_POSITIONS.min"
                :max="ALPHA_POSITIONS.max"
                :step="ALPHA_POSITIONS.step"
                :marks="factorMarks"
                :aria-label="'a · ' + t('surrealizer.factorA')"
                :value-text="'a = ' + fmt(factorA)"
              />
            </div>
            <div class="ef-factor">
              <div class="ef-factor-line">
                <b>b</b><span>{{ t('surrealizer.factorB') }}</span>
                <output class="ef-factor-val" aria-live="off">{{ fmt(factorB) }}</output>
              </div>
              <MarkedSlider
                class="ef-track"
                compact
                v-model="posB"
                :min="ALPHA_POSITIONS.min"
                :max="ALPHA_POSITIONS.max"
                :step="ALPHA_POSITIONS.step"
                :marks="factorMarks"
                :aria-label="'b · ' + t('surrealizer.factorB')"
                :value-text="'b = ' + fmt(factorB)"
              />
            </div>
            <div class="ef-factor">
              <div class="ef-factor-line">
                <b>c</b><span>{{ t('surrealizer.factorC') }}</span>
                <!-- Which rows the T5 block holds, the fourth setting; the
                     drawing follows it. Rows 0..511, or rows 77..511 alone,
                     the layout of the Surrealizer until 2026-09-15. Two
                     fields (components/ChipSelect.vue), small enough for
                     this line, so the column keeps its height. -->
                <ChipSelect
                  class="ef-switch"
                  :model-value="t5Rows"
                  :options="rowsOptions"
                  :columns="2"
                  @update:model-value="setRows"
                />
                <output class="ef-factor-val" aria-live="off">{{ fmt(factorC) }}</output>
              </div>
              <MarkedSlider
                class="ef-track"
                compact
                v-model="factorC"
                :min="C_RANGE.min"
                :max="C_RANGE.max"
                :step="C_RANGE.step"
                :marks="C_MARKS"
                :aria-label="'c · ' + t('surrealizer.factorC')"
                :value-text="'c = ' + fmt(factorC)"
              />
            </div>

            <!-- Which piece of the prompt stands in which row, at CLIP and at
                 T5, from the tokenizers the graph cuts the prompt with
                 (/api/text/encoder-rows; comfyui_nodes/ai4artsed_comfyui/
                 _tokenizers.py). The control marks stand as they are written.
                 T5's rows 0..76 are the cells b adds into the CLIP block, and
                 at b ≠ 0 they are tinted — the padding rows among them too,
                 which is why T5's padding is split at row 77. The table takes
                 the room left in the column and scrolls in itself. -->
            <div class="ef-tokens">
              <table v-if="tokenRows" class="ef-token-table">
                <thead>
                  <tr>
                    <th>{{ t('surrealizer.tokenRow') }}</th>
                    <th>CLIP</th>
                    <th>T5</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="line in tokenLines"
                    :key="line.n"
                    :class="{ 'ef-paired': line.n < CLIP_ROWS && factorB !== 0 }"
                  >
                    <td class="ef-tok-n">{{ line.n }}</td>
                    <td><TokenChip v-if="line.clip" :text="tokenText(line.clip)" :kind="tokenKind(line.clip)" :part="line.clip.part" /></td>
                    <td><TokenChip v-if="line.t5" :text="tokenText(line.t5)" :kind="tokenKind(line.t5)" :part="line.t5.part" /></td>
                  </tr>
                  <tr v-if="clipPadRange">
                    <td class="ef-tok-n">{{ clipPadRange }}</td>
                    <td><TokenChip :text="t('surrealizer.tokenPadding')" kind="pad" /></td>
                    <td></td>
                  </tr>
                  <tr
                    v-for="pad in t5PadRanges"
                    :key="pad.label"
                    :class="{ 'ef-paired': pad.paired && factorB !== 0 }"
                  >
                    <td class="ef-tok-n">{{ pad.label }}</td>
                    <td></td>
                    <td><TokenChip :text="t('surrealizer.tokenPadding')" kind="pad" /></td>
                  </tr>
                </tbody>
              </table>
              <p v-if="tokenRows && tokenRows.clip.cut" class="ef-tokens-note">
                {{ t('surrealizer.tokenCut', { n: tokenRows.clip.cut }, tokenRows.clip.cut) }}
              </p>
              <p v-else-if="tokenError" class="ef-tokens-note">{{ tokenError }}</p>
            </div>

            <div class="ef-foot">
              <details class="advanced-settings">
                <summary>{{ t('surrealizer.advancedLabel') }}</summary>
                <div class="settings-grid">
                  <label>
                    {{ t('surrealizer.negativeLabel') }}
                    <input v-model="negativePrompt" type="text" class="setting-input" />
                  </label>
                  <label>
                    {{ t('surrealizer.cfgLabel') }}
                    <input v-model.number="cfgScale" type="number" min="1" max="15" step="0.1" class="setting-input setting-small" />
                  </label>
                  <SeedControl v-model:seed="seed" v-model:random="randomSeed" />
                </div>
              </details>
            </div>
          </section>

          <!-- What came out, and the record of the run under it. It filled the
               band's third node until 2026-08-21 and had no other place on this
               surface; with the band gone it gets one of its own. Nothing is
               written under the picture: the medium glyph and „SD 3.5“ are
               gone since 2026-08-23, and the frame took the room they held.

               A line of run facts (duration / steps / α / strategy / seed)
               stood under the picture until 2026-08-23 and is gone: every one of
               those numbers is already on the box the run leaves in the series,
               and under the picture they only took its height. The whole info
               line was superfluous and came out, which gives the picture more
               room. What stays here is the error, which has nowhere
               else to be. -->
          <section class="ef-result">
            <div class="ef-out">
              <div class="ef-out-frame instr-frame">
                <div class="instr-stack">
                  <img
                    v-if="primaryOutput?.url"
                    class="ef-out-img instr-square"
                    :src="primaryOutput.url"
                    :alt="t('mediaOutput.generatedImage')"
                    role="button"
                    tabindex="0"
                    @click="showImageFullscreen(primaryOutput.url)"
                    @keydown.enter.prevent="showImageFullscreen(primaryOutput.url)"
                    @keydown.space.prevent="showImageFullscreen(primaryOutput.url)"
                  />
                  <div v-else class="ef-out-empty instr-square"></div>
                </div>
              </div>
            </div>

            <p v-if="generationErrorMessage" ref="errLine" class="ef-err">{{ generationErrorMessage }}</p>
          </section>
        </div>
      </div>
    </div>

    <!-- The runs, side by side. What this instrument teaches is not in one
         image; it becomes perceptible only through arrangement, in series
         and contrasts. -->
    <OutputDrawer
      ref="drawer"
      :items="runs"
      :is-collapsed="drawerCollapsed"
      :title="t('latentLab.shared.runsTitle')"
      :empty-text="t('latentLab.shared.runsEmpty')"
      :default-height="340"
      :box-width="240"
      :box-height="260"
      source-view="surrealizer"
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

    <!-- The platform's one fullscreen layer; see components/MediaFullscreen.vue.
         Only for a picture the strip cannot show: the run on the surface opens
         through its card in the strip, back and all (`showImageFullscreen`). -->
    <MediaFullscreen :src="fullscreenImage" @close="fullscreenImage = null" />
  </div>
</template>

<script setup lang="ts">
import ColumnFold from '@/components/ColumnFold.vue'
import { ref, computed, inject, watch, nextTick, onUnmounted } from 'vue'
import MediaFullscreen from '@/components/MediaFullscreen.vue'
import { useI18n } from 'vue-i18n'
import { usePictureTemplate } from '@/composables/usePictureTemplate'
import axios from 'axios'
import { postDirectRun } from '@/services/directRun'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import { usePromptPresets } from '@/lib/promptPresets'
import SeedControl from '@/components/SeedControl.vue'
import { useSeedAutomatic, STANDARD_SEED } from '@/composables/useSeedAutomatic'
import ConditioningTable from '@/components/ConditioningTable.vue'
import ChipSelect, { type ChipOption } from '@/components/ChipSelect.vue'
import TokenChip from '@/components/TokenChip.vue'
import MarkedSlider from '@/components/MarkedSlider.vue'
import ShellRun from '@/components/ShellRun.vue'
import OutputDrawer, { type DrawerItem } from '@/components/canvas/OutputDrawer.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import {
  ALPHA_POSITIONS,
  alphaToPos,
  posToAlpha,
  parseFusionStrategy,
} from '@/lib/fusionWeights'
import type { AlphaScale } from '@/lib/fusionWeights'
import {
  formatFactor,
  fusionSettingLabel,
  minus,
  recordedFactors,
  recordedNumber,
  recordedPooled,
  recordedRows,
  type Pooled,
  type T5Rows,
} from '@/lib/fusionSetting'
import { blockedReason, safetyBlockKey } from '@/composables/useGenerationStream'
import { generationErrorFor as labErrorText, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useLatentLabRecorder, type InstrumentRun } from '@/composables/useLatentLabRecorder'
import { useInstrumentRuns } from '@/composables/useInstrumentRuns'
import { useDeviceId } from '@/composables/useDeviceId'
import { usePageContextStore } from '@/stores/pageContext'
import { useFavoritesStore } from '@/stores/favorites'
import type { PageContext, FocusHint } from '@/composables/usePageContext'

// ============================================================================
// i18n
// ============================================================================

const { t, locale } = useI18n()

/**
 * The reasons a run did not come back, in the reader's language
 * (composables/useLabRun.ts). This view used to carry its own regexes, which
 * never learned about "device busy" and answered a saturated card with
 * "something went wrong"; then it carried the platform's reading a second time,
 * character for character, which is the parallel structure
 * docs/ELEMENT_STRUCTURE_REGISTRY.md forbids.
 */
function generationErrorFor(raw: string): string {
  return labErrorText(t, raw)
}

// ============================================================================
// Types
// ============================================================================

interface WorkflowOutput {
  type: 'image' | 'text' | 'json' | 'unknown'
  filename: string
  url?: string
  content?: string
}

// ============================================================================
// The band, and the columns under it
// ============================================================================

/**
 * The band's three stations — the flow's own geometry, taken over verbatim
 * (views/x2x_flow.vue: `const W = 1060 / const H = 150 / const RMAP = …`).
 *
 * Left margin, both gaps and the right margin are the same 110, and the nodes
 * take 620 of 1060 — the band is a row of three boxes with air around them, not
 * a header stretched across the page. The preparation node alone is wider (300)
 * because it carries the six glyphs and the model name, and the glyph row is
 * sized in rem and does not ride the stage scale.
 *
 * The surfaces below therefore no longer stand under their nodes; their widths
 * come from what they hold (see the sheet).
 */
// ============================================================================
// STATE
// ============================================================================

// Global clipboard
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const { record: labRecord } = useLatentLabRecorder('surrealizer')

// Favorites support
const favoritesStore = useFavoritesStore()
const deviceId = useDeviceId()
const currentRunId = ref<string | null>(null)

const inputText = ref('')

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
} = usePictureTemplate(inputText)
/*
 * The three factors on the conditioning table SD 3.5 reads, 589 rows by 4096
 * columns: a on the
 * CLIP block (rows 0..76), b for T5's rows 0..76 added into that block cell
 * by cell, c on the T5 block under the CLIP block. Which rows that block
 * holds is the fourth setting, `t5Rows` (the chunk's `t5_rows`): `full`,
 * rows 0..511, the layout SD 3.5 runs on its own, or `tail`, rows 77..511
 * alone, the layout of the Surrealizer until 2026-09-15, under which T5's
 * head exists only inside the CLIP block (measured: the full block pulls the
 * picture toward Standard, and the old pictures need the old layout). The
 * pooled vector,
 * which CLIP-L and CLIP-G compute and the model reads beside the table in
 * the modulation of every block, is the fifth setting, `pooled` (the chunk's
 * `pooled`): `clip`, the vector as computed, or `zero`, zeros in its place,
 * which ComfyUI itself puts there when no CLIP encoder runs.
 * The three factors are free of each other
 * and of the two switches. The setting SD 3.5 runs on its own is a 1, b 0,
 * c 1 on the full block with the pooled vector, named Standard, and the page
 * opens on it.
 * Concatenation is the edge b 0; the alpha of this page ran until
 * 2026-09-15 on the line lib/fusionWeights draws through this space (a 1
 * and b 1 at 0, one of them fading to 0 at the anchors ±1, past them
 * a + b = 1) at c 1 on the tail layout.
 *
 * One prompt goes to all three encoders. The switch „Same prompt" / „Adapted
 * prompts" that stood here until 2026-09-15 is gone with the alpha; the
 * adapted prompts and the five strategies stay in the backend for the stored
 * runs, whose cards still name them (`oldRunName`), and lib/fusionWeights
 * keeps their arithmetic for reading such a run back onto a and b.
 */
/**
 * The named points of the space, as the fields over the drawing: Standard,
 * and beside it the established Surrealization strategies as presets.
 * Standard is the setting SD 3.5 runs
 * on its own. CLIP only and T5 only are the two other points the research
 * schema names: the T5 block zeroed (the ablation 5.3.3 of Esser et al.
 * 2024), the CLIP block zeroed. The three Surrealization points are the old
 * Surrealizer's line a + b = 1 at the strengths every research row ran — α 5,
 * 15 and 35, written as a = 1 − α, b = α — on the tail layout, which makes
 * them the old runs bit for bit (comfyui_nodes/ai4artsed_sd3_conditioning.py:
 * (1 − α, α, 1, tail, clip) is AI4ArtsEdSD3Fusion under legacy at α). Every
 * field
 * carries its layout and its pooled vector; the three named points stand on
 * the full block, and T5 only alone puts zeros in the pooled vector's place,
 * so that no number CLIP computed reaches the model: the
 * CLIP block zero and the vector zero, the two CLIP outputs the training of
 * Esser et al. (2024, B.3) set to zero at random. An old run restored at one
 * of these alphas lands on its field.
 */
const PRESETS = [
  { id: 'standard', a: 1, b: 0, c: 1, rows: 'full', pooled: 'clip', name: () => t('surrealizer.standardButton') },
  { id: 'clip_only', a: 1, b: 0, c: 0, rows: 'full', pooled: 'clip', name: () => t('surrealizer.presetClipOnly') },
  { id: 't5_only', a: 0, b: 0, c: 1, rows: 'full', pooled: 'zero', name: () => t('surrealizer.presetT5Only') },
  { id: 'surrealization_5', a: -4, b: 5, c: 1, rows: 'tail', pooled: 'clip', name: () => t('surrealizer.presetSurrealization', { n: 5 }) },
  { id: 'surrealization_15', a: -14, b: 15, c: 1, rows: 'tail', pooled: 'clip', name: () => t('surrealizer.presetSurrealization', { n: 15 }) },
  { id: 'surrealization_35', a: -34, b: 35, c: 1, rows: 'tail', pooled: 'clip', name: () => t('surrealizer.presetSurrealization', { n: 35 }) },
] as const
const STANDARD = PRESETS[0]
const factorA = ref<number>(STANDARD.a)
const factorB = ref<number>(STANDARD.b)
const factorC = ref<number>(STANDARD.c)
/** Which rows the T5 block holds (lib/fusionSetting, `T5Rows`). */
const t5Rows = ref<T5Rows>(STANDARD.rows)
/** The two fields in the line of c. */
const rowsOptions = computed<ChipOption[]>(() => [
  { value: 'full', label: t('surrealizer.t5RowsFull'), title: t('surrealizer.t5RowsFullTitle') },
  { value: 'tail', label: t('surrealizer.t5RowsTail'), title: t('surrealizer.t5RowsTailTitle') },
])
function setRows(v: string | string[]) {
  t5Rows.value = recordedRows(v)
}
/** The pooled vector the model reads beside the table (lib/fusionSetting, `Pooled`). */
const pooled = ref<Pooled>(STANDARD.pooled)
/** The two fields in the line of a. */
const pooledOptions = computed<ChipOption[]>(() => [
  { value: 'clip', label: t('surrealizer.pooledClip'), title: t('surrealizer.pooledClipTitle') },
  { value: 'zero', label: t('surrealizer.pooledZero'), title: t('surrealizer.pooledZeroTitle') },
])
function setPooled(v: string | string[]) {
  pooled.value = recordedPooled(v)
}
/** The field whose point the three factors, the layout and the pooled vector stand on; none while they stand elsewhere. */
const activePreset = computed(() =>
  PRESETS.find(p => p.a === factorA.value && p.b === factorB.value && p.c === factorC.value
    && p.rows === t5Rows.value && p.pooled === pooled.value)?.id ?? '')
const presetOptions = computed<ChipOption[]>(() =>
  PRESETS.map(p => ({ value: p.id, label: p.name(), title: factorLabel(p.a, p.b, p.c, p.rows, p.pooled) })))
function applyPreset(id: string | string[]) {
  const preset = PRESETS.find(p => p.id === id)
  if (!preset) return
  factorA.value = preset.a
  factorB.value = preset.b
  factorC.value = preset.c
  t5Rows.value = preset.rows
  pooled.value = preset.pooled
}
/** The rows of the CLIP block; the rows of T5 that b pairs with it. */
const CLIP_ROWS = 77
/**
 * a and b stand on the axis the alpha stood on: ±75 (the fp16 cliff), the
 * band −1..1 taking 30 % of the track's each half, logarithmic past it, whole
 * numbers holding the handle (lib/fusionWeights). The step of 0.05 is the
 * slider's; the node takes any value in its range. c stands on a linear
 * 0..1 in the same steps.
 */
const FACTOR_SCALE: AlphaScale = { min: -75, max: 75, step: 0.05, band: { lo: -1, mid: 0, hi: 1 } }
const C_RANGE = Object.freeze({ min: 0, max: 1, step: 0.05 })
/**
 * The name of a stored run made before the three factors, on its card: the
 * position of the switch it ran under, or, for a strategy this page never had
 * a position for (legacy, dual_alpha, the 2025 `original`), the strategy.
 */
function oldRunName(strategy: string): string {
  if (strategy === 'centered_fade') return t('surrealizer.samePrompt')
  if (strategy === 'two_interceptions') return t('surrealizer.adaptedPrompts')
  // A three-factor record whose factors did not come through as numbers has
  // no position to name, and the language file has no name for the strategy.
  if (strategy === 'three_factor') return ''
  return t('surrealizer.fusion_' + strategy)
}
/**
 * The second line on such a card; a run made on the sphere (2026-09-10 to
 * 2026-09-12, see lib/fusionWeights) is named as such.
 */
function runSub(strategy: string, sphere = false): string {
  const parts = [oldRunName(strategy)]
  if (sphere) parts.push(t('surrealizer.path_sphere'))
  return parts.filter(Boolean).join(' · ')
}
/**
 * In the card's bar: the three factors of a run, its layout where that is
 * the old one, and its pooled vector where zeros stand in its place, in the
 * words the favourites panel uses for the same record (lib/fusionSetting).
 */
function factorLabel(a: number, b: number, c: number, rows: T5Rows = 'full', pool: Pooled = 'clip'): string {
  return fusionSettingLabel(a, b, c, rows, pool, locale.value)
}
const isExecuting = ref(false)
const generationErrorMessage = ref('')
/* The setting surface scrolls when the result surface takes its room, and this
   line is its last child — a failed run would say so below the fold, on a
   surface that looks as if nothing had happened. So the line fetches the eye
   when it appears. */
const errLine = ref<HTMLElement | null>(null)
watch(generationErrorMessage, (msg) => {
  if (!msg) return
  nextTick(() => errLine.value?.scrollIntoView({ block: 'nearest' }))
})
const outputs = ref<WorkflowOutput[]>([])
const fullscreenImage = ref<string | null>(null)
const generationProgress = ref(0)
// The seed the run came back with — it goes on the box in the series, which is
// where the facts of a run are read since the line under the picture went.
const lastRunSeed = ref<number | null>(null)
const primaryOutput = ref<WorkflowOutput | null>(null)

// The series. Every finished run stays as a box of its own, so two settings can
// be laid side by side instead of one replacing the other.
/**
 * Whether this instrument stands in the Latent Lab's frame (which has a bar and
 * a left column) or on its own route. The Lab provides it; see the switch in
 * the template.
 */
const inShellFrame = inject('shellFrame', false)

/**
 * The runs of this instrument, as its strip lays them side by side - which is
 * where this instrument is understood at all ("erfahrbar wird das erst durch
 * Arrangement"). They come back after a reload: `cardFor` reads a recorded run
 * back into its card.
 */
const { runs, removeRun } = useInstrumentRuns('surrealizer', cardFor)
const drawer = ref<InstanceType<typeof OutputDrawer> | null>(null)

/** The config this instrument runs. Named once — the card's back says it too. */
const OUTPUT_CONFIG = 'surrealization'

/** The × on a run's card takes that run off the surface. */
/**
 * A recorded run of this instrument, back as its card.
 *
 * The picture belongs to the PIPELINE run this instrument drives; the recorded
 * run names it (`results.run_id`) and holds the settings. Without that name
 * there is nothing to show, and the run stays out of the strip.
 */
function cardFor(run: InstrumentRun): DrawerItem | null {
  const params = (run.parameters || {}) as Record<string, unknown>
  const results = (run.results || {}) as Record<string, unknown>
  const pipelineRunId = typeof results.run_id === 'string' ? results.run_id : ''
  if (!pipelineRunId) return null
  // A run made with the three factors carries them; a run made before them
  // carries its alpha and the position it ran under, and its card keeps both.
  const fa = recordedNumber(params.factor_a)
  const fb = recordedNumber(params.factor_b)
  const fc = recordedNumber(params.factor_c)
  const threeFactors = fa !== null && fb !== null && fc !== null
  const axis = Number(params.axis_alpha ?? params.alpha_factor ?? 0)
  const setting = parseFusionStrategy(String(params.fusion_strategy ?? ''))
  return {
    id: pipelineRunId,
    label: threeFactors ? factorLabel(fa, fb, fc, recordedRows(params.t5_rows), recordedPooled(params.pooled)) : `\u03b1 ${fmt(axis)}`,
    sub: threeFactors ? '' : (setting.base ? runSub(setting.base, setting.sphere) : ''),
    meta: [`seed: ${params.seed ?? ''}`],
    prompt: String(params.prompt ?? ''),
    // The config the run went through, as the record names it. A record made
    // before the recorder wrote the config carries none, and the card's back
    // then names none.
    configId: typeof params.output_config === 'string' ? params.output_config : '',
    createdAt: Date.parse(run.timestamp || '') || Date.now(),
    modelMeta: null,
    runId: pipelineRunId,
    output: { url: `/api/media/image/${pipelineRunId}/0`, media_type: 'image' },
    error: null,
  }
}

const drawerCollapsed = ref(true)

// The perspectives, opened from the rings in the field.
const showPresetOverlay = ref(false)
const isEnriching = ref(false)

// Advanced settings
const negativePrompt = ref('')
const cfgScale = ref(5.5)
const seed = ref(STANDARD_SEED)
const randomSeed = ref(false)

/**
 * Everything a run goes out with except its seed, as one key: what the seed
 * automatic compares the next press with.
 */
function inputsKey(): string {
  return JSON.stringify([inputText.value, factorA.value, factorB.value, factorC.value,
    t5Rows.value, pooled.value, negativePrompt.value, cfgScale.value])
}
const seedAutomatic = useSeedAutomatic(seed, randomSeed, 'lat_lab_ef_seed_yardstick')

/*
 * Session persistence — read HERE, in the setup body, and deliberately not in
 * onMounted.
 *
 * The favourites watcher at the foot of this file is registered with
 * `immediate: true`, so a run that arrives with the navigation is written into
 * the fields while setup runs — before any onMounted hook fires. From an
 * onMounted these lines therefore landed ON TOP of a restored run, and it
 * showed the previous run's prompt, alpha, fusion, negative prompt, cfg and
 * seed under its own picture.
 *
 * Standing before that watcher instead, they are what they should be: the
 * ground the record is laid on. Where the record speaks it overwrites them;
 * where it is silent — an old run that named no fusion, one without a picture
 * seed, and the random-variation tick, which no record carries — the page
 * keeps where the user left it rather than dropping to its factory numbers.
 */
{
  const sa = sessionStorage
  const s = (k: string) => sa.getItem(k)
  if (s('lat_lab_ef_prompt')) inputText.value = s('lat_lab_ef_prompt')!
  // `lat_lab_ef_alpha_c` and `lat_lab_ef_fusion` until 2026-09-15, when the
  // alpha gave way to the three factors: a value left over from before would
  // come back as a different setting, and nothing would say so. A factor that
  // does not parse leaves the Standard setting standing.
  const factor = (k: string) => { const v = parseFloat(s(k) || ''); return Number.isFinite(v) ? v : null }
  const a = factor('lat_lab_ef_a'), b = factor('lat_lab_ef_b'), c = factor('lat_lab_ef_c')
  if (a !== null && b !== null && c !== null) {
    factorA.value = a
    factorB.value = b
    factorC.value = c
    clampFactors()
  }
  // The layout: only its two names count; anything else leaves the full block.
  if (s('lat_lab_ef_t5_rows') === 'tail') t5Rows.value = 'tail'
  // The pooled vector: only its two names count; anything else leaves the vector.
  if (s('lat_lab_ef_pooled') === 'zero') pooled.value = 'zero'
  if (s('lat_lab_ef_negative')) negativePrompt.value = s('lat_lab_ef_negative')!
  if (s('lat_lab_ef_cfg')) cfgScale.value = parseFloat(s('lat_lab_ef_cfg')!) || 5.5
  // parseInt, not `|| 123456789`: a seed of 0 is a seed.
  const keptSeed = parseInt(s('lat_lab_ef_seed') || '')
  if (Number.isInteger(keptSeed) && keptSeed >= 0) seed.value = keptSeed
  if (s('lat_lab_ef_random_seed')) randomSeed.value = s('lat_lab_ef_random_seed') === 'true'
}

// Session persistence — save on change
watch(inputText, v => sessionStorage.setItem('lat_lab_ef_prompt', v))
watch([factorA, factorB, factorC, t5Rows, pooled,
       negativePrompt, cfgScale, seed, randomSeed], () => {
  sessionStorage.setItem('lat_lab_ef_a', String(factorA.value))
  sessionStorage.setItem('lat_lab_ef_b', String(factorB.value))
  sessionStorage.setItem('lat_lab_ef_c', String(factorC.value))
  sessionStorage.setItem('lat_lab_ef_t5_rows', t5Rows.value)
  sessionStorage.setItem('lat_lab_ef_pooled', pooled.value)
  sessionStorage.setItem('lat_lab_ef_negative', negativePrompt.value)
  sessionStorage.setItem('lat_lab_ef_cfg', String(cfgScale.value))
  sessionStorage.setItem('lat_lab_ef_seed', String(seed.value))
  sessionStorage.setItem('lat_lab_ef_random_seed', String(randomSeed.value))
})

// Page Context for Träshy
const pageContextStore = usePageContextStore()

const trashyFocusHint = computed<FocusHint>(() => {
  // During/after execution: bottom-right
  if (isExecuting.value || primaryOutput.value) {
    return { x: 95, y: 85, anchor: 'bottom-right' }
  }
  // Default: bottom-left
  return { x: 2, y: 95, anchor: 'bottom-left' }
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'surrealizer',
  pageContent: {
    inputText: inputText.value
  },
  focusHint: trashyFocusHint.value
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onUnmounted(() => {
  pageContextStore.clearContext()
})

// ============================================================================
// Computed
// ============================================================================

/** The band's middle node is the run; it answers only with something to run. */
const canRun = computed(() => !!inputText.value.trim() && !isExecuting.value)

const canExecute = computed(() => {
  return inputText.value.trim().length > 0 && !isExecuting.value
})

/*
 * A line under the prompt field called a text of under 75 tokens short and
 * pointed at the perspective that lengthens it. It is gone, and with it the
 * word count, the threshold and the name of that perspective, which nothing
 * else on this surface read.
 *
 * What it said was that T5 reads in barely more than CLIP does at that length,
 * and it offered that as a defect to be repaired. The instrument runs on the
 * DIFFERENCE between the two readings of the same words, which is a property
 * of the two encoders rather than of the text's length; and the T5 positions
 * past the 77 core ones hold the reading steady while the core is extrapolated
 * rather than carrying content of their own — the tail switched off at alpha 10
 * and 25 gives a different picture at the same core and the same seed
 * (studies/tail_law_linear_vs_nonlinear_2026-09-10, the two tailoff files).
 * A longer text buys reach along the axis, not a better picture at a given
 * alpha.
 */

// WHERE on the track a factor stands is lib/fusionWeights' answer, as it was
// for the alpha: the band -1..1 takes 30 % of each half, everything past the
// anchor is logarithmic. Without that the band was 1.3 % of the track.
const posA = computed({
  get: () => alphaToPos(factorA.value, FACTOR_SCALE),
  set: (p: number) => { factorA.value = posToAlpha(p, FACTOR_SCALE) },
})
const posB = computed({
  get: () => alphaToPos(factorB.value, FACTOR_SCALE),
  set: (p: number) => { factorB.value = posToAlpha(p, FACTOR_SCALE) },
})

/** A factor in the reader's language, two decimals (lib/fusionSetting). */
function fmt(x: number) {
  return formatFactor(x, locale.value)
}
/** A mark on an axis: the number as it is, in the same language. */
function fmtMark(x: number) {
  return minus(new Intl.NumberFormat(locale.value, { maximumFractionDigits: 2 }).format(x || 0))
}

/**
 * The marks on a and on b: the two ends, 0, and 1, the factor a block stands
 * on unchanged. Numbers alone; the axis is compact.
 */
const factorMarks = computed(() => {
  const span = ALPHA_POSITIONS.max - ALPHA_POSITIONS.min
  const pct = (v: number) => ((alphaToPos(v, FACTOR_SCALE) - ALPHA_POSITIONS.min) / span) * 100
  return [FACTOR_SCALE.min, 0, 1, FACTOR_SCALE.max].map(v => ({ value: fmtMark(v), pct: pct(v) }))
})
/** The marks on c: its two ends. */
const C_MARKS = computed(() => [
  { value: fmtMark(C_RANGE.min), pct: 0 },
  { value: fmtMark(C_RANGE.max), pct: 100 },
])

// The sliders cannot leave their axes, but a stored or restored factor can.
// The watcher catches a restore; the read from storage above calls this
// itself, since it runs before the watcher is registered.
function clampFactors() {
  const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
  const a = clamp(factorA.value, FACTOR_SCALE.min, FACTOR_SCALE.max)
  const b = clamp(factorB.value, FACTOR_SCALE.min, FACTOR_SCALE.max)
  const c = clamp(factorC.value, C_RANGE.min, C_RANGE.max)
  if (a !== factorA.value) factorA.value = a
  if (b !== factorB.value) factorB.value = b
  if (c !== factorC.value) factorC.value = c
}
watch([factorA, factorB, factorC], clampFactors)

// ============================================================================
// The token table
// ============================================================================

/** One piece of the prompt in one row of an encoder's block. */
interface TokenPiece {
  row: number
  kind: 'start' | 'piece' | 'end'
  /** The piece as it reads; empty where the vocabulary has no readable form. */
  s: string
  raw: string
  id: number
  /** The rest of a word the row before began. */
  part: boolean
}
/** One encoder's block: its rows up to the end mark, and what is around them. */
interface EncoderRows {
  rows: TokenPiece[]
  /** Rows that carry a piece; from here to `block` the rows hold padding. */
  filled: number
  /** The rows the block has: 77 at CLIP, 512 at T5. */
  block: number
  /** Pieces past the block. CLIP is held to one block; T5 keeps every row. */
  cut: number
}

const tokenRows = ref<{ clip: EncoderRows; t5: EncoderRows } | null>(null)
const tokenError = ref('')
/** Which prompt was last asked about; an earlier answer arriving later is dropped. */
let tokenAsk = 0
let tokenTimer: ReturnType<typeof setTimeout> | null = null

async function fetchTokenRows(text: string) {
  const ask = ++tokenAsk
  if (!text.trim()) {
    tokenRows.value = null
    tokenError.value = ''
    return
  }
  try {
    const res = await axios.post('/api/text/encoder-rows', { text })
    if (ask !== tokenAsk) return
    // The shape the template reads, checked before it is handed over: a 2xx
    // with another body would throw in the render and leave the page blank.
    if (!Array.isArray(res.data?.clip?.rows) || !Array.isArray(res.data?.t5?.rows)) {
      throw Object.assign(new Error('answer without rows'), { response: res })
    }
    tokenRows.value = res.data
    tokenError.value = ''
  } catch (error: any) {
    if (ask !== tokenAsk) return
    tokenRows.value = null
    // The cause travels with the status. The DevServer writes it into `error`
    // (503 „Nothing answers where ComfyUI should be" when ComfyUI is down);
    // where no answer came at all, the message is the cause.
    const status = error?.response?.status ?? '\u2013'
    const cause = error?.response?.data?.error
    const reason = typeof cause === 'string' && cause ? cause : (error?.message ?? String(error))
    tokenError.value = t('surrealizer.tokensUnavailable', { status, reason })
  }
}
// Debounced: the prompt is typed, and every keystroke would be a request.
watch(inputText, (text) => {
  if (tokenTimer) clearTimeout(tokenTimer)
  tokenTimer = setTimeout(() => fetchTokenRows(text), 250)
}, { immediate: true })
onUnmounted(() => {
  if (tokenTimer) clearTimeout(tokenTimer)
})

/** The lines of the table: row number, the CLIP piece, the T5 piece. */
const tokenLines = computed(() => {
  const rows = tokenRows.value
  if (!rows) return []
  const n = Math.max(rows.clip.rows.length, rows.t5.rows.length)
  return Array.from({ length: n }, (_, i) => ({ n: i, clip: rows.clip.rows[i], t5: rows.t5.rows[i] }))
})
/** CLIP's padding rows, as one range; none when the block is full. */
const clipPadRange = computed(() => {
  const enc = tokenRows.value?.clip
  return enc && enc.filled < enc.block ? `${enc.filled}\u2013${enc.block - 1}` : ''
})
/**
 * T5's padding rows, split where the CLIP block ends: the padding up to row
 * 76 is among the cells b adds into the CLIP block, the rows from 77 on are
 * not.
 */
const t5PadRanges = computed(() => {
  const enc = tokenRows.value?.t5
  if (!enc || enc.filled >= enc.block) return []
  if (enc.filled >= CLIP_ROWS) return [{ label: `${enc.filled}\u2013${enc.block - 1}`, paired: false }]
  return [
    { label: `${enc.filled}\u2013${CLIP_ROWS - 1}`, paired: true },
    { label: `${CLIP_ROWS}\u2013${enc.block - 1}`, paired: false },
  ]
})
/** The chip a piece stands in: a control mark in the control colours. */
function tokenKind(piece: TokenPiece): 'piece' | 'control' {
  return piece.kind === 'piece' ? 'piece' : 'control'
}
function tokenText(piece: TokenPiece): string {
  return piece.s !== '' ? piece.s : piece.raw
}
// ============================================================================
// Methods
// ============================================================================

/**
 * A perspective run over the text in the field. The same call the comparison
 * pages make (`/api/schema/pipeline/stage2`); the answer overwrites the field,
 * so what goes to the encoders is what stands there.
 */
/**
 * What this instrument can be asked, ready to pick. One entry: the platform's
 * own example sentence.
 */
const promptExamples = usePromptPresets()

function applyExample(item: { fill: string[] }) {
  inputText.value = item.fill[0] ?? ''
}

// What the ring in the corner of the field says when the perspective wrote
// nothing: a refusal, a failure with its status, an empty answer, or no
// connection (composables/useLabRun.ts). Until 2026-10-10 all four ended in
// the console here, and the ring spun and stopped in silence.
const perspectiveError = ref('')

async function handlePresetSelected(payload: { configId: string; context: string; configName: string }) {
  showPresetOverlay.value = false
  if (!inputText.value.trim()) return

  isEnriching.value = true
  perspectiveError.value = ''
  try {
    const outcome = await interceptPrompt(payload.configId, inputText.value, deviceId)
    if ('written' in outcome) {
      inputText.value = outcome.written
    } else {
      perspectiveError.value = perspectiveFailureText(t, outcome)
    }
  } catch (error) {
    perspectiveError.value = labErrorText(t, error)
  } finally {
    isEnriching.value = false
  }
}

async function executeWorkflow() {
  if (!canExecute.value) return

  isExecuting.value = true
  outputs.value = []
  primaryOutput.value = null
  generationProgress.value = 0
  generationErrorMessage.value = ''

  // Progress: a simulated ramp against a run's usual length. The run is
  // ComfyUI's; the Diffusers progress of the GPU service is another run's.
  const durationSeconds = 60 * 0.9
  const targetProgress = 98
  const updateInterval = 100
  const totalUpdates = (durationSeconds * 1000) / updateInterval
  const progressPerUpdate = targetProgress / totalUpdates

  const progressInterval = setInterval(() => {
    if (generationProgress.value < targetProgress) {
      generationProgress.value += progressPerUpdate
      if (generationProgress.value > targetProgress) {
        generationProgress.value = targetProgress
      }
    }
  }, updateInterval)

  try {
    // The seed automatic (composables/useSeedAutomatic): the same seed when
    // something changed since the picture on the surface was made, a new one
    // when nothing did, the field's when it was typed, a new one on every run
    // under the tick. The seed goes into the field.
    const runInputs = inputsKey()
    const runSeed = seedAutomatic.seedForRun(runInputs)

    /*
     * What was SENT, frozen at the moment of sending.
     *
     * Everything below this line runs after an await that lasts a minute, and
     * every control on the surface stays live during it. Read from the refs
     * afterwards, the card said what the slider stood at when the image came
     * BACK: move alpha while a run is going and the finished image was labelled
     * with a value it was never made with. The research export
     * (`labRecord`) took the same reading, which is worse - a wrong caption is
     * seen, a wrong parameter row is not. The output pictures carried wrong
     * data: the alpha value at output, not at generation.
     *
     * The seed is not in here because it is already frozen: `runSeed` is a
     * constant of this call.
     */
    const sent = Object.freeze({
      prompt: inputText.value,
      // The three factors, as they stand on the sliders, the layout of the
      // T5 block and the pooled vector, as the fields in the lines of c and
      // a have them.
      a: factorA.value,
      b: factorB.value,
      c: factorC.value,
      rows: t5Rows.value,
      pooled: pooled.value,
      negative: negativePrompt.value,
      cfg: cfgScale.value,
    })

    // Lab Architecture: /legacy = Stage 1 (Safety) + Direct ComfyUI workflow
    // No Stage 2/3 needed - legacy workflows handle prompt directly
    const response = await postDirectRun({
      prompt: sent.prompt,
      output_config: OUTPUT_CONFIG,
      factor_a: sent.a,
      factor_b: sent.b,
      factor_c: sent.c,
      t5_rows: sent.rows,
      pooled: sent.pooled,
      seed: runSeed,
      negative_prompt: sent.negative,
      cfg: sent.cfg,
    })

    if (response.data.status === 'success') {
      lastRunSeed.value = response.data.media_output?.seed ?? null

      // Get run_id to fetch all entities
      const runId = response.data.run_id

      if (runId) {
        currentRunId.value = runId
        clearInterval(progressInterval)
        generationProgress.value = 100

        // Fetch all entities from pipeline recorder
        await fetchAllOutputs(runId)

        // Set primary output (first image)
        const imageOutput = outputs.value.find(o => o.type === 'image')
        if (imageOutput) {
          primaryOutput.value = imageOutput
          // This picture is now the one the next press is compared with.
          seedAutomatic.arrived(runInputs, lastRunSeed.value ?? runSeed)
          runs.value.push({
            id: runId,
            // In the card's bar: what tells two runs of this instrument apart.
            label: factorLabel(sent.a, sent.b, sent.c, sent.rows, sent.pooled),
            sub: '',
            // On its back, with the prompt and the model's sheet: the record.
            meta: [`seed: ${lastRunSeed.value ?? runSeed}`],
            prompt: sent.prompt,
            configId: OUTPUT_CONFIG,
            createdAt: Date.now(),
            modelMeta: response.data.model_meta ?? null,
            runId,
            output: { url: imageOutput.url, media_type: 'image' },
            error: null,
          })
        }

        // Record for research export (image already saved by pipeline recorder)
        labRecord({
          parameters: {
            prompt: sent.prompt,
            // The three factors - the card's own comparison key. Without them
            // a recorded run cannot be read back into the card it had.
            factor_a: sent.a, factor_b: sent.b, factor_c: sent.c,
            t5_rows: sent.rows,
            pooled: sent.pooled,
            // The name the chunk reports for a run of the three factors, so
            // that a record of this run and a record of an alpha run are told
            // apart by the same field.
            fusion_strategy: 'three_factor',
            seed: runSeed,
            negative_prompt: sent.negative, cfg: sent.cfg,
            output_config: OUTPUT_CONFIG,
          },
          results: { run_id: runId },
        })
      } else {
        clearInterval(progressInterval)
        console.error('[Surrealizer] No run_id in response')
        generationErrorMessage.value = t('generationError.unknown')
      }
    } else {
      clearInterval(progressInterval)
      const blockedBody = blockedReason(response.data)
      generationErrorMessage.value = blockedBody
        ? t(safetyBlockKey(blockedBody, response.data.stage))
        : generationErrorFor(response.data.error || '')
    }
  } catch (error: any) {
    clearInterval(progressInterval)
    console.error('[Surrealizer] Execution error:', error)
    // A blocked run is read as what it is and said in the reader's language;
    // the backend's own sentence is German and stays behind the classification.
    const blocked = blockedReason(error)
    if (blocked) {
      generationErrorMessage.value = t(safetyBlockKey(blocked, error.response?.data?.stage))
    } else {
      const errorMsg = error.response?.data?.error || error.message || ''
      generationErrorMessage.value = generationErrorFor(errorMsg)
    }
  } finally {
    isExecuting.value = false
  }
}

async function fetchAllOutputs(runId: string) {
  try {
    // Fetch entities metadata
    const entitiesResponse = await axios.get(`/api/pipeline/${runId}/entities`)
    const entities = entitiesResponse.data.entities || []

    // Process each entity and add to outputs
    for (const entity of entities) {
      const output = await processEntity(runId, entity)
      if (output) {
        outputs.value.push(output)
      }
    }
  } catch (error: any) {
    console.error('[Surrealizer] Error fetching outputs:', error)
  }
}

async function processEntity(runId: string, entity: any): Promise<WorkflowOutput | null> {
  try {
    const entityType = entity.type
    const filename = entity.filename

    // FAILSAFE: Only show final outputs (entities with prefix 'output_')
    // This filters out all intermediate results:
    // - config_used, input, stage1_output, interception, safety, safety_pre_output, etc.
    if (!entityType.startsWith('output_')) {
      return null
    }

    // Fetch entity content
    const response = await axios.get(`/api/pipeline/${runId}/entity/${entityType}`, {
      responseType: 'blob' // Get as blob to handle binary data
    })

    const contentType = String(response.headers['content-type'] ?? '')

    // Determine output type from content-type
    if (contentType.startsWith('image/')) {
      // Image output
      const url = URL.createObjectURL(response.data)
      return {
        type: 'image',
        filename,
        url
      }
    } else if (contentType.includes('application/json')) {
      // JSON output
      const text = await response.data.text()
      return {
        type: 'json',
        filename,
        content: text
      }
    } else if (contentType.includes('text/')) {
      // Text output
      const text = await response.data.text()
      return {
        type: 'text',
        filename,
        content: text
      }
    } else {
      // Unknown type
      return {
        type: 'unknown',
        filename
      }
    }
  } catch (error: any) {
    console.error(`[Surrealizer] Error processing entity:`, error)
    return null
  }
}

/**
 * The picture on the surface, large. It is the run standing in the strip, so
 * the strip shows it: the same view its card opens, with the record beside the
 * picture and the card's row behind it (one click, one view,
 * on every surface). A run the strip does not hold — a favourite from another
 * device, or a run taken off the strip with its × — opens as the picture alone,
 * as before 2026-09-22.
 */
function showImageFullscreen(imageUrl: string) {
  if (currentRunId.value && drawer.value?.show(currentRunId.value)) return
  fullscreenImage.value = imageUrl
}

// ============================================================================
// Textbox Actions (Copy/Paste/Delete)
// ============================================================================

function copyInputText() {
  copyToClipboard(inputText.value)
}

function pasteInputText() {
  inputText.value = pasteFromClipboard()
}

function clearInputText() {
  inputText.value = ''
  sessionStorage.removeItem('lat_lab_ef_prompt')
}

// ============================================================================
// Taking a run of this instrument back — from the strip and from the favourites
// ============================================================================

/**
 * Which card was last asked for. A run is read from disk, and without this the
 * answer to an earlier click can land on the surface after a later one.
 */
let wantedRun: string | null = null

/**
 * The key in a card's bar: that run, back on this surface.
 *
 * Through the SAME reader the favourites bar goes through, and through the same
 * route: `/api/favorites/<id>/restore` answers for any run, favourited or not.
 * A second reader here would be the strip and the gallery disagreeing about
 * what a run of this instrument restores to.
 */
async function restoreRun(id: string) {
  wantedRun = id
  const data = await favoritesStore.getRestoreData(id)
  if (wantedRun !== id || !data) return
  favoritesStore.setRestoreData(data)
}

watch(() => favoritesStore.pendingRestoreData, (restoreData) => {
  if (!restoreData) return

  // A run made by another instrument is not this one's to read - and above all
  // not this one's to CLEAR. The gallery sets the restore and then navigates;
  // whoever clears it first decides that nothing is restored at all. This page
  // stands in the same rail as Denoising Archaeology, so that was one click
  // away: a denoising favourite restored from here vanished without a word.
  const instrument = restoreData.instrument
  if (instrument && instrument.tool !== 'surrealizer') return
  // The same for a Canvas board (a kept workflow, an output of a Canvas run):
  // the gallery routes it to the Canvas, and this watcher fires before the
  // Canvas has mounted.
  if (restoreData.canvas_workflow) return

  // Whether every input the run went out with is read back onto the surface.
  // Where one is not, the surface's settings are not the picture's, and the
  // seed automatic counts the next press as a change.
  let readWhole = true

  if (restoreData.input_text) {
    inputText.value = restoreData.input_text
  } else {
    readWhole = false
  }

  // Restore this instrument's parameters from current_state, read through
  // lib/fusionSetting (`recordedFactors`), the reading the favourites panel
  // shows the same record with. A record it cannot read leaves the sliders
  // where they stand.
  const state = restoreData.current_state || {}
  const factors = recordedFactors(state)
  if (factors) {
    factorA.value = factors.a
    factorB.value = factors.b
    factorC.value = factors.c
    t5Rows.value = factors.rows
    pooled.value = factors.pooled
    if (!factors.exact) readWhole = false
  } else {
    readWhole = false
  }

  // Typed, not coerced. A run that was started without either field records a
  // JSON null — 16 of the stored runs for the negative prompt, 15 for the CFG —
  // and `!== undefined` let both through: String(null) put the four letters
  // "null" into the negative prompt, which was then persisted and sent with the
  // next run, and Number(null) put 0 into a CFG field whose own minimum is 1.
  if (typeof state.negative_prompt === 'string') negativePrompt.value = state.negative_prompt
  else readWhole = false
  if (typeof state.cfg === 'number' && Number.isFinite(state.cfg)) cfgScale.value = state.cfg
  else readWhole = false

  // And the PICTURE of that run, on the surface where the fields now stand.
  // Without this the settings step back to the chosen run while the large view
  // keeps showing the last one generated — the surface then reads as "these
  // settings made this picture", which is the one thing the key exists to
  // make true.
  const media = (restoreData.media_outputs || []) as Array<{
    type?: string; url?: string; filename?: string; metadata?: { seed?: unknown }
  }>
  const picture = media.find(entry => entry.type === 'image' && entry.url)
  if (picture?.url) {
    primaryOutput.value = {
      type: 'image',
      filename: String(picture.filename || ''),
      url: picture.url,
    }
    currentRunId.value = restoreData.run_id || null
    // And the seed that MADE it. No run has one in current_state; the recorder
    // writes it onto the picture, and favorites_routes hands each entity's
    // metadata out with the run (518 of the 535 runs stored under the Diffusers
    // twin's config by 2026-09-08 carry one). Unread, the seed field kept whatever the session had put
    // there, and a run started from a restored picture went out under a seed
    // that picture never had. The random-variation tick is left alone: the
    // record says which seed made the picture, not whether the next one is to
    // be drawn afresh.
    //
    // Read typed, not coerced (the composable checks it): Number(null) is 0,
    // and a run that produced no seed writes
    // exactly null (the cloud services that have none). Coercing would put a
    // 0 in the field and call it the picture's.
    const shotSeed = picture.metadata?.seed
    // The automatic writes it into the field and compares the next press with
    // this picture: pressing again unchanged makes a variation of it, moving a
    // slider shows the change on its seed.
    seedAutomatic.laidBack(readWhole ? inputsKey() : null, shotSeed)
  }

  favoritesStore.setRestoreData(null)
}, { immediate: true })

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
</script>

<style scoped>
/* ============================================================================
   The page: band, three columns, result surface. No vertical page scroll —
   each column carries its own overflow, so a long field never pushes the band
   or the result surface off the screen.
   ============================================================================ */

.ef {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  /* The instrument has two doors: the Latent Lab's column, and its own route.
     Through the first it stands in the page frame, which already keeps the
     favourites strip's room free (assets/shell.css); through the second it is
     the whole page and has to keep it itself, or the result surface's header
     ends up behind the strip. 36 px toggle bar plus its 1 px border. */
  padding-bottom: calc(var(--footer-collapsed-height, 36px) + 1px);
  box-sizing: border-box;
  background: var(--bg-base);
  color: #e2e8f0;
}

.shell-page .ef {
  padding-bottom: 0;
}

/* Standing on this instrument's own route the switch has no bar to sit in, so
   it keeps its own margin. Teleported into the Latent Lab's bar the margin is
   gone with the class, because there it is one button among the bar's own. */
.ef > .ef-drawer-btn { align-self: flex-start; margin: 8px 0 2px 4px; }

/* The frame, the stage and the two columns are `.lab-main` / `.lab-stage` /
   `.lab-work` from assets/flow-stage.css — the same rules this page carried as
   `.ef-*` down to the 2.0467 and the 1.509434 %, which is how they got into the
   shared file in the first place. Nothing about them is Encoder Fusion's, and a
   fourth copy of them here would be the second implementation that
   docs/ELEMENT_STRUCTURE_REGISTRY.md forbids.

   What is NOT there and stays out: `--flow-map-w`. As a page header the cap
   held the whole surface at 1000 px on a 1920 px screen — 111 px of text width
   at every window width. */

/* The node title, in the band's own step (assets/flow-stage.css). */
.lbl {
  font-size: var(--flow-fs-label);
  font-weight: 400;
  color: #e8e8e8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

/* ---------------------------------------------------------------------------
   Two surfaces, not three columns: the setting and what it does to the two
   readings are one thing being handled, and a functional unit is one surface.

   The proportion and its meaning come from `.lab-work`: 1fr : 2.0467fr, left
   what a run is prepared with, right what came out of it. At 1328 px of work
   area that is 429 / 878. The two children get min-0 and the column direction
   from `.lab-work > *`; what stands here is only what each of them adds.
   --------------------------------------------------------------------------- */

/* ---------------------------------------------------------------------------
   The text
   --------------------------------------------------------------------------- */
/* A HEIGHT, not a share of what is left. With `flex: 1` the field took the
   whole column, 464 of 513 px at a 1600x900 window, for a prompt of a line or
   two, and there was nowhere for the result to stand. Same measure as Denoising
   Archaeology. The floor lives on this holder rather than on the component, so
   this file never has to outrank the component's own scoped CSS to set it. */
.ef-field-slot {
  flex: 0 0 auto;
  height: 168px;
  display: flex;
  flex-direction: column;
}

.ef-field {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* ---------------------------------------------------------------------------
   What came out. It filled the band's third node until 2026-08-21 and had
   nowhere else to be on this surface; the room the band took is most of what it
   stands in now (at 1600x900: 429 px across, against the node's 151).
   --------------------------------------------------------------------------- */
.ef-out {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* The surface measures itself so the square inside can take the SMALLER of its
   two sides: .instr-frame / .instr-stack / .instr-square in
   assets/instrument-surface.css. Nothing stands in the stack besides the
   picture, and since 2026-08-23 nothing stands under it either, so the reserve
   stays 0 and the frame is the whole column. */
.ef-out-img,
.ef-out-empty {
  border-radius: 8px;
  display: block;
}

.ef-out-img {
  object-fit: contain;
  cursor: zoom-in;
}

.ef-out-empty {
  background: var(--surface-2);
}

.ef-field :deep(.bubble-textarea) {
  flex: 1;
  min-height: 0;
  height: 100%;
}

/* ---------------------------------------------------------------------------
   The setting — one surface
   --------------------------------------------------------------------------- */
/* Everything a run is prepared with. It scrolls, and since 2026-08-22 it does so
   as a matter of course rather than as a fallback: the prompt block, the
   drawing, the three axes and the table's floor together ask for more than the
   603 px column of the reference device (see .ef-tokens). */
.ef-set {
  gap: 12px;
  overflow-y: auto;
}

/* What came out. */
.ef-result {
  gap: 10px;
}

.ef-set-head {
  font-size: var(--flow-fs-sub);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-bottom: 6px;
}

.ef-table-head {
  margin-bottom: 2px;
}

/* The named points as fields (components/ChipSelect.vue), two to a row: the
   longest name, „Surrealization 35", does not fit three to the 303 px of the
   reference device's column. The lit field is the accent, the same green the
   Standard button had (green is for what is meant). */
.ef-presets {
  flex: 0 0 auto;
  margin-bottom: 6px;
}

/* The drawing: components/ConditioningTable.vue, at the column's width; its
   height follows from the viewBox. */
.ef-table {
  flex: 0 0 auto;
}

/* One factor: its line, and under it the axis. The axis itself lives in
   components/MarkedSlider.vue — the bar, the marks over it and the room they
   need at the ends. What stays here is only where it stands on this surface. */
.ef-factor {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
}

.ef-factor-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: var(--flow-fs-sub);
  color: #d5dbe3;
}

.ef-factor-line b {
  font-weight: 400;
  color: #fff;
}

.ef-factor-val {
  margin-inline-start: auto;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-variant-numeric: tabular-nums;
  color: #fff;
}

/* The two fields in a factor's line between the name and the number: in the
   line of a for the pooled vector, in the line of c for the T5 block's rows.
   Two columns as wide as their labels, at the line's own step. The selector
   outranks the component's own `.chip-select` rule, whose columns are equal,
   each as wide as the wider label. */
.ef-factor-line .ef-switch {
  grid-template-columns: auto auto;
  gap: 0.3rem;
  margin-inline-start: 4px;
}
.ef-switch :deep(.chip-select-option) {
  padding: 0.12rem 0.55rem;
  font-size: var(--flow-fs-sub);
}

.ef-track {
  flex: 0 0 auto;
}

/* The token table takes the room the column has left, and not less than this;
   below the floor the column scrolls, and the table scrolls in itself past
   that. 150 px is the head and four rows: the column of the reference device
   (603 px at 1210 x 834) is over-full with the field, the drawing and the
   three axes alone, so the floor decides how much of the table stands on the
   screen once the column is scrolled to its foot. */
.ef-tokens {
  flex: 1 1 auto;
  min-height: 150px;
  overflow: auto;
  border-top: 1px solid var(--surface-2);
  padding-top: 6px;
}

.ef-token-table {
  border-collapse: collapse;
  width: 100%;
  font-size: var(--flow-fs-hint);
}

.ef-token-table th {
  text-align: start;
  color: rgba(255, 255, 255, 0.45);
  font-weight: 400;
  padding: 2px 6px 4px 0;
}

.ef-token-table td {
  padding: 1px 6px 1px 0;
  vertical-align: top;
  color: #ddd;
  white-space: nowrap;
}

.ef-tok-n {
  color: rgba(255, 255, 255, 0.4);
  width: 34px;
  font-variant-numeric: tabular-nums;
}

/* A piece in its row is components/TokenChip.vue, the chip of the Tokenizer
   instrument (docs/latent_lab_station_design.md, R21 and R23): a control mark
   in the control-character colours, the padding as an empty frame. */

/* The T5 cells b adds into the CLIP block, in the T5 colour of the drawing. */
.ef-paired td:nth-child(3) {
  background: rgba(156, 106, 63, 0.12);
}

.ef-tokens-note {
  margin: 6px 0 0;
  font-size: var(--flow-fs-hint);
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.45);
}
.advanced-settings summary {
  color: rgba(255, 255, 255, 0.5);
  font-size: var(--flow-fs-sub);
  cursor: pointer;
  padding: 0.25rem 0;
}

.settings-grid label {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 0.25rem;
  color: rgba(255, 255, 255, 0.5);
  font-size: var(--flow-fs-hint);
}

.setting-input {
  min-width: 0;
  max-width: 100%;
  /* The field stands at the width of its content here, where the shared block
     in assets/flow-stage.css lets it fill the row. */
  width: auto;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
  color: white;
  font-size: var(--flow-fs-sub);
}

.setting-small {
  width: 80px;
}

/* The foot of the setting surface: the fold with the advanced settings. Until
   2026-09-15 the switch „Same prompt" / „Adapted prompts" stood in it too. */
.ef-foot {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 12px;
}

.ef-foot .advanced-settings {
  flex: 1 1 100%;
  min-width: 0;
  /* The shared block gives every klappe a step above itself; here the fold
     stands directly under the token table. */
  margin-top: 0;
}
.ef-err {
  margin: 0;
  font-size: var(--flow-fs-hint);
  line-height: 1.5;
  color: #ef4444;
}


/* ---------------------------------------------------------------------------
   Below 640 px the columns stand one under the other and the page scrolls as
   a column again. Until 2026-08-21 this breakpoint followed the band's own
   unstacking; the band is gone, the width at which two columns stop being two
   columns is not.
   --------------------------------------------------------------------------- */
@media (max-width: 640px) {
  .ef {
    height: auto;
    overflow: visible;
  }

  /* `.lab-stage` and `.lab-work` are unscoped, so these two need the page's own
     attribute to outrank them — that is what :deep does from a scoped block. */
  :deep(.lab-stage) {
    flex: 0 0 auto;
  }

  :deep(.lab-work) {
    grid-template-columns: 1fr;
    row-gap: 16px;
  }

  .ef-set,
  .ef-result {
    overflow: visible;
  }
}
</style>
