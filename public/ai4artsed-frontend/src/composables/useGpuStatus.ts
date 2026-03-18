/**
 * Composable for live GPU/VRAM status.
 *
 * Fetches from the existing /api/settings/backend-status endpoint
 * and normalizes the data for resource-aware UI components.
 */
import { ref, onMounted, onUnmounted } from 'vue'

export interface LoadedModel {
  backend: string
  model: string
  vram_mb: number
  in_use: number
}

export interface ModelCost {
  id: string
  name: string
  description: string
  vram_mb: number
  duration_s: string
  local: boolean
  backend_type: string
  media_type: string
}

export interface GpuStatus {
  gpuName: string
  totalMb: number
  freeMb: number
  allocatedMb: number
  tdpWatts: number
  loadedModels: LoadedModel[]
  modelCosts: ModelCost[]
}

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

      // Extract loaded models from vram_coordinator if available
      const loadedModels: LoadedModel[] = (coordinator.loaded_models || []).map((m: any) => ({
        backend: m.backend || '',
        model: m.model || '',
        vram_mb: m.vram_mb || 0,
        in_use: m.in_use || 0,
      }))

      // Extract model list from output_configs
      // VRAM values are NOT hardcoded — they come from real GPU measurement after loading
      // Descriptions: only factual media type, NO qualitative claims

      const CLOUD_BACKENDS = new Set(['openai', 'google'])

      const modelCosts: ModelCost[] = []
      const byBackend = data.output_configs?.by_backend || {}
      for (const [backend, configs] of Object.entries(byBackend)) {
        for (const cfg of configs as any[]) {
          if (cfg.hidden) continue
          const isCloud = CLOUD_BACKENDS.has(backend)
          modelCosts.push({
            id: cfg.id || '',
            name: cfg.name || cfg.id || '',
            description: '', // No invented descriptions — real info comes from output configs or user
            vram_mb: 0, // Real value comes from GPU measurement after loading
            duration_s: '',
            local: !isCloud,
            backend_type: backend,
            media_type: cfg.media_type || 'unknown',
          })
        }
      }

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
        modelCosts,
      }
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch GPU status'
    } finally {
      loading.value = false
    }
  }

  /** Computed metaphors based on live hardware data */
  function metaphors() {
    if (!status.value) return null
    const watts = status.value.tdpWatts || 600 // fallback
    const totalGb = Math.round(status.value.totalMb / 1024)
    // 1 GB ≈ 500 books (average ebook ~2MB), 1 book ≈ 2.5cm wide
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

  return { status, loading, error, refresh, metaphors }
}
