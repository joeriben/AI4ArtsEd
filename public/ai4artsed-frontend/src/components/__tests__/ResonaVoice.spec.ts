// Zoom scaling (the .turn taking the board's scale) is NOT covered here: vitest
// leaves SFC <style> blocks uncompiled, so the v-bind() CSS var never appears in
// jsdom. That behaviour is verified against the running board instead.
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ResonaVoice, { type VoiceUtterance, type VoiceCoupling } from '../ResonaVoice.vue'

const user = (id: number, text: string): VoiceUtterance => ({ id, role: 'user', text })
const said = (id: number, text: string): VoiceUtterance => ({ id, role: 'assistant', text, liftable: true })

function render(trail: VoiceUtterance[], props: Record<string, unknown> = {}) {
  return mount(ResonaVoice, { props: { trail, ...props } })
}

describe('ResonaVoice — the standing turn', () => {
  it('shows nothing before anyone has spoken', () => {
    // The column itself always stands -- it carries the open line, and a caret
    // may not wait for somebody else to speak first. What must not be there is
    // anything SAID: no body, no words, no answer.
    const w = render([])
    expect(w.find('.turn-body').exists()).toBe(false)
    expect(w.find('.turn-said').exists()).toBe(false)
    expect(w.find('.turn-answer').exists()).toBe(false)
    w.unmount()
  })

  it('stands up on the opening turn, before Resona has answered', () => {
    // The regression this guards: the box used to render only once an assistant
    // line existed, so the whole first wait was blank and the human's words and
    // the reply appeared to land together.
    const w = render([user(0, 'wir arbeiten mit Ton')], { speak: 'listening' })
    expect(w.find('.turn').exists()).toBe(true)
    expect(w.find('.turn').classes()).toContain('listening')
    expect(w.find('.turn-said').exists()).toBe(false)
    expect(w.find('.turn-answer').text()).toBe('wir arbeiten mit Ton')
    w.unmount()
  })

  it('speaks the latest assistant line with the answer beneath it', () => {
    const w = render([said(0, 'Was liegt auf dem Tisch?'), user(1, 'eine Grafik')])
    expect(w.find('.turn-said').text()).toContain('Was liegt auf dem Tisch?')
    expect(w.find('.turn-answer').text()).toBe('eine Grafik')
    w.unmount()
  })

  it('keeps the question standing above the reply it brought about', () => {
    // Two dialog texts stand at a time, and they are the two of ONE exchange.
    // This used to show the reply alone: the line that produced it was nowhere
    // on screen, so what had been asked could not be read off the surface.
    const w = render([user(0, 'eine Grafik'), said(1, 'Erzähl mehr.')])
    expect(w.find('.turn-said').text()).toContain('Erzähl mehr.')
    expect(w.find('.turn-answer').text()).toBe('eine Grafik')
    // Spoken first, so it stands first.
    expect(w.find('.turn-answer').classes()).toContain('above')
    const body = w.find('.turn-body').element as HTMLElement
    const kids = Array.from(body.children).map(el => el.className)
    expect(kids.findIndex(c => c.includes('turn-answer')))
      .toBeLessThan(kids.findIndex(c => c.includes('turn-said')))
    w.unmount()
  })

  it('puts a line written since BELOW the words it answers', () => {
    const w = render([said(0, 'Was liegt auf dem Tisch?'), user(1, 'eine Grafik')])
    expect(w.find('.turn-answer').text()).toBe('eine Grafik')
    expect(w.find('.turn-answer').classes()).not.toContain('above')
    w.unmount()
  })
})

// ---------------------------------------------------------------------------
// ONE PARAGRAPH, AND ONLY ONE
//
// The rule of the two speaking surfaces: what is said is heard and read ONCE,
// and when the next paragraph is spoken the one before it is gone. The AI is
// a counterpart here, and also a withdrawal. Every one of these has been
// broken before by a fix that looked local, which is why they are pinned here
// rather than only measured on the running surface.
// ---------------------------------------------------------------------------

const cut = (text: string): string[] =>
  text.split(/(?<=[.!?])\s+/).map(t => t.trim()).filter(Boolean)

function coupling(over: Partial<VoiceCoupling> = {}): VoiceCoupling {
  return {
    piece: null,
    askedKey: null,
    pendingKey: null,
    speakingKey: null,
    blockedKey: null,
    segment: cut,
    ...over,
  }
}

/** The pieces on the surface, in their order. */
function standing(w: ReturnType<typeof render>): string[] {
  return w.findAll('.sent-stack .voice-sent').map(n => n.text())
}

const FOUR = 'Eins hier. Zwei hier. Drei hier. Vier hier.'
const TWO_PARAS = 'Eins hier. Zwei hier.\n\nDrei hier. Vier hier.'

function sounding(text: string, index: number, id = 0): VoiceCoupling {
  const parts = cut(text)
  return coupling({
    speakingKey: id,
    piece: { key: id, index, text: parts[index] ?? '', total: parts.length, durationMs: 900 },
  })
}

describe('ResonaVoice — one paragraph at a time', () => {
  it('stands only as far as the voice has come', () => {
    const w = render([said(0, FOUR)], { words: true, coupling: sounding(FOUR, 0) })
    expect(standing(w)).toEqual(['Eins hier.'])
    w.unmount()
  })

  it('lets the paragraph grow with the voice, up to the maximum', async () => {
    const w = render([said(0, FOUR)], { words: true, coupling: sounding(FOUR, 0) })
    await w.setProps({ coupling: sounding(FOUR, 1) })
    await w.setProps({ coupling: sounding(FOUR, 2) })
    expect(standing(w)).toEqual(['Eins hier.', 'Zwei hier.', 'Drei hier.'])
    w.unmount()
  })

  it('REMOVES the paragraph that stood when the next one is spoken', async () => {
    const w = render([said(0, FOUR)], { words: true, coupling: sounding(FOUR, 0) })
    await w.setProps({ coupling: sounding(FOUR, 1) })
    await w.setProps({ coupling: sounding(FOUR, 2) })
    await w.setProps({ coupling: sounding(FOUR, 3) })
    expect(standing(w)).toEqual(['Vier hier.'])
    w.unmount()
  })

  it('starts a paragraph where the blank line is, before the maximum', async () => {
    const w = render([said(0, TWO_PARAS)], { words: true, coupling: sounding(TWO_PARAS, 1) })
    expect(standing(w)).toEqual(['Eins hier.', 'Zwei hier.'])
    await w.setProps({ coupling: sounding(TWO_PARAS, 2) })
    expect(standing(w)).toEqual(['Drei hier.'])
    w.unmount()
  })

  it('hands nothing over whole when the browser refuses to play', () => {
    // The escape that broke the rule: a sound the browser would not start used
    // to release the entire reply at once, so the paragraph stood there in full
    // and there was nothing left to listen along to.
    const w = render([said(0, FOUR)], {
      words: true,
      coupling: coupling({ askedKey: 0, blockedKey: 0 }),
    })
    expect(standing(w).length).toBeLessThanOrEqual(1)
    w.unmount()
  })

  it('hands nothing over whole when the voice cut the turn differently', () => {
    // Where the spoken pieces and the written pieces disagree, piece i and
    // piece i are no longer the same thing. The words then go at reading pace —
    // what they may NOT do is stand there complete.
    const w = render([said(0, FOUR)], {
      words: true,
      coupling: coupling({
        speakingKey: 0,
        piece: { key: 0, index: 0, text: 'Eins hier.', total: 9, durationMs: 900 },
      }),
    })
    expect(standing(w).length).toBeLessThanOrEqual(1)
    w.unmount()
  })

  it('reads on at reading pace when the voice cut the turn differently, asked for or not', () => {
    // A voice whose cut differs is no clock. Held for it while the turn was
    // still marked as asked, the words stood at one sentence while the voice
    // spoke the rest (a notice under the line made the counts differ).
    vi.useFakeTimers()
    try {
      const w = render([said(0, FOUR)], {
        words: true,
        streamingId: null,
        coupling: coupling({
          askedKey: 0,
          speakingKey: 0,
          piece: { key: 0, index: 0, text: 'Eins hier.', total: 9, durationMs: 900 },
        }),
      })
      expect(standing(w)).toEqual(['Eins hier.'])
      vi.advanceTimersByTime(3000)
      expect(standing(w)).toEqual(['Eins hier.', 'Zwei hier.'])
      w.unmount()
    } finally {
      vi.useRealTimers()
    }
  })

  it('clears what stood when the text is taken back', async () => {
    // A tool round's preamble is discarded: the standing text becomes empty
    // while the turn is still being written. Nothing of what stood is in it
    // any more, so nothing stands — the preamble used to stand through the
    // whole tool run.
    const w = render([said(0, FOUR)], {
      words: true,
      streamingId: 0,
      coupling: sounding(FOUR, 2),
    })
    expect(standing(w)).toEqual(['Eins hier.', 'Zwei hier.', 'Drei hier.'])
    await w.setProps({ trail: [said(0, '')], coupling: coupling({ askedKey: 0 }) })
    expect(standing(w)).toEqual([])
    w.unmount()
  })

  it('replaces a piece that came out differently once the rest had arrived', async () => {
    // While a reply is still arriving, the same cut can yield a different first
    // piece from one moment to the next. What stands has to become what the cut
    // now says, rather than a fragment left over from an earlier pass.
    const w = render([said(0, 'Ein')], {
      words: true,
      streamingId: null,
      coupling: sounding('Ein', 0),
    })
    expect(standing(w)).toEqual(['Ein'])
    await w.setProps({
      trail: [said(0, 'Ein Anfang. Und dann.')],
      coupling: sounding('Ein Anfang. Und dann.', 0),
    })
    expect(standing(w)).toEqual(['Ein Anfang.'])
    w.unmount()
  })
})
