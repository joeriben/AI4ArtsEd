/**
 * A key pressed in a field edits the field.
 *
 * The direct-writing composable has always asked this of a key event's target;
 * since 2026-10-10 the Canvas workspace asks the same question before a Delete
 * removes the selected node, because a node stays selected while its own text
 * is written and a Delete in that field removed the node with its text
 * (finding S-019 of the code review of 2026-10-10). One answer, exported from where it stood.
 */
import { describe, it, expect } from 'vitest'
import { isWritingTarget } from '../useDirectWriting'

describe('isWritingTarget', () => {
  it('is true for a field, a text area, a select and anything contenteditable', () => {
    for (const tag of ['input', 'textarea', 'select']) {
      expect(isWritingTarget(document.createElement(tag))).toBe(true)
    }
    // jsdom carries no isContentEditable; the browser's answer is stood in.
    const editable = document.createElement('div')
    Object.defineProperty(editable, 'isContentEditable', { value: true })
    expect(isWritingTarget(editable)).toBe(true)
  })

  it('is false for the surface itself and for nothing', () => {
    expect(isWritingTarget(document.createElement('div'))).toBe(false)
    expect(isWritingTarget(document.body)).toBe(false)
    expect(isWritingTarget(null)).toBe(false)
  })
})
