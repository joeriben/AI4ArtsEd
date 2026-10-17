/**
 * What the line under a perspective ring says when nothing was written, and
 * what a torn connection is read as.
 *
 * Until the second review of 2026-10-10 the one failure sentence named the
 * status and dropped what the server had said (the voice comparison showed
 * the server's own reason before the rings were consolidated), and a fetch
 * that never reached the server was read as "something went wrong" rather
 * than as the service not being reachable.
 */
import { describe, it, expect } from 'vitest'
import { perspectiveFailureText } from '../useLabRun'
import { classifyError } from '../useGenerationStream'

const t = (key: string, values?: Record<string, unknown>) =>
  values ? `${key}:${JSON.stringify(values)}` : key

describe('perspectiveFailureText', () => {
  it('says what the server said where it said anything', () => {
    expect(perspectiveFailureText(t, { failed: 404, said: 'Config "x" nicht gefunden' }))
      .toBe('Config "x" nicht gefunden')
  })

  it('names the status where the server said nothing', () => {
    expect(perspectiveFailureText(t, { failed: 502 })).toBe('perspective.failed:{"status":502}')
  })

  it('keeps the refusal and the empty answer as they were', () => {
    expect(perspectiveFailureText(t, { refusedKey: 'safetyBlocked.generic', reason: 'x' })).toBe('safetyBlocked.generic')
    expect(perspectiveFailureText(t, { empty: true })).toBe('perspective.empty')
  })
})

describe('classifyError', () => {
  it('reads a connection that never reached the server as the service not being reachable', () => {
    expect(classifyError('TypeError: Failed to fetch')).toBe('offline')
    expect(classifyError('NetworkError when attempting to fetch resource.')).toBe('offline')
    expect(classifyError('Network error: the stream ended before its complete frame')).toBe('offline')
  })

  it('still knows nothing about a message that names no cause', () => {
    expect(classifyError('')).toBe('unknown')
    expect(classifyError('a sentence that names no cause')).toBe('unknown')
  })
})
