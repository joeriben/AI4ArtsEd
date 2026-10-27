import { computed, type Ref } from 'vue'

export type MediumId = 'image' | 'video' | 'sound' | '3d' | 'code' | 'text'
export const MEDIA: MediumId[] = ['image', 'video', 'sound', '3d', 'code', 'text']

/**
 * The glyph a config's media type is drawn with on the canvas (StageModule,
 * ConfigSelectorModal): `audio` and `music` are both `sound`; a type with no
 * glyph answers null and the caller keeps its own mark.
 */
export function glyphOfMediaType(mediaType: string | undefined): MediumId | null {
  switch (mediaType) {
    case 'image': return 'image'
    case 'video': return 'video'
    case 'audio':
    case 'music': return 'sound'
    case 'text': return 'text'
    default: return null
  }
}

/**
 * Medium inference — Stage 1: a fast, client-side catchword pre-filter.
 *
 * Deliberately coarse, exactly like the safety check's keyword blocklist. The
 * small local LLM (Stage 2, coupled to the safety run at the input box) rewrites
 * the TEXT and never returns a medium; what it wrote is re-read here, word for
 * word, once it lies on the table (x2x_flow feeds the interception result back
 * into this tier). Same two-tier shape as safety, with the medium always read,
 * never chosen: the idea (and, once transformed, the reread version) already
 * carries its mediality. This tier runs on every keystroke with zero latency so
 * the medium symbols can light up ambiently while the learner writes.
 *
 * Steering happens through the prompt.
 */
const CATCHWORDS: Record<MediumId, string[]> = {
  image: [
    'bild', 'gemälde', 'gemaelde', 'foto', 'fotografie', 'zeichnung', 'illustration',
    'portrait', 'porträt', 'poster', 'plakat', 'malerei', 'collage', 'stillleben',
    // German painting vocabulary, missing until 2026-10-16 (UCD-260): the most
    // ordinary picture prompts — »gemalt als Aquarell«, »Kinder malen ein
    // Haus« — carried no image word at all, so a single movement word made them
    // video. 'malt' with it: the verb in all its forms names the medium.
    'aquarell', 'gemalt', 'malen', 'malt',
    'painting', 'photo', 'photograph', 'image', 'picture', 'drawing', 'render',
  ],
  video: [
    'video', 'film', 'animation', 'clip',
    // The one German compound whose head word names the other medium: a
    // »bewegtes Bild« is film (»Bewegte Bilder«), and its 'bild' must not read
    // as a picture. A phrase catchword is just a longer word to `wordAt`.
    'bewegtes bild', 'bewegte bilder', 'bewegten bilder',
    'animated', 'animate', 'sequence',
  ],
  sound: [
    'klang', 'klingt', 'musik', 'sound', 'ton', 'töne', 'toene', 'melodie', 'lied',
    'song', 'rhythmus', 'geräusch', 'geraeusch', 'hören', 'hoerspiel', 'soundscape',
    'audio', 'music', 'sonic', 'beat', 'noise', 'echo', 'hall',
    // The two plurals that do not begin with their singular.
    'klänge', 'klaenge', 'rhythmen',
  ],
  // Deliberately narrow. '3d' is reachable only from an image, so a false
  // positive here costs a lit glyph that cannot run — not a wrong generation.
  // Ambiguous words stay out: 'plastik' is also a material, 'figur' also a
  // character, 'modell' also a person.
  '3d': [
    '3d', 'dreidimensional', 'skulptur', 'statue', 'büste', 'bueste', 'relief',
    'mesh', 'sculpture', 'figurine', 'bust', 'three-dimensional',
  ],
  // Two configs write JavaScript rather than a file: p5.js draws, Tone.js
  // plays. Narrow on purpose — 'programm' and 'muster' are far too common to
  // carry a medium, and a false positive here would light a glyph over an idea
  // that meant a picture.
  code: [
    'code', 'sketch', 'p5', 'p5.js', 'tone.js', 'tonejs', 'javascript',
    'generativ', 'generative', 'algorithm', 'algorithmus', 'algorithmisch',
    'programmiert', 'programmed', 'coded', 'live coding', 'creative coding',
  ],
  // Empty, and that is the whole point: text is the one medium this platform
  // does NOT infer. Every other medium is read out of the idea; asking for a
  // reading is a decision about how to look, and a decision cannot be guessed
  // from the words that are to be looked at. Both loops below iterate this
  // list, so an empty one can never light the glyph and never win `primary`.
  text: [],
}

/**
 * Scene words: movement and stage vocabulary that names what HAPPENS in the
 * material, not what the material IS. Every one of them was an ordinary
 * catchword until 2026-10-16 (UCD-260), and that is how »video statt bild ohne
 * Anlass« happened: »Kinder laufen über eine Wiese, gemalt als Aquarell« had
 * exactly one hit — 'laufen' — and became video. They still light the glyph
 * (they are a hint), but they no longer outweigh a medium word: a Gemälde full
 * of running, dancing children stays a picture. Only a text with no medium word
 * anywhere falls to them (»die Kinder tanzen im Regen«), earliest mention
 * first — the old rule, on the smaller stage that remains.
 */
const SCENE: Record<MediumId, string[]> = {
  image: [
    // 'still' alone is an adjective (»ein stiller See«); it stays for the alt
    // spelling »Stilleben«, which the medium word 'stillleben' misses.
    'still',
    // A landscape names a subject, not a sheet: »Video einer Landschaft« stays
    // a video. Alone, it is the most ordinary picture request there is.
    'landschaft',
  ],
  video: [
    'bewegt', 'bewegte', 'bewegung', 'fliegt', 'fliegen', 'läuft', 'laufen',
    'tanz', 'tanzt', 'fährt', 'strömt', 'stroemt', 'szene',
    'moving', 'motion', 'flying', 'running', 'flowing',
  ],
  sound: [],
  '3d': [],
  code: [],
  text: [],
}

const DEFAULT_MEDIUM: MediumId = 'image'

/**
 * The catchwords that also count at the END of a word. German puts the medium
 * last in a compound ("Rockmusik", "Trickfilm", "Kinderlied", "Ölgemälde"),
 * and a catchword has to begin a word everywhere else (`wordAt`). A word
 * stands here when the compounds it closes name its medium far more often
 * than not, with its plural, because a plural does not end in its singular.
 * Left out on purpose, each for the words it closes: 'ton' ("Karton",
 * "Beton"), 'töne' ("Farbtöne"), 'klang' ("Einklang"), 'bewegung'
 * ("Kunstbewegung"), 'szene' ("Straßenszene"), 'tanz' ("Distanz"),
 * 'motion' ("emotion"). Taken with its trap:
 * 'lied' also closes "Mitglied". 'zeichnung' closes since 2026-10-16, when the
 * drawing compounds it opens were read as their other words instead
 * (»Bleistiftzeichnung eines Hundes, der läuft« became video, UCD-260); its own
 * trap — »Bezeichnung« — is handled by HEAD_NOT_BEFORE below.
 */
const HEADS: Record<MediumId, string[]> = {
  image: [
    'bild', 'bilder', 'gemälde', 'gemaelde', 'foto', 'fotos', 'fotografie', 'fotografien',
    'porträt', 'porträts', 'portrait', 'portraits', 'poster', 'plakat', 'plakate',
    'malerei', 'collage', 'collagen', 'illustration', 'illustrationen',
    'zeichnung', 'zeichnungen',
  ],
  video: ['video', 'videos', 'film', 'filme', 'animation', 'animationen', 'clip', 'clips'],
  sound: [
    'musik', 'lied', 'lieder', 'melodie', 'melodien', 'geräusch', 'geräusche',
    'geraeusch', 'geraeusche', 'hoerspiel', 'song', 'songs',
  ],
  '3d': [
    'skulptur', 'skulpturen', 'statue', 'statuen', 'büste', 'büsten', 'bueste', 'buesten',
    'relief', 'reliefs',
  ],
  code: [],
  text: [],
}

/**
 * A head that closes words which are not its medium. »Bezeichnung« ends in
 * 'zeichnung' and names no picture, so the letters standing directly in front
 * are checked against this table and such a close does not count. The letters
 * are few on purpose: compounds keep working, because what stands before
 * »Bleistiftzeichnung« is 'ft', not 'be'.
 */
const HEAD_NOT_BEFORE: Record<string, string[]> = {
  zeichnung: ['be'],
  zeichnungen: ['be'],
}

/** A letter or a digit, in any script: what a catchword may not follow. */
const WORD_CHAR = /[\p{L}\p{N}]/u

/**
 * Where `w` first stands in `t` at the start of a word, or -1; with `atEnd`,
 * also where it closes a word.
 *
 * Until 2026-09-27 this was a substring search, so a word only had to CONTAIN
 * a catchword: in a Prompt Interception text describing gouache and ink "auf
 * festem Karton", 'ton' in "Karton" stood before 'bild' in "Bildzentrum", and
 * the flow generated ninety seconds of audio. "Beton", "stone", "cotton",
 * "Farbtöne", "Einklang" and "emotion" fell into the same trap. A catchword
 * now has to begin a word: the start of the text or any character that is
 * neither a letter nor a digit stands before it. What follows it is left
 * free, which keeps the inflection ("tanzende", "fliegender", "bewegtes") and
 * the rest of a compound it opens ("Musikstück", "Tonaufnahme"). A compound
 * that ends in its medium counts through HEADS. What is still lost: a
 * compound whose last word is not in HEADS.
 */
function wordAt(t: string, w: string, atEnd: boolean): number {
  for (let p = t.indexOf(w); p >= 0; p = t.indexOf(w, p + 1)) {
    const opens = !WORD_CHAR.test(t.charAt(p - 1))
    const closes = !WORD_CHAR.test(t.charAt(p + w.length))
    if (opens || (atEnd && closes)) {
      const notBefore = HEAD_NOT_BEFORE[w]
      if (!opens && notBefore?.some((b) => t.startsWith(b, p - b.length))) continue
      return p
    }
  }
  return -1
}

/** Everything this tier sees of one medium in the text. */
interface Reading {
  /** Earliest position of any hit, or -1. */
  first: number
  /** Distinct medium words found (CATCHWORDS and HEADS count a word once). */
  strong: number
  /** Distinct scene words found. */
  scene: number
}

/** Where and how often `m` is named in `t`. */
function read(t: string, m: MediumId): Reading {
  const r: Reading = { first: -1, strong: 0, scene: 0 }
  const take = (p: number, scene: boolean) => {
    if (p < 0) return
    if (scene) r.scene++
    else r.strong++
    if (r.first < 0 || p < r.first) r.first = p
  }
  // A word standing in both tables (CATCHWORDS 'gemälde', HEADS 'gemälde') is
  // one word: counted once, read with the wider of its two rules.
  const strong = new Set(CATCHWORDS[m])
  for (const w of HEADS[m]) strong.add(w)
  for (const w of strong) take(wordAt(t, w, HEADS[m].includes(w)), false)
  for (const w of SCENE[m]) take(wordAt(t, w, false), true)
  return r
}

export function useMediumInference(text: Ref<string>) {
  /** all media whose catchwords appear — several can light up at once */
  const media = computed<Set<MediumId>>(() => {
    const t = text.value.toLowerCase()
    const hits = new Set<MediumId>()
    if (!t.trim()) return hits
    for (const m of MEDIA) {
      if (read(t, m).first >= 0) hits.add(m)
    }
    return hits
  })

  /**
   * primary = the medium the text names most, else the default (honest "I'd
   * guess image"). One medium word outweighs any number of scene words; among
   * media naming equally many medium words the earliest mention wins — the old
   * rule, which until 2026-10-16 ran everything and now only breaks ties; and
   * scene words carry a reading only where no medium word stands at all.
   */
  const primary = computed<MediumId>(() => {
    const t = text.value.toLowerCase()
    let best: MediumId | null = null
    let bestStrong = 0
    let bestPos = Infinity
    let bestScene = 0
    for (const m of MEDIA) {
      const r = read(t, m)
      if (r.strong === 0 && r.scene === 0) continue
      if (
        r.strong > bestStrong ||
        (r.strong === bestStrong && r.first < bestPos) ||
        (r.strong === bestStrong && r.first === bestPos && r.scene > bestScene)
      ) {
        best = m
        bestStrong = r.strong
        bestPos = r.first
        bestScene = r.scene
      }
    }
    return best ?? DEFAULT_MEDIUM
  })

  return { media, primary }
}
