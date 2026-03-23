/**
 * AudioWorklet processor for wavetable synthesis.
 *
 * Phase-accumulator reads single-cycle frames at a controlled frequency.
 * Bilinear interpolation between adjacent samples and adjacent frames
 * provides smooth timbral morphing via the scanPosition parameter.
 *
 * Frame size: 2048 samples (~21.5 Hz fundamental at 44.1 kHz).
 */

const FRAME_SIZE = 2048

class WavetableProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.frames = []
    this.phase = 0
    this.port.onmessage = (e) => {
      if (e.data && e.data.frames) {
        this.frames = e.data.frames
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
    if (!output || this.frames.length === 0) return true

    const numFrames = this.frames.length
    const freqParam = parameters.frequency
    const scanParam = parameters.scanPosition
    const interpParam = parameters.interpolate
    const freqConstant = freqParam.length === 1
    const scanConstant = scanParam.length === 1
    const doInterpolate = interpParam[0] >= 0.5

    for (let i = 0; i < output.length; i++) {
      const freq = freqConstant ? freqParam[0] : freqParam[i]
      const scan = scanConstant ? scanParam[0] : scanParam[i]

      // Frame selection via scan position
      const framePos = scan * (numFrames - 1)
      const frameA = Math.floor(framePos)

      // Sample position via phase accumulator
      const idx0 = Math.floor(this.phase) % FRAME_SIZE
      const idx1 = (idx0 + 1) % FRAME_SIZE
      const phaseFrac = this.phase - Math.floor(this.phase)

      const a = this.frames[frameA]
      const sampleA = a[idx0] + (a[idx1] - a[idx0]) * phaseFrac

      if (doInterpolate) {
        // Catmull-Rom cubic interpolation across 4 frames for smooth morphing
        const frameMix = framePos - frameA
        const i0 = Math.max(frameA - 1, 0)
        const i1 = frameA
        const i2 = Math.min(frameA + 1, numFrames - 1)
        const i3 = Math.min(frameA + 2, numFrames - 1)

        const f0 = this.frames[i0]
        const f1 = this.frames[i1]
        const f2 = this.frames[i2]
        const f3 = this.frames[i3]

        // Sample each frame at current phase (linear within-frame)
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

    return true
  }
}

registerProcessor('wavetable-processor', WavetableProcessor)
