/**
 * The LoRA register, as a surface reads it: what THIS session is offered.
 *
 * `/api/loras` answers with the platform's adapters, the session's own, and
 * those released to the course the session is in, each with `present` —
 * whether the file lies in the LoRA folder right now. A participant's course
 * is fixed on the server; an educator leads several, and the one this client
 * is in (`labAuth.activeCourseId`) goes along as `course_id`. What the
 * register does not offer is not here: another's training released nowhere,
 * another course's adapters, the accelerators of the video pipelines that
 * share the folder (issue #70).
 *
 * The listing is read again whenever the session's course changes: the same
 * page under another course is offered another list.
 */
import { ref, computed, watch } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { useLabAuthStore } from './labAuth'
import { apiBase } from '@/services/labApi'

/**
 * The colour of a LoRA on this platform: the violet of the sign (the purple of
 * the picture the sign was drawn from, lifted for the dark ground). Beside the
 * amber of a perspective and the green of the plus, and next to the violet of
 * the node boxes (#7f77dd) without falling into it.
 */
export const LORA_COLOR = '#a78bfa'

/**
 * The kinds the register sorts the adapters by. The server takes any short key
 * (`services/lora_register.py`), so this list is what the SURFACES offer and
 * name; a kind that reaches the register another way stands on the chooser's
 * ring under its own key. The adapters the platform's own presets bring carry
 * `photography`; every other row takes its kind in the register.
 */
export const LORA_CATEGORIES = ['photography'] as const

export interface LoraAdapter {
  id: number
  /** The file in the LoRA folder, as a run names it. */
  file: string
  /** What the surfaces call it. */
  name: string
  /** The word the captions were written under; the run puts it in front of the prompt. */
  trigger: string
  /**
   * What the adapter file says it was trained over, lower case, empty where it
   * says nothing. The server reads it from the file (2026-09-22) — it was
   * ticked off by hand in the Settings before that.
   */
  base?: string
  /**
   * The output configs this adapter reaches: those whose workflow can load an
   * adapter at all and whose config names `base` (`meta.lora_base`). Derived
   * by the server on every read, never sent back to it.
   */
  base_configs: string[]
  /**
   * The kind of thing it makes, which the chooser's ring sorts by: a short key
   * the register holds (`my_app/lab/models.py`), empty where nobody has said.
   * The platform's four adapters are `photography`.
   */
  category?: string
  owner_id: number | null
  /** The account whose training this is, by name — the register tab shows it. */
  owner_name?: string
  course_id: number | null
  course_name?: string
  visibility: 'platform' | 'course' | 'none'
  /** Whether the file lies in the folder right now. */
  present: boolean
}

/**
 * A bubble on the chooser's ring: a kind the register names, or — for the
 * adapters it names no kind for — the release they come under.
 */
export interface LoraRing {
  key: string
  kind: 'category' | 'platform' | 'course' | 'own'
  /** The register's key, where the bubble is a kind. */
  category: string
  items: LoraAdapter[]
}

export const useLoraStore = defineStore('loras', () => {
  const auth = useLabAuthStore()
  const items = ref<LoraAdapter[]>([])
  const loading = ref(false)
  const error = ref('')
  let loadedFor = ''

  async function load(force = false): Promise<void> {
    const key = `${auth.user?.id ?? ''}|${auth.activeCourseId ?? ''}`
    if (!force && loadedFor === key && (items.value.length || !error.value)) return
    loading.value = true
    error.value = ''
    try {
      const params = auth.activeCourseId != null ? { course_id: auth.activeCourseId } : undefined
      const { data } = await axios.get(`${apiBase()}/api/loras`, { params, withCredentials: true })
      items.value = Array.isArray(data?.loras) ? data.loras : []
      loadedFor = key
    } catch (e: any) {
      error.value = e?.response?.data?.error || e?.message || String(e)
      items.value = []
      loadedFor = ''
    } finally {
      loading.value = false
    }
  }

  // A course change is another list.
  watch(
    () => [auth.user?.id ?? null, auth.activeCourseId] as const,
    () => {
      if (loadedFor) void load(true)
    }
  )

  /** Those the platform offers to everyone. */
  const platform = computed(() => items.value.filter((l) => l.visibility === 'platform'))
  /** Those released to the course this session is in. */
  const course = computed(() =>
    items.value.filter((l) => l.visibility === 'course' && l.course_id === auth.activeCourseId)
  )
  /** The one name the course group stands under, from the rows themselves. */
  const courseName = computed(() => course.value.find((l) => l.course_name)?.course_name || '')
  /**
   * The rest: what the register offers this account as the OWNER of the
   * training — released nowhere, or to a course this session is not in. No
   * other path puts such a row in the listing.
   */
  const own = computed(() => items.value.filter((l) => !platform.value.includes(l) && !course.value.includes(l)))

  /**
   * What the chooser's ring carries (`components/LoraPickOverlay.vue`): one
   * bubble per KIND the register names, and, for the adapters it names no kind
   * for, one per release. A fresh training is in the chooser from the first
   * moment, under the account's own trainings, and moves onto a kind when
   * somebody gives it one.
   */
  const rings = computed<LoraRing[]>(() => {
    const kinds = new Map<string, LoraAdapter[]>()
    const unsorted: LoraAdapter[] = []
    for (const l of items.value) {
      const key = (l.category || '').trim()
      if (!key) {
        unsorted.push(l)
        continue
      }
      const bucket = kinds.get(key)
      if (bucket) bucket.push(l)
      else kinds.set(key, [l])
    }
    const out: LoraRing[] = [...kinds.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([category, adapters]) => ({
        key: `kind:${category}`,
        kind: 'category' as const,
        category,
        items: adapters,
      }))
    const byRelease: [LoraRing['kind'], LoraAdapter[]][] = [
      ['platform', unsorted.filter((l) => platform.value.includes(l))],
      ['course', unsorted.filter((l) => course.value.includes(l))],
      ['own', unsorted.filter((l) => own.value.includes(l))],
    ]
    for (const [kind, adapters] of byRelease) {
      if (adapters.length) out.push({ key: kind, kind, category: '', items: adapters })
    }
    return out
  })

  function byFile(file: string): LoraAdapter | undefined {
    return items.value.find((l) => l.file === file)
  }

  return { items, loading, error, load, platform, course, courseName, own, rings, byFile }
})
