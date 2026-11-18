import { beforeEach, describe, expect, it } from 'vitest'
import { keepSignInTab, lastSignInTab } from '../signInTab'

beforeEach(() => localStorage.clear())

describe('the tab of the last sign-in', () => {
  it('is none before a sign-in', () => {
    expect(lastSignInTab()).toBeNull()
  })

  it('is the tab kept at the sign-in', () => {
    keepSignInTab('educator')
    expect(lastSignInTab()).toBe('educator')
    keepSignInTab('participant')
    expect(lastSignInTab()).toBe('participant')
  })

  it('is none where the browser holds something else under its name', () => {
    localStorage.setItem('ai4artsed.signInTab', 'admin')
    expect(lastSignInTab()).toBeNull()
  })
})
