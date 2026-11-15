<!--
  SCENE STRIP — what stands on the document card: the summary of a PDF.

  WHAT THIS IS
    The board face of the flow's document summary. A PDF the group brought in
    was condensed the way the knowledge library condenses a document, and the
    card shows the result: the profile, the sections and the glossary. A run
    reads the profile (`documentText` in useSceneIntake.ts); a section goes on as
    a text card of its own through the carry event.

  WHAT IT IS NOT
    It stores nothing and decides nothing. Parts the check withheld appear as a
    COUNT, never as content. The card shell (background, bar, grip, corner,
    close) is FlowCard's, owned by the view; this is what stands inside it.

  THE STRIP
    The sections lie side by side under the profile, the glossary after them;
    the one under the hand stands out and carries its text in full.
-->
<template>
  <div class="scene-strip">
    <div class="ss-head">
      <span class="ss-kind">{{ t('resonaScene.kind') }}</span>
      <span class="ss-title">{{ doc.title }}</span>
      <span v-if="status" class="ss-status" role="status">{{ status }}</span>
    </div>

    <p v-if="doc.profile" class="ss-profile">{{ doc.profile }}</p>

    <div
      v-if="doc.sections.length || doc.glossary.length"
      class="ss-strip"
      role="listbox"
      :aria-label="t('resonaScene.stripLabel')"
    >
      <button
        v-for="(s, i) in doc.sections"
        :key="i"
        type="button"
        class="ss-cell"
        :class="{ on: active === i }"
        role="option"
        :aria-selected="active === i"
        :title="s.heading"
        @click="toggle(i)"
      >
        <span class="ss-cell-n">{{ i + 1 }}</span>
        <span class="ss-cell-scene">{{ s.heading }}</span>
      </button>
      <button
        v-if="doc.glossary.length"
        type="button"
        class="ss-cell"
        :class="{ on: active === GLOSSARY }"
        role="option"
        :aria-selected="active === GLOSSARY"
        @click="toggle(GLOSSARY)"
      >
        <span class="ss-cell-scene">{{ t('resonaScene.glossary') }}</span>
      </button>
    </div>

    <div v-if="activeSection" class="ss-detail">
      <p class="ss-scene">{{ activeSection.body }}</p>
      <button type="button" class="ss-carry" @click="$emit('carry', activeSection.body)">
        {{ t('resonaScene.carry') }}
      </button>
    </div>
    <dl v-else-if="active === GLOSSARY" class="ss-detail ss-glossary">
      <template v-for="g in doc.glossary" :key="g.term">
        <dt>{{ g.term }}</dt>
        <dd>{{ g.definition }}</dd>
      </template>
    </dl>

    <p v-if="doc.withheld > 0" class="ss-count">{{ t('resonaScene.withheldCount', { n: doc.withheld }, doc.withheld) }}</p>

    <div class="ss-meta">
      <span v-if="analyzedDate">{{ t('resonaScene.analyzed', { date: analyzedDate }) }}</span>
      <span v-if="doc.meta.analysisModel">{{ doc.meta.analysisModel }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { SceneDocument } from '@/composables/useSceneIntake'

/** `status`: how far the summary behind the card is, while it runs (the view says it). */
const props = defineProps<{ doc: SceneDocument; status?: string }>()
defineEmits<{ carry: [text: string] }>()

const { t, locale } = useI18n()
/** The glossary's place among the cells, which the sections number from 0. */
const GLOSSARY = -1
/** Which cell stands out — none until one is driven at. */
const active = ref<number | null>(null)
const activeSection = computed(() => (active.value === null ? null : props.doc.sections[active.value] ?? null))
function toggle(cell: number) {
  active.value = active.value === cell ? null : cell
}
/** The day of the analysis in the reader's own form; the wire carries an ISO stamp. */
const analyzedDate = computed(() => {
  const at = props.doc.meta.analyzedAt
  const date = at ? new Date(at) : null
  return date && !Number.isNaN(date.getTime()) ? date.toLocaleDateString(String(locale.value)) : ''
})
</script>

<style scoped>
.scene-strip {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.6rem 0.7rem;
  /* At least the card, and taller with the text: the card's body scrolls. A
     fixed height squeezed the row of sections to nothing under a long profile. */
  min-height: 100%;
  box-sizing: border-box;
  color: rgba(230, 230, 230, 0.95);
  font-size: var(--flow-fs-hint);
}
.ss-head { display: flex; flex-direction: column; gap: 0.1rem; }
.ss-kind {
  font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: rgba(230, 230, 230, 0.45);
}
.ss-title { font-size: 0.85rem; font-weight: 300; overflow-wrap: anywhere; }
.ss-status { font-size: 0.75rem; color: rgba(230, 230, 230, 0.85); }
.ss-profile { margin: 0; font-size: 0.78rem; line-height: 1.45; font-weight: 300; }

/* The strip: the sections side by side, the one under the hand standing out.
   It scrolls when a document carries many sections; the card shell above it
   decides the outer scroll, this row only its own. */
.ss-strip {
  display: flex; gap: 0.3rem;
  overflow-x: auto; padding-bottom: 0.15rem;
  scrollbar-width: thin;
}
.ss-cell {
  flex: 0 0 auto; width: 7.2rem; min-height: 3.4rem;
  display: flex; flex-direction: column; align-items: flex-start; gap: 0.2rem;
  padding: 0.35rem 0.45rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: rgba(230, 230, 230, 0.75);
  text-align: left; cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease;
}
.ss-cell:hover { border-color: rgba(62, 207, 142, 0.55); color: rgba(230, 230, 230, 0.95); }
.ss-cell.on { border-color: #3ecf8e; color: #e9e6fb; background: rgba(62, 207, 142, 0.08); }
.ss-cell-n { font-size: 0.6rem; color: rgba(230, 230, 230, 0.4); }
.ss-cell-scene {
  font-size: 0.66rem; line-height: 1.3; font-weight: 300;
  display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2;
  overflow: hidden;
}

/* The driven-at section in full and the way it goes on, or the glossary. */
.ss-detail {
  display: flex; flex-direction: column; gap: 0.35rem;
  padding: 0.45rem 0.55rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(62, 207, 142, 0.35);
  border-radius: 8px;
}
.ss-scene { margin: 0; font-size: 0.78rem; line-height: 1.45; font-weight: 300; white-space: pre-line; }
.ss-glossary { margin: 0; }
.ss-glossary dt { font-size: 0.72rem; color: rgba(230, 230, 230, 0.9); }
.ss-glossary dd { margin: 0; font-size: 0.72rem; line-height: 1.4; font-weight: 300; color: rgba(230, 230, 230, 0.7); }
.ss-carry {
  align-self: flex-start;
  padding: 0.2rem 0.6rem;
  background: transparent; border: 1px solid rgba(62, 207, 142, 0.5); border-radius: 8px;
  color: #3ecf8e; font-size: 0.66rem; cursor: pointer;
}
.ss-carry:hover { background: rgba(62, 207, 142, 0.12); color: #5fe0a6; }

/* The count of what the check withheld — a number, never contents. */
.ss-count { margin: 0; font-size: 0.66rem; color: rgba(230, 190, 120, 0.8); }
.ss-meta {
  display: flex; gap: 0.6rem; flex-wrap: wrap; margin-top: auto;
  font-size: 0.6rem; color: rgba(230, 230, 230, 0.35);
}
</style>
