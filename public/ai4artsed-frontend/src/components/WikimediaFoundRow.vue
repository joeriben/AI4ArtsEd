<!--
  WikimediaFoundRow — the found-images row under a comparison grid.

  What it is: one to three pictures that already existed, looked up in Wikimedia
  Commons with a search term derived from the same prompt the models were given.
  They are NOT a fourth model and NOT a correct answer; the closing line says so
  in as many words, and the licence line at each tile names who made the picture.

  Where the pictures come from: our own backend (`/api/commons/image/...`). The
  raw upload.wikimedia.org URL never reaches the browser, so opening the page
  does not connect any participant to a third-party host.

  Two of the empty states are results, not errors: a prompt that only says "make
  it brighter" names no motif, and a term that finds nothing finds nothing. The
  third, `error`, is the only one that speaks about us — an outage must never be
  shown to a room as a finding about a participant's prompt.
-->
<template>
  <section v-if="state !== 'idle'" class="found-row">
    <header class="found-head">
      <span class="found-title">{{ t('compare.found.title') }}</span>
      <span class="found-source">{{ t('compare.found.source') }}</span>
    </header>

    <p v-if="state === 'loading'" class="found-note found-note--waiting">
      {{ t('compare.found.loading') }}
    </p>

    <p v-else-if="state === 'no_motif'" class="found-note">
      {{ t('compare.found.noMotif') }}
    </p>

    <template v-else-if="state === 'nothing_found'">
      <div v-if="term" class="found-term">
        <span class="found-term-label">{{ t('compare.found.searchTerm') }}</span>
        <span class="found-term-value">{{ term }}</span>
      </div>
      <p class="found-note">{{ t('compare.found.nothingFound') }}</p>
    </template>

    <p v-else-if="state === 'error'" class="found-note">
      {{ t('compare.found.unavailable') }}
    </p>

    <template v-else>
      <div class="found-term">
        <span class="found-term-label">{{ t('compare.found.searchTerm') }}</span>
        <span class="found-term-value">{{ term }}</span>
      </div>

      <div class="found-grid">
        <a
          v-for="image in images"
          :key="image.thumb_proxy"
          class="found-tile"
          :href="image.file_page"
          target="_blank"
          rel="noopener noreferrer"
          :title="image.title"
        >
          <div class="found-thumb">
            <!-- A thumbnail that fails says so. It arrived as a broken-image
                 icon until 2026-09-08, when Commons moved its thumbnails to a
                 host the proxy's allowlist refused: three tiles, three browser
                 icons, and nothing on the surface naming the failure. -->
            <img
              v-if="!failed.has(image.thumb_proxy)"
              :src="baseUrl + image.thumb_proxy"
              :alt="image.title"
              loading="lazy"
              @error="failed.add(image.thumb_proxy)"
            />
            <span v-else class="found-thumb-out">{{ t('compare.found.thumbUnavailable') }}</span>
          </div>
          <div class="found-meta">
            <!-- Deliberately repeated at the tile: a picture that travels out of
                 this row (screenshot, projector) must carry what was asked for. -->
            <span class="found-tile-term">{{ term }}</span>
            <!-- Author and licence WRAP, and the author line is always there.
                 Cutting them with an ellipsis, or leaving the line out when the
                 file names nobody, would drop the attribution a CC BY-SA file is
                 shown on condition of. -->
            <span class="found-author" :title="image.author">
              {{ image.author || t('compare.found.authorUnknown') }}
            </span>
            <span class="found-licence" :title="image.licence">
              {{ image.licence || t('compare.found.licenceUnknown') }}
            </span>
            <!-- The categories the file carries. They are here so that a
                 machine-generated file the exclusion missed is visible in the
                 room instead of passing silently: the licence line reads
                 "Public domain" for those, and says nothing. -->
            <span
              v-if="image.categories && image.categories.length"
              class="found-categories"
              :title="image.categories.join(' · ')"
            >{{ image.categories.slice(0, 3).join(' · ') }}</span>
          </div>
        </a>
      </div>

      <p class="found-note">{{ t('compare.found.horizon') }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { apiBase } from '@/services/labApi'

export interface FoundImage {
  title: string
  thumb_proxy: string
  width: number
  height: number
  author: string
  licence: string
  file_page: string
  categories: string[]
}

export type FoundState = 'idle' | 'loading' | 'ok' | 'no_motif' | 'nothing_found' | 'error'

// `term` and `images` are declared optional, not required-with-a-default: Vue
// warns "Missing required prop" on a required key even when a default exists,
// so the defaults would be unusable by any second consumer.
withDefaults(defineProps<{
  state: FoundState
  term?: string | null
  images?: FoundImage[]
}>(), {
  term: null,
  images: () => [],
})

const { t } = useI18n()

// Which thumbnails came back as a failure. Keyed on the proxy path, which is
// what identifies a tile here.
const failed = reactive(new Set<string>())

// In dev the Vue server and the DevServer are two origins; in production the
// same Flask process serves both, so the prefix is empty.
const baseUrl = computed(() => apiBase())
</script>

<style scoped>
.found-row {
  margin-top: 1.75rem;
  padding-top: 1.25rem;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}

.found-head {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  margin-bottom: 0.5rem;
}

.found-title {
  font-size: 0.85rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
}

.found-source {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.5);
}

.found-term {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.found-term-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(255, 255, 255, 0.45);
}

.found-term-value {
  font-size: 0.85rem;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: rgba(129, 199, 132, 0.95);
}

/* Same three columns as the model grid above, so a found picture sits under a
   generated one instead of beside it. The tracks line up exactly; the generated
   picture sits 13 px inside its track, because it stands in a comparison column
   and this tile does not. */
.found-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1rem;
}

.found-tile {
  display: flex;
  flex-direction: column;
  min-width: 0;
  text-decoration: none;
  border-radius: 10px;
  overflow: hidden;
  background: rgb(var(--surface-2-rgb) / 0.9);
  border: 1px solid rgba(255, 255, 255, 0.12);
  transition: border-color 0.2s ease;
}

.found-tile:hover {
  border-color: rgba(255, 255, 255, 0.3);
}

/* The picture is absolutely placed inside the square, not sized by height:100%.
   A percentage height against an auto-height parent gives the box a definite
   content height, and aspect-ratio then loses to it — a portrait file made its
   tile 443 px tall next to two of 332, so the found pictures no longer lined up
   with the generated ones above them. */
.found-thumb {
  position: relative;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  background: rgb(var(--surface-1-rgb) / 0.6);
}

/* Where the picture stays out. The line sits in the square the picture would
   have filled, so the row keeps its columns. */
.found-thumb-out {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.9rem;
  text-align: center;
  font-size: 0.72rem;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.45);
}

.found-thumb img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.found-meta {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.5rem 0.6rem 0.6rem;
  min-width: 0;
}

.found-tile-term {
  font-size: 0.72rem;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: rgba(129, 199, 132, 0.85);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.found-author {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.75);
  overflow-wrap: anywhere;
}

.found-licence {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.45);
  overflow-wrap: anywhere;
}

.found-categories {
  margin-top: 0.15rem;
  font-size: 0.65rem;
  line-height: 1.35;
  color: rgba(255, 255, 255, 0.35);
  overflow-wrap: anywhere;
}

.found-note {
  margin: 0.85rem 0 0;
  font-size: 0.75rem;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.55);
}

.found-note--waiting {
  margin-top: 0;
}

/* A CONTAINER query, and at the same width as the model grid above (see
   `.mc-models` in views/compare/model_comparison.vue): both grids live inside
   `.cmp-page`, which is the container, and a window query here would stack the
   found pictures at window widths where the generated ones above still stand
   three across — the two rows are written to correspond column by column, so
   they have to break at the same moment. */
@container (max-width: 470px) {
  .found-grid {
    grid-template-columns: 1fr;
  }
}
</style>
