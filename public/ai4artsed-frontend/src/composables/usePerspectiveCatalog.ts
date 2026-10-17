import { computed, ref } from 'vue'
import { useConfigSelectionStore, type ConfigMetadata } from '@/stores/configSelection'
import { useLabAuthStore } from '@/stores/labAuth'
import { coursesApi, type PaletteItem } from '@/services/labApi'

/**
 * WHICH configs are perspectives — the platform's one answer, for every surface
 * that offers them.
 *
 * It stood twice until 2026-09-04: in the chooser
 * (`components/InterceptionPresetOverlay.vue`) and, two of its three filters
 * copied, in Perspectives on a Template. The copy dropped the third — the
 * active course's curated palette — so a member whose leader had enabled one
 * perspective was offered all of them on the instrument (Rule 13). What was
 * lifted out is the whole derivation: the two pipelines, the one excluded id,
 * and the narrowing by the course palette.
 *
 * What is NOT here: the configs a course cannot narrow (a config file marked
 * `hidden`, an output config, one without `properties`) never arrive — the
 * route drops them before the store sees them
 * (`devserver/my_app/routes/schema_pipeline_routes.py`,
 * `pipeline_configs_with_properties`).
 */

/**
 * The two pipelines an interception preset runs on. Everything else the store
 * carries is a mode (HeartMuLa, Latent Lab, the research presets) and no
 * perspective.
 */
export const PRESET_PIPELINES = new Set(['text_transformation', 'text_transformation_recursive'])

/** The one preset on those pipelines that is no perspective. */
export const EXCLUDED_IDS = new Set(['tonejs_composer'])

/**
 * The palette of the active course, read once for the whole surface rather than
 * once per component: two surfaces asking the same course the same question
 * would answer it differently only by accident.
 */
const coursePalette = ref<PaletteItem[]>([])

/**
 * WHOSE palette that is: the person and the course it was read for. It is
 * module state and outlives every component that reads it, so without this it
 * outlives the course and the person as well — one member works in a course
 * that offers one perspective, the next person logs in to another course
 * without the page being loaded again, their own read fails, and they are
 * offered the first one's narrowed list.
 */
const paletteFor = ref<string>('')

export function usePerspectiveCatalog() {
  const configStore = useConfigSelectionStore()
  const auth = useLabAuthStore()

  /**
   * Who a palette would be about. The course, because that is what a palette
   * belongs to; and the person, because a session can change hands without the
   * page being loaded again, and the same course id read under another session
   * is another answer.
   */
  const identity = computed(() => `${auth.user?.id ?? ''}|${auth.activeCourseId ?? ''}`)

  /**
   * The palette of the active course (P3): the list its leader curated. While
   * it carries at least one GIVEN perspective, the platform offers those and no
   * others — that IS the narrowing, expressed purely by what the leader
   * included.
   *
   * A palette holding only course-owned kept perspectives narrows nothing yet:
   * those are curated but not offered here (see the note in CourseEditor).
   * Narrowing on them would leave a member facing an empty surface.
   */
  const allowedPresetNames = computed<Set<string> | null>(() => {
    // A palette read for another course or under another session says nothing
    // about this one, so it narrows nothing here.
    if (paletteFor.value !== identity.value) return null
    // Two different situations that must not be confused:
    //   no given perspective in the palette at all → the course narrows nothing
    //   given ones are in it, all switched off     → it offers none of them
    // Reading the second as the first turned "withhold all three" into "show the
    // whole catalogue", which is the opposite of what the leader did.
    const hasPresetItems = coursePalette.value.some((i) => i.source_type === 'preset')
    if (!hasPresetItems) return null
    return new Set(
      coursePalette.value
        .filter((i) => i.enabled && i.source_type === 'preset' && i.preset_name)
        .map((i) => i.preset_name as string),
    )
  })

  /** The perspectives the platform offers right now, in the store's order. */
  const perspectives = computed<ConfigMetadata[]>(() => {
    const all = configStore.availableConfigs.filter(
      (config) => PRESET_PIPELINES.has(config.pipeline) && !EXCLUDED_IDS.has(config.id),
    )
    const allowed = allowedPresetNames.value
    return allowed ? all.filter((c) => allowed.has(c.id)) : all
  })

  async function loadCoursePalette(): Promise<void> {
    const who = identity.value
    // What was kept belongs to the course and the session it was read for.
    // Where that has changed, it goes BEFORE this reading and not after it: a
    // read that fails would otherwise leave the other course's narrowing
    // standing over this one. What is then in force until the answer arrives is
    // an empty palette, which narrows nothing — the state this surface was in
    // before its first read has ever landed.
    if (paletteFor.value !== who) {
      coursePalette.value = []
      paletteFor.value = who
    }
    const cid = auth.activeCourseId
    if (!cid) {
      coursePalette.value = []
      return
    }
    try {
      const { data } = await coursesApi.palette(cid)
      // The session or the course changed while this was out; the answer is
      // about a state that is gone. Both have to hold: the identity, because the
      // answer is about a course somebody has since left; and the LABEL on the
      // slot, because a read that started later has since claimed it for another
      // course. Read out A, switch to B (which clears the palette and relabels
      // it), switch back to A, and A's late answer lands: the identity matches
      // again while the slot still says B, so A's list would be handed out as
      // B's narrowing on the next switch there -- with no read of B's own left
      // to correct it.
      if (identity.value !== who || paletteFor.value !== who) return
      coursePalette.value = data.palette
    } catch {
      // Something went wrong reading it — a hiccup, or access that has since been
      // withdrawn. What must NOT happen here is clearing it: an empty palette
      // means "narrows nothing", so a failed read would silently hand out the
      // whole catalogue. Whatever was read last stays — and it is what was read
      // for THIS course and THIS session, because anything older went above.
      // eslint-disable-next-line no-console
      console.warn('[palette] could not be read; keeping the last one')
    }
  }

  /** The given perspectives themselves, where a surface has not read them yet. */
  async function ensureConfigs(): Promise<void> {
    if (configStore.availableConfigs.length === 0) await configStore.loadConfigs()
  }

  return { perspectives, allowedPresetNames, loadCoursePalette, ensureConfigs }
}
