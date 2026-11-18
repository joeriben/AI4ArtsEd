import { ref } from 'vue'
import { defineStore } from 'pinia'

/**
 * What a page says about itself, before anything has been asked of it.
 *
 * Two halves, always in this order: what happens on this page, and what there
 * is to learn by doing it. Both are i18n KEYS, never text written here — the
 * address is authored, it reaches the surface unchanged, and no model is asked
 * for it, paraphrases it or shortens it on the way.
 *
 * It is never spoken either. The surfaces that put an address up take a text
 * path that has no speech on it at all; a text that greets every page entrance
 * would be unbearable to anybody clicking through the platform, and that is the
 * reason the halves live here as words rather than as an utterance.
 */
export interface PageAddress {
  /** i18n key: what this page is, and what it does with what it is given. */
  storyKey: string
  /** i18n key: what can be learned here, and why that is worth doing. */
  purposeKey: string
  /**
   * i18n key: a closing sentence, said last.
   *
   * On the comparing instruments the address ends by saying that this help is
   * there for the analysis and the comparative interpretation. It stands as a
   * key of its own and not inside the purpose, because five routes share that
   * text and only some of them close this way.
   */
  noteKey?: string
}

/**
 * The addresses, by route path.
 *
 * Only pages that HAVE one stand here. A route that is missing has no address
 * yet, and that must stay silent: no empty block, no placeholder, no heading
 * over nothing. A page with nothing to say about itself says nothing.
 *
 * `/contesting` points at the two halves of the text that used to stand in that
 * page's own dormant screen. They were split apart at the sentence that turns
 * from what happens to what is learned, so that a surface can carry the story
 * without the purpose, or set the two down one after the other.
 *
 * Eight entries were first cut from the authored annotations of the pages: the
 * column "worum es geht" is the story, the two learning columns are drawn
 * together into the purpose. Cut at whole sentences and clauses; German is the
 * authored side and English is set after it, because the annotations were
 * written in German.
 *
 * Thirty-four entries: the four pages Flow, Together, Contesting and Canvas,
 * the lab's own page (`/latent-lab`), and the twenty-nine places of the
 * Latent Lab, the overview and every instrument in `SLUGS` of
 * `views/latent_lab.vue`. Every instrument of the lab has an address of its
 * own. Routes with a view and no entry: the start page, About, Direct, the
 * Surrealizer Flow, Settings, Impressum, Datenschutz, Dokumentation, the
 * usage agreement, login, account, the educator and admin areas, and the
 * test views (Kickin, Kickin per block, animation test, pixel editor). An
 * earlier address of an instrument (`IDS` in `views/latent_lab.vue`) has no
 * entry of its own; the lab rewrites the URL to the current one.
 */
const PAGE_ADDRESSES: Readonly<Record<string, PageAddress>> = {
  '/contesting': { storyKey: 'persona.story', purposeKey: 'persona.purpose' },
  '/together': { storyKey: 'resona.story', purposeKey: 'resona.purpose' },
  '/x2x-flow': {
    storyKey: 'x2xFlow.story',
    purposeKey: 'x2xFlow.purpose',
    // The third half is the handling: what to do with your hands to get a first
    // run out of this surface. It is there because an empty board with a dark
    // start control says nothing about how to fill it.
    noteKey: 'x2xFlow.note',
  },
  // Re-enactment used to be a page of its own and is an instrument of the lab;
  // its address is the one it had as a page, kept at the instrument level.
  '/latent-lab/re-enactment': { storyKey: 'coverBand.story', purposeKey: 'coverBand.purpose' },
  '/canvas': { storyKey: 'canvas.story', purposeKey: 'canvas.purpose' },
  '/latent-lab': { storyKey: 'latentLab.story', purposeKey: 'latentLab.purpose' },
  // The lab's overview is not an instrument: it is the frame, what the three
  // procedures are and where the twenty-eight instruments reach into them. The
  // lab's general address defines the frame and not the concrete contents of
  // an instrument, which is the reason no instrument borrows the lab's text.
  // The overview carries two halves of its own, because the map is a page.
  // German authored, English set after it.
  '/latent-lab/overview': {
    storyKey: 'latentLabOverview.story',
    purposeKey: 'latentLabOverview.purpose',
  },
  // Compare and LoRA Training are categories of the lab. Their addresses are
  // the ones they had as pages, and they are keyed per instrument because that
  // is what the route says — without these rows every one of the seven would
  // fall through to the lab's own address and lose what it says about itself.
  // Model Comparison. First half: the two sets of three, the single choice,
  // the minimum of two and the Commons row with its search term; second half:
  // the differences between the models, an occupation prompt, the Commons row.
  '/latent-lab/model-comparison': {
    storyKey: 'compare.address.model.story',
    purposeKey: 'compare.address.model.purpose',
    noteKey: 'compare.ask.note',
  },
  // Language Understanding. First half: the same prompt in two to four
  // languages, one row per image model, translation and back-translation per
  // column. Second half: the back-translation as the check, reading along a
  // row, and the matter of fact, which stays: the text encoders of SD 3.5 are
  // trained on English, and what is left is the cliché. The delivery of
  // 2026-11-08 had dropped it with this comment; it stands again since
  // 2026-11-15.
  '/latent-lab/language-understanding': {
    storyKey: 'compare.address.language.story',
    purposeKey: 'compare.address.language.purpose',
    noteKey: 'compare.ask.note',
  },
  // Image Understanding. First half: the picture, the six perspectives and
  // the field they fill. Second half: the machine readings are themselves the
  // matter of study, and the sentence that says so stays, because a surface
  // that has models read pictures invites exactly the opposite reading; then
  // why that weighs, since machine image analysis already decides about
  // people. The project lead confirmed both sentences on 2026-11-15, and they
  // stay word for word. After them: what a reading describes, interprets and
  // adds, and what a second perspective changes in it.
  '/latent-lab/image-understanding': {
    storyKey: 'compare.address.vlm-analysis.story',
    purposeKey: 'compare.address.vlm-analysis.purpose',
    noteKey: 'compare.ask.note',
  },
  // The second half rests on what three columns actually return: the
  // invented instruction changes the surface, and the obliging manner —
  // praise, sorted tips, a question back — stands in the EMPTY column too.
  '/latent-lab/system-prompts': {
    storyKey: 'compare.address.systemprompt.story',
    purposeKey: 'compare.address.systemprompt.purpose',
    noteKey: 'compare.ask.note',
  },
  // No closing note here: the interpretation help belongs to the comparisons
  // that are read, and this one is heard.
  '/latent-lab/voices': {
    storyKey: 'compare.address.voice.story',
    purposeKey: 'compare.address.voice.purpose',
  },
  '/latent-lab/lora-sd35': { storyKey: 'training.story', purposeKey: 'training.purpose' },
  // The first instrument of the lab to get its own address, cut at a
  // sentence boundary of the authored text: the first half says what the
  // sentences on this page are, the second what there is to see in them.
  // German is the authored side; English is set after it. The first half opens
  // with the same two sentences as Bias-Archaeology: the two instruments ask a
  // model the same question and the reason for asking it is the same, so a
  // group that meets either of them meets it stated.
  '/latent-lab/coreference-test': { storyKey: 'corefTest.story', purposeKey: 'corefTest.purpose' },
  // The second, cut where the authored text has a paragraph break: why a
  // biased model matters and what can be found out here, then how the
  // questions work and where they come from. The count is written
  // as an upper bound because the category is chosen on the page and the eleven
  // hold between 432 (Sexual orientation) and 7,980 (Race x gender) open
  // questions; a fixed number would be true of one category and wrong of ten.
  '/latent-lab/bias-archaeology': { storyKey: 'biasArchaeology.story', purposeKey: 'biasArchaeology.purpose' },
  // Stereotype Analysis, keys in `latentLab.census`. First half: base prompt,
  // variations, rows, columns, reruns, the studies in the note; second half:
  // the own word, the judgement of whoever knows the place, one model.
  '/latent-lab/cultural-un-known': {
    storyKey: 'latentLab.census.story',
    purposeKey: 'latentLab.census.purpose',
    noteKey: 'compare.ask.note',
  },
  // Language Model Comparison. First half: the step, the writing models and
  // the top row; second half: the texts as the matter of the comparison.
  // Read like the comparisons, so it carries the closing note.
  // The address changed with the instrument's name
  // (llm-cultural-understanding -> interception-across-models). The old one
  // still routes (`views/latent_lab.vue`), and a page reached under it stands
  // here without an Ansprache; the rail rewrites the URL to the new one.
  '/latent-lab/interception-across-models': {
    storyKey: 'latentLab.interception.models.story',
    purposeKey: 'latentLab.interception.models.purpose',
    noteKey: 'compare.ask.note',
  },
  // Interception Scope. First half: one prompt, a picture per perspective,
  // the first picture without the step; second half: a work under several
  // perspectives and the numbers in the note. Closing note as above.
  '/latent-lab/perspectives-on-a-template': {
    storyKey: 'latentLab.interception.template.story',
    purposeKey: 'latentLab.interception.template.purpose',
    noteKey: 'compare.ask.note',
  },
  // Aesthetic Poles. First half: the checklist, the chips and the reference
  // image; second half: where the scales come from and the comparison with
  // the reference image. Closing note as above.
  '/latent-lab/aesthetic-poles': {
    storyKey: 'latentLab.interception.poles.story',
    purposeKey: 'latentLab.interception.poles.purpose',
    noteKey: 'compare.ask.note',
  },
  // Attention Cartography. First half: the run and the settings of the view;
  // second half: what a colour patch is and the layers. No closing note.
  '/latent-lab/attention-cartography': {
    storyKey: 'latentLab.attention.story',
    purposeKey: 'latentLab.attention.purpose',
  },
  // LoRA Explorer (its keys keep the earlier working name LoRA Reach). First
  // half: adapter, word, motifs, four pictures per column; second half: the
  // drift named in the note. No closing note.
  '/latent-lab/lora-explorer': {
    storyKey: 'latentLab.loraReach.story',
    purposeKey: 'latentLab.loraReach.purpose',
  },
  // Mean Images, keys in `latentLab.meanImages`. First half: the two means per
  // model, the views, where the mean is taken; second half: the comparison
  // as an exploration of visual clichés. No closing note.
  '/latent-lab/mean-images': {
    storyKey: 'latentLab.meanImages.story',
    purposeKey: 'latentLab.meanImages.purpose',
  },
  // Denoising Archaeology. First half: the steps of a run and the slider at
  // the picture; second half: denoising and the division by noise level after
  // Choi et al. (2022) as a rough orientation. No closing note.
  '/latent-lab/denoising-archaeology': {
    storyKey: 'latentLab.archaeology.story',
    purposeKey: 'latentLab.archaeology.purpose',
  },
  // Model Comparison of the Transformers Lab. First half: the setup; second
  // half: what a model says or declines. Read like System Prompts: several
  // answers side by side, so it carries the closing note.
  '/latent-lab/system-prompt-across-models': {
    storyKey: 'latentLab.textLab.systempromptModels.story',
    purposeKey: 'latentLab.textLab.systempromptModels.purpose',
    noteKey: 'compare.ask.note',
  },
  // Encoder Fusion. First half: the project lead's opening sentences, then
  // the conditioning table and the factors a, b, c; second half: a row with
  // both encodings and what changes with b. No closing note.
  '/latent-lab/encoder-fusion': {
    storyKey: 'surrealizer.story',
    purposeKey: 'surrealizer.purpose',
  },
  // Dimension Explorer. First half: the two runs and the ranked dimensions;
  // second half: the numbers of an encoder and what a larger range moves.
  '/latent-lab/dimension-explorer': {
    storyKey: 'latentLab.probing.story',
    purposeKey: 'latentLab.probing.purpose',
  },
  // Concept Algebra. First half: A − B + C, the two columns and the scales;
  // second half: the calculation and what the result picture keeps.
  '/latent-lab/concept-algebra': {
    storyKey: 'latentLab.algebra.story',
    purposeKey: 'latentLab.algebra.purpose',
  },
  // Composable Diffusion. First half: concepts with weights, AND and NOT,
  // the place of composition; second half: the composition of the picture.
  '/latent-lab/composable-diffusion': {
    storyKey: 'latentLab.composable.story',
    purposeKey: 'latentLab.composable.purpose',
  },
  // Encoder Fusion Workbench. First half: the grid of a sweep and its preset
  // axes; second half: the moment of the fusion and the weights of a cell.
  '/latent-lab/fusion-workbench': {
    storyKey: 'latentLab.workbench.story',
    purposeKey: 'latentLab.workbench.purpose',
  },
  // Representation Engineering. First half: the three columns and the
  // direction from the contrast pairs; second half: the intervention and
  // the reference column.
  '/latent-lab/representation-engineering': {
    storyKey: 'latentLab.textLab.repeng.story',
    purposeKey: 'latentLab.textLab.repeng.purpose',
  },
  // Tokenizer. First half: the pieces, the counts and the translations;
  // second half: the cost of a language in tokens.
  '/latent-lab/tokenization': {
    storyKey: 'latentLab.textLab.tokens.story',
    purposeKey: 'latentLab.textLab.tokens.purpose',
  },
  // Latent Audio Synth. First half: the two prompts, α and the dimension
  // strip; second half: the numbers of T5Gemma and the semantic axes.
  '/latent-lab/audio-synth': {
    storyKey: 'latentLab.crossmodal.synth.story',
    purposeKey: 'latentLab.crossmodal.synth.purpose',
  },
  // MMAudio. First half: picture, text or both, and the sound; second half:
  // the sound for a still picture and what the model was built for.
  '/latent-lab/mmaudio': {
    storyKey: 'latentLab.crossmodal.mmaudio.story',
    purposeKey: 'latentLab.crossmodal.mmaudio.purpose',
  },
  // ImageBind Guidance. First half: the guided steps, the strength and the
  // cosine on the card; second half: the measure of fit.
  '/latent-lab/imagebind-guidance': {
    storyKey: 'latentLab.crossmodal.guidance.story',
    purposeKey: 'latentLab.crossmodal.guidance.purpose',
  },
}

/**
 * Which pages have already said their address AT THIS MACHINE.
 *
 * Kept per browser and not per account, deliberately. The machines these pages
 * run on in a workshop are shared and almost nobody sitting at one is signed
 * in, so there is no account for the memory to hang on — what this browser has
 * already shown is the only thing there is to remember. The consequence is
 * meant: an address is said once per machine and per page.
 */
const SEEN_STORAGE_KEY = 'ai4artsed_page_address_seen'

function loadSeen(): string[] {
  try {
    const raw = localStorage.getItem(SEEN_STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((entry): entry is string => typeof entry === 'string')
  } catch {
    // Unreadable or unavailable (private mode, cleared storage): every page
    // then owes its address again, which is the harmless direction to fail in.
    return []
  }
}

/**
 * The one place that knows what a page says about itself and whether it has
 * said it here before.
 *
 * Two kinds of surface read this store and they behave differently on purpose.
 * Where a page brings its own agent — the workshop, the contesting surface —
 * the address is put onto the canvas unprompted, as the first thing, because
 * there is no panel to open on those pages. Everywhere else the mask is help,
 * and the address is what help's panel opens with the first time it is opened
 * on that page. After that it is only ever shown on request.
 */
export const usePageAddressStore = defineStore('pageAddress', () => {
  const seen = ref<string[]>(loadSeen())

  /**
   * Pages on which somebody has actually said something to help, this visit.
   *
   * Not stored. What it holds is not a fact about the machine but about the
   * conversation going on right now: the address stops coming up by itself
   * once a page HAS a conversation, and a conversation ends with the tab. A
   * reload is a fresh start and the page introduces itself again, which is the
   * harmless direction to fail in.
   */
  const talked = ref<string[]>([])

  /** What this route says about itself, or null where nothing is written.
   *
   *  Exact match, and nothing else. Every Latent Lab instrument has a route of
   *  its own, and an instrument without an entry is not handed the lab's. The
   *  lab's general address defines the frame, but not the concrete contents of
   *  an instrument. So a place that has no text of its own says that, in help's
   *  own words, instead of borrowing the text of the place above it. */
  function addressFor(path: string): PageAddress | null {
    return PAGE_ADDRESSES[path] ?? null
  }

  function hasSeen(path: string): boolean {
    return seen.value.includes(path)
  }

  /** The address a route still owes this machine — null once it has been seen,
   *  and null on every route that has none. */
  function unseenAddressFor(path: string): PageAddress | null {
    return hasSeen(path) ? null : addressFor(path)
  }

  /** Whether a conversation has been held on this page during this visit. */
  function hasTalked(path: string): boolean {
    return talked.value.includes(path)
  }

  function markTalked(path: string): void {
    if (talked.value.includes(path)) return
    talked.value = [...talked.value, path]
  }

  function markSeen(path: string): void {
    if (seen.value.includes(path)) return
    seen.value = [...seen.value, path]
    try {
      localStorage.setItem(SEEN_STORAGE_KEY, JSON.stringify(seen.value))
    } catch {
      // Storage refused the write: the memory holds for this visit and the
      // address comes up once more next time. Nothing else depends on it.
    }
  }

  return { seen, addressFor, hasSeen, unseenAddressFor, markSeen, hasTalked, markTalked }
})
