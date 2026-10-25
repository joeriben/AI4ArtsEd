<template>
  <!-- Nothing curated yet, nothing shown. A drop-down with no option in it
       would claim there is something to choose from. -->
  <div v-if="items.length" class="prompt-examples">
    <select
      class="pe-select"
      :value="chosen"
      :disabled="disabled"
      :aria-label="labelText"
      @change="onChange(($event.target as HTMLSelectElement).value)"
    >
      <option value="">{{ labelText }}</option>
      <optgroup v-for="group in grouped" :key="group.name" :label="group.name">
        <option v-for="item in group.items" :key="item.id" :value="item.id">{{ item.label }}</option>
      </optgroup>
      <option v-for="item in loose" :key="item.id" :value="item.id">{{ item.label }}</option>
    </select>
  </div>
</template>

<script setup lang="ts">
/**
 * The prompts a page offers ready-made, above the field they go into.
 *
 * This is the sentence list of Compare -> Voices, generalised (2026-08-17): that
 * page is where the shape comes from, and it runs on this component too, so there
 * is one implementation of it and not two.
 *
 * Every page asks for something else, so the list belongs to the page and not
 * to this component: what is passed in is already in the reader's language, and
 * what comes back out is the entry that was picked. Writing your own stays the
 * other way of filling the field - choosing is an offer, not the only door.
 *
 * The list is the platform's own drop-down (native `<select>`, closes on the
 * choice, options over the row rather than under it), shaped like `.vc-select`
 * in `voice_comparison.vue`. Building an unfolding construction for this is a
 * parallel structure; see Rule #13 and the registry.
 *
 * An entry can fill more than one field - an instrument that subtracts one
 * prompt from another is only demonstrated by a matching SET of them, and
 * offering the three separately would leave it to the reader to guess which
 * three belong together. `fill` therefore carries one string per field, in the
 * order the page lists them, and the page decides where they go.
 *
 * Choosing writes into the field; editing it afterwards is what a field is for,
 * so the choice is dropped as soon as the leading field no longer holds what was
 * chosen - or the offer itself changes under it, which is what happens on Voices
 * when the language does: a sentence written for another language keeps being
 * speakable, but it is no longer attributed to that source.
 *
 * WHERE THE PROVENANCE LINE GOES IS THE PAGE'S DECISION, not this component's.
 * On Voices it stands UNDER the field, because that is what it is about: the
 * sentence that is now in the field. So what leaves here is the chosen entry
 * (`update:chosen`, null when the choice is dropped) and the page draws the line
 * where its own layout puts it.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

interface PromptExample {
  /** Stable id, used as the option's value. */
  id: string
  /** What the entry reads as in the list. For a single field, the prompt itself. */
  label: string
  /** One string per field this entry fills, in the page's own order. */
  fill: string[]
  /** Where it comes from, shown under the list while it is the chosen one. */
  source?: string
  /** Heading this entry is listed under. Entries without one come last. */
  group?: string
}

const props = withDefaults(defineProps<{
  items: PromptExample[]
  /** The text of the leading field, so a typed-over choice can let go. */
  current?: string
  disabled?: boolean
  /** Replaces the standard first line of the list where a page needs its own. */
  label?: string
}>(), {
  current: '',
  disabled: false,
  label: '',
})

const emit = defineEmits<{
  (e: 'pick', item: PromptExample): void
  (e: 'update:chosen', item: PromptExample | null): void
}>()

const { t } = useI18n()

/** Which entry is in the field, or none if it was typed. */
const chosen = ref('')

const labelText = computed(() => props.label || t('promptExamples.label'))

const grouped = computed(() => {
  const names: string[] = []
  for (const item of props.items) {
    if (item.group && !names.includes(item.group)) names.push(item.group)
  }
  return names.map((name) => ({ name, items: props.items.filter((i) => i.group === name) }))
})

const loose = computed(() => props.items.filter((i) => !i.group))

function onChange(id: string) {
  chosen.value = id
  const picked = props.items.find((i) => i.id === id) ?? null
  if (picked) emit('pick', picked)
  emit('update:chosen', picked)
}

function drop() {
  chosen.value = ''
  emit('update:chosen', null)
}

watch(() => props.current, (text) => {
  if (!chosen.value) return
  const picked = props.items.find((i) => i.id === chosen.value)
  if (picked && picked.fill[0] !== text) drop()
})

watch(() => props.items, () => {
  if (chosen.value && !props.items.find((i) => i.id === chosen.value)) drop()
})
</script>

<style scoped>
.prompt-examples {
  width: 100%;
}

/* The platform's list shape. Full width, because the options are prompts and a
   prompt is longer than a word. */
.pe-select {
  width: 100%;
  margin-bottom: 0.5rem;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 0.35rem 0.6rem;
  font-family: inherit;
  font-size: 0.85rem;
}

.pe-select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
