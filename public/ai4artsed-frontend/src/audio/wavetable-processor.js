/**
 * AudioWorklet processor for wavetable synthesis with mip-mapped anti-aliasing.
 *
 * Phase-accumulator reads single-cycle frames at a controlled frequency.
 * Catmull-Rom cubic interpolation between frames provides smooth timbral
 * morphing via the scanPosition parameter.
 *
 * Mip-mapping: each frame exists at multiple band-limited levels. Higher
 * playback frequencies use levels with fewer harmonics, preventing aliasing.
 * Level k has (1024 >> k) harmonics. Level selection based on frequency.
 *
 * Scan smoothing: one-pole lowpass on scanPosition prevents clicks when
 * frame content changes abruptly at the current phase position.
 *
 * Frame size: 2048 samples (~21.5 Hz fundamental at 44.1 kHz).
 */

const FRAME_SIZE = 2048
// Scan smoothing: ~5ms time constant at 44.1kHz (prevents clicks on frame transitions)
const SCAN_SMOOTH_COEFF = 1.0 - Math.exp(-1.0 / (44100 * 0.005))

class WavetableProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.mipFrames = []   // mipFrames[level][frameIndex] = Float32Array
    this.numLevels = 0
    this.numFrames = 0
    this.phase = 0
    this.smoothedScan = 0 // Smoothed scan position (one-pole lowpass)
    this.port.onmessage = (e) => {
      if (e.data && e.data.mipFrames) {
        this.mipFrames = e.data.mipFrames
        this.numLevels = this.mipFrames.length
        this.numFrames = this.numLevels > 0 ? this.mipFrames[0].length : 0
      }
    }
  }

  static get parameterDescriptors() {
    return [
      { name: 'frequency', defaultValue: 440, minValue: 20, maxValue: 20000, automationRate: 'a-rate' },
      { name: 'scanPosition', defaultValue: 0, minValue: 0, maxValue: 1, automationRate: 'a-rate' },
      { name: 'interpolate', defaultValue: 1, minValue: 0, maxValue: 1, automationRate: 'k-rate' },
    ]
  }

  process(_inputs, outputs, parameters) {
    const output = outputs[0] && outputs[0][0]
    if (!output || this.numFrames === 0) return true

    const numFrames = this.numFrames
    const numLevels = this.numLevels
    const freqParam = parameters.frequency
    const scanParam = parameters.scanPosition
    const interpParam = parameters.interpolate
    const freqConstant = freqParam.length === 1
    const scanConstant = scanParam.length === 1
    const doInterpolate = interpParam[0] >= 0.5
    const coeff = SCAN_SMOOTH_COEFF

    const invBaseFreq = FRAME_SIZE / sampleRate
    const log2 = Math.log2
    const maxLevel = numLevels - 1
    let smoothed = this.smoothedScan

    for (let i = 0; i < output.length; i++) {
      const freq = freqConstant ? freqParam[0] : freqParam[i]
      const rawScan = scanConstant ? scanParam[0] : scanParam[i]

      // One-pole lowpass on scan position — prevents clicks on frame transitions
      smoothed += (rawScan - smoothed) * coeff

      // Select mip level based on playback frequency
      const rawLevel = log2(freq * invBaseFreq)
      const mipLevel = Math.max(0, Math.min(maxLevel, Math.ceil(rawLevel)))
      const frames = this.mipFrames[mipLevel]

      // Frame selection via smoothed scan position
      const framePos = smoothed * (numFrames - 1)
      const frameA = Math.floor(framePos)

      // Sample position via phase accumulator
      const idx0 = Math.floor(this.phase) % FRAME_SIZE
      const idx1 = (idx0 + 1) % FRAME_SIZE
      const phaseFrac = this.phase - Math.floor(this.phase)

      const a = frames[frameA]
      const sampleA = a[idx0] + (a[idx1] - a[idx0]) * phaseFrac

      if (doInterpolate) {
        // Catmull-Rom cubic interpolation across 4 frames for smooth morphing
        const frameMix = framePos - frameA
        const i0 = Math.max(frameA - 1, 0)
        const i1 = frameA
        const i2 = Math.min(frameA + 1, numFrames - 1)
        const i3 = Math.min(frameA + 2, numFrames - 1)

        const f0 = frames[i0]
        const f1 = frames[i1]
        const f2 = frames[i2]
        const f3 = frames[i3]

        const s0 = f0[idx0] + (f0[idx1] - f0[idx0]) * phaseFrac
        const s1 = f1[idx0] + (f1[idx1] - f1[idx0]) * phaseFrac
        const s2 = f2[idx0] + (f2[idx1] - f2[idx0]) * phaseFrac
        const s3 = f3[idx0] + (f3[idx1] - f3[idx0]) * phaseFrac

        // Catmull-Rom spline
        const t = frameMix
        const t2 = t * t
        const t3 = t2 * t
        output[i] = 0.5 * (
          (2 * s1) +
          (-s0 + s2) * t +
          (2 * s0 - 5 * s1 + 4 * s2 - s3) * t2 +
          (-s0 + 3 * s1 - 3 * s2 + s3) * t3
        )
      } else {
        // Stepped: hard frame switch, no frame interpolation (raw wavetable)
        output[i] = sampleA
      }

      // Advance phase, wrap to prevent float precision loss
      this.phase += freq * FRAME_SIZE / sampleRate
      if (this.phase >= FRAME_SIZE) {
        this.phase -= FRAME_SIZE * Math.floor(this.phase / FRAME_SIZE)
      }
    }

    this.smoothedScan = smoothed
    return true
  }
}

registerProcessor('wavetable-processor', WavetableProcessor)
