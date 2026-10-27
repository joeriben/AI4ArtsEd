/**
 * The target language of the Canvas translation node (StageModule.vue): what
 * the select shows is what the executor sends (canvas_executor._execute_translation).
 *
 * The parent writes an emitted value into the node in place (stores/canvas.ts,
 * updateNode), so the tests mutate one reactive node the way the store does.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { reactive, nextTick } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import i18n from '@/i18n'
import StageModule from '../StageModule.vue'
import { translationDefaults } from '@/lib/translationDefaults'
import type { CanvasNode } from '@/types/canvas'

const DEFAULTS = { instruction: 'Translate everything into the target language.', language: 'en' }

beforeEach(() => {
  setActivePinia(createPinia())
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => DEFAULTS }))
  translationDefaults.value = { ...DEFAULTS }
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function translationNode(fields: Partial<CanvasNode> = {}): CanvasNode {
  return reactive({ id: 'translation', type: 'translation', x: 0, y: 0, llmModel: 'stub', ...fields }) as CanvasNode
}

/** Mounts the node and writes every emitted value into it, as the store does. */
function stage(node: CanvasNode) {
  return mount(StageModule, {
    props: {
      node,
      selected: false,
      'onUpdate-translation-language': (language: string | undefined) => { node.translationLanguage = language },
      'onUpdate-translation-prompt': (prompt: string | undefined) => { node.translationPrompt = prompt },
    },
    global: { plugins: [i18n] },
  })
}

function languageSelect(wrapper: VueWrapper) {
  const select = wrapper.findAll('select').find(s => s.find('option[value="__other__"]').exists())
  expect(select, 'no target-language select').toBeTruthy()
  return select!
}

describe('StageModule — translation target language', () => {
  it('keeps English where the default instruction is written into', async () => {
    const node = translationNode()
    const wrapper = stage(node)
    await nextTick()
    expect((languageSelect(wrapper).element as HTMLSelectElement).value).toBe('en')

    await wrapper.find('textarea').setValue(`${DEFAULTS.instruction} Keep proper names.`)
    expect(node.translationLanguage).toBe('en')
    expect((languageSelect(wrapper).element as HTMLSelectElement).value).toBe('en')
  })

  it('shows an instruction saved without a language as naming its language itself', async () => {
    const node = translationNode({ translationPrompt: 'Übersetze ins Französische:' })
    const wrapper = stage(node)
    await nextTick()
    expect((languageSelect(wrapper).element as HTMLSelectElement).value).toBe('__prompt__')

    await wrapper.find('textarea').setValue('Übersetze ins Französische, bitte:')
    expect(node.translationLanguage).toBeUndefined()
  })

  it('keeps a saved free-text language open while it is rewritten through a listed code', async () => {
    const node = translationNode({ translationLanguage: 'estonian' })
    const wrapper = stage(node)
    await nextTick()
    const field = wrapper.find('input.language-other')
    expect(field.exists()).toBe(true)

    await field.setValue('es')
    await nextTick()
    expect(node.translationLanguage).toBe('es')
    expect(wrapper.find('input.language-other').exists()).toBe(true)
    expect((languageSelect(wrapper).element as HTMLSelectElement).value).toBe('__other__')
  })

  it('drops an open free-text field when a board brings a new node of the same id', async () => {
    const wrapper = stage(translationNode())
    await nextTick()
    await languageSelect(wrapper).setValue('__other__')
    expect(wrapper.find('input.language-other').exists()).toBe(true)

    const replacement = translationNode()
    await wrapper.setProps({ node: replacement })
    expect(wrapper.find('input.language-other').exists()).toBe(false)
    expect((languageSelect(wrapper).element as HTMLSelectElement).value).toBe('en')
  })
})
