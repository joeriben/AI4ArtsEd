<template>
  <div class="training-container">
    <h1>LoRA Training Studio</h1>
    <p class="description">
      {{ t('training.info.studioDescription') }}
    </p>

    <!-- Training Info Box -->
    <div class="training-info-box" :class="{ 'expanded': infoExpanded }">
      <div class="info-header" @click="toggleInfo">
        <span class="info-icon"><svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="currentColor"><path d="M440-280h80v-240h-80v240Zm40-320q17 0 28.5-11.5T520-640q0-17-11.5-28.5T480-680q-17 0-28.5 11.5T440-640q0 17 11.5 28.5T480-600Zm0 520q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-320Z"/></svg></span>
        <span class="info-title">{{ t('training.info.title') }}</span>
        <span class="info-toggle">{{ infoExpanded ? t('training.info.showLess') : t('training.info.showMore') }}</span>
      </div>

      <div v-if="infoExpanded" class="info-content">
        <p>{{ t('training.info.description') }}</p>

        <div class="limitations">
          <strong>{{ t('training.info.limitations') }}:</strong>
          <ul>
            <li>{{ t('training.info.limitationDuration') }}</li>
            <li>{{ t('training.info.limitationBlocking') }}</li>
            <li>{{ t('training.info.limitationConfig') }}</li>
          </ul>
        </div>

      </div>
    </div>

    <!-- VRAM Confirmation Dialog -->
    <div v-if="showVramDialog" class="vram-dialog-overlay">
      <div class="vram-dialog">
        <h2>{{ t('training.vram.title') }}</h2>

        <div v-if="vramLoading" class="vram-loading">
          {{ t('training.vram.checking') }}
        </div>

        <div v-else-if="vramInfo" class="vram-info">
          <div class="vram-bar">
            <div
              class="vram-used"
              :style="{ width: vramInfo.usage_percent + '%' }"
              :class="{ 'vram-critical': !vramInfo.can_train }"
            ></div>
          </div>
          <div class="vram-stats">
            <span>{{ vramInfo.used_gb }} GB / {{ vramInfo.total_gb }} GB {{ t('training.vram.used') }}</span>
            <span class="vram-free">{{ vramInfo.free_gb }} GB {{ t('training.vram.free') }}</span>
          </div>

          <div v-if="!vramInfo.can_train" class="vram-warning">
            {{ t('training.vram.notEnough', { gb: vramInfo.min_required_gb }) }}
            <br>
            <strong>{{ t('training.vram.clearQuestion') }}</strong>
          </div>

          <div v-else class="vram-ok">
            {{ t('training.vram.enough') }}
          </div>

          <div v-if="vramClearing" class="vram-clearing">
            {{ t('training.vram.clearing') }}
          </div>

          <div v-if="vramClearResult" class="vram-clear-result">
            <div v-if="vramClearResult.comfyui">ComfyUI: {{ vramClearResult.comfyui }}</div>
            <div v-if="vramClearResult.llm">LLM: {{ vramClearResult.llm }}</div>
            <div v-if="vramClearResult.new_free_gb">{{ t('training.vram.newFree') }}: {{ vramClearResult.new_free_gb }} GB</div>
          </div>
        </div>

        <div class="vram-dialog-buttons">
          <button v-if="!vramInfo?.can_train && !vramClearing" class="clear-btn" @click="clearVram">
            {{ t('training.vram.clearBtn') }}
          </button>
          <button
            v-if="vramInfo?.can_train || vramClearResult"
            class="proceed-btn"
            @click="proceedWithTraining"
            :disabled="vramClearing"
          >
            {{ t('training.buttons.start') }}
          </button>
          <button class="cancel-btn" @click="cancelVramDialog" :disabled="vramClearing">
            {{ t('training.buttons.cancel') }}
          </button>
        </div>
      </div>
    </div>

    <div class="grid-layout">
      <!-- Config Column -->
      <div class="column config-column">
        <label>{{ t('training.labels.projectName') }}</label>
        <input v-model="project_name" :placeholder="t('training.placeholders.projectName')" :disabled="is_training" />

        <label>{{ t('training.labels.triggerWords') }}</label>
        <input v-model="trigger_word" :placeholder="t('training.placeholders.triggerWords')" :disabled="is_training" />
        <small>{{ t('training.labels.triggerHelp') }}</small>

        <label>{{ t('training.labels.images') }}</label>
        <div
          class="drop-zone"
          @dragover.prevent
          @drop.prevent="handleDrop"
          @click="loadFileSelect"
          :class="{ 'has-files': images.length > 0 }"
        >
          <input type="file" ref="fileInput" multiple @change="handleFileSelect" style="display: none" accept="image/*" />
          <div v-if="images.length === 0">
            {{ t('training.labels.dropZone') }}
          </div>
          <div v-else>
            {{ t('training.labels.imagesSelected', { count: images.length }) }}
          </div>
        </div>

        <div class="action-buttons">
          <button
            class="start-btn"
            @click="checkVramAndStart"
            :disabled="is_training || !canStart"
            :class="{ 'is-loading': is_training }"
          >
            {{ is_training ? t('training.buttons.inProgress') : t('training.buttons.start') }}
          </button>

          <button
            v-if="is_training"
            class="stop-btn"
            @click="stopTraining"
          >
            {{ t('training.buttons.stop') }}
          </button>
        </div>

        <!-- GDPR Delete Logic -->
        <button
          v-if="!is_training && project_name && !images.length"
          class="delete-btn"
          @click="deleteProject"
        >
          {{ t('training.buttons.delete') }}
        </button>
      </div>

      <!-- Log Column -->
      <div class="column log-column">
        <label>{{ t('training.labels.logs') }}</label>
        <div class="terminal" ref="logContainer" @scroll="handleScroll">
          <div v-for="(line, index) in logs" :key="index" class="log-line">
            {{ line }}
          </div>
          <div v-if="logs.length === 0" class="log-placeholder">
            {{ t('training.labels.waiting') }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import axios from 'axios';

const { t } = useI18n();

const project_name = ref('');
const trigger_word = ref('');
const images = ref<File[]>([]);
const logs = ref<string[]>([]);
const is_training = ref(false);
const upload_progress = ref(0);
const logContainer = ref<HTMLElement | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
let eventSource: EventSource | null = null;
let userHasScrolledUp = false;

// VRAM Dialog State
interface VramInfo {
  total_gb: number;
  used_gb: number;
  free_gb: number;
  usage_percent: number;
  can_train: boolean;
  min_required_gb: number;
  recommendation: string | null;
}

interface VramClearResult {
  comfyui?: string;
  llm?: string;
  new_free_gb?: number;
  new_used_gb?: number;
  errors?: string[];
}

const showVramDialog = ref(false);
const vramLoading = ref(false);
const vramClearing = ref(false);
const vramInfo = ref<VramInfo | null>(null);
const vramClearResult = ref<VramClearResult | null>(null);

// Info box state - collapsed after first visit
const infoExpanded = ref(!localStorage.getItem('training_info_seen'));

const toggleInfo = () => {
  infoExpanded.value = !infoExpanded.value;
  if (!infoExpanded.value) {
    localStorage.setItem('training_info_seen', 'true');
  }
};

const canStart = computed(() => {
  return project_name.value.length > 3 && images.value.length >= 5;
});

const API_BASE = import.meta.env.DEV ? 'http://localhost:17802' : '';

// Axios instance with long timeout for file uploads (5 minutes)
const uploadClient = axios.create({
  baseURL: API_BASE,
  timeout: 300000, // 5 minutes for large file uploads over WiFi
});

onMounted(() => {
  checkStatus();
});

onUnmounted(() => {
  if (eventSource) eventSource.close();
});

const loadFileSelect = () => {
  fileInput.value?.click();
};

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files) {
    addFiles(Array.from(target.files));
  }
};

const handleDrop = (event: DragEvent) => {
  if (event.dataTransfer?.files) {
    addFiles(Array.from(event.dataTransfer.files));
  }
};

const addFiles = (fileList: File[]) => {
  // Filter only images
  const imageFiles = fileList.filter(f => f.type.startsWith('image/'));
  images.value = [...images.value, ...imageFiles];
};

// ============================================================================
// VRAM MANAGEMENT
// ============================================================================

const checkVramAndStart = async () => {
  if (!canStart.value) return;

  // Reset dialog state
  vramInfo.value = null;
  vramClearResult.value = null;
  vramLoading.value = true;
  showVramDialog.value = true;

  try {
    const response = await uploadClient.get('/api/training/check-vram');
    vramInfo.value = response.data;
  } catch (e: any) {
    console.error("Failed to check VRAM:", e);
    // Proceed anyway if VRAM check fails
    vramInfo.value = {
      total_gb: 0,
      used_gb: 0,
      free_gb: 99,
      usage_percent: 0,
      can_train: true,
      min_required_gb: 20,
      recommendation: null
    };
  } finally {
    vramLoading.value = false;
  }
};

const clearVram = async () => {
  vramClearing.value = true;
  vramClearResult.value = null;

  try {
    const response = await uploadClient.post('/api/training/clear-vram', {
      unload_comfyui: true,
      unload_llm: true
    });

    if (response.data.success) {
      vramClearResult.value = response.data.results;

      // Update vramInfo with new free GB
      if (vramInfo.value && vramClearResult.value?.new_free_gb) {
        vramInfo.value.free_gb = vramClearResult.value.new_free_gb;
        vramInfo.value.used_gb = vramClearResult.value.new_used_gb || vramInfo.value.used_gb;
        vramInfo.value.usage_percent = Math.round((vramInfo.value.used_gb / vramInfo.value.total_gb) * 100);
        vramInfo.value.can_train = vramInfo.value.free_gb >= vramInfo.value.min_required_gb;
      }
    }
  } catch (e: any) {
    console.error("Failed to clear VRAM:", e);
    vramClearResult.value = {
      errors: [e.message || 'Failed to clear VRAM']
    };
  } finally {
    vramClearing.value = false;
  }
};

const proceedWithTraining = () => {
  showVramDialog.value = false;
  startTraining();
};

const cancelVramDialog = () => {
  showVramDialog.value = false;
};

// ============================================================================
// STATUS CHECK
// ============================================================================

const checkStatus = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/training/status`);
    const data = await res.json();
    if (data.is_training) {
      is_training.value = true;
      project_name.value = data.project_name || '';
      connectSSE();
    }
  } catch (e) {
    console.error("Failed to check status", e);
  }
};

const startTraining = async () => {
  if (!canStart.value) return;

  const formData = new FormData();
  formData.append('project_name', project_name.value);
  formData.append('trigger_word', trigger_word.value);
  images.value.forEach(img => {
    formData.append('images', img);
  });

  is_training.value = true;
  upload_progress.value = 0;
  logs.value = ["Initiating upload..."];

  try {
    // Use axios with progress tracking and long timeout for WiFi reliability
    const response = await uploadClient.post('/api/training/start', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          upload_progress.value = percent;
          // Update log with progress
          const lastLog = logs.value[logs.value.length - 1];
          if (lastLog?.startsWith('Upload:')) {
            logs.value[logs.value.length - 1] = `Upload: ${percent}%`;
          } else {
            logs.value.push(`Upload: ${percent}%`);
          }
        }
      }
    });

    if (response.status !== 200) {
      throw new Error(response.data?.message || 'Upload failed');
    }

    logs.value.push("Upload complete. Starting Kohya process...");
    connectSSE();

  } catch (e: any) {
    const errorMsg = e.response?.data?.message || e.message || 'Unknown error';
    logs.value.push(`Error: ${errorMsg}`);
    is_training.value = false;
  }
};

const stopTraining = async () => {
  try {
    await fetch(`${API_BASE}/api/training/stop`, { method: 'POST' });
    logs.value.push("Stop signal sent.");
  } catch (e) {
    console.error(e);
  }
};

const deleteProject = async () => {
  if (!confirm(`Are you sure you want to delete all data for project '${project_name.value}'? This cannot be undone.`)) return;
  
  try {
    const res = await fetch(`${API_BASE}/api/training/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_name: project_name.value })
    });
    
    if (res.ok) {
      alert("Project files deleted.");
      images.value = []; // Clear local
    } else {
      alert("Failed to delete files.");
    }
  } catch (e) {
    console.error(e);
  }
};

const connectSSE = () => {
  if (eventSource) eventSource.close();
  
  console.log("Connecting to Event Stream...");
  eventSource = new EventSource(`${API_BASE}/api/training/events`);
  
  eventSource.onmessage = (e) => {
      // General keepalive or ping
  };

  eventSource.addEventListener('log', (e) => {
    const newLogs = JSON.parse(e.data);
    logs.value.push(...newLogs);
    if (!userHasScrolledUp) {
      scrollToBottom();
    }
  });
  
  eventSource.addEventListener('status', (e) => {
    const status = JSON.parse(e.data);
    is_training.value = status.is_training;
    if (!status.is_training && eventSource) {
      eventSource.close();
      eventSource = null;
    }
  });
  
  eventSource.addEventListener('done', () => {
    eventSource?.close();
    is_training.value = false;
  });

  eventSource.onerror = (err) => {
    console.error("SSE Error (Timeout?):", err);
    eventSource?.close();
    
    // Auto-Reconnect Logic if we think training is still running
    if (is_training.value) {
        setTimeout(() => {
            console.log("Attempting reconnect...");
            connectSSE();
        }, 3000);
    }
  };
};

const scrollToBottom = () => {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight;
    }
  });
};

const handleScroll = () => {
  if (!logContainer.value) return;
  const { scrollTop, scrollHeight, clientHeight } = logContainer.value;
  // If user scrolls up (is not at bottom), stop autoscrolling
  // Tolerance of 50px
  if (scrollTop + clientHeight < scrollHeight - 50) {
    userHasScrolledUp = true;
  } else {
    userHasScrolledUp = false;
  }
};
</script>

<style scoped>
.training-container {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
  color: var(--text-color);
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
}

h1 {
  font-size: 2rem;
  margin-bottom: 0.5rem;
  background: linear-gradient(90deg, #ff00ff, #00ffff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.description {
  margin-bottom: 2rem;
  opacity: 0.8;
}

.grid-layout {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 2rem;
  flex: 1;
  min-height: 0; /* Important for scroll */
}

.column {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

label {
  font-weight: bold;
  margin-bottom: -0.5rem;
}

input {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 0.8rem;
  border-radius: 4px;
  color: white;
  font-size: 1rem;
}

.drop-zone {
  border: 2px dashed rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  padding: 3rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
}

.drop-zone:hover, .drop-zone.has-files {
  border-color: #00ffff;
  background: rgba(0, 255, 255, 0.05);
}

.action-buttons {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

.start-btn {
  flex: 1;
  background: #00ffff;
  color: black;
  border: none;
  padding: 1rem;
  font-weight: bold;
  font-size: 1.1rem;
  cursor: pointer;
  border-radius: 4px;
  transition: transform 0.1s;
}

.start-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.stop-btn {
  flex: 0.3;
  background: #ff0055;
  color: white;
  border: none;
  padding: 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}

.delete-btn {
  margin-top: 2rem;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.6);
  padding: 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.3s;
}

.delete-btn:hover {
  border-color: #ff0055;
  color: #ff0055;
  background: rgba(255, 0, 85, 0.1);
}

.terminal {
  flex: 1;
  background: #0a0a0a;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 4px;
  padding: 1rem;
  font-family: 'Consolas', 'Monaco', monospace;
  overflow-y: auto;
  font-size: 0.85rem;
  line-height: 1.4;
  color: #00ff00; /* Matrix green style for better readability */
  box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
}

/* Custom Scrollbar */
.terminal::-webkit-scrollbar {
  width: 10px;
}

.terminal::-webkit-scrollbar-track {
  background: #1a1a1a;
  border-radius: 4px;
}

.terminal::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 4px;
  border: 2px solid #1a1a1a;
}

.terminal::-webkit-scrollbar-thumb:hover {
  background: #555;
}

.log-line {
  margin-bottom: 2px;
  word-break: break-all;
}

.log-placeholder {
  color: #666;
  font-style: italic;
}

/* VRAM Dialog Styles */
.vram-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.vram-dialog {
  background: #1a1a2e;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 2rem;
  min-width: 400px;
  max-width: 500px;
}

.vram-dialog h2 {
  margin: 0 0 1.5rem 0;
  color: #00ffff;
}

.vram-loading {
  text-align: center;
  padding: 2rem;
  color: #888;
}

.vram-bar {
  height: 24px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.vram-used {
  height: 100%;
  background: linear-gradient(90deg, #00ff88, #00ffff);
  transition: width 0.5s ease;
}

.vram-used.vram-critical {
  background: linear-gradient(90deg, #ff4444, #ff8800);
}

.vram-stats {
  display: flex;
  justify-content: space-between;
  font-size: 0.9rem;
  color: #888;
  margin-bottom: 1rem;
}

.vram-free {
  color: #00ff88;
}

.vram-warning {
  background: rgba(255, 68, 68, 0.1);
  border: 1px solid #ff4444;
  border-radius: 8px;
  padding: 1rem;
  margin: 1rem 0;
  color: #ff8888;
}

.vram-ok {
  background: rgba(0, 255, 136, 0.1);
  border: 1px solid #00ff88;
  border-radius: 8px;
  padding: 1rem;
  margin: 1rem 0;
  color: #00ff88;
}

.vram-clearing {
  text-align: center;
  padding: 1rem;
  color: #ffaa00;
}

.vram-clear-result {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 0.8rem;
  margin: 1rem 0;
  font-size: 0.85rem;
  color: #aaa;
}

.vram-dialog-buttons {
  display: flex;
  gap: 1rem;
  margin-top: 1.5rem;
  justify-content: flex-end;
}

.vram-dialog-buttons button {
  padding: 0.8rem 1.5rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
  transition: all 0.2s;
}

.clear-btn {
  background: #ff8800;
  color: black;
}

.clear-btn:hover {
  background: #ffaa00;
}

.proceed-btn {
  background: #00ffff;
  color: black;
}

.proceed-btn:hover {
  background: #00ff88;
}

.proceed-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cancel-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2) !important;
  color: #888;
}

.cancel-btn:hover {
  border-color: rgba(255, 255, 255, 0.4) !important;
  color: #fff;
}

.cancel-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Training Info Box Styles */
.training-info-box {
  background: rgba(100, 100, 255, 0.08);
  border: 1px solid rgba(100, 100, 255, 0.2);
  border-radius: 12px;
  margin-bottom: 1.5rem;
  overflow: hidden;
  transition: all 0.3s ease;
}

.training-info-box.expanded {
  background: rgba(100, 100, 255, 0.1);
}

.info-header {
  display: flex;
  align-items: center;
  padding: 1rem 1.2rem;
  cursor: pointer;
  transition: background 0.2s;
}

.info-header:hover {
  background: rgba(255, 255, 255, 0.05);
}

.info-icon {
  font-size: 1.2rem;
  margin-right: 0.8rem;
}

.info-title {
  flex: 1;
  font-weight: 600;
  color: #aaccff;
}

.info-toggle {
  font-size: 0.85rem;
  color: #888;
  transition: color 0.2s;
}

.info-header:hover .info-toggle {
  color: #00ffff;
}

.info-content {
  padding: 0 1.2rem 1.2rem 1.2rem;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.info-content p {
  margin: 1rem 0;
  color: #bbb;
  line-height: 1.5;
}

.limitations {
  margin: 1rem 0;
}

.limitations strong {
  color: #ff9966;
}

.limitations ul {
  margin: 0.5rem 0 0 1.5rem;
  padding: 0;
  color: #aaa;
}

.limitations li {
  margin-bottom: 0.4rem;
}
</style>
