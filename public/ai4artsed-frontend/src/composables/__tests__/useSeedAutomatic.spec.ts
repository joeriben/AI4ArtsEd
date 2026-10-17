import { describe, it, expect, beforeEach } from 'vitest'
import { ref, effectScope } from 'vue'
import { useSeedAutomatic, STANDARD_SEED } from '../useSeedAutomatic'

const KEY = 'test_seed_yardstick'

function setup(start: unknown = STANDARD_SEED, random = false) {
  const seed = ref(start as number)
  const tick = ref(random)
  return { seed, tick, ...useSeedAutomatic(seed, tick, KEY) }
}

/** A press whose picture arrives. */
function run(a: ReturnType<typeof setup>, inputs: string): number {
  const s = a.seedForRun(inputs)
  a.arrived(inputs, s)
  return s
}

beforeEach(() => sessionStorage.clear())

describe('useSeedAutomatic', () => {
  it('runs a first run on the number in the field', () => {
    const a = setup()
    expect(run(a, 'k1')).toBe(STANDARD_SEED)
    expect(a.seed.value).toBe(STANDARD_SEED)
  })

  it('draws a new seed when nothing changed, and writes it into the field', () => {
    const a = setup()
    run(a, 'k1')
    const second = run(a, 'k1')
    expect(second).not.toBe(STANDARD_SEED)
    expect(a.seed.value).toBe(second)
    expect(run(a, 'k1')).not.toBe(second)
  })

  it('keeps the seed when something changed', () => {
    const a = setup()
    run(a, 'k1')
    const drawn = run(a, 'k1')
    expect(run(a, 'k2')).toBe(drawn)
    expect(run(a, 'k3')).toBe(drawn)
  })

  it('takes a typed seed, whether or not anything else changed, and goes on from it', () => {
    const a = setup()
    run(a, 'k1')
    a.seed.value = 42
    expect(run(a, 'k1')).toBe(42)
    expect(run(a, 'k2')).toBe(42)
    a.seed.value = 7
    expect(run(a, 'k2')).toBe(7)
  })

  it('draws on every run under the tick, also when something changed', () => {
    const a = setup(STANDARD_SEED, true)
    const s1 = run(a, 'k1')
    const s2 = run(a, 'k2')
    const s3 = run(a, 'k2')
    expect(s1).not.toBe(STANDARD_SEED)
    expect(new Set([s1, s2, s3]).size).toBe(3)
    expect(a.seed.value).toBe(s3)
  })

  it('goes on from the drawn seed when the tick is taken off', () => {
    const a = setup(STANDARD_SEED, true)
    const drawn = run(a, 'k1')
    a.tick.value = false
    expect(run(a, 'k2')).toBe(drawn)
  })

  it('treats a cleared, negative or fractional field as holding no seed', () => {
    for (const bad of ['', -5, 12.5]) {
      sessionStorage.clear()
      const a = setup(bad)
      expect(run(a, 'k1')).toBe(STANDARD_SEED)
      const drawn = run(a, 'k1')
      a.seed.value = bad as number
      expect(run(a, 'k2')).toBe(drawn)
    }
  })

  it('asks a run that made no picture again with its seed, and a change takes the picture seed', () => {
    const a = setup()
    const s1 = run(a, 'k1')
    // Nothing changed: a variation is drawn, and that run fails.
    const drawn = a.seedForRun('k1')
    expect(drawn).not.toBe(s1)
    // Pressed again unchanged: the same run, the same seed.
    expect(a.seedForRun('k1')).toBe(drawn)
    // A slider moved instead: the change is shown on the picture's seed.
    expect(a.seedForRun('k2')).toBe(s1)
    expect(a.seed.value).toBe(s1)
  })

  it('compares with the last picture, not with a blocked run', () => {
    const a = setup()
    const s1 = run(a, 'p1')
    expect(a.seedForRun('p2')).toBe(s1) // blocked
    expect(a.seedForRun('p1')).not.toBe(s1)
  })

  it('keeps its yardstick across a remount', () => {
    const a = setup()
    const s1 = run(a, 'k1')
    // Mounted afresh: the field comes back from the instrument's own storage.
    expect(setup(s1).seedForRun('k1')).not.toBe(s1)
    sessionStorage.clear()
    const b = setup()
    const t1 = run(b, 'k1')
    expect(setup(t1).seedForRun('k2')).toBe(t1)
  })

  it('keeps nothing in storage without a key: a fresh instance starts from its field', () => {
    const seed = ref(STANDARD_SEED)
    const a = useSeedAutomatic(seed, ref(false), null)
    a.arrived('k1', a.seedForRun('k1'))
    const s2 = a.seedForRun('k1')
    a.arrived('k1', s2)
    expect(sessionStorage.length).toBe(0)
    // Mounted afresh with the field at its default: a first run.
    expect(useSeedAutomatic(ref(-1), ref(false), null).seedForRun('k1')).toBe(STANDARD_SEED)
    // Mounted afresh, and the last seed typed back before the first press:
    // it is typed, though the old instance wrote that very number.
    const field = ref(-1)
    const b = useSeedAutomatic(field, ref(false), null)
    field.value = s2
    expect(b.seedForRun('k1')).toBe(s2)
  })

  it('writes nothing once taken down: a run landing in the old instance leaves the new one alone', () => {
    const scope = effectScope()
    const seed = ref(STANDARD_SEED)
    const tick = ref(false)
    const old = scope.run(() => useSeedAutomatic(seed, tick, KEY))!
    old.arrived('k1', old.seedForRun('k1'))
    const going = old.seedForRun('k1')
    scope.stop()
    const fresh = setup(going)
    old.arrived('k1', going)
    // The new instance never saw that picture: unchanged is still a variation.
    expect(fresh.seedForRun('k1')).not.toBe(going)
    expect(JSON.parse(sessionStorage.getItem(KEY)!).seed).toBe(STANDARD_SEED)
  })

  it('compares with a picture laid back: unchanged draws, changed keeps its seed', () => {
    const a = setup()
    run(a, 'k1')
    a.laidBack('restored', 555)
    expect(a.seed.value).toBe(555)
    expect(a.seedForRun('k9')).toBe(555)

    sessionStorage.clear()
    const b = setup()
    b.laidBack('restored', 555)
    expect(b.seedForRun('restored')).not.toBe(555)
  })

  it('keeps the picture seed on the next press when the record was not read back whole', () => {
    const a = setup()
    a.laidBack(null, 555)
    expect(a.seedForRun('anything')).toBe(555)
  })

  it('takes the field after a picture laid back that names no seed', () => {
    const a = setup(999)
    a.laidBack('restored', null)
    expect(a.seed.value).toBe(999)
    expect(a.seedForRun('restored')).toBe(999)
  })

  it('lets the field follow the picture that arrives last, unless a number was typed meanwhile', () => {
    // A run is going; the picture of an earlier run is laid back; then the
    // going run arrives and its picture stands on the surface.
    const a = setup()
    const s1 = run(a, 'k1')
    const s2 = a.seedForRun('k1')
    a.laidBack('k1', s1)
    a.arrived('k1', s2)
    expect(a.seed.value).toBe(s2)

    // A number typed while a run is going stays in the field and goes next,
    // also when it is the previous picture's seed.
    sessionStorage.clear()
    const b = setup()
    const t1 = run(b, 'k1')
    const going = b.seedForRun('k1')
    b.seed.value = t1
    b.arrived('k1', going)
    expect(b.seed.value).toBe(t1)
    expect(b.seedForRun('k1')).toBe(t1)
  })
})
