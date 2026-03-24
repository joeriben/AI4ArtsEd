<template>
  <div class="crossmodal-lab">
    <!-- Header -->
    <div class="page-header">
      <h2 class="page-title">
        {{ t('latentLab.crossmodal.headerTitle') }}
      </h2>
      <p class="page-subtitle">{{ t('latentLab.crossmodal.headerSubtitle') }}</p>
    </div>

    <!-- Tab Navigation -->
    <div class="tab-nav">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        <span class="tab-label">{{ t(`latentLab.crossmodal.tabs.${tab.id}.label`) }}</span>
        <span class="tab-short">{{ t(`latentLab.crossmodal.tabs.${tab.id}.short`) }}</span>
      </button>
    </div>

    <!-- ===== Tab 1: Latent Audio Synth ===== -->
    <div v-if="activeTab === 'synth'" class="tab-panel">
      <h3>{{ t('latentLab.crossmodal.tabs.synth.title') }}</h3>
      <p class="tab-description">{{ t('latentLab.crossmodal.tabs.synth.description') }}</p>

      <details class="explanation-details" :open="synthExplainOpen" @toggle="onSynthExplainToggle">
        <summary>{{ t('latentLab.crossmodal.explanationToggle') }}</summary>
        <div class="explanation-body">
          <div class="explanation-section">
            <h4>{{ t('latentLab.crossmodal.synth.explainWhatTitle') }}</h4>
            <p>{{ t('latentLab.crossmodal.synth.explainWhatText') }}</p>
          </div>
          <div class="explanation-section">
            <h4>{{ t('latentLab.crossmodal.synth.explainHowTitle') }}</h4>
            <p>{{ t('latentLab.crossmodal.synth.explainHowText') }}</p>
          </div>
        </div>
      </details>

      <!-- Sticky prompt + generate area -->
      <div class="synth-sticky-top">
        <!-- Prompt A -->
        <MediaInputBox
          icon="💡"
          :label="t('latentLab.crossmodal.synth.promptA')"
          :placeholder="t('latentLab.crossmodal.synth.promptAPlaceholder')"
          :value="synth.promptA"
          @update:value="synth.promptA = $event"
          :rows="2"
          :isEmpty="!synth.promptA"
          :isFilled="!!synth.promptA"
          @copy="copySynthPromptA"
          @paste="pasteSynthPromptA"
          @clear="clearSynthPromptA"
        />

        <!-- Prompt B (optional) -->
        <MediaInputBox
          icon="💡"
          :label="t('latentLab.crossmodal.synth.promptB')"
          :placeholder="t('latentLab.crossmodal.synth.promptBPlaceholder')"
          :value="synth.promptB"
          @update:value="synth.promptB = $event"
          :rows="2"
          :isEmpty="!synth.promptB"
          :isFilled="!!synth.promptB"
          @copy="copySynthPromptB"
          @paste="pasteSynthPromptB"
          @clear="clearSynthPromptB"
        />

        <div class="action-row">
          <button class="generate-btn" :disabled="!synth.promptA || generating" @click="runSynth">
            {{ generating ? t('latentLab.crossmodal.generating') : t('latentLab.crossmodal.generate') }}
          </button>
        </div>
      </div>

      <!-- Sliders -->
      <div class="slider-group synth-slider-group">
        <div class="slider-item">
          <div class="slider-header">
            <label>{{ t('latentLab.crossmodal.synth.alpha') }}</label>
            <span class="slider-value">{{ synth.alpha.toFixed(2) }}</span>
          </div>
          <input type="range" v-model.number="synth.alpha" min="-2" max="2" step="0.01" />
        </div>

        <div class="slider-item">
          <div class="slider-header">
            <label>{{ t('latentLab.crossmodal.synth.magnitude') }}</label>
            <span class="slider-value">{{ synth.magnitude.toFixed(2) }}</span>
          </div>
          <input type="range" v-model.number="synth.magnitude" min="0.1" max="5" step="0.1" />
          <span class="slider-hint">{{ t('latentLab.crossmodal.synth.magnitudeHint') }}</span>
        </div>

        <div class="slider-item">
          <div class="slider-header">
            <label>{{ t('latentLab.crossmodal.synth.noise') }}</label>
            <span class="slider-value">{{ synth.noise.toFixed(2) }}</span>
          </div>
          <input type="range" v-model.number="synth.noise" min="0" max="1" step="0.05" />
          <span class="slider-hint">{{ t('latentLab.crossmodal.synth.noiseHint') }}</span>
        </div>
      </div>

      <!-- Params row -->
      <div class="params-row">
        <div class="param param-wide">
          <div class="slider-header">
            <label>{{ t('latentLab.crossmodal.synth.duration') }}</label>
            <span class="slider-value">{{ synth.duration.toFixed(1) }}s</span>
          </div>
          <input type="range" :value="durationToSlider(synth.duration)" min="0" max="1" step="0.002" @input="synth.duration = sliderToDuration(Number(($event.target as HTMLInputElement).value))" />
          <span class="param-hint">{{ t('latentLab.crossmodal.synth.durationHint') }}</span>
        </div>
        <div class="param param-wide">
          <div class="slider-header">
            <label>{{ t('latentLab.crossmodal.synth.startPosition') }}</label>
            <span class="slider-value">{{ Math.round(synth.startPosition * 100) }}%</span>
          </div>
          <input type="range" v-model.number="synth.startPosition" min="0" max="0.95" step="0.05" />
          <span class="param-hint">{{ t('latentLab.crossmodal.synth.startPositionHint') }}</span>
        </div>
        <div class="param param-narrow">
          <label>{{ t('latentLab.crossmodal.synth.steps') }}</label>
          <input v-model.number="synth.steps" type="number" min="5" max="100" step="5" />
          <span class="param-hint">{{ t('latentLab.crossmodal.synth.stepsHint') }}</span>
        </div>
        <div class="param param-narrow">
          <label>{{ t('latentLab.crossmodal.synth.cfg') }}</label>
          <input v-model.number="synth.cfg" type="number" min="1" max="15" step="0.5" />
          <span class="param-hint">{{ t('latentLab.crossmodal.synth.cfgHint') }}</span>
        </div>
        <div class="param param-wide">
          <label>{{ t('latentLab.crossmodal.seed') }}</label>
          <input v-model.number="synth.seed" type="number" />
          <span class="param-hint">{{ t('latentLab.crossmodal.synth.seedHint') }}</span>
        </div>
      </div>

      <!-- Semantic Axes (collapsible, modifies prompt embedding) -->
      <details v-if="availableAxes.length > 0" class="semantic-axes-section lab-section" :open="semanticAxesOpen" @toggle="onSemanticAxesToggle">
        <summary>{{ t('latentLab.crossmodal.synth.semanticAxes.modeToggle') }}</summary>
        <div class="semantic-axes-content">
          <div class="semantic-axes-slots">
            <div
              v-for="(slot, idx) in axisSlots"
              :key="idx"
              class="axis-slot"
            >
              <span class="axis-color-dot" :style="{ background: axisColors[idx] }" />
              <select
                :value="slot.axis"
                class="axis-select"
                @change="onAxisSelectChange(idx, ($event.target as HTMLSelectElement).value)"
              >
                <option value="">{{ t('latentLab.crossmodal.synth.semanticAxes.slotNone') }}</option>
                <optgroup :label="t('latentLab.crossmodal.synth.semanticAxes.groupSemantic')">
                  <option
                    v-for="ax in semanticAxisList"
                    :key="ax.name"
                    :value="ax.name"
                  >
                    {{ ax.pole_b }} ↔ {{ ax.pole_a }}
                    <template v-if="ax.d !== null"> (d={{ ax.d }})</template>
                    <template v-if="ax.level === 'experimental'"> *</template>
                  </option>
                </optgroup>
                <optgroup v-if="pcaAxisList.length" :label="t('latentLab.crossmodal.synth.semanticAxes.groupPCA')">
                  <option
                    v-for="ax in pcaAxisList"
                    :key="ax.name"
                    :value="ax.name"
                  >
                    {{ ax.pole_b }} ↔ {{ ax.pole_a }}
                  </option>
                </optgroup>
              </select>
              <div v-if="slot.axis" class="axis-slider-row">
                <span class="axis-pole-label pole-b" :title="getAxisMeta(slot.axis)?.pole_b">{{ getAxisMeta(slot.axis)?.pole_b }}</span>
                <input
                  type="range"
                  :value="axisValueToSlider(slot.value)"
                  min="0"
                  max="1"
                  step="0.002"
                  class="axis-range"
                  :style="{ accentColor: axisColors[idx] }"
                  @input="slot.value = sliderToAxisValue(Number(($event.target as HTMLInputElement).value))"
                />
                <span class="axis-pole-label pole-a" :title="getAxisMeta(slot.axis)?.pole_a">{{ getAxisMeta(slot.axis)?.pole_a }}</span>
                <span class="axis-value" :style="{ color: axisColors[idx] }">{{ slot.value.toFixed(2) }}</span>
              </div>
            </div>
          </div>

          <div class="section-action-bar">
            <button class="dim-btn dim-btn-generate" :disabled="generating" @click="runSynth">
              {{ t('latentLab.crossmodal.synth.dimensions.applyAndGenerate') }}
            </button>
            <button class="dim-btn dim-btn-reset" @click="resetAxesToCenter">
              {{ t('latentLab.crossmodal.synth.semanticAxes.resetAll') }}
            </button>
          </div>
        </div>
      </details>

      <!-- Dimension Explorer Section (open by default) -->
      <details class="dim-explorer-section lab-section" :open="dimExplorerOpen" @toggle="onDimExplorerToggle">
        <summary>{{ t('latentLab.crossmodal.synth.dimensions.section') }}</summary>
        <div class="dim-explorer-content">
          <!-- Mode toggle: Relative / Absolute -->
          <div class="section-toggle dim-mode-toggle">
            <label class="inline-toggle" :class="{ active: spectralMode === 'relative' }">
              <input type="radio" value="relative" :checked="spectralMode === 'relative'" @change="onSpectralModeChange('relative')" :disabled="!hasABReference" />
              {{ t('latentLab.crossmodal.synth.dimensions.modeRelative') }}
            </label>
            <label class="inline-toggle" :class="{ active: spectralMode === 'absolute' }">
              <input type="radio" value="absolute" :checked="spectralMode === 'absolute'" @change="onSpectralModeChange('absolute')" />
              {{ t('latentLab.crossmodal.synth.dimensions.modeAbsolute') }}
            </label>
          </div>
          <p class="dim-hint">{{ spectralMode === 'relative' && hasABReference
            ? t('latentLab.crossmodal.synth.dimensions.hintRelative')
            : t('latentLab.crossmodal.synth.dimensions.hint') }}</p>

          <!-- Spectral Strip Canvas -->
          <div class="spectral-strip-container">
            <canvas
              ref="spectralCanvasRef"
              class="spectral-canvas"
              @mousedown="onSpectralMouseDown"
              @mousemove="onSpectralMouseMove"
              @mouseup="onSpectralMouseUp"
              @mouseleave="onSpectralMouseUp"
              @contextmenu="onSpectralContextMenu"
              @touchstart="onSpectralTouchStart"
              @touchmove="onSpectralTouchMove"
              @touchend="onSpectralTouchEnd"
            />
            <div v-if="!embeddingStats?.all_activations" class="spectral-empty">
              {{ t('latentLab.crossmodal.synth.dimensions.hint') }}
            </div>
          </div>

          <!-- Hover info + sort mode -->
          <div class="dim-info-row">
            <span v-if="hoveredDim" class="dim-hover-info">
              d{{ hoveredDim.dim }}:
              {{ t('latentLab.crossmodal.synth.dimensions.hoverActivation') }}={{ hoveredDim.activation.toFixed(4) }}
              <template v-if="spectralMode === 'relative' && hasABReference">
                {{ t('latentLab.crossmodal.synth.dimensions.hoverMix') }}={{ (hoveredDim.offset * 100).toFixed(0) }}%
              </template>
              <template v-else>
                {{ t('latentLab.crossmodal.synth.dimensions.hoverOffset') }}={{ hoveredDim.offset.toFixed(2) }}
              </template>
            </span>
            <span v-if="embeddingStats?.sort_mode" class="dim-sort-mode">
              {{ embeddingStats.sort_mode === 'diff'
                ? t('latentLab.crossmodal.synth.dimensions.sortDiff')
                : t('latentLab.crossmodal.synth.dimensions.sortMagnitude') }}
            </span>
          </div>

          <!-- Controls Row (always visible, disabled when inactive) -->
          <div class="section-action-bar">
            <button
              class="dim-btn dim-btn-generate"
              :disabled="generating || activeOffsetCount === 0"
              @click="runSynth"
            >
              {{ t('latentLab.crossmodal.synth.dimensions.applyAndGenerate') }}
            </button>
            <button class="dim-btn dim-btn-undo" :disabled="!canUndo" @click="undo" :title="t('latentLab.crossmodal.synth.dimensions.undo')">
              <img src="@/assets/icons/undo_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg" alt="Undo" class="action-icon" />
            </button>
            <button class="dim-btn dim-btn-undo" :disabled="!canRedo" @click="redo" :title="t('latentLab.crossmodal.synth.dimensions.redo')">
              <img src="@/assets/icons/redo_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg" alt="Redo" class="action-icon" />
            </button>
            <span v-if="activeOffsetCount > 0" class="dim-offset-status">
              {{ t('latentLab.crossmodal.synth.dimensions.activeOffsets', { count: activeOffsetCount }) }}
            </span>
            <button class="dim-btn dim-btn-reset" :disabled="activeOffsetCount === 0" @click="resetAllOffsets">
              {{ t('latentLab.crossmodal.synth.dimensions.resetAll') }}
            </button>
          </div>
        </div>
      </details>

      <!-- Looper Widget (collapsible, disabled when no audio) -->
      <details class="looper-widget lab-section" :open="looperOpen" @toggle="onLooperToggle"
               :class="{ disabled: !looper.hasAudio.value }">
        <summary>{{ t('latentLab.crossmodal.synth.looperSection') }}</summary>
        <div class="looper-status">
          <span class="looper-indicator" :class="{ pulsing: transport === 'playing' }" />
          <span class="looper-label">
            {{ transport === 'playing'
              ? (engineMode === 'wavetable'
                ? t('latentLab.crossmodal.synth.oscillating')
                : (sequencer.isPlaying.value
                  ? t('latentLab.crossmodal.synth.sequencing')
                  : (loopMode !== 'oneshot' ? t('latentLab.crossmodal.synth.looping') : t('latentLab.crossmodal.synth.playing'))))
              : (transport === 'generating' ? t('latentLab.crossmodal.generating') : t('latentLab.crossmodal.synth.stopped')) }}
          </span>
          <span v-if="looper.bufferDuration.value > 0" class="looper-duration">
            {{ looper.bufferDuration.value.toFixed(2) }}s
          </span>
        </div>
        <!-- Waveform + loop region (always visible when audio loaded) -->
        <div v-if="engineMode === 'looper'" class="loop-interval">
          <div class="slider-header">
            <label>{{ t('latentLab.crossmodal.synth.loopInterval') }}</label>
            <span class="slider-value">
              {{ (looper.loopStartFrac.value * looper.bufferDuration.value).toFixed(3) }}s
              – {{ (looper.loopEndFrac.value * looper.bufferDuration.value).toFixed(3) }}s
            </span>
          </div>
          <div class="waveform-loop-container">
            <canvas ref="waveformCanvasRef" class="waveform-canvas" />
            <div class="dual-range">
              <input
                type="range"
                :value="looper.loopStartFrac.value"
                min="0"
                max="1"
                step="0.001"
                class="range-start"
                :disabled="!looper.hasAudio.value"
                @input="onLoopStartInput"
              />
              <input
                type="range"
                :value="looper.loopEndFrac.value"
                min="0"
                max="1"
                step="0.001"
                class="range-end"
                :disabled="!looper.hasAudio.value"
                @input="onLoopEndInput"
              />
            </div>
          </div>
        </div>

        <!-- ═══════ BOX 1: ENGINE ═══════ -->
        <div class="synth-box">
          <!-- Engine Switch: Looper vs Wavetable -->
          <div class="section-toggle engine-switch-row">
            <label class="inline-toggle" :class="{ active: engineMode === 'looper' }">
              <input type="radio" value="looper" :checked="engineMode === 'looper'" @change="setEngineMode('looper')" />
              {{ t('latentLab.crossmodal.synth.engineLooper') }}
            </label>
            <label class="inline-toggle" :class="{ active: engineMode === 'wavetable' }" :title="!wavetableOsc.hasFrames.value ? 'Generate first' : ''">
              <input type="radio" value="wavetable" :checked="engineMode === 'wavetable'" :disabled="!wavetableOsc.hasFrames.value" @change="setEngineMode('wavetable')" />
              {{ t('latentLab.crossmodal.synth.engineWavetable') }}
              <span v-if="wavetableOsc.hasFrames.value" class="frame-badge">{{ wavetableOsc.frameCount.value }}</span>
            </label>
          </div>

          <!-- Looper options -->
          <div v-if="engineMode === 'looper'" class="looper-options">
            <div class="loop-mode-row">
              <label class="inline-toggle" :class="{ active: loopMode === 'oneshot' }">
                <input type="radio" value="oneshot" :checked="loopMode === 'oneshot'" @change="setLoopMode('oneshot')" />
                {{ t('latentLab.crossmodal.synth.loopOff') }}
              </label>
              <label class="inline-toggle" :class="{ active: loopMode === 'loop' }">
                <input type="radio" value="loop" :checked="loopMode === 'loop'" @change="setLoopMode('loop')" />
                {{ t('latentLab.crossmodal.synth.loopToggle') }}
              </label>
              <label class="inline-toggle" :class="{ active: loopMode === 'pingpong' }">
                <input type="radio" value="pingpong" :checked="loopMode === 'pingpong'" @change="setLoopMode('pingpong')" />
                {{ t('latentLab.crossmodal.synth.loopPingPong') }}
              </label>
            </div>
            <div v-if="loopMode !== 'oneshot'" class="loop-options">
              <label class="inline-toggle">
                <input type="checkbox" :checked="looper.loopOptimize.value" :disabled="!looper.hasAudio.value" @change="onOptimizeChange" />
                {{ t('latentLab.crossmodal.synth.loopOptimize') }}
              </label>
              <span v-if="looper.loopOptimize.value" class="optimized-hint">
                → {{ (looper.optimizedEndFrac.value * looper.bufferDuration.value).toFixed(3) }}s
              </span>
              <span class="slider-hint">{{ t('latentLab.crossmodal.synth.loopIntervalHint') }}</span>
            </div>
            <!-- Crossfade -->
            <div v-if="!sequencerOn" class="transpose-row">
              <label>{{ t('latentLab.crossmodal.synth.crossfade') }}</label>
              <input type="range" :value="looper.crossfadeMs.value" min="0" max="500" step="10" :disabled="!looper.hasAudio.value" @input="onCrossfadeInput" />
              <span class="transpose-value">{{ looper.crossfadeMs.value }}ms</span>
              <span class="param-hint">{{ t('latentLab.crossmodal.synth.crossfadeHint') }}</span>
            </div>
          </div>

          <!-- Wavetable controls -->
          <div v-if="wavetableOn" class="wavetable-controls">
            <div class="wavetable-mode-row">
              <label class="inline-toggle" :class="{ active: wtMode === 'extract' }" @click="wtMode = 'extract'">
                <input type="radio" value="extract" :checked="wtMode === 'extract'" />
                {{ t('latentLab.crossmodal.synth.wavetableExtract') }}
              </label>
              <label class="inline-toggle" :class="{ active: wtMode === 'semantic' }" @click="wtMode = 'semantic'">
                <input type="radio" value="semantic" :checked="wtMode === 'semantic'" />
                {{ t('latentLab.crossmodal.synth.wavetableSemantic') }}
              </label>
            </div>
            <div v-if="wtMode === 'semantic'" class="wt-build-section">
              <div class="wt-build-row">
                <select v-model="wtBuildAxis" class="wt-axis-select">
                  <option value="">{{ t('latentLab.crossmodal.synth.wtSelectAxis') }}</option>
                  <optgroup :label="t('latentLab.crossmodal.synth.semanticAxes.groupSemantic')">
                    <option v-for="ax in semanticAxisList" :key="ax.name" :value="ax.name">
                      {{ ax.pole_b }} ↔ {{ ax.pole_a }}
                    </option>
                  </optgroup>
                  <optgroup v-if="pcaAxisList.length" :label="t('latentLab.crossmodal.synth.semanticAxes.groupPCA')">
                    <option v-for="ax in pcaAxisList" :key="ax.name" :value="ax.name">
                      {{ ax.pole_b }} ↔ {{ ax.pole_a }}
                    </option>
                  </optgroup>
                </select>
                <select v-model.number="wtBuildFrameCount" class="wt-frame-select">
                  <option :value="8">8</option>
                  <option :value="16">16</option>
                  <option :value="32">32</option>
                </select>
                <button class="wt-build-btn" :disabled="!wtBuildAxis || wtBuilding" @click="buildSemanticWavetable">
                  {{ wtBuilding ? t('latentLab.crossmodal.synth.wtBuilding') : t('latentLab.crossmodal.synth.wtBuild') }}
                </button>
              </div>
              <div v-if="wtBuilding" class="wt-progress">
                <div class="wt-progress-bar" :style="{ width: `${wtBuildProgress}%` }" />
                <span class="wt-progress-label">{{ wtBuildProgressCurrent }}/{{ wtBuildFrameCount }}</span>
              </div>
              <span v-if="wtBuildAxis" class="slider-hint">{{ t('latentLab.crossmodal.synth.wtBuildHint') }}</span>
            </div>
            <!-- Scan position with range brackets -->
            <div class="slider-header">
              <label>{{ t('latentLab.crossmodal.synth.wavetableScan') }}</label>
              <span class="slider-value">{{ scanDisplayFrame }} / {{ wavetableOsc.frameCount.value }}</span>
            </div>
            <div class="wt-scan-track" ref="scanTrackEl">
              <div class="wt-range-band" :style="rangeBandStyle" />
              <div class="wt-bracket wt-bracket-start" :style="{ left: `${rangeStartPct}%` }" @pointerdown.prevent="startBracketDrag('start', $event)" />
              <div class="wt-bracket wt-bracket-end" :style="{ left: `${rangeEndPct}%` }" @pointerdown.prevent="startBracketDrag('end', $event)" />
              <input type="range" :value="wavetableScan" min="0" max="1" step="0.01" @input="onScanInput" />
            </div>
            <span class="slider-hint">{{ t('latentLab.crossmodal.synth.wavetableScanHint') }}</span>
            <label class="inline-toggle" :class="{ active: wtInterpolate }">
              <input type="checkbox" :checked="wtInterpolate" @change="onWtInterpolateChange" />
              {{ t('latentLab.crossmodal.synth.wtInterpolate') }}
            </label>
          </div>

          <!-- Normalize + Peak -->
          <div class="normalize-row">
            <label class="normalize-toggle">
              <input type="checkbox" :checked="looper.normalizeOn.value" :disabled="!looper.hasAudio.value" @change="onNormalizeChange" />
              {{ t('latentLab.crossmodal.synth.normalize') }}
            </label>
            <span class="param-hint">{{ t('latentLab.crossmodal.synth.normalizeHint') }}</span>
            <span v-if="looper.peakAmplitude.value > 0" class="peak-display">
              {{ t('latentLab.crossmodal.synth.peak') }}: {{ looper.peakAmplitude.value.toFixed(3) }}
            </span>
          </div>
        </div>

        <!-- ═══════ BOX 2: ENVELOPES ═══════ -->
        <!-- ═══════ BOX 2: MODULATION (3 Envelopes + 2 LFOs) ═══════ -->
        <div class="synth-box">
          <!-- 3 ADSR Envelopes -->
          <div v-for="(env, idx) in modulation.envs" :key="'env'+idx" class="adsr-section">
            <div class="mod-header">
              <h5>ENV {{ idx + 1 }}</h5>
              <select class="mod-target-select" :value="env.target.value" @change="modulation.setEnvParam(idx, 'target', ($event.target as HTMLSelectElement).value as ModTarget)">
                <option v-for="t in MOD_TARGETS" :key="t" :value="t">{{ t === 'none' ? '—' : t.toUpperCase() }}</option>
              </select>
              <label class="inline-toggle loop-toggle">
                <input type="checkbox" :checked="env.loop.value" @change="modulation.setEnvParam(idx, 'loop', ($event.target as HTMLInputElement).checked)" />
                Loop
              </label>
            </div>
            <div v-if="env.target.value !== 'none'" class="adsr-grid">
              <div class="adsr-slider">
                <label>A</label>
                <input type="range" v-model.number="env.attackMs.value" min="0" max="2000" step="1" />
                <span class="adsr-value">{{ env.attackMs.value }}ms</span>
              </div>
              <div class="adsr-slider">
                <label>D</label>
                <input type="range" v-model.number="env.decayMs.value" min="0" max="2000" step="1" />
                <span class="adsr-value">{{ env.decayMs.value }}ms</span>
              </div>
              <div class="adsr-slider">
                <label>S</label>
                <input type="range" v-model.number="env.sustain.value" min="0" max="1" step="0.01" />
                <span class="adsr-value">{{ env.sustain.value.toFixed(2) }}</span>
              </div>
              <div class="adsr-slider">
                <label>R</label>
                <input type="range" v-model.number="env.releaseMs.value" min="0" max="3000" step="1" />
                <span class="adsr-value">{{ env.releaseMs.value }}ms</span>
              </div>
              <div class="adsr-slider">
                <label>Amt</label>
                <input type="range" v-model.number="env.amount.value" min="0" max="1" step="0.01" />
                <span class="adsr-value">{{ env.amount.value.toFixed(2) }}</span>
              </div>
            </div>
          </div>

          <!-- 2 LFOs -->
          <div v-for="(lfo, idx) in modulation.lfos" :key="'lfo'+idx" class="adsr-section">
            <div class="mod-header">
              <h5>LFO {{ idx + 1 }}</h5>
              <select class="mod-target-select" :value="lfo.target.value" @change="modulation.setLfoParam(idx, 'target', ($event.target as HTMLSelectElement).value)">
                <option v-for="t in MOD_TARGETS" :key="t" :value="t">{{ t === 'none' ? '—' : t.toUpperCase() }}</option>
              </select>
              <select v-if="lfo.target.value !== 'none'" class="lfo-select" :value="lfo.waveform.value" @change="modulation.setLfoParam(idx, 'waveform', ($event.target as HTMLSelectElement).value)">
                <option value="sine">Sine</option>
                <option value="triangle">Tri</option>
                <option value="square">Sq</option>
                <option value="sawtooth">Saw</option>
              </select>
            </div>
            <div v-if="lfo.target.value !== 'none'" class="adsr-grid">
              <div class="adsr-slider">
                <label>{{ t('latentLab.crossmodal.synth.filter.lfoRate') }}</label>
                <input type="range" :value="lfo.rate.value" min="0.05" max="20" step="0.05" @input="modulation.setLfoParam(idx, 'rate', Number(($event.target as HTMLInputElement).value))" />
                <span class="adsr-value">{{ lfo.rate.value.toFixed(1) }} Hz</span>
              </div>
              <div class="adsr-slider">
                <label>{{ t('latentLab.crossmodal.synth.filter.lfoDepth') }}</label>
                <input type="range" :value="lfo.depth.value" min="0" max="1" step="0.01" @input="modulation.setLfoParam(idx, 'depth', Number(($event.target as HTMLInputElement).value))" />
                <span class="adsr-value">{{ lfo.depth.value.toFixed(2) }}</span>
              </div>
            </div>
          </div>

          <!-- ADR → WT Scan (legacy, kept separate) -->
          <div v-if="wavetableOn" class="adsr-section">
            <h5>{{ t('latentLab.crossmodal.synth.wtScanEnvelope') }} <span class="env-target">WT Scan</span></h5>
            <div class="adsr-grid">
              <div class="adsr-slider">
                <label>A</label>
                <input type="range" v-model.number="wtScanAttack" min="0" max="10000" step="50" />
                <span class="adsr-value">{{ (wtScanAttack / 1000).toFixed(1) }}s</span>
              </div>
              <div class="adsr-slider">
                <label>D</label>
                <input type="range" v-model.number="wtScanDecay" min="0" max="10000" step="50" />
                <span class="adsr-value">{{ (wtScanDecay / 1000).toFixed(1) }}s</span>
              </div>
              <div class="adsr-slider">
                <label>R</label>
                <input type="range" v-model.number="wtScanRelease" min="0" max="10000" step="50" />
                <span class="adsr-value">{{ (wtScanRelease / 1000).toFixed(1) }}s</span>
              </div>
            </div>
          </div>
        </div>

        <!-- ═══════ BOX 3: FILTER ═══════ -->
        <div class="synth-box">
          <div class="section-toggle">
            <label class="inline-toggle">
              <input type="checkbox" :checked="filter.enabled.value" @change="filter.setEnabled(($event.target as HTMLInputElement).checked)" />
              {{ t('latentLab.crossmodal.synth.filter.title') }}
            </label>
            <select v-if="filter.enabled.value" class="filter-type-select" :value="filter.type.value" @change="filter.setType(($event.target as HTMLSelectElement).value as FilterType)">
              <option value="lowpass">LP</option>
              <option value="highpass">HP</option>
              <option value="bandpass">BP</option>
            </select>
          </div>

          <div v-if="filter.enabled.value" class="filter-params">
            <div class="adsr-grid">
              <div class="adsr-slider">
                <label>{{ t('latentLab.crossmodal.synth.filter.cutoff') }}</label>
                <input type="range" :value="filter.cutoff.value" min="0" max="1" step="0.005" @input="filter.setCutoff(Number(($event.target as HTMLInputElement).value))" />
                <span class="adsr-value">{{ Math.round(normalizedToFreq(filter.cutoff.value)) }} Hz</span>
              </div>
              <div class="adsr-slider">
                <label>{{ t('latentLab.crossmodal.synth.filter.resonance') }}</label>
                <input type="range" :value="filter.resonance.value" min="0" max="1" step="0.01" @input="filter.setResonance(Number(($event.target as HTMLInputElement).value))" />
                <span class="adsr-value">{{ filter.resonance.value.toFixed(2) }}</span>
              </div>
              <div class="adsr-slider">
                <label>{{ t('latentLab.crossmodal.synth.filter.mix') }}</label>
                <input type="range" :value="filter.mix.value" min="0" max="1" step="0.01" @input="filter.setMix(Number(($event.target as HTMLInputElement).value))" />
                <span class="adsr-value">{{ Math.round(filter.mix.value * 100) }}%</span>
              </div>
              <div class="adsr-slider">
                <label>{{ t('latentLab.crossmodal.synth.filter.kbdTrack') }}</label>
                <input type="range" :value="filter.kbdTrack.value" min="0" max="1" step="0.01" @input="filter.setKbdTrack(Number(($event.target as HTMLInputElement).value))" />
                <span class="adsr-value">{{ Math.round(filter.kbdTrack.value * 100) }}%</span>
              </div>
            </div>

            <!-- Modulators route to filter cutoff via the modulation bank -->
          </div>
        </div>

        <!-- ═══════ BOX 4: EFFECTS (Delay + Reverb) ═══════ -->
        <div class="synth-box">
          <!-- Delay -->
          <div class="section-toggle">
            <label class="inline-toggle">
              <input type="checkbox" :checked="effects.delayEnabled.value" @change="effects.setDelayEnabled(($event.target as HTMLInputElement).checked)" />
              Delay
            </label>
          </div>
          <div v-if="effects.delayEnabled.value" class="effects-params">
            <div class="adsr-slider">
              <label>Time</label>
              <input type="range" :value="effects.delayTimeMs.value" min="1" max="2000" step="1" @input="effects.setDelayTime(Number(($event.target as HTMLInputElement).value))" />
              <span class="adsr-value">{{ effects.delayTimeMs.value }}ms</span>
            </div>
            <div class="adsr-slider">
              <label>Feedback</label>
              <input type="range" :value="effects.delayFeedback.value" min="0" max="0.95" step="0.01" @input="effects.setDelayFeedback(Number(($event.target as HTMLInputElement).value))" />
              <span class="adsr-value">{{ effects.delayFeedback.value.toFixed(2) }}</span>
            </div>
            <div class="adsr-slider">
              <label>Mix</label>
              <input type="range" :value="effects.delayMix.value" min="0" max="1" step="0.01" @input="effects.setDelayMix(Number(($event.target as HTMLInputElement).value))" />
              <span class="adsr-value">{{ effects.delayMix.value.toFixed(2) }}</span>
            </div>
          </div>
          <!-- Reverb -->
          <div class="section-toggle">
            <label class="inline-toggle">
              <input type="checkbox" :checked="effects.reverbEnabled.value" @change="effects.setReverbEnabled(($event.target as HTMLInputElement).checked)" />
              Reverb
            </label>
            <select
              v-if="effects.reverbEnabled.value"
              class="arp-select"
              :value="effects.reverbVariant.value"
              @change="effects.setReverbVariant(($event.target as HTMLSelectElement).value as any)"
            >
              <option value="bright">Bright</option>
              <option value="medium">Medium</option>
              <option value="dark">Dark</option>
            </select>
          </div>
          <div v-if="effects.reverbEnabled.value" class="effects-params">
            <div class="adsr-slider">
              <label>Mix</label>
              <input type="range" :value="effects.reverbMix.value" min="0" max="1" step="0.01" @input="effects.setReverbMix(Number(($event.target as HTMLInputElement).value))" />
              <span class="adsr-value">{{ effects.reverbMix.value.toFixed(2) }}</span>
            </div>
          </div>
        </div>

        <!-- ═══════ BOX 4: SEQUENCER / ARPEGGIATOR ═══════ -->
        <div class="synth-box">
          <!-- Keyboard -->
          <div class="keyboard-row">
            <button
              v-for="(note, idx) in keyboardNotes"
              :key="idx"
              class="key-btn"
              :class="{ black: note.black, active: activeKeyNote === note.midi }"
              :disabled="!hasLoadedAudio"
              @pointerdown="onKeyDown_key(note.midi)"
              @pointerup="onKeyUp_key"
              @pointerleave="onKeyUp_key"
            >{{ note.label }}</button>
            <button
              class="key-btn hold-btn"
              :class="{ active: holdActive }"
              :disabled="!hasLoadedAudio"
              @click="toggleHold"
            >Hold</button>
          </div>

          <!-- Sequencer -->
          <div class="section-toggle">
            <label class="inline-toggle">
              <input type="checkbox" :checked="sequencerEnabled" @change="setSequencerEnabled(($event.target as HTMLInputElement).checked)" />
              {{ t('latentLab.crossmodal.synth.sequencerToggle') }}
            </label>
          </div>
          <div v-if="sequencerEnabled" class="sequencer-controls">
            <div class="sequencer-transport">
              <button class="seq-play-btn" :disabled="!looper.hasAudio.value" @click="toggleSequencer">
                {{ sequencer.isPlaying.value ? t('latentLab.crossmodal.synth.sequencer.stop') : t('latentLab.crossmodal.synth.sequencer.play') }}
              </button>
              <div class="seq-step-count">
                <button v-for="opt in sequencer.stepCountOptions" :key="opt" class="step-count-btn" :class="{ active: sequencer.stepCount.value === opt }" @click="sequencer.setStepCount(opt)">{{ opt }}</button>
              </div>
              <div class="seq-division">
                <button v-for="div in sequencer.noteDivisions" :key="div" class="division-btn" :class="{ active: sequencer.division.value === div }" @click="sequencer.setDivision(div)">{{ div }}</button>
              </div>
              <div class="seq-division">
                <button v-for="oct in [-1, 0, 1]" :key="oct" class="division-btn" :class="{ active: seqOctave === oct }" @click="seqOctave = oct">{{ oct > 0 ? `+${oct}` : oct }}</button>
              </div>
              <span v-if="sequencer.midiClockActive.value" class="midi-sync-badge">
                {{ t('latentLab.crossmodal.synth.sequencer.midiSync') }}
                <template v-if="sequencer.midiClockBpm.value > 0"> {{ sequencer.midiClockBpm.value }}</template>
              </span>
            </div>
            <div class="sequencer-settings-row">
              <div class="sequencer-preset">
                <label>{{ t('latentLab.crossmodal.synth.sequencer.preset') }}</label>
                <select :value="sequencer.presetIndex.value" @change="onPresetChange">
                  <option :value="-1">—</option>
                  <option v-for="(p, idx) in sequencer.presets" :key="idx" :value="idx">
                    {{ t(`latentLab.crossmodal.synth.sequencer.patterns.${p.name}`) }}
                  </option>
                </select>
              </div>
              <div class="sequencer-bpm">
                <label>{{ t('latentLab.crossmodal.synth.sequencer.bpm') }}</label>
                <input type="range" :value="sequencer.bpm.value" min="60" max="200" step="1" :disabled="sequencer.midiClockActive.value" @input="onBpmInput" />
                <span class="seq-bpm-value">{{ sequencer.midiClockActive.value ? sequencer.midiClockBpm.value : sequencer.bpm.value }}</span>
              </div>
              <div class="sequencer-gate">
                <label>Gate</label>
                <input type="range" :value="sequencer.steps[0]?.gate ?? 0.8" min="0.1" max="1" step="0.05" @input="sequencer.setAllGates(Number(($event.target as HTMLInputElement).value))" />
                <span class="seq-bpm-value">{{ Math.round((sequencer.steps[0]?.gate ?? 0.8) * 100) }}%</span>
              </div>
            </div>
            <div class="seq-grid" :class="`seq-grid-${sequencer.stepCount.value}`">
              <div v-for="(step, idx) in sequencer.steps" :key="idx" class="seq-step" :class="{ active: step.active, playing: sequencer.isPlaying.value && sequencer.currentStep.value === idx, muted: !step.active }">
                <span class="seq-step-num">{{ idx + 1 }}</span>
                <input type="range" class="seq-semitone-slider" :value="step.semitone" min="-24" max="24" step="1" orient="vertical" @input="onStepSemitoneInput(idx, $event)" />
                <span class="seq-semitone-val">{{ step.semitone > 0 ? `+${step.semitone}` : step.semitone }}</span>
                <button class="seq-step-toggle" :class="{ on: step.active, playing: sequencer.isPlaying.value && sequencer.currentStep.value === idx }" @click="sequencer.setStepActive(idx, !step.active)" />
                <input type="range" class="seq-velocity-slider" :value="step.velocity" min="0" max="1" step="0.05" @input="onStepVelocityInput(idx, $event)" />
              </div>
            </div>
            <span class="slider-hint">{{ t('latentLab.crossmodal.synth.sequencer.gridHint') }}</span>
          </div>

          <!-- Arpeggiator -->
          <div class="section-toggle">
            <label class="inline-toggle">
              <input type="checkbox" :checked="arpeggiator.enabled.value" @change="arpeggiator.setEnabled(($event.target as HTMLInputElement).checked)" />
              {{ t('latentLab.crossmodal.synth.arpeggiator') }}
            </label>
            <select v-if="arpeggiator.enabled.value" class="arp-select" :value="arpeggiator.pattern.value" @change="arpeggiator.setPattern(($event.target as HTMLSelectElement).value as 'up' | 'down' | 'updown' | 'random')">
              <option value="up">{{ t('latentLab.crossmodal.synth.arpeggiatorPatterns.up') }}</option>
              <option value="down">{{ t('latentLab.crossmodal.synth.arpeggiatorPatterns.down') }}</option>
              <option value="updown">{{ t('latentLab.crossmodal.synth.arpeggiatorPatterns.updown') }}</option>
              <option value="random">{{ t('latentLab.crossmodal.synth.arpeggiatorPatterns.random') }}</option>
            </select>
            <select v-if="arpeggiator.enabled.value" class="arp-select" :value="arpeggiator.rate.value" @change="arpeggiator.setRate(($event.target as HTMLSelectElement).value as any)">
              <option value="1/4">1/4</option>
              <option value="1/8">1/8</option>
              <option value="1/16">1/16</option>
              <option value="1/32">1/32</option>
              <option value="1/4T">1/4T</option>
              <option value="1/8T">1/8T</option>
              <option value="1/16T">1/16T</option>
            </select>
            <select v-if="arpeggiator.enabled.value" class="arp-select" :value="arpeggiator.octaveRange.value" @change="arpeggiator.setOctaveRange(Number(($event.target as HTMLSelectElement).value))">
              <option :value="1">1 Oct</option>
              <option :value="2">2 Oct</option>
              <option :value="3">3 Oct</option>
              <option :value="4">4 Oct</option>
            </select>
          </div>
        </div>
      </details>

      <!-- Preset Export/Import -->
      <div class="synth-box preset-box">
        <div class="save-row">
          <button class="save-btn" :disabled="!looper.hasAudio.value" @click="saveRaw">
            {{ t('latentLab.crossmodal.synth.saveRaw') }}
          </button>
          <button v-if="engineMode === 'looper' && !sequencerOn" class="save-btn" :disabled="!looper.hasAudio.value" @click="saveLoop">
            {{ t('latentLab.crossmodal.synth.saveLoop') }}
          </button>
          <span class="save-separator" />
          <button class="save-btn" @click="exportPreset">
            {{ t('latentLab.crossmodal.synth.preset.export') }}
          </button>
          <button class="save-btn" @click="() => presetFileInput?.click()">
            {{ t('latentLab.crossmodal.synth.preset.import') }}
          </button>
          <input ref="presetFileInput" type="file" accept=".json" style="display:none" @change="importPreset" />
        </div>
      </div>

      <!-- MIDI Section (collapsed by default) -->
      <details class="midi-section lab-section" :open="midiOpen" @toggle="onMidiToggle">
        <summary>{{ t('latentLab.crossmodal.synth.midiSection') }}</summary>
        <div class="midi-content">
          <div v-if="!midi.isSupported.value" class="midi-unsupported">
            {{ t('latentLab.crossmodal.synth.midiUnsupported') }}
          </div>
          <template v-else>
            <div class="midi-input-select">
              <label>{{ t('latentLab.crossmodal.synth.midiInput') }}</label>
              <select
                :value="midi.selectedInputId.value"
                @change="onMidiInputChange"
              >
                <option :value="null">{{ t('latentLab.crossmodal.synth.midiNone') }}</option>
                <option v-for="inp in midi.inputs.value" :key="inp.id" :value="inp.id">
                  {{ inp.name }}
                </option>
              </select>
            </div>
            <div class="midi-mapping-table">
              <h5>{{ t('latentLab.crossmodal.synth.midiMappings') }}</h5>
              <table>
                <tbody>
                  <tr><td>CC1</td><td>{{ t('latentLab.crossmodal.synth.alpha') }}</td></tr>
                  <tr><td>CC2</td><td>{{ t('latentLab.crossmodal.synth.magnitude') }}</td></tr>
                  <tr><td>CC3</td><td>{{ t('latentLab.crossmodal.synth.noise') }}</td></tr>
                  <tr><td>CC5</td><td>{{ t('latentLab.crossmodal.synth.midiScan') }}</td></tr>
                  <tr><td>CC64</td><td>{{ t('latentLab.crossmodal.synth.loop') }}</td></tr>
                  <tr><td>{{ t('latentLab.crossmodal.synth.midiNoteC3') }}</td><td>{{ t('latentLab.crossmodal.synth.midiGenerate') }}</td></tr>
                  <tr><td>{{ t('latentLab.crossmodal.synth.midiPitch') }}</td><td>{{ t('latentLab.crossmodal.synth.transpose') }}</td></tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>
      </details>
    </div>

    <!-- ===== Tab 2: MMAudio ===== -->
    <div v-if="activeTab === 'mmaudio'" class="tab-panel">
      <h3>{{ t('latentLab.crossmodal.tabs.mmaudio.title') }}</h3>
      <p class="tab-description">{{ t('latentLab.crossmodal.tabs.mmaudio.description') }}</p>

      <details class="explanation-details" :open="mmaudioExplainOpen" @toggle="onMmaudioExplainToggle">
        <summary>{{ t('latentLab.crossmodal.explanationToggle') }}</summary>
        <div class="explanation-body">
          <div class="explanation-section">
            <h4>{{ t('latentLab.crossmodal.mmaudio.explainWhatTitle') }}</h4>
            <p>{{ t('latentLab.crossmodal.mmaudio.explainWhatText') }}</p>
          </div>
          <div class="explanation-section">
            <h4>{{ t('latentLab.crossmodal.mmaudio.explainHowTitle') }}</h4>
            <p>{{ t('latentLab.crossmodal.mmaudio.explainHowText') }}</p>
          </div>
        </div>
      </details>

      <MediaInputBox
        inputType="image"
        icon="🖼️"
        :label="t('latentLab.crossmodal.mmaudio.imageUpload')"
        :allow-sketch="true"
        value=""
        :initial-image="imagePreview"
        @image-uploaded="handleImageUpload"
        @image-removed="clearImage"
        @copy="copyImage"
        @paste="pasteImage"
        @clear="clearImage"
      />

      <MediaInputBox
        icon="💡"
        :label="t('latentLab.crossmodal.mmaudio.prompt')"
        :placeholder="t('latentLab.crossmodal.mmaudio.promptPlaceholder')"
        :value="mmaudio.prompt"
        @update:value="mmaudio.prompt = $event"
        :rows="2"
        :isEmpty="!mmaudio.prompt"
        :isFilled="!!mmaudio.prompt"
        @copy="copyMMAudioPrompt"
        @paste="pasteMMAudioPrompt"
        @clear="clearMMAudioPrompt"
      />

      <MediaInputBox
        icon="📋"
        :label="t('latentLab.crossmodal.mmaudio.negativePrompt')"
        :value="mmaudio.negativePrompt"
        @update:value="mmaudio.negativePrompt = $event"
        :rows="2"
        :isEmpty="!mmaudio.negativePrompt"
        :isFilled="!!mmaudio.negativePrompt"
        :showTranslate="false"
        @copy="copyMMAudioNeg"
        @paste="pasteMMAudioNeg"
        @clear="clearMMAudioNeg"
      />

      <div class="params-row">
        <div class="param">
          <label>{{ t('latentLab.crossmodal.mmaudio.duration') }}</label>
          <input v-model.number="mmaudio.duration" type="number" min="1" max="8" step="1" />
          <span class="param-hint">{{ t('latentLab.crossmodal.mmaudio.maxDuration') }}</span>
        </div>
        <div class="param">
          <label>{{ t('latentLab.crossmodal.mmaudio.cfg') }}</label>
          <input v-model.number="mmaudio.cfg" type="number" min="1" max="15" step="0.5" />
          <span class="param-hint">{{ t('latentLab.shared.cfgHint') }}</span>
        </div>
        <div class="param">
          <label>{{ t('latentLab.crossmodal.mmaudio.steps') }}</label>
          <input v-model.number="mmaudio.steps" type="number" min="10" max="50" step="5" />
          <span class="param-hint">{{ t('latentLab.shared.stepsHint') }}</span>
        </div>
        <div class="param">
          <label>{{ t('latentLab.crossmodal.seed') }}</label>
          <input v-model.number="mmaudio.seed" type="number" />
          <span class="param-hint">{{ t('latentLab.shared.seedHint') }}</span>
        </div>
      </div>

      <button class="generate-btn" :disabled="(!mmaudio.prompt && !imagePath) || generating" @click="runMMAudio">
        {{ generating ? t('latentLab.crossmodal.generating') : t('latentLab.crossmodal.generate') }}
      </button>
    </div>

    <!-- ===== Tab 3: ImageBind Guidance ===== -->
    <div v-if="activeTab === 'guidance'" class="tab-panel">
      <h3>{{ t('latentLab.crossmodal.tabs.guidance.title') }}</h3>
      <p class="tab-description">{{ t('latentLab.crossmodal.tabs.guidance.description') }}</p>

      <details class="explanation-details" :open="guidanceExplainOpen" @toggle="onGuidanceExplainToggle">
        <summary>{{ t('latentLab.crossmodal.explanationToggle') }}</summary>
        <div class="explanation-body">
          <div class="explanation-section">
            <h4>{{ t('latentLab.crossmodal.guidance.explainWhatTitle') }}</h4>
            <p>{{ t('latentLab.crossmodal.guidance.explainWhatText') }}</p>
          </div>
          <div class="explanation-section">
            <h4>{{ t('latentLab.crossmodal.guidance.explainHowTitle') }}</h4>
            <p>{{ t('latentLab.crossmodal.guidance.explainHowText') }}</p>
          </div>
          <div class="explanation-section explanation-references">
            <h4>{{ t('latentLab.crossmodal.guidance.referencesTitle') }}</h4>
            <ul class="reference-list">
              <li>
                <span class="ref-authors">Girdhar et al. (2023)</span>
                <span class="ref-title">"ImageBind: One Embedding Space To Bind Them All"</span>
                <span class="ref-venue">CVPR 2023</span>
                <a href="https://doi.org/10.48550/arXiv.2305.05665" target="_blank" rel="noopener" class="ref-doi">DOI</a>
              </li>
            </ul>
          </div>
        </div>
      </details>

      <MediaInputBox
        inputType="image"
        icon="🖼️"
        :label="t('latentLab.crossmodal.guidance.imageUpload')"
        :allow-sketch="true"
        value=""
        :initial-image="imagePreview"
        @image-uploaded="handleImageUpload"
        @image-removed="clearImage"
        @copy="copyImage"
        @paste="pasteImage"
        @clear="clearImage"
      />

      <MediaInputBox
        icon="💡"
        :label="t('latentLab.crossmodal.guidance.prompt')"
        :placeholder="t('latentLab.crossmodal.guidance.promptPlaceholder')"
        :value="guidance.prompt"
        @update:value="guidance.prompt = $event"
        :rows="2"
        :isEmpty="!guidance.prompt"
        :isFilled="!!guidance.prompt"
        @copy="copyGuidancePrompt"
        @paste="pasteGuidancePrompt"
        @clear="clearGuidancePrompt"
      />

      <!-- Guidance sliders -->
      <div class="slider-group">
        <div class="slider-item">
          <div class="slider-header">
            <label>{{ t('latentLab.crossmodal.guidance.lambda') }}</label>
            <span class="slider-value">{{ guidance.lambda.toFixed(3) }}</span>
          </div>
          <input type="range" v-model.number="guidance.lambda" min="0.01" max="1" step="0.01" />
          <span class="slider-hint">{{ t('latentLab.crossmodal.guidance.lambdaHint') }}</span>
        </div>

        <div class="slider-item">
          <div class="slider-header">
            <label>{{ t('latentLab.crossmodal.guidance.warmupSteps') }}</label>
            <span class="slider-value">{{ guidance.warmupSteps }}</span>
          </div>
          <input type="range" v-model.number="guidance.warmupSteps" min="5" max="30" step="1" />
          <span class="slider-hint">{{ t('latentLab.crossmodal.guidance.warmupHint') }}</span>
        </div>
      </div>

      <div class="params-row">
        <div class="param">
          <label>{{ t('latentLab.crossmodal.guidance.totalSteps') }}</label>
          <input v-model.number="guidance.totalSteps" type="number" min="20" max="150" step="10" />
          <span class="param-hint">{{ t('latentLab.crossmodal.guidance.totalStepsHint') }}</span>
        </div>
        <div class="param">
          <label>{{ t('latentLab.crossmodal.guidance.duration') }}</label>
          <input v-model.number="guidance.duration" type="number" min="1" max="30" step="1" />
          <span class="param-hint">{{ t('latentLab.crossmodal.guidance.durationHint') }}</span>
        </div>
        <div class="param">
          <label>{{ t('latentLab.crossmodal.guidance.cfg') }}</label>
          <input v-model.number="guidance.cfg" type="number" min="1" max="15" step="0.5" />
          <span class="param-hint">{{ t('latentLab.shared.cfgHint') }}</span>
        </div>
        <div class="param">
          <label>{{ t('latentLab.crossmodal.seed') }}</label>
          <input v-model.number="guidance.seed" type="number" />
          <span class="param-hint">{{ t('latentLab.shared.seedHint') }}</span>
        </div>
      </div>

      <button class="generate-btn" :disabled="!imagePath || generating" @click="runGuidance">
        {{ generating ? t('latentLab.crossmodal.generating') : t('latentLab.crossmodal.generate') }}
      </button>
    </div>

    <!-- ===== Output Area (MMAudio / Guidance only — synth uses looper + explorer) ===== -->
    <div v-if="error" class="output-area">
      <div class="error-message">{{ error }}</div>
    </div>
    <div v-if="activeTab !== 'synth'" class="output-section">
      <MediaOutputBox
        :output-image="resultAudio"
        media-type="audio"
        :is-executing="generating"
        :progress="0"
        @download="downloadResultAudio"
      />
      <div v-if="resultSeed !== null || generationTimeMs || cosineSimilarity !== null" class="result-meta">
        <span v-if="resultSeed !== null" class="meta-item">{{ t('latentLab.crossmodal.seed') }}: {{ resultSeed }}</span>
        <span v-if="generationTimeMs" class="meta-item">{{ t('latentLab.crossmodal.generationTime') }}: {{ generationTimeMs }}ms</span>
        <span v-if="cosineSimilarity !== null" class="meta-item">{{ t('latentLab.crossmodal.guidance.cosineSimilarity') }}: {{ cosineSimilarity.toFixed(4) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAudioLooper } from '@/composables/useAudioLooper'
import { useWavetableOsc } from '@/composables/useWavetableOsc'
import { useModulation, type ModTarget, type LfoWaveform, MOD_TARGETS } from '@/composables/useModulation'
import { useWebMidi } from '@/composables/useWebMidi'
import { useStepSequencer } from '@/composables/useStepSequencer'
import { useArpeggiator } from '@/composables/useArpeggiator'
import { useEffects, type PlateVariant } from '@/composables/useEffects'
import { useFilter, type FilterType, normalizedToFreq } from '@/composables/useFilter'
import MediaInputBox from '@/components/MediaInputBox.vue'
import MediaOutputBox from '@/components/MediaOutputBox.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useLatentLabRecorder } from '@/composables/useLatentLabRecorder'
import { useDetailsState } from '@/composables/useDetailsState'

const { t } = useI18n()
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
const { record: labRecord } = useLatentLabRecorder('crossmodal_lab')
const { isOpen: synthExplainOpen, onToggle: onSynthExplainToggle } = useDetailsState('ll_crossmodal_explain')
const { isOpen: dimExplorerOpen, onToggle: onDimExplorerToggle } = useDetailsState('ll_crossmodal_dims', true)
const { isOpen: looperOpen, onToggle: onLooperToggle } = useDetailsState('ll_crossmodal_looper', true)
const { isOpen: midiOpen, onToggle: onMidiToggle } = useDetailsState('ll_crossmodal_midi')
const { isOpen: mmaudioExplainOpen, onToggle: onMmaudioExplainToggle } = useDetailsState('ll_crossmodal_mmaudio_explain')
const { isOpen: guidanceExplainOpen, onToggle: onGuidanceExplainToggle } = useDetailsState('ll_crossmodal_guidance_explain')

const API_BASE = import.meta.env.DEV ? 'http://localhost:17802' : ''

type TabId = 'synth' | 'mmaudio' | 'guidance'

const tabs: { id: TabId }[] = [
  { id: 'synth' },
  { id: 'mmaudio' },
  { id: 'guidance' },
]

const activeTab = ref<TabId>('synth')
const error = ref('')
const resultAudio = ref('')
const resultSeed = ref<number | null>(null)
const generationTimeMs = ref<number | null>(null)
const cosineSimilarity = ref<number | null>(null)

interface EmbeddingStats {
  mean: number
  std: number
  top_dimensions: Array<{ dim: number; value: number }>
  all_activations?: Array<{ dim: number; value: number }>
  sort_mode?: string
  emb_a_values?: Record<number, number>
  emb_b_values?: Record<number, number>
}
const embeddingStats = ref<EmbeddingStats | null>(null)

// Image upload (shared across MMAudio and Guidance)
const imagePreview = ref('')
const imagePath = ref('')

// Last synth base64 for replay
const lastSynthBase64 = ref('')

// Fingerprint of last successful synth generation (prevents redundant GPU calls)
const lastSynthFingerprint = ref('')

// ===== Audio Looper =====
const looper = useAudioLooper()
const waveformCanvasRef = ref<HTMLCanvasElement | null>(null)

function drawWaveform() {
  const canvas = waveformCanvasRef.value
  if (!canvas || !looper.hasAudio.value) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const dpr = window.devicePixelRatio || 1
  const w = canvas.clientWidth
  const h = canvas.clientHeight
  if (w === 0 || h === 0) return
  canvas.width = w * dpr
  canvas.height = h * dpr
  ctx.scale(dpr, dpr)
  ctx.clearRect(0, 0, w, h)

  const peaks = looper.getWaveformPeaks(w)
  if (!peaks) return

  const startX = looper.loopStartFrac.value * w
  const endX = looper.loopEndFrac.value * w

  // Dim regions outside loop selection
  ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'
  ctx.fillRect(0, 0, startX, h)
  ctx.fillRect(endX, 0, w - endX, h)

  // Draw waveform bars
  const mid = h / 2
  for (let i = 0; i < peaks.length; i++) {
    const inLoop = i >= startX && i <= endX
    ctx.fillStyle = inLoop ? 'rgba(76, 175, 80, 0.6)' : 'rgba(76, 175, 80, 0.2)'
    const barH = peaks[i]! * mid
    ctx.fillRect(i, mid - barH, 1, barH * 2)
  }
}

// ===== Wavetable Oscillator =====
const wavetableOsc = useWavetableOsc()
const wavetableScan = ref(0)
type WtMode = 'extract' | 'semantic'
const wtMode = ref<WtMode>('extract')
const wtBuildAxis = ref('')
const wtBuildFrameCount = ref(16)
const wtBuilding = ref(false)
const wtBuildProgress = ref(0)
const wtBuildProgressCurrent = ref(0)
const wtInterpolate = ref(true)
const wtScanAttack = ref(500)
const wtScanDecay = ref(1000)
const wtScanRelease = ref(300)
const wtRangeStart = ref(0)   // 0-based frame index
const wtRangeEnd = ref(16)    // exclusive end, updated when frames loaded
const scanTrackEl = ref<HTMLElement | null>(null)

/** Display: current frame number within the clamped range */
const scanDisplayFrame = computed(() => {
  const total = wavetableOsc.frameCount.value
  if (total === 0) return '—'
  const rangeSize = wtRangeEnd.value - wtRangeStart.value
  const frame = wtRangeStart.value + Math.round(wavetableScan.value * Math.max(rangeSize - 1, 0))
  return `${frame + 1}`
})

/** Bracket positions as percentage of the track width */
const rangeStartPct = computed(() => {
  const total = wavetableOsc.frameCount.value
  return total > 0 ? (wtRangeStart.value / total) * 100 : 0
})
const rangeEndPct = computed(() => {
  const total = wavetableOsc.frameCount.value
  return total > 0 ? (wtRangeEnd.value / total) * 100 : 100
})
const rangeBandStyle = computed(() => ({
  left: `${rangeStartPct.value}%`,
  width: `${rangeEndPct.value - rangeStartPct.value}%`,
}))

/** Drag a bracket handle to adjust range start/end */
function startBracketDrag(which: 'start' | 'end', event: PointerEvent) {
  const track = scanTrackEl.value
  if (!track) return
  const handle = event.target as HTMLElement
  handle.setPointerCapture(event.pointerId)

  const onMove = (e: PointerEvent) => {
    const rect = track.getBoundingClientRect()
    const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    const total = wavetableOsc.frameCount.value
    const frame = Math.round(frac * total)
    if (which === 'start') {
      wtRangeStart.value = Math.max(0, Math.min(frame, wtRangeEnd.value - 1))
    } else {
      wtRangeEnd.value = Math.max(wtRangeStart.value + 1, Math.min(frame, total))
    }
  }
  const onUp = () => {
    handle.releasePointerCapture(event.pointerId)
    handle.removeEventListener('pointermove', onMove)
    handle.removeEventListener('pointerup', onUp)
  }
  handle.addEventListener('pointermove', onMove)
  handle.addEventListener('pointerup', onUp)
}

// ===== Step Sequencer =====
const sequencer = useStepSequencer()

// ===== Arpeggiator =====
// Use effective BPM: MIDI clock when active, otherwise manual BPM
const effectiveBpm = computed(() =>
  sequencer.midiClockActive.value ? sequencer.midiClockBpm.value : sequencer.bpm.value
)
const arpeggiator = useArpeggiator(effectiveBpm)

// ===== Transport State Machine =====
// Single source of truth for UI — decoupled from low-level engine playback events.
type TransportState = 'idle' | 'playing' | 'paused' | 'generating'
type EngineMode = 'looper' | 'wavetable'
type LoopMode = 'oneshot' | 'loop' | 'pingpong'

const transport = ref<TransportState>('idle')
const engineMode = ref<EngineMode>('looper')
const loopMode = ref<LoopMode>('oneshot')
const sequencerEnabled = ref(false)
const seqOctave = ref(0) // -1, 0, +1
let preGenTransport: 'idle' | 'playing' | 'paused' = 'idle'

// Derived state for template — NEVER flickers during MIDI/retrigger
const generating = computed(() => transport.value === 'generating')
const showPlayButton = computed(() =>
  transport.value === 'paused' && hasLoadedAudio.value
)
const hasLoadedAudio = computed(() =>
  engineMode.value === 'looper' ? looper.hasAudio.value : wavetableOsc.hasFrames.value
)
// Compat aliases for code that still references old names
const wavetableOn = computed(() => engineMode.value === 'wavetable')
const sequencerOn = computed(() => sequencerEnabled.value)

// ===== ADSR Envelope + Effects =====
const modulation = useModulation()
const filter = useFilter()
const effects = useEffects()
let envelopeWired = false

/**
 * Lazily wire: engines → DCA gain → filter → effects → destination.
 * All native Web Audio nodes, no AudioWorklet (iPad-safe).
 */
function wireEnvelope() {
  if (envelopeWired) return
  const ac = looper.getContext()

  // Initialize modulation bank
  modulation.init(ac)

  // Effects chain: returns an input GainNode that routes to destination
  const effectsInput = effects.createChain(ac, ac.destination)

  // Filter → effects input
  const { input: filterInput, output: filterOutput } = filter.createNode(ac)
  filterOutput.connect(effectsInput)

  // DCA GainNode (from modulation bank) → filter input
  const dcaGain = modulation.getDcaGainNode()!
  dcaGain.connect(filterInput)

  // Register modulation targets
  const freqParam = filter.getFrequencyParam()
  modulation.setTargets({
    dca: { param: dcaGain.gain, baseValue: 1 },
    ...(freqParam ? { dcf_cutoff: { param: freqParam, baseValue: freqParam.value } } : {}),
  })

  // Engines → DCA gain
  looper.setDestination(dcaGain)
  wavetableOsc.setContext(ac)
  wavetableOsc.setDestination(dcaGain)
  envelopeWired = true
}

// ===== Web MIDI =====
const midi = useWebMidi()

// MIDI reference note for transpose (C3 = 60)
const MIDI_REF_NOTE = 60

// ===== On-screen Keyboard =====
const keyboardNotes = [
  { label: 'C',  midi: 60, black: false },
  { label: 'C#', midi: 61, black: true },
  { label: 'D',  midi: 62, black: false },
  { label: 'D#', midi: 63, black: true },
  { label: 'E',  midi: 64, black: false },
  { label: 'F',  midi: 65, black: false },
  { label: 'F#', midi: 66, black: true },
  { label: 'G',  midi: 67, black: false },
  { label: 'G#', midi: 68, black: true },
  { label: 'A',  midi: 69, black: false },
  { label: 'A#', midi: 70, black: true },
  { label: 'B',  midi: 71, black: false },
]
const activeKeyNote = ref<number | null>(null)
const holdActive = ref(false)
const heldKeyNote = ref<number | null>(null)

/** Sequencer base transpose: semitone offset from C3 when a key is held */
const seqKeyTranspose = computed(() =>
  heldKeyNote.value !== null ? heldKeyNote.value - MIDI_REF_NOTE : 0
)

function onKeyDown_key(midi: number) {
  activeKeyNote.value = midi
  if (holdActive.value) {
    heldKeyNote.value = midi
  }
  triggerEngine(midi, 0.9)
}

function onKeyUp_key() {
  if (holdActive.value) return // Hold mode: note sustains
  releaseCurrentNote()
}

function toggleHold() {
  holdActive.value = !holdActive.value
  if (!holdActive.value) {
    // Turning hold off: release the sustained note
    heldKeyNote.value = null
    releaseCurrentNote()
  }
}

function releaseCurrentNote() {
  activeKeyNote.value = null
  if (engineMode.value === 'wavetable') {
    wavetableOsc.stopScanEnvelope(wtScanRelease.value, mappedScanPosition(0))
  }
  modulation.triggerRelease()
  const stopDelay = modulation.envs[0]!.releaseMs.value + 50
  setTimeout(() => {
    if (activeKeyNote.value !== null) return
    if (engineMode.value === 'looper') looper.stop()
    else wavetableOsc.stop()
  }, stopDelay)
}

// Monophonic note stack for last-note priority
const heldNotes: number[] = []

// Initialize MIDI
midi.init()

// MIDI CC mappings
// CC1 → Alpha (-2 to +2, center = 0, beyond ±1 = extrapolation)
midi.mapCC(1, (v) => { synth.alpha = v * 4 - 2 })
// CC2 → Magnitude (0.1 to 5)
midi.mapCC(2, (v) => { synth.magnitude = 0.1 + v * 4.9 })
// CC3 → Noise (0 to 1)
midi.mapCC(3, (v) => { synth.noise = v })
// CC64 → Loop toggle (sustain pedal: >0.5 = on)
midi.mapCC(64, (v) => { setLoopMode(v > 0.5 ? 'loop' : 'oneshot') })
// CC5 → Wavetable scan position
midi.mapCC(5, (v) => { wavetableScan.value = v; wavetableOsc.setScanPosition(v) })

// MIDI Clock → Step Sequencer
midi.onClock(sequencer.handleMidiClock)

// MIDI Note → Monophonic synth with ADSR envelope (NEVER triggers generation)
// In sequencer mode, MIDI notes are ignored (sequencer drives the engine)
midi.onNote((note, velocity, on) => {
  if (sequencerEnabled.value) return
  if (on) {
    wireEnvelope()
    const wasEmpty = heldNotes.length === 0
    // Remove duplicate if re-pressed, then push to top
    const idx = heldNotes.indexOf(note)
    if (idx !== -1) heldNotes.splice(idx, 1)
    heldNotes.push(note)

    if (wasEmpty) {
      // Non-legato: retrigger active engine + attack
      arpeggiator.processNote(note, velocity, (n, v) => {
        triggerEngine(n, v)
      }, () => {
        modulation.triggerRelease()
      })
    } else {
      // Legato: just transpose, envelope continues at sustain
      const semitones = note - MIDI_REF_NOTE
      if (engineMode.value === 'looper') {
        looper.setTranspose(semitones)
      } else {
        wavetableOsc.setFrequencyFromNote(note)
      }
    }
  } else {
    // Note-off: remove from stack
    const idx = heldNotes.indexOf(note)
    if (idx !== -1) heldNotes.splice(idx, 1)

    if (heldNotes.length === 0) {
      // Last note released: stop arpeggiator, start release phase
      arpeggiator.stop()
      if (engineMode.value === 'wavetable') {
        wavetableOsc.stopScanEnvelope(wtScanRelease.value, mappedScanPosition(0))
      }
      modulation.triggerRelease()
      setTimeout(() => {
        if (heldNotes.length === 0) {
          if (engineMode.value === 'looper') looper.stop()
          else wavetableOsc.stop()
        }
      }, modulation.envs[0]!.releaseMs.value + 50)
    } else {
      // Notes remaining: switch pitch to last held note
      const lastNote = heldNotes[heldNotes.length - 1]!
      if (engineMode.value === 'looper') {
        looper.setTranspose(lastNote - MIDI_REF_NOTE)
      } else {
        wavetableOsc.setFrequencyFromNote(lastNote)
      }
    }
  }
})

// Synth params
const synth = reactive({
  promptA: 'a steady clean saw wave, c3',
  promptB: 'glass breaking',
  alpha: -0.17,
  magnitude: 1.0,
  noise: 0.0,
  duration: 3.0,
  startPosition: 0.0,
  steps: 20,
  cfg: 7.0,
  seed: 123456789,
  loop: true,
})

// ===== Semantic Axes =====
const { isOpen: semanticAxesOpen, onToggle: onSemanticAxesToggle } = useDetailsState('ll_crossmodal_semantic_axes')

interface AxisDef {
  name: string
  pole_a: string
  pole_b: string
  level: string
  d: number | null
  type?: 'semantic' | 'pca'
}
const availableAxes = ref<AxisDef[]>([])
const semanticAxisList = computed(() => availableAxes.value.filter(a => a.type !== 'pca'))
const pcaAxisList = computed(() => availableAxes.value.filter(a => a.type === 'pca'))

interface AxisSlot {
  axis: string
  value: number
}
const axisSlots = reactive<AxisSlot[]>([
  { axis: 'acoustic_electronic', value: 0 },
  { axis: 'music_noise', value: 0 },
  { axis: 'vocal_instrumental', value: 0 },
])

const axisColors = ['#e91e63', '#2196f3', '#4caf50']

// Non-linear duration mapping: quadratic scale (finer control at short durations)
const DURATION_MIN = 0.1
const DURATION_MAX = 30
function sliderToDuration(t: number): number {
  return DURATION_MIN + t * t * (DURATION_MAX - DURATION_MIN)
}
function durationToSlider(d: number): number {
  return Math.sqrt(Math.max(0, (d - DURATION_MIN) / (DURATION_MAX - DURATION_MIN)))
}

// Non-linear axis mapping: cubic scale, symmetric around center.
// Slider 0–1 (center=0.5) → value -2 to +2, finer control near 0.
const AXIS_MAX = 2
function sliderToAxisValue(t: number): number {
  const centered = (t - 0.5) * 2 // -1 to +1
  return Math.sign(centered) * Math.pow(Math.abs(centered), 2) * AXIS_MAX
}
function axisValueToSlider(v: number): number {
  const norm = Math.sign(v) * Math.sqrt(Math.abs(v) / AXIS_MAX) // -1 to +1
  return norm / 2 + 0.5
}

interface AxisContribution {
  dim: number
  top_axis: string
  contribution: number
  all: Record<string, number>
}
const axisContributions = ref<AxisContribution[]>([])

function getAxisMeta(axisName: string): AxisDef | undefined {
  return availableAxes.value.find(a => a.name === axisName)
}

function onAxisSelectChange(idx: number, value: string) {
  axisSlots[idx]!.axis = value
  axisSlots[idx]!.value = 0
}

function resetAxesToCenter() {
  for (const slot of axisSlots) {
    slot.value = 0
  }
}

async function fetchSemanticAxes() {
  try {
    const resp = await fetch(`${API_BASE}/api/cross_aesthetic/semantic_axes`)
    if (!resp.ok) return
    const data = await resp.json()
    if (data.success && data.axes) {
      availableAxes.value = data.axes
    }
  } catch {
    // Silent fail — axes just won't be available
  }
}

// MMAudio params
const mmaudio = reactive({
  prompt: '',
  negativePrompt: '',
  duration: 8,
  cfg: 4.5,
  steps: 25,
  seed: -1,
})

// ImageBind Guidance params
const guidance = reactive({
  prompt: '',
  lambda: 0.1,
  warmupSteps: 10,
  totalSteps: 50,
  duration: 10,
  cfg: 7.0,
  seed: -1,
})

// ===== Dimension Explorer =====
type SpectralMode = 'relative' | 'absolute'
const spectralMode = ref<SpectralMode>('relative')
const dimensionOffsets = reactive<Record<number, number>>({})
// In relative mode, dimensionOffsets stores mix factors per dimension: -1 = pure B, 0 = current blend, +1 = pure A
// In absolute mode, dimensionOffsets stores direct activation offsets (existing behavior)
const spectralCanvasRef = ref<HTMLCanvasElement | null>(null)
const presetFileInput = ref<HTMLInputElement | null>(null)
const hoveredDim = ref<{ dim: number; activation: number; offset: number } | null>(null)
let isDragging = false
let lockedDim: number | null = null // pointer-captured dimension (prevents cross-dim painting)
let rafPending = false // coalesce draw calls via requestAnimationFrame

// Undo/Redo history (snapshot per paint stroke)
const MAX_HISTORY = 50
const undoStack: Record<number, number>[] = []
const redoStack: Record<number, number>[] = []
const canUndo = ref(false)
const canRedo = ref(false)

function snapshotOffsets(): Record<number, number> {
  return { ...dimensionOffsets }
}

function restoreOffsets(snapshot: Record<number, number>) {
  Object.keys(dimensionOffsets).forEach(k => delete dimensionOffsets[Number(k)])
  Object.assign(dimensionOffsets, snapshot)
  drawSpectralStrip()
}

function pushUndo() {
  undoStack.push(snapshotOffsets())
  if (undoStack.length > MAX_HISTORY) undoStack.shift()
  redoStack.length = 0
  canUndo.value = undoStack.length > 0
  canRedo.value = false
}

function undo() {
  if (!undoStack.length) return
  redoStack.push(snapshotOffsets())
  restoreOffsets(undoStack.pop()!)
  canUndo.value = undoStack.length > 0
  canRedo.value = redoStack.length > 0
}

function redo() {
  if (!redoStack.length) return
  undoStack.push(snapshotOffsets())
  restoreOffsets(redoStack.pop()!)
  canUndo.value = undoStack.length > 0
  canRedo.value = redoStack.length > 0
}

const activeOffsetCount = computed(() =>
  Object.values(dimensionOffsets).filter(v => v !== 0).length
)

/** Relative mode requires both A and B reference embeddings */
const hasABReference = computed(() =>
  !!(embeddingStats.value?.emb_a_values && embeddingStats.value?.emb_b_values)
)

const maxActivation = computed(() => {
  const acts = embeddingStats.value?.all_activations
  if (!acts?.length) return 1
  return Math.max(...acts.map(a => Math.abs(a.value)), 0.001)
})

function drawSpectralStrip() {
  const canvas = spectralCanvasRef.value
  const acts = embeddingStats.value?.all_activations
  if (!canvas || !acts?.length) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const dpr = window.devicePixelRatio || 1
  const rect = canvas.getBoundingClientRect()
  canvas.width = rect.width * dpr
  canvas.height = rect.height * dpr
  ctx.scale(dpr, dpr)

  const w = rect.width
  const h = rect.height
  const centerY = h / 2
  const barW = w / acts.length
  const maxAct = maxActivation.value
  const halfH = centerY - 2

  // Clear
  ctx.clearRect(0, 0, w, h)

  // Zero-line
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(0, centerY)
  ctx.lineTo(w, centerY)
  ctx.stroke()

  // Build axis color lookup for semantic mode
  const axisColorMap: Record<string, string> = {}
  if (axisContributions.value.length > 0) {
    for (let si = 0; si < axisSlots.length; si++) {
      const slot = axisSlots[si]!
      if (slot.axis) {
        axisColorMap[slot.axis] = axisColors[si]!
      }
    }
  }

  const isRelative = spectralMode.value === 'relative' && hasABReference.value
  const embAVals = embeddingStats.value?.emb_a_values
  const embBVals = embeddingStats.value?.emb_b_values

  // In ABSOLUTE mode with A/B reference: draw idealized A/B corridor lines
  if (spectralMode.value === 'absolute' && embAVals && embBVals) {
    // Collect A and B y-positions for the corridor envelope
    const aPoints: Array<{ x: number; y: number }> = []
    const bPoints: Array<{ x: number; y: number }> = []
    for (let i = 0; i < acts.length; i++) {
      const dim = acts[i]!.dim
      const aVal = embAVals[dim] ?? 0
      const bVal = embBVals[dim] ?? 0
      const x = i * barW + barW / 2
      aPoints.push({ x, y: centerY - (aVal / maxAct) * halfH })
      bPoints.push({ x, y: centerY - (bVal / maxAct) * halfH })
    }

    // Draw A corridor line (warm orange, dashed)
    ctx.strokeStyle = 'rgba(255, 152, 0, 0.5)'
    ctx.lineWidth = 1
    ctx.setLineDash([3, 3])
    ctx.beginPath()
    for (let i = 0; i < aPoints.length; i++) {
      const p = aPoints[i]!
      if (i === 0) ctx.moveTo(p.x, p.y)
      else ctx.lineTo(p.x, p.y)
    }
    ctx.stroke()

    // Draw B corridor line (cool blue, dashed)
    ctx.strokeStyle = 'rgba(66, 165, 245, 0.5)'
    ctx.beginPath()
    for (let i = 0; i < bPoints.length; i++) {
      const p = bPoints[i]!
      if (i === 0) ctx.moveTo(p.x, p.y)
      else ctx.lineTo(p.x, p.y)
    }
    ctx.stroke()
    ctx.setLineDash([])
  }

  // Draw bars
  for (let i = 0; i < acts.length; i++) {
    const entry = acts[i]!
    const dim = entry.dim
    const x = i * barW

    if (isRelative) {
      // RELATIVE MODE: bar shows current mix position between A and B
      // Full canvas height represents A (top) to B (bottom)
      // Center = current blend (alpha), offset pulls toward A (+1) or B (-1)
      const aVal = embAVals![dim] ?? 0
      const bVal = embBVals![dim] ?? 0
      const mixFactor = dimensionOffsets[dim] ?? 0 // -1..+1, 0 = no change

      // Draw A/B reference markers (thin horizontal ticks)
      const aY = centerY - (aVal / maxAct) * halfH
      const bY = centerY - (bVal / maxAct) * halfH
      ctx.fillStyle = 'rgba(255, 152, 0, 0.3)'
      ctx.fillRect(x, aY - 0.5, Math.max(barW - 0.5, 0.5), 1)
      ctx.fillStyle = 'rgba(66, 165, 245, 0.3)'
      ctx.fillRect(x, bY - 0.5, Math.max(barW - 0.5, 0.5), 1)

      // Current activation bar (muted)
      const val = entry.value
      const barH = (Math.abs(val) / maxAct) * halfH
      ctx.fillStyle = 'rgba(76, 175, 80, 0.2)'
      if (val >= 0) {
        ctx.fillRect(x, centerY - barH, Math.max(barW - 0.5, 0.5), barH)
      } else {
        ctx.fillRect(x, centerY, Math.max(barW - 0.5, 0.5), barH)
      }

      // Mix overlay: interpolate between current activation and target (A or B)
      if (mixFactor !== 0) {
        // mixFactor > 0 = toward A, < 0 = toward B
        const targetVal = mixFactor > 0
          ? val + Math.abs(mixFactor) * (aVal - val)
          : val + Math.abs(mixFactor) * (bVal - val)
        const targetY = centerY - (targetVal / maxAct) * halfH
        const currentY = centerY - (val / maxAct) * halfH

        // Draw line from current to target
        const segTop = Math.min(currentY, targetY)
        const segH = Math.abs(targetY - currentY)
        ctx.fillStyle = mixFactor > 0
          ? 'rgba(255, 152, 0, 0.7)' // toward A: warm
          : 'rgba(66, 165, 245, 0.7)' // toward B: cool
        ctx.fillRect(x, segTop, Math.max(barW - 0.5, 0.5), Math.max(segH, 1))
      }
    } else {
      // ABSOLUTE MODE: existing behavior
      const val = entry.value
      const barH = (Math.abs(val) / maxAct) * halfH

      // Determine bar color
      let barColor = 'rgba(76, 175, 80, 0.35)'
      if (axisContributions.value.length > 0) {
        const contrib = axisContributions.value.find(c => c.dim === dim)
        if (contrib && contrib.top_axis && axisColorMap[contrib.top_axis]) {
          barColor = hexToRgba(axisColorMap[contrib.top_axis]!, 0.45)
        }
      }

      ctx.fillStyle = barColor
      if (val >= 0) {
        ctx.fillRect(x, centerY - barH, Math.max(barW - 0.5, 0.5), barH)
      } else {
        ctx.fillRect(x, centerY, Math.max(barW - 0.5, 0.5), barH)
      }

      // Offset overlay (bright green)
      const offset = dimensionOffsets[dim]
      if (offset !== undefined && offset !== 0) {
        const offsetH = (Math.abs(offset) / maxAct) * halfH
        ctx.fillStyle = 'rgba(102, 187, 106, 0.8)'
        if (offset > 0) {
          const startY = val >= 0 ? centerY - barH : centerY
          ctx.fillRect(x, startY - offsetH, Math.max(barW - 0.5, 0.5), offsetH)
        } else {
          const startY = val >= 0 ? centerY : centerY + barH
          ctx.fillRect(x, startY, Math.max(barW - 0.5, 0.5), offsetH)
        }
      }
    }
  }
}

function dimAtX(canvas: HTMLCanvasElement, clientX: number): number | null {
  const acts = embeddingStats.value?.all_activations
  if (!acts?.length) return null
  const rect = canvas.getBoundingClientRect()
  const x = clientX - rect.left
  const idx = Math.floor(x / (rect.width / acts.length))
  if (idx < 0 || idx >= acts.length) return null
  return acts[idx]!.dim
}

function offsetAtY(canvas: HTMLCanvasElement, clientY: number): number {
  const rect = canvas.getBoundingClientRect()
  const centerY = rect.height / 2
  const y = clientY - rect.top

  if (spectralMode.value === 'relative' && hasABReference.value) {
    // Relative mode: map y to mix factor [-1, +1]
    // Top = +1 (toward A), Center = 0 (no change), Bottom = -1 (toward B)
    const normalized = (centerY - y) / centerY
    return Math.max(-1, Math.min(1, normalized))
  }

  // Absolute mode: map y to offset on activation scale
  const normalized = (centerY - y) / centerY
  const range = maxActivation.value
  return Math.max(-range, Math.min(range, normalized * range))
}

/** Coalesce canvas redraws to once per animation frame (prevents main-thread blocking → audio clicks) */
function scheduleRedraw() {
  if (rafPending) return
  rafPending = true
  requestAnimationFrame(() => {
    rafPending = false
    drawSpectralStrip()
  })
}

function onSpectralMouseDown(e: MouseEvent) {
  if (e.button === 2) return // right-click handled by contextmenu
  const canvas = spectralCanvasRef.value
  if (!canvas) return
  pushUndo()
  isDragging = true
  const dim = dimAtX(canvas, e.clientX)
  if (dim !== null) {
    lockedDim = dim // lock to this dimension — no cross-painting
    const off = offsetAtY(canvas, e.clientY)
    dimensionOffsets[dim] = off
    scheduleRedraw()
  }
}

function onSpectralMouseMove(e: MouseEvent) {
  const canvas = spectralCanvasRef.value
  if (!canvas) return

  const acts = embeddingStats.value?.all_activations
  if (!acts?.length) return

  const rect = canvas.getBoundingClientRect()
  const x = e.clientX - rect.left
  const idx = Math.floor(x / (rect.width / acts.length))

  // Update hover info
  if (idx >= 0 && idx < acts.length) {
    const entry = acts[idx]!
    hoveredDim.value = {
      dim: entry.dim,
      activation: entry.value,
      offset: dimensionOffsets[entry.dim] ?? 0,
    }
  } else {
    hoveredDim.value = null
  }

  // Adjust locked dimension only (no cross-painting)
  if (isDragging && lockedDim !== null) {
    const off = offsetAtY(canvas, e.clientY)
    dimensionOffsets[lockedDim] = off
    scheduleRedraw()
  }
}

function onSpectralMouseUp() {
  isDragging = false
  lockedDim = null
  hoveredDim.value = null
}

function onSpectralContextMenu(e: MouseEvent) {
  e.preventDefault()
  const canvas = spectralCanvasRef.value
  if (!canvas) return
  const dim = dimAtX(canvas, e.clientX)
  if (dim !== null && dim in dimensionOffsets) {
    pushUndo()
    delete dimensionOffsets[dim]
    drawSpectralStrip()
  }
}

function onSpectralTouchStart(e: TouchEvent) {
  const touch = e.touches[0]
  if (!touch || e.touches.length !== 1) return
  pushUndo()
  isDragging = true
  const canvas = spectralCanvasRef.value
  if (!canvas) return
  const dim = dimAtX(canvas, touch.clientX)
  if (dim !== null) {
    lockedDim = dim
    dimensionOffsets[dim] = offsetAtY(canvas, touch.clientY)
    scheduleRedraw()
  }
}

function onSpectralTouchMove(e: TouchEvent) {
  const touch = e.touches[0]
  if (!touch || !isDragging || e.touches.length !== 1) return
  e.preventDefault()
  const canvas = spectralCanvasRef.value
  if (!canvas) return
  if (lockedDim !== null) {
    dimensionOffsets[lockedDim] = offsetAtY(canvas, touch.clientY)
    scheduleRedraw()
  }
}

function onSpectralTouchEnd() {
  isDragging = false
  lockedDim = null
}

function onSpectralModeChange(mode: SpectralMode) {
  if (mode === spectralMode.value) return
  // Clear offsets when switching modes — values have different semantics
  pushUndo()
  Object.keys(dimensionOffsets).forEach(k => delete dimensionOffsets[Number(k)])
  spectralMode.value = mode
  drawSpectralStrip()
}

function resetAllOffsets() {
  pushUndo()
  Object.keys(dimensionOffsets).forEach(k => delete dimensionOffsets[Number(k)])
  drawSpectralStrip()
  runSynth()
}

// Redraw canvas when stats change
watch(embeddingStats, () => {
  nextTick(drawSpectralStrip)
})

watch(spectralMode, () => {
  nextTick(drawSpectralStrip)
})

/** Deterministic fingerprint of all generation-affecting synth params */
function synthFingerprint(): string {
  return JSON.stringify([
    synth.promptA, synth.promptB, synth.alpha, synth.magnitude,
    synth.noise, synth.duration, synth.startPosition, synth.steps, synth.cfg, synth.seed,
    axisSlots.map(s => [s.axis, s.value]),
    spectralMode.value,
    dimensionOffsets,
  ])
}

function clearResults() {
  error.value = ''
  resultAudio.value = ''
  resultSeed.value = null
  generationTimeMs.value = null
  cosineSimilarity.value = null
  embeddingStats.value = null
}

function handleImageUpload(data: any) {
  imagePath.value = data.image_path
  imagePreview.value = data.preview_url
}

// ===== Clipboard handlers =====

// Synth Prompt A
function copySynthPromptA() { copyToClipboard(synth.promptA) }
function pasteSynthPromptA() { synth.promptA = pasteFromClipboard() }
function clearSynthPromptA() { synth.promptA = '' }

// Synth Prompt B
function copySynthPromptB() { copyToClipboard(synth.promptB) }
function pasteSynthPromptB() { synth.promptB = pasteFromClipboard() }
function clearSynthPromptB() { synth.promptB = '' }

// MMAudio Prompt
function copyMMAudioPrompt() { copyToClipboard(mmaudio.prompt) }
function pasteMMAudioPrompt() { mmaudio.prompt = pasteFromClipboard() }
function clearMMAudioPrompt() { mmaudio.prompt = '' }

// MMAudio Negative Prompt
function copyMMAudioNeg() { copyToClipboard(mmaudio.negativePrompt) }
function pasteMMAudioNeg() { mmaudio.negativePrompt = pasteFromClipboard() }
function clearMMAudioNeg() { mmaudio.negativePrompt = '' }

// Guidance Prompt
function copyGuidancePrompt() { copyToClipboard(guidance.prompt) }
function pasteGuidancePrompt() { guidance.prompt = pasteFromClipboard() }
function clearGuidancePrompt() { guidance.prompt = '' }

// Shared image (used by both MMAudio + Guidance)
function copyImage() { copyToClipboard(imagePreview.value) }
function pasteImage() {
  const content = pasteFromClipboard()
  if (content) imagePreview.value = content
}
function clearImage() {
  imagePath.value = ''
  imagePreview.value = ''
}

async function apiPost(path: string, body: Record<string, unknown>) {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(`Error ${resp.status}: ${text}`)
  }
  return resp.json()
}

function base64ToDataUrl(b64: string, mime: string): string {
  return `data:${mime};base64,${b64}`
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function dimBarWidth(value: number): string {
  if (!embeddingStats.value?.top_dimensions?.length) return '0%'
  const maxVal = embeddingStats.value.top_dimensions[0]?.value ?? 0
  return maxVal > 0 ? `${(value / maxVal) * 100}%` : '0%'
}

function formatTranspose(semitones: number): string {
  if (semitones === 0) return '0'
  return semitones > 0 ? `+${semitones}` : `${semitones}`
}


function onTransposeInput(event: Event) {
  const val = parseInt((event.target as HTMLInputElement).value)
  looper.setTranspose(val)
}

function onLoopStartInput(event: Event) {
  const val = parseFloat((event.target as HTMLInputElement).value)
  looper.setLoopStart(val)
  drawWaveform()
}

function onLoopEndInput(event: Event) {
  const val = parseFloat((event.target as HTMLInputElement).value)
  looper.setLoopEnd(val)
  drawWaveform()
}

function onCrossfadeInput(event: Event) {
  const val = parseInt((event.target as HTMLInputElement).value)
  looper.setCrossfade(val)
}

function onNormalizeChange(event: Event) {
  looper.setNormalize((event.target as HTMLInputElement).checked)
}

function onOptimizeChange(event: Event) {
  looper.setLoopOptimize((event.target as HTMLInputElement).checked)
}
// ===== Transport State Machine Actions =====

/** Start audio output with the active engine. */
function transportPlay() {
  if (!hasLoadedAudio.value) return
  if (engineMode.value === 'looper') {
    looper.setLoop(loopMode.value !== 'oneshot')
    looper.setLoopPingPong(loopMode.value === 'pingpong')
    looper.replay()
  } else {
    if (wavetableOsc.hasFrames.value) {
      wavetableOsc.start()
      // Trigger scan sweep if ADR configured (deferred if worklet not yet ready)
      if (wtScanAttack.value > 0 || wtScanDecay.value > 0) {
        wavetableOsc.triggerScanEnvelope(
          wtScanAttack.value, wtScanDecay.value,
          mappedScanPosition(0), mappedScanPosition(1),
        )
      }
    }
  }
  if (sequencerEnabled.value && !sequencer.isPlaying.value) {
    wireEnvelope()
    wireSequencerCallbacks()
    const ac = looper.getContext()
    sequencer.start(ac)
  }
  transport.value = 'playing'
}

/** Pause audio output (keeps audio loaded). */
function transportStop() {
  sequencer.stop()
  arpeggiator.stop()
  if (engineMode.value === 'looper') {
    looper.stop()
  } else {
    wavetableOsc.stopScanEnvelope(wtScanRelease.value, mappedScanPosition(0))
    wavetableOsc.stop()
  }
  transport.value = 'paused'
}

/** Switch engine mode with mutual exclusion. */
function setEngineMode(mode: EngineMode) {
  if (mode === engineMode.value) return
  const wasPlaying = transport.value === 'playing'

  // Stop current engine
  sequencer.stop()
  arpeggiator.stop()
  looper.stop()
  wavetableOsc.stop()

  engineMode.value = mode

  if (mode === 'wavetable') {
    const ac = looper.getContext()
    wavetableOsc.setContext(ac)
    if (!envelopeWired) wireEnvelope()
  }

  // Resume if was playing and new engine has audio
  if (wasPlaying && hasLoadedAudio.value) {
    transportPlay()
  } else {
    transport.value = hasLoadedAudio.value ? 'paused' : 'idle'
  }
}

/** Set loop mode (oneshot/loop/pingpong). */
function setLoopMode(mode: LoopMode) {
  loopMode.value = mode
  looper.setLoop(mode !== 'oneshot')
  looper.setLoopPingPong(mode === 'pingpong')
}

/** Toggle sequencer section visibility. */
function setSequencerEnabled(on: boolean) {
  sequencerEnabled.value = on
  if (!on && sequencer.isPlaying.value) {
    sequencer.stop()
    arpeggiator.stop()
  }
  if (on && transport.value === 'playing') {
    wireEnvelope()
    wireSequencerCallbacks()
    const ac = looper.getContext()
    sequencer.start(ac)
  }
}

/** Trigger the active synthesis engine for a given note + velocity (MIDI/sequencer). */
function triggerEngine(note: number, velocity: number) {
  wireEnvelope()
  const semitones = note - MIDI_REF_NOTE
  if (engineMode.value === 'looper') {
    looper.setTranspose(semitones)
    if (looper.hasAudio.value) looper.retrigger()
  } else {
    wavetableOsc.setFrequencyFromNote(note)
    if (!wavetableOsc.isPlaying.value && wavetableOsc.hasFrames.value) {
      wavetableOsc.start()
    }
    // Re-trigger scan envelope on every note-on (like ADSR re-triggers)
    if (wtScanAttack.value > 0 || wtScanDecay.value > 0) {
      wavetableOsc.triggerScanEnvelope(
        wtScanAttack.value, wtScanDecay.value,
        mappedScanPosition(0), mappedScanPosition(1),
      )
    }
  }
  modulation.triggerAttack(velocity)
}

/**
 * Build a semantic wavetable by generating N ultra-short samples along a
 * semantic axis. Each sample produces one single-cycle frame. The axis
 * position becomes the wavetable scan position.
 */
async function buildSemanticWavetable() {
  if (!wtBuildAxis.value || wtBuilding.value) return

  const axisName = wtBuildAxis.value
  const n = wtBuildFrameCount.value
  wtBuilding.value = true
  wtBuildProgress.value = 0
  wtBuildProgressCurrent.value = 0

  const rawFrames: Float32Array[] = []
  const axisMeta = getAxisMeta(axisName)

  try {
    for (let i = 0; i < n; i++) {
      // Sweep axis from -1 to +1
      const t = n === 1 ? 0 : (i / (n - 1)) * 2 - 1

      const body: Record<string, unknown> = {
        prompt_a: 'sound',
        alpha: 0.5,
        magnitude: 1.0,
        noise_sigma: 0.0,
        duration_seconds: 0.1,
        start_position: 0.0,
        steps: 20,
        cfg_scale: synth.cfg,
        seed: 42 + i, // Deterministic but varied per frame
        axes: { [axisName]: t },
      }

      const result = await apiPost('/api/cross_aesthetic/synth', body)

      if (result.success && result.audio_base64) {
        // Decode WAV → AudioBuffer → extract one cycle
        const wavBytes = Uint8Array.from(atob(result.audio_base64), c => c.charCodeAt(0))
        const ac = looper.getContext()
        const audioBuffer = await ac.decodeAudioData(wavBytes.buffer.slice(0))
        const mono = audioBuffer.getChannelData(0)

        // Take a single cycle from the middle of the sample (avoids edge artifacts)
        const mid = Math.floor(mono.length / 2)
        const cycleLen = Math.min(2048, Math.floor(mono.length / 2))
        const start = Math.max(0, mid - Math.floor(cycleLen / 2))
        const frame = mono.slice(start, start + cycleLen)
        rawFrames.push(frame)
      }

      wtBuildProgressCurrent.value = i + 1
      wtBuildProgress.value = Math.round(((i + 1) / n) * 100)
    }

    if (rawFrames.length > 0) {
      wavetableOsc.loadRawFrames(rawFrames)
      wtRangeStart.value = 0
      wtRangeEnd.value = wavetableOsc.frameCount.value

      // Auto-switch to wavetable engine and start playing
      if (engineMode.value !== 'wavetable') setEngineMode('wavetable')
      if (transport.value !== 'playing') transportPlay()
    }
  } catch (e) {
    error.value = `Wavetable build failed: ${e}`
  } finally {
    wtBuilding.value = false
  }
}

// toggleSequencerSection replaced by setSequencerEnabled above

/** Map user scan (0–1) to actual scanPosition within clamped range. */
function mappedScanPosition(userScan: number): number {
  const total = wavetableOsc.frameCount.value
  if (total <= 1) return 0
  const startFrac = wtRangeStart.value / total
  const endFrac = (wtRangeEnd.value - 1) / total
  return startFrac + userScan * (endFrac - startFrac)
}

function onScanInput(event: Event) {
  const val = parseFloat((event.target as HTMLInputElement).value)
  wavetableScan.value = val
  wavetableOsc.setScanPosition(mappedScanPosition(val))
}

watch(wavetableScan, (v) => {
  wavetableOsc.setScanPosition(mappedScanPosition(v))
})

function onWtInterpolateChange(event: Event) {
  wtInterpolate.value = (event.target as HTMLInputElement).checked
  wavetableOsc.setInterpolate(wtInterpolate.value)
}

// ===== Sequencer transport =====
function wireSequencerCallbacks() {
  sequencer.setCallbacks(
    // noteOn: retrigger active engine at new pitch, through arpeggiator
    (note, velocity) => {
      const octNote = note + seqOctave.value * 12 + seqKeyTranspose.value
      arpeggiator.processNote(octNote, velocity, (n, v) => {
        triggerEngine(n, v)
      }, () => {
        modulation.triggerRelease()
      })
    },
    // noteOff: stop arpeggiator, fire ADSR release
    () => {
      arpeggiator.stop()
      modulation.triggerRelease()
    },
  )
}

function toggleSequencer() {
  if (sequencer.isPlaying.value) {
    sequencer.stop()
    modulation.triggerRelease()
    return
  }
  wireEnvelope()
  wireSequencerCallbacks()
  const ac = looper.getContext()
  sequencer.start(ac)
}

function onBpmInput(event: Event) {
  const val = parseInt((event.target as HTMLInputElement).value)
  sequencer.setBpm(val)
}

function onPresetChange(event: Event) {
  const idx = parseInt((event.target as HTMLSelectElement).value)
  if (idx >= 0) sequencer.loadPreset(idx)
}

function onStepSemitoneInput(idx: number, event: Event) {
  const val = parseInt((event.target as HTMLInputElement).value)
  sequencer.setStepSemitone(idx, val)
}

function onStepVelocityInput(idx: number, event: Event) {
  const val = parseFloat((event.target as HTMLInputElement).value)
  sequencer.setStepVelocity(idx, val)
}

// Stop engines + sequencer when navigating away from synth tab
watch(activeTab, (tab) => {
  if (tab !== 'synth') {
    transport.value = 'idle'
    sequencer.stop()
    arpeggiator.stop()
    looper.stop()
    wavetableOsc.stop()
  }
})

// ADSR values take effect on next note-on (no mid-note re-trigger — causes clicks)

function onMidiInputChange(event: Event) {
  const val = (event.target as HTMLSelectElement).value
  midi.selectInput(val || null)
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function downloadResultAudio() {
  if (!resultAudio.value) return
  const a = document.createElement('a')
  a.href = resultAudio.value
  const prefix = activeTab.value === 'mmaudio' ? 'mmaudio' : 'imagebind'
  a.download = `${prefix}_${resultSeed.value ?? 0}.wav`
  a.click()
}

function saveRaw() {
  const blob = looper.exportRaw()
  if (!blob) return
  downloadBlob(blob, `synth_raw_${resultSeed.value ?? 0}.wav`)
}

function saveLoop() {
  const blob = looper.exportLoop()
  if (!blob) return
  downloadBlob(blob, `synth_loop_${resultSeed.value ?? 0}.wav`)
}

// ===== Preset Export/Import =====

const PRESET_VERSION = 1

interface SynthPreset {
  version: number
  name: string
  timestamp: string
  synth: {
    promptA: string
    promptB: string
    alpha: number
    magnitude: number
    noise: number
    duration: number
    startPosition: number
    steps: number
    cfg: number
    seed: number
  }
  dimExplorer: {
    spectralMode: SpectralMode
    offsets: Record<string, number>
  }
  axes: Array<{ axis: string; value: number }>
  engine: {
    mode: EngineMode
    loopMode: LoopMode
    loopStartFrac: number
    loopEndFrac: number
    loopOptimize: boolean
    crossfadeMs: number
  }
  envelope: {
    attackMs: number
    decayMs: number
    sustain: number
    releaseMs: number
  }
  effects: {
    delayEnabled: boolean
    delayTimeMs: number
    delayFeedback: number
    delayMix: number
    reverbEnabled: boolean
    reverbMix: number
    reverbVariant: string
  }
  sequencer: {
    enabled: boolean
    bpm: number
    stepCount: number
    division: string
    steps: Array<{ active: boolean; semitone: number; velocity: number; gate: number }>
  }
  arpeggiator: {
    enabled: boolean
    pattern: string
    rate: string
    octaveRange: number
  }
  filter?: {
    enabled: boolean
    type: string
    cutoff: number
    resonance: number
    envAttackMs: number
    envDecayMs: number
    envSustain: number
    envReleaseMs: number
    envAmount: number
    lfo1: { enabled: boolean; rate: number; depth: number; waveform: string; target: string }
    lfo2: { enabled: boolean; rate: number; depth: number; waveform: string; target: string }
  }
}

function exportPreset() {
  const preset: SynthPreset = {
    version: PRESET_VERSION,
    name: `${synth.promptA.slice(0, 30)}`,
    timestamp: new Date().toISOString(),
    synth: {
      promptA: synth.promptA,
      promptB: synth.promptB,
      alpha: synth.alpha,
      magnitude: synth.magnitude,
      noise: synth.noise,
      duration: synth.duration,
      startPosition: synth.startPosition,
      steps: synth.steps,
      cfg: synth.cfg,
      seed: synth.seed,
    },
    dimExplorer: {
      spectralMode: spectralMode.value,
      offsets: { ...dimensionOffsets },
    },
    axes: axisSlots.map(s => ({ axis: s.axis, value: s.value })),
    engine: {
      mode: engineMode.value,
      loopMode: loopMode.value,
      loopStartFrac: looper.loopStartFrac.value,
      loopEndFrac: looper.loopEndFrac.value,
      loopOptimize: looper.loopOptimize.value,
      crossfadeMs: looper.crossfadeMs.value,
    },
    envelope: {
      attackMs: modulation.envs[0]!.attackMs.value,
      decayMs: modulation.envs[0]!.decayMs.value,
      sustain: modulation.envs[0]!.sustain.value,
      releaseMs: modulation.envs[0]!.releaseMs.value,
    },
    effects: {
      delayEnabled: effects.delayEnabled.value,
      delayTimeMs: effects.delayTimeMs.value,
      delayFeedback: effects.delayFeedback.value,
      delayMix: effects.delayMix.value,
      reverbEnabled: effects.reverbEnabled.value,
      reverbMix: effects.reverbMix.value,
      reverbVariant: effects.reverbVariant.value,
    },
    sequencer: {
      enabled: sequencerEnabled.value,
      bpm: sequencer.bpm.value,
      stepCount: sequencer.stepCount.value,
      division: sequencer.division.value,
      steps: sequencer.steps.map(s => ({
        active: s.active, semitone: s.semitone, velocity: s.velocity, gate: s.gate,
      })),
    },
    arpeggiator: {
      enabled: arpeggiator.enabled.value,
      pattern: arpeggiator.pattern.value,
      rate: arpeggiator.rate.value,
      octaveRange: arpeggiator.octaveRange.value,
    },
    filter: {
      enabled: filter.enabled.value,
      type: filter.type.value,
      cutoff: filter.cutoff.value,
      resonance: filter.resonance.value,
      mix: filter.mix.value,
      kbdTrack: filter.kbdTrack.value,
    } as any,
  }

  const json = JSON.stringify(preset, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const safeName = synth.promptA.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 40)
  downloadBlob(blob, `synth_preset_${safeName}.json`)
}

async function importPreset(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = '' // allow re-import of same file

  try {
    const text = await file.text()
    const preset: SynthPreset = JSON.parse(text)

    if (!preset.version || !preset.synth?.promptA) {
      error.value = 'Invalid preset file'
      return
    }

    // Restore synth params
    synth.promptA = preset.synth.promptA
    synth.promptB = preset.synth.promptB ?? ''
    synth.alpha = preset.synth.alpha ?? 0
    synth.magnitude = preset.synth.magnitude ?? 1
    synth.noise = preset.synth.noise ?? 0
    synth.duration = preset.synth.duration ?? 3
    synth.startPosition = preset.synth.startPosition ?? 0
    synth.steps = preset.synth.steps ?? 20
    synth.cfg = preset.synth.cfg ?? 7
    synth.seed = preset.synth.seed ?? -1

    // Restore dimension explorer
    if (preset.dimExplorer) {
      spectralMode.value = preset.dimExplorer.spectralMode ?? 'relative'
      Object.keys(dimensionOffsets).forEach(k => delete dimensionOffsets[Number(k)])
      if (preset.dimExplorer.offsets) {
        for (const [k, v] of Object.entries(preset.dimExplorer.offsets)) {
          dimensionOffsets[Number(k)] = v
        }
      }
    }

    // Restore axes
    if (preset.axes) {
      for (let i = 0; i < axisSlots.length; i++) {
        const saved = preset.axes[i]
        if (saved) {
          axisSlots[i]!.axis = saved.axis
          axisSlots[i]!.value = saved.value
        } else {
          axisSlots[i]!.axis = ''
          axisSlots[i]!.value = 0
        }
      }
    }

    // Restore engine settings
    if (preset.engine) {
      loopMode.value = preset.engine.loopMode ?? 'oneshot'
      looper.setLoopStart(preset.engine.loopStartFrac ?? 0)
      looper.setLoopEnd(preset.engine.loopEndFrac ?? 1)
      looper.setLoopOptimize(preset.engine.loopOptimize ?? false)
      looper.setCrossfade(preset.engine.crossfadeMs ?? 150)
    }

    // Restore envelope
    if (preset.envelope) {
      modulation.envs[0]!.attackMs.value = preset.envelope.attackMs ?? 0
      modulation.envs[0]!.decayMs.value = preset.envelope.decayMs ?? 0
      modulation.envs[0]!.sustain.value = preset.envelope.sustain ?? 1
      modulation.envs[0]!.releaseMs.value = preset.envelope.releaseMs ?? 0
    }

    // Restore effects
    if (preset.effects) {
      effects.setDelayEnabled(preset.effects.delayEnabled ?? false)
      effects.setDelayTime(preset.effects.delayTimeMs ?? 250)
      effects.setDelayFeedback(preset.effects.delayFeedback ?? 0.3)
      effects.setDelayMix(preset.effects.delayMix ?? 0.3)
      effects.setReverbEnabled(preset.effects.reverbEnabled ?? false)
      effects.setReverbMix(preset.effects.reverbMix ?? 0.3)
      if (preset.effects.reverbVariant) {
        effects.setReverbVariant(preset.effects.reverbVariant as PlateVariant)
      }
    }

    // Restore sequencer
    if (preset.sequencer) {
      sequencerEnabled.value = preset.sequencer.enabled ?? false
      sequencer.setBpm(preset.sequencer.bpm ?? 120)
      sequencer.setStepCount(preset.sequencer.stepCount as any ?? 8)
      sequencer.setDivision(preset.sequencer.division as any ?? '1/8')
      if (preset.sequencer.steps) {
        for (let i = 0; i < preset.sequencer.steps.length && i < sequencer.steps.length; i++) {
          const s = preset.sequencer.steps[i]!
          sequencer.setStepActive(i, s.active)
          sequencer.setStepSemitone(i, s.semitone)
          sequencer.setStepVelocity(i, s.velocity)
          sequencer.setStepGate(i, s.gate)
        }
      }
    }

    // Restore arpeggiator
    if (preset.arpeggiator) {
      arpeggiator.setEnabled(preset.arpeggiator.enabled ?? false)
      arpeggiator.setPattern(preset.arpeggiator.pattern as any ?? 'up')
      arpeggiator.setRate(preset.arpeggiator.rate as any ?? '1/8')
      arpeggiator.setOctaveRange(preset.arpeggiator.octaveRange ?? 2)
    }

    // Restore filter (pure filter — modulators are in the modulation bank)
    if (preset.filter) {
      filter.setType(preset.filter.type as FilterType ?? 'lowpass')
      filter.setCutoff(preset.filter.cutoff ?? 1)
      filter.setResonance(preset.filter.resonance ?? 0.7)
      if ('mix' in preset.filter) filter.setMix((preset.filter as any).mix ?? 1)
      if ('kbdTrack' in preset.filter) filter.setKbdTrack((preset.filter as any).kbdTrack ?? 0)
      filter.setEnabled(preset.filter.enabled ?? false)
    }

    // Regenerate audio with restored params
    await runSynth()

    // Restore engine mode after generation (wavetable needs frames)
    if (preset.engine?.mode === 'wavetable' && wavetableOsc.hasFrames.value) {
      setEngineMode('wavetable')
    }
  } catch (e) {
    error.value = `Preset import failed: ${(e as Error).message}`
  }
}

/** Encode AudioBuffer region as WAV Blob (16-bit PCM). */
function audioBufferToWav(buffer: AudioBuffer, startSample: number, endSample: number): Blob {
  const nc = buffer.numberOfChannels, sr = buffer.sampleRate
  const len = endSample - startSample, ds = len * nc * 2
  const ab = new ArrayBuffer(44 + ds), v = new DataView(ab)
  const ws = (o: number, s: string) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)) }
  ws(0, 'RIFF'); v.setUint32(4, 36 + ds, true); ws(8, 'WAVE'); ws(12, 'fmt ')
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, nc, true)
  v.setUint32(24, sr, true); v.setUint32(28, sr * nc * 2, true)
  v.setUint16(32, nc * 2, true); v.setUint16(34, 16, true); ws(36, 'data'); v.setUint32(40, ds, true)
  const chs: Float32Array[] = []
  for (let c = 0; c < nc; c++) chs.push(buffer.getChannelData(c))
  let off = 44
  for (let i = startSample; i < endSample; i++) {
    for (let c = 0; c < nc; c++) {
      const s = Math.max(-1, Math.min(1, chs[c]![i]!))
      v.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true); off += 2
    }
  }
  return new Blob([ab], { type: 'audio/wav' })
}

// ===== Synth =====
async function runSynth() {
  // Track pre-generation state to restore after completion
  preGenTransport = transport.value === 'generating'
    ? preGenTransport
    : (transport.value === 'playing' ? 'playing' : 'idle')
  error.value = ''
  resultSeed.value = null
  generationTimeMs.value = null

  // Snapshot A/B reference values before clearing stats (needed for relative→offset conversion)
  const prevStats = embeddingStats.value
  embeddingStats.value = null
  transport.value = 'generating'
  try {
    // Build request body — always /synth, axes included when active
    const body: Record<string, unknown> = {
      prompt_a: synth.promptA,
      alpha: synth.alpha / 2 + 0.5,
      magnitude: synth.magnitude,
      noise_sigma: synth.noise,
      duration_seconds: synth.duration,
      start_position: synth.startPosition,
      steps: synth.steps,
      cfg_scale: synth.cfg,
      seed: synth.seed,
    }
    if (synth.promptB.trim()) {
      body.prompt_b = synth.promptB
    }

    // Collect non-zero dimension offsets, converting from relative mix factors if needed
    const nonZeroOffsets: Record<string, number> = {}
    const isRelative = spectralMode.value === 'relative'
      && !!(prevStats?.emb_a_values && prevStats?.emb_b_values)
    const embAVals = prevStats?.emb_a_values
    const embBVals = prevStats?.emb_b_values
    const acts = prevStats?.all_activations

    for (const [k, v] of Object.entries(dimensionOffsets)) {
      if (v === 0) continue
      if (isRelative && embAVals && embBVals && acts) {
        // Convert mix factor to actual offset: delta needed to move activation toward A or B
        const dim = Number(k)
        const actEntry = acts.find(a => a.dim === dim)
        const currentVal = actEntry?.value ?? 0
        const aVal = embAVals[dim] ?? 0
        const bVal = embBVals[dim] ?? 0
        const targetVal = v > 0
          ? currentVal + Math.abs(v) * (aVal - currentVal)
          : currentVal + Math.abs(v) * (bVal - currentVal)
        const offset = targetVal - currentVal
        if (Math.abs(offset) > 0.0001) nonZeroOffsets[k] = offset
      } else {
        nonZeroOffsets[k] = v
      }
    }
    if (Object.keys(nonZeroOffsets).length > 0) {
      body.dimension_offsets = nonZeroOffsets
    }

    // Collect active semantic axes (only those moved away from center)
    const activeAxes: Record<string, number> = {}
    for (const slot of axisSlots) {
      if (slot.axis && Math.abs(slot.value) > 0.001) {
        activeAxes[slot.axis] = slot.value
      }
    }
    if (Object.keys(activeAxes).length > 0) {
      body.axes = activeAxes
    }

    const result = await apiPost('/api/cross_aesthetic/synth', body)

    // Store axis contributions for drawbar coloring
    axisContributions.value = result.success && result.axis_contributions
      ? result.axis_contributions
      : []

    if (result.success) {
      lastSynthBase64.value = result.audio_base64
      resultAudio.value = base64ToDataUrl(result.audio_base64, 'audio/wav')
      resultSeed.value = result.seed
      generationTimeMs.value = result.generation_time_ms
      embeddingStats.value = result.embedding_stats

      // Load audio into looper (always, for buffer access)
      looper.setLoop(loopMode.value !== 'oneshot')
      await looper.play(result.audio_base64)
      nextTick(drawWaveform)
      lastSynthFingerprint.value = synthFingerprint()

      // Extract wavetable frames from the new buffer
      const buf = looper.getOriginalBuffer()
      if (buf) {
        await wavetableOsc.loadFrames(buf)
        wtRangeStart.value = 0
        wtRangeEnd.value = wavetableOsc.frameCount.value
      }

      // Enforce correct engine mode
      if (engineMode.value === 'wavetable') {
        looper.stop()
        const ac = looper.getContext()
        wavetableOsc.setContext(ac)
        if (!envelopeWired) wireEnvelope()
        if (wavetableOsc.hasFrames.value) await wavetableOsc.start()
      }

      // Restore transport: play if was playing or first generation
      if (preGenTransport === 'playing' || preGenTransport === 'idle') {
        transport.value = 'playing'
      } else {
        // User had paused — load but don't play
        if (engineMode.value === 'looper') looper.stop()
        else wavetableOsc.stop()
        transport.value = 'paused'
      }

      // Record for research export
      labRecord({
        parameters: {
          tab: 'synth', prompt_a: synth.promptA, prompt_b: synth.promptB,
          alpha: synth.alpha / 2 + 0.5, magnitude: synth.magnitude, noise_sigma: synth.noise,
          ...(Object.keys(activeAxes).length > 0 ? { axes: activeAxes } : {}),
          duration: synth.duration, start_position: synth.startPosition, steps: synth.steps, cfg: synth.cfg, seed: synth.seed,
        },
        results: { seed: result.seed, generation_time_ms: result.generation_time_ms },
        outputs: [{ type: 'audio', format: 'wav', dataBase64: result.audio_base64 }],
      })
    } else {
      error.value = result.error || 'Synth generation failed'
      transport.value = preGenTransport === 'playing' ? 'playing' : 'idle'
    }
  } catch (e) {
    error.value = String(e)
    transport.value = preGenTransport === 'playing' ? 'playing' : 'idle'
  }
}

// ===== MMAudio =====
async function runMMAudio() {
  clearResults()
  transport.value = 'generating'
  try {
    const body: Record<string, unknown> = {
      prompt: mmaudio.prompt,
      negative_prompt: mmaudio.negativePrompt,
      duration_seconds: mmaudio.duration,
      cfg_strength: mmaudio.cfg,
      num_steps: mmaudio.steps,
      seed: mmaudio.seed,
    }
    if (imagePath.value) {
      body.image_path = imagePath.value
    }

    const result = await apiPost('/api/cross_aesthetic/mmaudio', body)
    if (result.success) {
      resultAudio.value = base64ToDataUrl(result.audio_base64, 'audio/wav')
      resultSeed.value = result.seed
      generationTimeMs.value = result.generation_time_ms

      labRecord({
        parameters: { tab: 'mmaudio', prompt: mmaudio.prompt, negative_prompt: mmaudio.negativePrompt,
          duration: mmaudio.duration, cfg: mmaudio.cfg, steps: mmaudio.steps, seed: mmaudio.seed,
          has_image: !!imagePath.value },
        results: { seed: result.seed, generation_time_ms: result.generation_time_ms },
        outputs: [{ type: 'audio', format: 'wav', dataBase64: result.audio_base64 }],
      })
    } else {
      error.value = result.error || 'MMAudio generation failed'
    }
  } catch (e) {
    error.value = String(e)
  } finally {
    transport.value = 'idle'
  }
}

// ===== ImageBind Guidance =====
async function runGuidance() {
  clearResults()
  transport.value = 'generating'
  try {
    const result = await apiPost('/api/cross_aesthetic/image_guided_audio', {
      image_path: imagePath.value,
      prompt: guidance.prompt,
      lambda_guidance: guidance.lambda,
      warmup_steps: guidance.warmupSteps,
      total_steps: guidance.totalSteps,
      duration_seconds: guidance.duration,
      cfg_scale: guidance.cfg,
      seed: guidance.seed,
    })
    if (result.success) {
      resultAudio.value = base64ToDataUrl(result.audio_base64, 'audio/wav')
      resultSeed.value = result.seed
      generationTimeMs.value = result.generation_time_ms
      cosineSimilarity.value = result.cosine_similarity ?? null

      labRecord({
        parameters: { tab: 'guidance', prompt: guidance.prompt,
          lambda: guidance.lambda, warmup_steps: guidance.warmupSteps,
          total_steps: guidance.totalSteps, duration: guidance.duration,
          cfg: guidance.cfg, seed: guidance.seed, has_image: !!imagePath.value },
        results: { seed: result.seed, generation_time_ms: result.generation_time_ms,
          cosine_similarity: result.cosine_similarity },
        outputs: [{ type: 'audio', format: 'wav', dataBase64: result.audio_base64 }],
      })
    } else {
      error.value = result.error || 'Guided generation failed'
    }
  } catch (e) {
    error.value = String(e)
  } finally {
    transport.value = 'idle'
  }
}

// Ctrl+Z / Ctrl+Shift+Z for dimension offsets undo/redo
function onKeyDown(e: KeyboardEvent) {
  if (activeTab.value !== 'synth') return
  if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
    e.preventDefault()
    undo()
  } else if ((e.ctrlKey || e.metaKey) && e.key === 'z' && e.shiftKey) {
    e.preventDefault()
    redo()
  } else if ((e.ctrlKey || e.metaKey) && e.key === 'y') {
    e.preventDefault()
    redo()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('resize', drawWaveform)
  fetchSemanticAxes()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('resize', drawWaveform)
  arpeggiator.dispose()
  sequencer.dispose()
  modulation.dispose()
  filter.dispose()
  effects.dispose()
  looper.dispose()
  wavetableOsc.dispose()
})
</script>

<style scoped>
.crossmodal-lab {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem;
  color: #ffffff;
}

/* Dark dropdown options (browser renders native popups white by default) */
.crossmodal-lab select,
.crossmodal-lab option,
.crossmodal-lab optgroup {
  background: #1a1a1a;
  color: #ffffff;
  color-scheme: dark;
}

.page-header {
  margin-bottom: 2rem;
}

.page-title {
  font-size: 1.4rem;
  font-weight: 300;
  letter-spacing: 0.05em;
  margin-bottom: 0.3rem;
}

.page-subtitle {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.85rem;
  margin: 0 0 0.75rem;
}

.explanation-details {
  background: rgba(76, 175, 80, 0.06);
  border: 1px solid rgba(76, 175, 80, 0.15);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 0.8rem;
}

.explanation-details summary {
  padding: 0.65rem 1rem;
  color: rgba(76, 175, 80, 0.8);
  font-size: 0.85rem;
  cursor: pointer;
  user-select: none;
}

.explanation-details summary:hover {
  color: #4CAF50;
}

.explanation-body {
  padding: 0 1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.explanation-section h4 {
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.85rem;
  margin: 0 0 0.25rem;
}

.explanation-section p {
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.82rem;
  line-height: 1.6;
  margin: 0;
}

.reference-list { list-style: none; padding: 0; margin: 0.5rem 0 0; }
.reference-list li { margin-bottom: 0.4rem; font-size: 0.8rem; color: rgba(255,255,255,0.6); }
.ref-authors { font-weight: 500; color: rgba(255,255,255,0.8); }
.ref-title { font-style: italic; }
.ref-venue { color: rgba(255,255,255,0.5); }
.ref-doi { color: rgba(76,175,80,0.8); text-decoration: none; margin-left: 0.3rem; }
.ref-doi:hover { text-decoration: underline; }

/* Tab Navigation */
.tab-nav {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 2rem;
}

.tab-btn {
  flex: 1;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}

.tab-btn:hover {
  background: rgba(255, 255, 255, 0.08);
}

.tab-btn.active {
  background: rgba(76, 175, 80, 0.1);
  border-color: rgba(76, 175, 80, 0.4);
  color: #ffffff;
}

.tab-label {
  font-size: 1rem;
  font-weight: 700;
  display: block;
  margin-bottom: 0.3rem;
}

.tab-short {
  font-size: 0.72rem;
  opacity: 0.7;
}

/* Tab Panels */
.tab-panel {
  padding: 1.5rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  margin-bottom: 2rem;
}

.tab-panel h3 {
  font-size: 1.1rem;
  font-weight: 500;
  margin-bottom: 0.5rem;
}

.tab-description {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.85rem;
  margin-bottom: 0.8rem;
  line-height: 1.5;
}

/* Sticky prompt + generate area */
.synth-sticky-top {
  position: sticky;
  top: 0;
  z-index: 10;
  background: #0a0a0a;
  padding-bottom: 0.5rem;
  margin: 0 -1.5rem;
  padding-left: 1.5rem;
  padding-right: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

/* Slider groups */
.slider-group {
  margin-bottom: 1rem;
}

.synth-slider-group {
  margin-top: 1rem;
}

.slider-item {
  margin-bottom: 0.6rem;
}

.slider-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.3rem;
}

.slider-header label {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.6);
}

.slider-value {
  font-size: 0.8rem;
  color: #4CAF50;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.slider-item input[type="range"] {
  width: 100%;
  accent-color: #4CAF50;
}

.slider-hint {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.35);
  display: block;
  margin-top: 0.2rem;
}

/* Params row */
.params-row {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}

.param {
  flex: 1;
  min-width: 100px;
}

.param-narrow {
  flex: 0.7;
  min-width: 70px;
}

.param-wide {
  flex: 2;
  min-width: 160px;
}

.param label {
  display: block;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 0.3rem;
}

.param input:not([type="range"]),
.param select {
  width: 100%;
  padding: 0.5rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  color: #ffffff;
  font-size: 0.85rem;
  box-sizing: border-box;
}

.param input[type="range"] {
  width: 100%;
}

.param input:not([type="range"]):focus,
.param select:focus {
  outline: none;
  border-color: rgba(76, 175, 80, 0.5);
}

.param-hint {
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.3);
  display: block;
  margin-top: 0.2rem;
}

/* Action row */
.action-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.generate-btn {
  padding: 0.8rem 2rem;
  background: rgba(76, 175, 80, 0.2);
  border: 1px solid rgba(76, 175, 80, 0.4);
  border-radius: 8px;
  color: #4CAF50;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.generate-btn:hover:not(:disabled) {
  background: rgba(76, 175, 80, 0.3);
}

.generate-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}


.play-btn {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
  background: rgba(76, 175, 80, 0.15);
  border: 1px solid rgba(76, 175, 80, 0.3);
  color: #4CAF50;
}

.play-btn:hover {
  background: rgba(76, 175, 80, 0.25);
}

/* Looper widget */
.looper-widget {
  padding: 1rem;
  background: rgba(255, 255, 255, 0.03);
  margin-bottom: 1rem;
  transition: opacity 0.2s;
}

.looper-widget.disabled {
  opacity: 0.35;
  pointer-events: none;
}

.looper-status {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.8rem;
}

.looper-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  flex-shrink: 0;
}

.looper-indicator.pulsing {
  background: #4CAF50;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 4px rgba(76, 175, 80, 0.4); }
  50% { opacity: 0.5; box-shadow: 0 0 8px rgba(76, 175, 80, 0.8); }
}

.looper-label {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.6);
}

.looper-duration {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.3);
  margin-left: auto;
  font-variant-numeric: tabular-nums;
}

/* Loop interval dual-range */
.loop-interval {
  margin-bottom: 0.8rem;
}

.waveform-loop-container {
  position: relative;
  height: 3rem;
}

.waveform-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border-radius: 4px;
}

.dual-range {
  position: relative;
  height: 1.5rem;
  top: 50%;
  transform: translateY(-50%);
}

.dual-range input[type="range"] {
  position: absolute;
  width: 100%;
  top: 0;
  pointer-events: none;
  appearance: none;
  -webkit-appearance: none;
  background: transparent;
  accent-color: #4CAF50;
}

.dual-range input[type="range"]::-webkit-slider-thumb {
  pointer-events: auto;
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #4CAF50;
  cursor: pointer;
  border: none;
}

.dual-range input[type="range"]::-moz-range-thumb {
  pointer-events: auto;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #4CAF50;
  cursor: pointer;
  border: none;
}

.dual-range input[type="range"]::-webkit-slider-runnable-track {
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.dual-range input[type="range"]::-moz-range-track {
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.transpose-row {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}

.transpose-row label {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
}

.transpose-row input[type="range"] {
  flex: 1;
  accent-color: #4CAF50;
}

.transpose-value {
  font-size: 0.8rem;
  color: #4CAF50;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  min-width: 2.5rem;
  text-align: right;
}

/* Loop options / Transpose mode */
.loop-options {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.3rem;
}

.optimized-hint {
  font-size: 0.7rem;
  color: #4CAF50;
  font-variant-numeric: tabular-nums;
}

.transpose-mode-row {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.6rem;
}

.inline-toggle {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
}

.inline-toggle.active {
  color: #4CAF50;
}

.inline-toggle input[type="checkbox"],
.inline-toggle input[type="radio"] {
  accent-color: #4CAF50;
}

/* Normalize row */
.normalize-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.6rem;
  margin-bottom: 0.4rem;
}

.normalize-toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
}

.normalize-toggle input[type="checkbox"] {
  accent-color: #4CAF50;
}

.peak-display {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.3);
  font-variant-numeric: tabular-nums;
}

/* Save buttons */
.save-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.8rem;
}

.save-separator {
  width: 1px;
  height: 1.2rem;
  background: rgba(255, 255, 255, 0.12);
}

.save-btn {
  padding: 0.4rem 0.8rem;
  font-size: 0.75rem;
  border-radius: 5px;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.6);
  transition: all 0.2s;
}

.save-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
}

/* MIDI section */
.midi-section {
  margin-top: 1rem;
}

.midi-section summary {
  background: rgba(255, 255, 255, 0.03);
}

.midi-content {
  padding: 1rem;
}

.midi-unsupported {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.35);
  font-style: italic;
}

.midi-input-select {
  margin-bottom: 1rem;
}

.midi-input-select label {
  display: block;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 0.3rem;
}

.midi-input-select select {
  width: 100%;
  padding: 0.5rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  color: #ffffff;
  font-size: 0.85rem;
}

.midi-mapping-table h5 {
  font-size: 0.75rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 0.5rem;
}

.midi-mapping-table table {
  width: 100%;
  font-size: 0.75rem;
  border-collapse: collapse;
}

.midi-mapping-table td {
  padding: 0.3rem 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.5);
}

.midi-mapping-table td:first-child {
  color: #4CAF50;
  font-weight: 600;
  width: 5rem;
}

/* Output area */
.output-area {
  padding: 1.5rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
}

.error-message {
  color: #ff5252;
  font-size: 0.85rem;
  padding: 0.8rem;
  background: rgba(255, 82, 82, 0.1);
  border-radius: 6px;
  margin-bottom: 1rem;
}

.output-section {
  margin-top: 1rem;
}

.result-meta {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.meta-item {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
}

/* Embedding stats */
.embedding-stats {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.embedding-stats h4 {
  font-size: 0.85rem;
  font-weight: 500;
  margin-bottom: 0.5rem;
  color: rgba(255, 255, 255, 0.6);
}

.stats-grid {
  display: flex;
  gap: 1.5rem;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 0.8rem;
}

.top-dims {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.dim-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  height: 1.2rem;
}

.dim-label {
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.4);
  width: 2.5rem;
  text-align: right;
  flex-shrink: 0;
}

.dim-fill {
  height: 0.5rem;
  background: rgba(76, 175, 80, 0.4);
  border-radius: 2px;
  min-width: 2px;
  transition: width 0.3s;
}

.dim-value {
  font-size: 0.6rem;
  color: rgba(255, 255, 255, 0.3);
  flex-shrink: 0;
}

/* Shared collapsible section style */
.lab-section {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  overflow: hidden;
}

.lab-section summary {
  padding: 0.7rem 1rem;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  font-weight: 500;
}

.lab-section summary:hover {
  color: rgba(255, 255, 255, 0.7);
}

/* Section action bars (Semantic Axes + Dim Explorer) */
.section-action-bar {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  margin-top: 0.5rem;
  flex-wrap: wrap;
}

.action-icon {
  width: 18px;
  height: 18px;
  vertical-align: middle;
  opacity: 0.7;
}

/* Dimension Explorer */
.dim-explorer-section {
  margin-top: 0.8rem;
  padding: 0.6rem;
}


.dim-explorer-content {
  margin-top: 0.6rem;
}

.dim-mode-toggle {
  border-top: none;
  padding: 0.3rem 0 0;
}

.dim-hint {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.35);
  margin-bottom: 0.5rem;
}

.spectral-strip-container {
  position: relative;
  height: 120px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 4px;
  overflow: hidden;
}

.spectral-canvas {
  width: 100%;
  height: 100%;
  cursor: crosshair;
  display: block;
}

.spectral-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.2);
  pointer-events: none;
}

.dim-info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 1.2rem;
  margin-top: 0.3rem;
  padding: 0 0.2rem;
}

.dim-hover-info {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.5);
  font-variant-numeric: tabular-nums;
  font-family: monospace;
}

.dim-sort-mode {
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.25);
}


.dim-control-group {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.dim-control-group label {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.4);
}

.dim-topn-input {
  width: 3rem;
  padding: 0.2rem 0.3rem;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
  color: #fff;
  font-size: 0.75rem;
  text-align: center;
}

.dim-btn {
  padding: 0.25rem 0.6rem;
  background: rgba(76, 175, 80, 0.15);
  border: 1px solid rgba(76, 175, 80, 0.3);
  border-radius: 4px;
  color: #4CAF50;
  font-size: 0.7rem;
  cursor: pointer;
  transition: background 0.2s;
}

.dim-btn:hover {
  background: rgba(76, 175, 80, 0.25);
}

.dim-btn-reset {
  background: rgba(255, 152, 0, 0.1);
  border-color: rgba(255, 152, 0, 0.3);
  color: #FF9800;
}

.dim-btn-reset:hover {
  background: rgba(255, 152, 0, 0.2);
}

.dim-btn-generate {
  background: rgba(76, 175, 80, 0.25);
  border-color: rgba(76, 175, 80, 0.5);
  font-weight: 500;
}

.dim-btn-generate:hover:not(:disabled) {
  background: rgba(76, 175, 80, 0.4);
}

.dim-btn-generate:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.dim-btn-undo:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.dim-offset-status {
  font-size: 0.7rem;
  color: #4CAF50;
  font-variant-numeric: tabular-nums;
}


/* Section toggles (independent on/off sections) */
.section-toggle {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.5rem 0;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.section-toggle .inline-toggle {
  font-size: 0.85rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
}

.section-toggle .inline-toggle input:checked + * {
  color: #4CAF50;
}

.wavetable-mode-row {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.wavetable-mode-row .inline-toggle.disabled {
  opacity: 0.35;
}

.frame-badge {
  font-size: 0.6rem;
  background: rgba(76, 175, 80, 0.25);
  color: #4CAF50;
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  margin-left: 0.3rem;
  font-weight: 600;
}

/* Wavetable controls */
.wavetable-controls {
  margin-top: 0.4rem;
  margin-bottom: 0.4rem;
}

.wavetable-controls input[type="range"] {
  width: 100%;
  accent-color: #4CAF50;
}

/* Semantic wavetable builder */
.wt-build-section {
  margin: 0.5rem 0;
}

.wt-build-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.wt-axis-select,
.wt-frame-select {
  padding: 0.35rem 0.5rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  color: #fff;
  font-size: 0.8rem;
}

.wt-axis-select {
  flex: 1;
}

.wt-frame-select {
  width: 60px;
}

.wt-build-btn {
  padding: 0.35rem 0.8rem;
  background: rgba(156, 39, 176, 0.2);
  border: 1px solid rgba(156, 39, 176, 0.4);
  border-radius: 4px;
  color: #CE93D8;
  font-size: 0.8rem;
  cursor: pointer;
  white-space: nowrap;
}

.wt-build-btn:hover:not(:disabled) {
  background: rgba(156, 39, 176, 0.35);
}

.wt-build-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.wt-progress {
  margin-top: 0.4rem;
  position: relative;
  height: 18px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  overflow: hidden;
}

.wt-progress-bar {
  height: 100%;
  background: rgba(156, 39, 176, 0.4);
  transition: width 0.2s;
}

.wt-progress-label {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 0.7rem;
  line-height: 18px;
  color: rgba(255, 255, 255, 0.7);
}

.effects-params {
  padding: 0.3rem 0;
}

.filter-params {
  padding: 0.3rem 0;
}

.mod-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.3rem 0;
}

.mod-header h5 {
  margin: 0;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.6);
  min-width: 3rem;
}

.mod-target-select {
  padding: 0.2rem 0.4rem;
  font-size: 0.7rem;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.8);
}

.loop-toggle {
  font-size: 0.65rem !important;
}

.filter-type-select,
.lfo-select {
  padding: 0.2rem 0.4rem;
  font-size: 0.7rem;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.8);
}

.lfo-header {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding-top: 0.4rem;
}

.arp-select {
  padding: 0.3rem 0.5rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 5px;
  color: #ffffff;
  font-size: 0.75rem;
}


/* Step Sequencer controls */
.sequencer-controls {
  margin-bottom: 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.sequencer-transport {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}

.seq-play-btn {
  padding: 0.4rem 1rem;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
  background: rgba(76, 175, 80, 0.15);
  border: 1px solid rgba(76, 175, 80, 0.3);
  color: #4CAF50;
  font-weight: 600;
}

.seq-play-btn:hover:not(:disabled) {
  background: rgba(76, 175, 80, 0.25);
}

.seq-play-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.seq-step-count {
  display: flex;
  gap: 0;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
  overflow: hidden;
}

.step-count-btn {
  padding: 0.25rem 0.5rem;
  background: rgba(255, 255, 255, 0.03);
  border: none;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.7rem;
  cursor: pointer;
  transition: all 0.15s;
}

.step-count-btn:last-child {
  border-right: none;
}

.step-count-btn.active {
  background: rgba(76, 175, 80, 0.15);
  color: #4CAF50;
  font-weight: 600;
}

.seq-division {
  display: flex;
  gap: 0;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
  overflow: hidden;
}

.division-btn {
  padding: 0.25rem 0.4rem;
  background: rgba(255, 255, 255, 0.03);
  border: none;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.65rem;
  cursor: pointer;
  transition: all 0.15s;
}

.division-btn:last-child {
  border-right: none;
}

.division-btn.active {
  background: rgba(76, 175, 80, 0.15);
  color: #4CAF50;
  font-weight: 600;
}

/* Scan track with range brackets */
.wt-scan-track {
  position: relative;
  height: 28px;
  margin-bottom: 0.2rem;
}

.wt-scan-track input[type="range"] {
  width: 100%;
  position: relative;
  z-index: 2;
}

.wt-range-band {
  position: absolute;
  top: 4px;
  height: 20px;
  background: rgba(206, 147, 216, 0.1);
  border-radius: 2px;
  z-index: 0;
  pointer-events: none;
}

.wt-bracket {
  position: absolute;
  top: 0;
  width: 6px;
  height: 28px;
  z-index: 3;
  cursor: ew-resize;
  touch-action: none;
}

.wt-bracket-start {
  border-left: 2px solid #CE93D8;
  border-top: 2px solid #CE93D8;
  border-bottom: 2px solid #CE93D8;
  border-radius: 3px 0 0 3px;
  transform: translateX(-6px);
}

.wt-bracket-end {
  border-right: 2px solid #CE93D8;
  border-top: 2px solid #CE93D8;
  border-bottom: 2px solid #CE93D8;
  border-radius: 0 3px 3px 0;
}

.wt-bracket:hover {
  border-color: #E1BEE7;
}

/* Wavetable options row */
.wt-options-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.4rem;
  flex-wrap: wrap;
}

.wt-scan-env {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  flex-wrap: wrap;
}

.wt-env-title {
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.7rem;
  margin-right: 0.2rem;
}

.wt-env-slider {
  width: 60px;
  accent-color: #CE93D8;
}

.wt-env-label {
  font-weight: 600;
  color: rgba(255, 255, 255, 0.4);
  font-size: 0.7rem;
}

.wt-env-value {
  color: rgba(255, 255, 255, 0.35);
  font-size: 0.6rem;
  min-width: 28px;
  text-align: right;
}

.midi-sync-badge {
  font-size: 0.7rem;
  padding: 0.2rem 0.5rem;
  background: rgba(33, 150, 243, 0.15);
  border: 1px solid rgba(33, 150, 243, 0.3);
  border-radius: 4px;
  color: #2196F3;
  font-weight: 500;
  margin-left: auto;
}

.sequencer-settings-row {
  display: flex;
  gap: 1rem;
  align-items: center;
  flex-wrap: wrap;
}

.sequencer-preset {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.sequencer-preset label,
.sequencer-bpm label {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.4);
  flex-shrink: 0;
}

.sequencer-preset select {
  padding: 0.3rem 0.4rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 5px;
  color: #ffffff;
  font-size: 0.75rem;
}

.sequencer-bpm {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.sequencer-bpm input[type="range"] {
  flex: 1;
  min-width: 80px;
  accent-color: #4CAF50;
}

.seq-bpm-value {
  font-size: 0.75rem;
  color: #4CAF50;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  min-width: 2rem;
  text-align: right;
}

/* Step Grid */
/* On-screen keyboard */
.keyboard-row {
  display: flex;
  gap: 2px;
  margin: 0.5rem 0;
}

.key-btn {
  flex: 1;
  padding: 0.5rem 0;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.65rem;
  cursor: pointer;
  transition: all 0.1s;
  user-select: none;
  touch-action: none;
}

.key-btn.black {
  background: rgba(255, 255, 255, 0.02);
  color: rgba(255, 255, 255, 0.4);
  border-color: rgba(255, 255, 255, 0.08);
}

.key-btn.active {
  background: rgba(76, 175, 80, 0.3);
  color: #4CAF50;
  border-color: rgba(76, 175, 80, 0.5);
}

.hold-btn {
  font-size: 0.6rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.hold-btn.active {
  background: rgba(255, 152, 0, 0.3);
  color: #FF9800;
  border-color: rgba(255, 152, 0, 0.5);
}

.key-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.seq-grid {
  display: grid;
  gap: 2px;
  padding: 0.4rem 0;
}

.seq-grid-5 { grid-template-columns: repeat(5, 1fr); }
.seq-grid-8 { grid-template-columns: repeat(8, 1fr); }
.seq-grid-16 { grid-template-columns: repeat(16, 1fr); }
.seq-grid-32 { grid-template-columns: repeat(32, 1fr); }

.seq-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 4px 2px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  transition: border-color 0.1s, background 0.1s;
}

.seq-step.playing {
  border-color: rgba(76, 175, 80, 0.5);
  background: rgba(76, 175, 80, 0.06);
}

.seq-step.muted {
  opacity: 0.35;
}

.seq-step-num {
  font-size: 0.55rem;
  color: rgba(255, 255, 255, 0.25);
  font-variant-numeric: tabular-nums;
}

/* Vertical semitone slider */
.seq-semitone-slider {
  writing-mode: vertical-lr;
  direction: rtl;
  width: 18px;
  height: 60px;
  accent-color: #4CAF50;
  cursor: pointer;
}

.seq-semitone-val {
  font-size: 0.6rem;
  color: rgba(255, 255, 255, 0.5);
  font-variant-numeric: tabular-nums;
  min-height: 1em;
}

/* Step active toggle dot */
.seq-step-toggle {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.08);
  cursor: pointer;
  transition: all 0.1s;
  padding: 0;
}

.seq-step-toggle.on {
  background: rgba(76, 175, 80, 0.5);
  border-color: rgba(76, 175, 80, 0.7);
}

.seq-step-toggle.playing {
  background: #4CAF50;
  border-color: #4CAF50;
  box-shadow: 0 0 6px rgba(76, 175, 80, 0.7);
}

/* Horizontal velocity slider (small) */
.seq-velocity-slider {
  width: 100%;
  height: 4px;
  accent-color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
}

/* ADSR Envelope */
/* Synth box grouping */
.synth-box {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  padding: 0.6rem;
  margin-bottom: 0.5rem;
}

.env-target {
  font-size: 0.6rem;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  background: rgba(206, 147, 216, 0.15);
  color: #CE93D8;
  font-weight: 600;
  margin-left: 0.4rem;
  vertical-align: middle;
}

.adsr-section {
  padding-top: 0.4rem;
}

.adsr-section h5 {
  font-size: 0.75rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 0.3rem;
}

.adsr-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.6rem 1.2rem;
  margin-top: 0.5rem;
}

.adsr-slider {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.adsr-slider label {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.5);
  min-width: 1.5rem;
  flex-shrink: 0;
}

.adsr-slider input[type="range"] {
  flex: 1;
  accent-color: #4CAF50;
}

.adsr-value {
  font-size: 0.7rem;
  color: #4CAF50;
  font-variant-numeric: tabular-nums;
  min-width: 3rem;
  text-align: right;
  flex-shrink: 0;
}

/* Semantic Axes Section */
.semantic-axes-section {
  margin-bottom: 1.2rem;
}

.semantic-axes-section summary {
  background: rgba(255, 255, 255, 0.03);
}

.semantic-axes-content {
  padding: 0.8rem;
}

.semantic-axes-info {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1.5;
  margin-bottom: 1rem;
}

.semantic-axes-slots {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  margin-bottom: 1rem;
}

.axis-slot {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.6rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
}

.axis-color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  align-self: flex-start;
}

.axis-select {
  width: 100%;
  padding: 0.4rem 0.5rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
  color: #ffffff;
  font-size: 0.8rem;
  color-scheme: dark;
}

.axis-select:focus {
  outline: none;
  border-color: rgba(76, 175, 80, 0.5);
}

.axis-slider-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.axis-pole-label {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.4);
  flex-shrink: 0;
  width: 6rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.axis-pole-label.pole-a {
  text-align: right;
}

.axis-range {
  flex: 1;
  min-width: 0;
}

.axis-value {
  font-size: 0.75rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  min-width: 2.5rem;
  text-align: right;
  flex-shrink: 0;
}


</style>
