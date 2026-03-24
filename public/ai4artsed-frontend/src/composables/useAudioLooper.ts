/**
 * Web Audio API looper composable for Crossmodal Lab Synth tab.
 *
 * - Linear crossfade (linearRampToValueAtTime — safe from AudioParam racing)
 * - Cross-correlation loop-point optimization for seamless oscillator-like loops
 * - Pitch transposition via playbackRate (preserves timing characteristics)
 * - Adjustable crossfade duration, loop interval
 * - Peak normalization (playback only), raw/loop WAV export
 *
 * AudioContext is created lazily on first play() call (browser autoplay policy).
 *
 * Equal-power crossfade: Boris Smus, "Web Audio API" (O'Reilly, 2013), Ch. 3
 * https://webaudioapi.com/book/Web_Audio_API_Boris_Smus_html/ch03.html
 * License: CC-BY-NC-ND 3.0
 */
import { ref, readonly } from 'vue'

// ═══════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════

const SCHEDULE_AHEAD = 0.005 // 5ms lookahead for scheduling safety
// Loop optimization
const XCORR_WINDOW = 512    // comparison window (samples)
const XCORR_SEARCH = 2000   // search radius (samples)

// ═══════════════════════════════════════════════════════════════════
// DSP utilities (stateless, pure functions)
// ═══════════════════════════════════════════════════════════════════


function encodeWav(buffer: AudioBuffer, startSample: number, endSample: number): Blob {
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

/**
 * Cross-correlation loop-point optimizer.
 * Finds the best loopEnd position (near the user's choice) where the waveform
 * at the end of the loop best matches the waveform at the start.
 * Uses normalized cross-correlation on channel 0.
 */
function optimizeLoopEndSample(
  data: Float32Array, loopStart: number, loopEnd: number,
): number {
  const win = Math.min(XCORR_WINDOW, Math.floor((loopEnd - loopStart) / 4))
  if (win < 16) return loopEnd

  // Reference: first `win` samples of the loop
  const searchLo = Math.max(loopStart + win * 2, loopEnd - XCORR_SEARCH)
  const searchHi = Math.min(data.length, loopEnd + XCORR_SEARCH)

  let bestCorr = -Infinity
  let bestEnd = loopEnd

  for (let cand = searchLo; cand < searchHi; cand++) {
    const eStart = cand - win
    if (eStart < loopStart) continue

    let sum = 0, normA = 0, normB = 0
    for (let i = 0; i < win; i++) {
      const a = data[loopStart + i]!
      const b = data[eStart + i]!
      sum += a * b
      normA += a * a
      normB += b * b
    }
    const denom = Math.sqrt(normA * normB)
    const corr = denom > 0 ? sum / denom : 0

    if (corr > bestCorr) {
      bestCorr = corr
      bestEnd = cand
    }
  }
  return bestEnd
}

/**
 * Loop crossfade: blend tail audio INTO head, then shorten loopEnd.
 *
 * AudioBufferSourceNode jumps instantly from loopEnd→loopStart (no built-in
 * crossfade). We make this seamless by mixing the last N samples of the loop
 * into the first N samples with equal-power crossfade, then moving loopEnd
 * back by N so the raw tail is never played.
 *
 * After processing, the sample at new loopEnd-1 is original audio, and the
 * sample at loopStart is almost pure tail audio — these are adjacent in the
 * original buffer, so the wrap transition is continuous.
 */
function applyLoopProcessing(
  ac: AudioContext, source: AudioBuffer,
  loopStart: number, loopEnd: number,
  optimize: boolean, crossfadeMs: number,
): { buffer: AudioBuffer; optimizedEnd: number; fadeSamples: number } {
  const copy = ac.createBuffer(source.numberOfChannels, source.length, source.sampleRate)
  for (let ch = 0; ch < source.numberOfChannels; ch++) {
    copy.getChannelData(ch).set(source.getChannelData(ch))
  }

  let actualEnd = loopEnd
  if (optimize && source.numberOfChannels > 0) {
    actualEnd = optimizeLoopEndSample(source.getChannelData(0), loopStart, loopEnd)
  }

  const loopLen = actualEnd - loopStart
  const fadeSamples = Math.min(
    Math.floor(crossfadeMs / 1000 * source.sampleRate),
    Math.floor(loopLen / 2), // max half the loop (prevents head/tail overlap)
  )

  if (fadeSamples >= 2) {
    for (let ch = 0; ch < copy.numberOfChannels; ch++) {
      const d = copy.getChannelData(ch)
      for (let i = 0; i < fadeSamples; i++) {
        const t = i / fadeSamples
        const gHead = Math.sin(t * Math.PI * 0.5) // 0→1
        const gTail = Math.cos(t * Math.PI * 0.5) // 1→0
        const headIdx = loopStart + i
        const tailIdx = actualEnd - fadeSamples + i
        // Blend fading-out tail into fading-in head. Tail region left untouched.
        d[headIdx] = d[headIdx]! * gHead + d[tailIdx]! * gTail
      }
    }
    // Shorten loop: tail samples are baked into head, never played directly
    actualEnd -= fadeSamples
  }

  return { buffer: copy, optimizedEnd: actualEnd, fadeSamples }
}

/**
 * Create palindrome buffer for ping-pong looping.
 * Forward: [loopStart ... loopEnd-1], Reverse: [loopEnd-2 ... loopStart+1].
 * Endpoints are NOT doubled → seamless forward↔reverse transitions.
 */
function createPalindromeBuffer(
  ac: AudioContext, source: AudioBuffer,
  loopStart: number, loopEnd: number,
): { buffer: AudioBuffer; palindromeEnd: number } {
  const loopLen = loopEnd - loopStart
  if (loopLen < 4) return { buffer: source, palindromeEnd: loopEnd }

  const reverseLen = loopLen - 2
  const newLen = source.length + reverseLen
  const result = ac.createBuffer(source.numberOfChannels, newLen, source.sampleRate)

  for (let ch = 0; ch < source.numberOfChannels; ch++) {
    const src = source.getChannelData(ch)
    const dst = result.getChannelData(ch)
    // Copy everything up to loopEnd
    for (let i = 0; i < loopEnd; i++) dst[i] = src[i]!
    // Insert reversed loop (skip endpoints to avoid doubling)
    for (let i = 0; i < reverseLen; i++) {
      dst[loopEnd + i] = src[loopEnd - 2 - i]!
    }
    // Copy post-loop data (shifted)
    for (let i = loopEnd; i < src.length; i++) {
      dst[i + reverseLen] = src[i]!
    }
  }

  return { buffer: result, palindromeEnd: loopEnd + reverseLen }
}

// ═══════════════════════════════════════════════════════════════════
// Composable
// ═══════════════════════════════════════════════════════════════════

export function useAudioLooper() {
  let ctx: AudioContext | null = null
  let activeSource: AudioBufferSourceNode | null = null
  let activeGain: GainNode | null = null
  let originalBuffer: AudioBuffer | null = null
  let rawBase64: string | null = null
  let destinationNode: AudioNode | null = null

  const isPlaying = ref(false)
  const isLooping = ref(false)
  const transposeSemitones = ref(0)
  const loopStartFrac = ref(0)
  const loopEndFrac = ref(1)
  const bufferDuration = ref(0)
  const hasAudio = ref(false)
  const crossfadeMs = ref(150)
  const normalizeOn = ref(true)
  const peakAmplitude = ref(0)
  const loopOptimize = ref(false)
  const loopPingPong = ref(false)
  // Optimized loop end as fraction (for display, may differ from user's loopEndFrac)
  const optimizedEndFrac = ref(1)
  // Internal loop bounds in seconds (decoupled from fractions when buffer length changes, e.g. palindrome)
  let preparedLoopStartSec = 0
  let preparedLoopEndSec = 0
  // Offset past the crossfade zone for cold starts (first play from silence)
  let preparedColdStartSec = 0

  function ensureContext(): AudioContext {
    if (!ctx || ctx.state === 'closed') ctx = new AudioContext()
    if (ctx.state === 'suspended') ctx.resume()
    return ctx
  }

  function rateForPlayback(): number {
    return Math.pow(2, transposeSemitones.value / 12)
  }

  function loopBoundsSamples(buf: AudioBuffer): [number, number] {
    return [
      Math.floor(loopStartFrac.value * buf.length),
      Math.min(buf.length, Math.ceil(loopEndFrac.value * buf.length)),
    ]
  }

  function measurePeak(buffer: AudioBuffer): number {
    let peak = 0
    for (let ch = 0; ch < buffer.numberOfChannels; ch++) {
      const d = buffer.getChannelData(ch)
      for (let i = 0; i < d.length; i++) {
        const a = Math.abs(d[i]!)
        if (a > peak) peak = a
      }
    }
    return peak
  }

  function normalizeBuffer(buffer: AudioBuffer): void {
    const peak = measurePeak(buffer)
    if (peak < 0.001) return
    const g = 0.95 / peak
    for (let ch = 0; ch < buffer.numberOfChannels; ch++) {
      const d = buffer.getChannelData(ch)
      for (let i = 0; i < d.length; i++) d[i]! *= g
    }
  }

  async function decodeBase64Wav(base64: string): Promise<AudioBuffer> {
    const ac = ensureContext()
    const bin = atob(base64)
    const bytes = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
    return ac.decodeAudioData(bytes.buffer)
  }

  function createSource(ac: AudioContext, buffer: AudioBuffer): AudioBufferSourceNode {
    const src = ac.createBufferSource()
    src.buffer = buffer
    src.loop = isLooping.value
    src.playbackRate.value = rateForPlayback()
    src.loopStart = preparedLoopStartSec
    src.loopEnd = preparedLoopEndSec
    return src
  }

  function prepareBuffer(ac: AudioContext, source: AudioBuffer): AudioBuffer {
    const [ls, le] = loopBoundsSamples(source)
    const sr = source.sampleRate

    let processed: AudioBuffer

    if (loopPingPong.value) {
      // Ping-pong: palindrome handles transitions, no crossfade needed.
      // Optionally optimize loop end first.
      let actualEnd = le
      if (loopOptimize.value && source.numberOfChannels > 0) {
        actualEnd = optimizeLoopEndSample(source.getChannelData(0), ls, le)
      }
      const copy = ac.createBuffer(source.numberOfChannels, source.length, sr)
      for (let ch = 0; ch < source.numberOfChannels; ch++) {
        copy.getChannelData(ch).set(source.getChannelData(ch))
      }
      const { buffer: palindrome, palindromeEnd } =
        createPalindromeBuffer(ac, copy, ls, actualEnd)
      optimizedEndFrac.value = actualEnd / source.length // display: based on original
      preparedLoopStartSec = ls / sr
      preparedLoopEndSec = palindromeEnd / sr
      preparedColdStartSec = preparedLoopStartSec // no crossfade zone in palindrome
      processed = palindrome
    } else {
      // Normal forward loop: crossfade at boundary
      const { buffer: loopProcessed, optimizedEnd, fadeSamples } =
        applyLoopProcessing(ac, source, ls, le, loopOptimize.value, crossfadeMs.value)
      optimizedEndFrac.value = optimizedEnd / source.length
      preparedLoopStartSec = ls / sr
      preparedLoopEndSec = optimizedEnd / sr
      preparedColdStartSec = (ls + fadeSamples) / sr // past the crossfade zone
      processed = loopProcessed
    }

    // Normalize (if enabled)
    if (normalizeOn.value) normalizeBuffer(processed)

    return processed
  }

  function startSource(ac: AudioContext, playBuffer: AudioBuffer) {
    const newGain = ac.createGain()
    newGain.gain.value = 0 // silent until fade-in
    newGain.connect(destinationNode ?? ac.destination)
    const newSource = createSource(ac, playBuffer)
    newSource.connect(newGain)

    const now = ac.currentTime + SCHEDULE_AHEAD
    const fadeSec = crossfadeMs.value / 1000
    const oldSource = activeSource
    const oldGain = activeGain
    const isCrossfade = !!(oldSource && oldGain && isPlaying.value)

    if (isCrossfade && oldSource && oldGain) {
      if (fadeSec <= 0) {
        // Instant switch: stop old immediately, start new at full volume
        oldGain.gain.cancelScheduledValues(0)
        oldGain.gain.setValueAtTime(0, now)
        oldSource.stop(now + 0.01)
        newGain.gain.setValueAtTime(1, now)
      } else {
        // Fade out old source: cancel ALL prior events then linear ramp to 0.
        // Linear ramp (NOT setValueCurveAtTime) — curves take exclusive
        // ownership of the AudioParam and block concurrent events.
        const oldGainVal = oldGain.gain.value
        oldGain.gain.cancelScheduledValues(0)
        oldGain.gain.setValueAtTime(oldGainVal, now)
        oldGain.gain.linearRampToValueAtTime(0, now + fadeSec)
        oldSource.stop(now + fadeSec + 0.05)

        // Fade in new source: linear ramp from 0 to 1
        newGain.gain.setValueAtTime(0, now)
        newGain.gain.linearRampToValueAtTime(1, now + fadeSec)
      }
    } else {
      newGain.gain.setValueAtTime(1, now)
    }

    // Cold start: skip past crossfade zone (head samples are modified tail audio,
    // designed for seamless loop wrapping, not for entry from silence).
    // Crossfade: start at loopStart — the fade-in masks the modified head.
    const offset = isCrossfade ? preparedLoopStartSec : preparedColdStartSec
    newSource.start(now, offset)
    newSource.onended = () => {
      if (newSource === activeSource) {
        isPlaying.value = false
        activeSource = null
        activeGain = null
      }
    }

    activeSource = newSource
    activeGain = newGain
    isPlaying.value = true
  }

  async function play(base64Wav: string) {
    const ac = ensureContext()
    const decoded = await decodeBase64Wav(base64Wav)
    originalBuffer = decoded
    rawBase64 = base64Wav
    bufferDuration.value = decoded.duration
    hasAudio.value = true
    peakAmplitude.value = measurePeak(decoded)
    startSource(ac, prepareBuffer(ac, decoded))
  }

  function replay() {
    if (!originalBuffer) return
    const ac = ensureContext()
    startSource(ac, prepareBuffer(ac, originalBuffer))
  }

  function stop() {
    if (activeSource) { try { activeSource.stop() } catch { /* */ } activeSource = null }
    if (activeGain) { activeGain.disconnect(); activeGain = null }
    isPlaying.value = false
  }

  function setLoop(on: boolean) {
    isLooping.value = on
    if (activeSource) activeSource.loop = on
  }

  function setTranspose(semitones: number) {
    transposeSemitones.value = semitones
    if (activeSource) activeSource.playbackRate.value = rateForPlayback()
  }

  function glideToSemitones(semitones: number, timeMs: number) {
    transposeSemitones.value = semitones
    if (activeSource && ctx) {
      const now = ctx.currentTime
      const rate = Math.pow(2, semitones / 12)
      // Anchor current value before ramp (required by Web Audio spec)
      activeSource.playbackRate.setValueAtTime(activeSource.playbackRate.value, now)
      activeSource.playbackRate.linearRampToValueAtTime(rate, now + timeMs / 1000)
    }
  }

  function setLoopStart(frac: number) {
    loopStartFrac.value = Math.max(0, Math.min(frac, loopEndFrac.value - 0.01))
    if (activeSource && originalBuffer) {
      activeSource.loopStart = loopStartFrac.value * originalBuffer.duration
    }
  }

  function setLoopEnd(frac: number) {
    loopEndFrac.value = Math.max(loopStartFrac.value + 0.01, Math.min(frac, 1))
    optimizedEndFrac.value = loopEndFrac.value
    if (activeSource && originalBuffer) {
      activeSource.loopEnd = loopEndFrac.value * originalBuffer.duration
    }
  }

  let crossfadeDebounce: ReturnType<typeof setTimeout> | null = null

  function setCrossfade(ms: number) {
    crossfadeMs.value = Math.max(0, Math.min(ms, 500))
    if (crossfadeDebounce) clearTimeout(crossfadeDebounce)
    crossfadeDebounce = setTimeout(() => {
      if (originalBuffer && isPlaying.value) replay()
    }, 100)
  }

  let loopModeDebounce: ReturnType<typeof setTimeout> | null = null

  function setNormalize(on: boolean) {
    normalizeOn.value = on
    if (loopModeDebounce) clearTimeout(loopModeDebounce)
    loopModeDebounce = setTimeout(() => {
      if (originalBuffer && isPlaying.value) replay()
    }, 100)
  }

  function setLoopOptimize(on: boolean) {
    loopOptimize.value = on
    if (loopModeDebounce) clearTimeout(loopModeDebounce)
    loopModeDebounce = setTimeout(() => {
      if (originalBuffer && isPlaying.value) replay()
    }, 100)
  }

  function setLoopPingPong(on: boolean) {
    loopPingPong.value = on
    if (loopModeDebounce) clearTimeout(loopModeDebounce)
    loopModeDebounce = setTimeout(() => {
      if (originalBuffer && isPlaying.value) replay()
    }, 100)
  }

  function exportRaw(): Blob | null {
    if (!rawBase64) return null
    const bin = atob(rawBase64)
    const bytes = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
    return new Blob([bytes], { type: 'audio/wav' })
  }

  function exportLoop(): Blob | null {
    if (!originalBuffer) return null
    const [s, e] = loopBoundsSamples(originalBuffer)
    if (e <= s) return null
    return encodeWav(originalBuffer, s, e)
  }

  function setDestination(node: AudioNode | null) {
    destinationNode = node
  }

  function getContext(): AudioContext {
    return ensureContext()
  }

  /** Hard stop + restart from loop start (no crossfade). For non-legato MIDI retrigger. */
  function retrigger() {
    if (!originalBuffer) return
    stop()
    const ac = ensureContext()
    startSource(ac, prepareBuffer(ac, originalBuffer))
  }

  function getWaveformPeaks(numBins: number): Float32Array | null {
    if (!originalBuffer) return null
    const ch = originalBuffer.getChannelData(0)
    const peaks = new Float32Array(numBins)
    const binSize = ch.length / numBins
    for (let i = 0; i < numBins; i++) {
      const start = Math.floor(i * binSize)
      const end = Math.min(Math.floor((i + 1) * binSize), ch.length)
      let max = 0
      for (let j = start; j < end; j++) {
        const abs = Math.abs(ch[j]!)
        if (abs > max) max = abs
      }
      peaks[i] = max
    }
    return peaks
  }

  function dispose() {
    stop()
    originalBuffer = null; rawBase64 = null; hasAudio.value = false
    if (ctx && ctx.state !== 'closed') ctx.close()
    ctx = null
  }

  return {
    play, replay, stop, retrigger,
    setLoop, setTranspose, glideToSemitones, setDestination, getContext,
    setLoopStart, setLoopEnd, setLoopOptimize, setLoopPingPong,
    setCrossfade, setNormalize,
    exportRaw, exportLoop, getWaveformPeaks, dispose,
    getOriginalBuffer: () => originalBuffer,
    isPlaying: readonly(isPlaying),
    isLooping: readonly(isLooping),
    transposeSemitones: readonly(transposeSemitones),
    loopStartFrac: readonly(loopStartFrac),
    loopEndFrac: readonly(loopEndFrac),
    optimizedEndFrac: readonly(optimizedEndFrac),
    bufferDuration: readonly(bufferDuration),
    hasAudio: readonly(hasAudio),
    crossfadeMs: readonly(crossfadeMs),
    normalizeOn: readonly(normalizeOn),
    peakAmplitude: readonly(peakAmplitude),
    loopOptimize: readonly(loopOptimize),
    loopPingPong: readonly(loopPingPong),
  }
}
