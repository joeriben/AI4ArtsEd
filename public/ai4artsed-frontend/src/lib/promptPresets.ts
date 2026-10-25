/**
 * The prompts every instrument offers ready-made, in ONE place.
 *
 * Five surfaces each carried their own single example and their own i18n key
 * for it — Encoder Fusion, Decomposition, Denoising Archaeology, AI Model
 * Comparison and Attention Cartography — four of them the same sentence written
 * out four times, and the fifth the standard test prompt that the other four did
 * not offer. They are built centrally here as one preset prompt source.
 *
 * The strings live under `promptExamples.presets` in the i18n files, beside the
 * `promptExamples.label` those five already shared. They are PROMPTS, not copy:
 * a label or prose pass never touches them, in any language.
 *
 * An instrument whose example only makes sense on that instrument keeps its own
 * list — the pair of houses of Concept Algebra, the three fields of Composable
 * Diffusion, the sentences of Voices. This is the general offer, not all of them.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

/** The order the list shows them in. */
// The three stock presets (composition/length, scarcity, under-specification)
// grew by ten entries, selected after the property catalogue of UCD-118:
// model idiosyncrasy (`walk`), WAS/HOW roles (`forest`),
// abstract concepts as cliché (`friendship`, `loneliness`), under-specification
// and geographical defaults (`meal`, `city`), stereotype reinforcement by
// profession (`nurse`, `plumber`), and two border experiments that invite
// failure rather than a result (`festival`, `shortcut`). Each entry's comment
// in en.ts names the property and the surface that can evaluate it; comparison
// pairs stay with the surfaces that hold the seed.
export const PROMPT_PRESETS = [
  'house',
  'street',
  'person',
  'walk',
  'forest',
  'friendship',
  'loneliness',
  'meal',
  'city',
  'nurse',
  'plumber',
  'festival',
  'shortcut',
] as const

export type PromptPresetId = (typeof PROMPT_PRESETS)[number]

/** Where the sentences stand in the i18n files: the key that carries their ids. */
export const PROMPT_PRESET_KEY = 'promptExamples.presets'

export interface PromptPreset {
  id: string
  label: string
  fill: string[]
}

/**
 * The ready-made prompts for a field, in the reader's language.
 *
 * One field per entry — every consumer so far writes the chosen prompt into a
 * single box. An instrument with two fields passes its own list.
 *
 * `ids` narrows the offer to some of the presets, in the order given, for an
 * instrument that shows one line or two of them. Such an instrument reads them
 * here and carries no key of its own for the same sentence: the keys six
 * surfaces had for it left with the move here, and each of them showed
 * the key where the sentence belonged until they were pointed here.
 */
export function usePromptPresets(ids: readonly PromptPresetId[] = PROMPT_PRESETS) {
  const { t } = useI18n()
  return computed<PromptPreset[]>(() =>
    ids.map(id => {
      const text = t(`${PROMPT_PRESET_KEY}.${id}`)
      return { id, label: text, fill: [text] }
    }),
  )
}
