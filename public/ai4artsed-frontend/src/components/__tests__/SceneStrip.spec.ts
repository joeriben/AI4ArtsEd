/**
 * UCD-133 — the capsule strip's own two acts: a capsule stands out when it
 * is driven at, and the prompt it carries goes on through the surface's
 * prompt instrument (the carry event; where it lands is resona.vue's open
 * line). Counts arrive as numbers — the strip has no excluded content to
 * show, and the test pins that it never tries.
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
  capsules: [
    {
      anchor: { chapter: 'Kapitel 1', probe: 'Eine Werkstatt, Tische voll Skizzen.' },
      scene: 'In einer Werkstatt stehen Lernende um einen Tisch.',
      prompt: 'Ein Bild, das zeigt: In einer Werkstatt stehen Lernende um einen Tisch.',
      safety: { verdict: 'pass', categories: [] },
    },
    {
      anchor: { chapter: 'Kapitel 2', probe: 'Offene Räume, Material in Reichweite.' },
      scene: 'An einer Planwand markiert eine Gruppe Arbeitsschritte.',
      prompt: 'Ein Bild, das zeigt: An einer Planwand markiert eine Gruppe Arbeitsschritte.',
      safety: { verdict: 'pass', categories: [] },
    },
  ],
  flagged: 3,
  discarded: 1,
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
  it('shows the whole document as a strip over the capsules', () => {
    const w = open()
    const cells = w.findAll('.ss-cell')
    expect(cells).toHaveLength(2)
    expect(w.text()).toContain('Probe-Programm')
    expect(w.text()).toContain('In einer Werkstatt stehen Lernende um einen Tisch.')
  })

  it('drives at one capsule: it stands out, and the carry event hands its prompt on', async () => {
    const w = open()
    expect(w.find('.ss-detail').exists()).toBe(false)
    await w.findAll('.ss-cell')[1]!.trigger('click')
    expect(w.find('.ss-detail').exists()).toBe(true)
    // The anchor is the capsule's evidence duty: chapter + in-vivo probe.
    expect(w.text()).toContain('Kapitel 2')
    expect(w.text()).toContain('Offene Räume, Material in Reichweite.')
    // A second click on the same cell puts it back.
    await w.findAll('.ss-cell')[1]!.trigger('click')
    expect(w.find('.ss-detail').exists()).toBe(false)
    // Drive again and carry: the prompt goes on in the surface's own words.
    await w.findAll('.ss-cell')[0]!.trigger('click')
    const btn = w.find('.ss-carry')
    expect(btn.exists()).toBe(true)
    await btn.trigger('click')
    expect(w.emitted('carry')).toEqual([['Ein Bild, das zeigt: In einer Werkstatt stehen Lernende um einen Tisch.']])
  })

  it('reports excluded sections and discarded capsules as counts, never as content', () => {
    const w = open()
    const text = w.text()
    expect(text).toContain('3 sections excluded, protection reasons')
    expect(text).toContain('1 capsules discarded by the capsule gate')
    // A flagged segment has no stored content to leak; what the strip shows
    // of the document is the capsules and the counts, nothing else.
    expect(w.findAll('.ss-count')).toHaveLength(2)
  })
})
