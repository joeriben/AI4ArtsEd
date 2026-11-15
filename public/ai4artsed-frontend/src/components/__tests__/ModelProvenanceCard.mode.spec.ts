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

function opened(
  mode: 'easy' | 'medium' | 'expert',
  meta: Record<string, any> = { publisher: 'Stability AI', params: '8B' },
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useUiModeStore().mode = mode
  const wrapper = mount(ModelProvenanceCard, {
    props: { meta },
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

  it('names the model the run generated with, first, in both views', async () => {
    const meta = {
      display_name: 'Concept Algebra (SD 3.5)',
      model_used: 'OfficialStableDiffusion/sd3.5_large.safetensors',
      publisher: 'Maker',
    }
    const easy = await opened('easy', meta)
    expect(easy.find('.kids-line').text()).toContain('sd3.5_large.safetensors')
    const medium = await opened('medium', meta)
    expect(medium.find('.spec-label').text()).toBe('Model')
    const value = medium.find('.spec-value')
    expect(value.text()).toBe('sd3.5_large.safetensors')
    expect(value.attributes('title')).toBe('OfficialStableDiffusion/sd3.5_large.safetensors')
    expect(medium.text()).not.toContain('Concept Algebra')
  })

  it('names a repository id without its publisher, and two experts both', async () => {
    const repo = await opened('expert', { model_used: 'stabilityai/stable-diffusion-3.5-large' })
    expect(repo.find('.spec-value').text()).toBe('stable-diffusion-3.5-large')
    const wan = await opened('expert', {
      model_used: 'wan2.2_high_noise_14B.safetensors + wan2.2_low_noise_14B.safetensors',
    })
    expect(wan.find('.spec-value').text()).toBe(
      'wan2.2_high_noise_14B.safetensors + wan2.2_low_noise_14B.safetensors',
    )
  })

  it('shows no model row where the run reported none', async () => {
    const wrapper = await opened('medium', { display_name: 'Declared', publisher: 'Maker' })
    expect(wrapper.find('.spec-label').text()).not.toBe('Model')
    expect(wrapper.text()).not.toContain('Declared')
  })
})
