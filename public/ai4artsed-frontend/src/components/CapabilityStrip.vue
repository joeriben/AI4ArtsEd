<template>
  <span class="cap-strip" :style="{ gridTemplateColumns: `repeat(${capabilities.length}, minmax(0, 1fr))` }">
    <!-- Header variant: the vocabulary itself, one column per requirement. -->
    <template v-if="head">
      <span
        v-for="cap in capabilities"
        :key="cap"
        class="cap-slot cap-slot-head"
        :title="$t('settings.capabilities.' + cap + 'Column')"
      >{{ $t('settings.capabilities.' + cap) }}</span>
    </template>

    <template v-else>
      <span
        v-for="cap in capabilities"
        :key="cap"
        class="cap-slot"
        :class="slotClass(cap)"
        :title="slotTitle(cap)"
      >
        <template v-if="requires(cap)">
          <span class="cap-state">{{ slotState(cap) }}</span>
          <button
            v-if="canCheck(cap)"
            @click="$emit('check', cap)"
            class="cap-btn"
            :disabled="busy.includes(cap)"
          >{{ busy.includes(cap) ? $t('settings.capabilities.checking') : $t('settings.capabilities.check') }}</button>
        </template>
      </span>
    </template>
  </span>
</template>

<script setup>
/**
 * The requirement strip of one row: one slot per requirement in the shared vocabulary,
 * same position in every row, so a column reads downwards.
 *
 * A slot says one of five things, and never two at once -- requirement and ability were
 * collapsed into a single token once and the result was unreadable:
 *   (empty)        this row does not need it
 *   no model       the row has no model to say anything about
 *   not checked    it can be measured and has not been
 *   ✓ / MISSING   it was measured, and this is what came back
 *   not possible   the connection rules it out; there is nothing to measure
 *
 * Used by the model table and by the safety models, which is why it is a component and
 * not markup inside one of them.
 */
import { useI18n } from 'vue-i18n'

const props = defineProps({
  // A role_overview() entry: { requires, measurable, model, known, fixed, evidence, checked }
  entry: { type: Object, default: null },
  capabilities: { type: Array, required: true },
  busy: { type: Array, default: () => [] },
  head: { type: Boolean, default: false },
})
defineEmits(['check'])

const { t } = useI18n()

function requires(cap) {
  return !!props.entry && props.entry.requires.includes(cap)
}

function isMeasurable(cap) {
  return !!props.entry && (props.entry.measurable || []).includes(cap)
}

function hasModel() {
  return !!props.entry && !!props.entry.model
}

// A verdict that follows from the connection rather than from the model: nothing can be
// measured and nothing can be changed by measuring, so no button is offered.
function isFixed(cap) {
  return !!props.entry && !!props.entry.fixed && props.entry.fixed[cap] === true
}

function known(cap) {
  return props.entry && props.entry.known ? (props.entry.known[cap] ?? null) : null
}

// The button is offered where a measurement is still owed: nothing measured yet, or a
// refusal that may have been a mistyped name or a provider that was briefly down. Behind
// a yes it has nothing left to do -- and it stays gone until the row gets another model,
// which drops the verdict with it.
function canCheck(cap) {
  return isMeasurable(cap) && hasModel() && !isFixed(cap) && known(cap) !== true
}

function slotState(cap) {
  if (!hasModel()) return t('settings.capabilities.noModel')
  if (isFixed(cap)) return t('settings.capabilities.notPossible')
  if (!isMeasurable(cap)) return t('settings.capabilities.needed')
  const verdict = known(cap)
  if (verdict === true) return '✓'
  if (verdict === false) return t('settings.capabilities.missing')
  return t('settings.capabilities.unchecked')
}

function slotClass(cap) {
  if (!requires(cap)) return 'cap-slot-idle'
  if (!hasModel()) return 'cap-slot-open'
  if (isFixed(cap)) return 'cap-slot-fixed'
  if (!isMeasurable(cap)) return 'cap-slot-needed'
  const verdict = known(cap)
  if (verdict === true) return 'cap-slot-present'
  if (verdict === false) return 'cap-slot-missing'
  return 'cap-slot-open'
}

// The tooltip says what the slot itself cannot: what the requirement is, and why a
// fixed slot is fixed. It carries nothing else -- the measurement date and the raw
// model reply stood here once and were noise in the reader's face.
function slotTitle(cap) {
  if (!requires(cap)) return ''
  if (isFixed(cap)) return t('settings.capabilities.' + cap + 'Fixed')
  return t('settings.capabilities.' + cap + 'Help')
}
</script>

<style scoped>
.cap-strip {
  flex: 1 1 auto;
  display: grid;
  gap: 4px;
}

.cap-slot {
  min-height: 30px;
  padding: 4px 6px;
  border-radius: 3px;
  font-size: 11px;
  line-height: 1.3;
  text-align: center;
}

.cap-slot-head {
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  color: #c8c8c8;
  background: var(--surface-2);
  min-height: 0;
}

/* Not needed in this row: the slot stays as a rule, not as a statement. */
.cap-slot-idle {
  background: transparent;
}

.cap-slot-needed,
.cap-slot-open {
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  color: #c8c8c8;
}

/* Ruled out by the connection, not by the model. Deliberately not the red of a
   measured refusal: nothing here is misconfigured and nothing can be measured. */
.cap-slot-fixed {
  background: transparent;
  border: 1px dashed var(--surface-4);
  color: #8a8a8a;
  font-style: italic;
}

.cap-slot-present {
  background: rgba(76, 175, 80, 0.14);
  border: 1px solid #4CAF50;
  color: #66bb6a;
}

.cap-slot-missing {
  background: rgba(229, 57, 53, 0.14);
  border: 1px solid #ef5350;
  color: #ff7b72;
  font-weight: 700;
}

.cap-state {
  display: block;
}

.cap-btn {
  display: block;
  width: 100%;
  margin-top: 4px;
  padding: 2px 4px;
  font-size: 10px;
  background: var(--surface-3);
  color: #f2f2f2;
  border: 1px solid var(--surface-4);
  border-radius: 3px;
  cursor: pointer;
}

.cap-btn:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
