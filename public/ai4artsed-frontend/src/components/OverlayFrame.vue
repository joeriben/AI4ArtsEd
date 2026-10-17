<template>
  <!-- THE frame for a layer over the page. The Documentation stood in it from
       the start; since 2026-09-17 the Settings stand in it too, so the gear no
       longer leaves the page (a run, a filled field, a position in the lab stay
       where they are, and closing the layer is standing on them again).

       Dark ground with a blur, a click on the ground closes, Escape closes,
       `<Teleport to="body">`, z-index 2000. Two sizes: `reading` (800 px wide,
       90 vh high, the Documentation) and `full` (the window minus 1 rem on each
       side, the Settings, whose tables keep the width they had as a page).
       With a `title` the frame draws its head row (title and ×); without one
       the content brings its own head, and only the × stands in the corner. -->
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="modelValue" class="modal-overlay" @click="close">
        <div class="modal-container" :class="{ full: size === 'full' }" @click.stop>
          <div v-if="title" class="modal-header">
            <h1>{{ title }}</h1>
            <button class="modal-close" @click="close" :title="$t('common.back')">×</button>
          </div>
          <button v-else class="modal-close modal-close-corner" @click="close" :title="$t('common.back')">×</button>
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: boolean
  title?: string
  size?: 'reading' | 'full'
}>(), {
  title: '',
  size: 'reading',
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

function close() {
  emit('update:modelValue', false)
}

function handleEscape(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.modelValue) {
    close()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleEscape)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscape)
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
  overflow-y: auto;
}

.modal-container {
  position: relative;
  background: var(--bg-base);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  max-width: 800px;
  width: 100%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  /* the content keeps to the rounded corners (the Settings paint their own
     ground right up to the edge) */
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-container.full {
  max-width: none;
  max-height: none;
  height: 100%;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}

.modal-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: #ffffff;
  margin: 0;
}

.modal-close {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.3s ease;
}

.modal-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.9);
}

/* without a head row: the × where the head row would have put it, over
   whatever head the content brings; clear of a classic scrollbar. */
.modal-close-corner {
  position: absolute;
  top: 1.5rem;
  inset-inline-end: 2rem;
  z-index: 1;
}

/* Modal Fade Transition */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-active .modal-container,
.modal-fade-leave-active .modal-container {
  transition: transform 0.3s ease;
}

.modal-fade-enter-from .modal-container,
.modal-fade-leave-to .modal-container {
  transform: scale(0.95);
}

/* Responsive */
@media (max-width: 768px) {
  .modal-container {
    max-height: 95vh;
  }

  .modal-container.full {
    max-height: none;
  }

  .modal-header {
    padding: 1rem 1.5rem;
  }

  .modal-header h1 {
    font-size: 1.25rem;
  }
}
</style>
