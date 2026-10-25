/**
 * The ten voices Supertonic 3 ships, as they were heard and written down.
 *
 * Measured and characterised on 2026-08-08 for the voice catalogue
 * (`tts_katalog_20260808`, `stimmen.html`): the same sentence through each
 * preset, median fundamental frequency with the 10th-to-90th percentile band
 * beside it — the register and how far the voice moves inside it. The wording
 * of each characterisation is that catalogue's, and is not to be re-derived or
 * smoothed; the labels live in `en.ts` so they can be read in the language of
 * the interface.
 *
 * Ordered by their own numbers, F1 to M5. Whoever looks for F3 looks for F3,
 * not for the fifth row - and the measured register travels with each line
 * anyway, so nothing is lost by not sorting on it.
 *
 * **There is no gender-neutral preset.** Five named male, five named female,
 * no third category — which is why the platform's own voice is a mixture and
 * never one of these (see `supertonic_backend.py`). F3 and F5 come closest
 * from above, M1 and M4 from below.
 */

export interface SupertonicPreset {
  /** What the model is asked for. Also shown, small: it is the technical name. */
  id: string
  /** Median f0 in Hz, from the 2026-08-08 catalogue. */
  hz: number
  /** The 10th and 90th percentile of that reading — how far the voice moves. */
  lo: number
  hi: number
}

export const SUPERTONIC_PRESETS: SupertonicPreset[] = [
  { id: 'F1', hz: 194, lo: 160, hi: 260 },
  { id: 'F2', hz: 197, lo: 160, hi: 282 },
  { id: 'F3', hz: 163, lo: 129, hi: 246 },
  { id: 'F4', hz: 194, lo: 183, hi: 239 },
  { id: 'F5', hz: 164, lo: 137, hi: 207 },
  { id: 'M1', hz: 135, lo: 96, hi: 203 },
  { id: 'M2', hz: 97, lo: 74, hi: 175 },
  { id: 'M3', hz: 107, lo: 86, hi: 159 },
  { id: 'M4', hz: 130, lo: 99, hi: 157 },
  { id: 'M5', hz: 89, lo: 74, hi: 132 },
]
