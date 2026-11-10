import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) {
      return sources(path)
    }
    return /\.(ts|tsx)$/.test(name) ? [path] : []
  })
}

describe('PRD-ux U1: no masked date input', () => {
  it('src has no MaskedDate helpers or components', () => {
    const needle = ['Masked', 'Date'].join('')
    const offenders = sources(join(__dirname)).filter(
      (path) => !path.endsWith('noMaskedDate.test.ts') && readFileSync(path, 'utf8').includes(needle),
    )
    expect(offenders).toEqual([])
  })
})
