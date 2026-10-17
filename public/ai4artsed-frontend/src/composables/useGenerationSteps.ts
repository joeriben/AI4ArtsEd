/**
 * Which denoising step a run is on, read from the GPU service.
 *
 * The service keeps `{step, total_steps, active}` and moves it on every step
 * (`gpu_service/services/diffusers_backend.py`); the DevServer hands it on
 * under `/api/settings/generation-progress`. For the archaeology run the
 * service already converts the number back to the steps that were ASKED FOR -
 * a second-order rule has 2n-1 timesteps for n steps, and raw it would put
 * "49 / 25" in the bar.
 *
 * `useAnimationProgress` reads the same address, but it turns the pair into a
 * percentage for the edutainment animations and hands the raw count to nobody.
 * So this is not a second reader of one number: it is the only one that reads
 * it as a count.
 */
import { ref, watch, onUnmounted, type ComputedRef, type Ref } from 'vue'

/**
 * How often the GPU is asked while a run is out. A step takes a good deal
 * longer than this on every card the platform runs on, so a second is dense
 * enough to show every one of them and quiet enough to be free.
 */
const POLL_MS = 1000

export function useGenerationSteps(isActive: Ref<boolean> | ComputedRef<boolean>) {
  const step = ref(0)
  const totalSteps = ref(0)
  /**
   * The denoising is over and the surface is still working. What is left is the
   * way home: the pictures are assembled into one answer and carried to the
   * browser. Measured 2026-08-25 at 25 steps and 2.5 MB for the finished
   * picture alone - the GPU was done after 13 s, the DevServer 2 s later, and
   * the rest of the wait was the answer travelling.
   */
  const settled = ref(false)
  /**
   * Whether THIS run has been seen at the GPU yet. Until it has, the numbers on
   * the wire still belong to the run before it and are left alone; once it has,
   * they belong to this one even after the service has switched itself off.
   */
  let seen = false
  let timer: number | null = null

  async function poll(): Promise<void> {
    try {
      const res = await fetch('/api/settings/generation-progress')
      if (!res.ok) return
      const d = await res.json()
      if (d.active) {
        seen = true
        step.value = Number(d.step) || 0
        totalSteps.value = Number(d.total_steps) || 0
        return
      }
      if (!seen) return
      // The denoising is over, and the surface is still working: it is decoding
      // and carrying home what the steps produced, which on this instrument is
      // one picture per step and takes about as long again. Measured 2026-08-25
      // at 25 steps: the service reaches 25 and switches off in the same
      // moment, so a poll a second later finds the run gone and the bar would
      // stand at „Schritt 24 / 25" for the whole tail. All the steps exist by
      // then, so that is what the count says.
      const total = Number(d.total_steps) || totalSteps.value
      if (total) {
        totalSteps.value = total
        step.value = total
      }
      settled.value = true
      stop()
    } catch {
      // The readout stays where it was. A missed poll is nothing the visitor
      // has anything to do with, and the run is unaffected by it.
    }
  }

  function stop(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  watch(isActive, on => {
    stop()
    if (!on) return
    // Each run starts its own count: the numbers of the previous one would
    // otherwise stand in the bar for the first second of this one.
    seen = false
    settled.value = false
    step.value = 0
    totalSteps.value = 0
    poll()
    timer = window.setInterval(poll, POLL_MS)
  })

  onUnmounted(stop)

  return { step, totalSteps, settled }
}
