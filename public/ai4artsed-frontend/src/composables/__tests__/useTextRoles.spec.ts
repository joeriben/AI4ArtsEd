import { describe, it, expect } from 'vitest'
import { classifyMusicRoles } from '../useTextRoles'

const LYRICS = `[Verse]
The city hums beneath the rain
a window keeps the light

[Chorus]
And we go on, and we go on
until the morning comes`

const STYLE = 'indie pop, melancholic, electric guitar, mid-tempo'

describe('classifyMusicRoles', () => {
  it('reads lyrics + style tags, in either order', () => {
    expect(classifyMusicRoles([LYRICS, STYLE])).toEqual({ lyrics: LYRICS, style: STYLE })
    expect(classifyMusicRoles([STYLE, LYRICS])).toEqual({ lyrics: LYRICS, style: STYLE })
  })

  it('reads a stanza without section markers when the tags are unambiguous', () => {
    const stanza = `the river carries what we said\nand leaves it on the shore\nthe morning takes it back again\nand asks us for one more\nwe answer with our silence\nand the water asks no more`
    const roles = classifyMusicRoles([stanza, 'folk, acoustic guitar, warm, slow'])
    expect(roles).not.toBeNull()
    expect(roles!.lyrics).toBe(stanza)
  })

  // The bar is high on purpose: a false positive turns a poem into a song.
  it('does not fire on a single text', () => {
    expect(classifyMusicRoles([LYRICS])).toBeNull()
    expect(classifyMusicRoles([STYLE])).toBeNull()
  })

  it('does not fire on three texts — that is material, not a song', () => {
    expect(classifyMusicRoles([LYRICS, STYLE, 'a fox made of light'])).toBeNull()
  })

  it('does not fire on two ordinary prose texts', () => {
    expect(
      classifyMusicRoles([
        'A fox made of light walks through an empty museum at night.',
        'Make it feel like an old photograph, slightly overexposed.',
      ])
    ).toBeNull()
  })

  it('does not fire on a poem plus an unrelated instruction', () => {
    const poem = `snow on the fence\na sparrow shakes it loose\nnobody saw it fall`
    expect(classifyMusicRoles([poem, 'use only cold colors'])).toBeNull()
  })

  it('does not fire on two style-like texts', () => {
    expect(classifyMusicRoles(['jazz, piano, slow', 'techno, synth, fast'])).toBeNull()
  })

  it('ignores empty and whitespace-only texts', () => {
    expect(classifyMusicRoles([LYRICS, '   ', STYLE])).toEqual({ lyrics: LYRICS, style: STYLE })
    expect(classifyMusicRoles(['', ''])).toBeNull()
  })

  it('accepts German style tags', () => {
    const roles = classifyMusicRoles([LYRICS, 'schlager, fröhlich, akkordeon'])
    expect(roles).not.toBeNull()
    expect(roles!.style).toBe('schlager, fröhlich, akkordeon')
  })
})
