<!--
  A text with single words set off, written as *asterisks* in the string itself.

  Not markdown and not HTML. The string is SPLIT on the asterisk and the parts
  are rendered as text nodes; the only markup that exists is the <em> in this
  template. Nothing a translation says can become an element, an attribute or a
  script - the failure modes are a missing emphasis and a stray asterisk, never
  broken markup.

  An unpaired asterisk leaves the text exactly as it stands: an odd number of
  markers means the author's intent cannot be read, and guessing at it would set
  off the whole tail of the sentence.

  Written for the address a page says about itself (stores/pageAddress.ts), where
  the authored German carries an emphasis and the interpolation showed it as two
  literal asterisks. Anything that renders authored, translated prose can use it.
-->
<template>
  <span class="emph"
    ><template v-for="(part, i) in parts" :key="i"
      ><em v-if="i % 2 === 1">{{ part }}</em
      ><template v-else>{{ part }}</template
    ></template
  ></span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ text?: string | null }>()

const parts = computed<string[]>(() => {
  const raw = String(props.text ?? '')
  const split = raw.split('*')
  // Even length means an unpaired marker. Leave the sentence alone.
  return split.length % 2 === 0 ? [raw] : split
})
</script>

<style scoped>
.emph em {
  font-style: italic;
}
</style>
