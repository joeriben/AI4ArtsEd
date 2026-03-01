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

      <!-- Mode Toggle: Free Prompt vs. Semantic Axes -->
      <div class="synth-mode-toggle">
        <button
          class="mode-toggle-btn"
          :class="{ active: synthMode === 'freePrompt' }"
          @click="synthMode = 'freePrompt'"
        >{{ t('latentLab.crossmodal.synth.semanticAxes.freeModeToggle') }}</button>
        <button
          class="mode-toggle-btn"
          :class="{ active: synthMode === 'semanticAxes' }"
          @click="synthMode = 'semanticAxes'"
        >{{ t('latentLab.crossmodal.synth.semanticAxes.modeToggle') }}</button>
      </div>

      <!-- ===== Semantic Axes Mode ===== -->
      <template v-if="synthMode === 'semanticAxes'">
        <p class="semantic-axes-info">{{ t('latentLab.crossmodal.synth.semanticAxes.info') }}</p>

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
              <option
                v-for="ax in availableAxes"
                :key="ax.name"
                :value="ax.name"
              >
                {{ ax.pole_a }} — {{ ax.pole_b }}
                <template v-if="ax.d !== null"> (d={{ ax.d }})</template>
                <template v-if="ax.level === 'experimental'"> *</template>
              </option>
            </select>
            <div v-if="slot.axis" class="axis-slider-row">
              <span class="axis-pole-label pole-a">{{ getAxisMeta(slot.axis)?.pole_a }}</span>
              <input
                type="range"
                :value="slot.value"
                min="0"
                max="1"
                step="0.01"
                class="axis-range"
                :style="{ accentColor: axisColors[idx] }"
                @input="slot.value = parseFloat(($event.target as HTMLInputElement).value)"
              />
              <span class="axis-pole-label pole-b">{{ getAxisMeta(slot.axis)?.pole_b }}</span>
              <span class="axis-value" :style="{ color: axisColors[idx] }">{{ slot.value.toFixed(2) }}</span>
            </div>
          </div>
        </div>

        <button class="dim-btn dim-btn-reset semantic-reset-btn" @click="resetAxesToCenter">
          {{ t('latentLab.crossmodal.synth.semanticAxes.resetAll') }}
        </button>
      </template>

      <!-- ===== Free Prompt Mode ===== -->
      <template v-else>
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
          icon="➕"
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

        <!-- Sliders -->
        <div class="slider-group">
          <div class="slider-item">
            <div class="slider-header">
              <label>{{ t('latentLab.crossmodal.synth.alpha') }}</label>
              <span class="slider-value">{{ synth.alpha.toFixed(2) }}</span>
            </div>
            <input type="range" v-model.number="synth.alpha" min="-2" max="3" step="0.01" />
            <span class="slider-hint">{{ t('latentLab.crossmodal.synth.alphaHint') }}</span>
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
      </template>

      <!-- Params row -->
      <div class="params-row">
        <div class="param">
          <label>{{ t('latentLab.crossmodal.synth.duration') }}</label>
          <input v-model.number="synth.duration" type="number" min="0.1" max="5" step="0.1" />
          <span class="param-hint">{{ t('latentLab.crossmodal.synth.durationHint') }}</span>
        </div>
        <div class="param">
          <label>{{ t('latentLab.crossmodal.synth.steps') }}</label>
          <input v-model.number="synth.steps" type="number" min="10" max="100" step="5" />
          <span class="param-hint">{{ t('latentLab.crossmodal.synth.stepsHint') }}</span>
        </div>
        <div class="param">
          <label>{{ t('latentLab.crossmodal.synth.cfg') }}</label>
          <input v-model.number="synth.cfg" type="number" min="1" max="15" step="0.5" />
          <span class="param-hint">{{ t('latentLab.crossmodal.synth.cfgHint') }}</span>
        </div>
        <div class="param">
          <label>{{ t('latentLab.crossmodal.seed') }}</label>
          <input v-model.number="synth.seed" type="number" />
          <span class="param-hint">{{ t('latentLab.crossmodal.synth.seedHint') }}</span>
        </div>
      </div>

      <div class="action-row">
        <button class="generate-btn" :disabled="(!synth.promptA && synthMode === 'freePrompt') || (!hasActiveAxes && synthMode === 'semanticAxes') || generating" @click="runSynth">
          {{ generating ? t('latentLab.crossmodal.generating') : t('latentLab.crossmodal.generate') }}
        </button>
        <button class="loop-btn" :class="{ active: looper.isLooping.value }" @click="toggleLoop">
          {{ looper.isLooping.value ? t('latentLab.crossmodal.synth.loopOn') : t('latentLab.crossmodal.synth.loopOff') }}
        </button>
        <button v-if="looper.isPlaying.value" class="stop-btn" @click="looper.stop()">
          {{ t('latentLab.crossmodal.synth.stop') }}
        </button>
        <button v-if="!looper.isPlaying.value && looper.hasAudio.value" class="play-btn" @click="looper.replay()">
          {{ t('latentLab.crossmodal.synth.play') }}
        </button>
      </div>

      <!-- Dimension Explorer Section (open by default) -->
      <details class="dim-explorer-section" :open="dimExplorerOpen" @toggle="onDimExplorerToggle">
        <summary>{{ t('latentLab.crossmodal.synth.dimensions.section') }}</summary>
        <div class="dim-explorer-content">
          <p class="dim-hint">{{ t('latentLab.crossmodal.synth.dimensions.hint') }}</p>

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
              {{ t('latentLab.crossmodal.synth.dimensions.hoverOffset') }}={{ hoveredDim.offset.toFixed(2) }}
            </span>
            <span v-if="embeddingStats?.sort_mode" class="dim-sort-mode">
              {{ embeddingStats.sort_mode === 'diff'
                ? t('latentLab.crossmodal.synth.dimensions.sortDiff')
                : t('latentLab.crossmodal.synth.dimensions.sortMagnitude') }}
            </span>
          </div>

          <!-- Controls Row -->
          <div class="dim-controls-row">
            <button
              v-if="activeOffsetCount > 0"
              class="dim-btn dim-btn-generate"
              :disabled="generating"
              @click="runSynth"
            >
              {{ t('latentLab.crossmodal.synth.dimensions.applyAndGenerate') }}
            </button>
            <button class="dim-btn dim-btn-undo" :disabled="!canUndo" @click="undo" title="Ctrl+Z">
              {{ t('latentLab.crossmodal.synth.dimensions.undo') }}
            </button>
            <button class="dim-btn dim-btn-undo" :disabled="!canRedo" @click="redo" title="Ctrl+Shift+Z">
              {{ t('latentLab.crossmodal.synth.dimensions.redo') }}
            </button>
            <span v-if="activeOffsetCount > 0" class="dim-offset-status">
              {{ t('latentLab.crossmodal.synth.dimensions.activeOffsets', { count: activeOffsetCount }) }}
            </span>
            <button v-if="activeOffsetCount > 0" class="dim-btn dim-btn-reset" @click="resetAllOffsets">
              {{ t('latentLab.crossmodal.synth.dimensions.resetAll') }}
            </button>
            <span class="dim-right-click-hint">
              {{ t('latentLab.crossmodal.synth.dimensions.rightClickReset') }}
            </span>
          </div>
        </div>
      </details>

      <!-- Looper Widget (always visible, disabled when no audio) -->
      <div class="looper-widget" :class="{ disabled: !looper.hasAudio.value }">
        <div class="looper-status">
          <span class="looper-indicator" :class="{ pulsing: looper.isPlaying.value }" />
          <span class="looper-label">
            {{ looper.isPlaying.value
              ? (looper.isLooping.value ? t('latentLab.crossmodal.synth.looping') : t('latentLab.crossmodal.synth.playing'))
              : t('latentLab.crossmodal.synth.stopped') }}
          </span>
          <span v-if="looper.bufferDuration.value > 0" class="looper-duration">
            {{ looper.bufferDuration.value.toFixed(2) }}s
          </span>
        </div>
        <!-- Loop Interval -->
        <div class="loop-interval">
          <div class="slider-header">
            <label>{{ t('latentLab.crossmodal.synth.loopInterval') }}</label>
            <span class="slider-value">
              {{ (looper.loopStartFrac.value * looper.bufferDuration.value).toFixed(3) }}s
              – {{ (looper.loopEndFrac.value * looper.bufferDuration.value).toFixed(3) }}s
            </span>
          </div>
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
          <!-- Playback mode selector -->
          <div class="playback-mode-selector">
            <button
              class="mode-btn"
              :class="{ active: playbackMode === 'loop' }"
              @click="setPlaybackMode('loop')"
            >{{ t('latentLab.crossmodal.synth.modeLoop') }}</button>
            <button
              class="mode-btn"
              :class="{ active: playbackMode === 'pingpong' }"
              @click="setPlaybackMode('pingpong')"
            >{{ t('latentLab.crossmodal.synth.modePingPong') }}</button>
            <button
              class="mode-btn"
              :class="{ active: playbackMode === 'wavetable' }"
              :disabled="!wavetableSupported"
              @click="setPlaybackMode('wavetable')"
            >{{ t('latentLab.crossmodal.synth.modeWavetable') }}</button>
          </div>
          <div v-if="playbackMode !== 'wavetable'" class="loop-options">
            <label class="inline-toggle">
              <input type="checkbox" :checked="looper.loopOptimize.value" :disabled="!looper.hasAudio.value" @change="onOptimizeChange" />
              {{ t('latentLab.crossmodal.synth.loopOptimize') }}
            </label>
            <span v-if="looper.loopOptimize.value" class="optimized-hint">
              → {{ (looper.optimizedEndFrac.value * looper.bufferDuration.value).toFixed(3) }}s
            </span>
          </div>
          <span v-if="playbackMode !== 'wavetable'" class="slider-hint">{{ t('latentLab.crossmodal.synth.loopIntervalHint') }}</span>
        </div>
        <!-- Wavetable scan slider -->
        <div v-if="playbackMode === 'wavetable'" class="wavetable-controls">
          <div class="transpose-row">
            <label>{{ t('latentLab.crossmodal.synth.wavetableScan') }}</label>
            <input
              type="range"
              :value="wavetableScan"
              min="0"
              max="1"
              step="0.001"
              :disabled="!wavetableOsc.hasFrames.value"
              @input="onScanInput"
            />
            <span class="transpose-value">{{ wavetableScan.toFixed(3) }}</span>
          </div>
          <span class="slider-hint">{{ t('latentLab.crossmodal.synth.wavetableScanHint') }}</span>
          <span v-if="wavetableOsc.frameCount.value > 0" class="wavetable-frame-count">
            {{ t('latentLab.crossmodal.synth.wavetableFrames', { count: wavetableOsc.frameCount.value }) }}
          </span>
        </div>
        <!-- Transpose -->
        <div class="transpose-row">
          <label>{{ t('latentLab.crossmodal.synth.transpose') }}</label>
          <input
            type="range"
            :value="looper.transposeSemitones.value"
            min="-24"
            max="24"
            step="1"
            :disabled="!looper.hasAudio.value"
            @input="onTransposeInput"
          />
          <span class="transpose-value">{{ formatTranspose(looper.transposeSemitones.value) }}</span>
          <span class="param-hint">{{ t('latentLab.crossmodal.synth.transposeHint') }}</span>
        </div>
        <div v-if="playbackMode !== 'wavetable'" class="transpose-mode-row">
          <label class="inline-toggle" :class="{ active: looper.transposeMode.value === 'rate' }">
            <input
              type="radio"
              value="rate"
              :checked="looper.transposeMode.value === 'rate'"
              :disabled="!looper.hasAudio.value"
              @change="looper.setTransposeMode('rate')"
            />
            {{ t('latentLab.crossmodal.synth.modeRate') }}
          </label>
          <label class="inline-toggle" :class="{ active: looper.transposeMode.value === 'pitch' }">
            <input
              type="radio"
              value="pitch"
              :checked="looper.transposeMode.value === 'pitch'"
              :disabled="!looper.hasAudio.value"
              @change="looper.setTransposeMode('pitch')"
            />
            {{ t('latentLab.crossmodal.synth.modePitch') }}
          </label>
        </div>
        <!-- Crossfade duration -->
        <div v-if="playbackMode !== 'wavetable'" class="transpose-row">
          <label>{{ t('latentLab.crossmodal.synth.crossfade') }}</label>
          <input
            type="range"
            :value="looper.crossfadeMs.value"
            min="0"
            max="500"
            step="10"
            :disabled="!looper.hasAudio.value"
            @input="onCrossfadeInput"
          />
          <span class="transpose-value">{{ looper.crossfadeMs.value }}ms</span>
          <span class="param-hint">{{ t('latentLab.crossmodal.synth.crossfadeHint') }}</span>
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
        <!-- Save buttons -->
        <div class="save-row">
          <button class="save-btn" :disabled="!looper.hasAudio.value" @click="saveRaw">
            {{ t('latentLab.crossmodal.synth.saveRaw') }}
          </button>
          <button v-if="playbackMode !== 'wavetable'" class="save-btn" :disabled="!looper.hasAudio.value" @click="saveLoop">
            {{ t('latentLab.crossmodal.synth.saveLoop') }}
          </button>
        </div>
      </div>

      <!-- MIDI Section (collapsed by default) -->
      <details class="midi-section" :open="midiOpen" @toggle="onMidiToggle">
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
            <!-- ADSR Envelope -->
            <div class="adsr-section">
              <h5>{{ t('latentLab.crossmodal.synth.adsrTitle') }}</h5>
              <span class="slider-hint">{{ t('latentLab.crossmodal.synth.adsrHint') }}</span>
              <div class="adsr-grid">
                <div class="adsr-slider">
                  <label>{{ t('latentLab.crossmodal.synth.adsrAttack') }}</label>
                  <input type="range" v-model.number="envelope.attackMs.value" min="0" max="1000" step="1" />
                  <span class="adsr-value">{{ envelope.attackMs.value }}ms</span>
                </div>
                <div class="adsr-slider">
                  <label>{{ t('latentLab.crossmodal.synth.adsrDecay') }}</label>
                  <input type="range" v-model.number="envelope.decayMs.value" min="0" max="2000" step="1" />
                  <span class="adsr-value">{{ envelope.decayMs.value }}ms</span>
                </div>
                <div class="adsr-slider">
                  <label>{{ t('latentLab.crossmodal.synth.adsrSustain') }}</label>
                  <input type="range" v-model.number="envelope.sustain.value" min="0" max="1" step="0.01" />
                  <span class="adsr-value">{{ envelope.sustain.value.toFixed(2) }}</span>
                </div>
                <div class="adsr-slider">
                  <label>{{ t('latentLab.crossmodal.synth.adsrRelease') }}</label>
                  <input type="range" v-model.number="envelope.releaseMs.value" min="0" max="3000" step="1" />
                  <span class="adsr-value">{{ envelope.releaseMs.value }}ms</span>
                </div>
              </div>
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
import { useEnvelope } from '@/composables/useEnvelope'
import { useWebMidi } from '@/composables/useWebMidi'
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
const generating = ref(false)
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

// ===== Wavetable Oscillator =====
const wavetableOsc = useWavetableOsc()
type PlaybackMode = 'loop' | 'pingpong' | 'wavetable'
const playbackMode = ref<PlaybackMode>('loop')
const wavetableScan = ref(0)
const wavetableSupported = ref(typeof AudioWorkletNode !== 'undefined')

// ===== ADSR Envelope =====
const envelope = useEnvelope()
let envelopeWired = false

/** Lazily wire envelope GainNode between engines and AudioContext destination. */
function wireEnvelope() {
  if (envelopeWired) return
  // Need an AudioContext — get it from whichever engine is active
  const ac = playbackMode.value === 'wavetable'
    ? wavetableOsc.getContext()
    : looper.getContext()
  const envNode = envelope.createNode(ac)
  envNode.connect(ac.destination)
  looper.setDestination(envNode)
  wavetableOsc.setDestination(envNode)
  envelopeWired = true
}

// ===== Web MIDI =====
const midi = useWebMidi()

// MIDI reference note for transpose (C3 = 60)
const MIDI_REF_NOTE = 60

// Monophonic note stack for last-note priority
const heldNotes: number[] = []

// Initialize MIDI
midi.init()

// MIDI CC mappings
// CC1 → Alpha (-2 to 3)
midi.mapCC(1, (v) => { synth.alpha = -2 + v * 5 })
// CC2 → Magnitude (0.1 to 5)
midi.mapCC(2, (v) => { synth.magnitude = 0.1 + v * 4.9 })
// CC3 → Noise (0 to 1)
midi.mapCC(3, (v) => { synth.noise = v })
// CC64 → Loop toggle (sustain pedal: >0.5 = on)
midi.mapCC(64, (v) => { looper.setLoop(v > 0.5) })
// CC5 → Wavetable scan position
midi.mapCC(5, (v) => { wavetableScan.value = v; wavetableOsc.setScanPosition(v) })

// MIDI Note → Monophonic synth with ADSR envelope (NEVER triggers generation)
midi.onNote((note, velocity, on) => {
  if (on) {
    wireEnvelope()
    const wasEmpty = heldNotes.length === 0
    // Remove duplicate if re-pressed, then push to top
    const idx = heldNotes.indexOf(note)
    if (idx !== -1) heldNotes.splice(idx, 1)
    heldNotes.push(note)

    if (playbackMode.value === 'wavetable') {
      wavetableOsc.setFrequencyFromNote(note)
      if (wasEmpty) {
        // Non-legato: retrigger engine + attack
        if (!wavetableOsc.isPlaying.value && wavetableOsc.hasFrames.value) {
          wavetableOsc.start()
        }
        envelope.triggerAttack(velocity)
      }
      // Legato: just pitch change, envelope continues at sustain
    } else {
      const semitones = note - MIDI_REF_NOTE
      looper.setTranspose(semitones)
      if (wasEmpty) {
        // Non-legato: hard retrigger + attack
        if (looper.hasAudio.value) looper.retrigger()
        envelope.triggerAttack(velocity)
      }
      // Legato: just transpose, envelope continues at sustain
    }
  } else {
    // Note-off: remove from stack
    const idx = heldNotes.indexOf(note)
    if (idx !== -1) heldNotes.splice(idx, 1)

    if (heldNotes.length === 0) {
      // Last note released: start release phase, stop engines after release
      envelope.triggerRelease(() => {
        if (heldNotes.length === 0) {
          if (playbackMode.value === 'wavetable') {
            wavetableOsc.stop()
          } else {
            looper.stop()
          }
        }
      })
    } else {
      // Notes remaining: switch pitch to last held note
      const lastNote = heldNotes[heldNotes.length - 1]!
      if (playbackMode.value === 'wavetable') {
        wavetableOsc.setFrequencyFromNote(lastNote)
      } else {
        looper.setTranspose(lastNote - MIDI_REF_NOTE)
      }
    }
  }
})

// Synth params
const synth = reactive({
  promptA: '',
  promptB: '',
  alpha: 0.5,
  magnitude: 1.0,
  noise: 0.0,
  duration: 1.0,
  steps: 20,
  cfg: 3.5,
  seed: -1,
  loop: true,
})

// ===== Semantic Axes =====
const synthMode = ref<'freePrompt' | 'semanticAxes'>('freePrompt')

interface AxisDef {
  name: string
  pole_a: string
  pole_b: string
  level: string
  d: number | null
}
const availableAxes = ref<AxisDef[]>([])

interface AxisSlot {
  axis: string
  value: number
}
const axisSlots = reactive<AxisSlot[]>([
  { axis: 'tonal_noisy', value: 0.5 },
  { axis: 'rhythmic_sustained', value: 0.5 },
  { axis: 'ceremonial_everyday', value: 0.5 },
  { axis: 'acoustic_electronic', value: 0.5 },
  { axis: 'music_soundscape', value: 0.5 },
])

const axisColors = ['#e91e63', '#2196f3', '#4caf50', '#ff9800', '#9c27b0']

interface AxisContribution {
  dim: number
  top_axis: string
  contribution: number
  all: Record<string, number>
}
const axisContributions = ref<AxisContribution[]>([])

const hasActiveAxes = computed(() =>
  axisSlots.some(s => s.axis !== '')
)

function getAxisMeta(axisName: string): AxisDef | undefined {
  return availableAxes.value.find(a => a.name === axisName)
}

function onAxisSelectChange(idx: number, value: string) {
  axisSlots[idx]!.axis = value
  axisSlots[idx]!.value = 0.5
}

function resetAxesToCenter() {
  for (const slot of axisSlots) {
    slot.value = 0.5
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
const dimensionOffsets = reactive<Record<number, number>>({})
const spectralCanvasRef = ref<HTMLCanvasElement | null>(null)
const hoveredDim = ref<{ dim: number; activation: number; offset: number } | null>(null)
let isDragging = false

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
  // Maps axis_name → color string
  const axisColorMap: Record<string, string> = {}
  if (synthMode.value === 'semanticAxes' && axisContributions.value.length > 0) {
    for (let si = 0; si < axisSlots.length; si++) {
      const slot = axisSlots[si]!
      if (slot.axis) {
        axisColorMap[slot.axis] = axisColors[si]!
      }
    }
  }

  // Draw bars
  for (let i = 0; i < acts.length; i++) {
    const entry = acts[i]!
    const dim = entry.dim
    const val = entry.value
    const x = i * barW
    const barH = (Math.abs(val) / maxAct) * (centerY - 2)

    // Determine bar color: axis-colored in semantic mode, muted green in free prompt mode
    let barColor = 'rgba(76, 175, 80, 0.35)'
    if (synthMode.value === 'semanticAxes' && axisContributions.value.length > 0) {
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
      const offsetH = (Math.abs(offset) / maxAct) * (centerY - 2)
      ctx.fillStyle = 'rgba(102, 187, 106, 0.8)'
      if (offset > 0) {
        // Positive offset: draw upward from activation endpoint
        const startY = val >= 0 ? centerY - barH : centerY
        ctx.fillRect(x, startY - offsetH, Math.max(barW - 0.5, 0.5), offsetH)
      } else {
        // Negative offset: draw downward from activation endpoint
        const startY = val >= 0 ? centerY : centerY + barH
        ctx.fillRect(x, startY, Math.max(barW - 0.5, 0.5), offsetH)
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
  // Drag up (above center) = positive offset, drag down = negative offset
  const normalized = (centerY - y) / centerY
  // Use maxActivation as range so offsets are on the same scale as activation bars
  const range = maxActivation.value
  return Math.max(-range, Math.min(range, normalized * range))
}

function onSpectralMouseDown(e: MouseEvent) {
  if (e.button === 2) return // right-click handled by contextmenu
  const canvas = spectralCanvasRef.value
  if (!canvas) return
  pushUndo()
  isDragging = true
  const dim = dimAtX(canvas, e.clientX)
  if (dim !== null) {
    const off = offsetAtY(canvas, e.clientY)
    dimensionOffsets[dim] = off
    drawSpectralStrip()
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

  // Paint while dragging
  if (isDragging) {
    const dim = dimAtX(canvas, e.clientX)
    if (dim !== null) {
      const off = offsetAtY(canvas, e.clientY)
      dimensionOffsets[dim] = off
      drawSpectralStrip()
    }
  }
}

function onSpectralMouseUp() {
  isDragging = false
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
    dimensionOffsets[dim] = offsetAtY(canvas, touch.clientY)
    drawSpectralStrip()
  }
}

function onSpectralTouchMove(e: TouchEvent) {
  const touch = e.touches[0]
  if (!touch || !isDragging || e.touches.length !== 1) return
  e.preventDefault()
  const canvas = spectralCanvasRef.value
  if (!canvas) return
  const dim = dimAtX(canvas, touch.clientX)
  if (dim !== null) {
    dimensionOffsets[dim] = offsetAtY(canvas, touch.clientY)
    drawSpectralStrip()
  }
}

function onSpectralTouchEnd() {
  isDragging = false
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

/** Deterministic fingerprint of all generation-affecting synth params */
function synthFingerprint(): string {
  if (synthMode.value === 'semanticAxes') {
    return JSON.stringify([
      'semantic', axisSlots.map(s => [s.axis, s.value]),
      synth.duration, synth.steps, synth.cfg, synth.seed,
      dimensionOffsets,
    ])
  }
  return JSON.stringify([
    synth.promptA, synth.promptB, synth.alpha, synth.magnitude,
    synth.noise, synth.duration, synth.steps, synth.cfg, synth.seed,
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

function toggleLoop() {
  looper.setLoop(!looper.isLooping.value)
}

function onTransposeInput(event: Event) {
  const val = parseInt((event.target as HTMLInputElement).value)
  if (playbackMode.value === 'wavetable') {
    wavetableOsc.setFrequencyFromNote(60 + val)
  } else {
    looper.setTranspose(val)
  }
}

function onLoopStartInput(event: Event) {
  const val = parseFloat((event.target as HTMLInputElement).value)
  looper.setLoopStart(val)
}

function onLoopEndInput(event: Event) {
  const val = parseFloat((event.target as HTMLInputElement).value)
  looper.setLoopEnd(val)
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
function onPingPongChange(event: Event) {
  looper.setLoopPingPong((event.target as HTMLInputElement).checked)
}

async function setPlaybackMode(mode: PlaybackMode) {
  playbackMode.value = mode
  // Non-MIDI mode switch: bypass envelope so gain=1
  if (envelopeWired) envelope.bypass()
  // Stop both engines
  wavetableOsc.stop()
  if (mode === 'wavetable') {
    looper.stop()
    looper.setLoopPingPong(false)
    // Load frames and start if audio exists
    const buf = looper.getOriginalBuffer()
    if (buf) {
      await wavetableOsc.loadFrames(buf)
      await wavetableOsc.start()
    }
  } else {
    looper.setLoopPingPong(mode === 'pingpong')
    if (looper.hasAudio.value) looper.replay()
  }
}

function onScanInput(event: Event) {
  const val = parseFloat((event.target as HTMLInputElement).value)
  wavetableScan.value = val
  wavetableOsc.setScanPosition(val)
}

watch(wavetableScan, (v) => {
  wavetableOsc.setScanPosition(v)
})

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
  if (blob) downloadBlob(blob, `synth_raw_${resultSeed.value ?? 0}.wav`)
}

function saveLoop() {
  const blob = looper.exportLoop()
  if (blob) downloadBlob(blob, `synth_loop_${resultSeed.value ?? 0}.wav`)
}

// ===== Synth =====
async function runSynth() {
  // Non-MIDI playback: bypass envelope so gain=1
  if (envelopeWired) envelope.bypass()
  // Don't clear looper state — keep playing during generation
  error.value = ''
  resultSeed.value = null
  generationTimeMs.value = null
  embeddingStats.value = null
  generating.value = true
  try {
    let result: any

    if (synthMode.value === 'semanticAxes') {
      // Multi-axis synth mode
      const axes: Record<string, number> = {}
      for (const slot of axisSlots) {
        if (slot.axis) axes[slot.axis] = slot.value
      }

      const body: Record<string, unknown> = {
        axes,
        duration_seconds: synth.duration,
        steps: synth.steps,
        cfg_scale: synth.cfg,
        seed: synth.seed,
      }

      // Add non-zero dimension offsets
      const nonZeroOffsets: Record<string, number> = {}
      for (const [k, v] of Object.entries(dimensionOffsets)) {
        if (v !== 0) nonZeroOffsets[k] = v
      }
      if (Object.keys(nonZeroOffsets).length > 0) {
        body.dimension_offsets = nonZeroOffsets
      }

      result = await apiPost('/api/cross_aesthetic/multi_axis_synth', body)

      if (result.success && result.axis_contributions) {
        axisContributions.value = result.axis_contributions
      }
    } else {
      // Free prompt mode
      const body: Record<string, unknown> = {
        prompt_a: synth.promptA,
        alpha: synth.alpha,
        magnitude: synth.magnitude,
        noise_sigma: synth.noise,
        duration_seconds: synth.duration,
        steps: synth.steps,
        cfg_scale: synth.cfg,
        seed: synth.seed,
      }
      if (synth.promptB.trim()) {
        body.prompt_b = synth.promptB
      }
      // Add non-zero dimension offsets
      const nonZeroOffsets: Record<string, number> = {}
      for (const [k, v] of Object.entries(dimensionOffsets)) {
        if (v !== 0) nonZeroOffsets[k] = v
      }
      if (Object.keys(nonZeroOffsets).length > 0) {
        body.dimension_offsets = nonZeroOffsets
      }

      result = await apiPost('/api/cross_aesthetic/synth', body)
      axisContributions.value = []
    }

    if (result.success) {
      lastSynthBase64.value = result.audio_base64
      resultAudio.value = base64ToDataUrl(result.audio_base64, 'audio/wav')
      resultSeed.value = result.seed
      generationTimeMs.value = result.generation_time_ms
      embeddingStats.value = result.embedding_stats

      // Feed into looper (crossfades if already playing)
      await looper.play(result.audio_base64)
      lastSynthFingerprint.value = synthFingerprint()

      // Record for research export
      const recordParams = synthMode.value === 'semanticAxes'
        ? { tab: 'synth_semantic', axes: Object.fromEntries(axisSlots.filter(s => s.axis).map(s => [s.axis, s.value])),
            duration: synth.duration, steps: synth.steps, cfg: synth.cfg, seed: synth.seed }
        : { tab: 'synth', prompt_a: synth.promptA, prompt_b: synth.promptB,
            alpha: synth.alpha, magnitude: synth.magnitude, noise_sigma: synth.noise,
            duration: synth.duration, steps: synth.steps, cfg: synth.cfg, seed: synth.seed }
      labRecord({
        parameters: recordParams,
        results: { seed: result.seed, generation_time_ms: result.generation_time_ms },
        outputs: [{ type: 'audio', format: 'wav', dataBase64: result.audio_base64 }],
      })

      // In wavetable mode, extract frames from the new buffer
      if (playbackMode.value === 'wavetable') {
        const buf = looper.getOriginalBuffer()
        if (buf) {
          await wavetableOsc.loadFrames(buf)
          if (!wavetableOsc.isPlaying.value) await wavetableOsc.start()
        }
        looper.stop() // looper not needed in wavetable mode
      }
    } else {
      error.value = result.error || 'Synth generation failed'
    }
  } catch (e) {
    error.value = String(e)
  } finally {
    generating.value = false
  }
}

// ===== MMAudio =====
async function runMMAudio() {
  clearResults()
  generating.value = true
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
    generating.value = false
  }
}

// ===== ImageBind Guidance =====
async function runGuidance() {
  clearResults()
  generating.value = true
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
    generating.value = false
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
  fetchSemanticAxes()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  envelope.dispose()
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
  margin-bottom: 1.5rem;
  line-height: 1.5;
}

/* Slider groups */
.slider-group {
  margin-bottom: 1.5rem;
}

.slider-item {
  margin-bottom: 1rem;
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
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.param {
  flex: 1;
  min-width: 100px;
}

.param label {
  display: block;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 0.3rem;
}

.param input,
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

.param input:focus,
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
  margin-bottom: 1rem;
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

.loop-btn,
.stop-btn {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
}

.loop-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.5);
}

.loop-btn.active {
  background: rgba(76, 175, 80, 0.15);
  border-color: rgba(76, 175, 80, 0.4);
  color: #4CAF50;
}

.stop-btn {
  background: rgba(255, 82, 82, 0.15);
  border: 1px solid rgba(255, 82, 82, 0.3);
  color: #ff5252;
}

.stop-btn:hover {
  background: rgba(255, 82, 82, 0.25);
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
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
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

.dual-range {
  position: relative;
  height: 1.5rem;
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
  gap: 0.6rem;
  margin-top: 0.8rem;
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
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  overflow: hidden;
}

.midi-section summary {
  padding: 0.7rem 1rem;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  background: rgba(255, 255, 255, 0.03);
}

.midi-section summary:hover {
  color: rgba(255, 255, 255, 0.7);
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

/* Dimension Explorer */
.dim-explorer-section {
  margin-top: 0.8rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 0.6rem;
}

.dim-explorer-section summary {
  cursor: pointer;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 500;
}

.dim-explorer-content {
  margin-top: 0.6rem;
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

.dim-controls-row {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  margin-top: 0.5rem;
  flex-wrap: wrap;
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

.dim-right-click-hint {
  font-size: 0.6rem;
  color: rgba(255, 255, 255, 0.2);
  margin-left: auto;
}

/* Playback mode selector (segmented control) */
.playback-mode-selector {
  display: flex;
  gap: 0;
  margin-bottom: 0.5rem;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  overflow: hidden;
}

.mode-btn {
  flex: 1;
  padding: 0.35rem 0.5rem;
  background: rgba(255, 255, 255, 0.03);
  border: none;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn:last-child {
  border-right: none;
}

.mode-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.06);
}

.mode-btn.active {
  background: rgba(76, 175, 80, 0.15);
  color: #4CAF50;
  font-weight: 600;
}

.mode-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* Wavetable controls */
.wavetable-controls {
  margin-bottom: 0.6rem;
}

.wavetable-frame-count {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.35);
  display: block;
  margin-top: 0.2rem;
}

/* ADSR Envelope */
.adsr-section {
  margin-top: 1rem;
  padding-top: 0.8rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
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

/* Synth Mode Toggle */
.synth-mode-toggle {
  display: flex;
  gap: 0;
  margin-bottom: 1.2rem;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  overflow: hidden;
}

.mode-toggle-btn {
  flex: 1;
  padding: 0.5rem 1rem;
  background: rgba(255, 255, 255, 0.03);
  border: none;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-toggle-btn:last-child {
  border-right: none;
}

.mode-toggle-btn:hover {
  background: rgba(255, 255, 255, 0.06);
}

.mode-toggle-btn.active {
  background: rgba(76, 175, 80, 0.15);
  color: #4CAF50;
  font-weight: 600;
}

/* Semantic Axes */
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
  max-width: 7rem;
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

.semantic-reset-btn {
  margin-bottom: 1rem;
}

</style>
