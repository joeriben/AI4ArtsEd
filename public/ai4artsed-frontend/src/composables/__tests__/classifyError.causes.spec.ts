/**
 * Two causes a language model comparison ended on without naming them
 * (platform test 2026-09-27): both came out as "Something went wrong".
 *
 *   - a cloud provider refusing for the moment → the streaming client's
 *     "API Error: 429"
 *   - the repetition guard stopping a local model → "finish_reason=repetition"
 *
 * The strings are the ones the backend logged for those runs, shortened and
 * with the model names replaced, behind the prefixes the pipeline executor
 * puts in front of them (schemas/engine/pipeline_executor.py, "Step … failed:"
 * and "Backend error:").
 */
import { describe, it, expect } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { classifyError, failureKey } from '../useGenerationStream'

setActivePinia(createPinia())

const RATE_LIMITED =
  'Step step_1_manipulate failed: Backend error: API Error: 429\n' +
  '{"error":{"message":"litellm.RateLimitError: RateLimitError: OpenrouterException - ' +
  '{\\"error\\":{\\"message\\":\\"Provider returned error\\",\\"code\\":429,\\"metadata\\":' +
  '{\\"raw\\":\\"a-provider/a-model is temporarily rate-limited upstream. ' +
  'Please retry shortly\\"}}}","type":"throttling_error","param":null,"code":"429"}}'

const REPEATED =
  'Step step_1_manipulate failed: Backend error: LLM returned no answer for a-local-model: ' +
  '18269 chars of thinking and no content (finish_reason=repetition)'

describe('causes a language model run ends on', () => {
  it('reads a provider rate limit as rate_limited', () => {
    expect(classifyError(RATE_LIMITED)).toBe('rate_limited')
    expect(failureKey('error', RATE_LIMITED)).toBe('generationError.causeRateLimited')
  })

  it('reads a stop by the repetition guard as repetition', () => {
    expect(classifyError(REPEATED)).toBe('repetition')
    expect(failureKey('error', REPEATED)).toBe('generationError.causeRepetition')
  })

  it('leaves the platform refusing a second run on the same device as busy', () => {
    expect(classifyError('Your previous generation is still running')).toBe('busy')
  })
})
