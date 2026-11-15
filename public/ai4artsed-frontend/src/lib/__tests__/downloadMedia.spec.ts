/**
 * One table from media type to file extension, and the served type wins.
 *
 * Five surfaces carried their own table until 2026-10-10, and two of them gave
 * audio another extension (mp3) than the other three (wav); which one opens
 * depends on what the recorder wrote, which it sniffs (RIFF or MP3 frame) and
 * the media route serves under its type (finding S-043 of the code review of 2026-10-10). The name a download starts
 * with comes from the one table; the bytes' own type corrects it.
 */
import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { carriesDisclosure, downloadMedia, mediaExtension, unmarkedName, withExtensionOf } from '../downloadMedia'

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

  it('keeps `_ai_generated` where the server served the file under it', async () => {
    const blob = new Blob(['x'], { type: 'image/png' })
    const served = (disposition: string) => ({
      ok: true, status: 200, statusText: 'OK', blob: async () => blob,
      headers: new Headers({ 'Content-Disposition': disposition }),
    })
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:x', revokeObjectURL: () => undefined })
    const names: string[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download)
    })
    vi.stubGlobal('fetch', vi.fn(async () => served('inline; filename=run_7_ai_generated.png')))
    await downloadMedia('/api/media/image/run_7', 'flow_run_7.png')
    vi.stubGlobal('fetch', vi.fn(async () => served('inline; filename=run_7.png')))
    await downloadMedia('/api/media/image/run_7', 'flow_run_7.png')
    expect(names).toEqual(['flow_run_7_ai_generated.png', 'flow_run_7.png'])
  })
})

describe('bytes the page holds', () => {
  const MARK = 'http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia'

  // jsdom's Blob has no arrayBuffer(); every browser the platform serves does.
  beforeAll(() => {
    if (typeof Blob.prototype.arrayBuffer !== 'function') {
      Blob.prototype.arrayBuffer = function (this: Blob) {
        return new Promise<ArrayBuffer>((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(reader.result as ArrayBuffer)
          reader.onerror = () => reject(reader.error)
          reader.readAsArrayBuffer(this)
        })
      }
    }
  })

  it('finds either value of the disclosure in the bytes', async () => {
    expect(await carriesDisclosure(new Blob(['\x89PNG...', MARK, '...']))).toBe(true)
    expect(await carriesDisclosure(new Blob(['x http://cv.iptc.org/newscodes/digitalsourcetype/algorithmicMedia']))).toBe(true)
    expect(await carriesDisclosure(new Blob(['http://cv.iptc.org/newscodes/digitalsourcetype/']))).toBe(false)
  })

  it('names a held file by its bytes, since no server named it', async () => {
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:x', revokeObjectURL: () => undefined })
    const names: string[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download)
    })
    for (const body of ['plain bytes', `bytes with ${MARK} in them`]) {
      const blob = new Blob([body], { type: 'image/png' })
      vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, statusText: 'OK', blob: async () => blob })))
      await downloadMedia('data:image/png;base64,AAAA', 'lab_7.png')
    }
    expect(names).toEqual(['lab_7_ai_generated.png', 'lab_7.png'])
  })
})

describe('unmarkedName', () => {
  it('puts the suffix before the extension, once', () => {
    expect(unmarkedName('run_7.png')).toBe('run_7_ai_generated.png')
    expect(unmarkedName('run_7_ai_generated.png')).toBe('run_7_ai_generated.png')
    expect(unmarkedName('media')).toBe('media_ai_generated')
    expect(unmarkedName('sketch.v2.js')).toBe('sketch.v2_ai_generated.js')
  })
})
