/**
 * The one way onto paper writes a document of its own around the picture.
 *
 * Until the second review of 2026-10-10 it opened the picture's address as a
 * page; a browser refuses to open a `data:` address in a window of its own,
 * and the Flow's sketches and captured frames carry such addresses. Given a
 * window, the helper writes an image into it and prints once it has loaded.
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { printMedia } from '../printMedia'

function aWindow() {
  const doc = document.implementation.createHTMLDocument('')
  const print = vi.fn()
  return { win: { document: doc, print } as unknown as Window, doc, print }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('printMedia', () => {
  it('writes the picture into a document of its own and prints once it has loaded', () => {
    const { win, doc, print } = aWindow()
    const open = vi.fn(() => win)
    vi.stubGlobal('open', open)

    printMedia('data:image/png;base64,AAAA')

    expect(open).toHaveBeenCalledWith('', '_blank')
    const picture = doc.body.querySelector('img')
    expect(picture, 'no picture was written into the window').toBeTruthy()
    expect(picture!.getAttribute('src')).toBe('data:image/png;base64,AAAA')
    expect(doc.title).toBe('ai4artsed')
    expect(print).not.toHaveBeenCalled()
    picture!.dispatchEvent(new Event('load'))
    expect(print).toHaveBeenCalledTimes(1)
  })

  it('does nothing without an address, and nothing when the window was refused', () => {
    const open = vi.fn(() => null)
    vi.stubGlobal('open', open)
    printMedia('')
    printMedia(null)
    expect(open).not.toHaveBeenCalled()
    printMedia('/api/media/image/run_1')
    expect(open).toHaveBeenCalledTimes(1)
  })
})
