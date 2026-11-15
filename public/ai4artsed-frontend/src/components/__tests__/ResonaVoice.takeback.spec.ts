// A preamble taken back with the voice switched off.
//
// Without a voice the words are cut by splitVoiceSentences (Intl.Segmenter),
// which in this test environment returns a whole text as one sentence, so
// nothing would stand while a turn is written. Here it cuts at the sentence
// marks, as it does in the browser; the voice's own cut is untouched.
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/lib/voiceText', async (importOriginal) => {
  const real = await importOriginal<typeof import('@/lib/voiceText')>()
  return {
    ...real,
    splitVoiceSentences: (text: string) =>
      text.split(/(?<=[.!?])\s+/).map(t => t.trim()).filter(Boolean),
  }
})

import ResonaVoice, { type VoiceUtterance } from '../ResonaVoice.vue'

const said = (id: number, text: string): VoiceUtterance => ({ id, role: 'assistant', text, liftable: true })

function standing(w: ReturnType<typeof mount>): string[] {
  return w.findAll('.sent-stack .voice-sent').map(n => n.text())
}

describe('ResonaVoice — the voice switched off', () => {
  it('clears what stood when the text is taken back', async () => {
    // The reading clock places the words. A tool round's preamble was taken
    // back (`discard`) and stood through the whole tool run on that clock.
    vi.useFakeTimers()
    try {
      const w = mount(ResonaVoice, { props: { trail: [said(0, '')], streamingId: 0 } })
      await w.setProps({ trail: [said(0, 'Ich sehe kurz nach. Einen Moment. Gleich.')] })
      expect(standing(w)).toEqual(['Ich sehe kurz nach.'])
      await w.setProps({ trail: [said(0, '')] })
      expect(standing(w)).toEqual([])
      w.unmount()
    } finally {
      vi.useRealTimers()
    }
  })

  it('stands the struck draft again when the preamble that replaced it is taken back', async () => {
    // A draft taken back stays, struck through, until the corrected text
    // follows. The corrected round can open with a tool round's preamble,
    // which takes the draft's place and is then taken back itself.
    vi.useFakeTimers()
    try {
      const struck = (text: string): VoiceUtterance => ({
        ...said(0, text), withdrawn: ['Der alte Entwurf.'] })
      const w = mount(ResonaVoice, { props: { trail: [said(0, '')], streamingId: 0 } })
      await w.setProps({ trail: [struck('')] })
      expect(standing(w)).toEqual(['Der alte Entwurf.'])
      await w.setProps({ trail: [struck('Ich sehe kurz nach. Einen Moment. Gleich.')] })
      expect(standing(w)).toEqual(['Ich sehe kurz nach.'])
      await w.setProps({ trail: [struck('')] })
      expect(standing(w)).toEqual(['Der alte Entwurf.'])
      expect(w.find('.sent-stack .voice-sent').classes()).toContain('withdrawn')
      await w.setProps({ trail: [struck('Das Bild zeigt einen Hafen. Ein Boot. Ein Kran.')] })
      expect(standing(w)).toEqual(['Das Bild zeigt einen Hafen.'])
      w.unmount()
    } finally {
      vi.useRealTimers()
    }
  })

  it('stands no struck draft again under a turn that is finished', async () => {
    // Only while the turn is still written does the corrected text follow.
    vi.useFakeTimers()
    try {
      const struck = (text: string): VoiceUtterance => ({
        ...said(0, text), withdrawn: ['Der alte Entwurf.'] })
      const w = mount(ResonaVoice, { props: { trail: [struck('')], streamingId: 0 } })
      await w.setProps({ trail: [struck('Ich sehe kurz nach. Einen Moment. Gleich.')] })
      expect(standing(w)).toEqual(['Ich sehe kurz nach.'])
      await w.setProps({ trail: [struck('')], streamingId: null })
      expect(standing(w)).toEqual([])
      w.unmount()
    } finally {
      vi.useRealTimers()
    }
  })

  it('fades a struck draft out struck through when the next turn comes', async () => {
    vi.useFakeTimers()
    try {
      const struck = (text: string): VoiceUtterance => ({
        ...said(0, text), withdrawn: ['Der alte Entwurf.'] })
      const w = mount(ResonaVoice, { props: { trail: [struck('')], streamingId: 0 } })
      expect(standing(w)).toEqual(['Der alte Entwurf.'])
      await w.setProps({ trail: [struck(''), said(1, 'Neu.')], streamingId: 1 })
      const fading = w.findAll('.turn-leaving .voice-sent')
      expect(fading.map(n => n.text())).toEqual(['Der alte Entwurf.'])
      expect(fading[0]!.classes()).toContain('withdrawn')
      w.unmount()
    } finally {
      vi.useRealTimers()
    }
  })

  it('reads the text that follows a take-back at its own pace', async () => {
    // The reading clock of the taken-back preamble stops with it; left
    // running, it brought the next text's second sentence up early.
    vi.useFakeTimers()
    try {
      const w = mount(ResonaVoice, { props: { trail: [said(0, '')], streamingId: 0 } })
      await w.setProps({ trail: [said(0, 'Ich sehe kurz nach. Einen Moment. Gleich.')] })
      await vi.advanceTimersByTimeAsync(1500)
      await w.setProps({ trail: [said(0, '')] })
      await vi.advanceTimersByTimeAsync(300)
      await w.setProps({ trail: [said(0, 'Erstens. Zweitens. Drittens.')] })
      expect(standing(w)).toEqual(['Erstens.'])
      await vi.advanceTimersByTimeAsync(800)
      expect(standing(w)).toEqual(['Erstens.'])
      await vi.advanceTimersByTimeAsync(1800)
      expect(standing(w)).toEqual(['Erstens.', 'Zweitens.'])
      w.unmount()
    } finally {
      vi.useRealTimers()
    }
  })
})
