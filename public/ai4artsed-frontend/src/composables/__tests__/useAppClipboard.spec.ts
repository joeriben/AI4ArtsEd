/**
 * The platform's one hand carries text. A run marker that an older copy left
 * in storage (the channel went on 2026-10-10) is not text anybody wrote, and
 * the hand answers empty for it.
 */
import { describe, it, expect } from 'vitest'
import { useAppClipboard } from '../useAppClipboard'

describe('useAppClipboard', () => {
  it('hands back what was copied', () => {
    const { copy, paste, clear } = useAppClipboard()
    copy('ein haus am feldrand')
    expect(paste()).toBe('ein haus am feldrand')
    clear()
    expect(paste()).toBe('')
  })

  it('answers empty for a run marker left over from the channel that went', () => {
    const { copy, paste, clear } = useAppClipboard()
    copy('ai4artsed:run:run_20260101_abc')
    expect(paste()).toBe('')
    clear()
  })
})
