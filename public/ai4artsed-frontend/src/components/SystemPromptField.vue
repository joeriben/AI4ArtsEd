<!--
  One system prompt: the preset it is set to, the field that holds it open and
  editable, and where it is published.

  Lifted out of the column head of views/compare/system_prompt_comparison.vue on
  2026-10-27, when Model Comparison (Transformers Lab) needed the same field
  once, in its preparing column. The two instruments set the same thing — what stands before
  the conversation — and a second copy of the field would have been a second
  field to keep true (docs/ELEMENT_STRUCTURE_REGISTRY.md).

  The host owns the value. What comes out is the text and the preset it now
  counts as, together, because the one is not right without the other.
  `disabled` while a round is out: the field can still be read and scrolled,
  but what it holds is what the round was sent with.
-->
<template>
  <div class="spf">
    <div class="cmp-pick-row">
      <label>{{ t('compare.systemprompt.presetLabel') }}</label>
      <select
        :value="presetId"
        :disabled="disabled"
        @change="onPresetChange(($event.target as HTMLSelectElement).value)"
      >
        <option v-for="p in SYSTEM_PROMPT_PRESETS" :key="p.id" :value="p.id">{{ t(`compare.systemprompt.presets.${p.id}`) }}</option>
        <option value="custom">{{ t('compare.systemprompt.custom') }}</option>
      </select>
    </div>
    <textarea
      ref="field"
      :value="prompt"
      class="prompt-textarea"
      :readonly="disabled"
      :placeholder="t('compare.systemprompt.emptyPrompt')"
      @input="onEdit(($event.target as HTMLTextAreaElement).value)"
    />
    <!-- Where this prompt is published, and when. It stands AT the
         prompt and not in a footnote: without its source a system
         prompt is a claim about a product, and what this field is for
         is reading a document from one. -->
    <p v-if="source" class="prompt-source">
      <a :href="source.source" target="_blank" rel="noopener noreferrer">
        {{ t('compare.systemprompt.publishedOn', { date: source.published }) }}
      </a>
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  SYSTEM_PROMPT_PRESETS,
  presetAfterEdit,
  publishedSourceOf,
} from '@/views/compare/system_prompt_presets'

const props = defineProps<{
  prompt: string
  presetId: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'change', prompt: string, presetId: string): void
}>()

const { t } = useI18n()

const field = ref<HTMLTextAreaElement | null>(null)

const source = computed(() => publishedSourceOf(props.presetId))

function onPresetChange(presetId: string) {
  const preset = SYSTEM_PROMPT_PRESETS.find(p => p.id === presetId)
  if (!preset) return
  emit('change', preset.prompt, presetId)
  // A chosen preset is a new document, and a document is read from its
  // beginning. The field may be standing deep inside the last one — the
  // published prompts run to 21,872 characters, which is 31,230 px of
  // scrolling in a 238 px field — and a browser that keeps that offset when
  // the text shrinks would show an empty box over a chosen preset.
  nextTick(() => {
    if (field.value) field.value.scrollTop = 0
  })
}

function onEdit(value: string) {
  emit('change', value, presetAfterEdit(props.presetId, value))
}
</script>

<style scoped>
/* The preset row is `.cmp-pick-row` (assets/compare-stage.css), shared with the
   model chooser in the head of a column of Model Comparison (Transformers Lab). */
.spf {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.prompt-source {
  margin: 4px 0 0;
  font-size: 0.72rem;
  line-height: 1.3;
  color: rgba(255, 255, 255, 0.45);
}

.prompt-source a {
  color: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.prompt-source a:hover {
  color: rgba(255, 255, 255, 0.75);
}

/* The field holds a DOCUMENT — what the maker of a model published as its
   system prompt — and it is there to be read.

   It stood at 0.72 rem once, which is tiny. Nothing
   computed that; it was written into this file, while the platform carries a
   step for monospace text and that step starts at 13 px. A monospace face reads
   smaller than a proportional one at the same size, so 11.5 px here was the
   smallest text on the surface.

   And it had a ceiling of 120 px, which made the grip a token: two pulls and it
   stopped, with the rest of the document behind a scrollbar. The field opens
   at twice that ceiling now and grows as far as it is pulled. */
.prompt-textarea {
  width: 100%;
  height: 240px;
  min-height: 48px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  padding: 0.35rem 0.5rem;
  color: rgba(255, 255, 255, 0.7);
  font-size: var(--flow-fs-mono);
  font-family: monospace;
  line-height: 1.4;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s ease;
}

.prompt-textarea:focus {
  border-color: rgba(255, 255, 255, 0.2);
}

.prompt-textarea::placeholder {
  color: rgba(255, 255, 255, 0.2);
  font-style: italic;
}
</style>
