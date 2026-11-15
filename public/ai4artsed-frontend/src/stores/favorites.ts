import { ref, computed, toRaw } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { useLabAuthStore } from './labAuth'
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

/** The server's own sentence for a refusal, where it gave one. */
function causeOf(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) {
    const said = (e.response?.data as { error?: string } | undefined)?.error
    if (said) return said
  }
  return e instanceof Error ? e.message : fallback
}

/** Favorite item from backend */
export interface FavoriteItem {
  run_id: string
  /** Whether whoever asks may remove it or change its note. The server says
   *  so (favorites_routes.py, `_may_change`): a favourite belongs to the
   *  account it was kept under, or, kept without one, to the device, and
   *  neither is in what a page receives (2026-11-14). */
  may_change?: boolean
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

  /**
   * Whether a run is kept by whoever asks: in the list, and theirs to take
   * back (`may_change`). In the "All" view the list holds the favourites of
   * other accounts and devices; their stars stay dark, since taking one back
   * could only be refused. Every star on the platform reads this, so a
   * sign-in or a sign-out, which changes whose the list is, reaches them all.
   */
  const isFavorited = (runId: string): boolean => {
    return favorites.value.some((f) => f.run_id === runId && f.may_change === true)
  }

  /** The load whose answer the list takes: the last one asked. */
  let loads = 0
  /** The last load asked, for whoever waits on what the list now holds. */
  let latest: Promise<void> = Promise.resolve()
  /**
   * A count of the starts and ends of the adds and removes. An answer to a
   * load is put in place only where none started or ended while the load was
   * out: the server may have read the store before it stored the change, and
   * the answer then took a new star off again or put back the one just taken
   * away. The list then asks again.
   */
  let edits = 0
  /**
   * The adds and removes out for whoever the list is now: by run, the entry an
   * add put in, or null for a remove. A second press on the same run is
   * refused until the first is answered: the two answers can arrive in either
   * order, and the list could not tell which one stands. An answer to a load
   * is put in place with these laid over it (`withEditsOut`): the server may
   * have read the store before an edit still out was stored. A load does not
   * wait for them; an add that never came back held the strip as it was.
   */
  let pending = new Map<string, FavoriteItem | null>()
  /** Counts the changes of whose the list is (a sign-in, a sign-out). */
  let owners = 0

  /** An add, with the entry it put in, or a remove (null) goes out; the
   *  function it returns marks its answer. */
  function beginEdit(runId: string, entry: FavoriteItem | null, deviceId?: string): () => void {
    const out = pending
    out.set(runId, entry)
    edits++
    let open = true
    return () => {
      if (!open) return
      open = false
      out.delete(runId)
      edits++
      if (out !== pending) {
        // Asked before the list changed owner. What it changed can still be
        // in the new owner's list: an account reaches what its browser kept
        // that day without one.
        void loadFavorites(deviceId)
      }
    }
  }

  /** A load's answer with the edits still out laid over it: the entry an add
   *  put in stands where the answer lacks its run, and a run whose removal is
   *  out is left out. */
  function withEditsOut(listed: FavoriteItem[]): FavoriteItem[] {
    const kept = listed.filter((f) => pending.get(f.run_id) !== null)
    // Newest first, as an add puts its entry in.
    const added: FavoriteItem[] = []
    pending.forEach((entry, runId) => {
      if (entry && !kept.some((f) => f.run_id === runId)) added.unshift(entry)
    })
    return [...added, ...kept]
  }

  // ============================================================================
  // ACTIONS
  // ============================================================================

  /**
   * Load all favorites from backend
   *
   * @param deviceId - Optional device ID for filtering (per_user mode)
   * @param afresh - Whose the list is has changed (a sign-in, a sign-out): the
   *   list of the one before is taken down at once, so no star of theirs stays
   *   lit while the answer is out.
   */
  function loadFavorites(deviceId?: string, afresh = false): Promise<void> {
    const load = ++loads
    if (afresh) {
      favorites.value = []
      owners++
      pending = new Map()
    }
    isLoading.value = true
    latest = fetchFavorites(load, deviceId)
    return latest
  }

  async function fetchFavorites(load: number, deviceId?: string): Promise<void> {
    const editsAsked = edits
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

      // A sign-in or a sign-out changes whose favourites these are. The answer
      // to a load asked before it would put the list of the one before back.
      if (load !== loads) return latest
      if (editsAsked !== edits) return loadFavorites(deviceId)

      favorites.value = withEditsOut(response.data.favorites)
      mode.value = response.data.mode

      console.log(
        `[Favorites] Loaded ${response.data.total} favorites ` +
          `(backend mode: ${mode.value}, view mode: ${viewMode.value})`
      )
    } catch (e) {
      if (load !== loads) return latest
      console.error('[Favorites] Failed to load favorites:', e)
      error.value = causeOf(e, 'Failed to load favorites')
      // The list stays as it was: a load that failed says nothing about what
      // is kept, and an empty strip would say that nothing is.
    } finally {
      if (load === loads) isLoading.value = false
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
    if (pending.has(runId)) return false
    error.value = null

    // Already in the list: kept by whoever asks, or by somebody else, whose
    // entry an optimistic star and its rollback would cover and then take
    // out of the strip.
    const listed = favorites.value.find((f) => f.run_id === runId)
    if (listed) {
      if (listed.may_change === true) return true
      error.value = 'This run is kept by another account or device'
      return false
    }

    // Optimistic update
    const tempFavorite: FavoriteItem = {
      run_id: runId,
      added_at: new Date().toISOString(),
      // A workflow has no picture and no file the media routes serve.
      thumbnail_url: mediaType === 'canvas'
        ? ''
        : `/api/media/${mediaType}/${runId}${mediaType === 'image' ? '/0' : ''}`,
      media_type: mediaType,
      user_id: userId,
      user_note: '',
      source_view: sourceView,
      exists: true,
      may_change: true
    }

    // Add to beginning (most recent first)
    favorites.value.unshift(tempFavorite)
    const settle = beginEdit(runId, tempFavorite, deviceId)

    try {
      console.log(`[Favorites] Adding favorite: ${runId} (${mediaType})`)
      const response = await axios.post<AddFavoriteResponse>('/api/favorites', {
        run_id: runId,
        media_type: mediaType,
        device_id: deviceId,
        user_id: userId,
        source_view: sourceView
      })
      settle()

      // Update with server response. The entry this add put in is gone only
      // where the list was taken down for another owner (a sign-in, a
      // sign-out); their own list follows.
      const index = favorites.value.findIndex((f) => toRaw(f) === tempFavorite)
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
      settle()
      // Rollback optimistic update: the entry this add put in, and no other.
      favorites.value = favorites.value.filter((f) => toRaw(f) !== tempFavorite)

      if (axios.isAxiosError(e) && e.response?.status === 409) {
        // Three refusals share this code: the run is already kept by whoever
        // asks, it is kept by somebody else, and it holds nothing of that kind
        // to keep. Reported as success alike, the last lit a star the server
        // never took — which is how a sketch kept as a picture came back +1 and
        // then -1 under the finger. The list decides: after the reload the run
        // is either kept by whoever asks or it is not.
        await loadFavorites(deviceId)
        // The entry of a second press on the run, made while this reload was
        // out, is no answer to this one.
        const second = pending.get(runId)
        const kept = favorites.value.some(
          (f) => f.run_id === runId && f.may_change === true && toRaw(f) !== second
        )
        // A reload that failed has said why already.
        if (!kept && !error.value) {
          const said = (e.response?.data as { error?: string } | undefined)?.error
          error.value = said || 'This run cannot be kept'
          console.warn(`[Favorites] Refused: ${runId} — ${error.value}`)
        }
        return kept
      }

      console.error(`[Favorites] Failed to add favorite: ${runId}`, e)
      error.value = causeOf(e, 'Failed to add favorite')
      return false
    } finally {
      settle()
    }
  }

  /**
   * Remove a favorite
   *
   * @param runId - Run ID to remove from favorites
   * @param deviceId - Optional device ID for ownership validation
   */
  async function removeFavorite(runId: string, deviceId?: string): Promise<boolean> {
    if (pending.has(runId)) return false
    error.value = null

    // Store for potential rollback
    const originalIndex = favorites.value.findIndex((f) => f.run_id === runId)
    const removed = originalIndex >= 0 ? favorites.value[originalIndex] : undefined
    const ownersAsked = owners

    // Optimistic update
    favorites.value = favorites.value.filter((f) => f.run_id !== runId)
    const settle = beginEdit(runId, null, deviceId)

    try {
      console.log(`[Favorites] Removing favorite: ${runId}`)

      // The deviceId is SENT, not just accepted. It is the parameter for
      // ownership validation: without it on the query the backend deletes by
      // run_id alone and any device can remove any other device's favourite.
      // Every caller already passes it.
      const query = deviceId ? `?device_id=${encodeURIComponent(deviceId)}` : ''
      await axios.delete<RemoveFavoriteResponse>(`/api/favorites/${runId}${query}`)
      settle()

      console.log(`[Favorites] Successfully removed favorite: ${runId}`)
      return true
    } catch (e) {
      settle()
      const status = axios.isAxiosError(e) ? e.response?.status : undefined
      if (status === 404) {
        // Gone already: taken back on another machine of the same account, or
        // by whoever kept it. What the press asked for is the case.
        console.warn(`[Favorites] Already gone: ${runId}`)
        return true
      }
      console.error(`[Favorites] Failed to remove favorite: ${runId}`, e)
      error.value = causeOf(e, 'Failed to remove favorite')
      if (status === 403) {
        // Not theirs to take back: a place whose sign-in has ended before the
        // page learnt of it. The list says whose it is now, and the page asks
        // at once who is signed in: the plate leaves the strip, and without
        // the question the header showed the place for up to half a minute
        // more, with nothing to say why the plate went.
        void loadFavorites(deviceId)
        const auth = useLabAuthStore()
        void auth.checkPlaceSession(true)
        void auth.checkLeaderSession(true)
        return false
      }
      // Rollback: the entry goes back where whose the list is has not changed,
      // and where nothing has put it back since.
      if (removed && ownersAsked === owners && !favorites.value.some((f) => f.run_id === runId)) {
        favorites.value.splice(Math.min(originalIndex, favorites.value.length), 0, removed)
      }
      return false
    } finally {
      settle()
    }
  }

  /**
   * Who keeps a run, asked of the server: nobody, whoever asks, or somebody
   * else. The "Mine" view holds whoever asks alone and cannot say so. A
   * surface that writes into a run before keeping it asks here first.
   */
  async function keeperOf(runId: string, deviceId: string): Promise<'nobody' | 'asker' | 'another'> {
    const params = new URLSearchParams({ device_id: deviceId })
    const response = await axios.get<{ kept: boolean; may_change: boolean }>(
      `/api/favorites/${runId}/keeper?${params.toString()}`
    )
    if (!response.data.kept) return 'nobody'
    return response.data.may_change ? 'asker' : 'another'
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
    keeperOf,
    getRestoreData,
    setViewMode,  // Toggle per_user/global view
    toggleGallery,
    setRestoreData
  }
})
