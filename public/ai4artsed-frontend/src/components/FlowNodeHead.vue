<template>
  <div class="fnh-title">{{ title }}</div>

  <!-- What this box prepares. One glyph where the medium is fixed, the row
       where it is inferred or chosen. -->
  <div v-if="media.length" class="cr-media" :aria-hidden="interactive ? undefined : 'true'">
    <MediumGlyph
      v-for="m in media"
      :key="m.id"
      :id="m.id"
      class="g"
      :class="{ lit: m.state === 'lit', primary: m.state === 'primary', manual: m.state === 'manual' }"
      :title="m.label"
      @click="interactive && emit('medium', m.id)"
    />
  </div>

  <!-- The machines. A row where there is something to pick, one name where the
       instrument has only one — a name that cannot be changed is still the
       answer to „what is making this“. -->
  <div v-if="models.length" class="cr-models" :role="interactive ? 'group' : undefined" :aria-label="modelsLabel">
    <component
      :is="interactive ? 'button' : 'span'"
      v-for="mo in models"
      :key="mo.id"
      class="cr-model"
      :class="{ a: mo.state === 'active', held: mo.state === 'held' }"
      :aria-pressed="interactive ? mo.state === 'active' : undefined"
      :disabled="interactive ? disabled : undefined"
      :title="mo.title"
      @click="interactive && emit('model', mo.id)"
    >{{ mo.label }}</component>
  </div>
</template>

<script setup lang="ts">
/**
 * The head of a band box — title, what it prepares, and by what.
 *
 * The flow is the ground truth for this shape, and the information belongs in
 * the box header template: the name of the station, under it the
 * medium as a glyph, under that the machine or machines. Re-enactment shows one
 * glyph and four names because its medium is fixed and its singer is not; the
 * flow shows six glyphs and one name because it infers the medium and resolves
 * the model from it; an instrument with one of each shows one of each, and that
 * IS the information — that nothing else is possible here.
 *
 * The box shell around this belongs to `FlowHeader` (`.nd`), which supplies it
 * through a slot; this component is only what stands inside.
 *
 * Without `interactive` nothing here answers to a click and the glyphs are
 * hidden from the reading order — a row that cannot be changed is a statement,
 * not a control, and a button that does nothing is worse than a word.
 */
import MediumGlyph from '@/components/MediumGlyph.vue'
import type { MediumId } from '@/composables/useMediumInference'

export interface HeadMedium {
  id: MediumId
  /**
   * `primary` is the one in force, `lit` one that was inferred but not chosen,
   * `manual` one a person pinned. Left unset the glyph recedes.
   */
  state?: 'lit' | 'primary' | 'manual'
  label?: string
}

export interface HeadModel {
  id: string
  label: string
  state?: 'active' | 'held'
  title?: string
}

withDefaults(
  defineProps<{
    title: string
    media?: HeadMedium[]
    models?: HeadModel[]
    /** Glyphs and names answer to a click. Off by default. */
    interactive?: boolean
    /** Interactive only: the pick is fixed for as long as something runs. */
    disabled?: boolean
    /** Interactive only: what the row of machines is asking. */
    modelsLabel?: string
  }>(),
  { media: () => [], models: () => [], interactive: false, disabled: false, modelsLabel: undefined }
)

const emit = defineEmits<{ medium: [MediumId]; model: [string] }>()
</script>

<style scoped>
/* The three steps are the band's own (assets/flow-stage.css), so a box keeps
   its proportions at every stage size. */
.fnh-title {
  font-size: var(--flow-fs-label);
  font-weight: 400;
  color: #e8e8e8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.cr-media {
  display: flex;
  align-items: center;
  gap: 0.34em;
  font-size: var(--flow-glyph-medium);
  color: #5a5470;
}

.cr-media .g {
  transition: color 0.25s;
}

.cr-media .g.lit {
  color: #b6afea;
}

.cr-media .g.primary {
  color: #e9e6fb;
}

/* The pinned one carries a dot under it rather than a fourth colour. */
.cr-media .g.manual {
  position: relative;
}

.cr-media .g.manual::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -0.16em;
  width: 0.16em;
  height: 0.16em;
  border-radius: 50%;
  background: #cfe0ff;
  transform: translateX(-50%);
}

.cr-models {
  display: flex;
  flex-wrap: nowrap;
  align-items: baseline;
  justify-content: center;
  gap: 0 0.45em;
  max-width: 100%;
}

.cr-model {
  font: inherit;
  font-size: var(--flow-fs-sub);
  font-weight: 400;
  color: #a8a2c6;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: none;
  border: none;
  padding: 0;
}

button.cr-model {
  cursor: pointer;
}

/* :not(.a) — without it this beats .cr-model.a on specificity and the pointer
   makes the chosen machine DIMMER than it was. */
button.cr-model:hover:not(:disabled):not(.a) {
  color: #e9e6fb;
}

.cr-model.a {
  color: #cfe0ff;
}

.cr-model.held {
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-color: #7f77dd;
}

.cr-model:focus-visible {
  outline: 1px solid #7fb2ff;
  outline-offset: 2px;
}

button.cr-model:disabled {
  cursor: default;
}

button.cr-model:disabled:not(.a) {
  color: #6f6a8a;
}

.cr-media .g {
  cursor: default;
}

.cr-media:not([aria-hidden]) .g {
  cursor: pointer;
}
</style>
