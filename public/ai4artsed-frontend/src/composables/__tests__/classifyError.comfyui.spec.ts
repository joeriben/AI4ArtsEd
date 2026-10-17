/**
 * A refusal from ComfyUI, put in the right drawer.
 *
 * Since 2026-09-07 the submission to ComfyUI carries ComfyUI's own reason
 * instead of a fixed sentence, and that reason names the node and what is
 * wrong with it. Two of its wordings mean the same thing: this installation
 * lacks something.
 *
 *   - a file it was asked for →  "Value not in list (ckpt_name: … not in […])"
 *   - a custom node          →  "Node 'X' not found. The custom node may not
 *                                be installed."
 *
 * `classifyError` documents `missing` as the one class that must never be
 * answered with "try again". The second wording was already covered by
 * `not found`; the first fell to `unknown`, whose answer is exactly that.
 * Pressing again installs nothing.
 *
 * The strings below are ComfyUI's own (`execution.py`, validate_prompt /
 * validate_inputs), read through the platform's reader, not invented here.
 */
import { describe, it, expect } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { classifyError } from '../useGenerationStream'

setActivePinia(createPinia())

// What actually arrives, with the prefixes the run puts in front of it.
const asRun = (reason: string) =>
  `Step step_1_output_image_sd35_large failed: Backend error: ` +
  `Output-Chunk processing error: ComfyUI refused the workflow (HTTP 400): ${reason}`

describe('a refusal from ComfyUI', () => {
  it('reads a missing checkpoint as missing, not as unknown', () => {
    expect(
      classifyError(
        asRun(
          'Prompt outputs failed validation — CheckpointLoaderSimple: Value not in list ' +
            "(ckpt_name: 'sd3.5_large.safetensors' not in ['flux1-dev.safetensors'])",
        ),
      ),
    ).toBe('missing')
  })

  it('reads a missing LoRA as missing', () => {
    expect(
      classifyError(asRun("LoraLoader: Value not in list (lora_name: 'x.safetensors' not in [])")),
    ).toBe('missing')
  })

  it('reads a custom node this installation lacks as missing', () => {
    expect(
      classifyError(
        asRun("Node 'LatentSubtract' not found. The custom node may not be installed. — Node ID '#7'"),
      ),
    ).toBe('missing')
  })

  it('leaves a ComfyUI that is simply not answering as offline', () => {
    expect(
      classifyError(
        'ComfyUI could not be reached (no answer): ClientConnectorError: Connection refused',
      ),
    ).toBe('offline')
  })

  it('reads the submission own wording for an absent ComfyUI, not just the socket error', () => {
    // aiohttp does not always say "connection refused"; on a host that is up
    // but has nothing on the port it says "Cannot connect to host". Without
    // either wording this landed in `unknown`, whose answer is "try again" —
    // which is the right answer here, but for a reason nobody could see.
    expect(
      classifyError(
        'ComfyUI could not be reached (no answer): ' +
          'ClientConnectorError: Cannot connect to host 127.0.0.1:17804 ssl:default',
      ),
    ).toBe('offline')
    expect(classifyError('ComfyUI could not be reached (no answer): TimeoutError: ')).toBe(
      'offline',
    )
  })

  it('leaves a busy card as busy', () => {
    expect(classifyError('queue full — 10 waiting')).toBe('busy')
  })
})
