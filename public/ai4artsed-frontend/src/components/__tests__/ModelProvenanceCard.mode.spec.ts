/**
 * The provenance card shows the depth the UI mode decides.
 *
 * The card has three depths (easy, medium, expert) and read them off a prop;
 * every caller wrote 'medium' into that prop, so the card showed the youth
 * depth in every mode and the kids note was never shown (finding S-017 of the code review of 2026-10-10). Since
 * 2026-10-10 the card reads the mode from its store.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import i18n from '@/i18n'
import { useUiModeStore } from '@/stores/uiMode'
import ModelProvenanceCard from '../ModelProvenanceCard.vue'

function opened(mode: 'easy' | 'medium' | 'expert') {
  const pinia = createPinia()
  setActivePinia(pinia)
  useUiModeStore().mode = mode
  const wrapper = mount(ModelProvenanceCard, {
    props: { meta: { publisher: 'Stability AI', params: '8B' } },
    global: { plugins: [pinia, i18n] },
  })
  return wrapper.find('.provenance-toggle').trigger('click').then(() => wrapper)
}

describe('ModelProvenanceCard and the UI mode', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows the short view in the easy mode', async () => {
    const wrapper = await opened('easy')
    expect(wrapper.find('.provenance-kids').exists()).toBe(true)
    expect(wrapper.find('.model-specs').exists()).toBe(false)
  })

  it('shows the full card in the medium mode', async () => {
    const wrapper = await opened('medium')
    expect(wrapper.find('.model-specs').exists()).toBe(true)
    expect(wrapper.find('.provenance-kids').exists()).toBe(false)
  })
})
