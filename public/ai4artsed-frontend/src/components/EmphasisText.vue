<!--
  A text with single words set off, written as *asterisks* in the string itself.

  Not markdown and not HTML. The string is cut at each marked pair and the parts
  are rendered as text nodes; the only markup that exists is the <em> in this
  template. Nothing a translation says can become an element, an attribute or a
  script - the failure modes are a missing emphasis and a stray asterisk, never
  broken markup.

  A pair counts only where each asterisk hugs a word on its inner side: no space,
  no second asterisk and no quotation mark next to it. An asterisk that stands
  for itself keeps a quotation mark or a space on that side - the placeholder
  „*“ of a prompt, „a person feeling *“ on Stereotype Analysis - and stays in
  the text as written. Before 2026-11-15 every two asterisks made a pair, and
  that page's text lost both placeholders and set the words between them in
  italics. An asterisk without a partner stays as it stands too.

  Written for the address a page says about itself (stores/pageAddress.ts), where
  the authored German carries an emphasis and the interpolation showed it as two
  literal asterisks. Anything that renders authored, translated prose can use it.
-->
<template>
  <span class="emph"
    ><template v-for="(part, i) in parts" :key="i"
      ><em v-if="part.em">{{ part.text }}</em
      ><template v-else>{{ part.text }}</template
    ></template
  ></span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ text?: string | null }>()

// Inner neighbour of a marker: anything but a space, an asterisk or a
// quotation mark.
const INNER = '[^\\s*„“”"‚‘’\'«»‹›]'
const PAIR = new RegExp(`\\*(${INNER}(?:[^*]*?${INNER})?)\\*`, 'g')

const parts = computed<{ text: string; em: boolean }[]>(() => {
  const raw = String(props.text ?? '')
  const out: { text: string; em: boolean }[] = []
  let last = 0
  for (const m of raw.matchAll(PAIR)) {
    const at = m.index ?? 0
    if (at > last) out.push({ text: raw.slice(last, at), em: false })
    out.push({ text: m[1] ?? '', em: true })
    last = at + m[0].length
  }
  if (last < raw.length || !out.length) out.push({ text: raw.slice(last), em: false })
  return out
})
</script>

<style scoped>
.emph em {
  font-style: italic;
}
</style>
