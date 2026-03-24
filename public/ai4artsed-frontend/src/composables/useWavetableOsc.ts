/**
 * Composable for wavetable oscillator playback.
 *
 * Extracts single-cycle frames from an AudioBuffer using pitch-synchronous
 * analysis (pitchy McLeod Pitch Method). Each detected period is resampled
 * to FRAME_SIZE via Lanczos sinc interpolation and Hann-windowed.
 * Falls back to overlapping windowed extraction for unpitched/noisy audio.
 *
 * Scan position morphs between frames for timbral control.
 */
import { ref, readonly } from 'vue'
import { PitchDetector } from 'pitchy'

const FRAME_SIZE = 2048
const MIN_FRAMES = 8
const PITCH_ANALYSIS_WINDOW = 4096
const PITCH_CONFIDENCE_THRESHOLD = 0.9
const SINC_KERNEL_A = 6

export function useWavetableOsc() {
  let ctx: AudioContext | null = null
  let workletNode: AudioWorkletNode | null = null
  let gainNode: GainNode | null = null
  let workletReady = false
  let frames: Float32Array[] = []
  let destinationNode: AudioNode | null = null
  let pendingScan: { attack: number; decay: number; start: number; end: number } | null = null

  const hasFrames = ref(false)
  const isPlaying = ref(false)
  const frameCount = ref(0)
  const currentFrequency = ref(440)
  const detectedPitch = ref(0)

  /** Accept an external AudioContext (e.g. from looper) for shared routing. */
  function setContext(ac: AudioContext): void {
    if (ctx && ctx !== ac) {
      stop()
      workletReady = false
    }
    ctx = ac
  }

  function ensureContext(): AudioContext {
    if (!ctx || ctx.state === 'closed') {
      ctx = new AudioContext()
      workletReady = false
    }
    if (ctx.state === 'suspended') ctx.resume()
    return ctx
  }

  async function ensureWorklet(ac: AudioContext): Promise<void> {
    if (workletReady) return
    await ac.audioWorklet.addModule(
      new URL('../audio/wavetable-processor.js', import.meta.url),
    )
    workletReady = true
  }

  /**
   * Lanczos windowed sinc resampling (local copy — avoids coupling with useAudioLooper).
   */
  function sincResample(input: Float32Array, outputLen: number): Float32Array {
    const inputLen = input.length
    if (inputLen === outputLen) return new Float32Array(input)
    if (inputLen === 0 || outputLen === 0) return new Float32Array(outputLen)

    const output = new Float32Array(outputLen)
    const ratio = inputLen / outputLen
    const filterScale = Math.max(1.0, ratio)
    const kernelRadius = Math.ceil(SINC_KERNEL_A * filterScale)
    const invFS = 1.0 / filterScale

    for (let i = 0; i < outputLen; i++) {
      const center = i * ratio
      const lo = Math.max(0, Math.ceil(center - kernelRadius))
      const hi = Math.min(inputLen - 1, Math.floor(center + kernelRadius))
      let sum = 0, wSum = 0

      for (let j = lo; j <= hi; j++) {
        const x = (j - center) * invFS
        let w: number
        if (Math.abs(x) < 1e-7) {
          w = 1.0
        } else if (Math.abs(x) >= SINC_KERNEL_A) {
          w = 0.0
        } else {
          const px = Math.PI * x
          const pxa = px / SINC_KERNEL_A
          w = (Math.sin(px) / px) * (Math.sin(pxa) / pxa)
        }
        sum += input[j]! * w
        wSum += w
      }
      output[i] = wSum > 1e-10 ? sum / wSum : 0
    }
    return output
  }

  /** Find nearest zero-crossing to `pos`, searching ±maxSearch samples. */
  function nearestZeroCrossing(mono: Float32Array, pos: number, maxSearch: number): number {
    const len = mono.length
    let best = pos
    let bestDist = maxSearch + 1
    for (let d = 0; d <= maxSearch; d++) {
      // Search forward
      const fwd = pos + d
      if (fwd < len - 1 && mono[fwd]! * mono[fwd + 1]! <= 0 && d < bestDist) {
        best = fwd
        bestDist = d
        break // first found is nearest
      }
      // Search backward
      const bwd = pos - d
      if (bwd >= 0 && bwd < len - 1 && mono[bwd]! * mono[bwd + 1]! <= 0 && d < bestDist) {
        best = bwd
        bestDist = d
        break
      }
    }
    return best
  }

  /**
   * Pitch-synchronous wavetable extraction.
   *
   * 1. Sum to mono
   * 2. Detect pitch at analysis points using pitchy (McLeod Pitch Method)
   * 3. For high-confidence detections: extract one period, align to zero-crossing,
   *    resample to FRAME_SIZE via Lanczos sinc, apply Hann window
   * 4. Fallback for unpitched/noisy audio: overlapping windowed extraction (50% overlap + Hann)
   */
  /**
   * Make a frame seamlessly loopable by spreading the loop-point discontinuity
   * as an imperceptible linear slope across all samples. Standard wavetable
   * technique — preserves harmonics (unlike Hann which destroys them).
   */
  function makeLoopSafe(frame: Float32Array): void {
    const n = frame.length
    if (n < 2) return
    const disc = frame[0]! - frame[n - 1]!
    if (Math.abs(disc) < 1e-7) return
    const step = disc / (n - 1)
    for (let i = 0; i < n; i++) {
      frame[i]! -= step * (n - 1 - i)
    }
  }

  /** Sum an AudioBuffer to mono, optionally slicing to [startSample, endSample). */
  function bufferToMono(buffer: AudioBuffer, startSample = 0, endSample = buffer.length): Float32Array {
    const nc = buffer.numberOfChannels
    const lo = Math.max(0, startSample)
    const hi = Math.min(buffer.length, endSample)
    const len = hi - lo
    const mono = new Float32Array(len)
    for (let ch = 0; ch < nc; ch++) {
      const data = buffer.getChannelData(ch)
      for (let i = 0; i < len; i++) mono[i] = mono[i]! + data[lo + i]!
    }
    if (nc > 1) {
      const scale = 1 / nc
      for (let i = 0; i < len; i++) mono[i] = mono[i]! * scale
    }
    return mono
  }

  interface ExtractionResult {
    frames: Float32Array[]
    medianPitchHz: number
  }

  function extractFrames(mono: Float32Array, sr: number): ExtractionResult {
    const len = mono.length

    // Hann window for fallback path (unpitched audio needs windowing for clean loops)
    const hann = new Float32Array(FRAME_SIZE)
    for (let i = 0; i < FRAME_SIZE; i++) {
      hann[i] = 0.5 * (1 - Math.cos(2 * Math.PI * i / FRAME_SIZE))
    }

    // --- Pitch-synchronous extraction ---
    // Uses linear-ramp discontinuity fix instead of Hann: preserves ALL harmonics
    // while ensuring seamless looping.
    const result: Float32Array[] = []
    const pitches: number[] = []

    if (len >= PITCH_ANALYSIS_WINDOW) {
      const detector = PitchDetector.forFloat32Array(PITCH_ANALYSIS_WINDOW)
      const hop = Math.floor(PITCH_ANALYSIS_WINDOW / 2)
      const analysisWindow = new Float32Array(PITCH_ANALYSIS_WINDOW)

      for (let pos = 0; pos + PITCH_ANALYSIS_WINDOW <= len; pos += hop) {
        analysisWindow.set(mono.subarray(pos, pos + PITCH_ANALYSIS_WINDOW))
        const [pitch, clarity] = detector.findPitch(analysisWindow, sr)

        if (clarity >= PITCH_CONFIDENCE_THRESHOLD && pitch > 20 && pitch < 20000) {
          pitches.push(pitch)
          const periodSamples = Math.round(sr / pitch)
          if (periodSamples < 4 || periodSamples > len) continue

          // Align extraction start to nearest zero-crossing
          const center = pos + Math.floor(PITCH_ANALYSIS_WINDOW / 2)
          const start = nearestZeroCrossing(mono, center - Math.floor(periodSamples / 2), periodSamples)

          if (start >= 0 && start + periodSamples <= len) {
            const period = mono.slice(start, start + periodSamples)
            const resampled = sincResample(period, FRAME_SIZE)
            makeLoopSafe(resampled)
            normalizeFrame(resampled)
            result.push(resampled)
          }
        }
      }
    }

    if (result.length > 0) {
      console.log(`[WT] pitch-sync extraction: ${result.length} frames`)
    }

    // --- Fallback: overlapping Hann-windowed extraction (unpitched/noisy audio) ---
    if (result.length < MIN_FRAMES) {
      result.length = 0
      const overlap = Math.floor(FRAME_SIZE / 2)
      let offset = 0
      while (offset + FRAME_SIZE <= len) {
        const frame = new Float32Array(FRAME_SIZE)
        for (let i = 0; i < FRAME_SIZE; i++) {
          frame[i] = mono[offset + i]! * hann[i]!
        }
        normalizeFrame(frame)
        result.push(frame)
        offset += overlap
      }
      console.log(`[WT] fallback extraction (Hann): ${result.length} frames`)
    }

    // Pad to MIN_FRAMES
    if (result.length === 0) {
      const padded = new Float32Array(FRAME_SIZE)
      padded.set(mono.subarray(0, Math.min(len, FRAME_SIZE)))
      for (let i = 0; i < FRAME_SIZE; i++) padded[i]! *= hann[i]!
      result.push(padded)
    }
    while (result.length < MIN_FRAMES) {
      result.push(new Float32Array(result[result.length - 1]!))
    }

    // Median pitch (sorted middle element)
    let medianPitchHz = 0
    if (pitches.length > 0) {
      pitches.sort((a, b) => a - b)
      medianPitchHz = pitches[Math.floor(pitches.length / 2)]!
    }

    return { frames: result, medianPitchHz }
  }

  /**
   * Extract wavetable frames from an AudioBuffer.
   * Optional startSample/endSample limit extraction to a region (for user-selected range).
   */
  async function loadFrames(buffer: AudioBuffer, startSample = 0, endSample = buffer.length): Promise<void> {
    const mono = bufferToMono(buffer, startSample, endSample)
    const { frames: extracted, medianPitchHz } = extractFrames(mono, buffer.sampleRate)
    frames = extracted
    frameCount.value = frames.length
    hasFrames.value = true
    detectedPitch.value = medianPitchHz

    // Default playback at detected pitch so timbre is immediately recognizable
    if (medianPitchHz > 0) {
      currentFrequency.value = medianPitchHz
      if (workletNode) {
        const freqParam = workletNode.parameters.get('frequency')
        if (freqParam) freqParam.value = medianPitchHz
      }
    }

    if (workletNode) {
      workletNode.port.postMessage({ frames })
    }
  }

  /** Normalize a frame to peak amplitude 1.0 to prevent volume jumps when scanning. */
  function normalizeFrame(frame: Float32Array): void {
    let peak = 0
    for (let i = 0; i < frame.length; i++) {
      const abs = Math.abs(frame[i]!)
      if (abs > peak) peak = abs
    }
    if (peak > 1e-6) {
      const scale = 1.0 / peak
      for (let i = 0; i < frame.length; i++) {
        frame[i]! *= scale
      }
    }
  }

  /**
   * Load pre-extracted frames directly (e.g. from semantic wavetable builder).
   * Each frame should be a single-cycle waveform. Frames are resampled to
   * FRAME_SIZE, loop-safed, and peak-normalized to prevent volume jumps.
   */
  function loadRawFrames(rawFrames: Float32Array[]): void {
    if (rawFrames.length === 0) return

    frames = rawFrames.map(f => {
      // Resample to FRAME_SIZE if needed
      const resampled = f.length === FRAME_SIZE ? new Float32Array(f) : sincResample(f, FRAME_SIZE)
      // Linear ramp loop-safe (preserves harmonics, unlike Hann)
      makeLoopSafe(resampled)
      // Normalize to peak 1.0
      normalizeFrame(resampled)
      return resampled
    })

    // Pad to MIN_FRAMES if needed
    while (frames.length < MIN_FRAMES) {
      frames.push(new Float32Array(frames[frames.length - 1]!))
    }

    frameCount.value = frames.length
    hasFrames.value = true

    if (workletNode) {
      workletNode.port.postMessage({ frames })
    }
  }

  async function start(): Promise<void> {
    if (isPlaying.value) return
    const ac = ensureContext()
    await ensureWorklet(ac)

    // Create fresh node chain
    workletNode = new AudioWorkletNode(ac, 'wavetable-processor', {
      numberOfInputs: 0,
      numberOfOutputs: 1,
      outputChannelCount: [1],
    })
    gainNode = ac.createGain()
    gainNode.gain.value = 0.5
    workletNode.connect(gainNode)
    gainNode.connect(destinationNode ?? ac.destination)

    // Send frames if already loaded
    if (frames.length > 0) {
      workletNode.port.postMessage({ frames })
    }

    // Set initial frequency
    const freqParam = workletNode.parameters.get('frequency')
    if (freqParam) freqParam.value = currentFrequency.value

    isPlaying.value = true

    // Apply deferred scan envelope (fixes async race: triggerScanEnvelope
    // may have been called before the worklet node was created)
    if (pendingScan) {
      const { attack, decay, start: s, end: e } = pendingScan
      pendingScan = null
      scheduleScanRamp(attack, decay, s, e)
    }
  }

  function stop(): void {
    pendingScan = null
    if (workletNode) {
      workletNode.disconnect()
      workletNode = null
    }
    if (gainNode) {
      gainNode.disconnect()
      gainNode = null
    }
    isPlaying.value = false
  }

  function setFrequency(hz: number): void {
    currentFrequency.value = Math.max(20, Math.min(20000, hz))
    if (workletNode) {
      const param = workletNode.parameters.get('frequency')
      if (param) param.value = currentFrequency.value
    }
  }

  function setFrequencyFromNote(midiNote: number): void {
    setFrequency(440 * Math.pow(2, (midiNote - 69) / 12))
  }

  function glideToNote(midiNote: number, timeMs: number): void {
    glideToFrequency(440 * Math.pow(2, (midiNote - 69) / 12), timeMs)
  }

  function glideToFrequency(hz: number, timeMs: number): void {
    currentFrequency.value = Math.max(20, Math.min(20000, hz))
    if (workletNode) {
      const param = workletNode.parameters.get('frequency')
      if (param) {
        const ac = ctx ?? ensureContext()
        const now = ac.currentTime
        // Anchor current value before ramp (required by Web Audio spec)
        param.setValueAtTime(param.value, now)
        param.linearRampToValueAtTime(currentFrequency.value, now + timeMs / 1000)
      }
    }
  }

  function setScanPosition(pos: number): void {
    const clamped = Math.max(0, Math.min(1, pos))
    if (workletNode) {
      const param = workletNode.parameters.get('scanPosition')
      if (param) {
        param.cancelScheduledValues(0)
        param.value = clamped
      }
    }
  }

  /** Toggle frame interpolation: true = smooth morph, false = stepped/raw. */
  function setInterpolate(on: boolean): void {
    if (workletNode) {
      const param = workletNode.parameters.get('interpolate')
      if (param) param.value = on ? 1 : 0
    }
  }

  /**
   * Schedule the ADR scan ramp on the worklet's scanPosition AudioParam.
   * Exponential ramps (RC-curve): A sweeps scanStart→scanEnd, D sweeps scanEnd→scanStart.
   * Floor at 0.001 because exponentialRamp requires values > 0.
   */
  function scheduleScanRamp(attackMs: number, decayMs: number, scanStart: number, scanEnd: number): void {
    if (!workletNode) return
    const param = workletNode.parameters.get('scanPosition')
    if (!param) return

    const now = (ctx ?? ensureContext()).currentTime
    const aSec = attackMs / 1000
    const dSec = decayMs / 1000
    const lo = Math.max(0.001, scanStart)
    const hi = Math.max(0.001, scanEnd)

    param.cancelScheduledValues(now)
    param.setValueAtTime(lo, now)
    if (aSec > 0) {
      param.exponentialRampToValueAtTime(hi, now + aSec)
    } else {
      param.setValueAtTime(hi, now)
    }
    if (dSec > 0) {
      param.exponentialRampToValueAtTime(lo, now + aSec + dSec)
    }
  }

  /**
   * Trigger scan envelope (ADR): sweep scanStart→scanEnd (Attack), then back (Decay).
   * If the worklet is not yet ready (async start), the envelope is deferred
   * and applied automatically once start() completes.
   */
  function triggerScanEnvelope(attackMs: number, decayMs: number, scanStart = 0, scanEnd = 1): void {
    pendingScan = { attack: attackMs, decay: decayMs, start: scanStart, end: scanEnd }
    if (workletNode) {
      const { attack, decay, start: s, end: e } = pendingScan
      pendingScan = null
      scheduleScanRamp(attack, decay, s, e)
    }
  }

  /**
   * Release: read current scan position, cancel automation,
   * then exponential ramp to scanTarget. Starts from wherever
   * the scan is — whether in A or D phase (ADSR principle).
   * Avoids cancelAndHoldAtTime (unreliable across browsers).
   */
  function stopScanEnvelope(releaseMs: number = 200, scanTarget = 0): void {
    if (!workletNode) return
    const param = workletNode.parameters.get('scanPosition')
    if (!param) return

    const now = (ctx ?? ensureContext()).currentTime
    const rSec = releaseMs / 1000
    const current = Math.max(0.001, param.value)
    const target = Math.max(0.001, scanTarget)

    param.cancelScheduledValues(now)
    param.setValueAtTime(current, now)
    if (rSec > 0) {
      param.exponentialRampToValueAtTime(target, now + rSec)
    } else {
      param.setValueAtTime(target, now)
    }
  }

  function setDestination(node: AudioNode | null): void {
    destinationNode = node
  }

  function getContext(): AudioContext {
    return ensureContext()
  }

  /** Get frame data for visualization. Returns null if index out of range. */
  function getFrameData(index: number): Float32Array | null {
    if (index < 0 || index >= frames.length) return null
    return frames[index]!
  }

  function dispose(): void {
    stop()
    frames = []
    hasFrames.value = false
    frameCount.value = 0
    detectedPitch.value = 0
    if (ctx && ctx.state !== 'closed') ctx.close()
    ctx = null
    workletReady = false
  }

  return {
    hasFrames: readonly(hasFrames),
    isPlaying: readonly(isPlaying),
    frameCount: readonly(frameCount),
    currentFrequency: readonly(currentFrequency),
    detectedPitch: readonly(detectedPitch),

    loadFrames,
    loadRawFrames,
    start,
    stop,
    setContext,
    setFrequency,
    setFrequencyFromNote,
    glideToNote,
    glideToFrequency,
    setScanPosition,
    setInterpolate,
    triggerScanEnvelope,
    stopScanEnvelope,
    setDestination,
    getContext,
    getFrameData,
    dispose,
  }
}
