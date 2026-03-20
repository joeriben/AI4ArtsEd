/**
 * Composable for workshop resource planning.
 *
 * Provides:
 * - Live GPU status (polling /api/settings/backend-status)
 * - Physical model definitions with measured VRAM values
 */
import { ref, onMounted, onUnmounted } from 'vue'

export interface LoadedModel {
  backend: string
  model: string
  vram_mb: number
  in_use: number
}

export interface GpuStatus {
  gpuName: string
  totalMb: number
  freeMb: number
  allocatedMb: number
  tdpWatts: number
  loadedModels: LoadedModel[]
}

export interface PhysicalModel {
  id: string
  name: string
  media_type: 'image' | 'video' | 'music' | 'sound' | '3d'
  vram_gb: number
  gen_time: string
  local: boolean
  publisher: string
  cloud_region: 'US' | 'EU' | null
  /** true if the model can be preloaded via /api/settings/workshop/preload */
  preloadable: boolean
  /** ID of another model that shares VRAM components (e.g. shared CLIP/VAE) */
  shared_with?: string
  /** GB of VRAM shared with shared_with model (don't double-count in bar) */
  shared_vram_gb?: number
  /** Short note shown on the card (e.g. "text-to-image + image-to-image") */
  note?: string
}

/**
 * Real VRAM measurements — Session 268 (2026-03-18).
 * RTX PRO 6000 Blackwell 96 GB, nvidia-smi peak monitoring.
 * ComfyUI models measured through actual ComfyUI workflows.
 * Diffusers models measured through GPU service.
 * Safety models measured via Ollama.
 */
export const PHYSICAL_MODELS: PhysicalModel[] = [
  // --- Bilder ---
  {
    id: 'sd35_large',
    name: 'Stable Diffusion 3.5 Large',
    media_type: 'image',
    vram_gb: 30,
    gen_time: '',
    local: true,
    publisher: 'Stability AI',
    cloud_region: null,
    preloadable: true,
    note: 'text-to-image',
  },
  {
    id: 'flux2',
    name: 'FLUX.2',
    media_type: 'image',
    vram_gb: 53,
    gen_time: '',
    local: true,
    publisher: 'Black Forest Labs',
    cloud_region: null,
    preloadable: true,
    note: 'text-to-image + image-to-image',
  },
  {
    id: 'qwen_t2i',
    name: 'Qwen Image',
    media_type: 'image',
    vram_gb: 20,
    gen_time: '',
    local: true,
    publisher: 'Alibaba / Qwen',
    cloud_region: null,
    preloadable: true,
    note: 'text-to-image',
  },
  {
    id: 'qwen_i2i',
    name: 'Qwen Image',
    media_type: 'image',
    vram_gb: 20,
    gen_time: '',
    local: true,
    publisher: 'Alibaba / Qwen',
    cloud_region: null,
    preloadable: true,
    note: 'image editing',
  },
  {
    id: 'qwen_multi',
    name: 'Qwen Image',
    media_type: 'image',
    vram_gb: 20,
    gen_time: '',
    local: true,
    publisher: 'Alibaba / Qwen',
    cloud_region: null,
    preloadable: true,
    note: 'multi-image fusion',
  },
  // --- Videos ---
  {
    id: 'wan22_t2v',
    name: 'Wan 2.2',
    media_type: 'video',
    vram_gb: 38,
    gen_time: '',
    local: true,
    publisher: 'Wan-AI / Alibaba',
    cloud_region: null,
    preloadable: true,
    note: 'text-to-video',
  },
  {
    id: 'wan22_i2v',
    name: 'Wan 2.2',
    media_type: 'video',
    vram_gb: 38,
    gen_time: '',
    local: true,
    publisher: 'Wan-AI / Alibaba',
    cloud_region: null,
    preloadable: true,
    shared_with: 'wan22_t2v',
    shared_vram_gb: 10,
    note: 'image-to-video',
  },
  {
    id: 'ltx_video',
    name: 'LTX Video',
    media_type: 'video',
    vram_gb: 24,
    gen_time: '',
    local: true,
    publisher: 'Lightricks',
    cloud_region: null,
    preloadable: true,
    note: 'text-to-video',
  },
  // --- Musik ---
  {
    id: 'heartmula',
    name: 'HeartMuLa',
    media_type: 'music',
    vram_gb: 12,
    gen_time: '',
    local: true,
    publisher: 'HeartMuLa Research',
    cloud_region: null,
    preloadable: true,
    note: 'lyrics + tags',
  },
  {
    id: 'acestep',
    name: 'ACE-Step',
    media_type: 'music',
    vram_gb: 8,
    gen_time: '',
    local: true,
    publisher: 'StepFun / ACE Studio',
    cloud_region: null,
    preloadable: true,
    note: 'lyrics + tags',
  },
  // --- Klaenge ---
  {
    id: 'stable_audio',
    name: 'Stable Audio',
    media_type: 'sound',
    vram_gb: 6,
    gen_time: '',
    local: true,
    publisher: 'Stability AI',
    cloud_region: null,
    preloadable: true,
    note: 'text-to-sound',
  },
  // --- Cloud (Mammouth AI — EU, DSGVO) ---
  {
    id: 'gemini_3_pro',
    name: 'Gemini 3 Pro',
    media_type: 'image',
    vram_gb: 0,
    gen_time: '',
    local: false,
    publisher: 'Google via Mammouth AI',
    cloud_region: 'EU',
    preloadable: false,
    note: 'text-to-image',
  },
]

/**
 * Measured safety model VRAM — Session 268 (2026-03-18), nvidia-smi peak.
 * These are ALWAYS loaded via Ollama when the platform runs.
 */
export const SAFETY_MODELS = [
  { name: 'Llama Guard', vram_gb: 1.6 },
  { name: 'Safety LLM', vram_gb: 1.4 },
  { name: 'Safety VLM', vram_gb: 1.9 },
] as const

/** ComfyUI baseline overhead (~600 MB measured, always present when ComfyUI runs) */
export const COMFYUI_OVERHEAD_GB = 0.6

/** Total safety baseline = safety models + ComfyUI overhead + CUDA caches (~2.5 GB) */
export const SAFETY_VRAM_GB = Math.ceil(
  SAFETY_MODELS.reduce((sum, m) => sum + m.vram_gb, 0) + COMFYUI_OVERHEAD_GB + 2.5
)

const POLL_INTERVAL = 30_000

export function useGpuStatus() {
  const status = ref<GpuStatus | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let timer: ReturnType<typeof setInterval> | null = null

  function getBaseUrl(): string {
    return import.meta.env.DEV ? 'http://localhost:17802' : ''
  }

  async function refresh() {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`${getBaseUrl()}/api/settings/backend-status`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()

      const infra = data.local_infrastructure || {}
      const hw = infra.gpu_hardware || {}
      const gpuService = infra.gpu_service || {}
      const gpuInfo = gpuService.gpu_info || {}
      const coordinator = gpuService.vram_coordinator || {}

      const loadedModels: LoadedModel[] = (coordinator.loaded_models || []).map((m: any) => ({
        backend: m.backend || '',
        model: m.model || '',
        vram_mb: m.vram_mb || 0,
        in_use: m.in_use || 0,
      }))

      const totalMb = Math.round((gpuInfo.total_vram_gb || hw.vram_gb || 0) * 1024)
      const allocatedMb = Math.round((gpuInfo.allocated_gb || 0) * 1024)
      const freeMb = Math.round((gpuInfo.free_gb || 0) * 1024)

      status.value = {
        gpuName: gpuInfo.gpu_name || hw.gpu_name || 'Unknown GPU',
        totalMb,
        freeMb,
        allocatedMb,
        tdpWatts: hw.tdp_watts || 0,
        loadedModels,
      }
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch GPU status'
    } finally {
      loading.value = false
    }
  }

  function metaphors() {
    if (!status.value) return null
    const watts = status.value.tdpWatts || 600
    const totalGb = Math.round(status.value.totalMb / 1024)
    const booksCount = totalGb * 500
    const booksMeters = Math.round(booksCount * 0.025)
    return {
      freezers: Math.round(watts / 150 * 10) / 10,
      phoneFlashlights: watts,
      cyclists: Math.round(watts / 200 * 10) / 10,
      booksCount,
      booksMeters,
      totalGb,
    }
  }

  onMounted(() => {
    refresh()
    timer = setInterval(refresh, POLL_INTERVAL)
  })

  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })

  return { status, loading, error, refresh, metaphors, physicalModels: PHYSICAL_MODELS }
}
