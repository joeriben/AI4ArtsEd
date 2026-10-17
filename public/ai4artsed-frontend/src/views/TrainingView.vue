<template>
  <div class="lab-page">
    <!-- The trigger, in the middle of the shell bar, where every instrument of
         this lab carries it. It stood as a button in the preparing column until
         2026-09-09 and the bar stood empty on this one surface. What it opens
         is still the VRAM check; the run itself starts from that dialog.

         No counter beside it: the status event of the training stream carries
         `is_training` and `error` and no number (devserver/my_app/routes/
         training_routes.py), so there is nothing to count and the line stays
         away (components/ShellRun.vue). The protocol says how far a run has
         come. `/api/training/status` DOES carry `current_step` / `total_steps`;
         putting them in the stream would give the bar a readout. -->
    <ShellRun
      :ready="canStart && !is_training"
      :running="is_training"
      :title="is_training ? t('training.buttons.inProgress') : t('training.buttons.start')"
      @run="checkVramAndStart"
    />

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

          <div v-if="energyEstimate" class="run-cost-line">
            {{ t('training.vram.runCost', energyParams) }}
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

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded: columnFolded }">
          <!-- What prepares a run, in the shape the Latent Lab gives that
               column (assets/flow-stage.css): the handle that folds it away,
               the controls under it, and the note box at its foot. -->
          <section class="lab-prep col-fold-host" :class="{ folded: columnFolded }">
            <!-- Folded away, this column keeps the handle and hides every other
                 child of it — the stop among them, which is the only way to
                 break a run off. So the column stands for the length of a run
                 and the handle says so; what was folded before it started folds
                 back when it ends. -->
            <ColumnFold v-model:folded="folded" :disabled="is_training" />

            <label class="lab-pick-label">{{ t('training.labels.projectName') }}</label>
            <input class="setting-input" v-model="project_name" :placeholder="t('training.placeholders.projectName')" data-example="no" :disabled="is_training" />

            <label class="lab-pick-label">{{ t('training.labels.triggerWords') }}</label>
            <input class="setting-input" v-model="trigger_word" :placeholder="t('training.placeholders.triggerWords')" data-example="no" :disabled="is_training" />
            <p class="lab-hint">{{ t('training.labels.triggerHelp') }}</p>

            <label class="lab-pick-label">{{ t('training.labels.images') }}</label>
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

            <!-- What a model wrote about each image, before anything is trained
                 on it. Editable, because what stands here is what goes in. -->
            <div v-if="captionItems.length" class="captions">
              <div class="captions-strip">
                <div v-for="(item, i) in captionItems" :key="item.file" class="caption-card">
                  <img v-if="thumbUrls[i]" :src="thumbUrls[i]" class="caption-thumb" alt="" />
                  <div v-else class="caption-thumb caption-thumb-empty"></div>
                  <textarea
                    v-model="captionItems[i]!.caption"
                    class="caption-text"
                    :class="{ 'caption-pending': item.caption === null && !item.failed }"
                    :placeholder="item.failed ? t('training.captions.failed') : t('training.captions.waiting')"
                    :disabled="is_training"
                  ></textarea>
                </div>
              </div>
              <div class="captions-foot">
                <span>{{ describing ? t('training.captions.running', { done: describedCount, total: captionItems.length }) : t('training.captions.hint') }}</span>
                <button class="captions-redo" :disabled="describing || is_training" @click="redescribeAll">
                  {{ t('training.captions.redoAll') }}
                </button>
              </div>
            </div>

            <!-- Only the stop stands here. The triangle in the bar starts a run
                 and ShellRun knows no way to break one off, so the one control
                 that has to reach a run while it is out keeps its place in the
                 column — and holds the column open, see the handle above. -->
            <button
              v-if="is_training"
              class="stop-btn"
              @click="stopTraining"
            >
              {{ t('training.buttons.stop') }}
            </button>

            <!-- GDPR Delete Logic -->
            <button
              v-if="!is_training && project_name && !images.length"
              class="delete-btn"
              @click="deleteProject"
            >
              {{ t('training.buttons.delete') }}
            </button>

            <!-- The platform's note box at the foot of the preparing column.
                 It carries what a run here is FIXED to — the eight values read
                 out of the configuration a run gets, never typed here — and
                 what that run costs. Both once stood in the about box at the
                 head of the page; that field is gone and both stand in the
                 explanation box at the foot of the column. What that box
                 said about duration and about blocking other runs is in Help. -->
            <aside class="lab-note">
              <h3>{{ t('latentLab.loraLab.tabs.lora.label') }}</h3>

              <div v-if="setup" class="setup">
                <div class="setup-cap">{{ t('training.info.setupTitle') }}</div>
                <div class="setup-grid">
                  <div v-for="row in setupRows" :key="row.label" class="setup-cell">
                    <span class="setup-label">{{ row.label }}</span>
                    <span class="setup-value">{{ row.value }}</span>
                  </div>
                </div>
              </div>

              <div v-if="energyEstimate" class="run-cost">
                <div class="setup-cap">{{ t('training.info.runCostTitle') }}</div>
                <p>{{ t('training.info.runCost', energyParams) }}</p>
              </div>
            </aside>
          </section>

          <!-- The protocol of the run, on the result side of the stage. It
               carries no heading of its own: the shell bar names the surface,
               and the placeholder in the frame says what is being waited for. -->
          <section class="lab-plot">
            <div class="terminal" ref="logContainer" @scroll="handleScroll">
              <div v-for="(line, index) in logs" :key="index" class="log-line">
                {{ line }}
              </div>
              <div v-if="logs.length === 0" class="log-placeholder">
                {{ t('training.labels.waiting') }}
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import axios from 'axios';
import { usePageContextStore } from '@/stores/pageContext';
import { useLabAuthStore } from '@/stores/labAuth';
import type { PageContext } from '@/composables/usePageContext';
import ColumnFold from '@/components/ColumnFold.vue';
import ShellRun from '@/components/ShellRun.vue';
import { apiBase } from '@/services/labApi'

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

// The preparing column folded away, so the protocol has the whole stage.
// `folded` is what was asked for and stays asked for; `columnFolded` is what
// the surface does with it. A run out means the column stands, because the
// stop is in it and the fold hides everything but its own handle.
const folded = ref(false);
const columnFolded = computed(() => folded.value && !is_training.value);

const pageContextStore = usePageContextStore();
const labAuth = useLabAuthStore();

// Same as the start page: the handbook entry needs the page to name itself.
const pageContext = computed<PageContext>(() => ({
  activeViewType: 'TrainingView',
  pageDescription:
    'LoRA Training Studio unter /training. Hier wird ein eigener ' +
    'LoRA-Adapter trainiert, damit ein Modell einen neuen visuellen ' +
    'Begriff lernt: Bilder hochladen, ein Auslösewort setzen, Lauf ' +
    'starten, Protokoll mitlesen. Die Seite prüft vor dem Lauf den freien ' +
    'VRAM. Der Kasten am Fuß der linken Spalte nennt, worauf ein Lauf ' +
    'festgelegt ist, und was er kostet.',
  pageContent: {
    inputText: project_name.value,
  },
}));

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx);
}, { immediate: true });

onUnmounted(() => {
  pageContextStore.clearContext();
});

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

// What a run costs, read before anybody starts one. Null when the card's
// power limit is unreadable - the page then says nothing rather than an
// invented number.
interface EnergyEstimate {
  watts: number;
  hours_min: number;
  hours_max: number;
  kwh_min: number;
  kwh_max: number;
  co2_g_min: number;
  co2_g_max: number;
  tree_days_min: number;
  tree_days_max: number;
  co2_factor: number;
}

const energyEstimate = ref<EnergyEstimate | null>(null);

// What a run will be. Read out of the configuration a run gets, never typed
// here - a value written twice is a value that drifts.
interface TrainingSetup {
  repeats: number;
  epochs: number;
  save_every_n_epochs: number;
  learning_rate: number;
  lr_scheduler: string;
  optimizer: string;
  network_dim: number;
  network_alpha: number;
  train_text_encoder: boolean;
  resolution: string;
  bucket_min: number;
  bucket_max: number;
  batch_size: number;
}

const setup = ref<TrainingSetup | null>(null);

const setupRows = computed<Array<{ label: string; value: string }>>(() => {
  const s = setup.value;
  if (!s) return [];
  return [
    { label: t('training.info.setupRepeats'), value: `${s.repeats} × ${s.epochs}` },
    { label: t('training.info.setupRank'), value: `${s.network_dim} / ${s.network_alpha}` },
    { label: t('training.info.setupLearningRate'), value: `${s.learning_rate}, ${s.lr_scheduler}` },
    { label: t('training.info.setupOptimizer'), value: s.optimizer },
    { label: t('training.info.setupResolution'), value: `${s.resolution.replace(',', '×')}, ${s.bucket_min}–${s.bucket_max}` },
    { label: t('training.info.setupTextEncoder'), value: s.train_text_encoder ? t('training.info.setupTextEncoderOn') : t('training.info.setupTextEncoderOff') },
    { label: t('training.info.setupBatch'), value: String(s.batch_size) },
    { label: t('training.info.setupCheckpoints'), value: t('training.info.setupCheckpointsEvery', { n: s.save_every_n_epochs }) },
  ];
});

const noParams: Record<string, number> = {};

const energyParams = computed<Record<string, number>>(() => {
  const e = energyEstimate.value;
  if (!e) return noParams;
  return {
    hoursMin: e.hours_min,
    hoursMax: e.hours_max,
    watts: e.watts,
    kwhMin: e.kwh_min,
    kwhMax: e.kwh_max,
    co2Min: e.co2_g_min,
    co2Max: e.co2_g_max,
    treeMin: e.tree_days_min,
    treeMax: e.tree_days_max,
    factor: e.co2_factor,
  };
});

const canStart = computed(() => {
  return project_name.value.length > 3 && images.value.length >= 5;
});

const API_BASE = apiBase();

// Axios instance with long timeout for file uploads (5 minutes)
const uploadClient = axios.create({
  baseURL: API_BASE,
  timeout: 300000, // 5 minutes for large file uploads over WiFi
});

onMounted(() => {
  checkStatus();
  loadEnergyEstimate();
  loadSetup();
});

onUnmounted(() => {
  if (eventSource) eventSource.close();
  stopDescribePoll();
  releaseThumbs();
});

// What a model wrote about each dropped image. The order is the order they
// were staged in, which is the order they were added in - the thumbnails
// beside them come from the local files and ride on the same index.
interface CaptionItem {
  file: string;
  caption: string | null;
  failed: boolean;
}

const stagingToken = ref<string | null>(null);
const captionItems = ref<CaptionItem[]>([]);
const thumbUrls = ref<string[]>([]);
const describing = ref(false);
let describePoll: ReturnType<typeof setTimeout> | null = null;

const describedCount = computed(
  () => captionItems.value.filter(i => i.caption !== null || i.failed).length,
);

const releaseThumbs = () => {
  thumbUrls.value.forEach(url => URL.revokeObjectURL(url));
  thumbUrls.value = [];
};

const stopDescribePoll = () => {
  if (describePoll !== null) {
    clearTimeout(describePoll);
    describePoll = null;
  }
};

/** Send images off to be described. Without `token` a fresh set is staged. */
const describeFiles = async (files: File[], token: string | null) => {
  if (!files.length) return;
  const form = new FormData();
  files.forEach(f => form.append('images', f));
  if (token) form.append('token', token);

  describing.value = true;
  try {
    const res = await uploadClient.post('/api/training/describe', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    stagingToken.value = res.data?.token ?? null;
    captionItems.value = res.data?.items ?? [];
    pollDescription();
  } catch {
    // Nothing was staged, so nothing is claimed: the strip stays away and the
    // training thread describes the images itself, as it did before.
    describing.value = false;
    stagingToken.value = null;
    captionItems.value = [];
    releaseThumbs();
  }
};

const pollDescription = () => {
  stopDescribePoll();
  const token = stagingToken.value;
  if (!token) return;
  describePoll = setTimeout(async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/training/describe/${token}`);
      const items: CaptionItem[] = res.data?.items ?? [];
      // Keep hand-corrected text: only fill in what is still unanswered.
      items.forEach((incoming, i) => {
        const held = captionItems.value[i];
        if (!held) captionItems.value[i] = incoming;
        else if (held.caption === null) {
          held.caption = incoming.caption;
          held.failed = incoming.failed;
        }
      });
      if (res.data?.running) pollDescription();
      else describing.value = false;
    } catch {
      describing.value = false;
    }
  }, 1500);
};

const redescribeAll = () => {
  stopDescribePoll();
  stagingToken.value = null;
  captionItems.value = [];
  describeFiles(images.value, null);
};

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
  if (!imageFiles.length) return;
  images.value = [...images.value, ...imageFiles];
  thumbUrls.value = [...thumbUrls.value, ...imageFiles.map(f => URL.createObjectURL(f))];
  // Only the new ones go to the card; a second handful must not cost the
  // first handful's minutes again.
  describeFiles(imageFiles, stagingToken.value);
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
      errors: [e.message || t('training.clearVramFailed')]
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

const loadSetup = async () => {
  try {
    const response = await axios.get(`${API_BASE}/api/training/setup`);
    setup.value = response.data?.setup ?? null;
  } catch {
    setup.value = null;
  }
};

const loadEnergyEstimate = async () => {
  try {
    const response = await axios.get(`${API_BASE}/api/training/energy-estimate`);
    energyEstimate.value = response.data?.estimate ?? null;
  } catch {
    energyEstimate.value = null;
  }
};

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

  stopDescribePoll();
  const formData = new FormData();
  formData.append('project_name', project_name.value);
  formData.append('trigger_word', trigger_word.value);
  // The course this training is released to (the LoRA register, issue #70).
  // A participant's course is fixed on the server; an educator leads several,
  // and the one this client is in is the one the row is written for.
  if (labAuth.activeCourseId != null) formData.append('course_id', String(labAuth.activeCourseId));
  if (stagingToken.value) {
    // Already uploaded when they were described. What goes with the request
    // are the sentences as they now stand.
    formData.append('staging_token', stagingToken.value);
    formData.append('captions', JSON.stringify(captionItems.value.map(i => i.caption ?? '')));
  } else {
    images.value.forEach(img => {
      formData.append('images', img);
    });
  }

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
      throw new Error(response.data?.error || 'Upload failed');
    }

    logs.value.push("Upload complete. Starting Kohya process...");
    connectSSE();

  } catch (e: any) {
    const errorMsg = e.response?.data?.error || e.message || t('generationError.unknown');
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
      alert(t('training.filesDeleted'));
      images.value = []; // Clear local
      stagingToken.value = null;
      captionItems.value = [];
      releaseThumbs();
    } else {
      alert(t('training.deleteFailed'));
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
/* The note box holds two blocks on this surface, and the cost of a run is a
   paragraph of 530 characters — four lines in the wide box at the head of the
   page it came from, nine in a column of 277 px. At its own height the box
   stands 459 px against 643 px of column (measured 1210 x 834), which is
   taller than everything it explains.

   So it takes the room the column has left and scrolls in itself, which is the
   registry's answer for a box its column cannot carry (`Erklaerkasten am
   Spaltenfuss`, Denoising Archaeology, 2026-08-31). The registry adds that this
   holds for a column which does NOT scroll - two scrollers inside one another
   are worse - and everything above the box in this column has a fixed height,
   so the floor alone decides from which window height on the column scrolls
   too. At 10 rem the whole column stands on one screen down to 1024 x 768,
   before any image is dropped, and the box is the only thing that scrolls. A
   floor of 14 rem, which would show both of the box's headings at once, makes
   1024 x 768 scroll the column by 57 px. Under 768 px of window the box stops
   giving way and the column takes over, which is the right order once the room
   is really gone. The registry's other answer, shortening the text, is not
   available here: SUPPLIED WORDING, down to the question about the trees.

   `0 1 auto` and not Denoising Archaeology's `1 1 auto`: this box has a
   natural height worth keeping. Where a window is tall enough it stands at its
   459 px and scrolls nowhere, rather than growing into empty room.
   `overflow-y` is what lets it give way at all - it makes the automatic
   minimum size of a flex item 0, and without it the box would push the column
   instead of yielding to it. */
.lab-note {
  flex: 0 1 auto;
  min-height: 10rem;
  overflow-y: auto;
}

/* The page frame, the stage, the two columns and the handle that folds the
   left one are the lab's own and stand in assets/flow-stage.css. What was here
   until 2026-09-09 - a centred 1400 px box with a 2 rem margin, a 1fr/2fr grid
   with a 2 rem gap, and bare `label` and `input` rules - was this one surface's
   second implementation of them (docs/ELEMENT_STRUCTURE_REGISTRY.md). Only
   what this surface has and no other one does stays below.

   The caption strip's own width no longer needs holding off: `.lab-work > *`
   gives both children `min-width: 0`, which is what the removed `.column`
   rule was for. */

.drop-zone {
  border: 2px dashed rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  padding: 3rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
}

.drop-zone:hover, .drop-zone.has-files {
  border-color: #667eea;
  background: rgba(102, 126, 234, 0.06);
}

/* What a model wrote about each image, before it is trained on. The strip
   scrolls in itself: at 10 to 50 images a wrapping grid would push the start
   button off the page. */
.captions {
  margin-top: 1rem;
}

.captions-strip {
  display: flex;
  gap: 0.6rem;
  overflow-x: auto;
  padding-bottom: 0.6rem;
  scrollbar-width: thin;
  scrollbar-color: var(--surface-4) var(--surface-2);
}

.captions-strip::-webkit-scrollbar {
  height: 9px;
}

.captions-strip::-webkit-scrollbar-track {
  background: var(--surface-2);
  border-radius: 4px;
}

.captions-strip::-webkit-scrollbar-thumb {
  background: var(--surface-4);
  border-radius: 4px;
}

.caption-card {
  flex: 0 0 205px;
  background: var(--surface-2);
  border: 1px solid var(--surface-4);
  border-radius: 6px;
  overflow: hidden;
}

.caption-thumb {
  display: block;
  width: 100%;
  height: 76px;
  object-fit: cover;
}

.caption-thumb-empty {
  background: var(--surface-3);
}

.caption-text {
  display: block;
  width: 100%;
  height: 84px;
  resize: vertical;
  border: none;
  border-top: 1px solid var(--surface-4);
  background: transparent;
  color: rgba(255, 255, 255, 0.72);
  font: inherit;
  font-size: 0.72rem;
  line-height: 1.35;
  padding: 0.45rem 0.5rem;
}

.caption-text:focus {
  outline: none;
  background: rgba(102, 126, 234, 0.06);
}

.caption-pending {
  color: rgba(255, 255, 255, 0.35);
}

.captions-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.45);
}

.captions-redo {
  background: none;
  border: none;
  padding: 0;
  color: #667eea;
  font: inherit;
  font-size: 0.72rem;
  cursor: pointer;
}

.captions-redo:disabled {
  opacity: 0.45;
  cursor: default;
}

/* It stood in a row beside the start button and took a share of that row's
   width. Alone in the column it takes the column, and `flex` here would have
   meant its HEIGHT. Its own top margin went with the row: the column's 10 px
   gap is the distance now, and a margin on top of that only made the two
   buttons in this column read as an ordered pair. What the delete button keeps
   is a distance of its own, because it destroys something. */
.stop-btn {
  background: #ff6b6b;
  color: white;
  border: none;
  padding: 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 700;
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
  border-color: #ff6b6b;
  color: #ff6b6b;
  background: rgba(255, 107, 107, 0.1);
}

.terminal {
  flex: 1;
  background: var(--bg-base);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 4px;
  padding: 1rem;
  font-family: 'Consolas', 'Monaco', monospace;
  overflow-y: auto;
  font-size: 0.85rem;
  line-height: 1.4;
  color: rgba(150, 220, 160, 0.92);
  box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
}

/* Custom Scrollbar */
.terminal::-webkit-scrollbar {
  width: 10px;
}

.terminal::-webkit-scrollbar-track {
  background: var(--surface-2);
  border-radius: 4px;
}

.terminal::-webkit-scrollbar-thumb {
  background: var(--surface-4);
  border-radius: 4px;
  border: 2px solid var(--surface-2);
}

.terminal::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.28);
}

.log-line {
  margin-bottom: 2px;
  word-break: break-all;
}

.log-placeholder {
  color: rgba(255, 255, 255, 0.4);
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
  background: var(--surface-2);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 2rem;
  min-width: 400px;
  max-width: 500px;
}

.vram-dialog h2 {
  margin: 0 0 1.5rem 0;
  color: #667eea;
}

.vram-loading {
  text-align: center;
  padding: 2rem;
  color: rgba(255, 255, 255, 0.55);
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
  background: linear-gradient(90deg, #667eea, #8b9dff);
  transition: width 0.5s ease;
}

.vram-used.vram-critical {
  background: linear-gradient(90deg, #ff6b6b, #ff9800);
}

.vram-stats {
  display: flex;
  justify-content: space-between;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.55);
  margin-bottom: 1rem;
}

.vram-free {
  color: #4CAF50;
}

.vram-warning {
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid #ff6b6b;
  border-radius: 8px;
  padding: 1rem;
  margin: 1rem 0;
  color: #ffb3b3;
}

.vram-ok {
  background: rgba(76, 175, 80, 0.12);
  border: 1px solid #4CAF50;
  border-radius: 8px;
  padding: 1rem;
  margin: 1rem 0;
  color: #7bc97f;
}

.vram-clearing {
  text-align: center;
  padding: 1rem;
  color: #ff9800;
}

.vram-clear-result {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 0.8rem;
  margin: 1rem 0;
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.65);
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
  font-weight: 700;
  transition: all 0.2s;
}

.clear-btn {
  background: #ff9800;
  color: #14141a;
}

.clear-btn:hover {
  background: #ffa726;
}

.proceed-btn {
  background: #667eea;
  color: #ffffff;
}

.proceed-btn:hover {
  background: #7b8cf0;
}

.proceed-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cancel-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2) !important;
  color: rgba(255, 255, 255, 0.55);
}

.cancel-btn:hover {
  border-color: rgba(255, 255, 255, 0.4) !important;
  color: #fff;
}

.cancel-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* The two blocks of the note box. They stood in the about box at the head of
   the page and carried its grammar - a rule above them and an upper-case
   caption; in the note they carry the note's, which is a quiet line over what
   it names. */
.setup {
  margin-top: 8px;
}

.setup-cap {
  color: rgba(255, 255, 255, 0.55);
  font-size: var(--flow-fs-hint);
  margin-bottom: 4px;
}

/* The floor is `min(260px, 100%)`, not 260px. The bare number was written for
   the full-width box at the head of the page; in the note at the foot of the
   preparing column the content box is 277 px at the reference 1210 x 834 and
   262 px once the column carries a classic scrollbar, so a 260 px track had
   two pixels of slack and overflowed its own bordered box below a 1204 px
   window. With `min()` the row simply stops splitting where there is no room
   for two, and it still splits on a wide window. */
.setup-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr));
  gap: 0.3rem 1.6rem;
}

.setup-cell {
  display: flex;
  gap: 0.4rem;
  font-size: 0.72rem;
}

.setup-label {
  color: rgba(255, 255, 255, 0.55);
}

.setup-value {
  color: rgba(255, 255, 255, 0.8);
}

.run-cost {
  margin-top: 10px;
}

.run-cost-line {
  margin: 1rem 0 0 0;
  color: rgba(255, 255, 255, 0.65);
  line-height: 1.5;
}
</style>
