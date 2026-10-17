/**
 * One table from media type to file extension, and the served type wins.
 *
 * Five surfaces carried their own table until 2026-10-10, and two of them gave
 * audio another extension (mp3) than the other three (wav); which one opens
 * depends on what the recorder wrote, which it sniffs (RIFF or MP3 frame) and
 * the media route serves under its type (finding S-043 of the code review of 2026-10-10). The name a download starts
 * with comes from the one table; the bytes' own type corrects it.
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { downloadMedia, mediaExtension, withExtensionOf } from '../downloadMedia'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('mediaExtension', () => {
  it('names one extension per media type, and bin for the unknown', () => {
    expect(mediaExtension('image')).toBe('png')
    expect(mediaExtension('audio')).toBe('wav')
    expect(mediaExtension('music')).toBe('mp3')
    expect(mediaExtension('video')).toBe('mp4')
    expect(mediaExtension('3d')).toBe('glb')
    expect(mediaExtension('code')).toBe('js')
    expect(mediaExtension('nothing-of-the-kind')).toBe('bin')
    expect(mediaExtension(undefined)).toBe('bin')
  })
})

describe('withExtensionOf', () => {
  it('replaces the extension with the one the served type says', () => {
    expect(withExtensionOf('run_7.wav', 'audio/mpeg')).toBe('run_7.mp3')
    expect(withExtensionOf('flow_abc.png', 'image/jpeg')).toBe('flow_abc.jpg')
    expect(withExtensionOf('piece.mp3', 'audio/wav')).toBe('piece.wav')
  })

  it('leaves a name alone where the types agree or the type says nothing', () => {
    expect(withExtensionOf('run_7.mp3', 'audio/mpeg; charset=binary')).toBe('run_7.mp3')
    expect(withExtensionOf('a.jpeg', 'image/jpeg')).toBe('a.jpeg')
    expect(withExtensionOf('run_7.wav', '')).toBe('run_7.wav')
    expect(withExtensionOf('run_7.wav', 'application/octet-stream')).toBe('run_7.wav')
    expect(withExtensionOf('run_7.bin', null)).toBe('run_7.bin')
  })
})

describe('downloadMedia', () => {
  it('hands the file over under the extension of the bytes it fetched', async () => {
    const blob = new Blob(['ID3'], { type: 'audio/mpeg' })
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, statusText: 'OK', blob: async () => blob })))
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:x', revokeObjectURL: () => undefined })
    const names: string[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download)
    })
    const problem = await downloadMedia('/api/media/audio/run_7', 'persona_run_7.wav')
    expect(problem).toBe('')
    expect(names).toEqual(['persona_run_7.mp3'])
  })
})
