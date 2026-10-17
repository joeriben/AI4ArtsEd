<template>
  <label class="seed-control">
    Seed
    <input
      v-model.number="seedModel"
      type="number"
      min="0"
      :disabled="randomModel || disabled"
      class="setting-input setting-seed"
    />
    <label class="seed-random-toggle">
      <input type="checkbox" v-model="randomModel" :disabled="disabled" />
      {{ t('latentLab.shared.randomVariation') }}
    </label>
  </label>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  seed: number
  random: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:seed': [value: number]
  'update:random': [value: boolean]
}>()

const seedModel = computed({
  get: () => props.seed,
  set: (v: number) => emit('update:seed', v),
})

const randomModel = computed({
  get: () => props.random,
  set: (v: boolean) => emit('update:random', v),
})
</script>

<style scoped>
/*
 * The field is drawn HERE, because nowhere else can.
 *
 * It carried the page's class names (`setting-input setting-seed`) and nothing
 * else, and a page's scoped CSS does not reach into a component: only this
 * component's root label takes the page's scope, never the input inside it. So
 * this field stood unstyled on all eight instruments that use it — a white
 * browser number box with the little up/down arrows the browser puts there.
 *
 * Surface tokens, not a literal: a field is `--surface-2` on `--surface-4`, so
 * it stays dark under every tone the platform can be set to. The seven klappen
 * that hold this control still carry three different local versions of
 * `.setting-input` — that is the consolidation the element registry already
 * records, and it is not settled here. The arrows are switched off: this
 * platform draws no such thing anywhere, and a number that is stepped one at a
 * time is not what a seed is for.
 *
 * Since 2026-09-05 the klappe's own `.setting-input` stands UNSCOPED in
 * assets/flow-stage.css, so it does reach this field, and every property it
 * sets that this file leaves unsaid lands here. `box-sizing` is the one that
 * changes nothing: assets/base.css gives `*` `border-box` platform-wide, so
 * the shared declaration restates the value this field already stands at, and
 * `width: 14ch` measures 94.58 px at this size — fourteen characters, which is
 * what it says. Saying `content-box` here laid the padding and the border on
 * top of those and took the field to 112.58 px on all ten surfaces that hold
 * it; measured 2026-09-05, and withdrawn the same day.
 */
.setting-input {
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  border-radius: 6px;
  /* One line high: the box holds the line and a hair of air, nothing more. The
     klappe's own fields still sit at 0.4rem and read as two-line boxes; that is
     the standing consolidation, not this field's shape. */
  padding: 0.15rem 0.5rem;
  line-height: 1.35;
  color: white;
  font-size: 0.85rem;
  font-family: inherit;
}
.setting-input:focus {
  outline: none;
  border-color: rgba(255, 255, 255, 0.28);
}
.setting-input:disabled {
  opacity: 0.4;
}
.setting-seed {
  width: 14ch;
}
.setting-input[type='number'] {
  appearance: textfield;
  -moz-appearance: textfield;
}
.setting-input[type='number']::-webkit-outer-spin-button,
.setting-input[type='number']::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.seed-random-toggle {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  cursor: pointer;
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.35);
}
</style>
