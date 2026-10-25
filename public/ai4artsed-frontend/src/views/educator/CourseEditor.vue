<!--
  Manage a single course (P1). Route: /educator/courses/:id  (requiresRole: 'educator')

  Sections: settings (name/safety/privacy), the PLACES, the palette,
  co-leaders, and a two-step cascade Delete-course flow (deletion-impact
  preview + confirmation).

  Places (2026-09-23): a course has numbered places, one per device, and each
  place has a code of five characters. The platform keeps only the code's
  hash, so a code is shown once, right after it is made, and is copied or
  printed as slips from there. A code enters its course while the access
  window is open (`access_until`). The platform keeps no name for a place:
  which person uses which device is the institution's own record.

  Since 2026-08-15 also the PALETTE (P3): the opt-in list of perspectives this
  course shows its members. It narrows what the perspective chooser offers, and
  only for the GIVEN perspectives — a course-owned kept perspective is curated
  here but not yet offered in the chooser (that turns on whether participants may
  read and change their leader's wording, which is not decided). A palette with
  no given perspective in it therefore narrows nothing. Black background.
-->
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  coursesApi,
  type Course,
  type CoursePlace,
  type DeletionImpact,
  type IssuedPlace,
  type PaletteItem,
  type PresetStyle,
} from '../../services/labApi'
import { useKeptPerspectivesStore } from '../../stores/keptPerspectives'
import { useI18n } from 'vue-i18n'
import SurfaceConfirm from '../../components/SurfaceConfirm.vue'

const route = useRoute()
const router = useRouter()
const courseId = Number(route.params.id)

const course = ref<Course | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const { t, locale } = useI18n()

const newCoLeader = ref('')

// places
/** The codes made on this visit of the page. Each one is shown only here, so a
 *  later action adds to the list and takes nothing out of it. */
const revealed = ref<IssuedPlace[]>([])
const deviceCount = ref<number | ''>(1)
const accessUntilInput = ref('')        // datetime-local, this browser's time zone
const placesBusy = ref(false)
const copied = ref(false)
/** The number of the place whose code waits for the leader's yes before it
 *  is replaced. */
const replacing = ref<number | null>(null)

const places = computed<CoursePlace[]>(() => course.value?.places ?? [])
const deviceCountValid = computed(() => {
  const n = deviceCount.value
  return typeof n === 'number' && Number.isInteger(n) && n >= 1 && n <= 100
})

// palette (P3)
const kept = useKeptPerspectivesStore()
const palette = ref<PaletteItem[]>([])
const presetStyles = ref<PresetStyle[]>([])
const paletteBusy = ref(false)
const addPreset = ref('')
const addKept = ref('')

/** The presets this course does not carry yet, by display name. */
const addablePresets = computed(() =>
  presetStyles.value
    .filter((s) => !s.in_palette)
    .sort((a, b) => presetLabel(a).localeCompare(presetLabel(b))),
)

/** What the leader keeps and has published — only a published perspective can
 *  be shown to a course, because the course reads it, not its author. */
const addableKept = computed(() =>
  kept.items.filter(
    (p) => p.is_published && !palette.value.some((i) => i.prompt_id === p.id),
  ),
)

function presetLabel(s: PresetStyle): string {
  return s.display_name?.en || s.display_name?.de || s.name
}

function itemLabel(i: PaletteItem): string {
  if (i.label) return i.label
  if (i.source_type === 'preset') {
    const s = presetStyles.value.find((x) => x.name === i.preset_name)
    return s ? presetLabel(s) : (i.preset_name ?? '')
  }
  return kept.byId(i.prompt_id ?? 0)?.name ?? i.style_key
}

// delete flow
const showDeleteModal = ref(false)
const deletionImpact = ref<DeletionImpact | null>(null)
const deleteConfirmText = ref('')
const busy = ref(false)

onMounted(async () => {
  await load()
  await loadPalette()
})

// ---- palette ---------------------------------------------------------------
async function loadPalette() {
  try {
    const [p, s] = await Promise.all([
      coursesApi.palette(courseId),
      coursesApi.availablePresets(courseId),
    ])
    palette.value = p.data.palette
    presetStyles.value = s.data.presets
    await kept.load()
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? t('educator.paletteFailed')
  }
}

async function addToPalette(body: Parameters<typeof coursesApi.addPaletteItem>[1]) {
  paletteBusy.value = true
  error.value = null
  try {
    const { data } = await coursesApi.addPaletteItem(courseId, body)
    palette.value.push(data.item)
    const s = presetStyles.value.find((x) => x.name === data.item.preset_name)
    if (s) s.in_palette = true
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? t('educator.paletteFailed')
  } finally {
    paletteBusy.value = false
  }
}

async function addPresetToPalette() {
  if (!addPreset.value) return
  await addToPalette({ source_type: 'preset', preset_name: addPreset.value })
  addPreset.value = ''
}

async function addKeptToPalette() {
  if (!addKept.value) return
  await addToPalette({ source_type: 'custom', prompt_id: Number(addKept.value) })
  addKept.value = ''
}

async function togglePaletteItem(i: PaletteItem) {
  error.value = null
  try {
    const { data } = await coursesApi.updatePaletteItem(courseId, i.id, { enabled: !i.enabled })
    Object.assign(i, data.item)
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? t('educator.paletteFailed')
    await loadPalette()
  }
}

/** Move one entry by one place. Both rows are written, so the order the course
 *  reads is the order shown here. */
async function movePaletteItem(i: PaletteItem, delta: number) {
  const idx = palette.value.indexOf(i)
  const other = palette.value[idx + delta]
  if (!other) return
  paletteBusy.value = true
  error.value = null
  try {
    const a = i.position
    const b = other.position
    await coursesApi.updatePaletteItem(courseId, i.id, { position: b })
    await coursesApi.updatePaletteItem(courseId, other.id, { position: a })
    i.position = b
    other.position = a
    palette.value.sort((x, y) => x.position - y.position)
  } catch (e: any) {
    // The two writes are not one operation. If the second fails, both rows can
    // hold the same position and the order here would no longer be the order
    // the course reads — so the list is read back rather than guessed at.
    error.value = e?.response?.data?.error ?? t('educator.paletteFailed')
    await loadPalette()
  } finally {
    paletteBusy.value = false
  }
}

async function removePaletteItem(i: PaletteItem) {
  error.value = null
  try {
    await coursesApi.removePaletteItem(courseId, i.id)
    palette.value = palette.value.filter((x) => x.id !== i.id)
    const s = presetStyles.value.find((x) => x.name === i.preset_name)
    if (s) s.in_palette = false
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? t('educator.paletteFailed')
    await loadPalette()
  }
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const { data } = await coursesApi.get(courseId)
    course.value = data.course
    if (!accessUntilInput.value) accessUntilInput.value = initialAccessUntil(data.course)
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? 'Failed to load course'
  } finally {
    loading.value = false
  }
}

// ---- settings --------------------------------------------------------------
async function saveSettings() {
  if (!course.value) return
  try {
    const { data } = await coursesApi.update(courseId, {
      title: course.value.name,
      safety_level: course.value.safety_level,
      educator_can_view_participant_works: course.value.educator_can_view_participant_works,
    })
    course.value = { ...course.value, ...data.course }
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? 'Failed to save settings'
  }
}

// ---- co-leaders ------------------------------------------------------------
async function addCoLeader() {
  if (!newCoLeader.value.trim()) return
  try {
    await coursesApi.addEducator(courseId, newCoLeader.value.trim())
    newCoLeader.value = ''
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? 'Failed to add co-leader'
  }
}

// ---- places ----------------------------------------------------------------
/** A moment in the reader's language: day, month, (year,) hour and minute. */
function formatMoment(iso: string, withYear = true): string {
  return new Date(iso).toLocaleString(locale.value, {
    day: '2-digit',
    month: '2-digit',
    ...(withYear ? { year: 'numeric' as const } : {}),
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** A Date as the value of a datetime-local field, in this browser's time zone. */
function toLocalInput(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}

/** Where the field starts: the end of the window while it is open, otherwise
 *  24 hours ahead at the next full hour. */
function initialAccessUntil(c: Course): string {
  if (c.access_open && c.access_until) return toLocalInput(new Date(c.access_until))
  const d = new Date(Date.now() + 24 * 3600 * 1000)
  if (d.getMinutes() || d.getSeconds() || d.getMilliseconds()) d.setHours(d.getHours() + 1, 0, 0, 0)
  return toLocalInput(d)
}

/** A failed place request in words: the server's own line, the status it
 *  answered with, or that the server gave no answer. */
function placesError(e: any): string {
  const said = e?.response?.data?.error
  if (said) return said
  const status = e?.response?.status
  return status ? t('educator.placesStatus', { status }) : t('educator.placesNoAnswer')
}

async function applyAccess() {
  if (!course.value || !accessUntilInput.value) return
  const until = new Date(accessUntilInput.value)
  if (Number.isNaN(until.getTime())) return
  if (until.getTime() <= Date.now()) {
    error.value = t('educator.accessUntilPast')
    return
  }
  placesBusy.value = true
  error.value = null
  try {
    const { data } = await coursesApi.openAccess(courseId, until.toISOString())
    course.value = { ...course.value, ...data.course }
    accessUntilInput.value = initialAccessUntil(course.value)
  } catch (e: any) {
    error.value = placesError(e)
  } finally {
    placesBusy.value = false
  }
}

async function endAccess() {
  if (!course.value) return
  placesBusy.value = true
  error.value = null
  try {
    const { data } = await coursesApi.closeAccess(courseId)
    course.value = { ...course.value, ...data.course }
    accessUntilInput.value = initialAccessUntil(course.value)
  } catch (e: any) {
    error.value = placesError(e)
  } finally {
    placesBusy.value = false
  }
}

/** Take codes into the list shown once: a place that already stands in it
 *  gets its newer code, and the list stays in the order of the numbers. */
function reveal(issued: IssuedPlace[]) {
  const byNumber = new Map(revealed.value.map((p) => [p.number, p]))
  for (const p of issued) byNumber.set(p.number, p)
  revealed.value = [...byNumber.values()].sort((a, b) => a.number - b.number)
  copied.value = false
}

async function makeCodes() {
  if (!deviceCountValid.value) return
  placesBusy.value = true
  error.value = null
  try {
    const { data } = await coursesApi.addPlaces(courseId, deviceCount.value as number)
    reveal(data.places)
    await load()
  } catch (e: any) {
    error.value = placesError(e)
  } finally {
    placesBusy.value = false
  }
}

/** A new code for one place. The old one stops entering the course, and a
 *  device still signed in with it is signed out at its next request. */
async function issueCode(p: CoursePlace) {
  placesBusy.value = true
  error.value = null
  try {
    const { data } = await coursesApi.replacePlaceCode(courseId, p.number)
    reveal([{ number: data.place.number, code: data.place.code }])
    p.has_code = data.place.has_code
    p.code_issued_at = data.place.code_issued_at
  } catch (e: any) {
    error.value = placesError(e)
  } finally {
    placesBusy.value = false
  }
}

/** A place that has a code asks first: its new code signs out a device that
 *  entered with the old one. A place without a code gets its first at once.
 *  Behind the open delete dialog the list does nothing: a key still reaches
 *  its buttons there. */
function askIssueCode(p: CoursePlace) {
  if (showDeleteModal.value) return
  if (p.has_code) replacing.value = p.number
  else issueCode(p)
}

/** The place is looked up anew: a reload of the course since the question
 *  holds other objects. */
async function replaceConfirmed() {
  const p = places.value.find((q) => q.number === replacing.value)
  replacing.value = null
  if (p) await issueCode(p)
}

async function copyCodes() {
  if (!revealed.value.length) return
  error.value = null
  const text = revealed.value
    .map((p) => `${t('educator.placeLabel', { n: p.number })}: ${p.code}`)
    .join('\n')
  // A browser offers its clipboard in a secure context alone: HTTPS, or the
  // machine itself. An installation in a school network may be plain HTTP.
  if (!window.isSecureContext) {
    error.value = t('educator.clipboardHttpsOnly', revealed.value.length)
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    error.value = t('educator.copyFailed', revealed.value.length)
  }
}

function esc(s: string): string {
  const map: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
  return s.replace(/[&<>"']/g, (c) => map[c] ?? c)
}

const SLIP_CSS = [
  '@page { margin: 10mm; }',
  'body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #000; }',
  '.sheet { display: grid; grid-template-columns: repeat(3, 1fr); }',
  '.slip { border: 1px dashed #888; padding: 8mm 4mm; text-align: center; break-inside: avoid; }',
  '.head { font-size: 10pt; }',
  '.code { font: 600 20pt ui-monospace, Menlo, Consolas, monospace; letter-spacing: 0.15em; margin: 3mm 0; }',
  '.where { font-size: 9pt; }',
].join('\n')

/** One slip per place, to cut out: course and place, the code, and where it
 *  is entered. The browser's print dialog does the rest. */
function printSlips() {
  if (!course.value || !revealed.value.length) return
  error.value = null
  const w = window.open('', '_blank')
  if (!w) {
    error.value = t('educator.printBlocked')
    return
  }
  const name = esc(course.value.name)
  const where = esc(t('educator.slipSignIn', { address: `${location.host}/login` }))
  const slips = revealed.value
    .map((p) =>
      `<div class="slip"><div class="head">${name} · ${esc(t('educator.placeLabel', { n: p.number }))}</div>` +
      `<div class="code">${esc(p.code)}</div><div class="where">${where}</div></div>`)
    .join('')
  w.document.write(
    `<!doctype html><html lang="${esc(locale.value)}"><head><meta charset="utf-8"><title>${name}</title>` +
    `<style>${SLIP_CSS}</style></head>` +
    `<body onload="setTimeout(() => { window.print(); window.close() }, 150)"><div class="sheet">${slips}</div></body></html>`,
  )
  w.document.close()
}

// ---- delete course ---------------------------------------------------------
async function openDeleteModal() {
  replacing.value = null
  busy.value = true
  try {
    deletionImpact.value = (await coursesApi.deletionImpact(courseId)).data.impact
    deleteConfirmText.value = ''
    replacing.value = null          // a row opened while the impact was read
    showDeleteModal.value = true
  } finally {
    busy.value = false
  }
}

const deleteAcknowledged = computed(
  () => !!course.value && deleteConfirmText.value.trim() === course.value.name.trim(),
)

async function confirmDelete() {
  if (!deleteAcknowledged.value) return
  busy.value = true
  try {
    await coursesApi.remove(courseId, true)
    showDeleteModal.value = false
    router.push('/educator')
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? 'Failed to delete course'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="course" v-if="course">
    <header>
      <div>
        <router-link to="/educator" class="back">&larr; {{ $t('common.back') }}</router-link>
        <h1>{{ course.name }}</h1>
      </div>
    </header>

    <p v-if="error" class="err">{{ error }}</p>

    <!-- settings -->
    <section class="block">
      <h2>{{ $t('educator.settings') }}</h2>
      <label>{{ $t('educator.promptName') }}</label>
      <input v-model="course.name" @blur="saveSettings" />
      <label>{{ $t('educator.safety') }}</label>
      <select v-model="course.safety_level" @change="saveSettings">
        <option value="kids">kids</option>
        <option value="youth">youth</option>
        <option value="open">open</option>
      </select>
      <label class="check">
        <input type="checkbox" v-model="course.educator_can_view_participant_works" @change="saveSettings" />
        {{ $t('educator.canViewWorks') }}
      </label>
      <p class="help">{{ $t('educator.canViewWorksHelp') }}</p>
    </section>

    <!-- places: one per device, each entered with its code -->
    <section class="block places">
      <h2>{{ $t('educator.places') }} <span class="count">({{ places.length }})</span></h2>
      <p class="status">
        <span v-if="course.access_open && course.access_until" class="access-on">
          {{ $t('educator.accessOpenUntil', { until: formatMoment(course.access_until) }) }}
        </span>
        <span v-else class="access-off">{{ $t('educator.accessClosed') }}</span>
      </p>

      <div class="row">
        <label class="inline" for="access-until">{{ $t('educator.accessUntil') }}</label>
        <input id="access-until" v-model="accessUntilInput" type="datetime-local" class="when" />
        <button class="primary" :disabled="placesBusy || !accessUntilInput" @click="applyAccess">
          {{ course.access_open ? $t('educator.changeAccess') : $t('educator.openAccess') }}
        </button>
        <button v-if="course.access_open" class="danger" :disabled="placesBusy" @click="endAccess">
          {{ $t('educator.closeAccess') }}
        </button>
      </div>

      <div class="row">
        <label class="inline" for="device-count">{{ $t('educator.deviceCount') }}</label>
        <input id="device-count" v-model.number="deviceCount" type="number" min="1" max="100" step="1" class="num" />
        <button class="primary" :disabled="placesBusy || !deviceCountValid" @click="makeCodes">
          {{ $t('educator.makeCodes') }}
        </button>
      </div>

      <div v-if="revealed.length" class="revealed">
        <ul class="codes">
          <li v-for="p in revealed" :key="p.number">
            <span class="place">{{ $t('educator.placeLabel', { n: p.number }) }}</span>
            <code class="big-key">{{ p.code }}</code>
          </li>
        </ul>
        <div class="row">
          <button class="ghost" @click="copyCodes">{{ copied ? $t('educator.copied') : $t('educator.copy') }}</button>
          <button class="ghost" @click="printSlips">{{ $t('educator.print') }}</button>
        </div>
        <p class="once">{{ $t('educator.codesShownOnce', { n: revealed.length }, revealed.length) }}</p>
      </div>

      <ul class="roster place-rows" v-if="places.length">
        <li v-for="p in places" :key="p.number">
          <span class="name">{{ $t('educator.placeLabel', { n: p.number }) }}</span>
          <span v-if="p.has_code && p.code_issued_at" class="issued">
            {{ $t('educator.codeIssued', { when: formatMoment(p.code_issued_at, false) }) }}
          </span>
          <button class="ghost small" :disabled="placesBusy" @click="askIssueCode(p)">
            {{ p.has_code ? $t('educator.replaceCode') : $t('educator.makeCode') }}
          </button>
        </li>
      </ul>
      <p class="help">{{ $t('educator.placesHelp') }}</p>
    </section>

    <!-- palette: what this course shows -->
    <section class="block">
      <h2>
        {{ $t('educator.palette') }}
        <span class="count">({{ palette.length }})</span>
      </h2>
      <p class="help">
        {{ palette.length ? $t('educator.paletteHelp') : $t('educator.paletteEmptyHelp') }}
      </p>

      <ul class="roster" v-if="palette.length">
        <li v-for="(i, idx) in palette" :key="i.id" :class="{ off: !i.enabled }">
          <span class="name">{{ itemLabel(i) }}</span>
          <code class="uname">{{ i.style_key }}</code>
          <button class="icon" :disabled="idx === 0 || paletteBusy"
                  :aria-label="$t('educator.paletteUp')" @click="movePaletteItem(i, -1)">↑</button>
          <button class="icon" :disabled="idx === palette.length - 1 || paletteBusy"
                  :aria-label="$t('educator.paletteDown')" @click="movePaletteItem(i, 1)">↓</button>
          <button class="icon" :aria-label="$t('educator.paletteToggle')"
                  @click="togglePaletteItem(i)">{{ i.enabled ? '◉' : '○' }}</button>
          <button class="icon remove" :aria-label="$t('common.remove')"
                  @click="removePaletteItem(i)">✕</button>
        </li>
      </ul>

      <div class="row">
        <select v-model="addPreset">
          <option value="">{{ $t('educator.paletteAddPreset') }}</option>
          <option v-for="s in addablePresets" :key="s.name" :value="s.name">
            {{ presetLabel(s) }}
          </option>
        </select>
        <button class="primary" :disabled="!addPreset || paletteBusy" @click="addPresetToPalette">
          {{ $t('educator.paletteAdd') }}
        </button>
      </div>

      <div class="row">
        <select v-model="addKept">
          <option value="">{{ $t('educator.paletteAddKept') }}</option>
          <option v-for="p in addableKept" :key="p.id" :value="String(p.id)">
            {{ p.name }}
          </option>
        </select>
        <button class="primary" :disabled="!addKept || paletteBusy" @click="addKeptToPalette">
          {{ $t('educator.paletteAdd') }}
        </button>
      </div>
      <p class="help">{{ $t('educator.paletteKeptHelp') }}</p>
    </section>

    <!-- co-leaders -->
    <section class="block">
      <h2>{{ $t('educator.coLeaders') }}</h2>
      <div class="row">
        <input v-model="newCoLeader" :placeholder="$t('educator.coLeaderIdentifier')" @keyup.enter="addCoLeader" />
        <button class="primary" @click="addCoLeader">{{ $t('educator.addCoLeader') }}</button>
      </div>
      <p class="help">{{ $t('educator.coLeaderHelp') }}</p>
    </section>

    <!-- DANGER ZONE -->
    <section class="block danger-zone">
      <h2>{{ $t('educator.dangerZone') }}</h2>
      <p class="help">{{ $t('educator.deleteCourseHelp') }}</p>
      <button class="danger" :disabled="busy" @click="openDeleteModal">{{ $t('educator.deleteCourse') }}</button>
    </section>

    <!-- delete modal -->
    <div v-if="showDeleteModal" class="modal-backdrop" @click.self="showDeleteModal = false">
      <div class="modal" role="dialog" aria-modal="true">
        <h2 class="modal-title">{{ $t('educator.deleteCourseTitle', { name: course.name }) }}</h2>
        <p class="modal-warn">{{ $t('educator.deleteCourseWarning') }}</p>
        <ul class="impact" v-if="deletionImpact">
          <li>{{ $t('educator.impactParticipants', { n: deletionImpact.places }, deletionImpact.places) }}</li>
          <li>{{ $t('educator.impactWorks', { n: deletionImpact.course_works }) }}</li>
        </ul>
        <p class="dsgvo">{{ $t('educator.deleteCourseDsgvo') }}</p>
        <p class="preset-safe">{{ $t('educator.deleteCoursePresetsSafe') }}</p>
        <label>{{ $t('educator.deleteConfirmPrompt', { name: course.name }) }}</label>
        <input v-model="deleteConfirmText" type="text" :placeholder="course.name" />
        <div class="modal-actions">
          <button class="ghost" @click="showDeleteModal = false">{{ $t('common.cancel') }}</button>
          <button class="danger" :disabled="busy || !deleteAcknowledged" @click="confirmDelete">
            {{ $t('educator.deleteCourseConfirm') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Replacing a code signs out a device that entered with the old one, so
         the leader says yes to it first. The yes waits while
         another change of the places is under way, as the buttons of the
         list do. Over the app: this page is a layer of its own, and the
         footer gallery would cover the row. -->
    <SurfaceConfirm
      v-if="replacing !== null"
      :text="$t('educator.replaceCodeConfirm', { n: replacing })"
      :yes="$t('educator.replaceCode')"
      :cancel="$t('common.cancel')"
      danger
      :disabled="placesBusy"
      over-app
      @confirm="replaceConfirmed"
      @cancel="replacing = null"
    />
  </div>
</template>

<style scoped>
.roster li.off .name,
.roster li.off .uname { opacity: 0.45; }

.course { position: fixed; inset: 0; top: 56px; background: var(--bg-base); color: rgba(255,255,255,0.9); padding: 24px; overflow-y: auto; max-width: 860px; }
header { display: flex; justify-content: space-between; align-items: flex-start; }
.back { color: rgba(255,255,255,0.5); text-decoration: none; font-size: 0.8rem; }
h1 { font-size: 1.3rem; margin: 4px 0 0; }
.uname { color: #4caf50; }
.block { margin-top: 24px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.1); }
h2 { font-size: 1rem; }
.count { color: rgba(255,255,255,0.4); font-weight: 400; }
label { display: block; font-size: 0.8rem; margin: 12px 0 4px; color: rgba(255,255,255,0.6); }
label.check { display: flex; gap: 8px; align-items: center; color: rgba(255,255,255,0.85); }
.help { font-size: 0.74rem; color: rgba(255,255,255,0.45); }
.row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-top: 8px; }
.row input { flex: 1; min-width: 160px; }
input, select { padding: 9px; border-radius: 8px; background: var(--surface-1); color: #fff; border: 1px solid rgba(255,255,255,0.15); }
input:focus, select:focus { outline: none; border-color: #4caf50; }

/* places */
.places .status { margin: 6px 0; }
.access-on { color: #4caf50; }
.access-off { color: rgba(255,255,255,0.4); }
.row label.inline { display: inline; margin: 0; }
.row input.when { flex: 0 1 240px; min-width: 200px; color-scheme: dark; }
.row input.num { flex: 0 0 90px; min-width: 0; }
.revealed { background: var(--surface-1); border: 1px solid rgba(76,175,80,0.4); border-radius: 10px; padding: 16px; margin: 12px 0; }
.codes { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 8px 20px; }
.codes li { display: flex; align-items: baseline; gap: 12px; }
.codes .place { font-size: 0.8rem; color: rgba(255,255,255,0.6); min-width: 64px; }
.big-key { font-size: 1.4rem; letter-spacing: 0.12em; color: #4caf50; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.once { margin: 10px 0 0; font-size: 0.74rem; color: #ffcc80; }
.place-rows li { flex-wrap: wrap; }
.roster.place-rows .name { flex: 0 0 auto; min-width: 72px; }
.place-rows .issued { font-size: 0.78rem; color: rgba(255,255,255,0.5); }
.place-rows button { margin-left: auto; }
.ghost.small { padding: 4px 10px; font-size: 0.8rem; }
.ghost:disabled { opacity: 0.4; cursor: not-allowed; }

/* roster */
.roster { list-style: none; padding: 0; margin: 12px 0 0; }
.roster li { display: flex; gap: 10px; align-items: center; padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.06); }
.roster .name { flex: 1; }
.icon { background: transparent; border: 1px solid rgba(255,255,255,0.15); color: #fff; border-radius: 6px; cursor: pointer; width: 26px; line-height: 1; padding: 3px 0; }
.icon.remove { border-color: rgba(255,107,107,0.4); color: #ff6b6b; }

.primary { background: #4caf50; color: #fff; border: none; border-radius: 8px; padding: 9px 16px; cursor: pointer; }
.primary:disabled { opacity: 0.4; cursor: not-allowed; }
.ghost { color: #fff; border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; padding: 7px 14px; text-decoration: none; background: transparent; cursor: pointer; }
.danger { background: transparent; color: #ff6b6b; border: 1px solid rgba(255,107,107,0.5); border-radius: 8px; padding: 9px 16px; cursor: pointer; }
.danger:disabled { opacity: 0.4; cursor: not-allowed; }

/* danger zone */
.danger-zone { border-top-color: rgba(255,107,107,0.3); }

/* delete modal */
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: var(--bg-base); border: 1px solid rgba(255,107,107,0.4); border-radius: 12px; padding: 24px; width: min(560px, 92vw); color: rgba(255,255,255,0.9); }
.modal-title { font-size: 1.05rem; margin: 0 0 8px; }
.modal-warn { color: #ff6b6b; font-weight: 700; }
.impact { list-style: disc; padding-left: 20px; margin: 12px 0; }
.dsgvo { font-size: 0.78rem; color: #ffcc80; }
.preset-safe { font-size: 0.78rem; color: #80cbc4; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.err { color: #ff6b6b; font-size: 0.85rem; }
</style>
