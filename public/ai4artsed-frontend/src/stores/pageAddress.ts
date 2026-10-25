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
 * The other eight are cut from the authored annotations of the pages: the
 * column "worum es geht" is the story, the two learning columns are drawn
 * together into the purpose. Cut at whole sentences and clauses; German is the
 * authored side and English is set after it, because the annotations were
 * written in German.
 *
 * Of the 37 places, eleven carry annotations. Missing here are the
 * four pages whose columns are still empty (start page, Direct, x2x Legacy, the
 * educator area), Text-Transformation and the two image transformations —
 * annotated, but their views are being taken off the platform — and the 14
 * Latent Lab instruments that carry no annotation. Those fourteen are reachable
 * now — they have routes of their own — and empty, which is a different thing
 * from unreachable: help says so on them. Every instrument gets an address of
 * its own; an instrument whose text is not yet written has no entry here.
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
  // procedures are and where the twenty-two instruments reach into them. The
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
  // The first of the four comparisons adapted to its own instrument. The
  // shared text names all four comparisons in one sentence, so three quarters
  // of it was about somewhere else; a shared text is not adapted to any one
  // instrument. The closing note stays on all four.
  '/latent-lab/model-comparison': {
    storyKey: 'compare.address.model.story',
    purposeKey: 'compare.address.model.purpose',
    noteKey: 'compare.ask.note',
  },
  // Its first half says the setup before the handling — the same description
  // of a picture in every column, only the language differs. Its second names
  // the matter of fact and no concrete example: the translation holds, the
  // text encoders are trained on English, and what is left is the cliché.
  '/latent-lab/language-understanding': {
    storyKey: 'compare.address.language.story',
    purposeKey: 'compare.address.language.purpose',
    noteKey: 'compare.ask.note',
  },
  // The second of the four adapted to its own instrument. Its first half is
  // the handling in the order a visitor meets it; its second says what the
  // readings are FOR: they are the matter of study themselves. The sentence
  // that says so stays, because a surface that has models read pictures
  // invites exactly the opposite reading, and that reading is a
  // misunderstanding of the platform. It keeps the closing note like the other
  // comparisons.
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
  // The first of the fourteen instruments to get its own address, cut at a
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
  // The third, cut where the surface itself is cut: the first half is what
  // happens to the line that is written, the second what the first column and
  // the further columns each show. Its keys live in the instrument's own block
  // (`latentLab.census`) because that block exists and holds every other word
  // this instrument says. It carries the closing note, like the three
  // comparisons: it is the one instrument outside Compare where the
  // interpretation help belongs.
  '/latent-lab/cultural-un-known': {
    storyKey: 'latentLab.census.story',
    purposeKey: 'latentLab.census.purpose',
    noteKey: 'compare.ask.note',
  },
  // The first instrument of Prompt Interception. Its keys live in its own
  // block, like the census's; it carries the same closing note as the
  // comparisons, because it is read the same way — several results side by
  // side, and the reading is the work.
  // Draft text, to be rewritten after the first real run.
  // The address changed with the instrument's name
  // (llm-cultural-understanding -> interception-across-models). The old one
  // still routes (`views/latent_lab.vue`), and a page reached under it stands
  // here without an Ansprache; the rail rewrites the URL to the new one.
  '/latent-lab/interception-across-models': {
    storyKey: 'latentLab.interception.models.story',
    purposeKey: 'latentLab.interception.models.purpose',
    noteKey: 'compare.ask.note',
  },
  // The second instrument of Prompt Interception, and the reverse of the
  // first: there one perspective and several writing models, here one
  // template and several perspectives. Same closing note, for the same reason.
  // Draft text, to be rewritten after the first real run.
  '/latent-lab/perspectives-on-a-template': {
    storyKey: 'latentLab.interception.template.story',
    purposeKey: 'latentLab.interception.template.purpose',
    noteKey: 'compare.ask.note',
  },
  // The third instrument of Prompt Interception. It asks what an aesthetic
  // checklist does to a template: one handle per property, one setting per
  // run, and a row for each of them under the template as it was written.
  // Same closing note, for the same reason.
  // Draft text, to be rewritten after the first real run.
  '/latent-lab/aesthetic-poles': {
    storyKey: 'latentLab.interception.poles.story',
    purposeKey: 'latentLab.interception.poles.purpose',
    noteKey: 'compare.ask.note',
  },
  // The fourth. Its first half is the handling in the order a visitor meets
  // it, its second the reading — that a word's influence lands in areas,
  // softly and often elsewhere than expected. No closing note here: the
  // interpretation help belongs to the comparisons and to Cultural (Un)Known,
  // and this instrument reads one picture rather than several.
  '/latent-lab/attention-cartography': {
    storyKey: 'latentLab.attention.story',
    purposeKey: 'latentLab.attention.purpose',
  },
  // LoRA Explorer (its keys keep the earlier working name LoRA Reach). Its
  // first half is what a run puts on the surface, its second how the four rows
  // are read against one another. No closing note: the interpretation help
  // belongs to the comparisons and to Cultural (Un)Known, and this instrument
  // compares one adapter with itself.
  '/latent-lab/lora-explorer': {
    storyKey: 'latentLab.loraReach.story',
    purposeKey: 'latentLab.loraReach.purpose',
  },
  // Mean Images. The two halves are the story and purpose the instrument
  // carries in its own block (`latentLab.meanImages`): the first says what a
  // run computes and shows, the second Steyerl's method and what the
  // comparison across models serves. No closing note: the interpretation help
  // belongs to the comparisons and to Cultural (Un)Known.
  '/latent-lab/mean-images': {
    storyKey: 'latentLab.meanImages.story',
    purposeKey: 'latentLab.meanImages.purpose',
  },
  // The fifth. Its second half rests on what a run actually looks like rather
  // than on the section names: the view stays noise well past the
  // middle, and the scene arrives within a few steps. Where that turn falls
  // moves with prompt, backbone and shift, so the address sends the visitor to
  // look for it instead of naming a step number.
  '/latent-lab/denoising-archaeology': {
    storyKey: 'latentLab.archaeology.story',
    purposeKey: 'latentLab.archaeology.purpose',
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
