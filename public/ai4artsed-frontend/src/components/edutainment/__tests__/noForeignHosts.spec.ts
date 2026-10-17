/**
 * The animations load nothing from a foreign host.
 *
 * The forest mini game drew its bird from a CodePen asset on amazonaws.com,
 * and the game is one of three animations the output box rotates through in
 * the kids and youth modes: every third generation connected the browser of a
 * participant to amazonaws.com (finding S-018 of the code review of 2026-10-10). The platform made exactly that
 * connection the reason for its Commons proxy. Since 2026-10-10 the sprite is
 * served from the platform's own origin (public/images).
 */
import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const EDUTAINMENT = join(HERE, '..')

describe('the edutainment components', () => {
  it('name no http(s) address', () => {
    const offenders: string[] = []
    for (const name of readdirSync(EDUTAINMENT)) {
      if (!name.endsWith('.vue') && !name.endsWith('.ts')) continue
      const text = readFileSync(join(EDUTAINMENT, name), 'utf8')
      text.split('\n').forEach((line, index) => {
        // An XML namespace (xmlns="http://www.w3.org/2000/svg") names no host
        // the browser connects to; everything else with a scheme does.
        const addresses = line.match(/https?:\/\/[^\s"'`)]+/g) || []
        if (addresses.some(a => !a.startsWith('http://www.w3.org/'))) {
          offenders.push(`${name}:${index + 1}`)
        }
      })
    }
    expect(offenders).toEqual([])
  })
})
