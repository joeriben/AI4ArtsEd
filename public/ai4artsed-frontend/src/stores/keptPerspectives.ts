/**
 * What a person keeps of their own (P3).
 *
 * A perspective written on a surface lived in `sessionStorage` and was gone with
 * the tab. This store is the other half: `/api/interception-prompts/*` keeps it
 * in the lab database, under the account of whoever wrote it — everyone who is
 * logged in keeps their own, participants included.
 *
 * Addressing is the platform's style key, identical to the backend's:
 *   `preset:<name>` — one of the immutable presets
 *   `custom:<id>`   — a kept perspective
 * A bare name is a preset. Once a perspective is kept, a run addresses it by its
 * `custom:` key, so the record of the run names what actually ran instead of the
 * preset the text was once written over.
 *
 * Nothing here is reachable without a session; `canKeep` is false then and the
 * surfaces simply do not offer it.
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import i18n from '@/i18n'
import { useLabAuthStore } from './labAuth'
import { apiBase } from '@/services/labApi'

/** Error text for the surfaces, from en.ts like every other string. */
function say(key: string): string {
  return i18n.global.t(`keptPerspectives.${key}`) as string
}

const API = '/api/interception-prompts'

/** The prompt text is a plain string when written here, an i18n dict when it
 *  was copied out of a preset that carries one. */
export type PromptText = string | Record<string, string>

export interface KeptPerspective {
  id: number
  name: string
  base_config: string | null
  pipeline: string
  context_text: PromptText
  parameters: Record<string, unknown>
  is_published: boolean
  forked_from_preset: string | null
  forked_from_prompt_id: number | null
  style_key: string
  created_at: string | null
  updated_at: string | null
}

/** Read a prompt text in one language, falling back to English, then anything. */
export function readPromptText(text: PromptText | undefined, lang: string): string {
  if (!text) return ''
  if (typeof text === 'string') return text
  return text[lang] || text.en || Object.values(text).find((v) => !!v) || ''
}

/** What a saved perspective RUNS THROUGH: the preset it was written over. Not
 *  a picture any more — a saved perspective wears a colour, see `keptColor`. */
export function keptPreviewId(p: KeptPerspective): string {
  return p.forked_from_preset || p.base_config || 'user_defined'
}

/** The platform's own palette — the colours the category bubbles wear, minus
 *  `#FFC107`: that one belongs to the centre bubble, in whose ring the saved
 *  perspectives hang, and a piece the colour of the bubble it hangs from reads
 *  as part of it. */
export const KEPT_PALETTE = [
  '#2196F3',
  '#9C27B0',
  '#E91E63',
  '#4CAF50',
  '#00BCD4',
  '#FF6F00',
  '#607D8B',
  '#FF1744',
] as const

/** The colour a saved perspective wears instead of a picture.
 *
 *  Taken from its PLACE among this person's own, oldest first — so no two of
 *  theirs share a colour until the ninth, and every surface draws the same one.
 *  The row id alone would not do it: it counts across all owners, so two of
 *  one's own can sit nine apart and land on the same colour. Where the list is
 *  not to hand, the id decides — a colour then, rather than none. */
export function keptColor(id: number, all: readonly KeptPerspective[] = []): string {
  const n = KEPT_PALETTE.length
  const rank = all.map((p) => p.id).sort((a, b) => a - b).indexOf(id)
  const i = rank >= 0 ? rank : id
  return KEPT_PALETTE[((i % n) + n) % n] ?? KEPT_PALETTE[0]
}

export const useKeptPerspectivesStore = defineStore('keptPerspectives', () => {
  const items = ref<KeptPerspective[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  /** Whether the session has been asked about at least once. */
  const sessionChecked = ref(false)

  const auth = useLabAuthStore()
  const canKeep = computed(() => auth.isAuthenticated)

  /** Restore a server session once. The flow surface is not a lab route, so the
   *  router guard never ran and the auth store would otherwise stay empty. */
  async function ensureSession(): Promise<void> {
    if (sessionChecked.value) return
    sessionChecked.value = true
    if (auth.user === null) await auth.fetchMe()
  }

  function put(p: KeptPerspective): KeptPerspective {
    const i = items.value.findIndex((x) => x.id === p.id)
    if (i >= 0) items.value[i] = p
    else items.value.unshift(p)
    return p
  }

  async function load(): Promise<void> {
    await ensureSession()
    if (!canKeep.value) {
      items.value = []
      return
    }
    loading.value = true
    error.value = null
    try {
      const { data } = await axios.get(`${apiBase()}${API}`, { withCredentials: true })
      items.value = data.prompts ?? []
    } catch (e: any) {
      error.value = e?.response?.data?.error ?? say('errRead')
      items.value = []
    } finally {
      loading.value = false
    }
  }

  /**
   * Keep a perspective as it stands on the surface.
   *
   * `basePreset` is the preset whose PIPELINE and CHUNKS the text runs through —
   * structure only. For a perspective written from scratch that is the blank one
   * (`user_defined`); for a reworded preset it is that preset, and the provenance
   * survives the rewording.
   */
  async function keep(
    basePreset: string,
    name: string,
    contextText: string,
  ): Promise<KeptPerspective | null> {
    await ensureSession()
    if (!canKeep.value) return null
    error.value = null
    try {
      const { data } = await axios.post(
        `${apiBase()}${API}/from-preset`,
        { preset_name: basePreset, name, context_text: contextText },
        { withCredentials: true },
      )
      return put(data.prompt)
    } catch (e: any) {
      error.value = e?.response?.data?.error ?? say('errKeep')
      return null
    }
  }

  /** True when the last update failed because the row is not there any more —
   *  dropped from the chooser, or a session that has run out. The surface then
   *  keeps it as a NEW one instead of leaving the tile in a dead end. */
  const lastUpdateWasGone = ref(false)

  /** Write a change into one that is already kept. The previous wording is
   *  snapshotted server-side, so nothing is lost by editing. */
  async function update(
    id: number,
    patch: Partial<Pick<KeptPerspective, 'name' | 'context_text' | 'is_published'>>,
  ): Promise<KeptPerspective | null> {
    error.value = null
    lastUpdateWasGone.value = false
    try {
      const { data } = await axios.put(`${apiBase()}${API}/${id}`, patch, {
        withCredentials: true,
      })
      return put(data.prompt)
    } catch (e: any) {
      const status = e?.response?.status
      lastUpdateWasGone.value = status === 404 || status === 401
      if (lastUpdateWasGone.value) {
        items.value = items.value.filter((x) => x.id !== id)
      }
      error.value = e?.response?.data?.error ?? say('errSave')
      return null
    }
  }

  async function remove(id: number): Promise<boolean> {
    error.value = null
    try {
      await axios.delete(`${apiBase()}${API}/${id}`, { withCredentials: true })
      items.value = items.value.filter((x) => x.id !== id)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error ?? say('errRemove')
      return false
    }
  }

  function byId(id: number): KeptPerspective | undefined {
    return items.value.find((x) => x.id === id)
  }

  return {
    items, loading, error, canKeep, lastUpdateWasGone,
    ensureSession, load, keep, update, remove, byId,
  }
})
