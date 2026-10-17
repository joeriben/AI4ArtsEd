/**
 * API client for the Lab User/Course system (P1).
 *
 * Follows the P0 labAuth store conventions exactly: a per-call `apiBase()`
 * (cross-origin in dev: 5173 -> 17802) and cookie sessions (`withCredentials`).
 * Kept separate from services/api.ts because the lab endpoints need credentialed
 * requests and the dev cross-origin base, unlike the same-origin apiClient there.
 *
 * Style keys ("preset:*" / "custom:*") and the palette API belong to P3 and are
 * intentionally absent here.
 */
import axios from 'axios'

/**
 * The development base URL, once. In dev the frontend is cross-origin
 * (5173 -> 17802) and every call that goes to the backend directly reads
 * the address from here; in production it is '' and every path is
 * relative. Until 2026-10-10 the same expression stood in 44 files.
 */
export function apiBase(): string {
  return import.meta.env.DEV ? 'http://localhost:17802' : ''
}

const cfg = { withCredentials: true } as const

// ---- types -----------------------------------------------------------------
export type Role = 'admin' | 'educator' | 'participant'
export type SafetyLevel = 'kids' | 'youth' | 'open'

export interface AdminUser {
  id: number
  role: Role
  email: string | null
  username: string | null
  display_name: string
  identifier: string
  locale: string
  is_active: boolean
  created_by: number | null
  created_at: string | null
  /** Present ONCE on create / password-reset responses. */
  temp_password?: string
}

export interface CourseEducatorRef {
  user_id: number
  role: 'owner' | 'co_leader'
}

/** A place of a course (2026-09-23): a number and whether, and since when, it
 *  has a code. The code itself is only in the response that makes it. */
export interface CoursePlace {
  number: number
  has_code: boolean
  code_issued_at: string | null
}

/** A place with its code, in the one response that carries the code. */
export interface IssuedPlace {
  number: number
  code: string
}

export interface Course {
  id: number
  name: string
  description: string
  safety_level: SafetyLevel
  educator_can_view_participant_works: boolean
  archived: boolean
  educators: CourseEducatorRef[]
  place_count: number
  /** Until when the codes of the places enter the course (ISO 8601 with offset). */
  access_until: string | null
  access_open: boolean
  /** Only on GET /api/courses/:id, and only for the course's leaders. */
  places?: CoursePlace[]
}

export interface DeletionImpact {
  places: number
  course_works: number
  course_custom_prompts: number
}

// ---- admin: educator management (admin only) -------------------------------
export const adminUsersApi = {
  list: (role?: Role) =>
    axios.get<{ users: AdminUser[] }>(
      `${apiBase()}/api/admin/users${role ? `?role=${role}` : ''}`, cfg),
  create: (payload: { email: string; username?: string; display_name?: string; temp_password?: string }) =>
    axios.post<{ user: AdminUser }>(`${apiBase()}/api/admin/users`, { role: 'educator', ...payload }, cfg),
  update: (id: number, patch: { is_active?: boolean; display_name?: string; reset_password?: boolean }) =>
    axios.patch<{ user: AdminUser }>(`${apiBase()}/api/admin/users/${id}`, patch, cfg),
  remove: (id: number) =>
    axios.delete(`${apiBase()}/api/admin/users/${id}`, cfg),
}

// ---- courses ---------------------------------------------------------------
/** One entry of a course palette: a given perspective or a kept one. */
export interface PaletteItem {
  id: number
  course_id: number
  source_type: 'preset' | 'custom'
  preset_name: string | null
  prompt_id: number | null
  label: string | null
  position: number
  enabled: boolean
  style_key: string
  forked_from_preset?: string | null
}

/** A given perspective, and whether this course already carries it. */
export interface PresetStyle {
  style_key: string
  name: string
  display_name: Record<string, string> | null
  source_type: 'preset'
  in_palette?: boolean
}

export const coursesApi = {
  list: () =>
    axios.get<{ courses: Course[] }>(`${apiBase()}/api/courses`, cfg),
  create: (payload: { title: string; safety_level?: SafetyLevel; description?: string }) =>
    axios.post<{ course: Course }>(`${apiBase()}/api/courses`, payload, cfg),
  get: (id: number) =>
    axios.get<{ course: Course }>(`${apiBase()}/api/courses/${id}`, cfg),
  update: (id: number, patch: Partial<Pick<Course, 'name' | 'safety_level' | 'description' | 'educator_can_view_participant_works' | 'archived'>> & { title?: string }) =>
    axios.patch<{ course: Course }>(`${apiBase()}/api/courses/${id}`, patch, cfg),

  // places (2026-09-23): each code is in the response that makes it, and nowhere else
  addPlaces: (id: number, count: number) =>
    axios.post<{ places: IssuedPlace[]; course: Course }>(
      `${apiBase()}/api/courses/${id}/places`, { count }, cfg),
  replacePlaceCode: (id: number, number: number) =>
    axios.post<{ place: CoursePlace & { code: string } }>(
      `${apiBase()}/api/courses/${id}/places/${number}/code`, {}, cfg),

  // the access window: the codes enter the course until `until`
  openAccess: (id: number, until: string) =>
    axios.put<{ course: Course }>(`${apiBase()}/api/courses/${id}/access`, { until }, cfg),
  closeAccess: (id: number) =>
    axios.delete<{ course: Course }>(`${apiBase()}/api/courses/${id}/access`, cfg),

  // co-leaders
  addEducator: (id: number, ident: string, role = 'co_leader') =>
    axios.post(`${apiBase()}/api/courses/${id}/educators`,
      // send both keys; backend accepts username or email
      { username: ident, email: ident, role }, cfg),
  removeEducator: (id: number, userId: number) =>
    axios.delete(`${apiBase()}/api/courses/${id}/educators/${userId}`, cfg),

  // the palette (P3): what this course shows its members
  palette: (id: number) =>
    axios.get<{ palette: PaletteItem[] }>(`${apiBase()}/api/courses/${id}/palette`, cfg),
  availablePresets: (id: number) =>
    axios.get<{ presets: PresetStyle[] }>(`${apiBase()}/api/courses/${id}/available-presets`, cfg),
  addPaletteItem: (id: number, body: {
    source_type: 'preset' | 'custom'
    preset_name?: string
    prompt_id?: number
    label?: string
  }) =>
    axios.post<{ item: PaletteItem }>(`${apiBase()}/api/courses/${id}/palette`, body, cfg),
  updatePaletteItem: (id: number, itemId: number,
                      patch: Partial<Pick<PaletteItem, 'label' | 'position' | 'enabled'>>) =>
    axios.patch<{ item: PaletteItem }>(`${apiBase()}/api/courses/${id}/palette/${itemId}`, patch, cfg),
  removePaletteItem: (id: number, itemId: number) =>
    axios.delete(`${apiBase()}/api/courses/${id}/palette/${itemId}`, cfg),

  // deletion (owner only, two-step)
  deletionImpact: (id: number) =>
    axios.get<{ impact: DeletionImpact }>(`${apiBase()}/api/courses/${id}/deletion-impact`, cfg),
  remove: (id: number, confirm: boolean) =>
    axios.delete(`${apiBase()}/api/courses/${id}`, { ...cfg, data: { confirm } }),
}
