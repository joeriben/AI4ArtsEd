<!--
  The front of an apparatus card: the apparatus at work, then its pedagogically
  relevant results. Provenance — why Resona built it, the pipeline summary, the
  run id — stands on the back (ResonaGraphCardBack), and the card that turns is
  FlowCard.
-->
<template>
  <div class="card-front">
    <div class="graph-header">
      <span class="graph-title">{{ box.title }}</span>
      <span class="graph-status" :class="`status-${box.status}`">
        <template v-if="box.status === 'running'">{{ t('resonaGraphCard.running') }}</template>
        <template v-else-if="box.status === 'complete'">{{ t('resonaGraphCard.finished') }}</template>
        <template v-else-if="box.status === 'partial'">{{ t('resonaGraphCard.partial') }}</template>
        <template v-else>{{ t('resonaGraphCard.failed') }}</template>
      </span>
    </div>

    <!-- Running: one line per node (type + status); inline thumbnail when a
         node_complete carried an image preview. -->
    <ul v-if="box.status === 'running'" class="progress-list">
      <li
        v-for="(p, i) in box.progress"
        :key="`${p.nodeId}-${i}`"
        class="progress-row"
        :class="{ 'row-live': i === box.progress.length - 1 }"
      >
        <span class="progress-type">{{ p.nodeType }}</span>
        <img
          v-if="p.previewUrl"
          :src="p.previewUrl"
          alt=""
          class="progress-thumb"
        />
        <span v-else-if="p.previewText" class="progress-preview">{{ p.previewText }}</span>
        <span v-else-if="p.message" class="progress-message">{{ p.message }}</span>
      </li>
      <li v-if="!box.progress.length" class="progress-row progress-waiting">
        {{ t('resonaGraphCard.starting') }}
      </li>
    </ul>

    <!-- Complete: the pedagogically relevant outputs, in execution order.
         Generation → image (or media link); evaluation/comparison/interception
         → text, clamped and expandable. Nothing else. -->
    <div v-else-if="box.status === 'complete'" class="results-list">
      <div v-for="(r, i) in box.results" :key="`${r.nodeId}-${i}`" class="result-item">
        <template v-if="r.kind === 'image' && r.url">
          <img
            :src="r.url"
            :alt="r.meta?.display_name || r.nodeType"
            class="result-image"
            @click="emitImageClick(r.url)"
          />
        </template>
        <template v-else-if="r.kind === 'media' && r.url">
          <a :href="r.url" target="_blank" rel="noopener" class="result-media-link">
            {{ r.meta?.display_name || r.nodeType }}: {{ r.url }}
          </a>
        </template>
        <template v-else-if="r.kind === 'text' && r.text">
          <div class="result-text" :class="{ clamped: !expandedText.has(r.nodeId) }">
            {{ r.text }}
          </div>
          <button
            v-if="isClampable(r.text)"
            class="text-toggle"
            @click="toggleText(r.nodeId)"
          >
            {{ expandedText.has(r.nodeId) ? t('resonaGraphCard.showLess') : t('resonaGraphCard.showMore') }}
          </button>
        </template>
      </div>
      <p v-if="!box.results.length" class="results-empty">{{ t('resonaGraphCard.noResults') }}</p>
    </div>

    <!-- Partial: the live stream tore (server restart) but finished pieces
         were recovered from disk. Show them in the same grid as results,
         then say plainly what happened and how much was saved. -->
    <div v-else-if="box.status === 'partial'" class="results-list">
      <div v-for="(r, i) in (box.recovered || [])" :key="`rec-${r.index}-${i}`" class="result-item">
        <img
          :src="r.url"
          :alt="r.nodeLabel || ''"
          class="result-image"
          @click="emitImageClick(r.url)"
        />
      </div>
      <p class="partial-note">{{ t('resonaGraphCard.connectionLost') }}</p>
      <p class="partial-count">
        {{ t('resonaGraphCard.partialRecovered', { n: (box.recovered || []).length, m: recoveredTotal }) }}
      </p>
    </div>

    <!-- Error: honest, no fake content — and no discarding either. What
         the apparatus rendered before it stopped is on disk and belongs to
         the group; the failure is stated first, the pieces follow. -->
    <div v-else class="card-error">
      <p class="error-caption">{{ t('resonaGraphCard.errorState') }}</p>
      <p v-if="box.error" class="error-detail">{{ box.error }}</p>
      <template v-if="(box.recovered || []).length">
        <p class="error-rendered-note">{{ t('resonaGraphCard.errorRendered') }}</p>
        <div class="results-list">
          <div v-for="(r, i) in (box.recovered || [])" :key="`err-rec-${r.index}-${i}`" class="result-item">
            <img
              :src="r.url"
              :alt="r.nodeLabel || ''"
              class="result-image"
              @click="emitImageClick(r.url)"
            />
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { GraphRunBox } from '@/views/resona_graph_types'

const props = defineProps<{
  box: GraphRunBox
}>()

const emit = defineEmits<{
  (e: 'image-click', url: string): void
}>()

const { t } = useI18n()

// Per-node text expand state for evaluation/comparison outputs.
const expandedText = ref<Set<string>>(new Set())

function toggleText(nodeId: string) {
  const next = new Set(expandedText.value)
  if (next.has(nodeId)) next.delete(nodeId)
  else next.add(nodeId)
  expandedText.value = next
}

function isClampable(text: string): boolean {
  return text.length > 220 || text.split('\n').length > 4
}

function emitImageClick(url: string) {
  emit('image-click', url)
}

// Partial recovery: n saved out of m total pieces (saved + never-landed).
const recoveredTotal = computed(() => {
  const saved = props.box.recovered?.length ?? 0
  const pending = props.box.recoveredPending ?? 0
  return saved + pending
})

</script>

<style scoped>
/* No frame here: the card around this one is FlowCard, and drawing a second
   border inside the first is what this change removed. */
.card-front {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.8rem 0.9rem;
}

.graph-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.8rem;
}

.graph-title {
  font-size: 1rem;
  font-weight: 700;
  color: rgba(240, 240, 240, 0.95);
  line-height: 1.35;
}

.graph-status {
  flex-shrink: 0;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  color: rgba(230, 230, 230, 0.6);
}

.status-running {
  color: #9ec8e0;
  border-color: rgba(158, 200, 224, 0.4);
}

.status-complete {
  color: #9ed0a8;
  border-color: rgba(158, 208, 168, 0.4);
}

.status-error {
  color: #e08a8a;
  border-color: rgba(224, 138, 138, 0.4);
}

/* Partial = a tear that still saved something. Amber, distinct from both the
   green of a clean finish and the red of a hard failure. */
.status-partial {
  color: #d9b77a;
  border-color: rgba(217, 183, 122, 0.45);
}

.error-rendered-note {
  margin: 0.6rem 0 0.35rem;
  font-size: 0.78rem;
  color: rgba(232, 232, 232, 0.6);
}
.partial-note {
  margin: 0.5rem 0 0;
  font-size: 0.82rem;
  color: rgba(217, 183, 122, 0.85);
  white-space: pre-wrap;
  word-break: break-word;
}

.partial-count {
  margin: 0.25rem 0 0;
  font-size: 0.76rem;
  color: rgba(217, 183, 122, 0.6);
}

/* ---------- Running: progress list ---------- */

.progress-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.progress-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.82rem;
  color: rgba(230, 230, 230, 0.8);
}

.progress-type {
  flex-shrink: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.72rem;
  color: rgba(230, 230, 230, 0.55);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.progress-thumb {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.progress-preview,
.progress-message {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgba(230, 230, 230, 0.65);
}

.progress-waiting {
  color: rgba(230, 230, 230, 0.55);
  font-style: italic;
  animation: resona-breathe 2.4s ease-in-out infinite alternate;
}

/* The front of the work breathes: the last row is the node most recently
   started — where the apparatus stands right now — and the waiting row is
   the moment before anything has reported. Only the type label breathes, so
   the preview text stays legible. A slow greyscale breath: orientation that
   something runs, never a mime of someone typing. */
@keyframes resona-breathe {
  from { opacity: 0.4; }
  to { opacity: 1; }
}

.progress-row.row-live .progress-type {
  animation: resona-breathe 2.4s ease-in-out infinite alternate;
}

@media (prefers-reduced-motion: reduce) {
  .progress-row.row-live .progress-type,
  .progress-waiting {
    animation: none;
  }
}

/* ---------- Complete: results ---------- */

.results-list {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.result-item {
  min-width: 0;
}

.result-image {
  width: 100%;
  max-width: 100%;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  cursor: pointer;
  display: block;
}

.result-media-link {
  display: inline-block;
  font-size: 0.85rem;
  color: #9ec8e0;
  word-break: break-all;
  text-decoration: none;
}

.result-media-link:hover {
  text-decoration: underline;
}

.result-text {
  font-size: var(--flow-fs-body);
  line-height: 1.55;
  color: rgba(230, 230, 230, 0.9);
  white-space: pre-wrap;
  word-break: break-word;
}

.result-text.clamped {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.text-toggle {
  margin-top: 0.25rem;
  padding: 0;
  background: transparent;
  border: none;
  color: rgba(158, 200, 224, 0.85);
  font-size: 0.76rem;
  cursor: pointer;
}

.text-toggle:hover {
  color: #9ec8e0;
}

.results-empty {
  margin: 0;
  font-size: 0.85rem;
  color: rgba(230, 230, 230, 0.5);
}

/* ---------- Error ---------- */

.card-error {
  padding: 0.4rem 0;
}

.error-caption {
  margin: 0;
  font-size: 0.88rem;
  color: #e08a8a;
}

.error-detail {
  margin: 0.35rem 0 0;
  font-size: 0.78rem;
  color: rgba(224, 138, 138, 0.7);
  white-space: pre-wrap;
  word-break: break-word;
}

</style>
