<!--
  MediaActionBar — the row of things one can do with a finished medium: keep it,
  hand it on, save it, print it, have it looked at.

  It stood FIVE times inside MediaOutputBox — once per media kind plus the dead
  row of the empty state — with the same buttons, the same paths and the same
  rules; only which of them appeared differed. See
  docs/ELEMENT_STRUCTURE_REGISTRY.md.

  The mark for KEEPING is the STAR, platform-wide. The
  heart it replaces stood only here, and the flow's viewer bar had been drawing
  the star since it was built — its colours come over from there unchanged
  (`#ffb300` on `#6a531c`, `views/x2x_flow.vue`) rather than being invented a
  second time.

  Which buttons a medium carries is a fact about the medium, not a setting: a
  picture can be handed on, printed and looked at; a sound file is kept and
  saved. The analysis asks for itself, because everything it needs — a run and a
  picture — already stands here as a prop.

  `layout` says which way the row runs: standing (`column`) where it hangs over
  a medium, lying (`row`) where it stands in a line of its own, as on the back
  of a card.

  The row can also open a kept run again in the instrument that made it
  (`canRestore`, one uniform icon in the bar). It stood as a text button in
  the corner of the favourites' enlarged view, where it was not seen; it now
  stands right after the star, where handing on stood, which the favourites
  view no longer offers, since one can drag from Favourites straight into Flow.
-->
<template>
  <div class="action-toolbar" :class="[layout, { inactive }]">
    <button
      v-if="showKeep"
      class="action-btn"
      :class="{ favorited: isFavorited }"
      :disabled="inactive || !runId || keepDisabled"
      :title="keepTitle"
      @click="emit('toggle-favorite')"
    >
      <span class="action-icon">
        <svg v-if="isFavorited" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
          <path d="m233-120 65-281L80-590l288-25 112-265 112 265 288 25-218 189 65 281-247-149-247 149Z"/>
        </svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
          <path d="m354-287 126-76 126 77-33-144 111-96-146-13-58-136-58 135-146 13 111 97-33 143ZM233-120l65-281L80-590l288-25 112-265 112 265 288 25-218 189 65 281-247-149-247 149Zm247-350Z"/>
        </svg>
      </span>
    </button>

    <!-- Back to where the run was made, with its setting. Only a surface that
         holds a kept run AND knows its instrument takes it back offers this;
         the instrument decides what of the record it reads. Any kind of
         medium: a kept Canvas workflow goes back as well as a picture. -->
    <button
      v-if="canRestore"
      class="action-btn"
      :disabled="inactive"
      :title="t('gallery.openRun')"
      @click="emit('restore')"
    >
      <span class="action-icon">
        <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
          <path d="M480-400q-33 0-56.5-23.5T400-480q0-33 23.5-56.5T480-560q33 0 56.5 23.5T560-480q0 33-23.5 56.5T480-400Zm0 280q-139 0-241-91.5T122-440h82q14 104 92.5 172T480-200q117 0 198.5-81.5T760-480q0-117-81.5-198.5T480-760q-69 0-129 32t-101 88h110v80H120v-240h80v94q51-64 124.5-99T480-840q75 0 140.5 28.5t114 77q48.5 48.5 77 114T840-480q0 75-28.5 140.5t-77 114q-48.5 48.5-114 77T480-120Z"/>
        </svg>
      </span>
    </button>

    <button
      v-if="showPictureActions && canForward"
      class="action-btn"
      :disabled="inactive"
      :title="forwardTitle || t('mediaOutput.forwardToImageTransform')"
      @click="emit('forward')"
    >
      <span class="action-icon">
        <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
          <path d="M480-480ZM200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h320v80H200v560h560v-280h80v280q0 33-23.5 56.5T760-120H200Zm40-160h480L570-480 450-320l-90-120-120 160Zm480-280v-167l-64 63-56-56 160-160 160 160-56 56-64-63v167h-80Z"/>
        </svg>
      </span>
    </button>

    <button class="action-btn" :disabled="inactive" :title="t('mediaOutput.download')" @click="emit('download')">
      <span class="action-icon">
        <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
          <path d="M480-320 280-520l56-58 104 104v-326h80v326l104-104 56 58-200 200ZM240-160q-33 0-56.5-23.5T160-240v-120h80v120h480v-120h80v120q0 33-23.5 56.5T720-160H240Z"/>
        </svg>
      </span>
    </button>

    <button
      v-if="showPictureActions"
      class="action-btn"
      :disabled="inactive"
      :title="t('mediaOutput.print')"
      @click="emit('print')"
    >
      <span class="action-icon">
        <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
          <path d="M640-640v-120H320v120h-80v-200h480v200h-80Zm-480 80h640-640Zm560 100q17 0 28.5-11.5T760-500q0-17-11.5-28.5T720-540q-17 0-28.5 11.5T680-500q0 17 11.5 28.5T720-460Zm-80 260v-160H320v160h320Zm80 80H240v-160H80v-240q0-51 35-85.5t85-34.5h560q51 0 85.5 34.5T880-520v240H720v160Zm80-240v-160q0-17-11.5-28.5T760-560H200q-17 0-28.5 11.5T160-520v160h80v-80h480v80h80Z"/>
        </svg>
      </span>
    </button>

    <button
      v-if="showPictureActions"
      class="action-btn"
      :disabled="inactive"
      :title="t('mediaOutput.analyze')"
      @click="askForAnalysis"
    >
      <span class="action-icon">
        <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
          <path d="M440-240q116 0 198-81.5T720-520q0-116-82-198t-198-82q-117 0-198.5 82T160-520q0 117 81.5 198.5T440-240Zm0-280Zm0 160q-83 0-147.5-44.5T200-520q28-70 92.5-115T440-680q82 0 146.5 45T680-520q-29 71-93.5 115.5T440-360Zm0-60q55 0 101-26.5t72-73.5q-26-46-72-73t-101-27q-56 0-102 27t-72 73q26 47 72 73.5T440-420Zm0-40q25 0 42.5-17t17.5-43q0-25-17.5-42.5T440-580q-26 0-43 17.5T380-520q0 26 17 43t43 17Zm0 300q-75 0-140.5-28.5t-114-77q-48.5-48.5-77-114T80-520q0-74 28.5-139.5t77-114.5q48.5-49 114-77.5T440-880q74 0 139.5 28.5T694-774q49 49 77.5 114.5T800-520q0 64-21 121t-58 104l159 159-57 56-159-158q-47 37-104 57.5T440-160Z"/>
        </svg>
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAnalysisEventStore } from '@/stores/analysisEvent'
// The kinds that can be kept stand in ONE place (stores/favorites.ts): this
// component decides whether the star is DRAWN, OutputDrawer whether it DOES
// anything, and a second hand-kept list drifted between the two.
import { isKeepableMedia } from '@/stores/favorites'

const props = withDefaults(
  defineProps<{
    mediaType?: string
    /** Without a run there is nothing to keep, and the star says so by staying dim. */
    runId?: string | null
    isFavorited?: boolean
    /**
     * There IS a run and it IS kept, but not by the person looking at it - the
     * favourites strip in `Alle` mode shows everyone's, and the server refuses
     * a foreign delete. Without this the star would be lit and do nothing.
     */
    keepDisabled?: boolean
    /** What handing it on is called where this stands; the platform's wording otherwise. */
    forwardTitle?: string
    /**
     * Whether handing it on is offered at all. It carries a picture to the
     * flow's table; on the flow itself the picture already lies there, and a
     * button that would carry it nowhere is turned off rather than left dead.
     */
    canForward?: boolean
    /**
     * Whether the run can be opened again in the instrument that made it, with
     * its setting. Off unless a surface says so: only the favourites strip
     * holds a run apart from its instrument, and only some instruments read a
     * run back (FooterGallery `backTo`).
     */
    canRestore?: boolean
    /**
     * Nothing has been made yet. The row stands where it will stand, dimmed and
     * deaf, so the surface keeps its shape between the empty state and the
     * first result.
     */
    inactive?: boolean
    layout?: 'column' | 'row'
  }>(),
  {
    mediaType: 'image',
    runId: null,
    isFavorited: false,
    keepDisabled: false,
    forwardTitle: '',
    canForward: true,
    canRestore: false,
    inactive: false,
    layout: 'column',
  },
)

const emit = defineEmits<{
  (e: 'toggle-favorite'): void
  (e: 'restore'): void
  (e: 'forward'): void
  (e: 'download'): void
  (e: 'print'): void
}>()

const { t } = useI18n()
const analysisEventStore = useAnalysisEventStore()

const showKeep = computed(() => props.inactive || isKeepableMedia(props.mediaType))
const showPictureActions = computed(() => props.inactive || props.mediaType === 'image')

const keepTitle = computed(() => {
  if (props.inactive) return t('mediaOutput.saveSoon')
  return props.isFavorited ? t('gallery.unfavorite') : t('gallery.favorite')
})

/**
 * Have the picture looked at. The run id arrives in several shapes on this
 * platform — a bare id, or a path with the id inside it — and only the id is
 * meant.
 */
function askForAnalysis() {
  if (!props.runId || props.mediaType !== 'image') return
  const runId = props.runId.includes('/')
    ? props.runId.match(/(run_[^/]+)/)?.[1] || props.runId
    : props.runId
  analysisEventStore.requestReflection('', '', 'media_output', runId)
}
</script>

<style scoped>
.action-toolbar {
  display: flex;
  gap: 0.3rem;
  padding: 0.3rem;
  background: rgb(var(--surface-1-rgb) / 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 7px;
  transition: all 0.3s ease;
}

.action-toolbar.column { flex-direction: column; }
.action-toolbar.row { flex-direction: row; }

.action-toolbar.inactive {
  opacity: 0.3;
  pointer-events: none;
}

.action-btn {
  width: 29px;
  height: 29px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(var(--surface-2-rgb) / 0.9);
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 5px;
  color: rgba(255, 255, 255, 0.9);
  cursor: pointer;
  transition: all 0.3s ease;
  padding: 0;
}

.action-btn:hover:not(:disabled) {
  background: rgba(102, 126, 234, 0.3);
  border-color: rgba(102, 126, 234, 0.8);
  transform: scale(1.05);
}

.action-btn:active:not(:disabled) { transform: scale(0.95); }

.action-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* The kept state, in the colours the flow's viewer bar has carried since it
   was built. */
.action-btn.favorited {
  background: rgb(var(--surface-2-rgb) / 0.9);
  border-color: #6a531c;
  color: #ffb300;
}

.action-btn.favorited:hover:not(:disabled) {
  background: rgba(255, 179, 0, 0.18);
  border-color: #ffb300;
}

.action-icon {
  font-size: 0.9rem;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-icon svg {
  width: 12px;
  height: 12px;
}
</style>
