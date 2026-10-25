<!--
  A block of text with **bold**, *italic* and "- " bullet lists, written as a
  small parsed structure and rendered through Vue's own template - never
  through v-html. The parser only ever produces text/strong/em runs and p/ul
  blocks; nothing in the source string can become an element, an attribute or
  a script, the same guarantee EmphasisText makes for a single inline marker,
  extended here to block structure for freeform model output (a chat reply,
  a comparison's analysis text) that EmphasisText's authored, single-line
  scope was never meant to carry.

  A stray "**"/"*"/"- " that isn't a real pair or a real bullet is simply not
  matched and stands in the text unchanged - the failure mode is a literal
  asterisk or dash, never broken structure.
-->
<template>
  <div class="mdlite">
    <template v-for="(block, bi) in blocks" :key="bi">
      <p v-if="block.type === 'p'"
        ><template v-for="(line, li) in block.lines" :key="li"
          ><br v-if="li > 0" /><template v-for="(run, ri) in line" :key="ri"
            ><strong v-if="run.type === 'strong'">{{ run.text }}</strong
            ><em v-else-if="run.type === 'em'">{{ run.text }}</em
            ><strong v-else-if="run.type === 'strongem'"><em>{{ run.text }}</em></strong
            ><template v-else>{{ run.text }}</template
          ></template
        ></template
      ></p>
      <ul v-else
        ><li v-for="(item, ii) in block.items" :key="ii"
          ><template v-for="(run, ri) in item" :key="ri"
            ><strong v-if="run.type === 'strong'">{{ run.text }}</strong
            ><em v-else-if="run.type === 'em'">{{ run.text }}</em
            ><strong v-else-if="run.type === 'strongem'"><em>{{ run.text }}</em></strong
            ><template v-else>{{ run.text }}</template
          ></template
        ></li
      ></ul>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type InlineRun = { type: 'text' | 'strong' | 'em' | 'strongem'; text: string }
type Block = { type: 'p'; lines: InlineRun[][] } | { type: 'ul'; items: InlineRun[][] }

const props = defineProps<{ text?: string | null }>()

// Both delimiters must hug non-space content on both sides, so an isolated
// "*" used as multiplication ("3 * 4") or a trailing footnote marker never
// pairs up into spurious emphasis. Longest marker (***) tried first so it
// isn't read as a bold pair sitting next to a stray italic marker.
const INLINE_RE = /\*\*\*(\S(?:.*?\S)?)\*\*\*|\*\*(\S(?:.*?\S)?)\*\*|\*(\S(?:.*?\S)?)\*/g

function parseInline(text: string): InlineRun[] {
  const runs: InlineRun[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null
  INLINE_RE.lastIndex = 0
  while ((match = INLINE_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      runs.push({ type: 'text', text: text.slice(lastIndex, match.index) })
    }
    if (match[1] !== undefined) {
      runs.push({ type: 'strongem', text: match[1] })
    } else if (match[2] !== undefined) {
      runs.push({ type: 'strong', text: match[2] })
    } else if (match[3] !== undefined) {
      runs.push({ type: 'em', text: match[3] })
    }
    lastIndex = INLINE_RE.lastIndex
  }
  if (lastIndex < text.length) {
    runs.push({ type: 'text', text: text.slice(lastIndex) })
  }
  return runs
}

const blocks = computed<Block[]>(() => {
  const raw = String(props.text ?? '')
  const lines = raw.split('\n')
  const result: Block[] = []
  let paragraphLines: string[] = []
  let listItems: string[] = []

  const flushParagraph = () => {
    if (paragraphLines.length > 0) {
      result.push({ type: 'p', lines: paragraphLines.map(parseInline) })
      paragraphLines = []
    }
  }
  const flushList = () => {
    if (listItems.length > 0) {
      result.push({ type: 'ul', items: listItems.map(parseInline) })
      listItems = []
    }
  }

  for (const rawLine of lines) {
    const line = rawLine.trim()
    const bulletMatch = line.match(/^[-*]\s+(.+)$/)
    if (bulletMatch) {
      flushParagraph()
      listItems.push(bulletMatch[1] ?? '')
    } else if (line === '' || /^[-*]$/.test(line)) {
      // A bare marker with no content is neither a list item nor prose -
      // treat it like a blank line so it can't split one list into two
      // around a stray paragraph.
      flushParagraph()
      flushList()
    } else {
      flushList()
      paragraphLines.push(line)
    }
  }
  flushParagraph()
  flushList()

  return result
})
</script>

<style scoped>
.mdlite {
  white-space: normal;
}
.mdlite p {
  margin: 0 0 0.5em;
}
.mdlite p:last-child {
  margin-bottom: 0;
}
.mdlite ul {
  margin: 0.3em 0 0.5em;
  padding-inline-start: 1.2em;
}
.mdlite ul:last-child {
  margin-bottom: 0;
}
.mdlite li {
  margin: 0.15em 0;
}
.mdlite strong {
  font-weight: 600;
}
.mdlite em {
  font-style: italic;
}
</style>
