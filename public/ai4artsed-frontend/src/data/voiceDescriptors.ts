/**
 * The words the three rows of buttons put into the description, in English.
 *
 * VoxCPM2 has no parameter for any property of a voice — no gender, no age, no
 * feeling. What it has is the description inside the utterance, so every one of
 * these is a piece of language and nothing else. The labels are translated in
 * `en.ts`; these phrases are not, because they go to the model, and the model
 * was given English.
 *
 * **Each button owns exactly one phrase.** Pressing it puts that phrase into
 * the field, pressing it again takes that phrase out, and neither touches a
 * single other character — including anything typed by hand. Which is why a
 * button needs no state of its own: it is lit when its phrase is in the field.
 * Any number can be lit at once, and the combinations that read oddly are part
 * of what there is to hear.
 *
 * They are all built the same way, "a … voice", so that any two of them can
 * stand next to each other without one swallowing the other.
 */

export interface VoiceDescriptor {
  /** Stable id. The label for it lives in `en.ts`. */
  id: string
  /** The phrase this button adds to the description, and removes again. */
  en: string
}

/** The seven that come from EmoDB, as against the five that do not. */
export const EMODB_EMOTIONS = new Set([
  'neutral', 'angry', 'happy', 'sad', 'anxious', 'bored', 'disgusted',
])

export const GENDERS: VoiceDescriptor[] = [
  { id: 'female', en: 'a female voice' },
  { id: 'male', en: 'a male voice' },
  { id: 'neutral', en: 'a gender-neutral voice' },
]

export const AGES: VoiceDescriptor[] = [
  { id: 'child', en: "a child's voice" },
  { id: 'young', en: 'a young voice' },
  { id: 'middle', en: 'a middle-aged voice' },
  { id: 'old', en: 'an old voice' },
]

/**
 * The seven of EmoDB (TU Berlin, Interspeech 2005) first, because the test
 * sentences on this page are built to that corpus and the two belong together.
 * Then five more, four of which are the words the voice catalogue of
 * 2026-08-08 uses for the Supertonic presets - so the same thing can be asked
 * for here in words that is available one column over as a vector.
 */
export const EMOTIONS: VoiceDescriptor[] = [
  { id: 'neutral', en: 'a neutral voice' },
  { id: 'angry', en: 'an angry voice' },
  { id: 'happy', en: 'a happy voice' },
  { id: 'sad', en: 'a sad voice' },
  { id: 'anxious', en: 'an anxious voice' },
  { id: 'bored', en: 'a bored voice' },
  { id: 'disgusted', en: 'a disgusted voice' },
  // From here on not EmoDB: five ways of speaking rather than seven feelings.
  { id: 'calm', en: 'a calm voice' },
  { id: 'friendly', en: 'a friendly voice' },
  { id: 'gentle', en: 'a gentle voice' },
  { id: 'decided', en: 'a decided voice' },
  { id: 'narrating', en: 'a narrating voice' },
]

export const ALL_DESCRIPTORS: VoiceDescriptor[] = [...GENDERS, ...AGES, ...EMOTIONS]

const SEPARATOR = ', '

/** Whether this phrase is currently in the description. */
export function hasPhrase(text: string, phrase: string): boolean {
  return splitPhrases(text).includes(phrase)
}

/** The description broken at the separators, empty pieces dropped. */
function splitPhrases(text: string): string[] {
  return text
    .split(',')
    .map((piece) => piece.trim())
    .filter(Boolean)
}

/** The phrase appended, if it is not already there. Nothing else moves. */
export function addPhrase(text: string, phrase: string): string {
  if (hasPhrase(text, phrase)) return text
  const before = text.trim()
  return before ? `${before}${SEPARATOR}${phrase}` : phrase
}

/** That one phrase taken out. Everything else stays exactly as it was. */
export function removePhrase(text: string, phrase: string): string {
  const kept = splitPhrases(text).filter((piece) => piece !== phrase)
  return kept.join(SEPARATOR)
}
