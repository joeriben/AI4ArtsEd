<template>
  <div class="session-export-container">
    <div class="export-header">
      <h2>Session Data Export</h2>
      <p class="help">View and export research data from generated sessions</p>
    </div>

    <!-- Statistics -->
    <div class="stats-container" v-if="!loading && !error">
      <div class="stat-card">
        <div class="stat-number">{{ stats.total }}</div>
        <div class="stat-label">Total Sessions</div>
      </div>
      <div class="stat-card">
        <div class="stat-number">{{ stats.devices }}</div>
        <div class="stat-label">Devices</div>
      </div>
      <div class="stat-card">
        <div class="stat-number">{{ stats.configs }}</div>
        <div class="stat-label">Configs</div>
      </div>
      <div class="stat-card">
        <div class="stat-number">{{ stats.media }}</div>
        <div class="stat-label">Media Files</div>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters-container" v-if="!loading && !error">
      <div class="filter-row">
        <div class="filter-group">
          <label>Date Range</label>
          <div class="date-range">
            <input type="date" v-model="filters.date_from" @change="applyFilters" placeholder="From" />
            <span class="date-separator">→</span>
            <input type="date" v-model="filters.date_to" @change="applyFilters" placeholder="To" />
          </div>
        </div>

        <div class="filter-group export-buttons-group">
          <button @click="exportFilteredAsZipJSON" class="export-zip-json-btn" :disabled="loading || sessions.length === 0">
            Export Filtered as ZIP (JSON)
          </button>
          <button @click="exportFilteredAsZipPDF" class="export-zip-pdf-btn" :disabled="loading || sessions.length === 0">
            Export Filtered as ZIP (PDF)
          </button>
        </div>

        <div class="filter-group available-dates-group">
          <label>Available Dates (click to select)</label>
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
              {{ showAllDates ? 'Less' : `+${availableDates.length - 10} more` }}
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
          <label>Device</label>
          <select v-model="filters.device_id" @change="applyFilters">
            <option value="">All Devices</option>
            <option v-for="device in availableFilters.devices" :key="device" :value="device">
              {{ device.substring(0, 8) }}...
            </option>
          </select>
        </div>

        <div class="filter-group">
          <label>Config</label>
          <select v-model="filters.config_name" @change="applyFilters">
            <option value="">All Configs</option>
            <option v-for="config in availableFilters.configs" :key="config" :value="config">
              {{ config }}
            </option>
          </select>
        </div>

        <div class="filter-group">
          <label>Safety Level</label>
          <select v-model="filters.safety_level" @change="applyFilters">
            <option value="">All Levels</option>
            <option v-for="level in availableFilters.safety_levels" :key="level" :value="level">
              {{ level }}
            </option>
          </select>
        </div>

        <div class="filter-group">
          <label>Source</label>
          <select v-model="filters.source_view" @change="applyFilters">
            <option value="">All Sources</option>
            <option v-for="sv in availableFilters.source_views" :key="sv" :value="sv">
              {{ sv }}
            </option>
          </select>
        </div>

        <div class="filter-group">
          <label>Search</label>
          <input
            type="text"
            v-model="filters.search"
            @input="debouncedSearch"
            placeholder="Session ID..."
          />
        </div>

        <div class="filter-group">
          <button @click="clearFilters" class="clear-btn">Clear Filters</button>
        </div>
      </div>
    </div>

    <!-- Loading / Error -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading sessions...</p>
    </div>

    <div v-if="error" class="error-state">
      <p>Error: {{ error }}</p>
    </div>

    <!-- Pagination (Top) -->
    <div v-if="!loading && !error && sessions.length > 0" class="pagination-top">
      <div class="pagination">
        <button
          @click="goToPage(currentPage - 1)"
          :disabled="currentPage <= 1"
          class="page-btn"
        >
          ‹ Previous
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
          Next ›
        </button>

        <select v-model.number="perPage" @change="applyFilters" class="per-page-select">
          <option :value="25">25 per page</option>
          <option :value="50">50 per page</option>
          <option :value="100">100 per page</option>
          <option :value="250">250 per page</option>
        </select>

        <span class="page-info">
          {{ stats.total }} total sessions
        </span>
      </div>
    </div>

    <!-- Sessions Table -->
    <div v-if="!loading && !error && sessions.length > 0" class="table-container">
      <table class="sessions-table">
        <thead>
          <tr>
            <th>Preview</th>
            <th @click="sortBy('timestamp')" class="sortable">
              Timestamp
              <span v-if="sortField === 'timestamp'">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
            </th>
            <th @click="sortBy('device_id')" class="sortable">
              Device
              <span v-if="sortField === 'device_id'">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
            </th>
            <th @click="sortBy('config_name')" class="sortable">
              Stage2-Config
              <span v-if="sortField === 'config_name'">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
            </th>
            <th>Source</th>
            <th>Modus</th>
            <th>Safety Level</th>
            <th>Stage</th>
            <th>Entities</th>
            <th>Media</th>
            <th>Session ID</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="session in sessions" :key="session.run_id">
            <td>
              <div v-if="session.thumbnail && session.thumbnail_type === 'image'" class="thumbnail-container">
                <img :src="session.thumbnail" class="thumbnail" @error="handleImageError" />
              </div>
              <div v-else-if="session.thumbnail && session.thumbnail_type === 'video'" class="thumbnail-container">
                <video :src="session.thumbnail" class="thumbnail" muted preload="metadata" @error="handleImageError"></video>
                <div class="video-indicator">▶</div>
              </div>
              <div v-else class="no-thumbnail">
                <span>No Media</span>
              </div>
            </td>
            <td>{{ formatTimestamp(session.timestamp) }}</td>
            <td>{{ session.device_id ? session.device_id.substring(0, 8) + '...' : 'N/A' }}</td>
            <td><span class="config-badge">{{ session.config_name }}</span></td>
            <td>
              <span v-if="session.source_view" class="source-badge" :class="`source-${session.source_view}`">{{ session.source_view }}</span>
              <span v-else class="source-badge source-default">direct</span>
            </td>
            <td><span class="mode-badge">{{ session.output_mode || 'N/A' }}</span></td>
            <td><span class="safety-badge" :class="`safety-${session.safety_level}`">{{ session.safety_level }}</span></td>
            <td>{{ session.stage }} / {{ session.step }}</td>
            <td>{{ session.entity_count }}</td>
            <td>{{ session.media_count }}</td>
            <td><code class="run-id">{{ session.run_id.substring(0, 8) }}...</code></td>
            <td>
              <button @click="viewSession(session.run_id)" class="action-btn view-btn">View</button>
              <button @click="downloadSession(session.run_id)" class="action-btn download-btn">JSON</button>
              <button @click="downloadSessionAsPDF(session.run_id)" class="action-btn pdf-btn">PDF</button>
            </td>
          </tr>
        </tbody>
      </table>

    </div>

    <!-- No Data -->
    <div v-if="!loading && !error && sessions.length === 0" class="no-data">
      <p>No sessions found for the selected filters.</p>
    </div>

    <!-- Session Detail Modal -->
    <div v-if="showModal" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Session Details</h3>
          <button @click="closeModal" class="close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="loadingDetail" class="loading-state">
            <div class="spinner"></div>
            <p>Loading session details...</p>
          </div>
          <div v-else-if="selectedSession">
            <div class="detail-section">
              <h4>Metadata</h4>
              <table class="detail-table">
                <tr>
                  <td><strong>Session ID:</strong></td>
                  <td><code>{{ selectedSession.run_id }}</code></td>
                </tr>
                <tr>
                  <td><strong>Timestamp:</strong></td>
                  <td>{{ formatTimestamp(selectedSession.timestamp) }}</td>
                </tr>
                <tr>
                  <td><strong>Config:</strong></td>
                  <td>{{ selectedSession.config_name }}</td>
                </tr>
                <tr>
                  <td><strong>Device:</strong></td>
                  <td>{{ selectedSession.device_id || 'N/A' }}</td>
                </tr>
                <tr>
                  <td><strong>Safety Level:</strong></td>
                  <td>{{ selectedSession.safety_level }}</td>
                </tr>
                <tr v-if="selectedSession.source_view">
                  <td><strong>Source:</strong></td>
                  <td><span class="source-badge" :class="`source-${selectedSession.source_view}`">{{ selectedSession.source_view }}</span></td>
                </tr>
                <tr v-if="selectedSession.comparison_group">
                  <td><strong>Comparison Group:</strong></td>
                  <td><code>{{ selectedSession.comparison_group.group_id }}</code></td>
                </tr>
                <tr>
                  <td><strong>Stage:</strong></td>
                  <td>{{ selectedSession.current_state?.stage }} / {{ selectedSession.current_state?.step }}</td>
                </tr>
              </table>
            </div>

            <div class="detail-section">
              <h4>Entities ({{ selectedSession.entities?.length || 0 }})</h4>
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
                    Your browser does not support the video tag.
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
import { ref, computed, onMounted } from 'vue'
import { jsPDF } from 'jspdf'
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
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `session_${runId}.json`
    a.click()
    URL.revokeObjectURL(url)
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
    doc.text('AI4ArtsEd Session Report', margin, yPos)
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
        `Generated by AI4ArtsEd DevServer - Page ${i} of ${pageCount}`,
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
    error.value = 'No sessions to download'
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
    const zipBlob = await zip.generateAsync({ type: 'blob' })
    const url = URL.createObjectURL(zipBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ai4artsed_sessions_${dateStr}.zip`
    a.click()
    URL.revokeObjectURL(url)

  } catch (e) {
    error.value = `ZIP creation failed: ${e.message}`
  } finally {
    loading.value = false
  }
}

async function exportFilteredAsZipPDF() {
  if (sessions.value.length === 0) {
    error.value = 'No sessions to download'
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
        const pageWidth = doc.internal.pageSize.getWidth()
        const pageHeight = doc.internal.pageSize.getHeight()
        const margin = 20
        const contentWidth = pageWidth - 2 * margin
        const maxImageHeight = 100
        let yPos = 20

        // Title
        doc.setFontSize(18)
        doc.setFont('helvetica', 'bold')
        doc.text('AI4ArtsEd Session Report', margin, yPos)
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
            `Generated by AI4ArtsEd DevServer - Page ${i} of ${pageCount}`,
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
    const zipBlob = await zip.generateAsync({ type: 'blob' })
    const url = URL.createObjectURL(zipBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ai4artsed_sessions_PDFs_${dateStr}.zip`
    a.click()
    URL.revokeObjectURL(url)

  } catch (e) {
    error.value = `PDF ZIP creation failed: ${e.message}`
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
  background: #000;
  color: #fff;
  min-height: 100vh;
}

.export-header {
  background: #fff;
  padding: 15px;
  border: 1px solid #ccc;
  margin-bottom: 20px;
}

.export-header h2 {
  margin: 0 0 5px 0;
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.export-header .help {
  margin: 0;
  font-size: 13px;
  color: #666;
}

/* Statistics */
.stats-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.stat-card {
  background: #fff;
  border: 1px solid #ccc;
  padding: 15px;
  text-align: center;
}

.stat-number {
  font-size: 28px;
  font-weight: bold;
  color: #007bff;
  margin-bottom: 5px;
}

.stat-label {
  font-size: 12px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Filters */
.filters-container {
  background: #fff;
  border: 1px solid #ccc;
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
  font-weight: 600;
  color: #333;
}

.filter-group input,
.filter-group select {
  padding: 6px 8px;
  border: 1px solid #ccc;
  font-size: 13px;
  background: #fff;
  color: #000;
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
  color: #666;
  font-weight: bold;
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
  background: #f0f0f0;
  border: 1px solid #ccc;
  cursor: pointer;
  font-size: 12px;
  color: #333;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 5px;
  transition: all 0.2s;
}

.date-btn:hover {
  background: #e0e0e0;
  border-color: #999;
}

.date-btn.active {
  background: #007bff;
  color: #fff;
  border-color: #0056b3;
  font-weight: 600;
}

.date-btn.active .date-count {
  background: rgba(255, 255, 255, 0.3);
}

.date-count {
  background: #ddd;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
}

.date-btn.more-dates {
  background: #e9ecef;
  color: #666;
  font-style: italic;
}

.clear-btn {
  padding: 6px 12px;
  background: #6c757d;
  color: #fff;
  border: 1px solid #999;
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
  font-weight: 600;
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
  background: #fff;
  border: 1px solid #ccc;
  padding: 40px;
  text-align: center;
  color: #333;
}

.spinner {
  border: 4px solid #f3f3f3;
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
  color: #c00;
}

/* Table */
.table-container {
  background: #fff;
  border: 1px solid #ccc;
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
  border-bottom: 1px solid #ddd;
  color: #000;
  font-size: 13px;
}

.sessions-table th {
  background: #f0f0f0;
  font-weight: 600;
  color: #333;
}

.sessions-table th.sortable {
  cursor: pointer;
  user-select: none;
}

.sessions-table th.sortable:hover {
  background: #e0e0e0;
}

.sessions-table tbody tr:hover {
  background: #f8f9fa;
}

.config-badge {
  background: #e7f3ff;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 12px;
  font-family: monospace;
}

.pipeline-badge {
  background: #fff3cd;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-family: monospace;
  color: #856404;
}

.mode-badge {
  background: #d1ecf1;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  color: #0c5460;
}

.safety-badge {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.source-badge {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.source-persona {
  background: #e8daef;
  color: #6c3483;
}

.source-compare {
  background: #d4efdf;
  color: #1e8449;
}

.source-default {
  background: #eaecee;
  color: #566573;
}

.safety-kids {
  background: #d4edda;
  color: #155724;
}

.safety-youth {
  background: #fff3cd;
  color: #856404;
}

.safety-adult,
.safety-open {
  background: #f8d7da;
  color: #721c24;
}

.run-id {
  font-family: monospace;
  font-size: 11px;
  background: #f1f3f4;
  padding: 2px 4px;
  border-radius: 2px;
}

.action-btn {
  padding: 4px 10px;
  font-size: 12px;
  border: 1px solid #ccc;
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
  background: #fff;
  border: 1px solid #ccc;
  margin-bottom: 10px;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 15px;
  padding: 15px;
  background: #f8f9fa;
  flex-wrap: wrap;
}

.page-btn {
  padding: 8px 16px;
  background: #fff;
  border: 1px solid #ccc;
  cursor: pointer;
  font-size: 13px;
  color: #000;
  border-radius: 4px;
  font-weight: 500;
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
  background: #fff;
  border: 1px solid #ccc;
  cursor: pointer;
  font-size: 13px;
  color: #000;
  border-radius: 4px;
  min-width: 36px;
  text-align: center;
}

.page-number-btn:hover:not(.active):not(.dots) {
  background: #e0e0e0;
}

.page-number-btn.active {
  background: #007bff;
  color: #fff;
  border-color: #007bff;
  font-weight: 600;
}

.page-number-btn.dots {
  border: none;
  background: transparent;
  cursor: default;
  color: #666;
}

.page-info {
  font-size: 13px;
  color: #666;
  white-space: nowrap;
}

.per-page-select {
  padding: 6px 8px;
  border: 1px solid #ccc;
  font-size: 13px;
  background: #fff;
  color: #000;
  border-radius: 4px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: #fff;
  width: 90%;
  max-width: 1000px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border: 1px solid #ccc;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid #ddd;
  background: #f8f9fa;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  color: #333;
}

.close-btn {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: #666;
  line-height: 1;
  padding: 0;
  width: 30px;
  height: 30px;
}

.close-btn:hover {
  color: #000;
}

.modal-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
  color: #000;
}

.detail-section {
  margin-bottom: 25px;
}

.detail-section h4 {
  margin: 0 0 10px 0;
  font-size: 16px;
  color: #333;
  border-bottom: 2px solid #007bff;
  padding-bottom: 5px;
}

.detail-table {
  width: 100%;
  border-collapse: collapse;
}

.detail-table td {
  padding: 8px 10px;
  border-bottom: 1px solid #eee;
}

.detail-table code {
  background: #f1f3f4;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: monospace;
  font-size: 12px;
}

.entity-item {
  border: 1px solid #ddd;
  margin-bottom: 10px;
  border-radius: 4px;
  overflow: hidden;
}

.entity-header {
  background: #f8f9fa;
  padding: 8px 12px;
  display: flex;
  gap: 15px;
  align-items: center;
  font-size: 12px;
}

.entity-type {
  font-weight: 600;
  color: #007bff;
}

.entity-filename {
  font-family: monospace;
  color: #666;
}

.entity-time {
  color: #999;
  margin-left: auto;
}

.entity-content {
  padding: 12px;
  background: #fff;
  border-top: 1px solid #ddd;
}

.entity-content pre {
  margin: 0;
  font-size: 12px;
  font-family: monospace;
  white-space: pre-wrap;
  word-wrap: break-word;
  color: #333;
}

.entity-image {
  padding: 12px;
  background: #fff;
  border-top: 1px solid #ddd;
  text-align: center;
}

.detail-image {
  max-width: 100%;
  max-height: 600px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

/* Thumbnails */
.thumbnail-container {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.thumbnail {
  max-width: 60px;
  max-height: 60px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #ddd;
}

.no-thumbnail {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f0f0;
  border-radius: 4px;
  border: 1px solid #ddd;
}

.no-thumbnail span {
  font-size: 10px;
  color: #999;
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
  background: #fff;
  border-top: 1px solid #ddd;
  text-align: center;
}

.detail-video {
  max-width: 100%;
  max-height: 600px;
  border: 1px solid #ddd;
  border-radius: 4px;
}
</style>
