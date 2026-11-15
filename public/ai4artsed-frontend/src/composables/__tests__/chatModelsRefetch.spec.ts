/**
 * The list of language models a surface offers follows the settings
 * (composables/useChatModels.ts, lib/settingsApplied.ts): asked anew once they
 * are applied, and whoever waits for it gets the latest answer, never one
 * asked for before.
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'

type Deferred = { promise: Promise<unknown>; resolve: (v: unknown) => void }

function deferred(): Deferred {
  let resolve!: (v: unknown) => void
  const promise = new Promise(r => { resolve = r })
  return { promise, resolve }
}

function listOf(...ids: string[]) {
  const models = ids.map(id => ({ id, label: id }))
  return { ok: true, json: async () => ({ models, chosen_models: models }) }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.resetModules()
})

async function mountChatModels() {
  const { useChatModels } = await import('../useChatModels')
  const { settingsApplied } = await import('@/lib/settingsApplied')
  let api!: ReturnType<typeof useChatModels>
  const Probe = defineComponent({
    setup() {
      api = useChatModels()
      return () => h('div')
    },
  })
  const i18n = createI18n({
    legacy: false, locale: 'en',
    messages: { en: { compare: { shared: { defaultModel: 'Default (Settings)' } } } },
  })
  const wrapper = mount(Probe, { global: { plugins: [i18n] } })
  return { api, settingsApplied, wrapper }
}

describe('the chat list after the settings were applied', () => {
  it('asks anew, and a waiter returns with the newer list, not the one asked for before', async () => {
    const answers: Deferred[] = []
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (String(url).includes('/api/chat/models')) {
        const d = deferred()
        answers.push(d)
        return d.promise
      }
      return Promise.reject(new Error('no register here'))
    }))
    const { api, settingsApplied, wrapper } = await mountChatModels()
    expect(answers).toHaveLength(1)

    let returned = false
    const waiting = api.refresh().then(() => { returned = true })
    expect(answers).toHaveLength(1)

    settingsApplied()
    expect(answers).toHaveLength(2)

    answers[0]!.resolve(listOf('before/a'))
    await flushPromises()
    expect(returned).toBe(false)
    expect(api.chosenModels.value.map(m => m.id)).toEqual([])

    answers[1]!.resolve(listOf('after/b'))
    await waiting
    expect(api.chosenModels.value.map(m => m.id)).toEqual(['after/b'])
    wrapper.unmount()
  })

  it('asks again when a surface is built, the list from before standing until the answer', async () => {
    let n = 0
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (String(url).includes('/api/chat/models')) {
        n++
        return Promise.resolve(listOf(n === 1 ? 'first/a' : 'second/b'))
      }
      return Promise.reject(new Error('no register here'))
    }))
    const first = await mountChatModels()
    await flushPromises()
    expect(first.api.chosenModels.value.map(m => m.id)).toEqual(['first/a'])
    first.wrapper.unmount()

    const { useChatModels } = await import('../useChatModels')
    let api!: ReturnType<typeof useChatModels>
    const Probe = defineComponent({ setup() { api = useChatModels(); return () => h('div') } })
    const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: {} } })
    const again = mount(Probe, { global: { plugins: [i18n] } })
    expect(api.chosenModels.value.map(m => m.id)).toEqual(['first/a'])
    await flushPromises()
    expect(n).toBe(2)
    expect(api.chosenModels.value.map(m => m.id)).toEqual(['second/b'])
    again.unmount()
  })
})
