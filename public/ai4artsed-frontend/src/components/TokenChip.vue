<!--
  One piece of a tokenizer's cut, as a chip.

  The colours are the ones R21 gives a machine part (docs/latent_lab_station_design.md,
  R21 and R23: a token stands in a chip as wide as its word): the piece in
  monospace, and with `n` its position after it. A piece that continues the
  word the piece before it began (`part`) has no left edge and a dashed frame,
  so that „집 집" reads as ONE character in two pieces and not as „집" twice;
  `joinNext` takes the right corners off a chip whose successor is such a piece.
  A control mark (`kind` control) stands in the control-character colours; the
  padding of a block (`kind` pad) is an empty frame, because it is not a piece.

  Pulled out of views/latent_lab/tokenization_comparison.vue on 2026-09-15,
  when Encoder Fusion's token table needed the same chip in a table cell.
  Registered as `Stueckchip` in docs/ELEMENT_STRUCTURE_REGISTRY.md.
-->
<template>
  <span class="tok" :class="[`tok-${kind}`, { part, 'join-next': joinNext }]">
    <span class="tok-s">{{ text }}</span>
    <span v-if="n !== null" class="tok-n">{{ n }}</span>
  </span>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  /** The piece as it reads. */
  text: string
  /** Its position in the cut, shown after it; nothing where the row says it. */
  n?: number | null
  /** The rest of a word the piece before began. */
  part?: boolean
  /** The next piece continues this one's word. */
  joinNext?: boolean
  kind?: 'piece' | 'control' | 'pad'
}>(), {
  n: null,
  part: false,
  joinNext: false,
  kind: 'piece',
})
</script>

<style scoped>
.tok {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  background: #1d2f45;
  border: 1px solid #3f6a9c;
  border-radius: 4px;
  padding: 2px 6px;
}

.tok.part {
  border-style: dashed;
  border-inline-start: none;
  border-color: #2c4c70;
  background: #16283c;
  border-start-start-radius: 0;
  border-end-start-radius: 0;
  padding-inline-start: 5px;
}

.tok.join-next {
  border-start-end-radius: 0;
  border-end-end-radius: 0;
}

.tok.part .tok-s {
  color: #93a1b2;
}

.tok-s {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.82rem;
  color: #dde4ee;
  white-space: pre;
}

.tok-n {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.4);
}

/* A control mark: the control-character colours of the station drawings. */
.tok-control {
  background: #141b26;
  border-color: #2c3a4c;
}

.tok-control .tok-s {
  color: #9fb3cc;
}

/* Padding: a frame and no piece. The frame is a surface token, not R21's
   #4a4a4a — a neutral grey literal on a border breaks every tone but the
   default (rule 7). */
.tok-pad {
  background: transparent;
  border: 1px dashed var(--surface-4);
}

.tok-pad .tok-s {
  font-family: inherit;
  color: rgba(255, 255, 255, 0.45);
}
</style>
