/**
 * The image models a raster instrument can put in a row or a column.
 *
 * ONE list, because there were two: Cultural (Un)Known
 * (`views/latent_lab/default_census.vue`) carried it as a literal with the note
 * that it is „deliberately not a second list", taken verbatim from the Model
 * Comparison — and it WAS a second copy of that instrument's two sets, folded
 * into one. When Interception across Models needed the same five for its
 * columns, the third copy was the one docs/ELEMENT_STRUCTURE_REGISTRY.md
 * forbids, so the list stands here and both surfaces read it.
 *
 * What stays with the Model Comparison is its own SHAPE: two named sets („Current
 * Top Models", „SD History") that a visitor switches between, which is a
 * different thing from a flat list of five that are ticked one by one. It is
 * marked in docs/ELEMENT_STRUCTURE_REGISTRY.md as the remaining copy to fold in.
 *
 * Having the generations in the same list as the current models asks the
 * sharper question — if SD 1.5, SDXL and SD 3.5 all do the same thing with the
 * same prompt, that is not one model's quirk.
 *
 * These are OUTPUT CONFIG ids, not model identifiers: which weights an id
 * reaches is the config's business (`devserver/schemas/configs/output/`), and
 * an instrument never names them.
 */
export interface RasterImageModel {
  /** The output config this column or row runs. */
  id: string
  /**
   * What it reads as. The YEAR is not part of these names: it is a fact about
   * the model, and it stands where every model's year stands, on the card
   * beside the field (`useModelRegister`). Carried in the name it
   * was here and nowhere else, and it made three of five names longer than the
   * rest for a reason no reader could see.
   */
  label: string
}

export const RASTER_IMAGE_MODELS: readonly RasterImageModel[] = [
  { id: 'sd15', label: 'SD 1.5' },
  { id: 'sdxl', label: 'SDXL' },
  // Stands directly after SDXL because it IS SDXL's architecture at the same
  // size, trained on Creative-Commons images alone. Side by side, the two ask
  // what the training set does that the architecture does not.
  { id: 'commoncanvas_xl_c', label: 'CommonCanvas XL C' },
  { id: 'sd35_large', label: 'SD 3.5 Large' },
  { id: 'flux2', label: 'Flux 2' },
  // FLUX 3 Image Klein, Black Forest Labs' model of 2026, stands after Flux 2,
  // the same maker's model of 2025, which stays in the list beside it.
  { id: 'flux3', label: 'Flux 3 Klein' },
  // Gemini 3 Pro stands in NO preselection that a press multiplies, because
  // every run of it costs money, and its name carries the € everywhere it can
  // be chosen.
  { id: 'gemini_3_pro_image', label: 'Gemini 3 Pro (€)' },
]

/**
 * The two ready sets a surface offers over its model row: the Stable Diffusion
 * generations one after another, and what is current. The names stand in i18n
 * under `compare.presets`.
 *
 * They live here and not in a view because two surfaces offer them. The Model
 * Comparison still carries its own copy beside its own catalogue, which
 * docs/ELEMENT_STRUCTURE_REGISTRY.md records as the copy to fold in.
 *
 * A surface where ONE press runs a model more than once takes Gemini 3 Pro out
 * of the current set before offering it: it may stand preselected only where a
 * press is one picture per model.
 */
export const RASTER_IMAGE_MODEL_SETS = {
  history: ['sd15', 'sdxl', 'sd35_large'],
  current: ['sd35_large', 'flux2', 'gemini_3_pro_image'],
} as const

/**
 * Where the picture is a CHECK on what something else did, rather than the
 * subject of the comparison. For Interception Scope the model choice is
 * limited to SD 3.5, Flux 2 and Flux 3 Klein.
 */
export const RASTER_IMAGE_MODELS_EFFECT_CHECK: readonly string[] = ['sd35_large', 'flux2', 'flux3']

/** Three that run on this platform's own cards. */
export const RASTER_IMAGE_MODELS_DEFAULT: readonly string[] = ['sdxl', 'sd35_large', 'flux2']

/**
 * Where a surface opens with ONE image model, this is it. The default is
 * SD 3.5, not SDXL, on every surface.
 *
 * Two surfaces read `RASTER_IMAGE_MODELS_DEFAULT[0]` for that and so opened on
 * SDXL — the first of the three by the order they happen to stand in, and
 * nobody's choice. A single default is a decision and stands here as one; the
 * set above stays the set of three that a surface ticks all of.
 */
export const RASTER_IMAGE_MODEL_SINGLE_DEFAULT = 'sd35_large'
