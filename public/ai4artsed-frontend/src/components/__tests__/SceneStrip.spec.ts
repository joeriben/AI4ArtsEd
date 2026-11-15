/**
 * The document card's own acts: it shows the summary it was handed, a section
 * stands out when it is driven at, and its text goes on through the surface's
 * prompt instrument (the carry event; where it lands is the view's). What the
 * check withheld arrives as a number: the card has no withheld content to show,
 * and the test pins that it never tries.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import SceneStrip from '../SceneStrip.vue'
import type { SceneDocument } from '@/composables/useSceneIntake'
import { en } from '@/i18n/en'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en },
})

const DOC: SceneDocument = {
  docId: 'doc-x',
  title: 'Probe-Programm',
  profile: 'Der Text fordert Werkstätten für alle Schulen.',
  sections: [
    { heading: 'Die Werkstatt', body: 'Lernende stehen um einen Tisch.\n- Skizzen\n- Modelle' },
    { heading: 'Die Planwand', body: 'Eine Gruppe markiert Arbeitsschritte.' },
  ],
  glossary: [{ term: 'Werkstatt', definition: 'Raum für gemeinsames Arbeiten.' }],
  withheld: 3,
  meta: { analyzedAt: '2026-09-27T16:00:00+00:00', analysisModel: 'mammouth/glm-5.3', analysisLang: 'de' },
}

function open(doc: SceneDocument = DOC) {
  return mount(SceneStrip, {
    props: { doc },
    global: { plugins: [i18n] },
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('SceneStrip', () => {
  it('shows the summary: title, profile, a cell per section and one for the glossary', () => {
    const w = open()
    expect(w.text()).toContain('Probe-Programm')
    expect(w.find('.ss-profile').text()).toBe('Der Text fordert Werkstätten für alle Schulen.')
    const cells = w.findAll('.ss-cell')
    expect(cells).toHaveLength(3)
    expect(cells[0]!.text()).toContain('Die Werkstatt')
    expect(cells[2]!.text()).toContain('Glossary')
  })

  it('shows only its head while the summary runs', () => {
    const w = mount(SceneStrip, {
      props: {
        doc: { docId: '', title: 'a.pdf', profile: '', sections: [], glossary: [], withheld: 0, meta: {} },
        status: 'Section 2 of 9',
      },
      global: { plugins: [i18n] },
    })
    expect(w.text()).toContain('a.pdf')
    expect(w.find('.ss-status').text()).toBe('Section 2 of 9')
    expect(w.find('.ss-strip').exists()).toBe(false)
    expect(w.find('.ss-profile').exists()).toBe(false)
  })

  it('drives at one section: it opens, and the carry event hands its text on', async () => {
    const w = open()
    expect(w.find('.ss-detail').exists()).toBe(false)
    await w.findAll('.ss-cell')[1]!.trigger('click')
    expect(w.find('.ss-detail').text()).toContain('Eine Gruppe markiert Arbeitsschritte.')
    // A second click on the same cell puts it back.
    await w.findAll('.ss-cell')[1]!.trigger('click')
    expect(w.find('.ss-detail').exists()).toBe(false)
    await w.findAll('.ss-cell')[0]!.trigger('click')
    await w.find('.ss-carry').trigger('click')
    expect(w.emitted('carry')).toEqual([['Lernende stehen um einen Tisch.\n- Skizzen\n- Modelle']])
  })

  it('opens the glossary, which carries nothing on', async () => {
    const w = open()
    await w.findAll('.ss-cell')[2]!.trigger('click')
    expect(w.find('.ss-glossary').text()).toContain('Raum für gemeinsames Arbeiten.')
    expect(w.find('.ss-carry').exists()).toBe(false)
  })

  it('reports withheld parts as a count, never as content', () => {
    const w = open()
    expect(w.text()).toContain('The safety check withheld 3 parts of this summary.')
    expect(w.findAll('.ss-count')).toHaveLength(1)
  })

  it('says one withheld part in the singular', () => {
    const w = open({ ...DOC, withheld: 1 })
    expect(w.find('.ss-count').text()).toBe('The safety check withheld one part of this summary.')
  })

  it('gives the day of the analysis in the reader\'s form, not the wire stamp', () => {
    const w = open()
    expect(w.text()).not.toContain('T16:00:00')
    expect(w.text()).toContain('mammouth/glm-5.3')
  })
})
