<template>
  <div class="knowledge-library">
    <!-- ==================== Wissensbereiche (MoJo chips) ==================== -->
    <div class="section">
      <h2>{{ $t('settings.knowledge.areas.title') }}</h2>
      <p class="help">{{ $t('settings.knowledge.areas.help') }}</p>

      <div class="area-chips">
        <!-- one chip per operator area -->
        <div
          v-for="a in operatorAreas"
          :key="a.id"
          :class="['area-chip', { active: activeAreaId === a.id, editing: editChip.open && editChip.id === a.id }]"
        >
          <!-- display -->
          <div v-if="!(editChip.open && editChip.id === a.id)" class="chip-display" @click="selectArea(a.id)">
            <span class="chip-name">{{ a.name }}</span>
            <span class="chip-count">{{ docCountLabel(a) }}</span>
            <button
              v-if="activeAreaId === a.id"
              class="chip-edit-btn"
              :title="$t('settings.knowledge.areas.edit')"
              @click.stop="openChipEdit(a)"
            >✎</button>
          </div>

          <!-- inline edit (MoJo pattern: name + note + OK/Cancel/Delete) -->
          <div v-else class="chip-edit">
            <input
              v-model="editChip.name"
              class="chip-input"
              :placeholder="$t('settings.knowledge.areas.editName')"
              @keyup.enter="saveChipEdit"
            />
            <input
              v-model="editChip.kommentar"
              class="chip-input"
              :placeholder="$t('settings.knowledge.areas.editKommentar')"
            />
            <div class="chip-edit-actions">
              <button class="chip-btn primary" :disabled="editChip.saving" @click="saveChipEdit">
                {{ editChip.saving ? $t('settings.knowledge.areas.saving') : $t('settings.knowledge.areas.save') }}
              </button>
              <button class="chip-btn" @click="editChip.open = false">{{ $t('settings.knowledge.areas.cancel') }}</button>
              <button class="chip-btn danger" @click="deleteArea(a)">{{ $t('settings.knowledge.areas.delete') }}</button>
            </div>
            <span v-if="editChip.error" class="chip-err">{{ editChip.error }}</span>
          </div>
        </div>

        <!-- UNESCO fixed pseudo-area chip -->
        <div
          v-if="unescoArea"
          :class="['area-chip', 'fixed', { active: activeAreaId === unescoArea.id }]"
        >
          <div class="chip-display" :title="$t('settings.knowledge.areas.unescoHint')" @click="selectArea(unescoArea.id)">
            <span class="chip-lock" aria-hidden="true">🔒</span>
            <span class="chip-name">{{ $t('settings.knowledge.areas.unescoName') }}</span>
            <span class="chip-count">{{ docCountLabel(unescoArea) }}</span>
            <span class="chip-fixed-tag">{{ $t('settings.knowledge.areas.fixed') }}</span>
          </div>
        </div>

        <!-- dashed "+ Neu" add chip -->
        <div :class="['area-chip', 'add', { editing: addChip.open }]">
          <div v-if="!addChip.open" class="chip-display" @click="openAddChip">
            <span class="chip-add-label">{{ $t('settings.knowledge.areas.addChip') }}</span>
          </div>
          <div v-else class="chip-edit">
            <input
              ref="addNameInput"
              v-model="addChip.name"
              class="chip-input"
              :placeholder="$t('settings.knowledge.areas.newName')"
              @keyup.enter="createArea"
            />
            <input
              v-model="addChip.kommentar"
              class="chip-input"
              :placeholder="$t('settings.knowledge.areas.newKommentar')"
            />
            <div class="chip-edit-actions">
              <button class="chip-btn primary" :disabled="addChip.saving" @click="createArea">
                {{ addChip.saving ? $t('settings.knowledge.areas.creating') : $t('settings.knowledge.areas.create') }}
              </button>
              <button class="chip-btn" @click="addChip.open = false">{{ $t('settings.knowledge.areas.cancel') }}</button>
            </div>
            <span v-if="addChip.error" class="chip-err">{{ addChip.error }}</span>
          </div>
        </div>
      </div>

      <p v-if="!activeAreaId" class="hint select-hint">{{ $t('settings.knowledge.areas.selectHint') }}</p>
    </div>

    <!-- ==================== Bereichs-Panel (active area) ==================== -->
    <div v-if="activeArea" class="section area-panel">
      <h2>
        <span v-if="activeArea.fixed" class="chip-lock" aria-hidden="true">🔒</span>
        {{ activeArea.fixed ? $t('settings.knowledge.areas.unescoName') : activeArea.name }}
      </h2>

      <!-- kommentar (agent note) — editable for operator areas -->
      <div v-if="!activeArea.fixed" class="kommentar-block">
        <div class="kommentar-label">{{ $t('settings.knowledge.areas.kommentarLabel') }}</div>
        <div v-if="!kommentarEdit.open" class="kommentar-view">
          <span v-if="activeArea.kommentar" class="kommentar-text">{{ activeArea.kommentar }}</span>
          <span v-else class="kommentar-empty">{{ $t('settings.knowledge.areas.kommentarEmpty') }}</span>
          <button class="chip-edit-btn" :title="$t('settings.knowledge.areas.edit')" @click="openKommentarEdit">✎</button>
        </div>
        <div v-else class="kommentar-edit">
          <textarea
            v-model="kommentarEdit.text"
            class="kommentar-textarea"
            rows="2"
            :placeholder="$t('settings.knowledge.areas.kommentarPlaceholder')"
          ></textarea>
          <div class="chip-edit-actions">
            <button class="chip-btn primary" :disabled="kommentarEdit.saving" @click="saveKommentar">
              {{ kommentarEdit.saving ? $t('settings.knowledge.areas.saving') : $t('settings.knowledge.areas.save') }}
            </button>
            <button class="chip-btn" @click="kommentarEdit.open = false">{{ $t('settings.knowledge.areas.cancel') }}</button>
          </div>
        </div>
      </div>
      <p v-else class="hint">{{ $t('settings.knowledge.areas.unescoReadonly') }}</p>

      <!-- drop-zone — only for operator areas -->
      <div v-if="!activeArea.fixed" class="dropzone-block">
        <div
          :class="['dropzone', { dragover: dropzone.dragover, busy: dropzone.uploading }]"
          @dragover.prevent="dropzone.dragover = true"
          @dragleave.prevent="dropzone.dragover = false"
          @drop.prevent="onDrop"
          @click="triggerFilePick"
        >
          <input ref="dropFileInput" type="file" accept=".pdf,.md" multiple class="hidden-file" @change="onFilePick" />
          <div class="dropzone-label">
            {{ dropzone.uploading ? $t('settings.knowledge.dropzone.uploading') : $t('settings.knowledge.dropzone.label') }}
          </div>
          <div class="dropzone-hint">{{ $t('settings.knowledge.dropzone.hint') }}</div>
        </div>
        <div class="field dropzone-hinweis">
          <label>{{ $t('settings.knowledge.dropzone.hinweisLabel') }}</label>
          <input v-model="dropzone.hinweis" type="text" :placeholder="$t('settings.knowledge.dropzone.hinweisPlaceholder')" />
        </div>
        <span v-if="dropzone.message" :class="['upload-msg', { error: dropzone.error }]">{{ dropzone.message }}</span>
      </div>

      <!-- Document list of this area. Operator areas show the full curation
           actions per row; the fixed UNESCO area shows the SAME list read-only
           (only "Profile" — no publish/move/delete), gated per row on
           it.readonly so the backend's readonly flag is the single source. -->
      <div class="panel-docs-head">
        <h3>{{ $t('settings.knowledge.areas.panelDocsTitle') }}</h3>
        <button
          v-if="!activeArea.fixed && areaItems.length > 0"
          class="action-btn secondary"
          :disabled="reanalyzingAll"
          :title="$t('settings.knowledge.items.reanalyzeHint')"
          @click="reanalyzeAllInArea"
        >
          {{ reanalyzingAll ? $t('settings.knowledge.items.reanalyzeAllRunning') : $t('settings.knowledge.items.reanalyzeAll') }}
        </button>
      </div>
      <p v-if="areaItems.length === 0" class="help">
        {{ activeArea.fixed ? $t('settings.knowledge.areas.panelDocsNoneFixed') : $t('settings.knowledge.areas.panelDocsNone') }}
      </p>
      <table v-else class="items-table" dir="ltr">
        <thead>
          <tr>
            <th>{{ $t('settings.knowledge.items.colStatus') }}</th>
            <th>{{ $t('settings.knowledge.items.colTitle') }}</th>
            <th>{{ $t('settings.knowledge.items.colYear') }}</th>
            <th>{{ $t('settings.knowledge.items.colAnalyzed') }}</th>
            <th>{{ $t('settings.knowledge.items.colChunks') }}</th>
            <th>{{ $t('settings.knowledge.items.colActions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="it in areaItems" :key="it.doc_id">
            <td>
              <span :class="['status-badge', 'status-' + it.status]">{{ it.status }}</span>
              <span v-if="it.readonly" class="ro-lock" :title="$t('settings.knowledge.items.readonlyHint')" aria-hidden="true">🔒</span>
            </td>
            <td>{{ it.titel }}<br /><span class="doc-id">{{ it.doc_id }}</span></td>
            <td>{{ it.jahr || '—' }}</td>
            <td class="analysis-cell">
              <span v-if="it.analyzed_at" class="analysis-meta">
                {{ formatAnalyzedAt(it.analyzed_at) }}<span v-if="it.analysis_lang" class="analysis-lang"> · {{ it.analysis_lang.toUpperCase() }}</span>
              </span>
              <span v-else class="analysis-meta analysis-none" :title="$t('settings.knowledge.items.neverAnalyzedHint')">
                {{ $t('settings.knowledge.items.neverAnalyzed') }}
              </span>
            </td>
            <td>{{ it.chunks }}</td>
            <td class="actions-cell">
              <button class="link-btn" @click="openCard(it.doc_id)">{{ $t('settings.knowledge.items.card') }}</button>
              <template v-if="!it.readonly">
                <button class="link-btn" @click="toggleStatus(it)">
                  {{ it.status === 'published' ? $t('settings.knowledge.items.unpublish') : $t('settings.knowledge.items.publish') }}
                </button>
                <button
                  class="link-btn"
                  :disabled="reprocessingDocId === it.doc_id"
                  :title="$t('settings.knowledge.items.reanalyzeHint')"
                  @click="reprocessItem(it)"
                >
                  {{ reprocessingDocId === it.doc_id ? $t('settings.knowledge.items.reanalyzing') : $t('settings.knowledge.items.reanalyze') }}
                </button>
                <!-- Move: a small dropdown of all other operator areas (+ "no area"). -->
                <span class="move-control">
                  <select
                    class="move-select"
                    :disabled="movingDocId === it.doc_id"
                    :value="''"
                    :aria-label="$t('settings.knowledge.items.move')"
                    @change="onMoveSelect(it, $event)"
                  >
                    <option value="" disabled>
                      {{ movingDocId === it.doc_id ? $t('settings.knowledge.items.moving') : $t('settings.knowledge.items.move') }}
                    </option>
                    <option v-for="opt in moveTargets(it)" :key="opt.value" :value="opt.value">
                      {{ opt.label }}
                    </option>
                  </select>
                </span>
                <button class="link-btn danger" @click="deleteItem(it)">{{ $t('settings.knowledge.items.delete') }}</button>
              </template>
              <span v-if="moveError.docId === it.doc_id && moveError.message" class="move-err">{{ moveError.message }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ==================== Jobs ==================== -->
    <div class="section">
      <h2>{{ $t('settings.knowledge.jobs.title') }}</h2>
      <p v-if="jobs.length === 0" class="help">{{ $t('settings.knowledge.jobs.none') }}</p>
      <div v-for="job in jobs" :key="job.job_id" class="job-row">
        <div class="job-head">
          <span :class="['job-badge', 'state-' + job.state]">{{ jobStateLabel(job.state) }}</span>
          <span class="job-title">{{ job.title || job.doc_id }}</span>
          <span class="job-msg">{{ job.message }}</span>
          <button class="link-btn" @click="toggleJobLog(job.job_id)">
            {{ expandedJobs.has(job.job_id) ? $t('settings.knowledge.jobs.hideLog') : $t('settings.knowledge.jobs.showLog') }}
          </button>
          <!-- Cancel: only for a job that is still queued or running. -->
          <button
            v-if="job.state === 'queued' || job.state === 'running'"
            class="link-btn danger"
            :disabled="cancellingJobs.has(job.job_id)"
            @click="cancelJob(job)"
          >
            {{ cancellingJobs.has(job.job_id) ? $t('settings.knowledge.jobs.cancelling') : $t('settings.knowledge.jobs.cancel') }}
          </button>
        </div>
        <pre v-if="expandedJobs.has(job.job_id)" class="job-log">{{ (jobLogs[job.job_id] || []).join('\n') }}</pre>
      </div>
    </div>

    <!-- ==================== Card editor / profile view (inline panel) ======= -->
    <div v-if="cardEditor.open" class="section">
      <h2>
        <span v-if="cardEditor.readonly" class="ro-lock" aria-hidden="true">🔒</span>
        {{ cardEditor.readonly ? $t('settings.knowledge.card.titleReadonly') : $t('settings.knowledge.card.title') }} — {{ cardEditor.docId }}
      </h2>

      <!-- Bibliographic meta (titel/autor/jahr/quelle). Tier-O: inline-editable
           (the ✎ pencil pattern, like the area comment) so the operator can fix a
           mis-identified title. Tier-F/UNESCO: shown read-only (no ✎). -->
      <div class="meta-panel">
        <!-- display -->
        <div v-if="!metaEditor.edit" class="meta-display">
          <dl class="meta-grid">
            <dt>{{ $t('settings.knowledge.meta.titel') }}</dt>
            <dd>{{ metaEditor.titel || '—' }}</dd>
            <dt>{{ $t('settings.knowledge.meta.autor') }}</dt>
            <dd>{{ metaEditor.autor || '—' }}</dd>
            <dt>{{ $t('settings.knowledge.meta.jahr') }}</dt>
            <dd>{{ metaEditor.jahr || '—' }}</dd>
            <dt>{{ $t('settings.knowledge.meta.quelle') }}</dt>
            <dd>{{ metaEditor.quelle || '—' }}</dd>
          </dl>
          <button
            v-if="!cardEditor.readonly"
            class="meta-edit-btn"
            :title="$t('settings.knowledge.meta.edit')"
            @click="openMetaEdit"
          >✎</button>
        </div>
        <!-- inline edit (Tier-O only) -->
        <div v-else class="meta-edit">
          <p class="help">{{ $t('settings.knowledge.meta.help') }}</p>
          <label class="meta-field">
            <span>{{ $t('settings.knowledge.meta.titel') }}</span>
            <input v-model="metaEditor.draft.titel" type="text" class="meta-input" />
          </label>
          <label class="meta-field">
            <span>{{ $t('settings.knowledge.meta.autor') }}</span>
            <input v-model="metaEditor.draft.autor" type="text" class="meta-input"
                   :placeholder="$t('settings.knowledge.meta.autorPlaceholder')" data-example="no" />
          </label>
          <label class="meta-field">
            <span>{{ $t('settings.knowledge.meta.jahr') }}</span>
            <input v-model="metaEditor.draft.jahr" type="text" class="meta-input meta-input-short"
                   :placeholder="$t('settings.knowledge.meta.jahrPlaceholder')" data-example="no" />
          </label>
          <label class="meta-field">
            <span>{{ $t('settings.knowledge.meta.quelle') }}</span>
            <input v-model="metaEditor.draft.quelle" type="text" class="meta-input"
                   :placeholder="$t('settings.knowledge.meta.quellePlaceholder')" />
          </label>
          <div class="form-actions">
            <button class="action-btn" :disabled="metaEditor.saving" @click="saveMeta">
              {{ metaEditor.saving ? $t('settings.knowledge.meta.saving') : $t('settings.knowledge.meta.save') }}
            </button>
            <button class="action-btn secondary" @click="metaEditor.edit = false">{{ $t('common.cancel') }}</button>
          </div>
        </div>
        <span v-if="metaEditor.message" :class="['upload-msg', { error: metaEditor.error }]">{{ metaEditor.message }}</span>
      </div>

      <!-- Analysis provenance (additive, 2026-07-10): always read-only, shown
           regardless of the bibliographic edit state above. `sprache` is the
           document's own detected SOURCE language; analyzedAt/analysisLang/
           analysisModel are the Verdichtung run's PROVENANCE (when / in what
           language / by which model(s) it actually ran) — the two languages
           are labelled distinctly so they are never confused. A document
           produced before this feature has no analyzedAt: shown as a muted
           "never analyzed with provenance" marker so the owner can spot at a
           glance which documents predate this feature and need a re-run. -->
      <div class="meta-panel">
        <dl class="meta-grid provenance-grid">
          <dt>{{ $t('settings.knowledge.meta.sprache') }}</dt>
          <dd>{{ metaEditor.sprache || '—' }}</dd>
          <dt>{{ $t('settings.knowledge.meta.analyzedAt') }}</dt>
          <dd>
            <span v-if="metaEditor.analyzedAt">{{ formatAnalyzedAt(metaEditor.analyzedAt) }}</span>
            <span v-else class="never-analyzed">{{ $t('settings.knowledge.meta.neverAnalyzed') }}</span>
          </dd>
          <dt>{{ $t('settings.knowledge.meta.analysisLang') }}</dt>
          <dd>{{ metaEditor.analysisLang ? metaEditor.analysisLang.toUpperCase() : '—' }}</dd>
          <dt>{{ $t('settings.knowledge.meta.analysisModel') }}</dt>
          <dd>{{ metaEditor.analysisModel || '—' }}</dd>
        </dl>
      </div>

      <!-- Read-only (Tier-F/UNESCO): the profile is shown as plain text, with no
           edit affordance. Operator (Tier-O): the editable PROFIL textarea. -->
      <template v-if="cardEditor.readonly">
        <p class="help">{{ $t('settings.knowledge.card.helpReadonly') }}</p>
        <pre class="card-readonly">{{ cardEditor.text || $t('settings.knowledge.card.emptyProfile') }}</pre>
        <div class="form-actions">
          <button class="action-btn secondary" @click="cardEditor.open = false">{{ $t('common.close') }}</button>
        </div>
      </template>
      <template v-else>
        <p class="help">{{ $t('settings.knowledge.card.help') }}</p>
        <textarea v-model="cardEditor.text" class="card-textarea" rows="14"></textarea>
        <div class="form-actions">
          <button class="action-btn" :disabled="cardEditor.saving" @click="saveCard">
            {{ cardEditor.saving ? $t('settings.knowledge.card.saving') : $t('settings.knowledge.card.save') }}
          </button>
          <button class="action-btn secondary" @click="cardEditor.open = false">{{ $t('common.cancel') }}</button>
          <span v-if="cardEditor.message" :class="['upload-msg', { error: cardEditor.error }]">{{ cardEditor.message }}</span>
        </div>
      </template>

      <!-- WISSEN sections of this doc (read-only) — the condensed knowledge the
           agent retrieves, so the operator sees the full stock, not only the
           profile. Collapsible per section for scanning. -->
      <div class="wissen-panel">
        <h3>{{ $t('settings.knowledge.wissen.title') }}</h3>
        <p class="hint">{{ $t('settings.knowledge.wissen.help') }}</p>
        <p v-if="!cardEditor.wissen.length" class="wissen-empty">{{ $t('settings.knowledge.wissen.empty') }}</p>
        <div v-for="(sec, i) in cardEditor.wissen" :key="i" class="wissen-section">
          <button type="button" class="wissen-head" @click="toggleWissen(i)">
            <span class="wissen-caret">{{ expandedWissen.has(i) ? '▾' : '▸' }}</span>
            <span class="wissen-title">{{ sec.heading }}</span>
          </button>
          <pre v-if="expandedWissen.has(i)" class="wissen-body">{{ sec.body }}</pre>
        </div>
      </div>

      <!-- Glossary of this doc. Tier-O: editable via overrides. Tier-F/UNESCO:
           read-only (terms + definitions shown as text, no override inputs). -->
      <div v-if="cardEditor.glossary.length" class="glossary-panel">
        <h3>{{ $t('settings.knowledge.glossary.title') }}</h3>
        <template v-if="cardEditor.readonly">
          <p class="hint">{{ $t('settings.knowledge.glossary.helpReadonly') }}</p>
          <div v-for="g in cardEditor.glossary" :key="g.term" class="gloss-row readonly">
            <div class="gloss-term">{{ g.term }}</div>
            <div class="gloss-def-ro">{{ g.definition }}</div>
          </div>
        </template>
        <template v-else>
          <p class="hint">{{ $t('settings.knowledge.glossary.help') }}</p>
          <div v-for="g in cardEditor.glossary" :key="g.term" class="gloss-row">
            <div class="gloss-term">{{ g.term }}</div>
            <input v-model="g.overrideDefinition" type="text" class="gloss-def" :placeholder="g.definition" />
            <label class="cb"><input type="checkbox" v-model="g.hidden" /> {{ $t('settings.knowledge.glossary.hide') }}</label>
          </div>
          <div class="form-actions">
            <button class="action-btn" :disabled="glossarySaving" @click="saveGlossaryOverrides">
              {{ glossarySaving ? $t('settings.knowledge.glossary.saving') : $t('settings.knowledge.glossary.save') }}
            </button>
            <span v-if="glossaryMessage" :class="['upload-msg', { error: glossaryError }]">{{ glossaryMessage }}</span>
          </div>
        </template>
      </div>
    </div>

    <!-- ==================== Reindex (kept, compact) ==================== -->
    <div class="section compact">
      <div class="refresh-bar">
        <button class="action-btn" @click="reloadAll">{{ $t('settings.knowledge.items.refresh') }}</button>
        <button class="action-btn" :disabled="reindexing" @click="doReindex">
          {{ reindexing ? $t('settings.knowledge.reindex.running') : $t('settings.knowledge.reindex.button') }}
        </button>
        <button class="action-btn" :disabled="exporting" @click="exportMarkdown">
          {{ exporting ? $t('settings.knowledge.export.running') : $t('settings.knowledge.export.button') }}
        </button>
        <span v-if="reindexMessage" :class="['upload-msg', { error: reindexError }]">{{ reindexMessage }}</span>
        <span v-if="exportMessage" :class="['upload-msg', { error: exportError }]">{{ exportMessage }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { apiBase } from '@/services/labApi'
import { downloadBlob } from '@/lib/downloadMedia'

const { t } = useI18n()

async function api(path: string, options: RequestInit = {}): Promise<Response> {
  return fetch(`${apiBase()}/api/knowledge${path}`, { credentials: 'include', ...options })
}

// Analysis provenance display (additive, 2026-07-10): the stored value is a
// UTC ISO-8601 timestamp (analyzed_at); shown in the viewer's local time as a
// quiet "10 Jul, 08:54" -- metadata, not a headline. Locale-independent (a
// fixed English month abbreviation) so the admin table reads the same for
// every operator regardless of browser locale.
const ANALYZED_MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function formatAnalyzedAt(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const day = String(d.getDate()).padStart(2, '0')
  const month = ANALYZED_MONTH_ABBR[d.getMonth()]
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${day} ${month}, ${hh}:${mm}`
}

// ---------- Areas ----------
interface AreaView {
  id: string
  name: string
  kommentar: string
  fixed: boolean
  count: number // total (drafts included) — kept for backwards compatibility
  count_published?: number
  count_total?: number
  created?: string
}
const areas = ref<AreaView[]>([])
const activeAreaId = ref<string | null>(null)

const operatorAreas = computed(() => areas.value.filter((a) => !a.fixed))
const unescoArea = computed(() => areas.value.find((a) => a.fixed) || null)
const activeArea = computed(() => areas.value.find((a) => a.id === activeAreaId.value) || null)

// Chip counter as published/total (e.g. "3/5 docs"): how many documents of the
// area the agent can already see vs how many the area holds in curation.
// Falls back to `count` (total) for a payload predating count_published/_total.
function docCountLabel(a: AreaView): string {
  const total = a.count_total ?? a.count
  const published = a.count_published ?? 0
  if (total === 0) return t('settings.knowledge.areas.docCountZero')
  return t('settings.knowledge.areas.docCountRatio', { published, total })
}

async function loadAreas() {
  try {
    const resp = await api('/areas')
    if (!resp.ok) return
    areas.value = (await resp.json()).areas || []
    // if the active area vanished (deleted), clear the selection
    if (activeAreaId.value && !areas.value.some((a) => a.id === activeAreaId.value)) {
      activeAreaId.value = null
    }
  } catch {
    /* ignore transient */
  }
}

function selectArea(id: string) {
  activeAreaId.value = activeAreaId.value === id ? null : id
  editChip.open = false
  kommentarEdit.open = false
  dropzone.message = ''
  if (activeAreaId.value) loadAreaItems()
  else areaItems.value = []
}

// --- add chip ---
const addNameInput = ref<HTMLInputElement | null>(null)
const addChip = reactive({ open: false, name: '', kommentar: '', saving: false, error: '' })

function openAddChip() {
  addChip.open = true
  addChip.name = ''
  addChip.kommentar = ''
  addChip.error = ''
  nextTick(() => addNameInput.value?.focus())
}

async function createArea() {
  if (!addChip.name.trim()) {
    addChip.error = t('settings.knowledge.areas.newName')
    return
  }
  addChip.saving = true
  addChip.error = ''
  try {
    const resp = await api('/areas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: addChip.name.trim(), kommentar: addChip.kommentar.trim() }),
    })
    const data = await resp.json()
    if (!resp.ok || !data.success) throw new Error(data.error || `HTTP ${resp.status}`)
    addChip.open = false
    await loadAreas()
    activeAreaId.value = data.area.id
    loadAreaItems()
  } catch (e: any) {
    addChip.error = e.message
  } finally {
    addChip.saving = false
  }
}

// --- edit chip ---
const editChip = reactive({ open: false, id: '', name: '', kommentar: '', saving: false, error: '' })

function openChipEdit(a: AreaView) {
  editChip.open = true
  editChip.id = a.id
  editChip.name = a.name
  editChip.kommentar = a.kommentar || ''
  editChip.error = ''
}

async function saveChipEdit() {
  if (!editChip.name.trim()) {
    editChip.error = t('settings.knowledge.areas.editName')
    return
  }
  editChip.saving = true
  editChip.error = ''
  try {
    const resp = await api(`/areas/${editChip.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: editChip.name.trim(), kommentar: editChip.kommentar.trim() }),
    })
    const data = await resp.json()
    if (!resp.ok || !data.success) throw new Error(data.error || `HTTP ${resp.status}`)
    editChip.open = false
    await loadAreas()
  } catch (e: any) {
    editChip.error = e.message
  } finally {
    editChip.saving = false
  }
}

async function deleteArea(a: AreaView) {
  if (!window.confirm(t('settings.knowledge.areas.confirmDelete', { name: a.name }))) return
  try {
    const resp = await api(`/areas/${a.id}`, { method: 'DELETE' })
    const data = await resp.json()
    if (!resp.ok) {
      editChip.error = data.error || t('settings.knowledge.areas.deleteBlocked')
      return
    }
    editChip.open = false
    if (activeAreaId.value === a.id) activeAreaId.value = null
    await loadAreas()
  } catch (e: any) {
    editChip.error = e.message
  }
}

// --- kommentar (agent note) edit in the panel ---
const kommentarEdit = reactive({ open: false, text: '', saving: false })

function openKommentarEdit() {
  kommentarEdit.open = true
  kommentarEdit.text = activeArea.value?.kommentar || ''
}

async function saveKommentar() {
  if (!activeArea.value) return
  kommentarEdit.saving = true
  try {
    const resp = await api(`/areas/${activeArea.value.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kommentar: kommentarEdit.text.trim() }),
    })
    const data = await resp.json()
    if (!resp.ok || !data.success) throw new Error(data.error || `HTTP ${resp.status}`)
    kommentarEdit.open = false
    await loadAreas()
  } catch {
    /* keep the editor open on failure */
  } finally {
    kommentarEdit.saving = false
  }
}

// ---------- Drop-zone upload (per active area) ----------
const dropFileInput = ref<HTMLInputElement | null>(null)
const dropzone = reactive({ dragover: false, uploading: false, hinweis: '', message: '', error: false })

function triggerFilePick() {
  if (dropzone.uploading) return
  dropFileInput.value?.click()
}

function onFilePick(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (files && files.length) uploadFiles(Array.from(files))
  if (dropFileInput.value) dropFileInput.value.value = ''
}

function onDrop(e: DragEvent) {
  dropzone.dragover = false
  const files = e.dataTransfer?.files
  if (files && files.length) uploadFiles(Array.from(files))
}

async function uploadFiles(files: File[]) {
  if (!activeArea.value || activeArea.value.fixed) {
    dropzone.message = t('settings.knowledge.dropzone.pickArea')
    dropzone.error = true
    return
  }
  const areaId = activeArea.value.id
  const hinweis = dropzone.hinweis.trim()
  dropzone.uploading = true
  dropzone.message = ''
  dropzone.error = false
  let ok = 0
  for (const file of files) {
    const fd = new FormData()
    fd.append('document', file)
    fd.append('bereich', areaId)
    fd.append('hinweis', hinweis)
    fd.append('lang', 'de')
    try {
      const resp = await api('/upload', { method: 'POST', body: fd })
      const data = await resp.json()
      if (!resp.ok || !data.success) throw new Error(data.error || `HTTP ${resp.status}`)
      trackJob(data.job_id)
      ok += 1
    } catch (e: any) {
      dropzone.message = e.message
      dropzone.error = true
    }
  }
  dropzone.uploading = false
  if (ok > 0) {
    dropzone.hinweis = ''
    loadJobs()
  }
}

// ---------- Jobs ----------
interface JobView {
  job_id: string
  state: string
  doc_id: string
  title: string
  message: string
  returncode: number | null
  log_tail?: string[]
}
const jobs = ref<JobView[]>([])
const jobLogs = reactive<Record<string, string[]>>({})
const expandedJobs = reactive<Set<string>>(new Set())
const trackedJobs = reactive<Set<string>>(new Set())
const cancellingJobs = reactive<Set<string>>(new Set())
let pollTimer: number | null = null

function jobStateLabel(state: string): string {
  return t(`settings.knowledge.jobs.state.${state}`)
}

function toggleJobLog(jobId: string) {
  if (expandedJobs.has(jobId)) expandedJobs.delete(jobId)
  else expandedJobs.add(jobId)
}

function trackJob(jobId: string) {
  trackedJobs.add(jobId)
  ensurePolling()
}

async function loadJobs() {
  try {
    const resp = await api('/jobs')
    if (!resp.ok) return
    const data = await resp.json()
    jobs.value = data.jobs || []
  } catch {
    /* ignore transient */
  }
}

async function cancelJob(job: JobView) {
  if (cancellingJobs.has(job.job_id)) return
  cancellingJobs.add(job.job_id)
  try {
    const resp = await api(`/jobs/${job.job_id}/cancel`, { method: 'POST' })
    const data = await resp.json()
    if (!resp.ok) {
      // 409 (already terminal) or 404 — refresh the list to reflect reality.
      loadJobs()
      return
    }
    // Reflect the returned job immediately; a running job may still be winding
    // down, so keep polling it until it lands in `cancelled`.
    if (data.job) {
      const idx = jobs.value.findIndex((j) => j.job_id === job.job_id)
      if (idx >= 0) jobs.value[idx] = data.job
      jobLogs[job.job_id] = data.job.log_tail || jobLogs[job.job_id] || []
    }
    trackJob(job.job_id)
  } catch {
    loadJobs()
  } finally {
    cancellingJobs.delete(job.job_id)
  }
}

async function pollTrackedJobs() {
  let anyActive = false
  for (const jobId of Array.from(trackedJobs)) {
    try {
      const resp = await api(`/jobs/${jobId}`)
      if (!resp.ok) {
        trackedJobs.delete(jobId)
        continue
      }
      const data: JobView = await resp.json()
      jobLogs[jobId] = data.log_tail || []
      const idx = jobs.value.findIndex((j) => j.job_id === jobId)
      if (idx >= 0) jobs.value[idx] = data
      if (data.state === 'queued' || data.state === 'running') {
        anyActive = true
      } else {
        trackedJobs.delete(jobId)
        // a finished job may have produced a new draft -> refresh area + counts
        loadAreas()
        loadAreaItems()
      }
    } catch {
      /* keep trying */
      anyActive = true
    }
  }
  if (!anyActive && pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function ensurePolling() {
  if (pollTimer === null) {
    pollTimer = window.setInterval(pollTrackedJobs, 2000)
    pollTrackedJobs()
  }
}

// ---------- Area inventory ----------
interface ItemRow {
  doc_id: string
  titel: string
  jahr: string
  lizenz: string
  status: string
  chunks: number
  sparten: string[]
  themen: string[]
  bereich: string
  hinweis: string
  // Analysis provenance (additive, 2026-07-10): '' on any document produced
  // before this feature -- rendered as a muted "never analyzed" marker.
  analyzed_at?: string
  analysis_lang?: string
  readonly?: boolean // Tier-F (UNESCO) rows are view-only — no curation actions
}
const areaItems = ref<ItemRow[]>([])
const reindexing = ref(false)
const reindexMessage = ref('')
const reindexError = ref(false)

async function loadAreaItems() {
  if (!activeAreaId.value) {
    areaItems.value = []
    return
  }
  // Both operator areas and the fixed UNESCO pseudo-area list their documents
  // through the same endpoint: ?bereich=<id>. For the UNESCO id the backend
  // returns the committed Tier-F corpus with readonly:true on every row (a
  // transparency view — no curation actions attach to it); for an operator area
  // it returns that area's Tier-O docs. Neither touches the Resona read path.
  try {
    const resp = await api(`/items?bereich=${encodeURIComponent(activeAreaId.value)}`)
    if (!resp.ok) return
    areaItems.value = (await resp.json()).items || []
  } catch {
    /* ignore */
  }
}

async function toggleStatus(it: ItemRow) {
  const next = it.status === 'published' ? 'draft' : 'published'
  try {
    const resp = await api(`/items/${it.doc_id}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: next }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`)
    it.status = next
  } catch (e: any) {
    reindexMessage.value = e.message
    reindexError.value = true
  }
}

async function deleteItem(it: ItemRow) {
  if (!window.confirm(t('settings.knowledge.items.confirmDelete', { title: it.titel }))) return
  try {
    const resp = await api(`/items/${it.doc_id}`, { method: 'DELETE' })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`)
    areaItems.value = areaItems.value.filter((x) => x.doc_id !== it.doc_id)
    if (cardEditor.open && cardEditor.docId === it.doc_id) cardEditor.open = false
    loadAreas() // refresh the chip count
  } catch (e: any) {
    reindexMessage.value = e.message
    reindexError.value = true
  }
}

// ---------- Re-analyze (re-run Verdichtung from the stored source, no re-upload) ----------
// One doc_id at a time (reprocessingDocId gates the per-row button); the
// "re-analyze all" loop just calls this sequentially so the backend's single
// FIFO worker serialises the jobs exactly like a multi-file upload would.
const reprocessingDocId = ref<string | null>(null)
const reanalyzingAll = ref(false)

async function reprocessItem(it: ItemRow) {
  if (reprocessingDocId.value === it.doc_id) return
  reprocessingDocId.value = it.doc_id
  try {
    const resp = await api(`/items/${it.doc_id}/reprocess`, { method: 'POST' })
    const data = await resp.json()
    if (!resp.ok || !data.success) throw new Error(data.error || `HTTP ${resp.status}`)
    // Same job-tracking idiom as an upload: track + refresh the Jobs panel.
    trackJob(data.job_id)
    loadJobs()
  } catch (e: any) {
    reindexMessage.value = e.message
    reindexError.value = true
  } finally {
    reprocessingDocId.value = null
  }
}

async function reanalyzeAllInArea() {
  if (reanalyzingAll.value) return
  const targets = areaItems.value.filter((it) => !it.readonly)
  if (targets.length === 0) return
  if (!window.confirm(t('settings.knowledge.items.confirmReanalyzeAll', { count: targets.length }))) return
  reanalyzingAll.value = true
  try {
    for (const it of targets) {
      await reprocessItem(it)
    }
  } finally {
    reanalyzingAll.value = false
  }
}

// ---------- Move a document to another area ----------
interface MoveTarget {
  value: string // area id, or '' for "no area"
  label: string
}
const movingDocId = ref<string | null>(null)
const moveError = reactive<{ docId: string; message: string }>({ docId: '', message: '' })

// The move menu for a row: every OTHER operator area (never UNESCO — the fixed
// pseudo-area cannot receive documents) plus a "no area" option, unless the
// document already has no area.
function moveTargets(it: ItemRow): MoveTarget[] {
  const out: MoveTarget[] = []
  for (const a of operatorAreas.value) {
    if (a.id === it.bereich) continue
    out.push({ value: a.id, label: a.name })
  }
  if (it.bereich) out.push({ value: '', label: t('settings.knowledge.items.moveNoArea') })
  return out
}

function onMoveSelect(it: ItemRow, e: Event) {
  const sel = e.target as HTMLSelectElement
  const value = sel.value
  // reset the select back to its placeholder so it can be reused
  sel.value = ''
  if (value === '' && !it.bereich) return
  moveDocument(it, value)
}

async function moveDocument(it: ItemRow, target: string) {
  movingDocId.value = it.doc_id
  moveError.docId = it.doc_id
  moveError.message = ''
  try {
    const resp = await api(`/items/${it.doc_id}/bereich`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      // '' means "no area" -> send null so the backend clears the field
      body: JSON.stringify({ bereich: target === '' ? null : target }),
    })
    const data = await resp.json()
    if (!resp.ok || !data.success) throw new Error(data.error || `HTTP ${resp.status}`)
    // The document left the active area (or changed area): drop it from this
    // list and refresh the chip counts (and the active area's inventory).
    areaItems.value = areaItems.value.filter((x) => x.doc_id !== it.doc_id)
    if (cardEditor.open && cardEditor.docId === it.doc_id) cardEditor.open = false
    loadAreas()
    loadAreaItems()
  } catch (e: any) {
    moveError.docId = it.doc_id
    moveError.message = e.message
  } finally {
    movingDocId.value = null
  }
}

async function doReindex() {
  reindexing.value = true
  reindexMessage.value = ''
  reindexError.value = false
  try {
    const resp = await api('/reindex', { method: 'POST' })
    const data = await resp.json()
    if (!resp.ok || !data.success) throw new Error((data.log || []).join(' ') || `HTTP ${resp.status}`)
    reindexMessage.value = t('settings.knowledge.reindex.done')
    reloadAll()
  } catch (e: any) {
    reindexMessage.value = e.message
    reindexError.value = true
  } finally {
    reindexing.value = false
  }
}

const exporting = ref(false)
const exportMessage = ref('')
const exportError = ref(false)

async function exportMarkdown() {
  exporting.value = true
  exportMessage.value = ''
  exportError.value = false
  try {
    const resp = await api('/export.md')
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    downloadBlob(await resp.blob(), 'knowledge_library.md')
  } catch (e: any) {
    exportMessage.value = e.message
    exportError.value = true
  } finally {
    exporting.value = false
  }
}

function reloadAll() {
  loadAreas()
  loadAreaItems()
  loadJobs()
}

// ---------- Card + glossary editor ----------
interface GlossRow {
  term: string
  definition: string
  overrideDefinition: string
  hidden: boolean
}
interface WissenSection {
  heading: string
  body: string
}
const cardEditor = reactive({
  open: false,
  docId: '',
  text: '',
  glossary: [] as GlossRow[],
  wissen: [] as WissenSection[],
  saving: false,
  message: '',
  error: false,
  readonly: false, // Tier-F (UNESCO): profile view only — no PROFIL/glossary edit
})

// Bibliographic meta (titel/autor/jahr/quelle) of the open document. The ingest
// identifier is best-effort; this is the operator's correction surface for a
// mis-identified title (the filename/byline/chapter-heading-as-title problem).
// Tier-F is view-only (edit === false always). `draft` holds the in-progress
// edit so a Cancel restores the shown values.
const metaEditor = reactive({
  edit: false,
  saving: false,
  message: '',
  error: false,
  titel: '',
  autor: '',
  jahr: '' as string | number,
  quelle: '',
  // Read-only always (never part of `draft` / the edit form): the document's
  // own detected SOURCE language, and the analysis PROVENANCE -- when / in
  // what language / by which model(s) the Verdichtung actually ran. The two
  // languages are never the same field and must not be confused.
  sprache: '',
  analyzedAt: '',
  analysisLang: '',
  analysisModel: '',
  draft: { titel: '', autor: '', jahr: '' as string | number, quelle: '' },
})

function openMetaEdit() {
  metaEditor.draft = {
    titel: metaEditor.titel,
    autor: metaEditor.autor,
    jahr: metaEditor.jahr,
    quelle: metaEditor.quelle,
  }
  metaEditor.message = ''
  metaEditor.error = false
  metaEditor.edit = true
}

async function saveMeta() {
  const titel = String(metaEditor.draft.titel || '').trim()
  if (!titel) {
    metaEditor.message = t('settings.knowledge.meta.titelRequired')
    metaEditor.error = true
    return
  }
  metaEditor.saving = true
  metaEditor.message = ''
  metaEditor.error = false
  try {
    const resp = await api(`/items/${cardEditor.docId}/meta`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        titel,
        autor: String(metaEditor.draft.autor || '').trim(),
        jahr: String(metaEditor.draft.jahr ?? '').trim(),
        quelle: String(metaEditor.draft.quelle || '').trim(),
      }),
    })
    const data = await resp.json()
    if (!resp.ok || !data.success) throw new Error(data.error || `HTTP ${resp.status}`)
    // Reflect the normalised values the backend echoed.
    metaEditor.titel = data.titel ?? titel
    metaEditor.autor = data.autor ?? ''
    metaEditor.jahr = data.jahr ?? ''
    metaEditor.quelle = data.quelle ?? ''
    metaEditor.edit = false
    metaEditor.message = t('settings.knowledge.meta.saved')
    // The inventory table shows the title — refresh it so the fix is visible.
    await reloadAll()
  } catch (e: any) {
    metaEditor.message = e.message
    metaEditor.error = true
  } finally {
    metaEditor.saving = false
  }
}
// Which WISSEN sections are expanded in the read-only document view (by index).
const expandedWissen = ref<Set<number>>(new Set())
function toggleWissen(i: number) {
  const s = new Set(expandedWissen.value)
  s.has(i) ? s.delete(i) : s.add(i)
  expandedWissen.value = s
}

// Split the ## WISSEN body into its ### subsections for the read-only view. The
// review anchors (<!-- quelle: … -->) are curation plumbing and are stripped.
function parseWissenSections(wissen: string): WissenSection[] {
  if (!wissen || !wissen.trim()) return []
  const out: WissenSection[] = []
  let heading = ''
  let body: string[] = []
  const flush = () => {
    const text = body.join('\n').replace(/<!--\s*quelle:[\s\S]*?-->/g, '').trim()
    if (heading || text) out.push({ heading: heading || '—', body: text })
  }
  for (const line of wissen.split('\n')) {
    const m = /^###\s+(.*\S)\s*$/.exec(line)
    if (m) {
      if (heading || body.length) flush()
      heading = (m[1] ?? '').trim()
      body = []
    } else {
      body.push(line)
    }
  }
  if (heading || body.length) flush()
  return out
}
const glossaryOverrides = ref<Record<string, { definition?: string; hidden?: boolean }>>({})
const glossarySaving = ref(false)
const glossaryMessage = ref('')
const glossaryError = ref(false)

async function openCard(docId: string) {
  cardEditor.message = ''
  cardEditor.error = false
  try {
    const [itemResp, ovResp] = await Promise.all([api(`/items/${docId}`), api('/glossary-overrides')])
    if (!itemResp.ok) throw new Error(`HTTP ${itemResp.status}`)
    const item = await itemResp.json()
    glossaryOverrides.value = ovResp.ok ? (await ovResp.json()).overrides || {} : {}
    cardEditor.docId = docId
    cardEditor.readonly = !!item.readonly
    cardEditor.text = item.card || ''
    // Bibliographic meta for the correction panel (reset any prior edit).
    metaEditor.edit = false
    metaEditor.message = ''
    metaEditor.error = false
    metaEditor.titel = item.titel || ''
    metaEditor.autor = item.autor || ''
    metaEditor.jahr = item.jahr ?? ''
    metaEditor.quelle = item.quelle || ''
    metaEditor.sprache = item.sprache || ''
    metaEditor.analyzedAt = item.analyzed_at || ''
    metaEditor.analysisLang = item.analysis_lang || ''
    metaEditor.analysisModel = item.analysis_model || ''
    cardEditor.wissen = parseWissenSections(item.wissen || '')
    expandedWissen.value = new Set()
    cardEditor.glossary = (item.glossary || []).map((g: any) => {
      const ov = glossaryOverrides.value[g.term] || {}
      return {
        term: g.term,
        definition: g.definition || '',
        overrideDefinition: ov.definition || '',
        hidden: !!ov.hidden,
      }
    })
    cardEditor.open = true
  } catch (e: any) {
    cardEditor.message = e.message
    cardEditor.error = true
    cardEditor.open = true
  }
}

async function saveCard() {
  cardEditor.saving = true
  cardEditor.message = ''
  cardEditor.error = false
  try {
    const resp = await api(`/items/${cardEditor.docId}/card`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card: cardEditor.text }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`)
    cardEditor.message = t('settings.knowledge.card.saved')
  } catch (e: any) {
    cardEditor.message = e.message
    cardEditor.error = true
  } finally {
    cardEditor.saving = false
  }
}

async function saveGlossaryOverrides() {
  glossarySaving.value = true
  glossaryMessage.value = ''
  glossaryError.value = false
  // merge this doc's edits into the full overrides map, then PUT the whole map
  const merged = { ...glossaryOverrides.value }
  for (const g of cardEditor.glossary) {
    const def = g.overrideDefinition.trim()
    if (g.hidden || def) {
      merged[g.term] = { definition: def || undefined, hidden: g.hidden || undefined }
    } else {
      delete merged[g.term]
    }
  }
  try {
    const resp = await api('/glossary-overrides', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ overrides: merged }),
    })
    const data = await resp.json()
    if (!resp.ok || !data.success) throw new Error(data.error || `HTTP ${resp.status}`)
    glossaryOverrides.value = merged
    glossaryMessage.value = t('settings.knowledge.glossary.saved')
  } catch (e: any) {
    glossaryMessage.value = e.message
    glossaryError.value = true
  } finally {
    glossarySaving.value = false
  }
}

onMounted(() => {
  loadAreas()
  loadJobs()
})
onUnmounted(() => {
  if (pollTimer !== null) clearInterval(pollTimer)
})
</script>

<style scoped>
.knowledge-library {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section {
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  padding: 15px;
}

.section.compact {
  padding: 12px 15px;
}

.section h2 {
  margin: 0 0 10px 0;
  font-size: 16px;
  font-weight: 700;
  color: #e0e0e0;
}

.section h3 {
  margin: 16px 0 8px 0;
  font-size: 14px;
  font-weight: 700;
  color: #e0e0e0;
}

.help {
  color: #b0b0b0;
  font-size: 13px;
  margin: 0 0 14px 0;
}

.hint {
  color: #9a9a9a;
  font-size: 12px;
  margin: 6px 0;
}

.select-hint {
  margin-top: 12px;
}

/* ===================== MoJo-style area chips ===================== */
.area-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.area-chip {
  border: 1px solid var(--surface-4);
  border-radius: 8px;
  background: var(--surface-2);
  min-width: 140px;
  transition: border-color 0.12s, box-shadow 0.12s, background 0.12s;
}

.area-chip.active {
  border-color: #4a90e2;
  box-shadow: 0 0 0 2px rgba(74, 144, 226, 0.25);
  background: var(--surface-1);
}

.area-chip.editing {
  min-width: 240px;
  background: var(--surface-1);
}

.area-chip .chip-display {
  padding: 9px 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.area-chip .chip-display:hover {
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
}

.chip-name {
  font-size: 13px;
  font-weight: 700;
  color: #e0e0e0;
}

.chip-count {
  font-size: 11px;
  color: #9a9a9a;
  white-space: nowrap;
}

.chip-edit-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: #4a90e2;
  font-size: 13px;
  padding: 0 2px;
  margin-inline-start: auto;
  line-height: 1;
}

.chip-edit-btn:hover {
  color: #6ba6e8;
}

/* fixed (UNESCO) chip */
.area-chip.fixed {
  background: var(--surface-2);
  border-style: solid;
  border-color: var(--surface-4);
}

.chip-lock {
  font-size: 12px;
}

.chip-fixed-tag {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #909090;
  border: 1px solid var(--surface-4);
  border-radius: 4px;
  padding: 1px 5px;
  margin-inline-start: auto;
}

/* dashed add chip */
.area-chip.add {
  border-style: dashed;
  border-color: var(--surface-4);
  background: transparent;
}

.chip-add-label {
  font-size: 13px;
  font-weight: 700;
  color: #4a90e2;
}

/* inline chip edit form */
.chip-edit {
  padding: 10px 12px;
  border-top: 1px solid var(--surface-4);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.area-chip.add .chip-edit,
.area-chip.editing .chip-edit {
  border-top: none;
}

.chip-input {
  padding: 5px 8px;
  border: 1px solid var(--surface-4);
  border-radius: 4px;
  font-size: 12px;
  background: var(--surface-1);
  color: #ececec;
  max-width: 260px;
}

.chip-edit-actions {
  display: flex;
  gap: 5px;
  align-items: center;
  flex-wrap: wrap;
}

.chip-btn {
  background: var(--surface-3);
  border: 1px solid var(--surface-4);
  color: #e0e0e0;
  border-radius: 4px;
  padding: 3px 9px;
  font-size: 12px;
  cursor: pointer;
}

.chip-btn:hover:not(:disabled) {
  background: var(--surface-4);
}

.chip-btn.primary {
  background: #4a90e2;
  border-color: #4a90e2;
  color: #fff;
}

.chip-btn.primary:hover:not(:disabled) {
  background: #3a7bc8;
}

.chip-btn.danger {
  color: #ff7b72;
  margin-inline-start: auto;
}

.chip-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chip-err {
  font-size: 11px;
  color: #ff7b72;
}

/* ===================== area panel ===================== */
.area-panel h2 {
  display: flex;
  align-items: center;
  gap: 6px;
}

.kommentar-block {
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 14px;
}

.kommentar-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #909090;
  margin-bottom: 4px;
}

.kommentar-view {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.kommentar-text {
  font-size: 13px;
  color: #e0e0e0;
  flex: 1;
}

.kommentar-empty {
  font-size: 12px;
  color: #aaa;
  font-style: italic;
  flex: 1;
}

.kommentar-edit {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kommentar-textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px;
  border: 1px solid var(--surface-4);
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  background: var(--surface-1);
  color: #ececec;
  resize: vertical;
}

/* drop-zone */
.dropzone-block {
  margin-bottom: 6px;
}

.dropzone {
  border: 2px dashed var(--surface-4);
  border-radius: 8px;
  padding: 22px 16px;
  text-align: center;
  cursor: pointer;
  background: var(--surface-2);
  transition: border-color 0.12s, background 0.12s;
}

.dropzone:hover {
  border-color: #4a90e2;
  background: var(--surface-3);
}

.dropzone.dragover {
  border-color: #4a90e2;
  background: rgba(33, 150, 243, 0.14);
}

.dropzone.busy {
  opacity: 0.6;
  cursor: default;
}

.dropzone-label {
  font-size: 14px;
  font-weight: 700;
  color: #c0c0c0;
}

.dropzone-hint {
  font-size: 12px;
  color: #909090;
  margin-top: 4px;
}

.hidden-file {
  display: none;
}

.dropzone-hinweis {
  margin-top: 10px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field label {
  font-size: 13px;
  font-weight: 700;
  color: #e0e0e0;
}

.field input[type='text'] {
  padding: 7px 9px;
  border: 1px solid var(--surface-4);
  border-radius: 3px;
  font-size: 13px;
  background: var(--surface-1);
  color: #ececec;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.action-btn {
  background: var(--surface-4);
  color: #fff;
  border: none;
  padding: 8px 16px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 13px;
}

.action-btn:hover:not(:disabled) {
  background: #777;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn.secondary {
  background: #999;
}

.upload-msg {
  font-size: 13px;
  color: #66bb6a;
}

.upload-msg.error {
  color: #ff7b72;
}

/* Jobs */
.job-row {
  border-top: 1px solid var(--surface-4);
  padding: 8px 0;
}

.job-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.job-badge {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 3px;
  color: #fff;
}

.state-queued { background: #9e9e9e; }
.state-running { background: #1976d2; }
.state-done { background: #2e7d32; }
.state-error { background: #c62828; }
.state-cancelled { background: #6d4c41; }

.job-title { font-weight: 700; color: #e0e0e0; font-size: 13px; }
.job-msg { color: #b0b0b0; font-size: 12px; }

.job-log {
  background: var(--surface-2);
  color: #d4d4d4;
  font-family: monospace;
  font-size: 11px;
  padding: 10px;
  border-radius: 3px;
  overflow-x: auto;
  white-space: pre-wrap;
  margin: 8px 0 0 0;
  max-height: 260px;
}

.link-btn {
  background: none;
  border: none;
  color: #64b5f6;
  cursor: pointer;
  font-size: 12px;
  padding: 2px 4px;
  text-decoration: underline;
}

.link-btn.danger { color: #ff7b72; }

.link-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  text-decoration: none;
}

.panel-docs-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.refresh-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* Items table */
.items-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.items-table th,
.items-table td {
  text-align: start;
  padding: 8px 10px;
  border-bottom: 1px solid var(--surface-4);
  vertical-align: top;
}

.items-table th {
  background: var(--surface-2);
  color: #e0e0e0;
  font-weight: 700;
}

.doc-id {
  color: #909090;
  font-family: monospace;
  font-size: 11px;
}

/* Analysis provenance — quiet metadata, not a headline (2026-07-10). */
.analysis-cell {
  white-space: nowrap;
}
.analysis-meta {
  color: #909090;
  font-size: 11px;
}
.analysis-lang {
  color: #aaa;
}
.analysis-none {
  font-style: italic;
}

.status-badge {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 3px;
  color: #fff;
}

.status-published { background: #2e7d32; }
.status-draft { background: #ef6c00; }

.actions-cell {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.move-control {
  display: inline-flex;
}

.move-select {
  font-size: 12px;
  padding: 2px 4px;
  border: 1px solid var(--surface-4);
  border-radius: 3px;
  background: var(--surface-1);
  color: #64b5f6;
  cursor: pointer;
  max-width: 160px;
}

.move-select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.move-err {
  font-size: 11px;
  color: #ff7b72;
  flex-basis: 100%;
}

/* Card editor */
.card-textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 10px;
  border: 1px solid var(--surface-4);
  border-radius: 3px;
  font-family: monospace;
  font-size: 13px;
  background: var(--surface-1);
  color: #ececec;
  resize: vertical;
  margin-bottom: 10px;
}

/* Bibliographic meta panel (titel/autor/jahr/quelle) in the document view. */
.meta-panel {
  border: 1px solid var(--surface-4);
  border-radius: 4px;
  padding: 10px 12px;
  margin: 0 0 14px 0;
  background: var(--surface-2);
}
.meta-display {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.meta-grid {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 3px 12px;
  margin: 0;
  flex: 1;
  min-width: 0;
}
.meta-grid dt {
  font-weight: 700;
  color: #c0c0c0;
  font-size: 12px;
}
.meta-grid dd {
  margin: 0;
  color: #ececec;
  font-size: 13px;
  word-break: break-word;
}
.provenance-grid dd {
  color: #b0b0b0;
}
.never-analyzed {
  font-style: italic;
  color: #909090;
}
.meta-edit-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: #4a90e2;
  font-size: 14px;
  padding: 0 2px;
  flex-shrink: 0;
}
.meta-edit-btn:hover { color: #64b5f6; }
.meta-field {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-bottom: 8px;
}
.meta-field > span {
  font-weight: 700;
  color: #c0c0c0;
  font-size: 12px;
}
.meta-input {
  width: 100%;
  box-sizing: border-box;
  padding: 6px 8px;
  border: 1px solid var(--surface-4);
  border-radius: 4px;
  font-size: 13px;
  background: var(--surface-1);
  color: #ececec;
}
.meta-input-short { max-width: 120px; }

.glossary-panel {
  margin-top: 18px;
  border-top: 1px solid var(--surface-4);
  padding-top: 12px;
}

.wissen-panel {
  margin-top: 18px;
  border-top: 1px solid var(--surface-4);
  padding-top: 12px;
}

.wissen-section {
  border: 1px solid var(--surface-4);
  border-radius: 4px;
  margin: 6px 0;
  overflow: hidden;
}

.wissen-head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  text-align: left;
  background: var(--surface-2);
  border: none;
  padding: 8px 10px;
  cursor: pointer;
  font-size: 13px;
  color: #ececec;
}

.wissen-head:hover {
  background: var(--surface-3);
}

.wissen-caret {
  color: #9a9a9a;
  font-size: 11px;
  width: 12px;
}

.wissen-title {
  font-weight: 700;
}

.wissen-body {
  margin: 0;
  padding: 10px 12px;
  background: var(--surface-1);
  color: #ececec;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-x: auto;
  border-top: 1px solid var(--surface-4);
}

.wissen-empty {
  font-size: 13px;
  color: #9a9a9a;
  font-style: italic;
}

.gloss-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 0;
  flex-wrap: wrap;
}

.gloss-term {
  font-weight: 700;
  color: #e0e0e0;
  font-size: 13px;
  min-width: 140px;
}

.gloss-def {
  flex: 1;
  min-width: 200px;
  padding: 6px 8px;
  border: 1px solid var(--surface-4);
  border-radius: 3px;
  font-size: 13px;
  background: var(--surface-1);
  color: #ececec;
}

.cb {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  font-weight: 400;
  color: #e0e0e0;
}

/* Read-only (Tier-F/UNESCO) affordances: a small lock on the row + plain-text
   renderings of the profile and glossary (no input chrome). */
.ro-lock {
  margin-left: 6px;
  font-size: 12px;
  opacity: 0.7;
}

.card-readonly {
  margin: 0 0 10px;
  padding: 10px 12px;
  background: var(--surface-1);
  color: #ececec;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-x: auto;
  border: 1px solid var(--surface-4);
  border-radius: 4px;
}

.gloss-row.readonly {
  align-items: baseline;
}

.gloss-def-ro {
  flex: 1;
  min-width: 200px;
  font-size: 13px;
  color: #e0e0e0;
  line-height: 1.5;
}
</style>
