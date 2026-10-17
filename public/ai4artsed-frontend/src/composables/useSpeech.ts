/**
 * Speaking — shared by Persona and Resona.
 *
 * The backend speaks a text verbatim through Supertonic 3 (POST /api/speech).
 * This is deliberately not the Web Speech API: that voice belongs to the
 * operating system, differs on every machine, and on most of them does not
 * exist at all for the languages this platform is used in.
 *
 * One page, one voice. The audio element is module-scoped, so starting an
 * utterance ends the one before it — two voices at once was never meant.
 *
 * One element, and nothing but the feed — `feed()`, of which `speak()` is
 * the whole-text case — may ever touch its src. Measured in
 * Safari on 2026-08-07 via /api/speech/diagnose: playback from a blob URL, from
 * a data URL, and a second playback on the same element all sound. Safari needs
 * no unlocking trick here — the earlier one (playing a zero-sample silence on
 * the first gesture) is what broke it: Safari aborts that play with
 * AbortError, so the unlock never counted as done, its listeners stayed on, and
 * every further click overwrote the src of the element that was speaking.
 *
 * One of the ten platform languages has no voice in the model: Hebrew. The
 * server speaks it in English; the caller can see it coming via
 * `speaksInFallback()` and say so, rather than being surprised by it. Which
 * languages those are is never hardcoded here — it comes from
 * /api/speech/status, so swapping the model does not strand this file.
 *
 * No voice is sent with the request, and that is what makes the voice move:
 * asked for none, the server draws one of its five mixtures per sentence, and
 * never the one the sentence before used. The mixtures are named in
 * config.SUPERTONIC_VOICES and the endpoint takes a `voice`; nothing in the UI
 * offers that choice — the voice is mixed here, not picked.
 */
import { computed, ref, type Ref } from 'vue'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { apiBase } from '@/services/labApi'

/** Whatever the caller uses to identify one utterance among its own. */
export type SpeechKey = string | number

/** Which piece of which utterance is sounding. See `soundingPiece`. */
export interface SoundingPiece {
  key: SpeechKey
  /** 0-based, over the same pieces `splitForSpeech` returns. */
  index: number
  text: string
  /**
   * How many pieces the utterance has. Null while it is still being handed
   * over piece by piece (a reply that is being written): the count is not
   * known until the writing is over, and a surface that compares it with its
   * own cut must not read "unknown" as "different".
   */
  total: number | null
  /**
   * How long this piece sounds, in milliseconds — measured on the clip, not
   * estimated.
   *
   * The model gives no word-level timing: its duration predictor returns ONE
   * number for the whole sentence (checked against the package, `dur` comes
   * back with shape (1,)), and the flow-matching decoder makes the latent in
   * one piece, so there is no alignment to read off. What there IS, exactly,
   * is how long the sentence takes to say.
   *
   * That is enough for reading and hearing to stay together: a surface can
   * spread the entrance of the words across exactly this span instead of a
   * fixed one, and then the sentence is finished being read at the moment it
   * is finished being spoken. Inside the sentence the placement of a single
   * word is proportional, not aligned — but the error never accumulates,
   * because every sentence starts from a measured span again.
   *
   * Null when the element would not say, which is a reason to keep whatever
   * pacing the surface uses by default.
   */
  durationMs: number | null
}

/**
 * An utterance handed over piece by piece — the way a reply arrives while it
 * is being written. See `useSpeech().feed`.
 */
export interface SpeechFeed {
  /** The next piece, in order. Ignored once the feed is closed or cancelled. */
  push(piece: string): void
  /**
   * No more pieces will come. What has been handed over sounds in turn,
   * unless the utterance ends first: a clip that could not be had, the
   * switch turned off, stop(), or the next utterance taking the line.
   */
  close(): void
  /** Over now: what has not sounded yet is dropped. */
  cancel(): void
  /** Settles when the utterance is over, however it ended. Never rejects. */
  done: Promise<void>
}

/** A turn spoken while it is being written. See `useSpeech().follow`. */
export interface SpeechFollower {
  /**
   * The text as it stands now — the SAME text the surface stands up, so that
   * the cut is the same. `whole` once the writing is over: then the last piece
   * is handed over too and the utterance is closed.
   */
  update(text: string, whole: boolean): void
  /** Not spoken after all: what has not sounded is dropped, without a word. */
  drop(): void
}

export interface SpeechStatus {
  available: boolean
  /** null when available; otherwise 'disabled' | 'safety_level' | 'not_installed' */
  reason: string | null
  /** Spoken in their own language. */
  voiced_languages: string[]
  /** Spoken in English instead. */
  unvoiced_languages: string[]
  fallback_language: string
  voices: string[]
  default_voice: string
  max_chars: number
}

// ---------------------------------------------------------------------------
// Visible trace, switched on with ?speech=debug
//
// Safari has no console the user can reach, and every failure in this file is
// silent by design — a guard that returns, a refused playback. Without this,
// "nothing happens" is indistinguishable from "the click never arrived", and
// the only way to tell them apart was to guess. Written imperatively so it
// needs no component and disappears with the flag.
// ---------------------------------------------------------------------------
function debugWanted(): boolean {
  if (typeof window === 'undefined') return false
  // The consent gate redirects through ?redirect=/together?speech=debug, which
  // swallows the flag. Once seen, it holds for the tab.
  if (new URLSearchParams(window.location.search).get('speech') === 'debug') {
    try { sessionStorage.setItem('speech_debug', '1') } catch { /* private mode */ }
    return true
  }
  try { return sessionStorage.getItem('speech_debug') === '1' } catch { return false }
}
const DEBUG = debugWanted()
let debugBox: HTMLElement | null = null

export function speechTrace(line: string) { trace(line) }

function trace(line: string) {
  if (!DEBUG || typeof document === 'undefined') return
  if (!debugBox) {
    debugBox = document.createElement('div')
    debugBox.setAttribute('style', [
      'position:fixed', 'left:8px', 'bottom:8px', 'z-index:99999',
      'max-width:min(560px,92vw)', 'max-height:42vh', 'overflow:auto',
      'background:rgba(0,0,0,.92)', 'color:#ece3d2', 'border:1px solid #ffb300',
      'border-radius:8px', 'padding:.6rem .8rem', 'font:12px/1.5 ui-monospace,monospace',
      'white-space:pre-wrap', 'pointer-events:none',
    ].join(';'))
    document.body.appendChild(debugBox)
  }
  const at = new Date().toISOString().slice(11, 19)
  debugBox.textContent = `${at}  ${line}\n` + (debugBox.textContent || '')
}

const status = ref<SpeechStatus | null>(null)
let statusRequest: Promise<void> | null = null

/** Key of the utterance currently sounding, so a caller can mark its own. */
const speakingKey = ref<SpeechKey | null>(null)
/** Key of the utterance being synthesized — the wait before the sound. */
const pendingKey = ref<SpeechKey | null>(null)
/**
 * Key of an utterance the browser refused to sound.
 *
 * Browsers only let audio play if a human asked for it with a gesture. Persona
 * speaks from a click and is always allowed; Resona answers by herself, so her
 * voice arrives seconds after the click that caused it and is refused — in
 * silence, which is indistinguishable from a broken voice. The sound is already
 * synthesized and stays loaded: one tap is the gesture, and it plays.
 */
const blockedKey = ref<SpeechKey | null>(null)

/**
 * The piece that is sounding right now — which utterance, which piece of it,
 * and what it says.
 *
 * The pieces were always there in the run (splitForSpeech, then one clip per
 * piece), but only the utterance was visible from outside. A surface that
 * wants a sentence to APPEAR at the moment it starts being spoken needs the
 * piece, and it needs the same pieces: render `splitForSpeech(text)` and
 * reveal piece i once `index >= i`.
 *
 * Set at the first `play()` of a piece that actually succeeds — so on the
 * blocked path, not before the gesture is made good. Null between utterances,
 * so nobody reads a stale piece as the current one.
 *
 * Written by this module only.
 */
const soundingPiece = ref<SoundingPiece | null>(null)

let audio: HTMLAudioElement | null = null
let objectUrl: string | null = null
/** Only the newest request may reach the speakers. */
let generation = 0
/**
 * Settles the `done` of the utterance that holds the line. Losing the line —
 * to the next utterance, or to stop() — is an ending, and the utterance has
 * to be able to report it: stopping takes the handlers off the element, so
 * the promise waiting for the piece's `ended` event would otherwise wait for
 * good, and a turn spoken while it is written would never learn that its
 * voice was taken away (found 2026-09-18, first refutation of `follow`).
 */
let holder: (() => void) | null = null

/** The one element every utterance goes through. */
function getAudio(): HTMLAudioElement {
  if (!audio) audio = new Audio()
  return audio
}

/** 50 ms of real silence — a valid clip, so play() actually resolves. */
let primingPromise: Promise<void> | null = null
const SILENCE_50MS = 'data:audio/wav;base64,UklGRrQBAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YZABAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA'
let primed = false

/**
 * Open the ear inside a human gesture — the same move a browser game makes on
 * its first click.
 *
 * Browsers only sound audio a human asked for. Persona is clicked and is
 * allowed; Resona answers by herself, so her voice arrives long after the
 * click that caused it and is refused. Playing a real, valid silence on the
 * shared element during a genuine click marks that element as the human's, and
 * everything spoken afterwards sounds.
 *
 * Call ONLY straight from a click or tap. Idempotent, and it steps aside
 * whenever the element is carrying an utterance, so it can never take the
 * voice away from itself.
 */
export function primeSpeech(): void {
  if (primed || typeof window === 'undefined') return
  if (speakingKey.value !== null || pendingKey.value !== null || blockedKey.value !== null) return
  const el = getAudio()
  if (el.src) { primed = true; return }
  el.src = SILENCE_50MS
  const started = el.play()
  if (!started || typeof started.then !== 'function') { primed = true; return }
  // Held so that speak() waits for it. Without that, a click that opens the ear
  // AND asks for an utterance in one move (Persona's voice) has the utterance
  // tear down its own opening: pause() on an element with a play() in flight
  // aborts it, the element never counts as the human's, and the very gesture
  // that was supposed to help destroys itself. That was AbortError.
  primingPromise = started.then(
    () => {
      el.pause()
      el.currentTime = 0
      primed = true
      trace('Ohr in der Geste geoeffnet')
    },
    err => { trace(`Oeffnen abgelehnt: ${err?.name ?? err}`) },
  ).finally(() => { primingPromise = null })
}

function releaseAudio() {
  if (audio) {
    // Drop the handlers BEFORE touching the element, and do not clear its src.
    // Removing the source and calling load() makes the element fire an error
    // event one turn later — which arrived after the next utterance had already
    // set its own handlers, and killed it before it made a sound. That was the
    // "one answer, then silence". The src is simply overwritten next time.
    audio.onended = null
    audio.onerror = null
    audio.pause()
  }
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl)
    objectUrl = null
  }
}

/**
 * Cut an utterance into pieces that can be synthesized and heard one after
 * the other, so the first words arrive in seconds instead of a minute.
 *
 * The cut is at SENTENCE ENDS AND NOWHERE ELSE, and that is the whole finding
 * of this file. Handed a fragment, the model does not speak the fragment — it
 * invents a continuation. Measured on this machine:
 *
 *   "Hallo. Ich bin Persona, eine Maschine, die Bilder, Klang,"
 *      57 characters -> 16.3 s of synthesis, 15.0 s of audio
 *   "Ich bin Persona, eine Maschine, die Bilder, Klang, Video und Objekte
 *    erzeugen kann."
 *      83 characters ->  4.7 s of synthesis,  5.7 s of audio
 *
 * A fragment of two thirds the length cost three times as much and came back
 * as something nobody asked for. So no clause splitting, no cutting a long
 * sentence to get the first word out sooner: a long first sentence is a long
 * wait, and that is the model's floor, not something to engineer around.
 *
 * Short sentences are kept as they are rather than merged into the next. They
 * are the best opening there is — "Hallo." is one second of audio after 2.8 of
 * synthesis, and the answer has begun.
 *
 * A full stop after a one- or two-letter token is an abbreviation and not a
 * sentence end — "z. B.", "u. a.", "Dr. Meier", "3. Januar". That rule needs
 * no list of abbreviations and holds in any language written with these marks.
 * Scripts without them come back whole, which is correct: never a wrong cut.
 */
function sentences(paragraph: string): string[] {
  const out: string[] = []
  const stops = /[.!?…。！？]+[)"»'”»]?(?=\s)/g
  let start = 0
  let m: RegExpExecArray | null
  while ((m = stops.exec(paragraph)) !== null) {
    const end = m.index + m[0].length
    // Only a full stop can be an abbreviation. Nobody shortens a word with a
    // question mark, and "Was siehst du?" was being swallowed because "du" is
    // two letters long.
    if (m[0].startsWith('.')) {
      const token = paragraph.slice(start, m.index).trimEnd().split(/\s+/).pop() ?? ''
      if (token.replace(/[^\p{L}\p{N}]/gu, '').length <= 2) continue
    }
    const piece = paragraph.slice(start, end).trim()
    if (piece) out.push(piece)
    start = end
  }
  const tail = paragraph.slice(start).trim()
  if (tail) out.push(tail)
  return out.length ? out : [paragraph]
}

export function splitForSpeech(text: string): string[] {
  // A blank line is a break the writer put there; it is a piece boundary too.
  const pieces = text
    .split(/\n\s*\n+/)
    .map(p => p.trim())
    .filter(Boolean)
    .flatMap(sentences)

  return pieces.length ? pieces : [text]
}

/** Resolved by resume(); a refused piece waits here for its tap. */
let unblock: (() => void) | null = null

export function useSpeech() {
  /** Ask the server what it can speak. Cached — one request per page load. */
  function loadStatus(): Promise<void> {
    if (statusRequest) return statusRequest
    statusRequest = fetch(`${apiBase()}/api/speech/status`)
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        status.value = data
        trace(`Status: available=${data?.available}, reason=${data?.reason}`)
      })
      .catch(() => {
        // No status means no voice. Silence is the correct fallback for a
        // feature that is meant to be absent when it is not there.
        status.value = null
      })
    return statusRequest
  }

  const prefs = useUserPreferencesStore()

  /**
   * True when a voice may be offered at all.
   *
   * Two things have to hold, and the switch is the second: the installation
   * must be able to speak, and the listener must not have turned the voice
   * off. This is the ONE place the switch is read: `speak()` asks it before
   * an utterance, the feed asks it before every piece, and everything that
   * offers to speak asks it, so a surface cannot keep a voice the listener
   * has silenced.
   */
  const isAvailable = computed(() =>
    status.value?.available === true && prefs.voiceChat)

  const maxChars = computed(() => status.value?.max_chars ?? 0)

  /** True when this language is spoken in English rather than its own. */
  function speaksInFallback(language: string): boolean {
    const voiced = status.value?.voiced_languages
    if (!voiced) return false
    return !voiced.includes(language)
  }

  /** True when the text is short enough to be spoken at all. */
  function isSpeakable(text: string): boolean {
    const t = (text || '').trim()
    return t.length > 0 && (!maxChars.value || t.length <= maxChars.value)
  }

  function stop() {
    generation += 1
    const lost = holder
    holder = null
    releaseAudio()
    speakingKey.value = null
    pendingKey.value = null
    blockedKey.value = null
    soundingPiece.value = null
    // A piece held back for the gesture is let go of too: the call waiting
    // for the tap returns, sees a newer generation, and is over.
    const waiting = unblock
    unblock = null
    if (waiting) waiting()
    if (lost) lost()
  }

  /**
   * Let the held-back piece sound. MUST be called straight from a click or
   * tap — that gesture is the whole point, and it also opens the ear for
   * everything that follows in this utterance.
   */
  function resume(): void {
    if (blockedKey.value === null) return
    blockedKey.value = null
    primed = true
    const waiting = unblock
    unblock = null
    if (waiting) waiting()
  }

  /** One piece of an utterance, as wav. Null when it could not be had. */
  async function fetchClip(piece: string, language: string): Promise<Blob | null> {
    try {
      const response = await fetch(`${apiBase()}/api/speech`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: piece, language }),
      })
      if (!response.ok) {
        // A voice that fails must not fail invisibly: "nothing to hear" is
        // indistinguishable from "nothing was said" unless it is written down.
        console.warn(`[SPEECH] /api/speech returned ${response.status}`)
        trace(`  Server antwortet ${response.status}`)
        return null
      }
      return await response.blob()
    } catch (e) {
      console.warn('[SPEECH] /api/speech unreachable:', e)
      trace(`  Server nicht erreichbar: ${e}`)
      return null
    }
  }

  /**
   * Sound one piece. Resolves when it has finished, or when it was superseded.
   *
   * A refusal is not the end of it: the piece is already synthesized and stays
   * loaded while the surface offers the tap, and the tap resumes here rather
   * than starting the utterance over.
   */
  async function playClip(
    blob: Blob,
    key: SpeechKey,
    mine: number,
    index: number,
    text: string,
    /**
     * How many pieces the utterance has, read at the moment the piece becomes
     * audible: a piece refused by the browser sounds only after the tap, and
     * by then the utterance may have been closed and the count be known.
     */
    count: () => number | null,
  ): Promise<boolean> {
    if (objectUrl) URL.revokeObjectURL(objectUrl)
    objectUrl = URL.createObjectURL(blob)
    const el = getAudio()
    el.onended = null
    el.onerror = null
    el.src = objectUrl

    for (;;) {
      pendingKey.value = null
      speakingKey.value = key
      try {
        await el.play()
        trace('  spielt')
        // Here, and nowhere earlier: this is the instant the piece becomes
        // audible. The generation check keeps a superseded call from claiming
        // the line — its play() can still resolve after a newer utterance
        // took over.
        if (mine === generation) {
          const seconds = el.duration
          const durationMs = Number.isFinite(seconds) && seconds > 0
            ? Math.round(seconds * 1000)
            : null
          soundingPiece.value = { key, index, text, total: count(), durationMs }
        }
        break
      } catch (err) {
        const e = err as { name?: string }
        console.warn('[SPEECH] playback refused by the browser:', e?.name ?? err)
        trace(`  Wiedergabe abgelehnt: ${e?.name ?? err} — Ton bleibt bereit`)
        if (mine !== generation) return false
        speakingKey.value = null
        blockedKey.value = key
        await new Promise<void>(res => { unblock = res })
        if (mine !== generation) return false
      }
    }

    await new Promise<void>(resolve => {
      let settled = false
      const done = () => { if (!settled) { settled = true; resolve() } }
      el.onended = done
      el.onerror = () => { console.warn('[SPEECH] audio element failed'); done() }
    })
    return mine === generation
  }

  /**
   * Speak `text`. Resolves when the utterance has finished sounding, or
   * immediately if it was superseded. Never throws: a voice that fails is a
   * silence, not an error dialogue in the middle of a workshop.
   *
   * Sentence by sentence, with the next one being synthesized while the
   * current one plays. Synthesis runs at about the speed of speech, so the
   * pieces after the first are usually ready before they are needed, and the
   * first one arrives in about two seconds instead of up to sixty.
   *
   * @param key  identifies the utterance, so a caller can highlight its own
   */
  async function speak(text: string, language: string, key: SpeechKey = 'default'): Promise<void> {
    const t = (text || '').trim()
    trace(`speak(key=${key}, lang=${language}, ${t.length} chars)`)
    if (!t) { trace('  abgebrochen: kein Text'); return }
    if (!isAvailable.value) { trace(`  abgebrochen: nicht verfuegbar (${status.value?.reason ?? 'kein Status'})`); return }
    if (!isSpeakable(t)) { trace(`  abgebrochen: zu lang (${t.length} > ${maxChars.value})`); return }

    const pieces = splitForSpeech(t)
    trace(`  ${pieces.length} Stueck(e)`)
    const utterance = feed(language, key)
    for (const piece of pieces) utterance.push(piece)
    utterance.close()
    return utterance.done
  }

  /**
   * An utterance whose pieces are handed over one at a time — the way a reply
   * arrives while it is being written. Until 2026-09-18 the voice began after
   * the LAST byte of the reply; with the first sentence standing after two or
   * three seconds and the rest taking ten or twenty more, that was ten or
   * twenty seconds in which the first sentence stood, unspoken.
   *
   * `push()` hands over the next CLOSED sentence, in order; `close()` says no
   * more will come; `cancel()` drops what has not sounded. `done` settles
   * when the utterance is over, however it ended: sounded to the end, a clip
   * that could not be had, cancelled, or the line taken by the next utterance
   * or by stop(). The pieces must be
   * the ones `splitForSpeech` returns for the text the surface stands up, in
   * that order: piece i and sentence i have to be the same thing, or the words
   * follow the wrong clip (the regression of 2026-09-06). Until `close()`, the
   * sounding piece carries `total: null`, because the count is not known while
   * the writing is still coming.
   *
   * Opening a feed takes the line, as speak() does: whatever was sounding
   * stops. speak() is this with every piece pushed at once.
   */
  function feed(language: string, key: SpeechKey): SpeechFeed {
    const pieces: string[] = []
    const clips: Array<Promise<Blob | null>> = []
    let closed = false
    let cancelled = false
    let issued = 0
    /** Index of the last piece whose clip has arrived; -1 before the first. */
    let head = -1
    /** This utterance's generation once it holds the line; -1 before. */
    let mine = -1
    let wake: (() => void) | null = null
    const notify = () => { const w = wake; wake = null; if (w) w() }
    let settle: () => void = () => {}
    const ended = new Promise<void>(resolve => { settle = resolve })

    // The opening sentence is asked for ALONE. Synthesis runs on the CPU
    // (onnxruntime here has no CUDA provider) and is serialized behind one
    // lock — _synth_lock in supertonic_backend.py — so asking for several at
    // once puts the first word in a queue behind sentences nobody is waiting
    // for yet. Measured, that made the first word take fifteen seconds
    // instead of four. It never queues behind image generation: that is a
    // different process on the GPU, and this one is not on the GPU at all.
    //
    // Once it is here, the rest are kept in flight a few at a time, LOOKAHEAD
    // beyond the last clip that arrived: the ones already handed over, and
    // each later one the moment it is pushed, as far as that width goes. The
    // model takes about a tenth of the length of what it speaks (2026-09-18,
    // four flow steps), so the later sentences are ready before they are
    // needed. The "slow pass" seen in August (the same text, byte-identical
    // output, 2.2 s and then 6.0 s) was never the model: thermald clamped the
    // CPU of the development machine to 400 MHz for four seconds at a time —
    // see docs/installation/INSTALLATION.md, Fedora. Asking early still costs
    // nothing and covers a machine where that has not been done.
    const LOOKAHEAD = 3
    const topUp = (from: number) => {
      while (issued < pieces.length && issued < from + LOOKAHEAD) {
        clips[issued] = fetchClip(pieces[issued]!, language)
        issued++
      }
    }
    const quiet = () => {
      pendingKey.value = null
      speakingKey.value = null
      soundingPiece.value = null
    }

    const run = async () => {
      // Let the ear finish opening before taking the element. 50 ms, once.
      if (primingPromise) await primingPromise
      if (cancelled) return
      stop()
      mine = generation
      holder = settle
      pendingKey.value = key

      for (let i = 0; ; i++) {
        // Nothing to sound yet and the writing is not over: wait for a push.
        while (i >= pieces.length && !closed) {
          await new Promise<void>(resolve => { wake = resolve })
          if (mine !== generation) { trace('  verworfen: inzwischen ueberholt'); return }
        }
        if (i >= pieces.length) break
        // The switch in the main menu is read before every piece, as speak()
        // reads it before an utterance: a listener who turns the voice off
        // mid-reply hears the piece that is sounding to its end, and nothing
        // after it.
        if (!isAvailable.value) { trace('  still: die Stimme ist ausgeschaltet'); releaseAudio(); quiet(); return }
        if (i === 0) {
          if (issued === 0) { clips[0] = fetchClip(pieces[0]!, language); issued = 1 }
        } else {
          topUp(i)
        }
        const blob = await clips[i]!
        if (mine !== generation) { trace('  verworfen: inzwischen ueberholt'); return }
        head = i
        topUp(i + 1)
        if (!blob) { quiet(); return }
        trace(`  Stueck ${i + 1}/${closed ? pieces.length : '…'}: ${blob.size} B`)
        const carryOn = await playClip(blob, key, mine, i, pieces[i]!, () => (closed ? pieces.length : null))
        if (!carryOn) return
      }

      releaseAudio()
      quiet()
    }

    return {
      push(piece) {
        if (closed || cancelled) return
        pieces.push(piece)
        // The line is held and the opening clip is in: this one goes into
        // flight now, as far as the width allows, instead of waiting for the
        // next turn of the loop.
        if (head >= 0 && mine === generation) topUp(head + 1)
        notify()
      },
      close() {
        if (closed) return
        closed = true
        // The count is known now; the piece that is sounding learns it too.
        const sounding = soundingPiece.value
        if (sounding && sounding.key === key && mine === generation) {
          soundingPiece.value = { ...sounding, total: pieces.length }
        }
        notify()
      },
      cancel() {
        if (cancelled) return
        cancelled = true
        if (mine >= 0 && mine === generation) stop()
        notify()
        settle()
      },
      // Over when the run is over, when the line was taken away (stop()
      // settles the holder), or when cancelled. The line is given back at the
      // run's own end, so that a later stop() does not settle a stranger. A
      // throw out of the run — none is known; fetchClip and play() catch their
      // own — ends the utterance the way a failed clip does, so `done` keeps
      // its word and never rejects.
      done: Promise.race([
        run()
          .catch(err => {
            console.warn('[SPEECH] utterance failed:', err)
            if (mine === generation) { releaseAudio(); quiet() }
          })
          .finally(() => { if (holder === settle) holder = null }),
        ended,
      ]),
    }
  }

  /**
   * Speak a turn while it is being written. Each `update()` hands over every
   * piece of the text that stands before its last one: a piece goes to the
   * voice once the stream has begun the piece after it. The last piece of a
   * text still arriving waits, because it may still grow, and goes with the
   * closing text.
   *
   * What the surface takes back, the voice drops with it. A tool round's
   * preamble (`discard`) and a draft that failed its evidence duty
   * (`withdraw`) both reset the standing text, so the pieces handed over no
   * longer open it; the utterance is cancelled unspoken and the corrected
   * text starts a new one from its first sentence.
   *
   * The closing text may differ from the stream: the delivery filter takes
   * offered-choice sentences out of it (filter_reply in chat_routes), and a
   * sentence it takes out may already have been handed over. What was handed
   * over stays said; what the closing text has beyond it is handed over after
   * it, and the turn goes on from where it is. The words then see a count
   * that differs from their own cut and read at reading pace (ResonaVoice).
   *
   * A turn whose voice is over is over for good: sounded to the end, the
   * switch turned off, the line taken by another utterance or by stop(), or a
   * clip that could not be had. What arrives for it after that stays
   * unspoken. A listener who stopped it, or Help speaking over it, would
   * otherwise hear the turn start again from the top when its closing text
   * lands. A closing text that arrives whole, with nothing handed over before
   * it, is spoken only if it is short enough to be spoken at all, the rule
   * speak() applies to every text.
   *
   * `over` is called when the turn's voice is over, however it ended, when a
   * closing text turns out to have nothing to say, and again for every update
   * that arrives after the ending — the caller marks the turn as asked before
   * each update and needs that unsaid on the same pass. It is not called
   * after `drop()`: the caller dropped it and knows.
   */
  function follow(language: string, key: SpeechKey, over: () => void): SpeechFollower {
    let current: SpeechFeed | null = null
    let sent: string[] = []
    let gone = false
    const drop = () => {
      if (!current) return
      current.cancel()
      current = null
      sent = []
    }
    return {
      update(text, whole) {
        if (gone) { over(); return }
        const pieces = text ? splitForSpeech(text) : []
        const ready = whole ? pieces.length : pieces.length - 1
        const same = sent.every((p, i) => pieces[i] === p)
        if (current && !same && !whole) {
          trace(`follow(key=${key}): der Text ist zurueckgenommen, neu von vorn`)
          drop()
        }
        if (!current) {
          if (ready <= 0) { if (whole) over(); return }
          if (whole && !isSpeakable(text)) {
            trace(`follow(key=${key}): zu lang (${text.trim().length} > ${maxChars.value})`)
            over()
            return
          }
          const mine = feed(language, key)
          current = mine
          void mine.done.finally(() => {
            if (current !== mine) return
            trace(`follow(key=${key}): die Stimme ist zu Ende`)
            current = null
            sent = []
            gone = true
            over()
          })
        }
        let next: string[]
        if (same) {
          next = pieces.slice(sent.length, ready)
        } else {
          // The closing text lost sentences to the delivery filter. Each of
          // its pieces is looked for among those handed over; what is found
          // stays where it was, what is new goes after.
          next = []
          let j = 0
          for (const p of pieces) {
            const k = sent.indexOf(p, j)
            if (k >= 0) j = k + 1
            else next.push(p)
          }
          trace(`follow(key=${key}): der Schluss-Text weicht vom Strom ab, ${next.length} Stueck(e) kommen nach`)
        }
        for (const p of next) {
          current.push(p)
          sent.push(p)
          trace(`follow(key=${key}): Stueck ${sent.length} an die Stimme${whole ? '' : ' (im Strom)'}`)
        }
        if (whole) current.close()
      },
      drop,
    }
  }

  /** Speak, or stop if this same utterance is already sounding. */
  function toggle(text: string, language: string, key: SpeechKey = 'default'): void {
    trace(`toggle(key=${key}) speaking=${String(speakingKey.value)} `
      + `pending=${String(pendingKey.value)} blocked=${String(blockedKey.value)}`)
    // The waiting sound goes first: this click IS the gesture it was missing.
    if (blockedKey.value === key) {
      trace('  -> resume (Geste nachgereicht)')
      resume()
      return
    }
    if (speakingKey.value === key || pendingKey.value === key) {
      trace('  -> stop (lief bereits)')
      stop()
      return
    }
    void speak(text, language, key)
  }

  return {
    status,
    isAvailable,
    maxChars,
    speakingKey,
    pendingKey,
    blockedKey,
    soundingPiece,
    loadStatus,
    speak,
    feed,
    follow,
    toggle,
    stop,
    resume,
    speaksInFallback,
    isSpeakable,
  }
}

/**
 * The speaking surfaces' side of `follow`: one follower per turn, and the
 * surface's `askedKey` unsaid when the turn's voice is over, however it
 * ended. The workshop (views/resona.vue) and Persona (views/ai_persona.vue)
 * both stand on this; a third speaking surface takes it and builds no glue
 * of its own (rule 13, and the registry's entry on the standing turn).
 *
 * `hand(key, text, whole)` hands a turn's standing text over as it grows —
 * the SAME text the surface stands up, so that the cut is the same — and
 * `whole` once with the closing text. `end()` drops the turn that is live
 * without a word, for a turn that turns out not to be spoken after all
 * (writing mode, restored history, nothing spoken in it).
 *
 * @param language  read when a turn begins, so the turn is spoken in the
 *                  surface's language of that moment
 * @param askedKey  the surface's own "this turn is to be spoken": set by the
 *                  surface before it hands a turn over, unsaid here when the
 *                  turn's voice is over
 */
export function useSpokenTurn<K extends SpeechKey>(
  language: () => string,
  askedKey: Ref<K | null>,
): { hand(key: K, text: string, whole: boolean): void; end(): void } {
  const { follow } = useSpeech()
  let live: { key: K; turn: SpeechFollower } | null = null

  function end() {
    if (!live) return
    live.turn.drop()
    live = null
  }

  function hand(key: K, text: string, whole: boolean) {
    if (live && live.key !== key) end()
    if (!live) {
      // Over, one way or the other: a voice that is over is one the words no
      // longer have to follow.
      const over = () => { if (askedKey.value === key) askedKey.value = null }
      live = { key, turn: follow(language(), key, over) }
    }
    live.turn.update(text, whole)
    if (whole) live = null
  }

  return { hand, end }
}
