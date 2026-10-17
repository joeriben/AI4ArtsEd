<!--
  LoraRegisterTab — the register of adapters, kept in the Settings.

  One row per file the platform offers (issue #70): its name, the trigger word
  that goes in front of the prompt, whose training it is, and to whom it is
  released — everyone, one course, or nobody. The models column is READ ONLY:
  the adapter file says what it was trained over, the server reads it, and a
  row of tick boxes made that look like a preference.

  Under the table stand the files the LoRA folder holds that no row
  names: what came before the register, and the accelerators of the video
  pipelines, which stay there. Registering one is a decision made here, never
  a sweep of the folder; a file whose training project still lies in the
  dataset folder is entered with that project's name and trigger word.

  A training at the training place writes its own row (released to the course
  the client was in; none when there was none); the two presets that bring an
  adapter have theirs written at start. This table is where the older files
  are entered once and where a release is changed.
-->
<template>
  <div class="lora-register">
    <div class="section">
      <h2>{{ t('settings.loras.title') }}</h2>
      <p class="help">{{ t('settings.loras.help') }}</p>
      <p v-if="loadError" class="err">{{ t('settings.loras.loadFailed', { cause: loadError }) }}</p>

      <table v-if="rows.length" class="config-table">
        <thead>
          <tr>
            <th>{{ t('settings.loras.file') }}</th>
            <th>{{ t('settings.loras.name') }}</th>
            <th>{{ t('settings.loras.trigger') }}</th>
            <th>{{ t('settings.loras.models') }}</th>
            <th>{{ t('settings.loras.owner') }}</th>
            <th>{{ t('settings.loras.category') }}</th>
            <th>{{ t('settings.loras.release') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id">
            <td>
              <div class="file-cell">
                <span
                  class="dot"
                  :class="{ present: r.present }"
                  :title="r.present ? t('settings.loras.present') : t('settings.loras.missing')"
                ></span>
                <select v-model="r.draft.file" class="text-input">
                  <option v-for="f in filesFor(r)" :key="f" :value="f">{{ f }}</option>
                </select>
              </div>
            </td>
            <td><input v-model="r.draft.name" class="text-input" /></td>
            <td><input v-model="r.draft.trigger" class="text-input" /></td>
            <td class="models-cell">
              <template v-if="r.present && modelNames(r).length">
                <span v-for="m in modelNames(r)" :key="m" class="model-name">{{ m }}</span>
              </template>
              <span v-else class="model-none">{{ modelNote(r) }}</span>
            </td>
            <td class="owner-cell">{{ r.owner_name || '—' }}</td>
            <td>
              <select v-model="r.draft.category" class="text-input">
                <option value="">{{ t('settings.loras.categoryNone') }}</option>
                <option v-for="c in kindsFor(r)" :key="c" :value="c">{{ kindLabel(c) }}</option>
              </select>
            </td>
            <td>
              <div class="release-cell">
                <select v-model="r.draft.visibility" class="text-input">
                  <option value="platform">{{ t('settings.loras.releasePlatform') }}</option>
                  <option value="course">{{ t('settings.loras.releaseCourse') }}</option>
                  <option value="none">{{ t('settings.loras.releaseNone') }}</option>
                </select>
                <select v-if="r.draft.visibility === 'course'" v-model="r.draft.course_id" class="text-input">
                  <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
              </div>
            </td>
            <td class="actions-cell">
              <button class="action-btn" :disabled="r.busy || !dirty(r)" @click="save(r)">
                {{ t('settings.loras.save') }}
              </button>
              <button class="action-btn danger" :disabled="r.busy" @click="remove(r)">
                {{ t('settings.loras.remove') }}
              </button>
              <p v-if="r.error" class="err">{{ t('settings.loras.saveFailed', { cause: r.error }) }}</p>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else-if="!loadError" class="help">{{ t('settings.loras.empty') }}</p>
    </div>

    <div v-if="unregistered.length" class="section">
      <h2>{{ t('settings.loras.unregistered') }}</h2>
      <ul class="unregistered">
        <li v-for="u in unregistered" :key="u.file">
          <code>{{ u.file }}</code>
          <span v-if="u.name !== u.file.replace(/\.safetensors$/, '')" class="prefill">{{ u.name }}</span>
          <span class="u-models">{{ modelsLine(u) }}</span>
          <button class="action-btn" :disabled="busyFile === u.file" @click="register(u)">
            {{ t('settings.loras.register') }}
          </button>
        </li>
      </ul>
      <p v-if="registerError" class="err">{{ t('settings.loras.saveFailed', { cause: registerError }) }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { LORA_CATEGORIES, type LoraAdapter } from '@/stores/loras'
import { apiBase } from '@/services/labApi'

const { t, te } = useI18n()

/**
 * The kinds a row may take: those the platform names, and — so that a kind
 * entered another way is not silently dropped by a save — the one the row
 * already carries.
 */
function kindsFor(r: Row): string[] {
  const known = [...LORA_CATEGORIES] as string[]
  const own = (r.category || '').trim()
  return own && !known.includes(own) ? [...known, own] : known
}

function kindLabel(key: string): string {
  const k = `x2xFlow.loraCategories.${key}`
  return te(k) || te(k, 'en') ? t(k) : key.replace(/_/g, ' ')
}

const API = () => `${apiBase()}/api/loras/register`

interface Draft {
  file: string
  name: string
  trigger: string
  /** The kind the chooser's ring sorts it by; empty until somebody says. */
  category: string
  visibility: LoraAdapter['visibility']
  course_id: number | null
}
interface Row extends LoraAdapter {
  draft: Draft
  busy: boolean
  error: string
}
/**
 * A file no row names, with what the server could read for it: the name and
 * trigger of the training project it came from, or the file's own stem and an
 * empty trigger.
 */
interface Unregistered {
  file: string
  name: string
  trigger: string
  /** What the file says it was trained over, and the configs that run it. */
  base: string
  base_configs: string[]
}

const rows = ref<Row[]>([])
const unregistered = ref<Unregistered[]>([])
const courses = ref<Array<{ id: number; name: string }>>([])
const carriers = ref<Array<{ id: string; name: string }>>([])
const loadError = ref('')
const registerError = ref('')
const busyFile = ref('')

function draftOf(r: LoraAdapter): Draft {
  return {
    file: r.file,
    name: r.name,
    trigger: r.trigger,
    category: r.category || '',
    visibility: r.visibility,
    course_id: r.course_id,
  }
}

function cause(e: any): string {
  return e?.response?.data?.error || e?.message || String(e)
}

async function load(): Promise<void> {
  loadError.value = ''
  try {
    const { data } = await axios.get(API(), { withCredentials: true })
    rows.value = (data.loras as LoraAdapter[]).map((r) => ({ ...r, draft: draftOf(r), busy: false, error: '' }))
    unregistered.value = data.unregistered || []
    courses.value = data.courses || []
    carriers.value = data.carriers || []
  } catch (e: any) {
    loadError.value = cause(e)
  }
}

/**
 * The configs of an id list, under the names the carriers carry, each name
 * once: two configs can run the same model and carry the same name, as
 * `sd35_large` and `sd35_large_diffusers` both carry “Stable Diffusion 3.5
 * Large”.
 */
function configNames(ids: string[]): string[] {
  const out: string[] = []
  for (const id of ids) {
    const name = carriers.value.find((c) => c.id === id)?.name || id
    if (!out.includes(name)) out.push(name)
  }
  return out
}

/**
 * What the models column shows. Nothing in it is editable: the file says which
 * model it was trained over and the output configs say which of them run that
 * model, so the column is read from both and set from neither.
 */
function modelNames(r: Row): string[] {
  return configNames(r.base_configs)
}

/** What stands there instead where no model is named. */
function modelNote(e: { present?: boolean; base?: string; base_configs: string[] }): string {
  if (e.present === false) return t('settings.loras.baseAbsent')
  return e.base
    ? t('settings.loras.baseUnmatched', { base: e.base })
    : t('settings.loras.baseMissing')
}

/** The same, on one line, for an entry the register does not hold yet. */
function modelsLine(e: { present?: boolean; base?: string; base_configs: string[] }): string {
  const names = configNames(e.base_configs)
  return names.length ? names.join(' · ') : modelNote(e)
}

/** The files a row may name: its own, and those no row names. */
function filesFor(r: Row): string[] {
  return [r.file, ...unregistered.value.map((u) => u.file).filter((f) => f !== r.file)]
}

function dirty(r: Row): boolean {
  const d = r.draft
  return (
    d.file !== r.file ||
    d.name !== r.name ||
    d.trigger !== r.trigger ||
    d.category !== (r.category || '') ||
    d.visibility !== r.visibility ||
    (d.course_id ?? null) !== (r.course_id ?? null)
  )
}

async function save(r: Row): Promise<void> {
  r.busy = true
  r.error = ''
  try {
    const { data } = await axios.put(`${API()}/${r.id}`, r.draft, { withCredentials: true })
    Object.assign(r, data, { draft: draftOf(data) })
    await load()
  } catch (e: any) {
    r.error = cause(e)
  } finally {
    r.busy = false
  }
}

async function remove(r: Row): Promise<void> {
  if (!window.confirm(t('settings.loras.removeConfirm', { name: r.name }))) return
  r.busy = true
  r.error = ''
  try {
    await axios.delete(`${API()}/${r.id}`, { withCredentials: true })
    await load()
  } catch (e: any) {
    r.error = cause(e)
    r.busy = false
  }
}

/** A file from the folder becomes a row, with what could be read for it, released nowhere until the row is edited. */
async function register(u: Unregistered): Promise<void> {
  busyFile.value = u.file
  registerError.value = ''
  try {
    await axios.post(
      API(),
      { file: u.file, name: u.name, trigger: u.trigger, visibility: 'none' },
      { withCredentials: true }
    )
    await load()
  } catch (e: any) {
    registerError.value = cause(e)
  } finally {
    busyFile.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.lora-register {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section {
  background: var(--surface-1);
  border: 1px solid var(--surface-3);
  padding: 15px;
}

.section h2 {
  margin: 0 0 10px 0;
  font-size: 16px;
  font-weight: 700;
  color: #e0e0e0;
}

.help {
  color: #b0b0b0;
  font-size: 13px;
  margin: 0 0 14px 0;
}

.err {
  color: #ff9e9e;
  font-size: 12px;
  margin: 6px 0 0;
}

.config-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid var(--surface-4);
  font-size: 13px;
}

.config-table th,
.config-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--surface-4);
  vertical-align: top;
  text-align: start;
}

.config-table th {
  color: #b0b0b0;
  font-weight: 400;
}

.text-input {
  width: 100%;
  box-sizing: border-box;
  padding: 6px 8px;
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 13px;
}

.file-cell {
  min-width: 260px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dot {
  flex: 0 0 auto;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #6a2036;
}

.dot.present {
  background: #3ecf8e;
}

.models-cell {
  min-width: 200px;
}

.model-name {
  display: block;
  margin: 2px 0;
  color: #d0d0d0;
  white-space: nowrap;
}

.model-none {
  color: #9a9a9a;
  font-size: 12px;
}

.owner-cell {
  color: #d0d0d0;
  white-space: nowrap;
}

.release-cell {
  min-width: 150px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.actions-cell {
  white-space: nowrap;
}

.action-btn {
  padding: 6px 12px;
  margin-inline-end: 6px;
  background: var(--surface-3);
  border: 1px solid var(--surface-4);
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 12px;
  cursor: pointer;
}

.action-btn:disabled {
  opacity: 0.45;
  cursor: default;
}

.action-btn.danger:not(:disabled):hover {
  border-color: #e0568a;
  color: #e0568a;
}

.unregistered {
  list-style: none;
  margin: 0;
  padding: 0;
}

.unregistered li {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px solid var(--surface-3);
}

.unregistered code {
  font-size: 12px;
  color: #d0d0d0;
}

.prefill {
  color: #b0b0b0;
  font-size: 12px;
}
/* The models of a file no row names, at the right end of its line — where the
   register's own column stands, so the eye reads the two lists the same way. */
.u-models {
  margin-left: auto;
  text-align: right;
  color: #9a9a9a;
  font-size: 12px;
}
</style>
