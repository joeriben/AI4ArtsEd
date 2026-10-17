import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import type { InstrumentRun } from '@/composables/useLatentLabRecorder'

/**
 * Pinia Store for Footer Gallery Favorites
 *
 * Manages:
 * - Favorites list (persisted on backend)
 * - Gallery expand/collapse state
 * - Favorite toggle actions
 * - Restore data fetching for session restoration
 */

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

/** Favorite item from backend */
export interface FavoriteItem {
  run_id: string
  device_id?: string  // Per-user favorites (optional for backward compat)
  added_at: string
  thumbnail_url: string
  media_type:
    | 'image'
    | 'audio'
    | 'video'
    | 'music'
    | 'composition'
    | 'text'
    | '3d'
    | 'midi'
    | 'p5'
    | 'tonejs'
    | 'sonicpi'
    | 'canvas'
  user_id: string
  user_note: string
  source_view?: string  // Vue route path, e.g. 'surrealizer', 'text-transformation'
  // Enriched by backend
  exists?: boolean
  schema?: string
  timestamp?: string
  input_preview?: string
  /**
   * The picture's own measurements, read off the file by the listing (images
   * only, and absent where it could not be read). What they are for: a surface
   * that opens the picture large can hold its place before the file is there.
   */
  width?: number
  height?: number
}

/** Response from GET /api/favorites */
interface FavoritesResponse {
  favorites: FavoriteItem[]
  total: number
  mode: 'global' | 'per_user'
}

/** Response from POST /api/favorites */
interface AddFavoriteResponse {
  success: boolean
  favorite: FavoriteItem
  total: number
}

/** Response from DELETE /api/favorites/{run_id} */
interface RemoveFavoriteResponse {
  success: boolean
  run_id: string
  total: number
}

/** Media output data for restore */
/**
 * The kinds a run can be kept as. The star is drawn where this says so and acts
 * where this says so: with two separate lists a widened one drew a star that
 * the other refused to honour, silently.
 *
 * A sketch is kept as its runtime (`p5`/`tonejs`) because that is what the run
 * holds; a composition is its own kind because it is served from its own route.
 * `text`, `3d`, `midi` and `sonicpi` are left out: no surface offers the star
 * for them yet.
 *
 * A Canvas workflow is kept as itself (`canvas`): the board,
 * not anything it made. The Canvas keeps it as a run of its own that holds the
 * workflow file (`POST /api/canvas/keep`), because a favourite is a run.
 */
export const KEEPABLE_MEDIA: Array<FavoriteItem['media_type']> = [
  'image',
  'video',
  'audio',
  'music',
  'composition',
  'p5',
  'tonejs',
  'canvas',
]

export function isKeepableMedia(kind: string): kind is FavoriteItem['media_type'] {
  return (KEEPABLE_MEDIA as string[]).includes(kind)
}

export interface MediaOutput {
  type: string
  filename: string
  url: string
  metadata: Record<string, unknown>
}

/** Models used at each pipeline stage */
export interface ModelsUsed {
  stage1_safety?: string
  stage2_interception?: string
  stage3_translation?: string
  stage3_safety?: string
  stage4_output?: string
  context_translation?: string
}

/** Response from GET /api/favorites/{run_id}/restore */
export interface RestoreData {
  run_id: string
  schema: string
  timestamp: string
  current_state: Record<string, unknown>
  expected_outputs: string[]
  user_id: string
  input_text?: string
  context_prompt?: string  // Meta-Prompt/Regeln (user-editable!)
  transformed_text?: string
  translation_en?: string  // English translation for media generation
  models_used?: ModelsUsed  // LLM models used at each stage
  media_outputs: MediaOutput[]
  target_view: string
  /**
   * Present when the run was made by a Latent Lab instrument: the whole run as
   * that instrument's own object — parameters, ordered parts, outputs. The
   * gallery neither reads nor needs it; the instrument named in `tool` takes it
   * back (see composables/useLatentLabRecorder.ts).
   */
  instrument?: InstrumentRun
  /**
   * The Canvas workflow behind the run, where there is one: the board itself
   * for a kept workflow, the board that made it for an output of a Canvas run
   * (read from that run's `workflow.json`). The Canvas opens it; nothing else
   * reads it.
   */
  canvas_workflow?: Record<string, unknown>
}

// ============================================================================
// STORE DEFINITION
// ============================================================================

export const useFavoritesStore = defineStore('favorites', () => {
  // ============================================================================
  // STATE
  // ============================================================================

  /** List of favorite items */
  const favorites = ref<FavoriteItem[]>([])

  /** Loading state */
  const isLoading = ref(false)

  /** Gallery expand/collapse state */
  const isGalleryExpanded = ref(false)

  /** Error message (if any) */
  const error = ref<string | null>(null)

  /** Favorites mode (global vs per_user) */
  const mode = ref<'global' | 'per_user'>('global')

  /** View mode: 'per_user' shows only own favorites, 'global' shows all */
  const viewMode = ref<'per_user' | 'global'>('per_user')  // Default to per_user

  /** Pending restore data (set by FooterGallery, consumed by views via watcher) */
  const pendingRestoreData = ref<RestoreData | null>(null)

  // ============================================================================
  // COMPUTED
  // ============================================================================

  /** Total number of favorites */
  const totalFavorites = computed(() => favorites.value.length)

  /** Check if a run is favorited */
  const isFavorited = (runId: string): boolean => {
    return favorites.value.some((f) => f.run_id === runId)
  }

  // ============================================================================
  // ACTIONS
  // ============================================================================

  /**
   * Load all favorites from backend
   *
   * @param deviceId - Optional device ID for filtering (per_user mode)
   */
  async function loadFavorites(deviceId?: string): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      console.log('[Favorites] Loading favorites from backend...')

      // Query parameters for filtering
      const params = new URLSearchParams()
      if (deviceId) {
        params.append('device_id', deviceId)
      }
      params.append('view_mode', viewMode.value)

      const response = await axios.get<FavoritesResponse>(`/api/favorites?${params.toString()}`)

      favorites.value = response.data.favorites
      mode.value = response.data.mode

      console.log(
        `[Favorites] Loaded ${response.data.total} favorites ` +
          `(backend mode: ${mode.value}, view mode: ${viewMode.value})`
      )
    } catch (e) {
      console.error('[Favorites] Failed to load favorites:', e)
      error.value = e instanceof Error ? e.message : 'Failed to load favorites'
      favorites.value = []
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Add a new favorite
   *
   * @param runId - Run ID to favorite
   * @param mediaType - Type of media
   * @param deviceId - Device identifier (browser_id + date)
   * @param userId - Optional user ID (default: 'anonymous')
   */
  async function addFavorite(
    runId: string,
    mediaType: FavoriteItem['media_type'],
    deviceId: string,
    userId: string = 'anonymous',
    sourceView?: string
  ): Promise<boolean> {
    error.value = null

    // Optimistic update
    const tempFavorite: FavoriteItem = {
      run_id: runId,
      device_id: deviceId,
      added_at: new Date().toISOString(),
      // A workflow has no picture and no file the media routes serve.
      thumbnail_url: mediaType === 'canvas'
        ? ''
        : `/api/media/${mediaType}/${runId}${mediaType === 'image' ? '/0' : ''}`,
      media_type: mediaType,
      user_id: userId,
      user_note: '',
      source_view: sourceView,
      exists: true
    }

    // Add to beginning (most recent first)
    favorites.value.unshift(tempFavorite)

    try {
      console.log(`[Favorites] Adding favorite: ${runId} (${mediaType})`)
      const response = await axios.post<AddFavoriteResponse>('/api/favorites', {
        run_id: runId,
        media_type: mediaType,
        device_id: deviceId,
        user_id: userId,
        source_view: sourceView
      })

      // Update with server response
      const index = favorites.value.findIndex((f) => f.run_id === runId)
      if (index >= 0) {
        // `exists` is not in the add answer, and the strip draws no picture
        // without it — a freshly kept image showed the grey placeholder until
        // the page was reloaded. The server refuses a run that holds nothing of
        // the kind (409), so a 201 IS the statement that the piece is there.
        favorites.value[index] = { ...response.data.favorite, exists: true }
      }

      console.log(`[Favorites] Successfully added favorite: ${runId}`)
      return true
    } catch (e) {
      // Rollback optimistic update
      favorites.value = favorites.value.filter((f) => f.run_id !== runId)

      if (axios.isAxiosError(e) && e.response?.status === 409) {
        // TWO different refusals share this code: the run is already kept, and
        // the run holds nothing of that kind to keep. Reported as success alike,
        // the second lit a star the server never took — which is how a sketch
        // kept as a picture came back +1 and then -1 under the finger. The list
        // decides: after the reload the run is either in it or it is not.
        await loadFavorites(deviceId)
        const kept = favorites.value.some((f) => f.run_id === runId)
        if (!kept) {
          const said = (e.response?.data as { error?: string } | undefined)?.error
          error.value = said || 'This run cannot be kept'
          console.warn(`[Favorites] Refused: ${runId} — ${error.value}`)
        }
        return kept
      }

      console.error(`[Favorites] Failed to add favorite: ${runId}`, e)
      error.value = e instanceof Error ? e.message : 'Failed to add favorite'
      return false
    }
  }

  /**
   * Remove a favorite
   *
   * @param runId - Run ID to remove from favorites
   * @param deviceId - Optional device ID for ownership validation
   */
  async function removeFavorite(runId: string, deviceId?: string): Promise<boolean> {
    error.value = null

    // Store for potential rollback
    const removed = favorites.value.find((f) => f.run_id === runId)
    const originalIndex = favorites.value.findIndex((f) => f.run_id === runId)

    // Optimistic update
    favorites.value = favorites.value.filter((f) => f.run_id !== runId)

    try {
      console.log(`[Favorites] Removing favorite: ${runId}`)

      // The deviceId is SENT, not just accepted. It is the parameter for
      // ownership validation: without it on the query the backend deletes by
      // run_id alone and any device can remove any other device's favourite.
      // Every caller already passes it.
      const query = deviceId ? `?device_id=${encodeURIComponent(deviceId)}` : ''
      await axios.delete<RemoveFavoriteResponse>(`/api/favorites/${runId}${query}`)

      console.log(`[Favorites] Successfully removed favorite: ${runId}`)
      return true
    } catch (e) {
      // Rollback optimistic update
      if (removed && originalIndex >= 0) {
        favorites.value.splice(originalIndex, 0, removed)
      }

      console.error(`[Favorites] Failed to remove favorite: ${runId}`, e)
      error.value = e instanceof Error ? e.message : 'Failed to remove favorite'
      return false
    }
  }

  /**
   * Toggle favorite status
   *
   * @param runId - Run ID to toggle
   * @param mediaType - Type of media (required for adding)
   * @param deviceId - Device identifier
   * @param userId - Optional user ID
   */
  async function toggleFavorite(
    runId: string,
    mediaType: FavoriteItem['media_type'],
    deviceId: string,
    userId: string = 'anonymous',
    sourceView?: string
  ): Promise<boolean> {
    if (isFavorited(runId)) {
      return removeFavorite(runId, deviceId)
    } else {
      return addFavorite(runId, mediaType, deviceId, userId, sourceView)
    }
  }

  /**
   * Get restore data for a favorite
   *
   * Returns complete session data for restoring UI state
   *
   * @param runId - Run ID to get restore data for
   */
  async function getRestoreData(runId: string): Promise<RestoreData | null> {
    try {
      console.log(`[Favorites] Getting restore data for: ${runId}`)
      const response = await axios.get<RestoreData>(`/api/favorites/${runId}/restore`)
      return response.data
    } catch (e) {
      console.error(`[Favorites] Failed to get restore data: ${runId}`, e)
      error.value = e instanceof Error ? e.message : 'Failed to get restore data'
      return null
    }
  }

  /**
   * Toggle gallery expanded state
   */
  function toggleGallery(): void {
    isGalleryExpanded.value = !isGalleryExpanded.value
    console.log(`[Favorites] Gallery ${isGalleryExpanded.value ? 'expanded' : 'collapsed'}`)
  }

  /**
   * Toggle between per_user and global view mode
   *
   * @param newMode - 'per_user' or 'global'
   * @param deviceId - Device ID for filtering (required in per_user mode)
   */
  async function setViewMode(
    newMode: 'per_user' | 'global',
    deviceId?: string
  ): Promise<boolean> {
    try {
      console.log(`[Favorites] Switching to ${newMode} view`)
      viewMode.value = newMode

      // Reload with new filter
      await loadFavorites(deviceId)

      return true
    } catch (e) {
      console.error('[Favorites] Failed to switch view:', e)
      error.value = e instanceof Error ? e.message : 'Failed to switch view'
      return false
    }
  }

  /**
   * Set restore data for cross-component communication
   *
   * Used by FooterGallery to signal views to restore state.
   * Views watch this and consume it immediately.
   *
   * @param data - Restore data or null to clear
   */
  function setRestoreData(data: RestoreData | null): void {
    pendingRestoreData.value = data
  }

  // ============================================================================
  // RETURN PUBLIC API
  // ============================================================================

  return {
    // State
    favorites,
    isLoading,
    isGalleryExpanded,
    error,
    mode,
    viewMode,  // Per-user favorites
    pendingRestoreData,

    // Computed
    totalFavorites,

    // Getters (functions)
    isFavorited,

    // Actions
    loadFavorites,
    addFavorite,
    removeFavorite,
    toggleFavorite,
    getRestoreData,
    setViewMode,  // Toggle per_user/global view
    toggleGallery,
    setRestoreData
  }
})
