<!--
  SCENE STRIP — the capsule strip of a document the session analysed.

  WHAT THIS IS
    The board face of the scene capsule pipeline (UCD-133 on UCD-132's
    backend): a PDF the group brought in came back as scene capsules, and
    they stand here as a strip over the capsules — the whole document shown
    in scenes, one capsule driven at a time, its prompt carried on in the
    surface's own prompt instrument (the open line — see the handoff in
    resona.vue).

  WHAT IT IS NOT
    It stores nothing and decides nothing. The document space is the
    session's (it dies with the journal); flagged segments and discarded
    capsules appear as COUNTS, never as content — the counts are the whole
    transparency the plan gives them (UCD-124 §3 step 4 / §7.2). The card
    shell — background, bar, grip, corner, close — is FlowCard's, owned by
    the view; this is what stands inside it.

  THE STRIP
    The capsules lie side by side; the one under the hand stands out and
    carries its scene in full. What the anchor names (chapter + in-vivo
    probe) is the capsule's evidence duty made visible: the scene is
    traceable to its chapter without the original ever being kept (the raw
    PDF was discarded at job end, UCD-124 §6 — the anchor is the reference,
    not a copy).
-->
<template>
  <div class="scene-strip">
    <div class="ss-head">
      <span class="ss-kind">{{ t('resonaScene.kind') }}</span>
      <span class="ss-title">{{ doc.title }}</span>
      <span v-if="status" class="ss-status" role="status">{{ status }}</span>
    </div>

    <div class="ss-strip" role="listbox" :aria-label="t('resonaScene.stripLabel')">
      <button
        v-for="(c, i) in doc.capsules"
        :key="i"
        type="button"
        class="ss-cell"
        :class="{ on: active === i }"
        role="option"
        :aria-selected="active === i"
        :title="c.scene"
        @click="active = active === i ? null : i"
      >
        <span class="ss-cell-n">{{ i + 1 }}</span>
        <span class="ss-cell-scene">{{ c.scene }}</span>
      </button>
    </div>

    <div v-if="activeCapsule" class="ss-detail">
      <div class="ss-anchor">
        <span class="ss-anchor-ch">{{ activeCapsule.anchor.chapter }}</span>
        <span class="ss-anchor-probe">{{ activeCapsule.anchor.probe }}</span>
      </div>
      <p class="ss-scene">{{ activeCapsule.scene }}</p>
      <div class="ss-prompt-row">
        <span class="ss-prompt-label">{{ t('resonaScene.promptLabel') }}</span>
        <span class="ss-prompt">{{ activeCapsule.prompt }}</span>
      </div>
      <button type="button" class="ss-carry" @click="$emit('carry', activeCapsule.prompt)">
        {{ t('resonaScene.carry') }}
      </button>
    </div>

    <p v-if="doc.flagged > 0" class="ss-count">{{ t('resonaScene.flaggedCount', { n: doc.flagged }) }}</p>
    <p v-if="doc.discarded > 0" class="ss-count">{{ t('resonaScene.discardedCount', { n: doc.discarded }) }}</p>

    <div class="ss-meta">
      <span v-if="doc.meta.analyzedAt">{{ t('resonaScene.analyzed', { date: doc.meta.analyzedAt }) }}</span>
      <span v-if="doc.meta.analysisModel">{{ doc.meta.analysisModel }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { SceneDocument } from '@/composables/useSceneIntake'

/** `status`: how far the analysis behind the card is, while it runs (the view says it). */
const props = defineProps<{ doc: SceneDocument; status?: string }>()
defineEmits<{ carry: [prompt: string] }>()

const { t } = useI18n()
/** Which capsule stands out — none until one is driven at. */
const active = ref<number | null>(null)
const activeCapsule = computed(() => (active.value === null ? null : props.doc.capsules[active.value] ?? null))
</script>

<style scoped>
.scene-strip {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.6rem 0.7rem;
  height: 100%;
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

/* The strip: the capsules side by side, the one under the hand standing out.
   It scrolls when a document carries many capsules; the card shell above it
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

/* The driven-at capsule: its anchor (evidence duty), its scene in full, the
   prompt it carries, and the way that prompt goes on. */
.ss-detail {
  display: flex; flex-direction: column; gap: 0.35rem;
  padding: 0.45rem 0.55rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(62, 207, 142, 0.35);
  border-radius: 8px;
}
.ss-anchor { display: flex; flex-direction: column; gap: 0.05rem; }
.ss-anchor-ch {
  font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.06em;
  color: rgba(230, 230, 230, 0.5);
}
.ss-anchor-probe { font-size: 0.66rem; font-style: italic; color: rgba(230, 230, 230, 0.55); }
.ss-scene { margin: 0; font-size: 0.78rem; line-height: 1.45; font-weight: 300; }
.ss-prompt-row { display: flex; flex-direction: column; gap: 0.15rem; }
.ss-prompt-label {
  font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: rgba(230, 230, 230, 0.45);
}
.ss-prompt { font-size: 0.72rem; line-height: 1.4; color: rgba(230, 230, 230, 0.8); overflow-wrap: anywhere; }
.ss-carry {
  align-self: flex-start;
  padding: 0.2rem 0.6rem;
  background: transparent; border: 1px solid rgba(62, 207, 142, 0.5); border-radius: 8px;
  color: #3ecf8e; font-size: 0.66rem; cursor: pointer;
}
.ss-carry:hover { background: rgba(62, 207, 142, 0.12); color: #5fe0a6; }

/* Counts of what was excluded — numbers, never contents. */
.ss-count { margin: 0; font-size: 0.66rem; color: rgba(230, 190, 120, 0.8); }
.ss-meta {
  display: flex; gap: 0.6rem; flex-wrap: wrap; margin-top: auto;
  font-size: 0.6rem; color: rgba(230, 230, 230, 0.35);
}
</style>
