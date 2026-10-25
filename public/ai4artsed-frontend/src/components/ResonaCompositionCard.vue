<!--
  The front of a composition card: the Bild+Ton — a still you can play. The
  first frame is the image; pressing play sounds the coupled audio. Deliberately
  NOT framed as a video: it is a sounded still, its own kind of artifact.

  The card around it, and the turning, are FlowCard's; the provenance stands on
  its back (ResonaCompositionCardBack).
-->
<template>
  <div class="bildton">
    <video
      class="bildton-media"
      :src="url"
      :poster="posterUrl ?? undefined"
      controls
      playsinline
      preload="metadata"
    />
    <span class="bildton-badge">{{ badgeText }}</span>
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
  url: string
  runId: string | null
  operation: string
  composedFrom: ComposedSource[]
}>()

const { t } = useI18n()

// Poster = the source still, shown instantly before the <video> has loaded its
// own first frame. Taken from the composed_from provenance (the image role) —
// the same still that is baked into the frame, so the poster and the frame match.
const posterUrl = computed<string | null>(() => {
  const img = props.composedFrom?.find(s => s.role === 'image')
  return img ? `/api/media/image/${img.run_id}/0` : null
})

// Badge names the KIND of composition: a still+sound is a Bild+Ton, a video+sound
// a Video+Ton. Same card, honest label.
const badgeText = computed(() =>
  props.operation === 'video_plus_audio'
    ? t('resonaCompositionCard.badgeVideo')
    : t('resonaCompositionCard.badge')
)
</script>

<style scoped>
.bildton {
  position: relative;
  width: 100%;
}

.bildton-media {
  display: block;
  width: 100%;
  border-radius: 12px;
  background: var(--bg-base);
}

.bildton-badge {
  position: absolute;
  top: 0.6rem;
  left: 0.6rem;
  padding: 0.2rem 0.6rem;
  font-size: 0.72rem;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.92);
  background: rgb(var(--bg-base-rgb) / 0.66);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 999px;
  pointer-events: none;
}
</style>
