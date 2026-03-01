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

  const hasFrames = ref(false)
  const isPlaying = ref(false)
  const frameCount = ref(0)
  const currentFrequency = ref(440)

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
  function extractFrames(buffer: AudioBuffer): Float32Array[] {
    const nc = buffer.numberOfChannels
    const len = buffer.length
    const sr = buffer.sampleRate

    // Sum to mono
    const mono = new Float32Array(len)
    for (let ch = 0; ch < nc; ch++) {
      const data = buffer.getChannelData(ch)
      for (let i = 0; i < len; i++) mono[i] = mono[i]! + data[i]!
    }
    if (nc > 1) {
      const scale = 1 / nc
      for (let i = 0; i < len; i++) mono[i] = mono[i]! * scale
    }

    // Pre-compute Hann window for FRAME_SIZE
    const hann = new Float32Array(FRAME_SIZE)
    for (let i = 0; i < FRAME_SIZE; i++) {
      hann[i] = 0.5 * (1 - Math.cos(2 * Math.PI * i / FRAME_SIZE))
    }

    // --- Pitch-synchronous extraction ---
    const result: Float32Array[] = []

    if (len >= PITCH_ANALYSIS_WINDOW) {
      const detector = PitchDetector.forFloat32Array(PITCH_ANALYSIS_WINDOW)
      const hop = Math.floor(PITCH_ANALYSIS_WINDOW / 2)
      const analysisWindow = new Float32Array(PITCH_ANALYSIS_WINDOW)

      for (let pos = 0; pos + PITCH_ANALYSIS_WINDOW <= len; pos += hop) {
        analysisWindow.set(mono.subarray(pos, pos + PITCH_ANALYSIS_WINDOW))
        const [pitch, clarity] = detector.findPitch(analysisWindow, sr)

        if (clarity >= PITCH_CONFIDENCE_THRESHOLD && pitch > 20 && pitch < 20000) {
          const periodSamples = Math.round(sr / pitch)
          if (periodSamples < 4 || periodSamples > len) continue

          // Align extraction start to nearest zero-crossing
          const center = pos + Math.floor(PITCH_ANALYSIS_WINDOW / 2)
          const start = nearestZeroCrossing(mono, center - Math.floor(periodSamples / 2), periodSamples)

          if (start >= 0 && start + periodSamples <= len) {
            // Extract one period
            const period = mono.slice(start, start + periodSamples)
            // Resample to FRAME_SIZE
            const resampled = sincResample(period, FRAME_SIZE)
            // Apply Hann window
            for (let i = 0; i < FRAME_SIZE; i++) {
              resampled[i]! *= hann[i]!
            }
            result.push(resampled)
          }
        }
      }
    }

    // --- Fallback: overlapping windowed extraction (50% overlap + Hann) ---
    if (result.length < MIN_FRAMES) {
      result.length = 0 // discard sparse pitch-sync frames; windowed fallback is more consistent
      const overlap = Math.floor(FRAME_SIZE / 2)
      let offset = 0
      while (offset + FRAME_SIZE <= len) {
        const frame = new Float32Array(FRAME_SIZE)
        for (let i = 0; i < FRAME_SIZE; i++) {
          frame[i] = mono[offset + i]! * hann[i]!
        }
        result.push(frame)
        offset += overlap
      }
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

    return result
  }

  async function loadFrames(buffer: AudioBuffer): Promise<void> {
    frames = extractFrames(buffer)
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
  }

  function stop(): void {
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

  function setScanPosition(pos: number): void {
    const clamped = Math.max(0, Math.min(1, pos))
    if (workletNode) {
      const param = workletNode.parameters.get('scanPosition')
      if (param) param.value = clamped
    }
  }

  function setDestination(node: AudioNode | null): void {
    destinationNode = node
  }

  function getContext(): AudioContext {
    return ensureContext()
  }

  function dispose(): void {
    stop()
    frames = []
    hasFrames.value = false
    frameCount.value = 0
    if (ctx && ctx.state !== 'closed') ctx.close()
    ctx = null
    workletReady = false
  }

  return {
    hasFrames: readonly(hasFrames),
    isPlaying: readonly(isPlaying),
    frameCount: readonly(frameCount),
    currentFrequency: readonly(currentFrequency),

    loadFrames,
    start,
    stop,
    setContext,
    setFrequency,
    setFrequencyFromNote,
    setScanPosition,
    setDestination,
    getContext,
    dispose,
  }
}
