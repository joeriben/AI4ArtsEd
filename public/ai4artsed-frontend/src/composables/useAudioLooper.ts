/**
 * Web Audio API looper composable for Crossmodal Lab Synth tab.
 *
 * - Linear crossfade (linearRampToValueAtTime — safe from AudioParam racing)
 * - Cross-correlation loop-point optimization for seamless oscillator-like loops
 * - WSOLA pitch shifting: transpose without tempo change
 * - Adjustable crossfade duration, loop interval, pitch transposition
 * - Peak normalization (playback only), raw/loop WAV export
 *
 * AudioContext is created lazily on first play() call (browser autoplay policy).
 *
 * Equal-power crossfade: Boris Smus, "Web Audio API" (O'Reilly, 2013), Ch. 3
 * https://webaudioapi.com/book/Web_Audio_API_Boris_Smus_html/ch03.html
 * License: CC-BY-NC-ND 3.0
 *
 * WSOLA pitch shifting: Waveform Similarity Overlap-Add for artifact-free pitch shift.
 * Cross-correlation grain alignment eliminates phase cancellation artifacts.
 * Lanczos sinc resampling eliminates aliasing from the time-stretch step.
 * Reference: Verhelst & Roelands, ICASSP 1993.
 */
import { ref, readonly } from 'vue'

// ═══════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════

const SCHEDULE_AHEAD = 0.005 // 5ms lookahead for scheduling safety
// WSOLA pitch shift
const GRAIN_SIZE = 2048      // ~46ms at 44.1kHz
const WSOLA_OVERLAP = 4      // 75% overlap → analysisHop = grain/4
const WSOLA_TOLERANCE = 512  // cross-correlation search window ±samples
const SINC_KERNEL_A = 6      // Lanczos kernel half-width
const CORR_SUBSAMPLE = 4     // subsample correlation for speed
// Loop optimization
const XCORR_WINDOW = 512    // comparison window (samples)
const XCORR_SEARCH = 2000   // search radius (samples)
// Pitch cache: pre-computed WSOLA buffers for instant MIDI response
const PITCH_CACHE_LO = -12  // C2 relative to C3
const PITCH_CACHE_HI = 12   // C4 relative to C3

// ═══════════════════════════════════════════════════════════════════
// DSP utilities (stateless, pure functions)
// ═══════════════════════════════════════════════════════════════════

// Pre-computed Hann window for WSOLA
const hannWindow = new Float32Array(GRAIN_SIZE)
for (let i = 0; i < GRAIN_SIZE; i++) {
  hannWindow[i] = 0.5 * (1 - Math.cos(2 * Math.PI * i / GRAIN_SIZE))
}


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

/**
 * Lanczos windowed sinc resampling with anti-aliasing.
 * Properly band-limits when downsampling (ratio > 1) to prevent aliasing.
 */
function sincResample(input: Float32Array, outputLen: number): Float32Array {
  const inputLen = input.length
  if (inputLen === outputLen) return new Float32Array(input)
  if (inputLen === 0 || outputLen === 0) return new Float32Array(outputLen)

  const output = new Float32Array(outputLen)
  const ratio = inputLen / outputLen
  // When downsampling, widen the kernel to act as anti-aliasing low-pass filter
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

/**
 * WSOLA (Waveform Similarity Overlap-Add) pitch shift.
 *
 * Phase 1: Time-stretch by rate via WSOLA — each grain's analysis position is
 * adjusted by cross-correlation search to find the best waveform continuity
 * with the previously written output. This eliminates the phase cancellation
 * artifacts of naive OLA.
 *
 * Phase 2: Lanczos sinc resample back to original length → pitch shift.
 *
 * Amplitude is normalized by accumulated window sum to prevent modulation
 * artifacts from non-constant overlap at arbitrary synthesis hops.
 */
function wsolaPitchShift(input: Float32Array, semitones: number): Float32Array {
  if (semitones === 0) return input
  const inputLen = input.length
  if (inputLen < GRAIN_SIZE) return input

  const rate = Math.pow(2, semitones / 12)
  const analysisHop = Math.floor(GRAIN_SIZE / WSOLA_OVERLAP)
  const synthesisHop = Math.max(1, Math.round(analysisHop * rate))
  const numGrains = Math.floor((inputLen - GRAIN_SIZE) / analysisHop) + 1
  if (numGrains < 1) return input

  const stretchedLen = (numGrains - 1) * synthesisHop + GRAIN_SIZE
  const stretched = new Float32Array(stretchedLen)
  const winSum = new Float32Array(stretchedLen)
  const overlapLen = GRAIN_SIZE - synthesisHop
  const minOverlap = 64 // skip WSOLA search if overlap too small (extreme shifts)

  let analysisOffset = 0 // cumulative offset from cross-correlation search

  for (let g = 0; g < numGrains; g++) {
    const nominalPos = g * analysisHop
    let bestPos = nominalPos + analysisOffset

    // WSOLA: find analysis position with best waveform continuity
    if (g > 0 && overlapLen >= minOverlap) {
      const synthStart = g * synthesisHop
      const searchLen = Math.min(overlapLen, GRAIN_SIZE)
      let bestCorr = -Infinity
      const lo = Math.max(0, bestPos - WSOLA_TOLERANCE)
      const hi = Math.min(inputLen - GRAIN_SIZE, bestPos + WSOLA_TOLERANCE)

      for (let cand = lo; cand <= hi; cand++) {
        let dot = 0, na = 0, nb = 0
        for (let i = 0; i < searchLen; i += CORR_SUBSAMPLE) {
          const outIdx = synthStart + i
          const a = outIdx < stretchedLen && winSum[outIdx]! > 0.01
            ? stretched[outIdx]! / winSum[outIdx]!
            : 0
          const b = input[cand + i]!
          dot += a * b
          na += a * a
          nb += b * b
        }
        const denom = Math.sqrt(na * nb)
        const corr = denom > 1e-10 ? dot / denom : 0
        if (corr > bestCorr) {
          bestCorr = corr
          bestPos = cand
        }
      }
      analysisOffset = bestPos - nominalPos
    }

    bestPos = Math.max(0, Math.min(inputLen - GRAIN_SIZE, bestPos))

    // Write windowed grain to output
    const synthPos = g * synthesisHop
    for (let i = 0; i < GRAIN_SIZE; i++) {
      const outIdx = synthPos + i
      if (outIdx < stretchedLen) {
        stretched[outIdx]! += input[bestPos + i]! * hannWindow[i]!
        winSum[outIdx]! += hannWindow[i]!
      }
    }
  }

  // Normalize by accumulated window sum
  for (let i = 0; i < stretchedLen; i++) {
    if (winSum[i]! > 0.001) {
      stretched[i]! /= winSum[i]!
    }
  }

  // Resample to original length via Lanczos sinc interpolation
  return sincResample(stretched, inputLen)
}

/**
 * Apply OLA pitch shift to an AudioBuffer (all channels).
 */
function pitchShiftBuffer(ac: AudioContext, source: AudioBuffer, semitones: number): AudioBuffer {
  if (semitones === 0) return source
  const result = ac.createBuffer(source.numberOfChannels, source.length, source.sampleRate)
  for (let ch = 0; ch < source.numberOfChannels; ch++) {
    const shifted = wsolaPitchShift(source.getChannelData(ch), semitones)
    result.getChannelData(ch).set(shifted)
  }
  return result
}

// ═══════════════════════════════════════════════════════════════════
// Composable
// ═══════════════════════════════════════════════════════════════════

export type TransposeMode = 'rate' | 'pitch'

export function useAudioLooper() {
  let ctx: AudioContext | null = null
  let activeSource: AudioBufferSourceNode | null = null
  let activeGain: GainNode | null = null
  let originalBuffer: AudioBuffer | null = null
  let rawBase64: string | null = null
  let destinationNode: AudioNode | null = null

  // ── Pitch cache (pre-computed OLA buffers per semitone) ──
  let pitchCache: Map<number, AudioBuffer> = new Map()
  let pitchCacheGeneration = 0

  const isPlaying = ref(false)
  const isLooping = ref(false)
  const transposeSemitones = ref(0)
  const transposeMode = ref<TransposeMode>('rate')
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
  const pitchCacheSize = ref(0)

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
    return transposeMode.value === 'rate'
      ? Math.pow(2, transposeSemitones.value / 12)
      : 1 // OLA mode: pitch baked into buffer, play at normal rate
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

  // ── Pitch cache management ──

  function invalidatePitchCache() {
    pitchCacheGeneration++
    pitchCache = new Map()
    pitchCacheSize.value = 0
  }

  /**
   * Asynchronously pre-compute OLA-shifted buffers for all semitones in range.
   * Iterates center-outward (0, ±1, ±2, ...) so common transpositions cache first.
   * Uses requestIdleCallback to yield to user input between computations.
   */
  function buildPitchCacheAsync(
    ac: AudioContext, loopProcessed: AudioBuffer, generation: number,
  ) {
    // Build ordering: 0, +1, -1, +2, -2, ...
    const semitones: number[] = [0]
    for (let i = 1; i <= Math.max(PITCH_CACHE_HI, -PITCH_CACHE_LO); i++) {
      if (i <= PITCH_CACHE_HI) semitones.push(i)
      if (-i >= PITCH_CACHE_LO) semitones.push(-i)
    }

    // Schedule with requestIdleCallback to avoid blocking input events.
    // Fallback to setTimeout(fn, 50) for browsers without rIC support.
    const schedule = typeof requestIdleCallback === 'function'
      ? (fn: () => void) => requestIdleCallback(fn, { timeout: 200 })
      : (fn: () => void) => setTimeout(fn, 50)

    let idx = 0
    function processNext() {
      if (pitchCacheGeneration !== generation) return
      if (idx >= semitones.length) return

      const st = semitones[idx++]!
      if (!pitchCache.has(st)) {
        let buf: AudioBuffer
        if (st === 0) {
          buf = ac.createBuffer(
            loopProcessed.numberOfChannels, loopProcessed.length, loopProcessed.sampleRate,
          )
          for (let ch = 0; ch < loopProcessed.numberOfChannels; ch++) {
            buf.getChannelData(ch).set(loopProcessed.getChannelData(ch))
          }
        } else {
          buf = pitchShiftBuffer(ac, loopProcessed, st)
        }
        if (normalizeOn.value) normalizeBuffer(buf)
        if (pitchCacheGeneration !== generation) return
        pitchCache.set(st, buf)
        pitchCacheSize.value = pitchCache.size
      }
      schedule(processNext)
    }
    schedule(processNext)
  }

  function rebuildPitchCache() {
    if (!originalBuffer || !ctx) return
    invalidatePitchCache()
    // Pitch cache is only needed for OLA transpose mode.
    // In 'rate' mode, pitch is handled by playbackRate — zero CPU cost.
    if (transposeMode.value !== 'pitch') return
    const ac = ensureContext()
    const [ls, le] = loopBoundsSamples(originalBuffer)

    let baseBuffer: AudioBuffer
    if (loopPingPong.value) {
      let actualEnd = le
      if (loopOptimize.value && originalBuffer.numberOfChannels > 0) {
        actualEnd = optimizeLoopEndSample(originalBuffer.getChannelData(0), ls, le)
      }
      const copy = ac.createBuffer(originalBuffer.numberOfChannels, originalBuffer.length, originalBuffer.sampleRate)
      for (let ch = 0; ch < originalBuffer.numberOfChannels; ch++) {
        copy.getChannelData(ch).set(originalBuffer.getChannelData(ch))
      }
      baseBuffer = createPalindromeBuffer(ac, copy, ls, actualEnd).buffer
    } else {
      const { buffer: loopProcessed, optimizedEnd } =
        applyLoopProcessing(ac, originalBuffer, ls, le, loopOptimize.value, crossfadeMs.value)
      optimizedEndFrac.value = optimizedEnd / originalBuffer.length
      baseBuffer = loopProcessed
    }
    buildPitchCacheAsync(ac, baseBuffer, pitchCacheGeneration)
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

    // OLA pitch shift (if in pitch mode)
    if (transposeMode.value === 'pitch') {
      const st = transposeSemitones.value
      const cached = pitchCache.get(st)
      if (cached) return cached // already OLA-shifted + normalized
      if (st !== 0) {
        processed = pitchShiftBuffer(ac, processed, st)
      }
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
    invalidatePitchCache()
    startSource(ac, prepareBuffer(ac, decoded))
    rebuildPitchCache()
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
    if (transposeMode.value === 'rate') {
      // Instant: just change playback rate
      if (activeSource) activeSource.playbackRate.value = rateForPlayback()
    } else {
      // OLA: use cached buffer for instant response, fall back to live OLA
      if (originalBuffer && isPlaying.value) {
        const cached = pitchCache.get(semitones)
        if (cached) {
          startSource(ensureContext(), cached)
        } else {
          replay()
        }
      }
    }
  }

  function setTransposeMode(mode: TransposeMode) {
    transposeMode.value = mode
    if (originalBuffer && isPlaying.value) replay()
    if (mode === 'pitch') rebuildPitchCache()
  }

  let loopBoundsDebounce: ReturnType<typeof setTimeout> | null = null

  function setLoopStart(frac: number) {
    loopStartFrac.value = Math.max(0, Math.min(frac, loopEndFrac.value - 0.01))
    // Instant audio update: approximate using original buffer duration
    if (activeSource && originalBuffer) {
      activeSource.loopStart = loopStartFrac.value * originalBuffer.duration
    }
    if (loopBoundsDebounce) clearTimeout(loopBoundsDebounce)
    loopBoundsDebounce = setTimeout(() => rebuildPitchCache(), 150)
  }

  function setLoopEnd(frac: number) {
    loopEndFrac.value = Math.max(loopStartFrac.value + 0.01, Math.min(frac, 1))
    optimizedEndFrac.value = loopEndFrac.value
    if (activeSource && originalBuffer) {
      activeSource.loopEnd = loopEndFrac.value * originalBuffer.duration
    }
    if (loopBoundsDebounce) clearTimeout(loopBoundsDebounce)
    loopBoundsDebounce = setTimeout(() => rebuildPitchCache(), 150)
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
      rebuildPitchCache()
    }, 100)
  }

  function setLoopOptimize(on: boolean) {
    loopOptimize.value = on
    if (loopModeDebounce) clearTimeout(loopModeDebounce)
    loopModeDebounce = setTimeout(() => {
      if (originalBuffer && isPlaying.value) replay()
      rebuildPitchCache()
    }, 100)
  }

  function setLoopPingPong(on: boolean) {
    loopPingPong.value = on
    if (loopModeDebounce) clearTimeout(loopModeDebounce)
    loopModeDebounce = setTimeout(() => {
      if (originalBuffer && isPlaying.value) replay()
      rebuildPitchCache()
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
    invalidatePitchCache()
    originalBuffer = null; rawBase64 = null; hasAudio.value = false
    if (ctx && ctx.state !== 'closed') ctx.close()
    ctx = null
  }

  return {
    play, replay, stop, retrigger,
    setLoop, setTranspose, setTransposeMode, setDestination, getContext,
    setLoopStart, setLoopEnd, setLoopOptimize, setLoopPingPong,
    setCrossfade, setNormalize,
    exportRaw, exportLoop, getWaveformPeaks, dispose,
    getOriginalBuffer: () => originalBuffer,
    isPlaying: readonly(isPlaying),
    isLooping: readonly(isLooping),
    transposeSemitones: readonly(transposeSemitones),
    transposeMode: readonly(transposeMode),
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
    pitchCacheSize: readonly(pitchCacheSize),
  }
}
