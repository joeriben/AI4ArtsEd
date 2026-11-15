import { afterEach, describe, expect, it } from 'vitest'
import { modelLabelDrop, modelLabelLine, modelLabelLines } from '@/lib/modelAxisLabel'

describe('modelLabelLines', () => {
  it('puts the bracket after the name on a line of its own', () => {
    expect(modelLabelLines('Qwen1.5 7B (02/2024)')).toEqual(['Qwen1.5 7B', '(02/2024)'])
  })

  it('leaves a name without a bracket on one line', () => {
    expect(modelLabelLines('Ministral 3 14B')).toEqual(['Ministral 3 14B'])
  })

  it('cuts at the first bracket and keeps what follows it together', () => {
    expect(modelLabelLines('Qwen 3.8 (China 2026) 27b')).toEqual(['Qwen 3.8', '(China 2026) 27b'])
  })

  it('does not cut a label that is nothing but the bracket', () => {
    expect(modelLabelLines('(02/2024)')).toEqual(['(02/2024)'])
  })
})

describe('modelLabelDrop', () => {
  afterEach(() => {
    document.documentElement.style.fontSize = ''
  })

  it('is nothing while every name has one line', () => {
    document.documentElement.style.fontSize = '16px'
    expect(modelLabelDrop(['Qwen3 4B', 'Qwen3 8B'])).toBe(0)
    expect(modelLabelDrop([])).toBe(0)
  })

  it('is one line as soon as one name has two', () => {
    document.documentElement.style.fontSize = '16px'
    expect(modelLabelDrop(['Qwen3 8B', 'Qwen3.5 9B (02/2026)'])).toBe(16)
  })

  it('grows with the reader\'s font setting', () => {
    document.documentElement.style.fontSize = '20px'
    expect(modelLabelLine()).toBe(20)
    expect(modelLabelDrop(['Qwen3.5 9B (02/2026)'])).toBe(20)
  })
})
