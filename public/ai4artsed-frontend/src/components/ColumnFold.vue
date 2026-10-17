<!--
  Der Griff, der die vorbereitende Spalte wegklappt.

  He stood in views/latent_lab/perspectives_template.vue first, for that one
  surface, and is here for every instrument built as ONE preparing column plus
  two or three result columns where that makes sense. A second copy would be a
  parallel structure (docs/ELEMENT_STRUCTURE_REGISTRY.md), so the surfaces
  have none — they carry the host class and the state, and what the handle looks
  like, where it stands in each of its two states and what it hides is here.

  The GLYPH carries it alone, the icon suffices; what it does
  stands in its title. Folding happens when this is pressed and at no other
  moment — a column that folded itself when a run started took the controls away
  from a hand that was still on them.

  A host folds by keeping the handle and hiding its other children, rather than
  by taking them out of the tree: what a reader had typed, opened or scrolled to
  is still there when the column comes back.

  `disabled` is for the host that has a control in this column which a run has
  to be able to reach WHILE it is out — the LoRA Training Studio's stop, which
  the fold would hide along with everything else. Such a host keeps the column
  standing for the length of the run and says so by handing the handle its own
  state, rather than leaving a control that presses and does nothing.
-->
<template>
  <button
    class="col-fold"
    :disabled="disabled"
    :title="folded ? t('columnFold.show') : t('columnFold.hide')"
    @click="emit('update:folded', !folded)"
  >
    <svg class="col-fold-icon" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
      <rect x="1.6" y="2.6" width="12.8" height="10.8" rx="1.6" />
      <path d="M6.4 2.6v10.8" />
      <path d="M11.9 6.3 9.6 8l2.3 1.7" />
    </svg>
  </button>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

withDefaults(defineProps<{ folded: boolean; disabled?: boolean }>(), { disabled: false })
const emit = defineEmits<{ 'update:folded': [boolean] }>()
const { t } = useI18n()
</script>

<!-- Unscoped on purpose: `.col-fold-host` is the other half of this structure
     and sits on a section of the surface, not inside this component. The two
     stage sheets keep only what is theirs, the TRACK the folded column stands
     in (`.lab-work.folded` in assets/flow-stage.css, `.cmp-work.folded` in
     assets/compare-stage.css) — a narrower child in an unchanged track would
     only have left a gap. -->
<style>
/* Folded, the column is the handle and nothing else. */
.col-fold-host.folded {
  padding-inline: 0;
  overflow: hidden;
  align-items: center;
}

.col-fold-host.folded > *:not(.col-fold) {
  display: none;
}

/* The handle is the one control that stays when the others go, so it stands at
   the top of the column in both states rather than moving when it is used. */
.col-fold {
  align-self: flex-start;
  flex: 0 0 auto;
  height: 26px;
  padding-inline: 7px;
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.6);
  font-family: inherit;
  font-size: var(--flow-fs-hint);
  line-height: 1;
  min-width: 0;
  cursor: pointer;
}

.col-fold-host.folded > .col-fold {
  align-self: center;
  padding-inline: 0;
  width: 26px;
  justify-content: center;
}

.col-fold:hover:not(:disabled) {
  color: rgba(255, 255, 255, 0.9);
  border-color: rgba(255, 255, 255, 0.3);
}

/* The colour of its own border, the way a handle that cannot be moved says so
   everywhere else on the platform (`.lab-range:disabled`, assets/flow-stage.css). */
.col-fold:disabled {
  color: var(--surface-4);
  cursor: default;
}

/* The glyph: a panel with its leading edge marked, and the arrow going into it.
   Folded it is the same glyph the other way round, so the two states are one
   thing turning rather than two signs. */
.col-fold-icon {
  flex: none;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.col-fold-host.folded > .col-fold .col-fold-icon {
  transform: scaleX(-1);
}

/* Right to left the column stands on the right and folds the other way, and an
   SVG is not turned by `dir`. So the glyph is mirrored in the state the other
   direction leaves it unmirrored, and the other way round. */
[dir='rtl'] .col-fold-icon {
  transform: scaleX(-1);
}

[dir='rtl'] .col-fold-host.folded > .col-fold .col-fold-icon {
  transform: none;
}
</style>
