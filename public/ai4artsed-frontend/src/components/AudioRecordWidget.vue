<!--
  AudioRecordWidget — the audio input, in the shape the image input has.

  MediaInputBox has held two kinds of material: a text field and, through
  ImageUploadWidget, a picture. Audio was the missing third, and every page that
  wanted it built its own row of controls instead. This is that third, written
  as ImageUploadWidget's sibling: the same box, the same empty prompt, the same
  filled preview, the trash in the MediaInputBox header.

  It owns the microphone: permission, the recorder, the clock, the ceiling, and
  the conversion to wav. What it hands over is a finished wav and its length —
  no page has to know that MediaRecorder produces webm/opus, or that a bare
  AudioContext resamples to whatever the audio interface happens to run at.
-->
<template>
  <div class="audio-record-widget">
    <div
      class="drop-zone"
      :class="{ recording, 'has-audio': !!src, disabled: disabled || handing }"
      @click="onZoneClick"
    >
      <div v-if="src" class="audio-preview">
        <audio
          :src="src"
          controls
          controlsList="nodownload noplaybackrate"
          @click.stop
          @contextmenu.prevent
        ></audio>
        <p class="audio-length">{{ clock }}</p>
      </div>

      <div v-else-if="handing" class="upload-prompt">
        <div class="upload-icon">
          <svg viewBox="0 -960 960 960" width="48" height="48" fill="currentColor" aria-hidden="true">
            <path d="M480-400q-50 0-85-35t-35-85v-240q0-50 35-85t85-35q50 0 85 35t35 85v240q0 50-35 85t-85 35Zm-40 280v-123q-104-14-172-93t-68-184h80q0 83 58.5 141.5T480-320q83 0 141.5-58.5T680-520h80q0 105-68 184t-172 93v123h-80Z" />
          </svg>
        </div>
        <p class="upload-text">{{ t('audioRecord.preparing') }}</p>
        <p class="upload-hint">{{ clock }}</p>
      </div>

      <div v-else class="upload-prompt">
        <div class="upload-icon">
          <svg v-if="recording" viewBox="0 -960 960 960" width="48" height="48" fill="currentColor" aria-hidden="true">
            <path d="M240-240v-480h480v480H240Z" />
          </svg>
          <svg v-else viewBox="0 -960 960 960" width="48" height="48" fill="currentColor" aria-hidden="true">
            <path d="M480-400q-50 0-85-35t-35-85v-240q0-50 35-85t85-35q50 0 85 35t35 85v240q0 50-35 85t-85 35Zm-40 280v-123q-104-14-172-93t-68-184h80q0 83 58.5 141.5T480-320q83 0 141.5-58.5T680-520h80q0 105-68 184t-172 93v123h-80Z" />
          </svg>
        </div>
        <p v-if="recording" class="upload-clock" :class="{ near: left <= 15 }">
          {{ clock }} / {{ maxClock }}
        </p>
        <p v-else class="upload-text">
          <strong>{{ t('audioRecord.clickHere') }}</strong> {{ t('audioRecord.toRecord') }}
        </p>
        <p class="upload-hint">
          {{ recording ? t('audioRecord.stop') : t('audioRecord.upTo', { max: maxClock }) }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    /** The take, once there is one. The page owns the URL and revokes it. */
    src?: string
    /** The ceiling, in seconds. */
    maxSeconds?: number
    disabled?: boolean
  }>(),
  { src: '', maxSeconds: 240, disabled: false }
)

const emit = defineEmits<{
  (e: 'audio-recorded', wav: Blob, seconds: number): void
  (e: 'mic-error'): void
}>()

const recording = ref(false)
/** Between the press and the microphone answering — the prompt can stand open. */
const arming = ref(false)
/**
 * Between the stop and the finished wav. Its own state, because `recording` is
 * already false there and `src` is not yet set, so without it the empty prompt
 * stands open over a take that is still being converted — and a second click
 * started a second recording on top of the first.
 */
const handing = ref(false)
const elapsed = ref(0)

let stream: MediaStream | null = null
let recorder: MediaRecorder | null = null
let chunks: Blob[] = []
let tick = 0
let startedAt = 0
let gone = false

const maxClock = computed(() => fmt(props.maxSeconds))
const clock = computed(() => fmt(elapsed.value))
const left = computed(() => props.maxSeconds - elapsed.value)

function fmt(s: number) {
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

function onZoneClick() {
  if (props.disabled || arming.value || handing.value) return
  // A take is playing material, not a button: the zone stops taking clicks once
  // there is one. Getting rid of it is the trash in the box header.
  if (props.src) return
  if (recording.value) stop()
  else void start()
}

async function start() {
  arming.value = true
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: true },
    })
  } catch {
    arming.value = false
    emit('mic-error')
    return
  }
  // The page can be gone by now: the permission prompt stands open for as long
  // as somebody looks at it, and the unmount that ran while it did had no
  // recorder and no stream to stop. Without this the microphone came up on a
  // dead component and stayed up until the four minutes were over.
  if (gone) {
    stream.getTracks().forEach(track => track.stop())
    stream = null
    arming.value = false
    return
  }
  chunks = []
  recorder = new MediaRecorder(stream)
  recorder.ondataavailable = e => {
    if (e.data.size) chunks.push(e.data)
  }
  recorder.onstop = () => {
    if (!gone) void handOver()
  }
  recorder.start()
  recording.value = true
  arming.value = false
  elapsed.value = 0

  // Read off a monotonic clock rather than counted: a hidden tab or a loaded
  // main thread suppresses interval callbacks, and a counted second that never
  // ran made the file longer than the number on screen.
  startedAt = performance.now()
  tick = window.setInterval(() => {
    elapsed.value = (performance.now() - startedAt) / 1000
    if (elapsed.value >= props.maxSeconds) stop()
  }, 250)
}

function stop() {
  window.clearInterval(tick)
  recording.value = false
  if (recorder && recorder.state !== 'inactive') {
    handing.value = true
    recorder.stop()
  }
  stream?.getTracks().forEach(track => track.stop())
  stream = null
}

async function handOver() {
  // Read off the clock BEFORE the await, not after: what is handed over has to
  // be the length of the file being handed over.
  const seconds = elapsed.value
  const raw = new Blob(chunks, { type: chunks[0]?.type || 'audio/webm' })
  chunks = []
  try {
    const wav = await toWav(raw)
    if (!gone) emit('audio-recorded', wav, seconds)
  } catch {
    if (!gone) emit('mic-error')
  } finally {
    handing.value = false
  }
}

async function toWav(blob: Blob): Promise<Blob> {
  // 48 kHz, not the device's rate. decodeAudioData resamples to the context's
  // rate, and a bare AudioContext takes whatever the audio interface runs at —
  // at 96 kHz a legal four-minute recording came to 46 MB, over the upload
  // guard, and was refused as "longer than four minutes", which it was not.
  let ctx: AudioContext
  try {
    ctx = new AudioContext({ sampleRate: 48000 })
  } catch {
    ctx = new AudioContext()
  }
  const decoded = await ctx.decodeAudioData(await blob.arrayBuffer())
  await ctx.close()

  // Downmix to mono: what reads audio on this platform wants one channel.
  const n = decoded.length
  const mono = new Float32Array(n)
  for (let c = 0; c < decoded.numberOfChannels; c++) {
    const data = decoded.getChannelData(c)
    for (let i = 0; i < n; i++) mono[i] = (mono[i] ?? 0) + (data[i] ?? 0) / decoded.numberOfChannels
  }

  const buffer = new ArrayBuffer(44 + n * 2)
  const view = new DataView(buffer)
  const ascii = (offset: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i))
  }
  ascii(0, 'RIFF'); view.setUint32(4, 36 + n * 2, true); ascii(8, 'WAVE')
  ascii(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true)
  view.setUint16(22, 1, true); view.setUint32(24, decoded.sampleRate, true)
  view.setUint32(28, decoded.sampleRate * 2, true); view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  ascii(36, 'data'); view.setUint32(40, n * 2, true)
  for (let i = 0; i < n; i++) {
    const s = Math.max(-1, Math.min(1, mono[i] ?? 0))
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

// The microphone may not outlive the widget. `gone` is set BEFORE the recorder
// is stopped, because onstop fires asynchronously after the unmount — without
// it, leaving mid-recording still handed a wav to a page that is no longer
// there, and on the cover band that meant a whole chain, GPU song included.
onBeforeUnmount(() => {
  gone = true
  stop()
})

defineExpose({ recording, handing, elapsed })
</script>

<style scoped>
.audio-record-widget { width: 100%; }

/* ImageUploadWidget's zone, at the height a player needs rather than a picture. */
.drop-zone {
  width: 100%;
  min-height: 120px;
  border: 2px dashed #4a8f4d;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background: rgb(var(--bg-base-rgb) / 0.3);
  position: relative;
}
.drop-zone:hover { border-color: #5fb563; background: rgba(74, 143, 77, 0.1); }
.drop-zone.recording { border-color: #a04040; border-style: solid; background: rgba(160, 64, 64, 0.12); }
.drop-zone.has-audio { cursor: default; border-color: #4a8f4d; }
.drop-zone.has-audio:hover { background: rgb(var(--bg-base-rgb) / 0.3); }
/* Only the EMPTY zone is dimmed while it refuses: a take that is playing is
   still playable, and half-transparent said the opposite. And a zone that
   refuses must not light up green under the pointer as if it did not. */
.drop-zone.disabled { cursor: default; }
.drop-zone.disabled:not(.has-audio) { opacity: 0.5; }
.drop-zone.disabled:hover { border-color: #4a8f4d; background: rgb(var(--bg-base-rgb) / 0.3); }

.upload-prompt { text-align: center; padding: 1.5rem; }
.upload-icon {
  margin-bottom: 0.75rem;
  opacity: 0.7;
  display: flex;
  align-items: center;
  justify-content: center;
}
.upload-icon svg { width: 48px; height: 48px; }
.upload-text { font-size: var(--flow-fs-body); color: #e0e0e0; margin-bottom: 0.5rem; }
.upload-text strong { color: #fff; }
/* The counting line is the feedback while recording. Large and tabular, so a
   change every second is visible from across a workshop table. */
.upload-clock { font-size: var(--flow-fs-display); color: #e8e8e8; font-variant-numeric: tabular-nums; margin-bottom: 0.5rem; }
.upload-clock.near { color: #c08a4a; }
.upload-hint { font-size: var(--flow-fs-hint); color: #999; font-variant-numeric: tabular-nums; }

.audio-preview {
  width: 100%;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}
.audio-preview audio { width: 100%; max-width: 34rem; display: block; }
.audio-length { font-size: var(--flow-fs-hint); color: #999; font-variant-numeric: tabular-nums; margin: 0; }
</style>
