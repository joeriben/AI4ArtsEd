<!--
  Encoder Fusion Workbench — a comparison instrument, not a generator: which
  parameter varies along which of the three axes is set here, and the runs stand
  against each other. X gives the columns, Y the rows, Z the axis the reader
  drives through afterwards; everything else stays constant.

  Rebuilt on 2026-09-05 into the frame the Latent Lab's instruments share, and
  it brings nothing of its own where the platform has it: the page skeleton and
  the stage proportion from assets/flow-stage.css (`.lab-page` / `.lab-main` /
  `.lab-stage` / `.lab-work` / `.lab-prep` / `.lab-col` / `.lab-plot` /
  `.lab-grid` / `.lab-series` / `.lab-pick-label` / `.lab-prep-err`), the square
  surface around a picture (assets/instrument-surface.css), the cell of a raster
  (components/MediaGridCell.vue), the trigger in the frame's bar
  (components/ShellRun.vue) and the axis with its marks
  (components/MarkedSlider.vue). See docs/ELEMENT_STRUCTURE_REGISTRY.md.

  EVERY control stands in the left column — the three axes, the
  drive-through, the constants. The right side carries the raster alone.

  The prompt rows take NO perspective and no ready list, and that is the point:
  what a row holds is a VALUE OF AN AXIS, the wording whose effect is being
  measured. A perspective would rewrite exactly the words the comparison is
  about, as it would in Bias Archaeology. The prompt of the instrument this one
  measures — Encoder Fusion — stands on that instrument.
-->
<template>
  <div class="fw lab-page">
    <!-- `defer` is not optional: a Teleport resolves its target against the live
         document, and on the app's FIRST render the tree is still detached, so
         `.shell-bar-run` cannot be found. -->
    <ShellRun
      :ready="canRun"
      :running="isRunning"
      :title="`${t('latentLab.workbench.runSweep')} · ${cellPlan.length} ${t('latentLab.workbench.cells')}`"
      :label="t('latentLab.runLine.image')"
      :count="doneCount"
      :total="cellPlan.length"
      @run="runSweep"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <section class="lab-prep lab-col col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <!-- The prompt field of Encoder Fusion, taken over whole
                 (views/surrealizer.vue): the ready-made examples over the
                 field, the field with its four actions and the way in for a
                 dropped picture, and under it the line that says what a short
                 text costs where T5 is the point. It stands over the axes
                 because a page begins with the prompt, and it
                 steps aside where `prompt` is an axis: the axis then carries up
                 to three written prompts and this one runs nothing. -->
            <template v-if="hasPromptConstant">
              <PromptExamples
                :items="promptExamples"
                :current="promptText"
                :disabled="isRunning"
                @pick="applyExample"
              />
              <MediaInputBox
                chrome="bare"
                :placeholder="t('mediaInput.freePromptPlaceholder')"
                v-model:value="promptText"
                input-type="text"
                :rows="4"
                :is-filled="!!promptText"
                :is-loading="readingPicture"
                :disabled="readingPicture || isRunning"
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
              <p v-if="isShortPrompt" class="lab-hint">
                {{ t('surrealizer.shortPrompt', { preset: storyPresetName }) }}
              </p>
              <button
                type="button"
                class="fw-mini"
                :disabled="isRunning || !!t5Busy[promptText] || !promptText.trim()"
                @click="expandT5(promptText)"
              >{{ t5Busy[promptText] ? t('latentLab.workbench.t5Expanding') : t('latentLab.workbench.t5Expand') }}</button>
              <textarea
                class="setting-input fw-t5 fw-t5-lead"
                rows="2"
                :placeholder="t('latentLab.workbench.t5Placeholder')"
                :value="t5For(promptText)"
                :disabled="isRunning"
                @change="setT5(promptText, ($event.target as HTMLTextAreaElement).value)"
              ></textarea>
            </template>

            <!-- The three axes. Each says which parameter it carries and then
                 the values that parameter takes, in the shape that parameter
                 has: a list of numbers, a track of windows, a row of fusions, or
                 up to three written prompts. The third may carry nothing. -->
            <div v-for="ax in axisDescriptors" :key="ax.slot" class="fw-axis">
              <label class="lab-pick-label">{{ t(ax.labelKey) }}</label>
              <select
                class="setting-input"
                :value="ax.ref.value.param"
                :disabled="isRunning"
                @change="onParamChange(ax.ref, ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="p in ax.available.value" :key="p.id" :value="p.id" :disabled="p.taken">{{ paramLabel(p.id) }}</option>
              </select>

              <template v-if="kindOf(ax.ref.value.param) === 'number'">
                <input type="text" class="setting-input" v-model.lazy="ax.text.value" :disabled="isRunning" />
                <p v-if="ax.ref.value.param === 'layer'" class="lab-hint">{{ t('latentLab.workbench.layerHint') }}</p>
              </template>

              <template v-else-if="kindOf(ax.ref.value.param) === 'text'">
                <div v-for="(pv, i) in ax.ref.value.values" :key="i" class="fw-prompt">
                  <div class="fw-prompt-main">
                    <textarea
                      class="setting-input fw-prompt-text"
                      rows="2"
                      :value="pv"
                      :disabled="isRunning"
                      @change="setPromptValue(ax.ref, i, ($event.target as HTMLTextAreaElement).value)"
                    ></textarea>
                    <button
                      type="button"
                      class="fw-remove"
                      v-if="ax.ref.value.values.length > 1"
                      :disabled="isRunning"
                      :title="t('latentLab.workbench.promptRemove')"
                      @click="removePromptValue(ax.ref, i)"
                    >&times;</button>
                  </div>
                  <button
                    type="button"
                    class="fw-mini"
                    :disabled="isRunning || !!t5Busy[pv] || !pv.trim()"
                    @click="expandT5(pv)"
                  >{{ t5Busy[pv] ? t('latentLab.workbench.t5Expanding') : t('latentLab.workbench.t5Expand') }}</button>
                  <textarea
                    class="setting-input fw-t5"
                    rows="2"
                    :placeholder="t('latentLab.workbench.t5Placeholder')"
                    :value="t5For(pv)"
                    :disabled="isRunning"
                    @change="setT5(pv, ($event.target as HTMLTextAreaElement).value)"
                  ></textarea>
                </div>
                <button
                  type="button"
                  class="fw-mini fw-add"
                  v-if="ax.ref.value.values.length < MAX_PROMPTS"
                  :disabled="isRunning"
                  @click="addPromptValue(ax.ref)"
                >{{ t('latentLab.workbench.promptAdd') }}</button>
              </template>

              <template v-else-if="kindOf(ax.ref.value.param) === 'range'">
                <RangeTrack
                  :model-value="rangesOf(ax.ref)"
                  :max="numSteps"
                  :marks="stepMarks"
                  :disabled="isRunning"
                  @update:model-value="v => setRanges(ax.ref, v)"
                />
                <p class="lab-hint">{{ t('latentLab.workbench.stepWindowHint', { steps: numSteps }) }}</p>
              </template>

              <template v-else-if="kindOf(ax.ref.value.param) === 'strategy'">
                <ChipSelect
                  :model-value="ax.ref.value.values"
                  :options="strategyOptions"
                  :columns="2"
                  multiple
                  :disabled="isRunning"
                  @update:model-value="v => setStrategies(ax.ref, v as string[])"
                />
              </template>

              <p v-else class="lab-hint">{{ t('latentLab.workbench.zNoneHint') }}</p>
            </div>

            <!-- Which fusion is in effect, and its arithmetic. It stands always,
                 because the picture cannot be read without it. -->
            <div class="fw-formula">
              <label class="lab-pick-label">{{ t('latentLab.workbench.fusionFormulaLabel') }}</label>
              <div v-for="sName in activeStrategies" :key="sName" class="fw-formula-row">
                <span class="fw-formula-name">{{ valueLabel('strategy', sName) }}</span>
                <code class="fw-code">{{ t('latentLab.workbench.formulaCore') }} = {{ formulaFor(sName).core }} · {{ t('latentLab.workbench.formulaTail') }} = {{ formulaFor(sName).tail }}</code>
                <code v-if="formulaFor(sName).note" class="fw-code fw-code-note">{{ formulaFor(sName).note }}</code>
              </div>
              <p class="fw-legend">{{ t('latentLab.workbench.formulaLegend') }}</p>
            </div>

            <!-- The third dimension, driven through after the sweep. With one
                 value there is nothing to drive, and the axis says where it
                 stands instead. -->
            <template v-if="hasResults && zAxis.param !== 'none'">
              <label class="lab-pick-label">
                {{ t('latentLab.workbench.driveLabel') }} ·
                {{ paramLabel(zAxis.param) }} = {{ trunc(valueLabel(zAxis.param, currentZ), 28) }}
              </label>
              <MarkedSlider
                v-if="zAxis.values.length > 1"
                :model-value="zIndex"
                :min="0"
                :max="zAxis.values.length - 1"
                :step="1"
                :marks="zMarks"
                :aria-label="t('latentLab.workbench.driveLabel')"
                :value-text="`${paramLabel(zAxis.param)} = ${valueLabel(zAxis.param, currentZ)}`"
                @update:model-value="v => (zIndex = v)"
              />
            </template>

            <!-- Shut on every visit. It used to remember being open, which is
                 why the seldom-set values sat under the axes in plain sight;
                 now it is folded away, as everywhere. -->
            <details class="advanced-settings">
              <summary>{{ t('latentLab.workbench.advancedLabel') }}</summary>
              <div class="settings-grid">
                <template v-for="p in constantParamsBelow" :key="p">
                <!-- A <label> may hold ONE control, and it hands every click in
                     it to the first one it finds. A row of fields and a track of
                     handles are several, so they get a caption instead. -->
                <div v-if="kindOf(p) === 'range'" class="fw-wide fw-field">
                  <span>{{ paramLabel(p) }}</span>
                  <RangeTrack
                    :model-value="[parseRange(constants[p])]"
                    :max="numSteps"
                    :max-ranges="1"
                    :marks="stepMarks"
                    :disabled="isRunning"
                    @update:model-value="v => (constants[p] = rangeValue(v[0]!))"
                  />
                </div>
                <div v-else-if="kindOf(p) === 'strategy'" class="fw-wide fw-field">
                  <span>{{ paramLabel(p) }}</span>
                  <ChipSelect
                    :model-value="constants[p]"
                    :options="strategyOptions"
                    :columns="2"
                    :disabled="isRunning"
                    @update:model-value="v => (constants[p] = v as string)"
                  />
                </div>
                <label v-else class="fw-wide">
                  {{ paramLabel(p) }}
                  <template v-if="kindOf(p) === 'text'">
                    <textarea v-model.lazy="constants[p]" rows="2" class="setting-input" :disabled="isRunning"></textarea>
                    <button
                      type="button"
                      class="fw-mini"
                      :disabled="isRunning || !!t5Busy[constants[p]] || !constants[p].trim()"
                      @click="expandT5(constants[p])"
                    >{{ t5Busy[constants[p]] ? t('latentLab.workbench.t5Expanding') : t('latentLab.workbench.t5Expand') }}</button>
                    <textarea
                      class="setting-input fw-t5"
                      rows="2"
                      :placeholder="t('latentLab.workbench.t5Placeholder')"
                      :value="t5For(constants[p])"
                      :disabled="isRunning"
                      @change="setT5(constants[p], ($event.target as HTMLTextAreaElement).value)"
                    ></textarea>
                  </template>
                  <input v-else type="text" v-model="constants[p]" class="setting-input setting-small" :disabled="isRunning" />
                  <p v-if="p === 'layer'" class="lab-hint">{{ t('latentLab.workbench.layerHint') }}</p>
                </label>
                </template>
                <label class="fw-wide">
                  {{ t('latentLab.workbench.negativeLabel') }}
                  <input v-model="negativePrompt" type="text" class="setting-input" :disabled="isRunning" />
                </label>
                <label>
                  {{ t('latentLab.workbench.stepsLabel') }}
                  <input v-model.number="numSteps" type="number" min="10" max="50" class="setting-input setting-small" :disabled="isRunning" />
                </label>
              </div>
            </details>

            <!-- Before the first sweep: what this surface is waiting for. -->
            <p v-if="!hasResults && !isRunning" class="lab-prep-err quiet">
              {{ t('latentLab.workbench.emptyHint') }}
            </p>
            <p v-if="errorMessage" class="lab-prep-err">{{ errorMessage }}</p>
          </section>

          <!-- The raster: one column per value of X, one row per value of Y, at
               the place on Z the axis on the left stands. -->
          <section class="lab-plot">
            <div
              ref="gridEl"
              class="lab-grid labelled"
              :style="{
                '--lab-grid-cols': xAxis.values.length,
                '--lab-grid-rows': yAxis.values.length,
                '--lab-grid-cell': cellPx ? `${cellPx}px` : '',
              }"
            >
              <div class="lab-grid-col">
                <div class="lab-grid-head fw-corner">
                  {{ paramLabel(yAxis.param) }} \ {{ paramLabel(xAxis.param) }}
                </div>
                <div class="lab-series">
                  <div v-for="yv in yAxis.values" :key="`r${yv}`" class="lab-grid-rowname" :title="valueLabel(yAxis.param, yv)">
                    {{ trunc(valueLabel(yAxis.param, yv), 18) }}
                  </div>
                </div>
              </div>
              <div v-for="xv in xAxis.values" :key="`c${xv}`" class="lab-grid-col">
                <div class="lab-grid-head" :title="valueLabel(xAxis.param, xv)">{{ trunc(valueLabel(xAxis.param, xv), 18) }}</div>
                <div class="lab-series">
                  <div v-for="yv in yAxis.values" :key="`${yv}|${xv}`" class="instr-frame">
                    <div class="instr-stack">
                      <MediaGridCell
                        :url="cellUrl(xv, yv)"
                        :run-id="cellRunId(xv, yv)"
                        :prompt="cellPrompt(xv, yv)"
                        :config-id="OUTPUT_CONFIG"
                        :created-at="cellMadeAt(xv, yv)"
                        :facts="cellFacts(xv, yv)"
                        :is-favorited="isFavorited(cellRunId(xv, yv))"
                        @toggle-favorite="toggleFavorite(cellRunId(xv, yv))"
                        @download="downloadCell(xv, yv)"
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

    <!-- What the prompt field's button opens: the perspectives, and the one
         that is picked writes the prompt over. -->
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
import { ref, computed, watch, onBeforeUnmount, type Ref, type WritableComputedRef } from 'vue'
import MediaGridCell from '@/components/MediaGridCell.vue'
import ShellRun from '@/components/ShellRun.vue'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import { usePromptPresets } from '@/lib/promptPresets'
import { usePictureTemplate } from '@/composables/usePictureTemplate'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { INTERCEPTION_PRESETS } from '@/types/canvas'
import ChipSelect, { type ChipOption } from '@/components/ChipSelect.vue'
import MarkedSlider, { type SliderMark } from '@/components/MarkedSlider.vue'
import RangeTrack, { type RangeSelection, type RangeMark } from '@/components/RangeTrack.vue'
import { useI18n } from 'vue-i18n'
import { generationErrorFor as labErrorText, refusalKeyOf, interceptPrompt, perspectiveFailureText } from '@/composables/useLabRun'
import { downloadMedia } from '@/lib/downloadMedia'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'
import axios from 'axios'
import { postStreamedRun } from '@/services/directRun'
import { useLatentLabRecorder } from '@/composables/useLatentLabRecorder'
import { useGridCellWidth } from '@/composables/useGridCellWidth'
import { useDeviceId } from '@/composables/useDeviceId'
import { useFavoritesStore } from '@/stores/favorites'
import { apiBase } from '@/services/labApi'

const { t } = useI18n()

/** What this surface asks the server for, named once. */
const OUTPUT_CONFIG = 'fusion_workbench'

const { record: labRecord, sessionId, lastRunId } = useLatentLabRecorder('workbench')
const deviceId = useDeviceId()
const favoritesStore = useFavoritesStore()

// --- parameter registry ---
type ParamId = 'prompt' | 'alpha' | 'cfg' | 'step' | 'layer' | 'strategy' | 'seed'
/**
 * The THIRD axis alone may carry nothing. Two dimensions are often the whole
 * question, and a third that has to hold something forces a sweep three or five
 * times the size for a comparison nobody asked for.
 */
type AxisParam = ParamId | 'none'
type ParamKind = 'number' | 'text' | 'range' | 'strategy'
interface ParamDef {
  kind: ParamKind
  vocab?: string[]
}
/**
 * The five fusions are the five `_fused_pair` implements
 * (gpu_service/services/diffusers_backend.py). `original`, which stands beside
 * Centered Fade on Encoder Fusion, is a different ENCODING: CLIP-L alone, T5 at
 * the length of its own text, two separately written prompts. An axis that
 * varies one formula has no place to put it.
 *
 * The denoising window and the entry block replaced the five named bands on
 * 2026-09-08. `rep_hook` compares a FRACTION of the run at every step, which is
 * what a free window says. The hook is installed at ONE block, and every later
 * block computes from what that one put out; the note „(approx.)" on middle and
 * deep had been standing in for that.
 */
const PARAMS: Record<ParamId, ParamDef> = {
  prompt: { kind: 'text' },
  alpha: { kind: 'number' },
  cfg: { kind: 'number' },
  step: { kind: 'range' },
  layer: { kind: 'number' },
  strategy: { kind: 'strategy', vocab: ['centered_fade', 'legacy', 'dual_alpha', 'slerp', 'normalized'] },
  seed: { kind: 'number' },
}
const ALL_PARAMS = Object.keys(PARAMS) as ParamId[]
// This platform's standard test prompt, in its English rendering whatever the
// page's language: the workbench hands the prompt to the encoders itself.
const DEFAULT_PROMPT = t('promptExamples.presets.house', {}, { locale: 'en' })

function kindOf(p: AxisParam): ParamKind | 'none' {
  return p === 'none' ? 'none' : PARAMS[p].kind
}
function paramLabel(p: AxisParam): string {
  return t(`latentLab.workbench.param.${p}`)
}
function defaultValuesFor(p: AxisParam): string[] {
  switch (p) {
    case 'prompt': return [DEFAULT_PROMPT]
    case 'alpha': return ['0', '10', '15', '20', '25', '35']
    case 'cfg': return ['3', '5.5', '8']
    case 'step': return ['1-8', '9-17', '18-25']
    case 'layer': return ['0', '10', '23']
    case 'strategy': return [...(PARAMS.strategy.vocab || [])]
    case 'seed': return ['42']
    case 'none': return ['']
  }
}

/** A window over the run, written as the two step numbers it runs between. */
function parseRange(v: string): RangeSelection {
  const m = /^(\d+)\s*-\s*(\d+)$/.exec(v.trim())
  if (!m) return { from: 1, to: 0 }
  return { from: parseInt(m[1]!, 10), to: parseInt(m[2]!, 10) }
}
function rangeValue(r: RangeSelection): string {
  return `${r.from}-${r.to}`
}

/**
 * An axis holds each of its values ONCE. A cell is addressed by its three
 * values (`cellKeyOf`), so two equal values on one axis are two raster columns
 * sharing one address: both are generated, the second overwrites the first, and
 * the reader sees the same picture twice under the same heading. Two identical
 * windows and two identical numbers are both a keystroke away.
 */
function uniq(values: string[]): string[] {
  return [...new Set(values)]
}

/** The fusions as fields, named the way Encoder Fusion names them. */
const strategyOptions = computed<ChipOption[]>(() =>
  (PARAMS.strategy.vocab || []).map((v) => ({ value: v, label: t(`surrealizer.fusion_${v}`) })),
)

// --- axis state ---
interface AxisState {
  param: AxisParam
  values: string[]
}
/**
 * The fusion is the leading dimension. It is the one thing this bench is FOR —
 * „Fusion Strategy als zentrales UI-Element, nicht Advanced Setting"
 * (docs/DEVELOPMENT_DECISIONS.md) — and it had been sitting in the fold of
 * constants while alpha took the columns.
 */
const xAxis = ref<AxisState>({ param: 'strategy', values: defaultValuesFor('strategy') })
const yAxis = ref<AxisState>({ param: 'step', values: defaultValuesFor('step') })
const zAxis = ref<AxisState>({ param: 'none', values: defaultValuesFor('none') })

function makeTextModel(axis: Ref<AxisState>): WritableComputedRef<string> {
  return computed<string>({
    get: () => (kindOf(axis.value.param) === 'text' ? axis.value.values.join('\n') : axis.value.values.join(', ')),
    set: (v: string) => {
      const isText = kindOf(axis.value.param) === 'text'
      const parts = v.split(isText ? '\n' : ',').map((s) => s.trim()).filter((s) => s.length > 0)
      axis.value = { ...axis.value, values: uniq(parts) }
    },
  })
}
const xText = makeTextModel(xAxis)
const yText = makeTextModel(yAxis)
const zText = makeTextModel(zAxis)

function onParamChange(axis: Ref<AxisState>, p: string): void {
  const pid = p as AxisParam
  axis.value = { param: pid, values: defaultValuesFor(pid) }
}

/** The windows this axis carries, one raster column or row each. */
function rangesOf(axis: Ref<AxisState>): RangeSelection[] {
  return axis.value.values.map(parseRange)
}
function setRanges(axis: Ref<AxisState>, next: RangeSelection[]): void {
  axis.value = { ...axis.value, values: uniq(next.map(rangeValue)) }
}

/**
 * What comes back from a field row is what is ON, in the order it was ticked —
 * so it is put back into the vocabulary's own order, which is the order the
 * axis reads in and the one the raster's columns then stand in.
 */
function setStrategies(axis: Ref<AxisState>, next: string[]): void {
  const vocab = PARAMS.strategy.vocab || []
  axis.value = { ...axis.value, values: vocab.filter((v) => next.includes(v)) }
}

/**
 * Every parameter stands in every axis list, and the ones the other two axes
 * hold stand there unselectable — the platform's own way with a field that
 * BELONGS in a list and is not reachable here and now.
 *
 * It is also what keeps the list itself still. A `<select>` bound with `:value`
 * loses its value when its options are replaced, and they were replaced every
 * time a neighbouring axis changed: the box then stood empty while the axis it
 * names was carrying a parameter and the raster was drawing it.
 */
interface ParamChoice {
  id: AxisParam
  taken: boolean
}
function choicesFor(self: Ref<AxisState>, a: Ref<AxisState>, b: Ref<AxisState>) {
  return computed<ParamChoice[]>(() =>
    ALL_PARAMS.map((p) => ({
      id: p,
      taken: p !== self.value.param && (p === a.value.param || p === b.value.param),
    })),
  )
}
const availableX = choicesFor(xAxis, yAxis, zAxis)
const availableY = choicesFor(yAxis, xAxis, zAxis)
/** Only the drive-through may carry nothing, and it offers that first. */
const zChoices = choicesFor(zAxis, xAxis, yAxis)
const availableZ = computed<ParamChoice[]>(() => [
  { id: 'none' as AxisParam, taken: false },
  ...zChoices.value,
])

const axisDescriptors = [
  { slot: 'x', ref: xAxis, text: xText, available: availableX, labelKey: 'latentLab.workbench.axisX' },
  { slot: 'y', ref: yAxis, text: yText, available: availableY, labelKey: 'latentLab.workbench.axisY' },
  { slot: 'z', ref: zAxis, text: zText, available: availableZ, labelKey: 'latentLab.workbench.axisZ' },
]

// constants = params on no axis
const axisParams = computed<AxisParam[]>(() => [xAxis.value.param, yAxis.value.param, zAxis.value.param])
const constantParams = computed<ParamId[]>(() => ALL_PARAMS.filter((p) => !axisParams.value.includes(p)))
const constants = ref<Record<ParamId, string>>({
  prompt: DEFAULT_PROMPT,
  alpha: '20',
  cfg: '5.5',
  step: '1-25',
  layer: '0',
  strategy: 'centered_fade',
  seed: '42',
})
const negativePrompt = ref('')
const numSteps = ref(25)

// ---------------------------------------------------------------------------
// The prompt, as Encoder Fusion has it
//
// The field, its ready-made examples, the way in for a dropped picture and the
// short-text line are that instrument's (views/surrealizer.vue) and are read
// from there rather than built a second time
// (docs/ELEMENT_STRUCTURE_REGISTRY.md). What belongs to this
// bench is where the field stands and that it steps aside for the axis.
// ---------------------------------------------------------------------------
const promptText = computed<string>({
  get: () => constants.value.prompt,
  set: (v: string) => {
    constants.value.prompt = v
  },
})
/** Where `prompt` is on an axis, the axis carries the prompts and this is off. */
const hasPromptConstant = computed(() => constantParams.value.includes('prompt'))
/** The rest of the constants, which is what the folded block still holds. */
const constantParamsBelow = computed(() => constantParams.value.filter(p => p !== 'prompt'))

const promptExamples = usePromptPresets()
function applyExample(item: { fill: string[] }) {
  promptText.value = item.fill[0] ?? ''
}

const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
function copyPrompt() {
  copyToClipboard(promptText.value)
}
function pastePrompt() {
  promptText.value = pasteFromClipboard()
}
function clearPrompt() {
  promptText.value = ''
}

const {
  reading: readingPicture,
  readingFailedKey,
  handlePicture,
  dropPicture,
} = usePictureTemplate(promptText)

/**
 * Under 75 tokens T5's 512 positions carry little that CLIP's 77 do not carry
 * as well, and the difference this bench sweeps barely arises. The line names
 * the perspective that
 * makes a text out of a sentence; the button in the field opens it.
 */
const SHORT_PROMPT_TOKENS = 75
const isShortPrompt = computed(() => {
  const words = promptText.value.trim().split(/\s+/).filter(w => w).length
  return words > 0 && Math.round(words * 1.3) < SHORT_PROMPT_TOKENS
})
const storyPresetName = computed(() => t(INTERCEPTION_PRESETS.tellastory.labelKey))

const showPresetOverlay = ref(false)
const isEnriching = ref(false)
/**
 * Streamed, not one silent POST: the interception is a cloud model writing
 * prose, and the edge in front of this server cuts a request whose origin has
 * sent nothing for about 100 seconds.
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
    perspectiveError.value = labErrorText(t, error)
  } finally {
    isEnriching.value = false
  }
}

// --- fusion formulas (display only; mirrors gpu_service _fuse_prompt) ---
interface FusionFormula { core: string; tail: string; note?: string }
const FORMULAS: Record<string, FusionFormula> = {
  legacy: { core: '(1−α)·CLIP + α·T5', tail: 'T5 ×1' },
  dual_alpha: { core: '(1−α)·CLIP + α·T5', tail: '0.15·α·T5' },
  normalized: { core: '(1−α)·CLIP + α·T5', tail: 'T5 · ‖core‖/‖T5‖' },
  centered_fade: {
    core: 'w_C·CLIP + w_T5·T5',
    tail: 'T5 ×1',
    note: 'h=1 · α≤0: w_C=max(1,−α), w_T5=1+α · α>0: w_C=1−α, w_T5=max(1,α)',
  },
  // The core interpolated on the sphere: legacy's operands and legacy's tail, so
  // the strategy axis carries the geometry alone. The arithmetic is slerp_tokens
  // in gpu_service/services/diffusers_backend.py, from the ComfyUI node
  // ai4artsed_conditioning_fusion. Its coefficients differ from token to token
  // with the angle the two readings stand at, so lib/fusionWeights, which
  // answers the Surrealizer's slider with a single pair of numbers, covers the
  // four strategies on that slider and leaves this one to the formula below.
  slerp: {
    core: 'm · slerp(u_CLIP, u_T5; α)',
    tail: 'T5 ×1',
    note:
      'slerp = (sin((1−α)θ)·u_CLIP + sin(αθ)·u_T5)/sinθ, u_X = X/‖X‖ · ' +
      'θ = acos⟨u_CLIP,u_T5⟩ · ∠ = α·θ · ' +
      'm = (1−α)·‖CLIP‖ + α·‖T5‖ · α: 0 = CLIP, 1 = T5',
  },
}
function formulaFor(name: string): FusionFormula {
  return FORMULAS[name] || { core: '—', tail: '—' }
}

/**
 * The three phase names over the window, each at the step its stretch begins at.
 * The fractions 0.32 and 0.68 are Kwon et al.'s DDPM observations carried over
 * to SD3.5 Rectified Flow, which the backend itself records as descriptive; the
 * words therefore stand loosely above a scale that can be set anywhere; the
 * names are not exact either way.
 */
const stepMarks = computed<RangeMark[]>(() => {
  const n = Math.max(1, numSteps.value)
  return [
    { at: 1, label: t('latentLab.workbench.stepMark.composition') },
    { at: Math.round(n * 0.32) + 1, label: t('latentLab.workbench.stepMark.semantics') },
    { at: Math.round(n * 0.68) + 1, label: t('latentLab.workbench.stepMark.detail') },
  ]
})

/**
 * What a stored axis value READS as. The raster's heads, the back of a card and
 * the drive-through all say the same thing, and none of them says `1-8` or
 * `dual_alpha`.
 */
function valueLabel(p: AxisParam, v: string): string {
  if (p === 'strategy') return t(`surrealizer.fusion_${v}`)
  if (p === 'layer') return t('latentLab.workbench.layerFrom', { block: v })
  if (p === 'step') {
    const r = parseRange(v)
    return r.to < r.from
      ? t('latentLab.workbench.windowNone')
      : t('latentLab.workbench.windowSteps', { from: r.from, to: r.to })
  }
  return v
}
const activeStrategies = computed<string[]>(() => {
  const onAxis = [xAxis, yAxis, zAxis].find((ax) => ax.value.param === 'strategy')
  if (onAxis) return onAxis.value.values.length ? onAxis.value.values : ['legacy']
  return [constants.value.strategy || 'legacy']
})

// --- run + results ---
const isRunning = ref(false)
const doneCount = ref(0)
const errorMessage = ref('')

/**
 * One cell as it came back. The picture alone was enough while the raster was a
 * bare `<img>`; the platform's cell is a RUN, so it also holds the id that run
 * was written under and the moment it arrived - the star and the back of the
 * card are addressed by them.
 */
interface CellResult {
  b64: string
  runId: string | null
  madeAt: number
  /** What made it, written down here: a constant changed afterwards would
      otherwise rewrite a finished picture's own account of itself. */
  prompt: string
}
const cells = ref<Record<string, CellResult>>({})

// --- prompt rows + T5 expansion (Part A) ---
const MAX_PROMPTS = 3
const t5ByText = ref<Record<string, string>>({})
const t5Busy = ref<Record<string, boolean>>({})

function t5For(text: string): string {
  return t5ByText.value[text] || ''
}
function setT5(text: string, val: string): void {
  t5ByText.value = { ...t5ByText.value, [text]: val }
}
function setPromptValue(axis: Ref<AxisState>, i: number, val: string): void {
  const next = axis.value.values.slice()
  next[i] = val
  axis.value = { ...axis.value, values: next }
}
function addPromptValue(axis: Ref<AxisState>): void {
  if (axis.value.values.length >= MAX_PROMPTS) return
  axis.value = { ...axis.value, values: [...axis.value.values, ''] }
}
function removePromptValue(axis: Ref<AxisState>, i: number): void {
  if (axis.value.values.length <= 1) return
  axis.value = { ...axis.value, values: axis.value.values.filter((_, j) => j !== i) }
}
async function expandT5(text: string): Promise<void> {
  if (!text.trim() || t5Busy.value[text]) return
  t5Busy.value = { ...t5Busy.value, [text]: true }
  errorMessage.value = ''
  try {
    const baseUrl = apiBase()
    const resp = await axios.post(`${baseUrl}/api/fusion_workbench/expand_t5`, { prompt: text })
    if (resp.data?.success && resp.data.t5_expansion) {
      t5ByText.value = { ...t5ByText.value, [text]: resp.data.t5_expansion as string }
    } else {
      errorMessage.value = resp.data?.error || t('latentLab.workbench.t5ExpandFailed')
    }
  } catch (e) {
    errorMessage.value = (e as Error).message || t('latentLab.workbench.t5ExpandFailed')
  } finally {
    const nb = { ...t5Busy.value }
    delete nb[text]
    t5Busy.value = nb
  }
}
const zIndex = ref(0)

const currentZ = computed<string>(() => zAxis.value.values[Math.min(zIndex.value, zAxis.value.values.length - 1)] ?? '')
const hasResults = computed<boolean>(() => Object.keys(cells.value).length > 0)

/** The places on the drive-through, one per value of Z. */
const zMarks = computed<SliderMark[]>(() => {
  const vals = zAxis.value.values
  if (vals.length < 2) return []
  return vals.map((v, i) => ({
    value: trunc(valueLabel(zAxis.value.param, v), 8),
    pct: (i / (vals.length - 1)) * 100,
  }))
})

/** Ready to sweep: a plan with cells in it, and nothing out. */
const canRun = computed<boolean>(() => !isRunning.value && cellPlan.value.length > 0)

/** A separator no axis value can contain, so a key is never ambiguous. */
const SEP = String.fromCharCode(1)
function cellKeyOf(xv: string, yv: string, zv: string): string {
  return `${xv}${SEP}${yv}${SEP}${zv}`
}
function cellAt(xv: string, yv: string): CellResult | null {
  return cells.value[cellKeyOf(xv, yv, currentZ.value)] || null
}
function cellImg(xv: string, yv: string): string {
  return cellAt(xv, yv)?.b64 || ''
}
function cellUrl(xv: string, yv: string): string {
  const b64 = cellImg(xv, yv)
  return b64 ? imgSrc(b64) : ''
}
function cellRunId(xv: string, yv: string): string | null {
  return cellAt(xv, yv)?.runId ?? null
}
function cellMadeAt(xv: string, yv: string): number {
  return cellAt(xv, yv)?.madeAt ?? 0
}
/** What made this cell, as it stood when the cell was made. */
function cellPrompt(xv: string, yv: string): string {
  return cellAt(xv, yv)?.prompt ?? ''
}
/** Where this cell stands on the three axes, for the back of its card. */
function cellFacts(xv: string, yv: string): string[] {
  const facts = [
    `${paramLabel(xAxis.value.param)} = ${trunc(valueLabel(xAxis.value.param, xv), 24)}`,
    `${paramLabel(yAxis.value.param)} = ${trunc(valueLabel(yAxis.value.param, yv), 24)}`,
  ]
  if (zAxis.value.param !== 'none') {
    facts.push(`${paramLabel(zAxis.value.param)} = ${trunc(valueLabel(zAxis.value.param, currentZ.value), 24)}`)
  }
  return facts
}
function isFavorited(runId: string | null): boolean {
  return runId ? favoritesStore.isFavorited(runId) : false
}
async function toggleFavorite(runId: string | null): Promise<void> {
  if (!runId) return
  await favoritesStore.toggleFavorite(runId, 'image', deviceId, 'anonymous', 'fusion-workbench')
}
/** The picture of one cell, under the name that leads back to its run. */
function downloadCell(xv: string, yv: string): void {
  const b64 = cellImg(xv, yv)
  if (!b64) return
  void downloadMedia(imgSrc(b64), buildFilename(xv, yv, currentZ.value))
}
function imgSrc(b64: string): string {
  return `data:image/png;base64,${b64}`
}
function trunc(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}

interface Cell {
  xv: string
  yv: string
  zv: string
  key: string
}
const cellPlan = computed<Cell[]>(() => {
  const plan: Cell[] = []
  for (const zv of zAxis.value.values) {
    for (const yv of yAxis.value.values) {
      for (const xv of xAxis.value.values) {
        plan.push({ xv, yv, zv, key: cellKeyOf(xv, yv, zv) })
      }
    }
  }
  return plan
})

/**
 * The raster caps its rows at the measured width of a picture column, so the
 * height it cannot use stands as ONE strip below it - see
 * composables/useGridCellWidth.ts. Re-measured when a column or a row is added.
 */
const { gridEl, cellPx } = useGridCellWidth(() => [xAxis.value.values, yAxis.value.values])

// resolve one logical parameter for a cell
function resolveParam(id: ParamId, xv: string, yv: string, zv: string): string {
  if (xAxis.value.param === id) return xv
  if (yAxis.value.param === id) return yv
  if (zAxis.value.param === id) return zv
  return constants.value[id]
}
/**
 * The window in fractions of the run, which is what the hook compares against
 * at every step (`frac = step / steps`). Both step numbers are included, so a
 * window of 9 to 17 out of 25 goes out as 0.32 to 0.68 — the same two numbers
 * the named phase carried, now reachable at any other pair. A window whose end
 * lies before its start injects nowhere and says so as an empty span.
 */
function stepWindowPayload(v: string, steps: number): [number, number] {
  const r = parseRange(v)
  const n = Math.max(1, steps)
  if (r.to < r.from || r.from > n) return [0, 0]
  return [Math.max(0, (r.from - 1) / n), Math.min(1, r.to / n)]
}

/**
 * A window is written in STEP NUMBERS, so a changed step count moves what it
 * covers. Lowering the count to 10 left a window of 18 to 25 standing: it ran
 * past the end of the run, injected nothing at all, and its heading went on
 * saying „Steps 18–25". Anything past the new end is brought back to it, and a
 * window that now begins past the end becomes one that injects nowhere and says
 * so.
 */
watch(numSteps, (n) => {
  const held = Math.max(1, n)
  const fit = (v: string): string => {
    const r = parseRange(v)
    if (r.from > held) return rangeValue({ from: 1, to: 0 })
    return rangeValue({ from: r.from, to: Math.min(r.to, held) })
  }
  for (const ax of [xAxis, yAxis, zAxis]) {
    if (ax.value.param !== 'step') continue
    ax.value = { ...ax.value, values: uniq(ax.value.values.map(fit)) }
  }
  constants.value = { ...constants.value, step: fit(constants.value.step) }
})
function buildBody(cell: Cell): Record<string, unknown> {
  const p = (id: ParamId) => resolveParam(id, cell.xv, cell.yv, cell.zv)
  const promptText = p('prompt')
  const expansion = (t5ByText.value[promptText] || '').trim()
  const body: Record<string, unknown> = {
    prompt: promptText,
    negative_prompt: negativePrompt.value,
    fusion_strategy: p('strategy') || 'legacy',
    alpha_factor: parseFloat(p('alpha')) || 0,
    cfg_scale: parseFloat(p('cfg')) || 5.5,
    seed: Number.isNaN(parseInt(p('seed'), 10)) ? 42 : parseInt(p('seed'), 10),
    steps: numSteps.value,
    width: 1024,
    height: 1024,
    step_window: stepWindowPayload(p('step'), numSteps.value),
    // Sent as it stands. A field that cannot be read as a block index used to
    // become block 0 here, and the sweep then ran the strongest intervention
    // there is under the label the reader had typed; now the card answers with
    // what is wrong with it.
    layer_entry: p('layer').trim(),
  }
  if (expansion) body.t5_prompt = promptText + ' ' + expansion
  return body
}

async function genCell(cell: Cell): Promise<void> {
  const baseUrl = apiBase()
  const body = buildBody(cell)
  // Streamed, not awaited in one silent POST: a cell stands in the plant-wide
  // GPU queue before it renders, and the edge in front of the server cuts a
  // request whose origin has sent nothing for about 100 seconds - which ended
  // the whole sweep on a cell the card had already made. It resolves and throws
  // exactly as the axios call it replaces, so runSweep reads a failure the same
  // way it always has.
  const resp = await postStreamedRun('/api/fusion_workbench/generate', body, { baseUrl })
  if (!resp.data?.success || !resp.data.image_base64) {
    throw new Error(resp.data?.error || 'generation failed')
  }
  const b64 = resp.data.image_base64 as string
  // Written down first, so the cell that appears already carries the run it is.
  const runId = await labRecord({
    parameters: {
      ...body,
      axes: {
        x: xAxis.value.param,
        y: yAxis.value.param,
        z: zAxis.value.param === 'none' ? null : zAxis.value.param,
      },
      cell: { x: cell.xv, y: cell.yv, z: zAxis.value.param === 'none' ? null : cell.zv },
    },
    outputs: [{ type: 'image', format: 'png', dataBase64: b64 }],
  })
  cells.value = {
    ...cells.value,
    [cell.key]: {
      b64,
      runId: runId ?? null,
      madeAt: Date.now(),
      prompt: String(body.prompt ?? ''),
    },
  }
}

async function runSweep(): Promise<void> {
  if (isRunning.value || cellPlan.value.length === 0) return
  isRunning.value = true
  errorMessage.value = ''
  doneCount.value = 0
  cells.value = {}
  zIndex.value = 0
  const plan = cellPlan.value
  try {
    for (const cell of plan) {
      await genCell(cell)
      doneCount.value++
    }
  } catch (err: unknown) {
    // A refusal is not a fault, and it says which kind it was.
    const key = refusalKeyOf(err)
    errorMessage.value = key
      ? t(key)
      : labErrorText(t, err)
  } finally {
    isRunning.value = false
  }
}

function slugForFile(id: AxisParam, v: string): string {
  if (id === 'prompt') return v.toLowerCase().replace(/[^a-z0-9]+/g, '').slice(0, 24) || 'x'
  return v.replace(/[^a-zA-Z0-9.-]+/g, '') || 'x'
}
function buildFilename(xv: string, yv: string, zv: string): string {
  // The run this file came out of, so the name leads back to the folder that
  // holds it; the sitting only while no run has been written yet.
  const id = (lastRunId.value || sessionId.value || 'run')
    .replace(/^(run|lab)_/, '')
    .replace(/[^a-zA-Z0-9]+/g, '_')
  const axes: Array<[AxisParam, string]> = [
    [xAxis.value.param, xv],
    [yAxis.value.param, yv],
    [zAxis.value.param, zv],
  ]
  const parts = axes
    .filter(([pid]) => pid !== 'none')
    .map(([pid, val]) => `${pid}${slugForFile(pid, val)}`)
  return `surr_${id}_${parts.join('_')}.png`
}
const pageContextStore = usePageContextStore()

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'fusion_workbench',
  pageDescription:
    'Encoder Fusion Workbench — die siebte Kachel im Diffusion Lab. Ein ' +
    'Vergleichsinstrument, kein Generator: man bestimmt, welcher Parameter ' +
    'entlang welcher der drei Achsen variiert, und die Läufe stehen ' +
    'gegeneinander. Variieren können der Prompt, das Fusionsgewicht (α), CFG, ' +
    'der Seed, die Fusionsstrategie (legacy, dual_alpha, normalized, ' +
    'centered_fade, slerp) sowie zwei Bandauswahlen: in welcher Phase der ' +
    'Entrauschung und in welchem Tiefenband des Netzes die Fusion wirkt. ' +
    'Variiert werden die Parameter der Encoder Fusion; das Instrument selbst ' +
    'liegt auf der Kachel daneben.',
  pageContent: {
    inputText: constants.value.prompt,
  },
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
/* The page skeleton, the stage proportion, the raster and the square surface
   are shared and stand in assets/flow-stage.css and
   assets/instrument-surface.css. What is here is what this instrument alone
   needs: an axis with its values, and the formula that says what the pictures
   are showing. */

/* --- one axis ------------------------------------------------------------- */

.fw-axis {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.fw-prompt {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fw-prompt-main {
  display: flex;
  align-items: flex-start;
  gap: 5px;
}

.fw-prompt-text { flex: 1 1 auto; }

.fw-t5 { opacity: 0.8; }
/* The T5 box over the axes is a direct child of the preparing column, and that
   column is a flex column: as soon as it overflows, a shrinkable child is
   pressed to a sliver — this one to 13 px of the 47 its two rows need, so its
   text was unreadable. The other two sit in the axis row and in the folded
   block, where nothing shrinks them. */
.fw-t5-lead { flex: none; }

.fw-remove {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.4);
  border-radius: 50%;
  cursor: pointer;
  font-size: 0.75rem;
  line-height: 1;
}
.fw-remove:hover { color: #ef5350; border-color: rgba(244, 67, 54, 0.3); }
.fw-remove:disabled { opacity: 0.4; cursor: not-allowed; }

/* The small button of this surface: T5 expansion, one more prompt. */
.fw-mini {
  align-self: flex-start;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--surface-4);
  border-radius: 6px;
  background: var(--surface-2);
  color: rgba(255, 255, 255, 0.6);
  font-family: inherit;
  font-size: var(--flow-fs-hint);
  text-decoration: none;
  cursor: pointer;
}
.fw-mini:hover:not(:disabled) { color: rgba(255, 255, 255, 0.9); border-color: rgba(255, 255, 255, 0.3); }
.fw-mini:disabled { opacity: 0.4; cursor: not-allowed; }

.fw-add { border-style: dashed; }

/* --- what the pictures are showing ---------------------------------------- */

.fw-formula {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fw-formula-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.fw-formula-name {
  font-size: var(--flow-fs-sub);
  color: rgba(255, 255, 255, 0.75);
}

.fw-code {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: var(--flow-fs-hint);
  color: rgba(255, 255, 255, 0.6);
  overflow-wrap: anywhere;
}

.fw-code-note { color: rgba(255, 255, 255, 0.4); }

.fw-legend {
  margin: 0;
  font-size: var(--flow-fs-hint);
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.4);
}

/* --- the raster ----------------------------------------------------------- */

/* The corner names the two axes the raster is read along; it is not one of the
   cases, so it stands as quietly as a row name. */
.fw-corner {
  font-size: var(--flow-fs-hint);
  color: rgba(255, 255, 255, 0.45);
  text-align: right;
  white-space: nowrap;
}

/* --- the run's own settings ------------------------------------------------ */

/* The klappe of the instruments is the platform's and stands in
   assets/flow-stage.css (`details.advanced-settings` + `.settings-grid`). */

/* A constant that is written takes the whole width of the klappe; the numbers
   stand beside each other. */
.fw-wide { flex: 1 1 100%; }

/* What `.settings-grid > label` gives a label, for the two constants that hold
   several controls and therefore cannot be one (assets/flow-stage.css). */
.fw-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.75rem;
}

/* The klappe is the platform's (assets/flow-stage.css). What stays here is what
   only this surface needs: its settings are WRITTEN into, in textareas, and a
   textarea keeps the browser's own face and its own resize grip unless it is
   told otherwise. */
.setting-input {
  font-family: inherit;
  resize: vertical;
}

/* Narrow windows: the two surfaces stand under each other and the page scrolls
   in the work area, as every instrument of this frame does. */
@media (max-width: 640px) {
  .lab-stage { flex: 0 0 auto; }
  .lab-work { grid-template-columns: 1fr; }
}
</style>
