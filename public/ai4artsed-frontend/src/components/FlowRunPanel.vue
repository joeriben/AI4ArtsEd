<!--
  FlowRunPanel — what a flow's middle node shows while it is open.

  The flow's grammar one level down: the run laid out station by station, each
  saying as precisely as it can what it is, the running one lit and the ones
  still to come dimmed. x2x-flow drew it first; it is taken out of that page so
  that a second page can report ITS run in the same panel instead of drawing a
  second one beside it.

  It owns the row and the small boxes in it. What a station IS stays with the
  page — every page has its own chain, and this component never learns any of
  them. The foot is a slot: x2x-flow puts the card's live energy figures there,
  a page with nothing to put there leaves it out and the line does not appear.
-->
<template>
  <div class="gr">
    <div class="gr-row">
      <div v-for="st in stations" :key="st.id" class="gr-st" :class="[st.state, { w2: st.wide }]">
        <div class="gr-k">{{ st.label }}</div>
        <div class="gr-v" :title="st.detail">{{ st.detail }}</div>
        <div v-if="st.note" class="gr-n" :title="st.note">{{ st.note }}</div>
        <div v-if="st.time" class="gr-t">{{ st.time }}</div>
      </div>
    </div>
    <div v-if="$slots.foot" class="gr-foot"><slot name="foot" /></div>
  </div>
</template>

<script setup lang="ts">
// The type steps this panel is written in (--flow-fs-hint, --flow-fs-sub) live
// on :root in flow-stage.css, which main.ts loads once since 2026-10-10 (until
// then both callers pulled it in themselves, x2x_flow directly, the cover band
// through FlowHeader).

interface FlowRunStation {
  id: string
  label: string
  detail: string
  note?: string
  /** Bottom line, held to the foot of the box: what the station cost. */
  time?: string
  state: 'todo' | 'live' | 'done' | 'failed'
  /** Carries more figures than an equal share can hold. */
  wide?: boolean
}

defineProps<{ stations: FlowRunStation[] }>()
</script>

<style scoped>
.gr { display: flex; flex-direction: column; width: 100%; height: 100%; padding: 5px 7px; box-sizing: border-box; gap: 3px; }
.gr-row { display: flex; flex: 1; min-height: 0; align-items: stretch; gap: 5px; }
.gr-st { flex: 1; min-width: 0; overflow: hidden; display: flex; flex-direction: column; gap: 1px; padding: 4px 6px; border-radius: 7px;
  border: 1px solid #2c4762; background: rgba(0, 0, 0, 0.18); text-align: start; opacity: 0.45; transition: opacity 0.25s, border-color 0.25s; }
.gr-st.w2 { flex: 1.6; }
/* flex-shrink: 0 on every line. .gr-v carries overflow:hidden, which under
   flexbox sets its automatic minimum size to zero — so when the column was short
   it absorbed ALL the negative space and its text was sliced through the middle
   or erased outright, measured at 768px, which is iPad portrait. A line can be
   clipped at the bottom, which stays legible; a half-height glyph does not. */
.gr-st > * { flex: 0 0 auto; }
.gr-st.done { opacity: 0.8; }
.gr-st.live { opacity: 1; border-color: #7fb2ff; background: rgba(127, 178, 255, 0.09); }
/* A station that did not answer. x2x-flow has no such state today; the cover
   band's chain can stop at any of its four. */
.gr-st.failed { opacity: 1; border-color: #a04040; }
.gr-k { font-size: var(--flow-fs-hint); color: #8fa6bf; line-height: 1.2; overflow-wrap: anywhere; }
.gr-v { font-size: var(--flow-fs-sub); color: rgba(255, 255, 255, 0.92); line-height: 1.25; overflow: hidden;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow-wrap: anywhere; }
.gr-n { font-size: var(--flow-fs-hint); color: #7f9ab5; line-height: 1.2; overflow-wrap: anywhere; overflow: hidden;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }
/* Pushed to the foot of its box so the figures line up across the row however
   many lines the stations above them needed. */
/* line-height with the other three, not the document's 1.6. At the same font
   size this line was 5px taller than a label — and being held to the foot of the
   box by margin-top:auto, it is the first thing lost when a box overflows, which
   makes it the wrong line to let grow. */
.gr-t { margin-top: auto; line-height: 1.2; font-size: var(--flow-fs-hint); color: #6f7a86; font-variant-numeric: tabular-nums; }
.gr-st.live .gr-k { color: #7fb2ff; }
.gr-foot { display: flex; gap: 10px; align-items: baseline; }
</style>
