import { describe, it, expect, vi } from 'vitest'
import { useRasterRun } from '../useRasterRun'

// The composable registers an unmount hook; outside a component Vue only says
// so in the console.
vi.spyOn(console, 'warn').mockImplementation(() => {})

describe('useRasterRun', () => {
  it('counts a plan handed over as a list by its length', async () => {
    const run = useRasterRun()
    const seen: number[] = []
    await run.start([1, 2, 3], async step => { seen.push(step) })
    expect(seen).toEqual([1, 2, 3])
    expect(run.expected.value).toBe(3)
    expect(run.done.value).toBe(3)
    expect(run.running.value).toBe(false)
  })

  it('runs a plan the surface is still writing, and leaves the count to the surface', async () => {
    const run = useRasterRun()
    run.expected.value = 4
    let release!: () => void
    const later = new Promise<void>(resolve => { release = resolve })
    async function* steps() {
      yield 'a'
      yield 'b'
      await later
      yield 'c'
    }
    const seen: string[] = []
    const going = run.start(steps(), async step => {
      seen.push(step)
      // The steps that join later arrive while the first ones run.
      if (step === 'b') release()
    })
    await going
    expect(seen).toEqual(['a', 'b', 'c'])
    expect(run.expected.value).toBe(4)
    expect(run.done.value).toBe(3)
    expect(run.running.value).toBe(false)
  })

  it('runs nothing more of a stream given up while it waited for its next step', async () => {
    const run = useRasterRun()
    let release!: () => void
    const later = new Promise<void>(resolve => { release = resolve })
    async function* steps() {
      yield 1
      await later
      yield 2
    }
    const seen: number[] = []
    const going = run.start(steps(), async step => {
      seen.push(step)
      // Given up after the first step, while the stream waits for the second.
      setTimeout(() => { run.stop(); release() }, 0)
    })
    await going
    expect(seen).toEqual([1])
    expect(run.running.value).toBe(false)
  })
})
