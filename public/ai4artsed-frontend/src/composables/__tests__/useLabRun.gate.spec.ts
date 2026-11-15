/**
 * The comparison surfaces' stage-2 gate runs through the platform's one
 * perspective call, and a refusal reaches it as the block it is.
 *
 * Until 2026-10-10 the model comparison and the language comparison posted the
 * stage-2 route themselves and matched the German refusal sentence in the
 * answer (a second German fragment and three English literals beside it), a
 * copy of the backend's constant; the
 * backend now answers a block at stage 2
 * (finding S-015 of the code review of 2026-10-10). The gate asks for the
 * pre-check, on which no model writes: the server takes the text in at the
 * intake and hands it back as it came in, and a refusal there is the
 * intake's.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const posted: Array<{ path: string; body: Record<string, unknown> }> = []
let answer: { status: number; data: unknown } = { status: 200, data: {} }

vi.mock('@/services/directRun', () => ({
  postStreamedRun: vi.fn(async (path: string, body: Record<string, unknown>) => {
    posted.push({ path, body })
    return answer
  }),
}))
vi.mock('@/services/labApi', () => ({ apiBase: () => '' }))

import { interceptPrompt } from '../useLabRun'

// The reason the backend carries is the model's own sentence; any text does
// here, because the block is read off its block message, never off the wording.
const SENTENCE = 'The model declined this prompt.'

beforeEach(() => {
  posted.length = 0
})

describe('the stage-2 gate of the comparison surfaces', () => {
  it('asks for the pre-check when told to skip the adaptation', async () => {
    answer = { status: 200, data: { success: true, stage2_result: 'a house' } }
    const outcome = await interceptPrompt('user_defined', 'a house', null, { skipOptimization: true })
    expect(posted).toEqual([{
      path: '/api/schema/pipeline/stage2',
      body: expect.objectContaining({ schema: 'user_defined', input_text: 'a house', skip_optimization: true }),
    }])
    expect(outcome).toEqual({ written: 'a house' })
  })

  it('sends no skip where none was asked for', async () => {
    answer = { status: 200, data: { success: true, stage2_result: 'x' } }
    await interceptPrompt('bauhaus', 'a house', null)
    expect(posted[0]?.body).not.toHaveProperty('skip_optimization')
  })

  it("reads the backend's block at stage 2 as a refusal", async () => {
    const block = { checkpoint: 'refusal', field: 'interception', reason_key: 'refusal', reason: SENTENCE }
    answer = {
      status: 403,
      data: { success: false, status: 'blocked', error: SENTENCE, safety_block: block },
    }
    const outcome = await interceptPrompt('bauhaus', 'something', null)
    expect(outcome).toEqual({ refusedKey: 'safetyBlocked.generic', block })
  })

  it('says a refusal at the gate in the sentence its block message names', async () => {
    const block = { checkpoint: 'intake', field: 'input_text', reason_key: 'personal_data', reason: SENTENCE }
    answer = { status: 403, data: { success: false, error: SENTENCE, safety_block: block } }
    const outcome = await interceptPrompt('user_defined', 'something', null, { skipOptimization: true })
    expect(outcome).toEqual({ refusedKey: 'safetyBlocked.dsgvo', block })
  })
})
