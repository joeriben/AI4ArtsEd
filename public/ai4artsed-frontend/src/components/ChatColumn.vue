<!--
  One column of a chat comparison: what sets the column apart in its head, and
  under it the conversation that column has had — the message, the answer, and
  the three dots while an answer is still out.

  Lifted out of views/compare/system_prompt_comparison.vue on 2026-10-27, when
  Model Comparison (Transformers Lab) needed the same column with something else
  in its head: there it is a model, in System Prompts a system prompt. The registry had
  recorded that no further copy of this head would be written
  (docs/ELEMENT_STRUCTURE_REGISTRY.md, `.cmp-column`), so the head is a slot
  and the column is this one file.

  The column follows its own conversation to the end: a new message, an answer
  arriving and the dots appearing all scroll it down, and so does coming back to
  a surface that still holds a conversation.
-->
<template>
  <div class="chat-column" :class="`tint-${TINTS[tint] ?? 'b'}`">
    <div class="chat-column-head">
      <slot name="head" />
    </div>
    <div ref="stream" class="chat-column-messages">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="chat-bubble"
        :class="msg.role"
      >
        {{ msg.content }}
      </div>
      <div v-if="loading" class="chat-bubble assistant loading">
        <span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import type { ChatMessage } from '@/stores/personaChat'

const props = defineProps<{
  messages: ChatMessage[]
  loading: boolean
  /** Which of the three columns this is; it sets the tint of the head. */
  tint: number
}>()

const TINTS = ['a', 'b', 'c'] as const

const stream = ref<HTMLElement | null>(null)

function toEnd() {
  nextTick(() => {
    if (stream.value) stream.value.scrollTop = stream.value.scrollHeight
  })
}

watch(() => [props.messages.length, props.loading] as const, toEnd)
onMounted(toEnd)
</script>

<style scoped>
.chat-column {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: rgb(var(--bg-base-rgb) / 0.6);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  overflow: hidden;
}

/* The head keeps the height its content is pulled to instead of shrinking
   under it: without this a field pulled past the column's height would be cut
   off by the flex layout and paint over the answers under it. Pulled that far
   the stream of answers is what gives way, which is what somebody pulling the
   field that far is asking for, and one pull back returns it. */
.chat-column-head {
  display: flex;
  flex-direction: column;
  flex: 0 0 auto;
  gap: 0.4rem;
  padding: 0.6rem 0.8rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

/* Column color tints. `--chat-column-tint` is the border a drop-down in the
   head takes (`.cmp-pick-row`, assets/compare-stage.css). */
.tint-a {
  --chat-column-tint: rgba(171, 130, 255, 0.15);
}

.tint-a .chat-column-head {
  border-bottom-color: rgba(171, 130, 255, 0.2);
}

.tint-b {
  --chat-column-tint: rgba(130, 200, 160, 0.15);
}

.tint-b .chat-column-head {
  border-bottom-color: rgba(130, 200, 160, 0.2);
}

.tint-c {
  --chat-column-tint: rgba(255, 160, 100, 0.15);
}

.tint-c .chat-column-head {
  border-bottom-color: rgba(255, 160, 100, 0.2);
}

.chat-column-messages {
  flex: 1;
  overflow-y: auto;
  padding: 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-height: 0;
  /* Set by the host where the columns stack and a row takes the height of its
     content (`.cmp-chat-columns`, assets/compare-stage.css). */
  max-height: var(--chat-column-max-h, none);
}

.chat-bubble {
  max-width: 95%;
  padding: 0.5rem 0.7rem;
  border-radius: 10px;
  font-size: var(--flow-fs-body);
  line-height: 1.45;
  word-break: break-word;
}

.chat-bubble.assistant {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.85);
  border-bottom-left-radius: 3px;
}

.chat-bubble.user {
  align-self: flex-end;
  background: rgba(76, 175, 80, 0.12);
  color: rgba(255, 255, 255, 0.9);
  border-bottom-right-radius: 3px;
}

.chat-bubble.loading {
  padding: 0.5rem 0.8rem;
}

.typing-dots span {
  animation: typing 1.2s infinite;
  font-size: 1.1rem;
  color: rgba(255, 255, 255, 0.4);
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
}
</style>
