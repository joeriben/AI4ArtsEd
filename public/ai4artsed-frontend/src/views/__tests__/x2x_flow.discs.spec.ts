/**
 * The discs on the flow board: a perspective and a LoRA lying on the table.
 *
 * A press on a disc drags it, however long the press stands still before it
 * moves, and a click opens the disc's one box. The pointer is a mouse or a
 * trackpad, which is how the platform is operated, on a tablet too.
 * For a time a disc also opened the
 * platform's InfoCard, after a pointer had rested on it
 * for 350 ms and on a long press, and the card coming up ended the drag: a
 * drag that lasted longer than that stopped under the hand, and hover and click
 * left two boxes with the same text standing side by side.
 * The marks at a disc's rim stopped the press, so the disc could not be
 * picked up by them. Every case below failed against that version, except
 * the two with a ctrl-click: those hold what stays, a mouse's context menu
 * ends the drag.
 *
 * The waits are real and longer than both of the platform's gesture times
 * (the 350 ms rest of `useInfoCard`, the 450 ms hold of `useHold`), so a card
 * or a hold that came back would have had its moment. The view is attached to
 * the document: a detached element never gets a card, and the test would pass
 * for the wrong reason.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import i18n from '@/i18n'
import X2X from '../x2x_flow.vue'

class NoWatcher {
  observe() {}
  unobserve() {}
  disconnect() {}
}
const browser = globalThis as any
browser.ResizeObserver ??= NoWatcher
browser.IntersectionObserver ??= NoWatcher
browser.requestAnimationFrame ??= (cb: (t: number) => void) =>
  setTimeout(() => cb(0), 0) as unknown as number
browser.cancelAnimationFrame ??= (id: number) => clearTimeout(id as never)
browser.matchMedia ??= () => ({
  matches: false,
  media: '',
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {},
})
browser.scrollTo ??= () => {}

class NoStream {
  addEventListener() {}
  removeEventListener() {}
  close() {}
}

/** The config list is empty; a disc asks it which adapters its preset brings. */
function answer(input: unknown): Response {
  const body = String(input).includes('/pipeline_configs_with_properties') ? { configs: [] } : {}
  return {
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response
}

/** Longer than the 350 ms rest and the 450 ms hold. */
const LONGER_THAN_ANY_GESTURE = 600
const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

function pointer(type: string, x: number, y: number, pointerType: string, buttons = 1) {
  return new PointerEvent(type, {
    bubbles: type !== 'pointerenter' && type !== 'pointerleave',
    cancelable: true,
    clientX: x,
    clientY: y,
    pointerId: 1,
    pointerType,
    isPrimary: true,
    button: 0,
    buttons,
  })
}

function click(el: Element, x: number, y: number) {
  el.dispatchEvent(
    new MouseEvent('click', { bubbles: true, cancelable: true, clientX: x, clientY: y, detail: 1 })
  )
}

/** Where the disc lies, in the world's pixels. */
function place(el: HTMLElement) {
  return { x: parseFloat(el.style.left), y: parseFloat(el.style.top) }
}

/** No InfoCard anywhere: it is teleported to the body, so it is looked for there. */
function cards() {
  return document.body.querySelectorAll('.info-card').length
}

let w: VueWrapper<any>

beforeEach(async () => {
  setActivePinia(createPinia())
  sessionStorage.clear()
  sessionStorage.setItem(
    't2i_perspectives2',
    JSON.stringify([
      { id: 'p1', configId: 'bauhaus', configName: 'Bauhaus', context: 'Form follows function.', x: 1400, y: 900 },
    ])
  )
  sessionStorage.setItem(
    't2i_loras',
    JSON.stringify([
      {
        id: 'l1',
        file: 'solarization.safetensors',
        name: 'solarization',
        trigger: 'solarization',
        baseConfigs: ['sd35_large'],
        strength: 80,
        x: 1700,
        y: 900,
      },
    ])
  )
  vi.stubGlobal('fetch', vi.fn(async (input: unknown) => answer(input)))
  vi.stubGlobal('EventSource', NoStream)
  w = mount(X2X, { global: { plugins: [i18n] }, attachTo: document.body })
  await flushPromises()
})

afterEach(() => {
  w?.unmount()
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

describe.each([
  ['perspective', '.pb:not(.lora-tile)', '.persp-edit:not(.lora-edit)'],
  ['LoRA', '.pb.lora-tile', '.lora-edit'],
])('the %s disc on the board', (_kind, discSel, boxSel) => {
  const disc = () => w.find(discSel).element as HTMLElement

  it('follows a press that stood still first, and opens nothing', async () => {
    const el = disc()
    const before = place(el)
    el.dispatchEvent(pointer('pointerenter', 100, 100, 'mouse', 0))
    el.dispatchEvent(pointer('pointerdown', 100, 100, 'mouse'))
    await wait(LONGER_THAN_ANY_GESTURE)
    window.dispatchEvent(pointer('pointermove', 160, 130, 'mouse'))
    await flushPromises()
    const zoom = w.vm.zoom as number
    const after = place(el)
    expect(after.x - before.x).toBeCloseTo(60 / zoom)
    expect(after.y - before.y).toBeCloseTo(30 / zoom)
    expect(cards()).toBe(0)
    // The click the browser sends at the end of the drag opens nothing.
    window.dispatchEvent(pointer('pointerup', 160, 130, 'mouse', 0))
    click(el, 160, 130)
    await flushPromises()
    expect(document.body.querySelectorAll(boxSel).length).toBe(0)
    expect(cards()).toBe(0)
  })

  it('lets go of a mouse whose ctrl-click opened the context menu', async () => {
    const el = disc()
    const before = place(el)
    el.dispatchEvent(pointer('pointerdown', 100, 100, 'mouse'))
    window.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }))
    window.dispatchEvent(pointer('pointermove', 160, 130, 'mouse'))
    await flushPromises()
    expect(place(el)).toEqual(before)
  })

  it('opens its one box on a click, and nothing else beside it', async () => {
    const el = disc()
    el.dispatchEvent(pointer('pointerenter', 100, 100, 'mouse', 0))
    await wait(LONGER_THAN_ANY_GESTURE)
    el.dispatchEvent(pointer('pointerdown', 100, 100, 'mouse'))
    window.dispatchEvent(pointer('pointerup', 100, 100, 'mouse', 0))
    click(el, 100, 100)
    await flushPromises()
    // The pointer leaves the disc for the box and comes back to it.
    el.dispatchEvent(pointer('pointerleave', 100, 100, 'mouse', 0))
    el.dispatchEvent(pointer('pointerenter', 100, 100, 'mouse', 0))
    await wait(LONGER_THAN_ANY_GESTURE)
    expect(document.body.querySelectorAll(boxSel).length).toBe(1)
    expect(cards()).toBe(0)
  })
})

it('picks the LoRA tile up by its strength mark', async () => {
  const el = w.find('.pb.lora-tile').element as HTMLElement
  const mark = w.find('.pb.lora-tile .pb-pct').element as HTMLElement
  const before = place(el)
  mark.dispatchEvent(pointer('pointerdown', 100, 100, 'mouse'))
  window.dispatchEvent(pointer('pointermove', 160, 130, 'mouse'))
  await flushPromises()
  const zoom = w.vm.zoom as number
  expect(place(el).x - before.x).toBeCloseTo(60 / zoom)
  window.dispatchEvent(pointer('pointerup', 160, 130, 'mouse', 0))
  click(mark, 160, 130)
  await flushPromises()
  expect(document.body.querySelectorAll('.lora-edit').length).toBe(0)
})
