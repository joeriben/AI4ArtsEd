/**
 * The voice's TEXT TREATMENT: how an utterance becomes standing words — where
 * one sentence ends, how a sentence is built, how it arrives and how it leaves.
 *
 * Nothing here knows where the words stand. Placement, threads, anchors and
 * host chrome belong to the component that speaks; this module only decides
 * how the words READ, so that two surfaces speaking at once read as one voice
 * rather than as two implementations of it.
 *
 * The sentence DOM is built imperatively, off any framework's reactive path: a
 * per-character entrance runs on CSS transitions and must not be interrupted
 * by a re-render halfway through.
 *
 * The classes written here (`voice-sent`, `pvl-w`, `pvl-ch`) carry their whole
 * appearance in `@/assets/voiceText.css`; a host that renders the voice must
 * import that file. A host hooks its own placement rules onto the sentence via
 * `extraClass` — never by restyling the shared classes.
 */

type GraphemeSegmenter = new (
  loc: string,
  opts: { granularity: string },
) => { segment(s: string): Iterable<{ segment: string }> }

const segmentGraphemes: (s: string) => string[] = (() => {
  const S = (Intl as unknown as { Segmenter?: GraphemeSegmenter }).Segmenter
  if (!S) return (s: string) => Array.from(s)
  try {
    const inst = new S('en', { granularity: 'grapheme' })
    return (s: string) => Array.from(inst.segment(s), (x) => x.segment)
  } catch {
    return (s: string) => Array.from(s)
  }
})()

// The chat model answers in markdown; standing page-speech is plain writing.
function stripChatMarkup(text: string): string {
  return text
    .replace(/\*\*([^*]*)\*\*/g, '$1')
    .replace(/\*([^*]*)\*/g, '$1')
    .replace(/^#+\s+/gm, '')
    .replace(/(^|\s)(\d+[.)])\s+/g, '$1')
    .replace(/(^|\n)\s*[-•]\s+/g, '$1')
}

/**
 * Sentence boundaries for a spoken reply. The locale tag selects the sentence
 * segmenter's rules; it is the reply's language, not the UI's chrome language.
 */
export function splitVoiceSentences(text: string, localeTag: string = 'en'): string[] {
  const clean = stripChatMarkup(text).replace(/\s+/g, ' ').trim()
  if (!clean) return []
  let parts: string[] = []
  const S = (Intl as unknown as { Segmenter?: GraphemeSegmenter }).Segmenter
  if (S) {
    try {
      const inst = new S(String(localeTag || 'en'), { granularity: 'sentence' })
      parts = Array.from(inst.segment(clean), (x) => x.segment.trim()).filter(Boolean)
    } catch {
      /* fall through to regex */
    }
  }
  if (!parts.length) parts = clean.split(/(?<=[.!?…])\s+/).filter(Boolean)

  // Both paths break German abbreviations ("z. B.", "u. a.", "d. h."): the
  // period after a single letter reads as a sentence end, and the remainder
  // then stands in the room as its own placed sentence. The repair below runs
  // on the parts list whichever path produced it. Both merges only re-join
  // neighbours with the single space the split consumed — the character
  // sequence of `clean` is preserved, nothing is reordered or dropped.

  // A part ending in a detached single-letter head ("… (z." / "… u.") is the
  // opening half of an abbreviation and belongs to what follows. Merging into
  // the part already collected makes this iterative for free: a merged part
  // that again ends on a head ("… z. B. u.") keeps absorbing.
  const abbrevHead = /(^|\P{L})\p{L}\.$/u
  const joined: string[] = []
  for (const part of parts) {
    const lastIndex = joined.length - 1
    const prev = lastIndex >= 0 ? joined[lastIndex] : undefined
    if (prev !== undefined && abbrevHead.test(prev)) {
      joined[lastIndex] = prev + ' ' + part
    } else {
      joined.push(part)
    }
  }

  // No standalone fragments: under 25 characters a part is a clause remnant,
  // not an utterance, and placing it on the page states it as if it were one.
  // It joins its predecessor — or, when it is the head of the reply and has no
  // predecessor, the part that follows it (regardless of that part's length).
  const merged: string[] = []
  let headPending = false
  for (const part of joined) {
    const lastIndex = merged.length - 1
    const prev = lastIndex >= 0 ? merged[lastIndex] : undefined
    if (prev !== undefined && (headPending || part.length < 25)) {
      merged[lastIndex] = prev + ' ' + part
      headPending = false
      continue
    }
    merged.push(part)
    if (merged.length === 1 && part.length < 25) headPending = true
  }
  return merged
}

/**
 * Whether the words may arrive character by character. Per-character spans
 * break Arabic and Hebrew shaping, and the rubber-band entrance is motion the
 * user may have asked not to see; either way the sentence fades in as a whole.
 */
export function voiceCharMode(localeTag: string): boolean {
  const l = String(localeTag || '')
  if (l.startsWith('ar') || l.startsWith('he')) return false
  // matchMedia is absent under test; there the entrance simply stands.
  if (!window.matchMedia) return true
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * How long a character takes to be READ: the opacity transition on
 * `.voice-sent .pvl-ch` in @/assets/voiceText.css. Mirrored here because a
 * sentence given a span has to be finished by the end of that span, not merely
 * started — so the last character's fade has to fit inside it. If that CSS
 * duration ever changes, this must follow it.
 *
 * The rubber-band transform on the same rule is longer and is deliberately not
 * counted: a letter still settling into place has already been read. The
 * reduced-motion rule further down that file carries its own, longer fade and
 * never meets this number — `voiceCharMode()` refuses the per-character
 * variant under reduced motion in the first place.
 */
export const VOICE_CH_FADE_MS = 360

/**
 * How much longer a STRESSED grapheme takes to arrive than a plain one.
 *
 * From the platform-voice study, where the step was 76ms against 24ms. Carried
 * as a ratio rather than as milliseconds because the entrance here is spread
 * over a budget (a reading rhythm, or the measured length of the clip being
 * heard) — a fixed 76ms would blow that budget on any sentence with several
 * stressed words. At the short-sentence step of 22ms the ratio lands on 70ms,
 * which is the study's value back again.
 */
const STRESS_FACTOR = 3.2

/**
 * A word written `^so^` is spoken with weight: it takes longer to appear.
 *
 * NOT `|so|`, which is what the study used and what this was first written as.
 * The bar is the absolute value, and this platform's own texts are full of it —
 * `|α|` stands 47 times across the ten catalogues, saying the magnitude of
 * alpha. A notation that ate those bars would not fail loudly; it would set the
 * α apart and quietly drop the thing it meant. The caret is nowhere in those
 * texts as an enclosure, and no model writes it as one.
 *
 * The marks enclose the WORD, and punctuation may sit outside them — a sentence
 * ends `^so^.` and a quotation opens `"^so^`, so a mark that had to be the
 * token's very first and last character would miss the commonest place a word
 * carries weight. Letters and digits may not stand outside: the whole word has
 * to be enclosed, which is what keeps a stray caret from becoming a mark.
 */
const STRESSED = /^([^\p{L}\p{N}^]*)\^([^^]+)\^([^\p{L}\p{N}^]*)$/u

/** A word in the pieces that carry stress and the pieces that only sit beside it. */
interface WordPart {
  text: string
  stressed: boolean
}

function splitWordStress(word: string): WordPart[] {
  const m = STRESSED.exec(word)
  if (!m || !m[2]) return [{ text: word, stressed: false }]
  // A single character is not a word, and stress falls on words. This is what
  // keeps an exponent out (`x^2^`, `10^6^`) and a lone symbol with it — the
  // cost is stressing a one-letter word, which speech does not do anyway.
  if (segmentGraphemes(m[2]).length < 2) return [{ text: word, stressed: false }]
  const parts: WordPart[] = []
  if (m[1]) parts.push({ text: m[1], stressed: false })
  parts.push({ text: m[2], stressed: true })
  if (m[3]) parts.push({ text: m[3], stressed: false })
  return parts
}

/** The text as it is READ and heard — the marks are notation, not writing. */
function unmarkStress(text: string): string {
  return text
    .split(' ')
    .map((word) =>
      splitWordStress(word)
        .map((p) => p.text)
        .join(''),
    )
    .join(' ')
}

export interface VoiceSentenceOptions {
  /** The quieter register: what the voice reports about itself, not speech. */
  dim?: boolean
  /** false builds the whole-sentence variant (shaping-safe, motion-safe). */
  charMode: boolean
  /** The host's own hook on the sentence — placement is styled under it. */
  extraClass?: string
  /**
   * How long this sentence is being SPOKEN, measured. Given one, the entrance
   * is spread over it instead of over the fixed budget, so that the sentence is
   * finished being read when it is finished being heard. Shapes the
   * per-character variant only; the whole-sentence variant has no internal
   * rhythm to spread.
   */
  spanMs?: number
}

/**
 * One sentence, ready to be placed. It does not enter until it is revealed.
 *
 * A word may be written `^so^`. That is stress, and stress here is TIME: the
 * word takes longer to arrive than the words around it, and it is set apart
 * while it does. The marks are notation and never stand on the page — they are
 * out of the accessible label and out of the whole-sentence variant, which has
 * no rhythm for a stress to lengthen. Authored text only: nothing that comes
 * back from a model is marked, and a stray caret is not a mark, since the whole
 * word has to be enclosed — punctuation may stand outside the marks, letters
 * may not.
 */
export function buildVoiceSentence(text: string, opts: VoiceSentenceOptions): HTMLElement {
  const d = document.createElement('div')
  d.className =
    'voice-sent' + (opts.extraClass ? ' ' + opts.extraClass : '') + (opts.dim ? ' dim' : '')
  const plain = unmarkStress(text)
  // The characters are aria-hidden, so the sentence has to carry its own text
  // for assistive reading — in both variants, so both read the same.
  d.setAttribute('aria-label', plain)
  if (!opts.charMode) {
    d.classList.add('whole')
    // The whole-sentence variant has no per-character rhythm, so there is
    // nothing for a stress to lengthen. It reads the words, not the marks.
    d.textContent = plain
    return d
  }
  const words = text.split(' ')
  // Stressed graphemes cost STRESS_FACTOR of the budget, so they have to be
  // counted that way before the step is divided out of it — otherwise a
  // sentence with weight in it runs past the rhythm it was given.
  let graphemeCount = 0
  for (const word of words) {
    for (const part of splitWordStress(word)) {
      const n = segmentGraphemes(part.text).length
      graphemeCount += part.stressed ? n * STRESS_FACTOR : n
    }
  }
  let delayStep: number
  let delay: number
  if (opts.spanMs === undefined) {
    // The entrance must converge to stable word forms within a reading rhythm,
    // so the budget belongs to the whole sentence, not to the single character:
    // however long the sentence, its staggered delays span at most ~2.6s. Only
    // graphemes carry a step (the spaces between words do not), so the budget is
    // divided by the grapheme count alone. 22ms stays the step for short
    // sentences; 5ms is the floor at which the stagger still reads as one letter
    // arriving after another rather than as a single block.
    delayStep = Math.min(22, Math.max(5, Math.floor(2600 / Math.max(1, graphemeCount))))
    delay = 180
  } else {
    // A span is a MEASURED length of sound, and the sentence has to be read by
    // the time that sound stops — so the last character's fade has to fall
    // inside it, and the steps are spread over what is left once that fade is
    // taken off the end. The characters start at once: with a span the sound is
    // already running as the sentence is built, and an opening pause would be
    // taken out of the reading. 1ms is a floor against a step of nothing.
    //
    // No ceiling here, unlike the fixed budget above: the 22ms there keeps a
    // short sentence from crawling through a budget it never asked for, while
    // here the budget IS the voice. A cap would let the words finish early and
    // re-open the very gap between reading and hearing that a span closes.
    const budget = Math.max(0, opts.spanMs - VOICE_CH_FADE_MS)
    delayStep = Math.max(1, Math.floor(budget / Math.max(1, graphemeCount)))
    delay = 0
  }
  words.forEach((word, wi) => {
    // The word stays one body either way; the stress sits INSIDE it, so a
    // stressed word still cannot break between its characters — and neither can
    // the punctuation beside it, which is why the parts share the one body.
    const w = document.createElement('span')
    w.className = 'pvl-w'
    for (const part of splitWordStress(word)) {
      const host = part.stressed ? document.createElement('em') : w
      if (part.stressed) w.appendChild(host)
      const step = part.stressed ? delayStep * STRESS_FACTOR : delayStep
      segmentGraphemes(part.text).forEach((g) => {
        const c = document.createElement('span')
        c.className = 'pvl-ch'
        c.setAttribute('aria-hidden', 'true')
        c.textContent = g
        c.style.transitionDelay = Math.round(delay) + 'ms'
        delay += step
        host.appendChild(c)
      })
    }
    d.appendChild(w)
    if (wi < words.length - 1) d.appendChild(document.createTextNode(' '))
  })
  return d
}

/**
 * Let a placed sentence enter.
 *
 * `delayMs` holds the sentence back before it begins, in BOTH variants. Its
 * characters carry the rhythm INSIDE the sentence; this is the distance
 * BETWEEN sentences, and several of them handed rising delays follow one
 * another instead of standing up as one block. Until 2026-08-17 the argument
 * reached the whole-sentence variant alone — so on every locale that reads per
 * character, which is all of them but ar/he, a whole reply appeared at once
 * while both callers were already passing the rising delays that were meant to
 * space it out.
 *
 * A sentence built over a measured span of sound is passed 0 by its caller:
 * the sound is already running as it is placed, and a wait would take its
 * opening out of the reading.
 */
export function revealVoiceSentence(el: HTMLElement, delayMs: number): void {
  // The whole-sentence variant has no internal rhythm, so its entrance can
  // only be placed in time from outside.
  if (el.classList.contains('whole')) {
    window.setTimeout(() => el.classList.add('on'), delayMs)
    return
  }
  // Per character the characters carry the rhythm INSIDE the sentence
  // (transition-delay, written at build time); the wait below is the distance
  // to the sentence before it.
  el.classList.add('on')
  // Two frames must pass before they start: the characters have to have been
  // painted in their starting state, or there is nothing to run from.
  const light = () => el.querySelectorAll('.pvl-ch').forEach((c) => c.classList.add('on'))
  // A frame that is not painted never comes: a tab in the background is handed
  // no animation frames at all, and a sentence that waited for two of them
  // would still be standing there unlit when the human came back. Out of sight
  // the characters are simply set — there is no transition to run either.
  const enter = () =>
    document.hidden
      ? window.setTimeout(light, 0)
      : requestAnimationFrame(() => requestAnimationFrame(light))
  // The sentence is placed and measured at once — only its characters wait, so
  // nothing moves under the sentences that follow it.
  if (delayMs > 0) window.setTimeout(enter, delayMs)
  else enter()
}

/** Let a sentence leave for good. */
export function fadeOutVoiceSentence(el: HTMLElement): void {
  // The node goes only after the fade has run: removed earlier it would cut
  // the fade, left standing it would still occupy the ground it fell out of.
  el.classList.add('gone')
  window.setTimeout(() => el.remove(), 400)
}
