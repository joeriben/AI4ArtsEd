<script setup lang="ts">
/**
 * The codes of a course's places, large, for a projector (2026-11-14): the
 * group reads the code of its place from the wall. The board stands in
 * OverlayFrame at the size `screen` and is opened from the box of codes the
 * course page shows once (views/educator/CourseEditor.vue). It shows those
 * codes and no others: the platform keeps none (lab/place_codes.py). Over
 * the codes stand the course's name and where a code is entered, as on the
 * printed slips.
 *
 * The size of the codes is computed from the window and the number of places
 * (lib/placeCodesBoard.ts), and the lines and the border of a tile are set
 * from the same numbers; in the browser's fullscreen mode the window is the
 * screen.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { IssuedPlace } from '@/services/labApi'
import {
  BOARD_GAP,
  BOARD_HEAD,
  BOARD_PAD,
  CODE_LINE,
  PLACE_LINE,
  PLACE_SIZE,
  TILE_BORDER,
  boardLayout,
  signInAddress,
} from '@/lib/placeCodesBoard'

const props = defineProps<{
  courseName: string
  places: IssuedPlace[]
}>()

const { t } = useI18n()

const width = ref(window.innerWidth)
const height = ref(window.innerHeight)

function measureWindow(): void {
  width.value = window.innerWidth
  height.value = window.innerHeight
}

const layout = computed(() => boardLayout(props.places.length, width.value, height.value))

const signIn = computed(() => t('educator.slipSignIn', { address: signInAddress() }))

const boardStyle = computed(() => ({
  '--board-pad': `${BOARD_PAD}px`,
  '--board-head': `${BOARD_HEAD}px`,
  '--board-gap': `${BOARD_GAP}px`,
  '--board-cols': String(layout.value.cols),
  '--code-size': `${layout.value.size}px`,
  '--code-line': String(CODE_LINE),
  '--place-size': `${layout.value.size * PLACE_SIZE}px`,
  '--place-line': String(PLACE_LINE),
  '--tile-border': `${TILE_BORDER}px`,
}))

onMounted(() => window.addEventListener('resize', measureWindow))
onUnmounted(() => window.removeEventListener('resize', measureWindow))
</script>

<template>
  <div class="codes-board" :style="boardStyle">
    <div class="board-head">
      <strong class="board-course">{{ courseName }}</strong>
      <span class="board-signin">{{ signIn }}</span>
    </div>
    <ul class="board-grid">
      <li v-for="p in places" :key="p.number" class="board-tile">
        <span class="board-place">{{ t('educator.placeLabel', { n: p.number }) }}</span>
        <code class="board-code">{{ p.code }}</code>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.codes-board {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: var(--board-pad);
  background: var(--bg-base);
  color: rgba(255, 255, 255, 0.9);
}

/* The head row keeps clear of the frame's × at its end (36 px wide, 2 rem
   from the frame's edge, 1.5 rem from its top). Where the row grows short,
   the course's name yields and where a code is entered stays whole. */
.board-head {
  flex: 0 0 var(--board-head);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2.4em;
  padding-inline: 4rem;
  font-size: 1.25rem;
  color: rgba(255, 255, 255, 0.7);
  overflow: hidden;
  white-space: nowrap;
}

.board-course {
  color: #fff;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
}

.board-signin {
  flex-shrink: 0;
}

/* Below 900 px a row holds the course's name beside where a code is entered
   no longer: the two stand one over the other in smaller type, at the foot of
   the row, which keeps its height. The lower line passes below the ×; the
   upper one keeps 3 rem from either side, clear of it. A line wider than the
   window ends in an ellipsis. */
@media (max-width: 899px) {
  .board-head {
    flex-direction: column;
    justify-content: flex-end;
    gap: 3px;
    padding-inline: 0;
    font-size: 15px;
    line-height: 1.3;
  }

  .board-course {
    max-width: calc(100% - 6rem);
  }

  .board-signin {
    flex-shrink: 1;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.board-grid {
  flex: 1;
  min-height: 0;
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(var(--board-cols), minmax(0, 1fr));
  grid-auto-rows: minmax(0, 1fr);
  gap: var(--board-gap);
}

.board-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 0;
  border: var(--tile-border) solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
}

.board-place {
  font-size: var(--place-size);
  line-height: var(--place-line);
  color: rgba(255, 255, 255, 0.6);
}

/* The spacing after the last character is given back at the start, so the
   code stands in the middle of its tile. */
.board-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: var(--code-size);
  letter-spacing: 0.12em;
  padding-inline-start: 0.12em;
  line-height: var(--code-line);
  color: #4caf50;
}
</style>
