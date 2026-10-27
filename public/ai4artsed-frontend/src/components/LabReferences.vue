<!--
  LabReferences — the research the instrument rests on, as one collapsed list.

  The references are MANDATORY on the instrument itself. The
  help entry keeps its own copy; it never replaces this one. Four instruments
  had lost theirs to the opposite recommendation (Attention Cartography,
  Denoising Archaeology, Representation Engineering, and the two bias surfaces
  carried theirs only as prose), and three carried this same markup as a
  verbatim copy - a parallel structure either way. Registered in
  docs/ELEMENT_STRUCTURE_REGISTRY.md.

  WHERE IT STANDS: at the foot of the preparing column, directly under the
  `.lab-note`, closed. The note refers in prose ("the sentences come from
  WinoBias"); the title with its DOI stands HERE: the running text in the
  explanation box only refers, and the title with its DOI stands underneath.

  ONLY VALIDATED TITLES. A source whose method the instrument does not actually
  run is removed rather than listed - see feature_probing.vue, whose three
  references failed exactly that check and stay out.

  The bibliography is NOT i18n: authors, titles and venues are the same in every
  language and are passed as `items` from the view. Only the summary is a key.
  A translated edition is a title of its own: where one language's copy quotes
  it, with its pages, the view passes that language its own list
  (views/latent_lab/mean_images.vue).
-->
<template>
  <!-- ONE list, two wrappers. Flat, it is a heading over an open list and sits
       inside whatever holds it; otherwise it is the closed disclosure with the
       count beside its line. The entries are written once either way — a second
       copy of the markup for the second shape would be the parallel structure
       this component was made to end. -->
  <component
    :is="flat ? 'div' : 'details'"
    class="lab-references"
    :class="{ 'is-flat': flat }"
    :open="flat ? undefined : isOpen"
    @toggle="onToggle"
  >
    <component :is="flat ? 'h4' : 'summary'">
      {{ title }}
      <span v-if="!flat" class="ref-count">{{ items.length }}</span>
    </component>
    <ul class="reference-list">
      <li v-for="ref in items" :key="ref.title">
        <span class="ref-authors">{{ ref.authors }}</span>
        <span class="ref-title">{{ ref.title }}</span>
        <span v-if="ref.venue" class="ref-venue">{{ ref.venue }}</span>
        <a
          v-if="ref.doi"
          :href="ref.doi"
          target="_blank"
          rel="noopener"
          class="ref-doi"
        >DOI</a>
        <span v-if="ref.licence" class="ref-licence">{{ ref.licence }}</span>
      </li>
    </ul>
  </component>
</template>

<script setup lang="ts">
import { useDetailsState } from '@/composables/useDetailsState'

/** One entry. `venue` and `doi` are optional - an arXiv preprint has neither. */
export interface LabReference {
  authors: string
  title: string
  venue?: string
  doi?: string
  /** Where a corpus carries an attribution requirement, it is named here. */
  licence?: string
}

const props = defineProps<{
  /** The summary line, from the instrument's own i18n block. */
  title: string
  items: LabReference[]
  /**
   * localStorage key, so a reader who opened it finds it open again. A flat
   * list has nothing to remember and passes none.
   */
  storageKey?: string
  /**
   * No disclosure: heading and list, open, for a place that already IS the
   * container — the `.lab-note` at the foot of the column.
   */
  flat?: boolean
}>()

const { isOpen, onToggle } = useDetailsState(props.storageKey ?? '')
</script>

<style scoped>
/* The values are the platform's, taken from the three surfaces that kept the
   block (concept_algebra, composable_diffusion, crossmodal_lab). The DOI is
   GREEN - the Latent Lab's accent; the blue one in the older text instruments
   was the drift, not the standard. */
.lab-references {
  margin-top: 0.6rem;
}

/* Inside the note box: the heading carries the weight the summary line carried,
   and the list loses the indent that set it off from a clickable line above. */
.lab-references.is-flat {
  margin-top: 0.7rem;
}

.lab-references.is-flat h4 {
  margin: 0;
  font-size: 0.8rem;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.45);
}

.lab-references.is-flat .reference-list {
  margin-top: 0.35rem;
  padding-left: 0;
}

.lab-references summary {
  color: rgba(255, 255, 255, 0.4);
  font-size: 0.8rem;
  cursor: pointer;
  user-select: none;
}

.lab-references summary:hover {
  color: rgba(255, 255, 255, 0.6);
}

.ref-count {
  color: rgba(255, 255, 255, 0.25);
  margin-left: 0.4rem;
}

.reference-list {
  list-style: none;
  margin: 0.6rem 0 0;
  padding: 0 0 0 1.1rem;
  display: grid;
  gap: 0.35rem;
}

.reference-list li {
  font-size: 0.75rem;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.4);
}

.ref-authors { font-weight: 700; margin-right: 0.3rem; }
.ref-title { font-style: italic; margin-right: 0.3rem; }
.ref-venue { margin-right: 0.3rem; }
.ref-doi { color: rgba(76, 175, 80, 0.6); text-decoration: none; }
.ref-doi:hover { color: rgba(76, 175, 80, 0.9); }
.ref-licence { color: rgba(255, 255, 255, 0.28); margin-left: 0.4rem; }
</style>
