/**
 * Two things the registry forbids and the code review of 2026-10-10 found
 * anyway (S-038, S-016):
 *
 *  - `v-html` in a template. Authored prose goes through EmphasisText or
 *    MarkdownLiteText, which never make an element out of a string; the two
 *    settings strings and the landing page's icons were the last three uses.
 *  - the server's response body on the screen of an instrument. The line
 *    under a field says the platform's sentence with the status in it
 *    (`generationErrorFor`); the body stays in the log (registry, `useLabRun`).
 *    Seven instruments still read `err.response?.data?.error` into their line.
 */
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

const SRC = join(__dirname, '..', '..')

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) {
      if (name === '__tests__' || name === 'node_modules') continue
      walk(path, out)
    } else if (name.endsWith('.vue')) {
      out.push(path)
    }
  }
  return out
}

describe('no v-html, no server body on screen', () => {
  it('no template renders a string as HTML', () => {
    const offenders = walk(SRC)
      // The template is what is left once every script block is struck; in
      // eighteen files the script stands before the template.
      .filter((path) => /\bv-html\s*=/.test(readFileSync(path, 'utf8').replace(/<script\b[\s\S]*?<\/script>/g, '')))
      .map((path) => relative(SRC, path))
    expect(offenders).toEqual([])
  })

  it('no instrument reads the response body into its error line', () => {
    const offenders: string[] = []
    for (const dir of ['views/latent_lab', 'views/compare']) {
      for (const path of walk(join(SRC, dir))) {
        const text = readFileSync(path, 'utf8')
        text.split('\n').forEach((line, i) => {
          // The body may be handed to generationErrorFor, which reads it for
          // the classifier and answers the platform's sentence; it may not
          // stand in the line itself.
          if (/response\??\.data\??\.error\s*\|\|/.test(line) && !/generationErrorFor\(/.test(line)) {
            offenders.push(`${relative(SRC, path)}:${i + 1}`)
          }
        })
      }
    }
    expect(offenders).toEqual([])
  })
})
