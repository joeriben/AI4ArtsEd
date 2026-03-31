<template>
  <div class="footer-gallery" :class="{ expanded: isExpanded }">
    <!-- Toggle Bar -->
    <div class="toggle-bar" @click="toggleGallery">
      <div class="toggle-content">
        <span class="toggle-icon">
          <svg v-if="!isExpanded" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M480-528 296-344l-56-56 240-240 240 240-56 56-184-184Z"/>
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
            <path d="M480-344 240-584l56-56 184 184 184-184 56 56-240 240Z"/>
          </svg>
        </span>
        <span class="toggle-text">
          {{ $t('gallery.title') }}
          <span v-if="totalFavorites > 0" class="badge">{{ totalFavorites }}</span>
        </span>

        <!-- View Mode Toggle (Session 145: Per-user favorites - 2-Feld-Switch) -->
        <div class="view-mode-switch" @click.stop>
          <button
            class="switch-option"
            :class="{ active: viewMode === 'per_user' }"
            @click="setViewModePerUser"
            title="Nur meine Favoriten"
          >
            <svg xmlns="http://www.w3.org/2000/svg" height="14" width="14" viewBox="0 -960 960 960">
              <path
                d="M480-480q-66 0-113-47t-47-113q0-66 47-113t113-47q66 0 113 47t47 113q0 66-47 113t-113 47ZM160-160v-112q0-34 17.5-62.5T224-378q62-31 126-46.5T480-440q66 0 130 15.5T736-378q29 15 46.5 43.5T800-272v112H160Z"
              />
            </svg>
            <span>Meine</span>
          </button>
          <button
            class="switch-option"
            :class="{ active: viewMode === 'global' }"
            @click="setViewModeGlobal"
            title="Alle Favoriten"
          >
            <svg xmlns="http://www.w3.org/2000/svg" height="14" width="14" viewBox="0 -960 960 960">
              <path
                d="M0-240v-63q0-43 44-70t116-27q13 0 25 .5t23 2.5q-14 21-21 44t-7 48v65H0Zm240 0v-65q0-32 17.5-58.5T307-410q32-20 76.5-30t96.5-10q53 0 97.5 10t76.5 30q32 20 49 46.5t17 58.5v65H240Zm540 0v-65q0-26-6.5-49T754-397q11-2 22.5-2.5t23.5-.5q72 0 116 26.5t44 70.5v63H780Z"
              />
            </svg>
            <span>Alle</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Gallery Content -->
    <Transition name="gallery-slide">
      <div v-if="isExpanded" class="gallery-content">
        <!-- Loading State -->
        <div v-if="isLoading" class="gallery-loading">
          <span class="spinner"></span>
          {{ $t('common.loading') }}
        </div>

        <!-- Empty State -->
        <div v-else-if="favorites.length === 0" class="gallery-empty">
          <span class="empty-icon">
            <svg xmlns="http://www.w3.org/2000/svg" height="48" viewBox="0 -960 960 960" width="48" fill="currentColor">
              <path d="m480-120-58-52q-101-91-167-157T150-447.5Q111-500 95.5-544T80-634q0-94 63-157t157-63q52 0 99 22t81 62q34-40 81-62t99-22q94 0 157 63t63 157q0 46-15.5 90T810-447.5Q771-395 705-329T538-172l-58 52Z"/>
            </svg>
          </span>
          <p>{{ $t('gallery.empty') }}</p>
        </div>

        <!-- Favorites Grid -->
        <div v-else class="gallery-grid" ref="galleryGridRef">
          <div
            v-for="favorite in favorites"
            :key="favorite.run_id"
            class="gallery-item"
            :class="{ 'not-found': !favorite.exists }"
          >
            <!-- Thumbnail -->
            <div class="thumbnail-container" @click="handleItemClick(favorite)">
              <img
                v-if="favorite.media_type === 'image'"
                :src="favorite.thumbnail_url"
                :alt="favorite.input_preview || 'Favorite'"
                class="thumbnail"
                loading="lazy"
              />
              <div v-else class="thumbnail-placeholder">
                <span class="media-icon">{{ getMediaIcon(favorite.media_type) }}</span>
              </div>

              <!-- Overlay with info -->
              <div class="thumbnail-overlay">
                <span v-if="favorite.input_preview" class="preview-text">
                  {{ favorite.input_preview }}
                </span>
              </div>
            </div>

            <!-- Actions -->
            <div class="item-actions">
              <!-- Continue (only for images) -->
              <button
                v-if="favorite.media_type === 'image'"
                class="action-btn continue-btn"
                :title="$t('gallery.continue')"
                @click="handleContinue(favorite)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" height="16" viewBox="0 -960 960 960" width="16" fill="currentColor">
                  <path d="M360-240q-33 0-56.5-23.5T280-320v-480q0-33 23.5-56.5T360-880h360q33 0 56.5 23.5T800-800v480q0 33-23.5 56.5T720-240H360Zm0-80h360v-480H360v480ZM200-80q-33 0-56.5-23.5T120-160v-560h80v560h440v80H200Zm160-240v-480 480Z"/>
                </svg>
              </button>

              <!-- Restore -->
              <button
                class="action-btn restore-btn"
                :title="$t('gallery.restore')"
                @click="handleRestore(favorite)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" height="16" viewBox="0 -960 960 960" width="16" fill="currentColor">
                  <path d="M480-120q-138 0-240.5-91.5T122-440h82q14 104 92.5 172T480-200q117 0 198.5-81.5T760-480q0-117-81.5-198.5T480-760q-69 0-129 32t-101 88h110v80H120v-240h80v94q51-64 124.5-99T480-840q75 0 140.5 28.5t114 77q48.5 48.5 77 114T840-480q0 75-28.5 140.5t-77 114q-48.5 48.5-114 77T480-120Zm112-192L440-464v-216h80v184l128 128-56 56Z"/>
                </svg>
              </button>

              <!-- Remove -->
              <button
                class="action-btn remove-btn"
                :title="$t('gallery.unfavorite')"
                @click="handleRemove(favorite)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" height="16" viewBox="0 -960 960 960" width="16" fill="currentColor">
                  <path d="m256-200-56-56 224-224-224-224 56-56 224 224 224-224 56 56-224 224 224 224-56 56-224-224-224 224Z"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useFavoritesStore, type FavoriteItem } from '@/stores/favorites'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { useDeviceId } from '@/composables/useDeviceId'

const router = useRouter()
const favoritesStore = useFavoritesStore()
const { copy: copyToClipboard } = useAppClipboard()
const galleryGridRef = ref<HTMLElement | null>(null)

// Computed from store
const favorites = computed(() => favoritesStore.favorites)
const totalFavorites = computed(() => favoritesStore.totalFavorites)
const isLoading = computed(() => favoritesStore.isLoading)
const isExpanded = computed(() => favoritesStore.isGalleryExpanded)
const viewMode = computed(() => favoritesStore.viewMode)  // Session 145

const currentDeviceId = ref(useDeviceId())

// Actions
function toggleGallery() {
  favoritesStore.toggleGallery()
}

// Session 145: Set view mode handlers
function setViewModePerUser() {
  if (viewMode.value !== 'per_user') {
    favoritesStore.setViewMode('per_user', currentDeviceId.value)
  }
}

function setViewModeGlobal() {
  if (viewMode.value !== 'global') {
    favoritesStore.setViewMode('global', currentDeviceId.value)
  }
}

function getMediaIcon(mediaType: string): string {
  const icons: Record<string, string> = {
    image: 'IMG',
    video: 'VID',
    audio: 'AUD',
    music: 'MUS',
    '3d': '3D',
    midi: 'MID',
    p5: 'P5',
    sonicpi: 'SPI',
    text: 'TXT'
  }
  return icons[mediaType] || '—'
}

function handleItemClick(favorite: FavoriteItem) {
  if (favorite.media_type === 'image') {
    // Open image in lightbox or navigate
    console.log('[FooterGallery] Item clicked:', favorite.run_id)
  }
}

function handleContinue(favorite: FavoriteItem) {
  // Simple copy: User can paste in I2I input
  copyToClipboard(favorite.thumbnail_url)
  console.log('[FooterGallery] Image URL copied to clipboard:', favorite.thumbnail_url)
}

async function handleRestore(favorite: FavoriteItem) {
  console.log('[FooterGallery] Restore session:', favorite.run_id)

  const restoreData = await favoritesStore.getRestoreData(favorite.run_id)
  if (!restoreData) {
    console.error('[FooterGallery] Failed to get restore data')
    return
  }

  // Set restore data in store (reactive - views watch this)
  favoritesStore.setRestoreData(restoreData)
  console.log('[FooterGallery] Restore data set in store:', Object.keys(restoreData))

  // Navigate to target view (watcher will process restore)
  const targetView = restoreData.target_view || 'text-transformation'
  router.push(`/${targetView}`)
}

async function handleRemove(favorite: FavoriteItem) {
  console.log('[FooterGallery] Remove favorite:', favorite.run_id)
  await favoritesStore.removeFavorite(favorite.run_id, currentDeviceId.value)  // Session 145
}

// Load favorites on mount (Session 145: Pass device_id)
onMounted(() => {
  favoritesStore.loadFavorites(currentDeviceId.value)
})
</script>

<style scoped>
/* ============================================================================
   Footer Gallery Container
   ============================================================================ */

.footer-gallery {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 950;
  background: rgba(10, 10, 10, 0.99);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  transition: transform 0.3s ease;
}

/* ============================================================================
   Toggle Bar
   ============================================================================ */

.toggle-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: var(--footer-collapsed-height);
  padding: 0 1rem;
  cursor: pointer;
  transition: background 0.2s ease;
}

.toggle-bar:hover {
  background: rgba(255, 255, 255, 0.05);
}

.toggle-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.875rem;
}

.toggle-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.toggle-icon svg {
  width: 20px;
  height: 20px;
  fill: currentColor;
}

.toggle-text {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.badge {
  background: rgba(76, 175, 80, 0.3);
  color: #4CAF50;
  padding: 0.125rem 0.5rem;
  border-radius: 10px;
  font-size: 0.75rem;
  font-weight: 600;
}

/* View Mode Switch (Session 145: 2-Feld-Switch) */
.view-mode-switch {
  display: flex;
  gap: 0;
  margin-left: auto;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 6px;
  padding: 2px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.switch-option {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.switch-option:hover {
  color: rgba(255, 255, 255, 0.8);
  background: rgba(255, 255, 255, 0.05);
}

.switch-option.active {
  background: rgba(102, 126, 234, 0.4);
  color: rgba(255, 255, 255, 1);
  font-weight: 600;
}

.switch-option svg {
  fill: currentColor;
  flex-shrink: 0;
}

.switch-option span {
  font-weight: inherit;
}

/* ============================================================================
   Gallery Content
   ============================================================================ */

.gallery-content {
  max-height: 140px; /* Reduziert von 180px um weniger Output zu verdecken */
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0.5rem 1rem 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

/* Loading & Empty States */
.gallery-loading,
.gallery-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  color: rgba(255, 255, 255, 0.5);
  gap: 0.75rem;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: #4CAF50;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-icon svg {
  fill: rgba(255, 255, 255, 0.3);
}

.gallery-empty p {
  margin: 0;
  font-size: 0.875rem;
}

/* ============================================================================
   Gallery Grid (Horizontal Scroll)
   ============================================================================ */

.gallery-grid {
  display: flex;
  gap: 0.75rem;
  padding-bottom: 0.5rem;
}

/* Gallery Item */
.gallery-item {
  flex: 0 0 auto;
  width: 100px; /* Reduziert von 120px */
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.gallery-item.not-found {
  opacity: 0.5;
}

/* Thumbnail Container */
.thumbnail-container {
  position: relative;
  width: 100px; /* Reduziert von 120px */
  height: 70px; /* Reduziert von 90px */
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  background: rgba(30, 30, 30, 0.8);
  border: 2px solid rgba(255, 255, 255, 0.1);
  transition: all 0.2s ease;
}

.thumbnail-container:hover {
  border-color: rgba(102, 126, 234, 0.5);
  transform: translateY(-2px);
}

.thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumbnail-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(40, 40, 40, 0.9);
}

.media-icon {
  font-size: 2rem;
}

/* Thumbnail Overlay */
.thumbnail-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 0.25rem 0.5rem;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.8));
  opacity: 0;
  transition: opacity 0.2s ease;
}

.thumbnail-container:hover .thumbnail-overlay {
  opacity: 1;
}

.preview-text {
  font-size: 0.625rem;
  color: rgba(255, 255, 255, 0.9);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Item Actions */
.item-actions {
  display: flex;
  gap: 0.25rem;
  justify-content: center;
}

.action-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(30, 30, 30, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover {
  transform: scale(1.1);
}

.action-btn svg {
  width: 16px;
  height: 16px;
  fill: currentColor;
}

/* Continue Button */
.continue-btn:hover {
  background: rgba(102, 126, 234, 0.3);
  border-color: rgba(102, 126, 234, 0.5);
  color: #667eea;
}

/* Restore Button */
.restore-btn:hover {
  background: rgba(76, 175, 80, 0.3);
  border-color: rgba(76, 175, 80, 0.5);
  color: #4CAF50;
}

/* Remove Button */
.remove-btn:hover {
  background: rgba(244, 67, 54, 0.3);
  border-color: rgba(244, 67, 54, 0.5);
  color: #f44336;
}

/* ============================================================================
   Animations
   ============================================================================ */

.gallery-slide-enter-active,
.gallery-slide-leave-active {
  transition: all 0.3s ease;
}

.gallery-slide-enter-from,
.gallery-slide-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}

/* ============================================================================
   Responsive
   ============================================================================ */

@media (max-width: 768px) {
  .footer-gallery {
    left: 0;
  }

  .gallery-content {
    max-height: 120px;
    padding: 0.5rem;
  }

  .gallery-item {
    width: 80px;
  }

  .thumbnail-container {
    width: 80px;
    height: 60px;
  }

  .action-btn {
    width: 24px;
    height: 24px;
  }

  .action-btn svg {
    width: 14px;
    height: 14px;
  }
}
</style>
