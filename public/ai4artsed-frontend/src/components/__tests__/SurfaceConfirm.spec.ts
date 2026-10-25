/**
 * The one decision a surface asks before it acts (components/SurfaceConfirm.vue).
 */
import { describe, it, expect, afterEach } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import SurfaceConfirm from '../SurfaceConfirm.vue'

const props = { text: 'Place 2 gets a new code.', yes: 'Replace code', cancel: 'Cancel' }

let wrapper: VueWrapper | undefined
let host: HTMLElement | undefined

function mountIn(extra: Record<string, unknown> = {}) {
  host = document.createElement('div')
  document.body.appendChild(host)
  wrapper = mount(SurfaceConfirm, { props: { ...props, ...extra }, attachTo: host })
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  host?.remove()
  host = undefined
})

describe('SurfaceConfirm', () => {
  it('stands in its surface', () => {
    mountIn()
    expect(host!.querySelector('.action-confirm-row')).not.toBeNull()
    expect(document.body.querySelector(':scope > .action-confirm-row')).toBeNull()
  })

  it('stands at the end of the document over the app', () => {
    mountIn({ overApp: true })
    expect(host!.querySelector('.action-confirm-row')).toBeNull()
    const row = document.body.querySelector(':scope > .action-confirm-row.over-app')
    expect(row).not.toBeNull()
    wrapper!.unmount()
    wrapper = undefined
    expect(document.body.querySelector('.action-confirm-row')).toBeNull()
  })

  it('says its sentence and answers with the button pressed', async () => {
    mountIn({ danger: true })
    expect(wrapper!.text()).toContain('Place 2 gets a new code.')
    const [yes, cancel] = wrapper!.findAll('button')
    expect(yes!.text()).toBe('Replace code')
    expect(yes!.classes()).toContain('danger')
    expect(cancel!.text()).toBe('Cancel')
    await yes!.trigger('click')
    await cancel!.trigger('click')
    expect(wrapper!.emitted('confirm')).toHaveLength(1)
    expect(wrapper!.emitted('cancel')).toHaveLength(1)
  })

  it('holds the yes back while disabled', () => {
    mountIn({ disabled: true })
    const [yes, cancel] = wrapper!.findAll('button')
    expect(yes!.attributes('disabled')).toBeDefined()
    expect(cancel!.attributes('disabled')).toBeUndefined()
  })

  it.each([false, true])('keeps a file dropped on the row from opening (over the app: %s)', (overApp) => {
    mountIn({ overApp })
    const row = document.body.querySelector('.action-confirm-row')!
    for (const type of ['dragover', 'drop']) {
      const event = new Event(type, { bubbles: true, cancelable: true })
      row.dispatchEvent(event)
      expect(event.defaultPrevented).toBe(true)
    }
  })
})
