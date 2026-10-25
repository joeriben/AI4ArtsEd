<!--
  MediaCardBack — what stands on the back of a generated medium's card.

  One drawing of it, because two surfaces need the same thing and had started to
  each write their own: the workshop had it (motivation, prompt, the model's
  sheet), the contesting surface had none at all and printed the sheet under the
  front instead, where a 300px card clipped it with no way to scroll.

  It also carries the ROW of things one can do with the medium (the functions
  stand on the back, in the flow too). A card that turns has a side for the
  record of a run, and the actions belong with that record rather than over the
  picture: the front is then the medium alone. The row is `MediaActionBar`, the
  same one a page-wide box hangs over its own result — `mediaType` decides which
  buttons it carries, so a sound file gets what a sound file has. Left without a
  `mediaType` the row stays away entirely, which is what a surface with nothing
  to offer says by saying nothing.

  It is also the panel beside the medium in the enlarged view
  (`MediaFullscreen`'s `back` prop; one click, one view, on every surface).
  The rows that the x2x flow's own inspect layer had shown —
  the perspective, the LoRAs, the AI marking read out of the file, the checks
  the run passed, a looked-up source — came over here with it, so the turned
  card and the enlarged view read the same record. The AI marking is read out
  of the DELIVERED file (`useMediaDisclosure`), and only while the back is
  looked at (`active`): under every card of a grid a back is rendered face
  down, and one request per card at mount is what that avoids.

  It is content only — the turning, the frame and the scrolling are FlowCard's.
  A page drops this into that card's `back` slot. Its props are `MediaBack`
  (`components/mediaBack.ts`), the one shape both hosts hand over.

  The labels are the ones the platform already speaks in every language; nothing
  new is invented here — the flow's own keys for the rows that came from the
  flow. One label is new: `resonaMediaCard.settingLabel` (2026-10-03), over the
  setting row, which no surface had before. `motivation` left out entirely (not null) means the page has no such
  notion — the contesting surface does not, and a block explaining that no
  reason was given would be an answer to a question nobody asked there.
-->
<template>
  <div class="mcb">
    <MediaActionBar
      v-if="mediaType"
      class="mcb-actions"
      layout="row"
      :media-type="mediaType"
      :run-id="runId ?? null"
      :is-favorited="isFavorited"
      :keep-disabled="keepDisabled"
      :forward-title="forwardTitle"
      :can-forward="canForward"
      :can-restore="canRestore"
      @toggle-favorite="emit('toggle-favorite')"
      @restore="emit('restore')"
      @forward="emit('forward')"
      @download="emit('download')"
      @print="emit('print')"
    />

    <!-- A source a perspective looked up. Topmost the reason, because it is the
         one thing here that is about the model and not about the article: what
         it did not trust itself to know. -->
    <template v-if="source">
      <template v-if="source.why">
        <div class="mcb-label">{{ t('x2xFlow.sourceWhy') }}</div>
        <p class="mcb-motivation">{{ source.why }}</p>
      </template>
      <template v-if="source.perspective">
        <div class="mcb-label">{{ t('x2xFlow.sourcePerspective') }}</div>
        <p class="mcb-fact">{{ source.perspective }}</p>
      </template>
      <div class="mcb-label">{{ t('x2xFlow.sourceSearched') }}</div>
      <p class="mcb-fact">{{ source.term }}</p>
      <template v-if="source.lang">
        <div class="mcb-label">{{ t('x2xFlow.sourceLanguage') }}</div>
        <p class="mcb-fact">{{ source.lang }}</p>
      </template>
      <div class="mcb-label">{{ t('x2xFlow.sourceArticle') }}</div>
      <p class="mcb-fact">
        <a v-if="source.url" class="mcb-link" :href="source.url" target="_blank" rel="noopener">
          {{ source.title }} ↗
        </a>
        <template v-else>{{ t('x2xFlow.sourceNotFound') }}</template>
      </p>
      <template v-if="source.extract">
        <div class="mcb-label">{{ t('x2xFlow.sourceText') }}</div>
        <p class="mcb-motivation">{{ source.extract }}</p>
      </template>
    </template>

    <template v-if="motivation !== undefined">
      <div class="mcb-label">{{ t('resonaMediaCard.motivation') }}</div>
      <p class="mcb-motivation">{{ motivation || t('resonaMediaCard.motivationMissing') }}</p>
    </template>

    <template v-if="perspective">
      <div class="mcb-label">{{ t('x2xFlow.perspectiveLabel') }}</div>
      <p class="mcb-fact">{{ perspective }}</p>
    </template>

    <!-- What Prompt Interception wrote, over what the image model was then
         given. On the instruments of the Prompt Interception group that text IS
         the finding, so the interception prompt goes on the back of the card.
         The label is page vocabulary — the platform names this text differently
         per surface — so without one the block stays away. -->
    <template v-if="intercepted && interceptedLabel">
      <div class="mcb-label">{{ interceptedLabel }}</div>
      <p class="mcb-prompt">{{ intercepted }}</p>
    </template>

    <template v-if="prompt">
      <div class="mcb-label">{{ t('resonaMediaCard.promptLabel') }}</div>
      <p class="mcb-prompt">{{ prompt }}</p>
    </template>

    <template v-if="setting">
      <div class="mcb-label">{{ t('resonaMediaCard.settingLabel') }}</div>
      <p class="mcb-fact">{{ setting }}</p>
    </template>

    <template v-if="loras">
      <div class="mcb-label">{{ t('x2xFlow.loraLabel') }}</div>
      <p class="mcb-fact mcb-lora"><LoraGlyph light class="mcb-mark" />{{ loras }}</p>
    </template>

    <template v-if="safety?.length">
      <div class="mcb-label">{{ t('x2xFlow.safetyLabel') }}</div>
      <p class="mcb-fact">{{ safety.join(' · ') }}</p>
    </template>

    <!-- The AI-Origin Disclosure (EU AI Act Art. 50), as the file carries it.
         Only where a file was there to be read: an absent file is not an
         unmarked file, and the row makes no claim about something nobody
         opened. What was found stands in the hover text. -->
    <template v-if="disclosure?.present">
      <div class="mcb-label">{{ t('x2xFlow.aiMark') }}</div>
      <p
        class="mcb-fact"
        :title="
          disclosure.description ||
          disclosure.digital_source_type ||
          [disclosure.standard, disclosure.carrier].filter(Boolean).join(' · ')
        "
      >
        {{ disclosure.marked ? t('x2xFlow.aiMarkYes') : t('x2xFlow.aiMarkNone') }}
      </p>
    </template>

    <ModelProvenanceCard v-if="modelMeta" :meta="modelMeta" class="mcb-provenance" />

    <div class="mcb-meta">
      <span v-if="configId">{{ configId }}</span>
      <span v-for="(f, fi) in facts ?? []" :key="fi">{{ f }}</span>
      <span v-if="createdAt">{{ t('resonaMediaCard.timestamp') }}: {{ timeText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue'
import { useI18n } from 'vue-i18n'
import ModelProvenanceCard from '@/components/ModelProvenanceCard.vue'
import MediaActionBar from '@/components/MediaActionBar.vue'
import LoraGlyph from '@/components/LoraGlyph.vue'
import { useMediaDisclosure } from '@/composables/useMediaDisclosure'
import type { MediaBack } from '@/components/mediaBack'

// The booleans only: an absent boolean prop is cast to false, and two of them
// mean the opposite when nothing is said.
const props = withDefaults(defineProps<MediaBack>(), {
  isFavorited: false,
  canForward: true,
  canRestore: false,
  active: true,
})

const emit = defineEmits<{
  (e: 'toggle-favorite'): void
  (e: 'restore'): void
  (e: 'forward'): void
  (e: 'download'): void
  (e: 'print'): void
}>()

const { t } = useI18n()

const timeText = computed(() =>
  props.createdAt
    ? new Date(props.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : ''
)

const { disclosure } = useMediaDisclosure(
  toRef(props, 'runId'),
  toRef(props, 'mediaType'),
  toRef(props, 'mediaUrl'),
  toRef(props, 'active'),
)
</script>

<style scoped>
.mcb {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.7rem 0.9rem;
  color: rgba(230, 230, 230, 0.95);
}
.mcb-label {
  margin-top: 0.5rem;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(230, 230, 230, 0.5);
}
.mcb-label:first-child { margin-top: 0; }
/* The row stands at the top of this side and to the leading edge, above the
   record it belongs to. */
.mcb-actions { align-self: flex-start; margin-bottom: 0.2rem; }
.mcb-actions + .mcb-label { margin-top: 0; }
/* A reason or an extract: its own line breaks kept, a long token broken. */
.mcb-motivation { margin: 0; font-size: 0.95rem; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; }
.mcb-prompt {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: rgba(230, 230, 230, 0.85);
  white-space: pre-wrap;
  word-break: break-word;
  /* The prompt is the one thing on this side somebody copies out. */
  user-select: text;
  cursor: text;
}
/* One fact under its label: a name, a list of checks, what the file says. */
.mcb-fact {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: rgba(230, 230, 230, 0.85);
  overflow-wrap: anywhere;
}
.mcb-lora { display: flex; align-items: center; gap: 0.35rem; }
/* The net at the 32 px and in the LoRA colour the flow's own back gave it;
   the glyph itself is drawn at 100 % of whatever box it stands in. */
.mcb-mark { flex: 0 0 auto; width: 32px; height: 32px; color: #a78bfa; }
.mcb-link { color: inherit; text-decoration: underline; text-underline-offset: 3px; }
.mcb-link:hover { color: #fff; }
.mcb-provenance { margin-top: 0.6rem; }
.mcb-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 1rem;
  margin-top: 0.6rem;
  font-size: 0.75rem;
  color: rgba(230, 230, 230, 0.5);
}
</style>
