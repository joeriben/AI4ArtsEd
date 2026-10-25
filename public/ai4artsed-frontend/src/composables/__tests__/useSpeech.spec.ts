import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import { splitForSpeech, useSpeech, useSpokenTurn } from '@/composables/useSpeech'
import { useUserPreferencesStore } from '@/stores/userPreferences'

// Sentence ends and nowhere else. A fragment is not spoken as a fragment: the
// model invents a continuation, and "Hallo. Ich bin Persona, eine Maschine,
// die Bilder, Klang," (57 characters) came back as 15 seconds of audio after
// 16 seconds of synthesis, against 4.7 for a whole sentence half again as long.
describe('splitForSpeech', () => {
  it('leaves one sentence whole, however long', () => {
    const long = 'Ich bin Persona, eine Maschine, die Bilder, Klang, Video und Objekte '
      + 'erzeugen kann, aber nicht auf Kommando, und die darueber mit dir verhandelt.'
    expect(splitForSpeech(long)).toEqual([long])
  })

  it('cuts between sentences', () => {
    expect(splitForSpeech(
      'Schau dir das Bild noch einmal an, in aller Ruhe. '
      + 'Was faellt dir jetzt auf, das dir vorher entgangen ist?',
    )).toEqual([
      'Schau dir das Bild noch einmal an, in aller Ruhe.',
      'Was faellt dir jetzt auf, das dir vorher entgangen ist?',
    ])
  })

  // A short opening sentence is the best start there is — one second of audio,
  // and the answer has begun. It is never merged away.
  it('keeps a short opening sentence as its own piece', () => {
    expect(splitForSpeech('Hallo. Ich bin Persona, eine Maschine mit einer Position.'))
      .toEqual(['Hallo.', 'Ich bin Persona, eine Maschine mit einer Position.'])
  })

  it('does not break on abbreviations', () => {
    expect(splitForSpeech(
      'Nimm dir ein Material, z. B. Ton oder Papier, und arbeite damit weiter. '
      + 'Danach reden wir darueber.',
    )).toEqual([
      'Nimm dir ein Material, z. B. Ton oder Papier, und arbeite damit weiter.',
      'Danach reden wir darueber.',
    ])
  })

  it('does not break on a date or a title', () => {
    expect(splitForSpeech('Am 3. Januar kommt Dr. Meier zu uns in den Workshop.'))
      .toEqual(['Am 3. Januar kommt Dr. Meier zu uns in den Workshop.'])
  })

  it('cuts on blank lines', () => {
    expect(splitForSpeech('Erster Abschnitt\n\nZweiter Abschnitt'))
      .toEqual(['Erster Abschnitt', 'Zweiter Abschnitt'])
  })

  it('handles question and exclamation marks', () => {
    expect(splitForSpeech('Was siehst du? Sag es laut! Und dann noch einmal.'))
      .toEqual(['Was siehst du?', 'Sag es laut!', 'Und dann noch einmal.'])
  })

  it('keeps a script without sentence marks in one piece', () => {
    const ko = '이 이미지를 다시 한 번 보세요 무엇이 보이나요'
    expect(splitForSpeech(ko)).toEqual([ko])
  })

  it('never returns nothing', () => {
    expect(splitForSpeech('…')).toEqual(['…'])
  })

  it('loses no text, whatever the shape', () => {
    for (const t of [
      'Kurz.',
      'Eins. Zwei. Drei. Vier. Fuenf.',
      'Ein sehr langer Satz ohne jede Interpunktion der einfach immer weiter geht',
      'Frage? Antwort! Und dann noch ein abschliessender Satz dazu.',
      'Am 3. Januar, also z. B. naechste Woche, treffen wir uns wieder.',
    ]) {
      expect(splitForSpeech(t).join(' ').replace(/\s+/g, ' ')).toBe(t.replace(/\s+/g, ' '))
    }
  })
})


// ---------------------------------------------------------------------------
// The piece that is sounding.
//
// Another surface builds on this: it renders splitForSpeech(text) itself and
// lets sentence i appear at the moment sentence i starts being spoken. That
// makes `soundingPiece` a contract between two files, and a contract that is
// only kept by hand is kept until someone edits playClip.
//
// The element is faked so that a piece does NOT end on its own — the test says
// when it ends. Without that, the middle of an utterance is not observable.
// ---------------------------------------------------------------------------
class FakeAudio {
  static el: FakeAudio | null = null
  /** Set to make the next play() refuse, the way a browser without a gesture does. */
  static refuseOnce = false
  src = ''
  currentTime = 0
  /** Whatever a real clip of this sentence would last. */
  duration = 6.4
  onended: (() => void) | null = null
  onerror: (() => void) | null = null
  constructor() { FakeAudio.el = this }
  play(): Promise<void> {
    if (FakeAudio.refuseOnce) {
      FakeAudio.refuseOnce = false
      const refusal = new Error('play() needs a gesture')
      refusal.name = 'NotAllowedError'
      return Promise.reject(refusal)
    }
    return Promise.resolve()
  }
  pause() { /* nothing to stop */ }
  /** This piece has finished sounding. */
  end() { this.onended?.() }
}

const STATUS = {
  available: true,
  reason: null,
  voiced_languages: ['de', 'en'],
  unvoiced_languages: ['he'],
  fallback_language: 'en',
  voices: ['clear'],
  default_voice: 'clear',
  max_chars: 4000,
}

/** Let every pending fetch, blob and play() settle. */
async function settle(): Promise<void> {
  for (let i = 0; i < 6; i++) await new Promise(resolve => setTimeout(resolve, 0))
}

/** A fresh ear per test. */
function freshEar(): void {
  // The voice asks the main menu's switch whether it may speak at all, so
  // there has to be a store to ask. Fresh per test, and the switch is on by
  // default — a listener who has decided nothing is spoken to.
  localStorage.clear()
  setActivePinia(createPinia())
  FakeAudio.refuseOnce = false
  vi.stubGlobal('Audio', FakeAudio)
  vi.stubGlobal('fetch', vi.fn(async (url: unknown) => (
    String(url).endsWith('/api/speech/status')
      ? { ok: true, json: async () => STATUS }
      : { ok: true, blob: async () => new Blob(['wav']) }
  )))
  URL.createObjectURL = () => 'blob:piece'
  URL.revokeObjectURL = () => { /* nothing held */ }
}

/** How many clips have been asked for so far. */
function clipsAsked(): number {
  const calls = (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls
  return calls.filter(([url]) => String(url).endsWith('/api/speech')).length
}

describe('soundingPiece', () => {
  const TEXT = 'Schau dir das Bild noch einmal an, in aller Ruhe. '
    + 'Was faellt dir jetzt auf, das dir vorher entgangen ist?'
  const PIECES = splitForSpeech(TEXT)

  beforeEach(freshEar)

  it('splits into more than one piece, or the rest of this proves nothing', () => {
    expect(PIECES.length).toBe(2)
  })

  it('names the audible piece, moves on with it, and clears at the end', async () => {
    const speech = useSpeech()
    await speech.loadStatus()

    const utterance = speech.speak(TEXT, 'de', 'k1')
    await settle()
    expect(speech.soundingPiece.value)
      .toEqual({ key: 'k1', index: 0, text: PIECES[0], total: 2, durationMs: 6400 })

    FakeAudio.el!.end()
    await settle()
    expect(speech.soundingPiece.value)
      .toEqual({ key: 'k1', index: 1, text: PIECES[1], total: 2, durationMs: 6400 })

    FakeAudio.el!.end()
    await utterance
    expect(speech.soundingPiece.value).toBeNull()
  })

  // The whole point of setting it at play() rather than before: a piece the
  // browser refused is not sounding, however loaded it is.
  it('says nothing is sounding while a piece waits for the gesture', async () => {
    FakeAudio.refuseOnce = true
    const speech = useSpeech()
    await speech.loadStatus()

    void speech.speak(TEXT, 'de', 'k2')
    await settle()
    expect(speech.blockedKey.value).toBe('k2')
    expect(speech.soundingPiece.value).toBeNull()

    speech.resume()
    await settle()
    expect(speech.soundingPiece.value)
      .toEqual({ key: 'k2', index: 0, text: PIECES[0], total: 2, durationMs: 6400 })

    speech.stop()
    expect(speech.soundingPiece.value).toBeNull()
  })

  // The span is what lets the words be read in the time the sentence is
  // spoken. Where it cannot be had, the surface must be able to tell, rather
  // than pace against a zero.
  it('says null for the span when the element does not know it', async () => {
    const speech = useSpeech()
    await speech.loadStatus()
    FakeAudio.el!.duration = NaN

    void speech.speak(TEXT, 'de', 'k3')
    await settle()
    expect(speech.soundingPiece.value)
      .toEqual({ key: 'k3', index: 0, text: PIECES[0], total: 2, durationMs: null })

    speech.stop()
    FakeAudio.el!.duration = 6.4
  })

  // The switch in the main menu is the one place a listener can silence
  // everything at once. If it only stopped Help, or only the workshop, it
  // would not be that.
  it('offers no voice at all once the switch is off', async () => {
    const speech = useSpeech()
    await speech.loadStatus()
    expect(speech.isAvailable.value).toBe(true)

    useUserPreferencesStore().setVoiceChat(false)
    expect(speech.isAvailable.value).toBe(false)

    await speech.speak(TEXT, 'de', 'k4')
    expect(speech.soundingPiece.value).toBeNull()
    expect(speech.speakingKey.value).toBeNull()
  })

  // A stale piece read as the current one is worse than none: the surface
  // would reveal a sentence of an utterance nobody is hearing any more.
  it('hands the line straight to the utterance that took over', async () => {
    const speech = useSpeech()
    await speech.loadStatus()

    void speech.speak(TEXT, 'de', 'first')
    await settle()
    expect(speech.soundingPiece.value?.key).toBe('first')

    void speech.speak(TEXT, 'de', 'second')
    await settle()
    expect(speech.soundingPiece.value)
      .toEqual({ key: 'second', index: 0, text: PIECES[0], total: 2, durationMs: 6400 })

    speech.stop()
  })
})

// An utterance that arrives while it is being written: the pieces are handed
// over one at a time, and how many there are is known only at the end.
describe('feed', () => {
  const PIECES = [
    'Schau dir das Bild noch einmal an, in aller Ruhe.',
    'Was faellt dir jetzt auf, das dir vorher entgangen ist?',
    'Sag es laut.',
  ]

  beforeEach(freshEar)

  it('sounds a piece as soon as it is handed over, and learns the count at the end', async () => {
    const speech = useSpeech()
    await speech.loadStatus()

    const feed = speech.feed('de', 'f1')
    feed.push(PIECES[0]!)
    await settle()
    expect(speech.soundingPiece.value)
      .toEqual({ key: 'f1', index: 0, text: PIECES[0], total: null, durationMs: 6400 })

    feed.push(PIECES[1]!)
    feed.close()
    // The count reaches the piece that is sounding, not only the next one.
    expect(speech.soundingPiece.value?.total).toBe(2)

    FakeAudio.el!.end()
    await settle()
    expect(speech.soundingPiece.value)
      .toEqual({ key: 'f1', index: 1, text: PIECES[1], total: 2, durationMs: 6400 })

    FakeAudio.el!.end()
    await feed.done
    expect(speech.soundingPiece.value).toBeNull()
    expect(speech.speakingKey.value).toBeNull()
  })

  // The opening piece alone, then each later one the moment it is handed
  // over — while the first still sounds, not once it has finished.
  it('asks for a later piece the moment it is handed over', async () => {
    const speech = useSpeech()
    await speech.loadStatus()

    const feed = speech.feed('de', 'f2')
    feed.push(PIECES[0]!)
    await settle()
    expect(clipsAsked()).toBe(1)
    expect(speech.soundingPiece.value?.index).toBe(0)

    feed.push(PIECES[1]!)
    expect(clipsAsked()).toBe(2)
    feed.close()
    speech.stop()
  })

  it('drops what has not sounded when cancelled, and settles', async () => {
    const speech = useSpeech()
    await speech.loadStatus()

    const feed = speech.feed('de', 'f3')
    feed.push(PIECES[0]!)
    feed.push(PIECES[1]!)
    await settle()
    expect(speech.soundingPiece.value?.index).toBe(0)

    feed.cancel()
    expect(speech.soundingPiece.value).toBeNull()
    expect(speech.speakingKey.value).toBeNull()
    await feed.done

    // Nothing handed over after that reaches the speakers.
    const asked = clipsAsked()
    feed.push(PIECES[2]!)
    await settle()
    expect(clipsAsked()).toBe(asked)
    expect(speech.soundingPiece.value).toBeNull()
  })

  // Nothing follows an utterance that has said it is over.
  it('ignores a piece handed over after close()', async () => {
    const speech = useSpeech()
    await speech.loadStatus()

    const feed = speech.feed('de', 'f4')
    feed.push(PIECES[0]!)
    feed.close()
    feed.push(PIECES[1]!)
    await settle()
    expect(speech.soundingPiece.value?.total).toBe(1)

    FakeAudio.el!.end()
    await feed.done
    expect(speech.soundingPiece.value).toBeNull()
  })

  // Stopping takes the handlers off the element, so nothing would ever say
  // the piece ended. The ending is reported all the same.
  it('settles when the line is taken away, by stop() or by the next utterance', async () => {
    const speech = useSpeech()
    await speech.loadStatus()

    const first = speech.feed('de', 'f6')
    first.push(PIECES[0]!)
    await settle()
    expect(speech.soundingPiece.value?.key).toBe('f6')
    let firstOver = false
    void first.done.then(() => { firstOver = true })

    speech.stop()
    await settle()
    expect(firstOver).toBe(true)

    const second = speech.feed('de', 'f7')
    second.push(PIECES[0]!)
    await settle()
    expect(speech.soundingPiece.value?.key).toBe('f7')
    let secondOver = false
    void second.done.then(() => { secondOver = true })

    const third = speech.feed('de', 'f8')
    third.push(PIECES[0]!)
    await settle()
    expect(speech.soundingPiece.value?.key).toBe('f8')
    expect(secondOver).toBe(true)
    speech.stop()
  })

  // A piece the browser refused sounds after the tap; by then the writing
  // may be over, and the count with it.
  it('gives a piece held back for the gesture the count known at the tap', async () => {
    FakeAudio.refuseOnce = true
    const speech = useSpeech()
    await speech.loadStatus()

    const feed = speech.feed('de', 'f9')
    feed.push(PIECES[0]!)
    await settle()
    expect(speech.blockedKey.value).toBe('f9')
    expect(speech.soundingPiece.value).toBeNull()

    feed.push(PIECES[1]!)
    feed.close()
    speech.resume()
    await settle()
    expect(speech.soundingPiece.value)
      .toEqual({ key: 'f9', index: 0, text: PIECES[0], total: 2, durationMs: 6400 })
    speech.stop()
  })

  // A piece held back for the gesture is let go of with the utterance: the
  // next one that is refused waits on its own, and the tap reaches it.
  it('lets a held-back piece go when the line is taken away', async () => {
    FakeAudio.refuseOnce = true
    const speech = useSpeech()
    await speech.loadStatus()

    const first = speech.feed('de', 'f10')
    first.push(PIECES[0]!)
    first.close()
    await settle()
    expect(speech.blockedKey.value).toBe('f10')
    let firstOver = false
    void first.done.then(() => { firstOver = true })

    speech.stop()
    await settle()
    expect(firstOver).toBe(true)
    expect(speech.blockedKey.value).toBeNull()

    FakeAudio.refuseOnce = true
    const second = speech.feed('de', 'f11')
    second.push(PIECES[1]!)
    second.close()
    await settle()
    expect(speech.blockedKey.value).toBe('f11')
    speech.resume()
    await settle()
    expect(speech.soundingPiece.value)
      .toEqual({ key: 'f11', index: 0, text: PIECES[1], total: 1, durationMs: 6400 })
    speech.stop()
  })

  // The switch in the main menu, turned off while a reply is being spoken:
  // the piece that sounds ends, and nothing after it begins.
  it('sounds nothing further once the switch is off', async () => {
    const speech = useSpeech()
    await speech.loadStatus()

    const feed = speech.feed('de', 'f12')
    feed.push(PIECES[0]!)
    feed.push(PIECES[1]!)
    feed.close()
    await settle()
    expect(speech.soundingPiece.value?.index).toBe(0)
    let over = false
    void feed.done.then(() => { over = true })

    useUserPreferencesStore().setVoiceChat(false)
    FakeAudio.el!.end()
    await settle()
    expect(over).toBe(true)
    expect(speech.soundingPiece.value).toBeNull()
    expect(speech.speakingKey.value).toBeNull()
  })

  // speak() is the feed with every piece handed over at once, so the count is
  // known from the first sound.
  it('is what speak() is made of', async () => {
    const speech = useSpeech()
    await speech.loadStatus()

    void speech.speak(PIECES.join(' '), 'de', 'f5')
    await settle()
    expect(speech.soundingPiece.value)
      .toEqual({ key: 'f5', index: 0, text: PIECES[0], total: 3, durationMs: 6400 })
    speech.stop()
  })
})

// A turn spoken while it is being written: the surface hands over the text as
// it stands, and what waits, what is dropped and what starts over is decided
// here and not once per surface.
describe('follow', () => {
  const S = [
    'Schau dir das Bild noch einmal an, in aller Ruhe.',
    'Was faellt dir jetzt auf, das dir vorher entgangen ist?',
    'Sag es laut.',
  ]

  beforeEach(freshEar)

  it('hands over a sentence once the stream has begun the next one, and the last one with the whole', async () => {
    const speech = useSpeech()
    await speech.loadStatus()
    const over = vi.fn()
    const turn = speech.follow('de', 't1', over)

    // Half a sentence: nothing is closed yet.
    turn.update(S[0]!.slice(0, 20), false)
    await settle()
    expect(clipsAsked()).toBe(0)

    // The first sentence stands and the second has begun: the first goes.
    turn.update(S[0] + ' ' + S[1]!.slice(0, 10), false)
    await settle()
    expect(clipsAsked()).toBe(1)
    expect(speech.soundingPiece.value)
      .toEqual({ key: 't1', index: 0, text: S[0], total: null, durationMs: 6400 })

    // The writing is over: the last sentence goes too, and the count is known.
    turn.update(S[0] + ' ' + S[1], true)
    expect(clipsAsked()).toBe(2)
    expect(speech.soundingPiece.value?.total).toBe(2)
    expect(over).not.toHaveBeenCalled()

    FakeAudio.el!.end()
    await settle()
    FakeAudio.el!.end()
    await settle()
    expect(over).toHaveBeenCalledTimes(1)
    expect(speech.soundingPiece.value).toBeNull()
  })

  // A tool round's preamble, or a draft that failed its evidence duty: the
  // standing text no longer begins with what was handed over.
  it('drops a text that was taken back and starts the next one from its first sentence', async () => {
    const speech = useSpeech()
    await speech.loadStatus()
    const over = vi.fn()
    const turn = speech.follow('de', 't2', over)

    turn.update(S[0] + ' ' + S[1], false)
    await settle()
    expect(speech.soundingPiece.value?.text).toBe(S[0])

    turn.update('', false)
    expect(speech.soundingPiece.value).toBeNull()
    expect(speech.speakingKey.value).toBeNull()
    // Dropped by the text, not by the caller: the words are not told yet,
    // because a corrected text is on its way and will be spoken.
    expect(over).not.toHaveBeenCalled()

    turn.update(S[2] + ' ' + S[1]!.slice(0, 8), false)
    await settle()
    expect(speech.soundingPiece.value)
      .toEqual({ key: 't2', index: 0, text: S[2], total: null, durationMs: 6400 })
    turn.drop()
  })

  // The delivery filter took a sentence out of the closing text that the
  // stream had already handed over: what was said stays said, the rest of the
  // closing text follows, and the turn goes on from where it is.
  it('goes on with what the closing text has beyond what was said', async () => {
    const speech = useSpeech()
    await speech.loadStatus()
    const over = vi.fn()
    const turn = speech.follow('de', 't3', over)
    const Q = 'Wollt ihr Ton oder Papier?'

    turn.update(S[0] + ' ' + Q + ' ' + S[2]!.slice(0, 5), false)
    await settle()
    expect(clipsAsked()).toBe(2)
    expect(speech.soundingPiece.value?.text).toBe(S[0])

    turn.update(S[0] + ' ' + S[2], true)
    await settle()
    // The first piece sounds on; one more clip was asked for, the new sentence.
    expect(clipsAsked()).toBe(3)
    expect(speech.soundingPiece.value)
      .toEqual({ key: 't3', index: 0, text: S[0], total: 3, durationMs: 6400 })
    expect(over).not.toHaveBeenCalled()
    turn.drop()
  })

  // A closing text that arrives whole, nothing handed over before it, is under
  // the rule speak() applies to every text: too long is unspoken.
  it('leaves a whole text that is too long unspoken', async () => {
    const speech = useSpeech()
    await speech.loadStatus()
    const over = vi.fn()
    const turn = speech.follow('de', 't10', over)
    const long = Array.from({ length: 120 }, () => S[0]).join(' ')
    expect(long.length).toBeGreaterThan(STATUS.max_chars)

    turn.update(long, true)
    await settle()
    expect(clipsAsked()).toBe(0)
    expect(over).toHaveBeenCalledTimes(1)
    expect(speech.speakingKey.value).toBeNull()
  })

  it('says nothing after drop(), and does not report it over', async () => {
    const speech = useSpeech()
    await speech.loadStatus()
    const over = vi.fn()
    const turn = speech.follow('de', 't4', over)

    turn.update(S[0] + ' ' + S[1], false)
    await settle()
    expect(speech.soundingPiece.value?.index).toBe(0)

    turn.drop()
    expect(speech.soundingPiece.value).toBeNull()
    await settle()
    expect(over).not.toHaveBeenCalled()
  })

  it('reports a closing text with nothing to say as over', async () => {
    const speech = useSpeech()
    await speech.loadStatus()
    const over = vi.fn()
    const turn = speech.follow('de', 't5', over)
    turn.update('', true)
    expect(over).toHaveBeenCalledTimes(1)
  })

  // Help speaking over the turn, or the listener stopping it, while a piece
  // sounds: the turn's voice is over, the words are told, and the closing text
  // does not start it again from the top.
  it('is over for good once another utterance took the line while a piece sounded', async () => {
    const speech = useSpeech()
    await speech.loadStatus()
    const over = vi.fn()
    const turn = speech.follow('de', 't6', over)

    turn.update(S[0] + ' ' + S[1]!.slice(0, 10), false)
    await settle()
    expect(speech.soundingPiece.value?.key).toBe('t6')

    void speech.speak(S[2]!, 'de', 'help')
    await settle()
    expect(speech.soundingPiece.value?.key).toBe('help')
    expect(over).toHaveBeenCalledTimes(1)

    // The stream goes on, and then closes: nothing of it is asked for.
    const asked = clipsAsked()
    turn.update(S[0] + ' ' + S[1] + ' ' + S[2]!.slice(0, 5), false)
    turn.update(S.join(' '), true)
    await settle()
    expect(clipsAsked()).toBe(asked)
    expect(speech.soundingPiece.value?.key).toBe('help')
    // Told once at the ending and once more for each update after it: the
    // caller marks the turn as asked before an update.
    expect(over).toHaveBeenCalledTimes(3)
    speech.stop()
  })

  it('is over for good once the line was taken while it waited for the next sentence', async () => {
    const speech = useSpeech()
    await speech.loadStatus()
    const over = vi.fn()
    const turn = speech.follow('de', 't7', over)

    turn.update(S[0] + ' ' + S[1]!.slice(0, 10), false)
    await settle()
    FakeAudio.el!.end()
    await settle()
    // The first sentence has sounded and the second is not closed yet. The
    // last piece that became audible stands until the next one does, as it
    // does while a slow synthesis is awaited.
    expect(speech.soundingPiece.value?.index).toBe(0)
    expect(speech.speakingKey.value).toBe('t7')

    speech.stop()
    await settle()
    expect(over).toHaveBeenCalledTimes(1)

    const asked = clipsAsked()
    turn.update(S[0] + ' ' + S[1] + ' ' + S[2]!.slice(0, 5), false)
    turn.update(S.join(' '), true)
    await settle()
    expect(clipsAsked()).toBe(asked)
    expect(speech.soundingPiece.value).toBeNull()
    expect(speech.speakingKey.value).toBeNull()
    expect(over).toHaveBeenCalledTimes(3)
  })

  // A closing text that adds no new piece (the delivery filter cut the last
  // sentence) opens nothing and takes the line from nobody.
  it('opens no second utterance for a closing text that adds nothing', async () => {
    const speech = useSpeech()
    await speech.loadStatus()
    const over = vi.fn()
    const turn = speech.follow('de', 't8', over)

    turn.update(S[0] + ' ' + S[1]!.slice(0, 10), false)
    await settle()
    void speech.speak(S[2]!, 'de', 'help')
    await settle()
    expect(over).toHaveBeenCalledTimes(1)

    turn.update(S[0]!, true)
    await settle()
    expect(speech.soundingPiece.value?.key).toBe('help')
    expect(speech.speakingKey.value).toBe('help')
    speech.stop()
  })

  // The surfaces' side: one follower per turn, and the surface's askedKey
  // unsaid when the turn's voice is over.
  it('unsays the surface\'s askedKey when the turn is over, and on a turn it drops', async () => {
    const speech = useSpeech()
    await speech.loadStatus()
    const askedKey = ref<number | null>(null)
    const spoken = useSpokenTurn(() => 'de', askedKey)

    askedKey.value = 7
    spoken.hand(7, S[0] + ' ' + S[1]!.slice(0, 10), false)
    await settle()
    expect(speech.soundingPiece.value?.key).toBe(7)
    expect(askedKey.value).toBe(7)

    spoken.hand(7, S[0] + ' ' + S[1], true)
    FakeAudio.el!.end()
    await settle()
    FakeAudio.el!.end()
    await settle()
    expect(askedKey.value).toBeNull()

    // A next turn, dropped by the surface: the voice stops, the key is the
    // surface's to unsay.
    askedKey.value = 8
    spoken.hand(8, S[2] + ' ' + S[1]!.slice(0, 10), false)
    await settle()
    expect(speech.soundingPiece.value?.key).toBe(8)
    spoken.end()
    expect(speech.soundingPiece.value).toBeNull()
    expect(askedKey.value).toBe(8)
  })

  // A clip that could not be had ends the turn's voice, as it ends speak():
  // the rest is not spoken misnumbered from a fresh start.
  it('is over once a clip could not be had, and does not start over at the closing text', async () => {
    const speech = useSpeech()
    await speech.loadStatus()
    const over = vi.fn()
    const turn = speech.follow('de', 't9', over)

    turn.update(S[0] + ' ' + S[1]!.slice(0, 10), false)
    await settle()
    expect(speech.soundingPiece.value?.index).toBe(0)

    // The second clip fails on the server.
    const fetchMock = globalThis.fetch as unknown as { mockImplementationOnce: (f: () => unknown) => void }
    fetchMock.mockImplementationOnce(async () => ({ ok: false, status: 500, text: async () => 'down' }))
    turn.update(S[0] + ' ' + S[1] + ' ' + S[2]!.slice(0, 5), false)
    await settle()
    FakeAudio.el!.end()
    await settle()
    expect(over).toHaveBeenCalledTimes(1)
    expect(speech.soundingPiece.value).toBeNull()

    const asked = clipsAsked()
    turn.update(S.join(' '), true)
    await settle()
    expect(clipsAsked()).toBe(asked)
    expect(speech.soundingPiece.value).toBeNull()
    expect(over).toHaveBeenCalledTimes(2)
  })
})
