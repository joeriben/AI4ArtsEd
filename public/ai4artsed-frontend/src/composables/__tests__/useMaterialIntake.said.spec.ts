/**
 * The one upload carries what the server said. The widget showed a house
 * sentence for every failure until the second review of 2026-10-10, while
 * the route names the reason (a size, a type, a refusal).
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { uploadImageFile } from '../useMaterialIntake'

function answering(status: number, body: unknown): Response {
  return {
    ok: status < 400,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('uploadImageFile', () => {
  it('carries the reason the server gave', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => answering(413, { success: false, error: 'the file is larger than 20 MB' })))
    const file = new File([new Uint8Array(4)], 'x.png', { type: 'image/png' })
    const failed = await uploadImageFile(file).then(() => null, (e: unknown) => e as Error & { said?: string })
    expect(failed).toBeTruthy()
    expect(failed!.message).toBe('the file is larger than 20 MB')
    expect(failed!.said).toBe('the file is larger than 20 MB')
  })

  it('says nothing beyond the house sentence where the server said nothing', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => answering(500, { success: false })))
    const file = new File([new Uint8Array(4)], 'x.png', { type: 'image/png' })
    const failed = await uploadImageFile(file).then(() => null, (e: unknown) => e as Error & { said?: string })
    expect(failed!.message).toBe('upload failed')
    expect(failed!.said).toBeUndefined()
  })
})
