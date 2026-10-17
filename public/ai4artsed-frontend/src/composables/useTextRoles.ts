/**
 * Text-role reading — the first step of canvas intelligence (Phase 2, still no agent).
 *
 * Phase 1 asked only *how many* texts and images lie on the board. It could not
 * ask what a text IS. But two texts can stand in a relation the material itself
 * declares: one is a song's words, the other describes how it should sound. That
 * constellation has exactly one pipeline on this platform — heartmula_standard
 * (dual_text_media_generation, requires_dual_input), whose chunk reads
 * lyrics (TEXT_1) and tags (TEXT_2).
 *
 * The reading is deliberately conservative and deterministic, in the same spirit
 * as the medium catchwords: it fires only when BOTH roles are unambiguous and
 * they disagree about which text is which. Anything less returns null, and the
 * board falls back to the ordinary sound route (Stable Audio 3). A false
 * positive here would silently turn a poem into a song, so the bar is high.
 */

/** Section markers are the strongest evidence a text is meant to be sung. */
const SECTION_RE = /\[(verse|chorus|bridge|intro|outro|hook|refrain|strophe|pre-chorus)\b[^\]]*\]/i

/**
 * Words that describe music rather than say something. Genre, mood, instrument,
 * tempo — the four axes HeartMuLa's tag input expects.
 */
const STYLE_WORDS = new Set([
  // genre
  'pop', 'rock', 'jazz', 'classical', 'electronic', 'hip-hop', 'hiphop', 'rap', 'r&b', 'soul',
  'funk', 'blues', 'country', 'folk', 'metal', 'punk', 'indie', 'reggae', 'latin', 'salsa',
  'tango', 'samba', 'bossa nova', 'flamenco', 'gospel', 'afrobeat', 'highlife', 'cumbia',
  'fado', 'qawwali', 'k-pop', 'bollywood', 'house', 'techno', 'trance', 'dubstep',
  'drum and bass', 'synthwave', 'lo-fi', 'lofi', 'trap', 'ambient', 'dance', 'chanson',
  'schlager', 'volksmusik', 'orchestral', 'cinematic', 'chiptune',
  // mood
  'dark', 'happy', 'sad', 'melancholic', 'melancholy', 'dreamy', 'aggressive', 'calm',
  'energetic', 'uplifting', 'haunting', 'nostalgic', 'epic', 'playful', 'somber', 'warm',
  'traurig', 'fröhlich', 'düster', 'ruhig', 'melancholisch', 'verträumt',
  // instrument
  'piano', 'guitar', 'acoustic guitar', 'electric guitar', 'violin', 'cello', 'strings',
  'drums', 'bass', 'synth', 'synthesizer', 'saxophone', 'trumpet', 'flute', 'harp', 'organ',
  'choir', 'vocals', 'female vocals', 'male vocals', 'a cappella', 'accordion', 'sitar',
  'klavier', 'gitarre', 'geige', 'schlagzeug', 'streicher', 'chor',
  // tempo / production
  'slow', 'fast', 'mid-tempo', 'midtempo', 'upbeat', 'downtempo', 'bpm', 'instrumental',
  'minimal', 'reverb', 'distorted', 'acoustic', 'live', 'langsam', 'schnell',
])

export interface MusicRoles {
  /** TEXT_1 — the words to be sung. */
  lyrics: string
  /** TEXT_2 — comma-separated tags describing the sound. */
  style: string
}

function nonEmptyLines(t: string): number {
  return t.split('\n').filter((l) => l.trim()).length
}

/** How much a text behaves like a song's words. */
function lyricsScore(t: string): number {
  let s = 0
  if (SECTION_RE.test(t)) s += 4
  const lines = nonEmptyLines(t)
  if (lines >= 3) s += 1
  if (lines >= 6) s += 1
  if (t.length > 120) s += 1
  return s
}

/** How much a text behaves like a description of a sound. */
function styleScore(t: string): number {
  const parts = t
    .split(',')
    .map((x) => x.trim().toLowerCase())
    .filter(Boolean)
  let s = 0
  if (parts.length >= 2) s += 2
  if (t.length <= 140) s += 1
  if (!/[.!?]/.test(t)) s += 1
  const hits = parts.filter((p) => STYLE_WORDS.has(p)).length
  if (hits >= 1) s += 2
  if (hits >= 2) s += 1
  // Evidence against: sung structure, or the length of an actual text.
  if (SECTION_RE.test(t)) s -= 4
  if (nonEmptyLines(t) > 2) s -= 2
  return s
}

/**
 * Read exactly two texts as lyrics + style, or return null.
 *
 * Requires: two non-empty texts, each role clearly met, and the two texts
 * disagreeing about which of them is which. Three texts on the board are not a
 * song — they are material, and the ordinary route handles them.
 */
export function classifyMusicRoles(texts: string[]): MusicRoles | null {
  const t = texts.map((x) => (x || '').trim()).filter(Boolean)
  if (t.length !== 2) return null

  const [a, b] = t as [string, string]
  const la = lyricsScore(a)
  const lb = lyricsScore(b)
  const sa = styleScore(a)
  const sb = styleScore(b)

  // Orientation must be unambiguous: one text is more lyrics than the other,
  // and the other is more style than the first.
  const aIsLyrics = la > lb && sb > sa
  const bIsLyrics = lb > la && sa > sb
  if (!aIsLyrics && !bIsLyrics) return null

  const lyrics = aIsLyrics ? a : b
  const style = aIsLyrics ? b : a
  // A section marker (4), or a real body of lines: >=6 lines and >120 chars (3).
  // A three-line note or a single prose sentence never clears this.
  const lyricsOk = (aIsLyrics ? la : lb) >= 3
  // The real guard against false positives: comma-separated, short, no sentence
  // punctuation, and at least one word that names a genre, mood or instrument.
  const styleOk = (aIsLyrics ? sb : sa) >= 5

  return lyricsOk && styleOk ? { lyrics, style } : null
}
