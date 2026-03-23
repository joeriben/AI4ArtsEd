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
        // Bilinear: smooth interpolation between adjacent frames
        const frameB = Math.min(frameA + 1, numFrames - 1)
        const frameMix = framePos - frameA
        const b = this.frames[frameB]
        const sampleB = b[idx0] + (b[idx1] - b[idx0]) * phaseFrac
        output[i] = sampleA + (sampleB - sampleA) * frameMix
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
