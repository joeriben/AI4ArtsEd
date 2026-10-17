/**
 * The frames a reading of a PICTURE can be held in: the five the platform has,
 * in the order the flow board offers them — the first is the one a reading takes
 * unasked there.
 *
 * The ids are the backend's own keys (`config.py`, `IMAGE_ANALYSIS_PROMPTS`, one
 * prompt per frame in German and English) and stay exactly as they are there;
 * they are handed to the analysis routes as `frame` and are NOT output configs —
 * they never reach Stage 4. What they are called on screen is
 * `compare.vlmAnalysis.perspectives.<id>`, and that is the surfaces' business.
 *
 * Gathered here on 2026-09-04, when the second instrument of Prompt Interception
 * needed the same five: the list stood twice, in `views/x2x_flow.vue` and in
 * `views/compare/vlm_analysis_comparison.vue` (Rule 13). Image Understanding
 * offers them in an order of its own and adds a sixth of its own making
 * ("neutral", whose wording lives on that page rather than in the backend); both
 * stay there, and what came here is the set.
 */
export const READING_FRAMES = [
  'bildungstheoretisch',
  'bildwissenschaftlich',
  'ethisch',
  'kritisch',
  'descriptive',
] as const

export type ReadingFrame = (typeof READING_FRAMES)[number]

/** Whether an id names a frame rather than an output config. */
export function isReadingFrame(id: string): id is ReadingFrame {
  return (READING_FRAMES as readonly string[]).includes(id)
}
