<template>
  <div class="session-export-container">
    <div class="export-header">
      <h2>{{ t('sessionExport.title') }}</h2>
      <p class="help">{{ t('sessionExport.intro') }}</p>
    </div>

    <!-- Statistics -->
    <div class="stats-container" v-if="!loading && !error">
      <div class="stat-card">
        <div class="stat-number">{{ stats.total }}</div>
        <div class="stat-label">{{ t('sessionExport.totalSessions') }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-number">{{ stats.devices }}</div>
        <div class="stat-label">{{ t('sessionExport.devices') }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-number">{{ stats.configs }}</div>
        <div class="stat-label">{{ t('sessionExport.configs') }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-number">{{ stats.media }}</div>
        <div class="stat-label">{{ t('sessionExport.mediaFiles') }}</div>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters-container" v-if="!loading && !error">
      <div class="filter-row">
        <div class="filter-group">
          <label>{{ t('sessionExport.dateRange') }}</label>
          <div class="date-range">
            <input type="date" v-model="filters.date_from" @change="applyFilters" :placeholder="t('sessionExport.from')" />
            <span class="date-separator">→</span>
            <input type="date" v-model="filters.date_to" @change="applyFilters" :placeholder="t('sessionExport.to')" />
          </div>
        </div>

        <div class="filter-group export-buttons-group">
          <button @click="exportFilteredAsZipJSON" class="export-zip-json-btn" :disabled="loading || sessions.length === 0">
            {{ t('sessionExport.exportZipJson') }}
          </button>
          <button @click="exportFilteredAsZipPDF" class="export-zip-pdf-btn" :disabled="loading || sessions.length === 0">
            {{ t('sessionExport.exportZipPdf') }}
          </button>
        </div>

        <div class="filter-group available-dates-group">
          <label>{{ t('sessionExport.availableDates') }}</label>
          <div class="available-dates">
            <button
              v-for="dateInfo in availableDates.slice(0, 10)"
              :key="dateInfo.date"
              @click="selectDate(dateInfo.date)"
              :class="['date-btn', { active: isDateSelected(dateInfo.date) }]"
              :title="`${dateInfo.count} sessions`"
            >
              {{ formatShortDate(dateInfo.date) }}
              <span class="date-count">{{ dateInfo.count }}</span>
            </button>
            <button
              v-if="availableDates.length > 10"
              @click="showAllDates = !showAllDates"
              class="date-btn more-dates"
            >
              {{ showAllDates ? t('sessionExport.less') : t('sessionExport.nMore', { n: availableDates.length - 10 }) }}
            </button>
          </div>
          <div v-if="showAllDates" class="available-dates">
            <button
              v-for="dateInfo in availableDates.slice(10)"
              :key="dateInfo.date"
              @click="selectDate(dateInfo.date)"
              :class="['date-btn', { active: isDateSelected(dateInfo.date) }]"
              :title="`${dateInfo.count} sessions`"
            >
              {{ formatShortDate(dateInfo.date) }}
              <span class="date-count">{{ dateInfo.count }}</span>
            </button>
          </div>
        </div>

        <div class="filter-group">
          <label>{{ t('sessionExport.device') }}</label>
          <select v-model="filters.device_id" @change="applyFilters">
            <option value="">{{ t('sessionExport.allDevices') }}</option>
            <option v-for="device in availableFilters.devices" :key="device" :value="device">
              {{ device.substring(0, 8) }}...
            </option>
          </select>
        </div>

        <div class="filter-group">
          <label>{{ t('sessionExport.config') }}</label>
          <select v-model="filters.config_name" @change="applyFilters">
            <option value="">{{ t('sessionExport.allConfigs') }}</option>
            <option v-for="config in availableFilters.configs" :key="config" :value="config">
              {{ config }}
            </option>
          </select>
        </div>

        <div class="filter-group">
          <label>{{ t('sessionExport.safetyLevel') }}</label>
          <select v-model="filters.safety_level" @change="applyFilters">
            <option value="">{{ t('sessionExport.allLevels') }}</option>
            <option v-for="level in availableFilters.safety_levels" :key="level" :value="level">
              {{ level }}
            </option>
          </select>
        </div>

        <div class="filter-group">
          <label>{{ t('sessionExport.source') }}</label>
          <select v-model="filters.source_view" @change="applyFilters">
            <option value="">{{ t('sessionExport.allSources') }}</option>
            <option v-for="sv in availableFilters.source_views" :key="sv" :value="sv">
              {{ sv }}
            </option>
          </select>
        </div>

        <div class="filter-group">
          <label>{{ t('sessionExport.search') }}</label>
          <input
            type="text"
            v-model="filters.search"
            @input="debouncedSearch"
            :placeholder="t('sessionExport.sessionIdPlaceholder')"
          />
        </div>

        <div class="filter-group">
          <button @click="clearFilters" class="clear-btn">{{ t('sessionExport.clearFilters') }}</button>
        </div>
      </div>
    </div>

    <!-- Loading / Error -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>{{ t('sessionExport.loadingSessions') }}</p>
    </div>

    <div v-if="error" class="error-state">
      <p>{{ t('sessionExport.errorColon') }} {{ error }}</p>
    </div>

    <!-- Pagination (Top) -->
    <div v-if="!loading && !error && sessions.length > 0" class="pagination-top">
      <div class="pagination">
        <button
          @click="goToPage(currentPage - 1)"
          :disabled="currentPage <= 1"
          class="page-btn"
        >
          {{ t('sessionExport.previous') }}
        </button>

        <div class="page-numbers">
          <button
            v-for="page in visiblePages"
            :key="page"
            @click="page !== '...' && goToPage(page)"
            :class="['page-number-btn', { active: page === currentPage, dots: page === '...' }]"
            :disabled="page === '...'"
          >
            {{ page }}
          </button>
        </div>

        <button
          @click="goToPage(currentPage + 1)"
          :disabled="currentPage >= totalPages"
          class="page-btn"
        >
          {{ t('sessionExport.next') }}
        </button>

        <select v-model.number="perPage" @change="applyFilters" class="per-page-select">
          <option v-for="n in [25, 50, 100, 250]" :key="n" :value="n">{{ t('sessionExport.perPage', { n }) }}</option>
        </select>

        <span class="page-info">
          {{ t('sessionExport.totalSessionsCount', { n: stats.total }) }}
        </span>
      </div>
    </div>

    <!-- Sessions Table -->
    <div v-if="!loading && !error && sessions.length > 0" class="table-container">
      <table class="sessions-table">
        <thead>
          <tr>
            <th>{{ t('sessionExport.preview') }}</th>
            <th @click="sortBy('timestamp')" class="sortable">
              {{ t('sessionExport.timestamp') }}
              <span v-if="sortField === 'timestamp'">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
            </th>
            <th @click="sortBy('device_id')" class="sortable">
              {{ t('sessionExport.device') }}
              <span v-if="sortField === 'device_id'">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
            </th>
            <th @click="sortBy('config_name')" class="sortable">
              {{ t('sessionExport.stage2Config') }}
              <span v-if="sortField === 'config_name'">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
            </th>
            <th>{{ t('sessionExport.source') }}</th>
            <th>{{ t('sessionExport.mode') }}</th>
            <th>{{ t('sessionExport.safetyLevel') }}</th>
            <th>{{ t('sessionExport.stage') }}</th>
            <th>{{ t('sessionExport.entities') }}</th>
            <th>{{ t('sessionExport.media') }}</th>
            <th>{{ t('sessionExport.sessionId') }}</th>
            <th>{{ t('sessionExport.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="session in sessions" :key="session.run_id">
            <td>
              <!-- Preferred: the server-built miniature, a few kB instead of the full render. -->
              <div v-if="session.thumbnail_url" class="thumbnail-container">
                <img v-lazy-media="session.thumbnail_url" class="thumbnail" @error="handleImageError" />
                <div v-if="session.thumbnail_type === 'video'" class="video-indicator">▶</div>
              </div>
              <!-- Fallback for servers that cannot build one (e.g. no ffmpeg for video). -->
              <div v-else-if="session.thumbnail && session.thumbnail_type === 'image'" class="thumbnail-container">
                <img v-lazy-media="session.thumbnail" class="thumbnail" @error="handleImageError" />
              </div>
              <div v-else-if="session.thumbnail && session.thumbnail_type === 'video'" class="thumbnail-container">
                <video v-lazy-media="session.thumbnail" class="thumbnail" muted preload="metadata" @error="handleImageError"></video>
                <div class="video-indicator">▶</div>
              </div>
              <div v-else class="no-thumbnail">
                <span>{{ t('sessionExport.noMedia') }}</span>
              </div>
            </td>
            <td>{{ formatTimestamp(session.timestamp) }}</td>
            <td>{{ session.device_id ? session.device_id.substring(0, 8) + '...' : t('sessionExport.notAvailable') }}</td>
            <td><span class="config-badge">{{ session.config_name }}</span></td>
            <td>
              <span v-if="session.source_view" class="source-badge" :class="`source-${session.source_view}`">{{ session.source_view }}</span>
              <span v-else class="source-badge source-default">{{ t('sessionExport.sourceDirect') }}</span>
            </td>
            <td><span class="mode-badge">{{ session.output_mode || t('sessionExport.notAvailable') }}</span></td>
            <td><span class="safety-badge" :class="`safety-${session.safety_level}`">{{ session.safety_level }}</span></td>
            <td>{{ session.stage }} / {{ session.step }}</td>
            <td>{{ session.entity_count }}</td>
            <td>{{ session.media_count }}</td>
            <td><code class="run-id">{{ session.run_id.substring(0, 8) }}...</code></td>
            <td>
              <button @click="viewSession(session.run_id)" class="action-btn view-btn">{{ t('sessionExport.view') }}</button>
              <button @click="downloadSession(session.run_id)" class="action-btn download-btn">{{ t('sessionExport.json') }}</button>
              <button @click="downloadSessionAsPDF(session.run_id)" class="action-btn pdf-btn">{{ t('sessionExport.pdf') }}</button>
            </td>
          </tr>
        </tbody>
      </table>

    </div>

    <!-- No Data -->
    <div v-if="!loading && !error && sessions.length === 0" class="no-data">
      <p>{{ t('sessionExport.noSessions') }}</p>
    </div>

    <!-- Session Detail Modal -->
    <div v-if="showModal" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ t('sessionExport.sessionDetails') }}</h3>
          <button @click="closeModal" class="close-btn">×</button>
        </div>
        <div class="modal-body">
          <div v-if="loadingDetail" class="loading-state">
            <div class="spinner"></div>
            <p>{{ t('sessionExport.loadingDetails') }}</p>
          </div>
          <div v-else-if="selectedSession">
            <div class="detail-section">
              <h4>{{ t('sessionExport.metadata') }}</h4>
              <table class="detail-table">
                <tr>
                  <td><strong>{{ t('sessionExport.sessionIdColon') }}</strong></td>
                  <td><code>{{ selectedSession.run_id }}</code></td>
                </tr>
                <tr>
                  <td><strong>{{ t('sessionExport.timestampColon') }}</strong></td>
                  <td>{{ formatTimestamp(selectedSession.timestamp) }}</td>
                </tr>
                <tr>
                  <td><strong>{{ t('sessionExport.configColon') }}</strong></td>
                  <td>{{ selectedSession.config_name }}</td>
                </tr>
                <tr>
                  <td><strong>{{ t('sessionExport.deviceColon') }}</strong></td>
                  <td>{{ selectedSession.device_id || t('sessionExport.notAvailable') }}</td>
                </tr>
                <tr>
                  <td><strong>{{ t('sessionExport.safetyLevelColon') }}</strong></td>
                  <td>{{ selectedSession.safety_level }}</td>
                </tr>
                <tr v-if="selectedSession.source_view">
                  <td><strong>{{ t('sessionExport.sourceColon') }}</strong></td>
                  <td><span class="source-badge" :class="`source-${selectedSession.source_view}`">{{ selectedSession.source_view }}</span></td>
                </tr>
                <tr v-if="selectedSession.comparison_group">
                  <td><strong>{{ t('sessionExport.comparisonGroupColon') }}</strong></td>
                  <td><code>{{ selectedSession.comparison_group.group_id }}</code></td>
                </tr>
                <tr>
                  <td><strong>{{ t('sessionExport.stageColon') }}</strong></td>
                  <td>{{ selectedSession.current_state?.stage }} / {{ selectedSession.current_state?.step }}</td>
                </tr>
              </table>
            </div>

            <div class="detail-section">
              <h4>{{ t('sessionExport.entitiesCount', { n: selectedSession.entities?.length || 0 }) }}</h4>
              <div v-for="entity in selectedSession.entities" :key="entity.sequence" class="entity-item">
                <div class="entity-header">
                  <span class="entity-type">{{ entity.type }}</span>
                  <span class="entity-filename">{{ entity.filename }}</span>
                  <span class="entity-time">{{ formatTime(entity.timestamp) }}</span>
                </div>
                <div v-if="entity.image_url" class="entity-image">
                  <img :src="entity.image_url" :alt="entity.filename" class="detail-image" />
                </div>
                <div v-else-if="entity.video_url" class="entity-video">
                  <video :src="entity.video_url" controls class="detail-video">
                    {{ t('sessionExport.videoUnsupported') }}
                  </video>
                </div>
                <div v-else-if="entity.content" class="entity-content">
                  <pre>{{ entity.content }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { vLazyMedia } from '@/composables/useLazyMedia'
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { jsPDF } from 'jspdf'
import { downloadBlob } from '@/lib/downloadMedia'

const { t } = useI18n()

/**
 * AI-Origin Disclosure (EU AI Act Art. 50) on the report itself.
 *
 * The pictures in this report are re-encoded through a canvas on the way into
 * the document, and that strips what the platform wrote into each file. The
 * document can still say what it holds — and the untouched, marked originals
 * are in the ZIP export next to it.
 */
const DIGITAL_SOURCE_TYPE_AI =
  'http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia'

function markPdf(doc) {
  try {
    doc.setProperties({
      subject: `Contains AI-generated media. iptcExt:DigitalSourceType=${DIGITAL_SOURCE_TYPE_AI}`,
      keywords: `AI-generated, ${DIGITAL_SOURCE_TYPE_AI}`,
    })
  } catch {
    /* a report without the property is still a report */
  }
}
import JSZip from 'jszip'

const loading = ref(false)
const error = ref(null)
const sessions = ref([])
const currentPage = ref(1)
const perPage = ref(50)
const totalPages = ref(0)
const sortField = ref('timestamp')
const sortOrder = ref('desc')

const filters = ref({
  date_from: new Date().toISOString().split('T')[0], // Today by default
  date_to: new Date().toISOString().split('T')[0],   // Today by default
  device_id: '',
  config_name: '',
  safety_level: '',
  source_view: '',
  search: ''
})

const availableDates = ref([])
const showAllDates = ref(false)

const availableFilters = ref({
  devices: [],
  configs: [],
  safety_levels: [],
  source_views: []
})

const stats = ref({
  total: 0,
  devices: 0,
  configs: 0,
  media: 0
})

const showModal = ref(false)
const selectedSession = ref(null)
const loadingDetail = ref(false)

let searchTimeout = null

const visiblePages = computed(() => {
  const pages = []
  const total = totalPages.value
  const current = currentPage.value

  if (total <= 7) {
    // Show all pages if 7 or fewer
    for (let i = 1; i <= total; i++) {
      pages.push(i)
    }
  } else {
    // Always show first page
    pages.push(1)

    if (current > 3) {
      pages.push('...')
    }

    // Show pages around current
    const start = Math.max(2, current - 1)
    const end = Math.min(total - 1, current + 1)

    for (let i = start; i <= end; i++) {
      pages.push(i)
    }

    if (current < total - 2) {
      pages.push('...')
    }

    // Always show last page
    pages.push(total)
  }

  return pages
})

async function loadAvailableDates() {
  try {
    const response = await fetch('/api/settings/sessions/available-dates', {
      credentials: 'include'
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()
    availableDates.value = data.dates
  } catch (e) {
    console.error('Failed to load available dates:', e)
  }
}

async function loadSessions() {
  try {
    loading.value = true
    error.value = null

    const params = new URLSearchParams({
      page: currentPage.value,
      per_page: perPage.value,
      sort: sortField.value,
      order: sortOrder.value,
      ...(filters.value.date_from && { date_from: filters.value.date_from }),
      ...(filters.value.date_to && { date_to: filters.value.date_to }),
      ...(filters.value.device_id && { device_id: filters.value.device_id }),
      ...(filters.value.config_name && { config_name: filters.value.config_name }),
      ...(filters.value.safety_level && { safety_level: filters.value.safety_level }),
      ...(filters.value.source_view && { source_view: filters.value.source_view }),
      ...(filters.value.search && { search: filters.value.search })
    })

    const response = await fetch(`/api/settings/sessions?${params}`, {
      credentials: 'include'
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()
    sessions.value = data.sessions
    totalPages.value = data.total_pages
    stats.value.total = data.total

    // Update available filters
    availableFilters.value = data.filters
    stats.value.devices = data.filters.devices.length
    stats.value.configs = data.filters.configs.length
    stats.value.media = data.sessions.reduce((sum, s) => sum + s.media_count, 0)

  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  currentPage.value = 1
  loadSessions()
}

function debouncedSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    applyFilters()
  }, 500)
}

function clearFilters() {
  const today = new Date().toISOString().split('T')[0]
  filters.value = {
    date_from: today,
    date_to: today,
    device_id: '',
    config_name: '',
    safety_level: '',
    source_view: '',
    search: ''
  }
  applyFilters()
}

function selectDate(dateStr) {
  filters.value.date_from = dateStr
  filters.value.date_to = dateStr
  applyFilters()
}

function isDateSelected(dateStr) {
  return filters.value.date_from === dateStr && filters.value.date_to === dateStr
}

function formatShortDate(dateStr) {
  try {
    const dt = new Date(dateStr)
    return dt.toLocaleDateString('de-DE', { month: 'short', day: 'numeric' })
  } catch {
    return dateStr
  }
}

function sortBy(field) {
  if (sortField.value === field) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortOrder.value = 'desc'
  }
  loadSessions()
}

function goToPage(page) {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
    loadSessions()
  }
}

async function viewSession(runId) {
  try {
    showModal.value = true
    loadingDetail.value = true
    selectedSession.value = null

    const response = await fetch(`/api/settings/sessions/${runId}`, {
      credentials: 'include'
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    selectedSession.value = await response.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loadingDetail.value = false
  }
}

function closeModal() {
  showModal.value = false
  selectedSession.value = null
}

async function downloadSession(runId) {
  try {
    const response = await fetch(`/api/settings/sessions/${runId}`, {
      credentials: 'include'
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()
    downloadBlob(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }), `session_${runId}.json`)
  } catch (e) {
    error.value = e.message
  }
}

async function downloadSessionAsPDF(runId) {
  try {
    const response = await fetch(`/api/settings/sessions/${runId}`, {
      credentials: 'include'
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()

    // Helper function to load media as data URL
    const loadMediaAsDataURL = async (url, isVideo = false) => {
      try {
        if (isVideo) {
          // Create video element and extract first frame
          return new Promise((resolve, reject) => {
            const video = document.createElement('video')
            video.crossOrigin = 'anonymous'
            video.src = url
            video.muted = true

            video.addEventListener('loadeddata', () => {
              // Seek to 0.1 seconds to avoid blank frame
              video.currentTime = 0.1
            })

            video.addEventListener('seeked', () => {
              try {
                const canvas = document.createElement('canvas')
                canvas.width = video.videoWidth
                canvas.height = video.videoHeight
                const ctx = canvas.getContext('2d')
                ctx.drawImage(video, 0, 0)
                const dataURL = canvas.toDataURL('image/jpeg', 0.8)
                resolve(dataURL)
              } catch (e) {
                reject(e)
              }
            })

            video.addEventListener('error', () => reject(new Error('Video load failed')))
          })
        } else {
          // Load image
          return new Promise((resolve, reject) => {
            const img = new Image()
            img.crossOrigin = 'anonymous'
            img.onload = () => {
              const canvas = document.createElement('canvas')
              canvas.width = img.width
              canvas.height = img.height
              const ctx = canvas.getContext('2d')
              ctx.drawImage(img, 0, 0)
              const dataURL = canvas.toDataURL('image/jpeg', 0.8)
              resolve(dataURL)
            }
            img.onerror = () => reject(new Error('Image load failed'))
            img.src = url
          })
        }
      } catch (e) {
        console.error('Failed to load media:', e)
        return null
      }
    }

    // Create PDF
    const doc = new jsPDF()
    markPdf(doc)
    const pageWidth = doc.internal.pageSize.getWidth()
    const pageHeight = doc.internal.pageSize.getHeight()
    const margin = 20
    const contentWidth = pageWidth - 2 * margin
    const maxImageWidth = contentWidth
    const maxImageHeight = 100 // Max height for images in PDF
    let yPos = 20

    // Title
    doc.setFontSize(18)
    doc.setFont('helvetica', 'bold')
    doc.text('ATELIER Session Report', margin, yPos)
    yPos += 15

    // Session ID
    doc.setFontSize(10)
    doc.setFont('helvetica', 'normal')
    doc.text(`Session ID: ${runId}`, margin, yPos)
    yPos += 10

    // Basic Information Section
    doc.setFontSize(14)
    doc.setFont('helvetica', 'bold')
    doc.text('Basic Information', margin, yPos)
    yPos += 8

    doc.setFontSize(10)
    doc.setFont('helvetica', 'normal')
    const basicInfo = [
      `Timestamp: ${formatTimestamp(data.timestamp)}`,
      `Device: ${data.device_id || 'N/A'}`,
      `Stage2-Config: ${data.config_name}`,
      `Output Mode: ${data.output_mode || 'N/A'}`,
      `Safety Level: ${data.safety_level}`,

      `Stage: ${data.current_state?.stage || 'N/A'}`,
      `Step: ${data.current_state?.step || 'N/A'}`,
      `Entity Count: ${data.entities?.length || 0}`,
      `Media Count: ${data.media_count || 0}`
    ]

    basicInfo.forEach(line => {
      if (yPos > pageHeight - 30) {
        doc.addPage()
        yPos = 20
      }
      doc.text(line, margin, yPos)
      yPos += 6
    })

    yPos += 10

    // Entities Section with Media
    if (data.entities && data.entities.length > 0) {
      doc.setFontSize(14)
      doc.setFont('helvetica', 'bold')
      if (yPos > pageHeight - 30) {
        doc.addPage()
        yPos = 20
      }
      doc.text('Entities', margin, yPos)
      yPos += 8

      doc.setFontSize(9)
      doc.setFont('helvetica', 'normal')

      for (let index = 0; index < data.entities.length; index++) {
        const entity = data.entities[index]

        // Check if we need a new page for entity header
        if (yPos > pageHeight - 40) {
          doc.addPage()
          yPos = 20
        }

        // Entity header
        doc.setFont('helvetica', 'bold')
        doc.text(`${index + 1}. ${entity.type}`, margin, yPos)
        yPos += 5

        doc.setFont('helvetica', 'normal')
        doc.text(`Filename: ${entity.filename}`, margin + 5, yPos)
        yPos += 5

        if (entity.timestamp) {
          doc.text(`Time: ${formatTime(entity.timestamp)}`, margin + 5, yPos)
          yPos += 5
        }

        // Handle media (images and videos)
        if (entity.image_url) {
          try {
            const dataURL = await loadMediaAsDataURL(entity.image_url, false)
            if (dataURL) {
              // Check if image will fit on current page
              if (yPos + maxImageHeight > pageHeight - 30) {
                doc.addPage()
                yPos = 20
              }

              // Calculate scaled dimensions (wait for image to load)
              await new Promise((resolve) => {
                const img = new Image()
                img.onload = () => {
                  const aspectRatio = img.width / img.height
                  let imgWidth = maxImageWidth
                  let imgHeight = imgWidth / aspectRatio

                  if (imgHeight > maxImageHeight) {
                    imgHeight = maxImageHeight
                    imgWidth = imgHeight * aspectRatio
                  }

                  doc.addImage(dataURL, 'JPEG', margin + 5, yPos, imgWidth, imgHeight)
                  yPos += imgHeight + 5
                  resolve()
                }
                img.onerror = () => {
                  doc.text('[Image dimensions unavailable]', margin + 5, yPos)
                  yPos += 5
                  resolve()
                }
                img.src = dataURL
              })
            } else {
              doc.text('[Image could not be loaded]', margin + 5, yPos)
              yPos += 5
            }
          } catch (e) {
            doc.text(`[Image error: ${e.message}]`, margin + 5, yPos)
            yPos += 5
          }
        } else if (entity.video_url) {
          try {
            const dataURL = await loadMediaAsDataURL(entity.video_url, true)
            if (dataURL) {
              // Check if video frame will fit on current page
              if (yPos + maxImageHeight > pageHeight - 30) {
                doc.addPage()
                yPos = 20
              }

              // Calculate scaled dimensions (wait for image to load)
              await new Promise((resolve) => {
                const img = new Image()
                img.onload = () => {
                  const aspectRatio = img.width / img.height
                  let imgWidth = maxImageWidth
                  let imgHeight = imgWidth / aspectRatio

                  if (imgHeight > maxImageHeight) {
                    imgHeight = maxImageHeight
                    imgWidth = imgHeight * aspectRatio
                  }

                  doc.setFont('helvetica', 'italic')
                  doc.text('[Video frame]', margin + 5, yPos)
                  yPos += 5
                  doc.setFont('helvetica', 'normal')

                  doc.addImage(dataURL, 'JPEG', margin + 5, yPos, imgWidth, imgHeight)
                  yPos += imgHeight + 5
                  resolve()
                }
                img.onerror = () => {
                  doc.text('[Video frame dimensions unavailable]', margin + 5, yPos)
                  yPos += 5
                  resolve()
                }
                img.src = dataURL
              })
            } else {
              doc.text('[Video frame could not be extracted]', margin + 5, yPos)
              yPos += 5
            }
          } catch (e) {
            doc.text(`[Video error: ${e.message}]`, margin + 5, yPos)
            yPos += 5
          }
        }

        // Content preview (if text content exists)
        if (entity.content && typeof entity.content === 'string') {
          if (yPos > pageHeight - 30) {
            doc.addPage()
            yPos = 20
          }
          const contentPreview = entity.content.substring(0, 300) + (entity.content.length > 300 ? '...' : '')
          const lines = doc.splitTextToSize(`Content: ${contentPreview}`, contentWidth - 5)
          lines.forEach(line => {
            if (yPos > pageHeight - 30) {
              doc.addPage()
              yPos = 20
            }
            doc.text(line, margin + 5, yPos)
            yPos += 4
          })
        }

        yPos += 5
      }
    }

    // Footer on all pages
    const pageCount = doc.internal.getNumberOfPages()
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i)
      doc.setFontSize(8)
      doc.setFont('helvetica', 'italic')
      doc.text(
        `Generated by ATELIER - Page ${i} of ${pageCount}`,
        pageWidth / 2,
        pageHeight - 10,
        { align: 'center' }
      )
    }

    // Save PDF
    doc.save(`session_${runId}.pdf`)
  } catch (e) {
    error.value = e.message
  }
}

async function exportFilteredAsZipJSON() {
  if (sessions.value.length === 0) {
    error.value = t('sessionExport.noSessionsToDownload')
    return
  }

  try {
    loading.value = true
    error.value = null

    const zip = new JSZip()
    const dateStr = filters.value.date_from || new Date().toISOString().split('T')[0]
    const zipFolder = zip.folder(`ai4artsed_sessions_${dateStr}`)

    // Fetch all session details
    for (const session of sessions.value) {
      try {
        const response = await fetch(`/api/settings/sessions/${session.run_id}`, {
          credentials: 'include'
        })

        if (!response.ok) {
          console.error(`Failed to fetch session ${session.run_id}`)
          continue
        }

        const sessionData = await response.json()
        const sessionFolder = zipFolder.folder(session.run_id)

        // Add metadata.json
        sessionFolder.file('metadata.json', JSON.stringify(sessionData, null, 2))

        // Add all entity files
        if (sessionData.entities && sessionData.entities.length > 0) {
          for (const entity of sessionData.entities) {
            try {
              // Add text content
              if (entity.content && typeof entity.content === 'string') {
                sessionFolder.file(entity.filename, entity.content)
              }

              // Download and add images
              if (entity.image_url) {
                try {
                  const imgResponse = await fetch(entity.image_url)
                  if (imgResponse.ok) {
                    const imgBlob = await imgResponse.blob()
                    sessionFolder.file(entity.filename, imgBlob)
                  }
                } catch (e) {
                  console.error(`Failed to fetch image ${entity.filename}:`, e)
                }
              }

              // Download and add videos
              if (entity.video_url) {
                try {
                  const vidResponse = await fetch(entity.video_url)
                  if (vidResponse.ok) {
                    const vidBlob = await vidResponse.blob()
                    sessionFolder.file(entity.filename, vidBlob)
                  }
                } catch (e) {
                  console.error(`Failed to fetch video ${entity.filename}:`, e)
                }
              }
            } catch (e) {
              console.error(`Failed to process entity ${entity.filename}:`, e)
            }
          }
        }
      } catch (e) {
        console.error(`Failed to process session ${session.run_id}:`, e)
      }
    }

    // Generate and download ZIP
    downloadBlob(await zip.generateAsync({ type: 'blob' }), `ai4artsed_sessions_${dateStr}.zip`)

  } catch (e) {
    error.value = t('sessionExport.zipFailed', { m: e.message })
  } finally {
    loading.value = false
  }
}

async function exportFilteredAsZipPDF() {
  if (sessions.value.length === 0) {
    error.value = t('sessionExport.noSessionsToDownload')
    return
  }

  try {
    loading.value = true
    error.value = null

    const zip = new JSZip()
    const dateStr = filters.value.date_from || new Date().toISOString().split('T')[0]

    // Helper to load media (same as in downloadSessionAsPDF)
    const loadMediaAsDataURL = async (url, isVideo = false) => {
      try {
        if (isVideo) {
          return new Promise((resolve, reject) => {
            const video = document.createElement('video')
            video.crossOrigin = 'anonymous'
            video.src = url
            video.muted = true
            video.addEventListener('loadeddata', () => { video.currentTime = 0.1 })
            video.addEventListener('seeked', () => {
              try {
                const canvas = document.createElement('canvas')
                canvas.width = video.videoWidth
                canvas.height = video.videoHeight
                const ctx = canvas.getContext('2d')
                ctx.drawImage(video, 0, 0)
                resolve(canvas.toDataURL('image/jpeg', 0.8))
              } catch (e) { reject(e) }
            })
            video.addEventListener('error', () => reject(new Error('Video load failed')))
          })
        } else {
          return new Promise((resolve, reject) => {
            const img = new Image()
            img.crossOrigin = 'anonymous'
            img.onload = () => {
              const canvas = document.createElement('canvas')
              canvas.width = img.width
              canvas.height = img.height
              const ctx = canvas.getContext('2d')
              ctx.drawImage(img, 0, 0)
              resolve(canvas.toDataURL('image/jpeg', 0.8))
            }
            img.onerror = () => reject(new Error('Image load failed'))
            img.src = url
          })
        }
      } catch (e) {
        console.error('Failed to load media:', e)
        return null
      }
    }

    // Generate PDF for each session
    for (const session of sessions.value) {
      try {
        const response = await fetch(`/api/settings/sessions/${session.run_id}`, {
          credentials: 'include'
        })

        if (!response.ok) {
          console.error(`Failed to fetch session ${session.run_id}`)
          continue
        }

        const data = await response.json()

        const doc = new jsPDF()
        markPdf(doc)
        const pageWidth = doc.internal.pageSize.getWidth()
        const pageHeight = doc.internal.pageSize.getHeight()
        const margin = 20
        const contentWidth = pageWidth - 2 * margin
        const maxImageHeight = 100
        let yPos = 20

        // Title
        doc.setFontSize(18)
        doc.setFont('helvetica', 'bold')
        doc.text('ATELIER Session Report', margin, yPos)
        yPos += 15

        doc.setFontSize(10)
        doc.setFont('helvetica', 'normal')
        doc.text(`Session ID: ${session.run_id}`, margin, yPos)
        yPos += 10

        // Basic Info
        doc.setFontSize(14)
        doc.setFont('helvetica', 'bold')
        doc.text('Basic Information', margin, yPos)
        yPos += 8

        doc.setFontSize(10)
        doc.setFont('helvetica', 'normal')
        const basicInfo = [
          `Timestamp: ${formatTimestamp(data.timestamp)}`,
          `Device: ${data.device_id || 'N/A'}`,
          `Stage2-Config: ${data.config_name}`,
          `Output Mode: ${data.output_mode || 'N/A'}`,
          `Safety Level: ${data.safety_level}`,
    
          `Stage: ${data.current_state?.stage || 'N/A'}`,
          `Step: ${data.current_state?.step || 'N/A'}`,
          `Entity Count: ${data.entities?.length || 0}`,
          `Media Count: ${data.media_count || 0}`
        ]

        basicInfo.forEach(line => {
          if (yPos > pageHeight - 30) {
            doc.addPage()
            yPos = 20
          }
          doc.text(line, margin, yPos)
          yPos += 6
        })

        yPos += 10

        // Entities Section with Media
        if (data.entities && data.entities.length > 0) {
          doc.setFontSize(14)
          doc.setFont('helvetica', 'bold')
          if (yPos > pageHeight - 30) {
            doc.addPage()
            yPos = 20
          }
          doc.text('Entities', margin, yPos)
          yPos += 8

          doc.setFontSize(9)
          doc.setFont('helvetica', 'normal')

          for (let index = 0; index < data.entities.length; index++) {
            const entity = data.entities[index]

            if (yPos > pageHeight - 40) {
              doc.addPage()
              yPos = 20
            }

            doc.setFont('helvetica', 'bold')
            doc.text(`${index + 1}. ${entity.type}`, margin, yPos)
            yPos += 5

            doc.setFont('helvetica', 'normal')
            doc.text(`Filename: ${entity.filename}`, margin + 5, yPos)
            yPos += 5

            if (entity.timestamp) {
              doc.text(`Time: ${formatTime(entity.timestamp)}`, margin + 5, yPos)
              yPos += 5
            }

            // Handle media (images and videos)
            if (entity.image_url) {
              try {
                const dataURL = await loadMediaAsDataURL(entity.image_url, false)
                if (dataURL) {
                  if (yPos + maxImageHeight > pageHeight - 30) {
                    doc.addPage()
                    yPos = 20
                  }
                  await new Promise((resolve) => {
                    const img = new Image()
                    img.onload = () => {
                      const aspectRatio = img.width / img.height
                      let imgWidth = contentWidth
                      let imgHeight = imgWidth / aspectRatio
                      if (imgHeight > maxImageHeight) {
                        imgHeight = maxImageHeight
                        imgWidth = imgHeight * aspectRatio
                      }
                      doc.addImage(dataURL, 'JPEG', margin + 5, yPos, imgWidth, imgHeight)
                      yPos += imgHeight + 5
                      resolve()
                    }
                    img.onerror = () => {
                      doc.text('[Image dimensions unavailable]', margin + 5, yPos)
                      yPos += 5
                      resolve()
                    }
                    img.src = dataURL
                  })
                } else {
                  doc.text('[Image could not be loaded]', margin + 5, yPos)
                  yPos += 5
                }
              } catch (e) {
                doc.text(`[Image error: ${e.message}]`, margin + 5, yPos)
                yPos += 5
              }
            } else if (entity.video_url) {
              try {
                const dataURL = await loadMediaAsDataURL(entity.video_url, true)
                if (dataURL) {
                  if (yPos + maxImageHeight > pageHeight - 30) {
                    doc.addPage()
                    yPos = 20
                  }
                  await new Promise((resolve) => {
                    const img = new Image()
                    img.onload = () => {
                      const aspectRatio = img.width / img.height
                      let imgWidth = contentWidth
                      let imgHeight = imgWidth / aspectRatio
                      if (imgHeight > maxImageHeight) {
                        imgHeight = maxImageHeight
                        imgWidth = imgHeight * aspectRatio
                      }
                      doc.setFont('helvetica', 'italic')
                      doc.text('[Video frame]', margin + 5, yPos)
                      yPos += 5
                      doc.setFont('helvetica', 'normal')
                      doc.addImage(dataURL, 'JPEG', margin + 5, yPos, imgWidth, imgHeight)
                      yPos += imgHeight + 5
                      resolve()
                    }
                    img.onerror = () => {
                      doc.text('[Video frame dimensions unavailable]', margin + 5, yPos)
                      yPos += 5
                      resolve()
                    }
                    img.src = dataURL
                  })
                } else {
                  doc.text('[Video frame could not be extracted]', margin + 5, yPos)
                  yPos += 5
                }
              } catch (e) {
                doc.text(`[Video error: ${e.message}]`, margin + 5, yPos)
                yPos += 5
              }
            }

            // Content preview
            if (entity.content && typeof entity.content === 'string') {
              if (yPos > pageHeight - 30) {
                doc.addPage()
                yPos = 20
              }
              const contentPreview = entity.content.substring(0, 300) + (entity.content.length > 300 ? '...' : '')
              const lines = doc.splitTextToSize(`Content: ${contentPreview}`, contentWidth - 5)
              lines.forEach(line => {
                if (yPos > pageHeight - 30) {
                  doc.addPage()
                  yPos = 20
                }
                doc.text(line, margin + 5, yPos)
                yPos += 4
              })
            }

            yPos += 5
          }
        }

        // Footer
        const pageCount = doc.internal.getNumberOfPages()
        for (let i = 1; i <= pageCount; i++) {
          doc.setPage(i)
          doc.setFontSize(8)
          doc.setFont('helvetica', 'italic')
          doc.text(
            `Generated by ATELIER - Page ${i} of ${pageCount}`,
            pageWidth / 2,
            pageHeight - 10,
            { align: 'center' }
          )
        }

        const pdfBlob = doc.output('blob')
        zip.file(`${session.run_id}.pdf`, pdfBlob)

      } catch (e) {
        console.error(`Failed to generate PDF for session ${session.run_id}:`, e)
      }
    }

    // Generate and download ZIP
    downloadBlob(await zip.generateAsync({ type: 'blob' }), `ai4artsed_sessions_PDFs_${dateStr}.zip`)

  } catch (e) {
    error.value = t('sessionExport.pdfZipFailed', { m: e.message })
  } finally {
    loading.value = false
  }
}

function formatTimestamp(timestamp) {
  try {
    const dt = new Date(timestamp)
    return dt.toLocaleString('de-DE')
  } catch {
    return timestamp
  }
}

function formatTime(timestamp) {
  try {
    const dt = new Date(timestamp)
    return dt.toLocaleTimeString('de-DE')
  } catch {
    return timestamp
  }
}

function handleImageError(event) {
  // Hide broken image icon
  event.target.style.display = 'none'
}

onMounted(() => {
  loadAvailableDates()
  loadSessions()
})
</script>

<style scoped>
.session-export-container {
  padding: 20px;
  background: var(--bg-base);
  color: #fff;
  min-height: 100%;
}

.export-header {
  background: var(--surface-1);
  padding: 15px;
  border: 1px solid var(--surface-4);
  margin-bottom: 20px;
}

.export-header h2 {
  margin: 0 0 5px 0;
  font-size: 18px;
  font-weight: 700;
  color: #e0e0e0;
}

.export-header .help {
  margin: 0;
  font-size: 13px;
  color: #b0b0b0;
}

/* Statistics */
.stats-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.stat-card {
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  padding: 15px;
  text-align: center;
}

.stat-number {
  font-size: 28px;
  font-weight: 700;
  color: #4a9eff;
  margin-bottom: 5px;
}

.stat-label {
  font-size: 12px;
  color: #b0b0b0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Filters */
.filters-container {
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  padding: 15px;
  margin-bottom: 20px;
}

.filter-row {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
  align-items: flex-end;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 150px;
}

.filter-group label {
  font-size: 12px;
  font-weight: 700;
  color: #e0e0e0;
}

.filter-group input,
.filter-group select {
  padding: 6px 8px;
  border: 1px solid var(--surface-4);
  font-size: 13px;
  background: var(--surface-1);
  color: #f2f2f2;
}

.date-range {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-range input {
  flex: 1;
  min-width: 140px;
}

.date-separator {
  color: #b0b0b0;
  font-weight: 700;
}

.available-dates-group {
  min-width: 100%;
  flex-basis: 100%;
}

.available-dates {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 5px;
}

.date-btn {
  padding: 6px 10px;
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  cursor: pointer;
  font-size: 12px;
  color: #e0e0e0;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 5px;
  transition: all 0.2s;
}

.date-btn:hover {
  background: var(--surface-3);
  border-color: var(--surface-4);
}

.date-btn.active {
  background: #007bff;
  color: #fff;
  border-color: #0056b3;
  font-weight: 700;
}

.date-btn.active .date-count {
  background: rgba(255, 255, 255, 0.12);
}

.date-count {
  background: var(--surface-3);
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 700;
}

.date-btn.more-dates {
  background: var(--surface-3);
  color: #b0b0b0;
  font-style: italic;
}

.clear-btn {
  padding: 6px 12px;
  background: #6c757d;
  color: #fff;
  border: 1px solid var(--surface-4);
  cursor: pointer;
  font-size: 13px;
}

.clear-btn:hover {
  background: #888;
}

.export-buttons-group {
  display: flex;
  flex-direction: row;
  gap: 8px;
  align-items: center;
}

.export-zip-json-btn,
.export-zip-pdf-btn {
  padding: 6px 12px;
  color: #fff;
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  border-radius: 4px;
}

.export-zip-json-btn {
  background: #007bff;
}

.export-zip-json-btn:hover:not(:disabled) {
  background: #0056b3;
}

.export-zip-pdf-btn {
  background: #dc3545;
}

.export-zip-pdf-btn:hover:not(:disabled) {
  background: #c82333;
}

.export-zip-json-btn:disabled,
.export-zip-pdf-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Loading / Error */
.loading-state,
.error-state,
.no-data {
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  padding: 40px;
  text-align: center;
  color: #e0e0e0;
}

.spinner {
  border: 4px solid var(--surface-4);
  border-top: 4px solid #007bff;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin: 0 auto 15px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-state {
  color: #ff6b6b;
}

/* Table */
.table-container {
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  overflow-x: auto;
}

.sessions-table {
  width: 100%;
  border-collapse: collapse;
}

.sessions-table th,
.sessions-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--surface-4);
  color: #f2f2f2;
  font-size: 13px;
}

.sessions-table th {
  background: var(--surface-2);
  font-weight: 700;
  color: #e0e0e0;
}

.sessions-table th.sortable {
  cursor: pointer;
  user-select: none;
}

.sessions-table th.sortable:hover {
  background: var(--surface-3);
}

.sessions-table tbody tr:hover {
  background: var(--surface-2);
}

.config-badge {
  background: rgba(33, 150, 243, 0.14);
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 12px;
  font-family: monospace;
}

.pipeline-badge {
  background: rgba(255, 152, 0, 0.12);
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-family: monospace;
  color: #e0b64a;
}

.mode-badge {
  background: rgba(33, 150, 243, 0.14);
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 700;
  color: #7fd4e0;
}

.safety-badge {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.source-badge {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.source-persona {
  background: rgba(156, 39, 176, 0.18);
  color: #c39bd3;
}

.source-compare {
  background: rgba(76, 175, 80, 0.14);
  color: #66bb6a;
}

.source-default {
  background: var(--surface-3);
  color: #a9b3bd;
}

.safety-kids {
  background: rgba(76, 175, 80, 0.14);
  color: #7bc47f;
}

.safety-youth {
  background: rgba(255, 152, 0, 0.12);
  color: #e0b64a;
}

.safety-adult,
.safety-open {
  background: rgba(229, 57, 53, 0.14);
  color: #ff9e9e;
}

.run-id {
  font-family: monospace;
  font-size: 11px;
  background: var(--surface-2);
  padding: 2px 4px;
  border-radius: 2px;
}

.action-btn {
  padding: 4px 10px;
  font-size: 12px;
  border: 1px solid var(--surface-4);
  cursor: pointer;
  margin-right: 5px;
}

.view-btn {
  background: #007bff;
  color: #fff;
}

.view-btn:hover {
  background: #0056b3;
}

.download-btn {
  background: #28a745;
  color: #fff;
}

.download-btn:hover {
  background: #218838;
}

.pdf-btn {
  background: #dc3545;
  color: #fff;
}

.pdf-btn:hover {
  background: #c82333;
}

/* Pagination */
.pagination-top {
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  margin-bottom: 10px;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 15px;
  padding: 15px;
  background: var(--surface-2);
  flex-wrap: wrap;
}

.page-btn {
  padding: 8px 16px;
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  cursor: pointer;
  font-size: 13px;
  color: #f2f2f2;
  border-radius: 4px;
  font-weight: 400;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-btn:not(:disabled):hover {
  background: #007bff;
  color: #fff;
  border-color: #007bff;
}

.page-numbers {
  display: flex;
  gap: 5px;
  align-items: center;
}

.page-number-btn {
  padding: 6px 12px;
  background: var(--surface-1);
  border: 1px solid var(--surface-4);
  cursor: pointer;
  font-size: 13px;
  color: #f2f2f2;
  border-radius: 4px;
  min-width: 36px;
  text-align: center;
}

.page-number-btn:hover:not(.active):not(.dots) {
  background: var(--surface-3);
}

.page-number-btn.active {
  background: #007bff;
  color: #fff;
  border-color: #007bff;
  font-weight: 700;
}

.page-number-btn.dots {
  border: none;
  background: transparent;
  cursor: default;
  color: #b0b0b0;
}

.page-info {
  font-size: 13px;
  color: #b0b0b0;
  white-space: nowrap;
}

.per-page-select {
  padding: 6px 8px;
  border: 1px solid var(--surface-4);
  font-size: 13px;
  background: var(--surface-1);
  color: #f2f2f2;
  border-radius: 4px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgb(var(--bg-base-rgb) / 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--surface-1);
  width: 90%;
  max-width: 1000px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--surface-4);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid var(--surface-4);
  background: var(--surface-2);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  color: #e0e0e0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: #b0b0b0;
  line-height: 1;
  padding: 0;
  width: 30px;
  height: 30px;
}

.close-btn:hover {
  color: #f2f2f2;
}

.modal-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
  color: #f2f2f2;
}

.detail-section {
  margin-bottom: 25px;
}

.detail-section h4 {
  margin: 0 0 10px 0;
  font-size: 16px;
  color: #e0e0e0;
  border-bottom: 2px solid #007bff;
  padding-bottom: 5px;
}

.detail-table {
  width: 100%;
  border-collapse: collapse;
}

.detail-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--surface-4);
}

.detail-table code {
  background: var(--surface-2);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: monospace;
  font-size: 12px;
}

.entity-item {
  border: 1px solid var(--surface-4);
  margin-bottom: 10px;
  border-radius: 4px;
  overflow: hidden;
}

.entity-header {
  background: var(--surface-2);
  padding: 8px 12px;
  display: flex;
  gap: 15px;
  align-items: center;
  font-size: 12px;
}

.entity-type {
  font-weight: 700;
  color: #4a9eff;
}

.entity-filename {
  font-family: monospace;
  color: #b0b0b0;
}

.entity-time {
  color: #909090;
  margin-left: auto;
}

.entity-content {
  padding: 12px;
  background: var(--surface-1);
  border-top: 1px solid var(--surface-4);
}

.entity-content pre {
  margin: 0;
  font-size: 12px;
  font-family: monospace;
  white-space: pre-wrap;
  word-wrap: break-word;
  color: #e0e0e0;
}

.entity-image {
  padding: 12px;
  background: var(--surface-1);
  border-top: 1px solid var(--surface-4);
  text-align: center;
}

.detail-image {
  max-width: 100%;
  max-height: 600px;
  border: 1px solid var(--surface-4);
  border-radius: 4px;
}

/* Thumbnails */
.thumbnail-container {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  /* Holds the row height while the thumbnail has not been fetched yet. */
  background: var(--surface-2);
  border-radius: 4px;
}

.thumbnail {
  max-width: 60px;
  max-height: 60px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid var(--surface-4);
}

.no-thumbnail {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-2);
  border-radius: 4px;
  border: 1px solid var(--surface-4);
}

.no-thumbnail span {
  font-size: 10px;
  color: #909090;
  text-align: center;
}

.thumbnail-container {
  position: relative;
}

.video-indicator {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 20px;
  color: white;
  text-shadow: 0 0 4px rgba(0, 0, 0, 0.8);
  pointer-events: none;
}

.entity-video {
  padding: 12px;
  background: var(--surface-1);
  border-top: 1px solid var(--surface-4);
  text-align: center;
}

.detail-video {
  max-width: 100%;
  max-height: 600px;
  border: 1px solid var(--surface-4);
  border-radius: 4px;
}
</style>
