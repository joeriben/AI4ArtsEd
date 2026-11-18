<!--
  The back of an anchor: the excerpt the card is an anchor TO.

  Where the excerpt comes from is decided on the server, per kind
  (devserver/my_app/services/resona_entities.py): the memo of a kept strategy,
  the wording of a note, the passage read from a library document. A page opened
  on an external site carries its link and nothing of its text — that text
  belongs to whoever wrote it. A teaching scenario comes whole, its parts as
  paragraphs (setting, text, sequence, subject link); the other kinds arrive
  as one line, so keeping the line breaks changes nothing for them. Its
  source (the use report's version and the scenario's number) arrives as data
  and is worded here.
-->
<template>
  <div class="eb">
    <template v-if="detail">
      <div class="eb-label">{{ kind === 'scenario' ? t('resonaEntityCard.scenario') : t('resonaEntityCard.detailLabel') }}</div>
      <p class="eb-detail">{{ detail }}</p>
    </template>
    <p v-else class="eb-detail eb-empty">{{ t('resonaEntityCard.keptHere') }}</p>
    <template v-if="facts.length">
      <div class="eb-label">{{ t('resonaEntityCard.factsLabel') }}</div>
      <ul class="eb-facts">
        <li v-for="(f, i) in facts" :key="i">{{ f }}</li>
        <li v-if="source">{{ t('resonaEntityCard.scenarioSource', { version: source.version, scenario: source.scenario }) }}</li>
      </ul>
    </template>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineProps<{
  detail: string
  facts: string[]
  /** The card's kind. A teaching scenario's back is the whole scenario, not an excerpt. */
  kind?: string
  /** A teaching scenario's origin: the use report's version and its number. */
  source?: { version: string; scenario: string } | null
}>()

const { t } = useI18n()
</script>

<style scoped>
.eb {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.6rem 0.7rem;
  color: rgba(230, 230, 230, 0.95);
}
.eb-label {
  margin-top: 0.5rem;
  font-size: 0.62rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(230, 230, 230, 0.5);
}
.eb-label:first-child { margin-top: 0; }
.eb-detail { margin: 0; font-size: 0.8rem; line-height: 1.5; white-space: pre-line; }
.eb-empty { color: rgba(230, 230, 230, 0.55); }
.eb-facts {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.eb-facts li {
  font-size: 0.72rem;
  line-height: 1.4;
  color: rgba(230, 230, 230, 0.7);
  word-break: break-word;
}
</style>
