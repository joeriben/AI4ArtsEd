<!--
  The back of a composition card: why Resona held these two together, and which
  two artifacts they were — provenance, not a prompt (post-production composes,
  it does not generate).

  It used to be a face of ResonaCompositionCard, which turned itself over with
  its own rotateY, its own pair of buttons and its own copy of the backface
  handling — the third such copy in the workshop. The turning is FlowCard's now
  (no parallel structures); what is left here is the content.
-->
<template>
  <div class="cb">
    <div class="cb-label">{{ t('resonaCompositionCard.motivation') }}</div>
    <p class="cb-motivation">{{ motivation || t('resonaCompositionCard.motivationMissing') }}</p>
    <div class="cb-label">{{ t('resonaCompositionCard.composedFrom') }}</div>
    <ul class="cb-sources">
      <li v-for="src in composedFrom" :key="src.run_id">
        <span class="src-role">{{ roleLabel(src.role) }}</span>
        <span class="src-run">{{ src.run_id }}</span>
      </li>
    </ul>
    <div class="cb-meta">
      <span>{{ operation }}</span>
      <span>{{ t('resonaCompositionCard.timestamp') }}: {{ timeText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

interface ComposedSource {
  role: string
  run_id: string
  type: string
}

const props = defineProps<{
  operation: string
  motivation: string | null
  composedFrom: ComposedSource[]
  createdAt: number
}>()

const { t } = useI18n()

function roleLabel(role: string): string {
  if (role === 'image') return t('resonaCompositionCard.roleImage')
  if (role === 'video') return t('resonaCompositionCard.roleVideo')
  if (role === 'audio') return t('resonaCompositionCard.roleSound')
  return role
}

const timeText = computed(() =>
  new Date(props.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
)
</script>

<style scoped>
.cb {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.7rem 0.9rem;
  color: rgba(230, 230, 230, 0.95);
}
.cb-label {
  margin-top: 0.5rem;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(230, 230, 230, 0.5);
}
.cb-label:first-child { margin-top: 0; }
.cb-motivation { margin: 0; font-size: 0.95rem; line-height: 1.55; }
.cb-sources {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.cb-sources li { display: flex; gap: 0.6rem; font-size: 0.82rem; line-height: 1.4; }
.src-role { min-width: 3.2rem; color: rgba(230, 230, 230, 0.55); }
.src-run { color: rgba(230, 230, 230, 0.85); word-break: break-all; }
.cb-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 1rem;
  margin-top: 0.6rem;
  font-size: 0.75rem;
  color: rgba(230, 230, 230, 0.5);
}
</style>
