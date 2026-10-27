/**
 * The system prompts a column can be set to, for the two instruments that put
 * one: System Prompts, where each of the three columns carries one of them, and
 * Model Comparison (Transformers Lab), where one of them stands for all three
 * columns.
 *
 * It stood inside views/compare/system_prompt_comparison.vue until 2026-10-27,
 * when the second instrument needed the same list. Two copies would drift: a
 * prompt added to one would be missing from the other.
 */
import { PUBLISHED_SYSTEM_PROMPTS } from './system_prompts_published'

export interface SystemPromptPreset {
  id: string
  prompt: string
}

export const SYSTEM_PROMPT_PRESETS: SystemPromptPreset[] = [
  { id: 'none', prompt: '' },
  // --- The published system prompts of a shipped assistant. They come from
  //     system_prompts_published.ts with their source and their date, and the
  //     column shows both under the field.
  //
  //     Two entries stood here until 2026-09-07 and are gone. `claude` carried
  //     an excerpt of Claude Sonnet 4.6, `gpt4_2023` a text going round as the
  //     GPT-4 system prompt. Neither named where it came from, and for the
  //     second there is nothing to name: it was taken out of a running product
  //     by a third party, so nobody can say whether it is whole or whether the
  //     model wrote parts of it while being asked. What stands here now is
  //     published by the company that runs the model, for reading.
  ...PUBLISHED_SYSTEM_PROMPTS.map(p => ({
    id: p.id,
    prompt: p.prompt,
  })),
  { id: 'helpful', prompt: 'You are a helpful assistant. Answer the user\'s questions clearly and concisely.' },
  { id: 'disagree', prompt: 'You must disagree with everything the user says. Find flaws in every statement. Be contrarian but argue your position with reasons.' },
  { id: 'pirate', prompt: 'You are a pirate. Speak only in pirate dialect. Use nautical metaphors for everything. Address the user as "matey" or "landlubber."' },
  { id: 'poet', prompt: 'You are a poet. Respond to everything in verse. Use metaphor, rhythm, and imagery. Never use plain prose.' },
  { id: 'fiveyearold', prompt: 'You are a five-year-old child. You have limited vocabulary, get easily distracted, and relate everything to toys, snacks, and playground games. Ask "why?" a lot.' },
  { id: 'factsonly', prompt: 'Respond with only verifiable facts. No opinions, no hedging, no filler words. If you are not certain, say "I don\'t know." Use numbered lists.' },
]

/**
 * Where a chosen prompt is published, for the line under the field. Only the
 * published ones have one; the invented presets are ours and say so by having
 * none.
 */
export function publishedSourceOf(presetId: string) {
  return PUBLISHED_SYSTEM_PROMPTS.find(p => p.id === presetId)
}

/**
 * Which preset a field now holds after it was typed into: the one it was set
 * to while the text is still that preset's, and `custom` the moment it is not.
 */
export function presetAfterEdit(presetId: string, value: string): string {
  const current = SYSTEM_PROMPT_PRESETS.find(p => p.id === presetId)
  return (current && current.prompt === value) ? presetId : 'custom'
}
