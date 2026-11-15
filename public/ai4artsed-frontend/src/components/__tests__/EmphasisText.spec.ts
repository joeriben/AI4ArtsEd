/**
 * A marked word is set off; an asterisk that stands for itself stays in the
 * text. The case that made the rule: Stereotype Analysis names the placeholder
 * of its prompt as „*“ and closes on „a person feeling *“, and the two were
 * read as one pair (2026-11-15).
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EmphasisText from '../EmphasisText.vue'

const render = (text: string) => mount(EmphasisText, { props: { text } })

describe('EmphasisText', () => {
  it('sets off a marked word', () => {
    const w = render('Das ist *eindeutig* so.')
    expect(w.findAll('em').map(e => e.text())).toEqual(['eindeutig'])
    expect(w.text()).toBe('Das ist eindeutig so.')
  })

  it('sets off a marked phrase in another script', () => {
    const w = render('결과는 *명확하지 않습니다* 그래서')
    expect(w.findAll('em').map(e => e.text())).toEqual(['명확하지 않습니다'])
  })

  it('keeps a quoted placeholder and a trailing placeholder as asterisks', () => {
    const text =
      'Jede Zeile ersetzt den Stern „*“ im Basis-Prompt einmal, für einen Basis-Prompt wie „a person feeling *“.'
    const w = render(text)
    expect(w.findAll('em')).toHaveLength(0)
    expect(w.text()).toBe(text)
  })

  it('keeps two quoted placeholders with straight quotes', () => {
    const text = 'Use "*" here and "*" there.'
    const w = render(text)
    expect(w.findAll('em')).toHaveLength(0)
    expect(w.text()).toBe(text)
  })

  it('keeps an unpaired asterisk and still sets off a real pair', () => {
    const w = render('A *word* and a lone * star.')
    expect(w.findAll('em').map(e => e.text())).toEqual(['word'])
    expect(w.text()).toBe('A word and a lone * star.')
  })

  it('renders an empty text as nothing', () => {
    expect(render('').text()).toBe('')
  })
})
