/**
 * The Canvas's keys: Escape ends a connection being drawn wherever the focus
 * stands, and Delete removes a node only outside a field.
 *
 * Until the second review of 2026-10-10 the field check stood first, so a
 * connection started while a field had the focus could not be cancelled from
 * the keyboard. Read off the source: the handler is not exposed, and mounting
 * the workspace with its stores is not what this spec is about.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const SOURCE = readFileSync(resolve(__dirname, '..', 'CanvasWorkspace.vue'), 'utf-8')

function handler(): string {
  const start = SOURCE.indexOf('function onKeyDown(e: KeyboardEvent) {')
  expect(start, 'no onKeyDown in CanvasWorkspace.vue').toBeGreaterThan(-1)
  return SOURCE.slice(start, SOURCE.indexOf('\n}\n', start))
}

describe('CanvasWorkspace keys', () => {
  it('cancels a connection on Escape before asking whether a field has the focus', () => {
    const body = handler()
    const escape = body.indexOf("e.key === 'Escape'")
    const field = body.indexOf('isWritingTarget(e.target)')
    expect(escape).toBeGreaterThan(-1)
    expect(field).toBeGreaterThan(-1)
    expect(escape).toBeLessThan(field)
  })

  it('still asks whether a field has the focus before a Delete removes a node', () => {
    const body = handler()
    expect(body.indexOf('isWritingTarget(e.target)')).toBeLessThan(body.indexOf("e.key === 'Delete'"))
  })
})
