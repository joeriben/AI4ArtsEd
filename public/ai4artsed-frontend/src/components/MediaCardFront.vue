<!--
  MediaCardFront — the front of a generated medium's card: the medium itself,
  and nothing else.

  This was ResonaMediaCard, which turned itself over with its own rotateY, its
  own two faces and its own pair of buttons — a second answer to the question
  FlowCard already answered, and one the contesting surface could not use, so
  that page built a third. The turning, the frame, the bar and the corner are
  FlowCard's now; what is left here is genuinely shared: a medium rendered
  frameless, because the card around it is the frame.

  The front is the medium ALONE. The row of things one can do with it stands
  on the back, in the flow too, where the
  prompt, the model's sheet and the facts of the run already stood — a card that
  turns has a place for them, and a picture that is being looked at is worth
  more unobstructed than a hand's breadth of buttons over it. The box is told
  `actions="none"` for that; the row itself is `MediaActionBar`, drawn once and
  used on both sides of this platform.

  It also carries material that was BROUGHT rather than generated (a favourite
  or a file dropped on the board): `isExecuting` false, no stream, no run.
-->
<template>
  <div class="media-card-front">
    <MediaOutputBox
      :output-image="outputUrl"
      :media-type="mediaType"
      :is-executing="isExecuting"
      :progress="progress"
      :preview-image="previewImage"
      :run-id="runId"
      :is-favorited="isFavorited"
      :model-meta="modelMeta"
      :stage4-duration-ms="stage4DurationMs || 0"
      :mesh-url="meshUrl"
      frame="card"
      actions="none"
      @image-click="emit('image-click', $event)"
    />
    <div v-if="error" class="card-error">{{ t('resonaMediaCard.errorState') }}</div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import MediaOutputBox from '@/components/MediaOutputBox.vue'

defineProps<{
  outputUrl: string | null
  mediaType: string
  runId: string | null
  error?: boolean
  isExecuting: boolean
  progress: number
  previewImage?: string | null
  modelMeta?: Record<string, any> | null
  stage4DurationMs?: number | null
  meshUrl?: string | null
  /**
   * Kept or not. The star itself stands on the back; the front takes this only
   * so the box below can pass it on, and so a caller has ONE place to say it.
   */
  isFavorited?: boolean
}>()

const emit = defineEmits<{
  (e: 'image-click', url: string): void
}>()

const { t } = useI18n()
</script>

<style scoped>
.media-card-front {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.card-error {
  padding: 0.5rem 0.7rem;
  font-size: 0.82rem;
  color: #e08a8a;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
</style>
