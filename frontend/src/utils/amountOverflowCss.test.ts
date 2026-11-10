import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(__dirname, '..', 'index.css'), 'utf8')

function block(selector: string): string {
  const start = css.indexOf(`\n${selector} {`)
  expect(start).toBeGreaterThan(-1)
  return css.slice(start, css.indexOf('}', start))
}

// B5: an amount never breaks; the line shrinks/ellipsizes as a whole
describe('amount cells do not break or overflow (B5)', () => {
  for (const selector of [
    '.home-figures-card__balance',
    '.home-figures-card__stat-value',
    '.home-ops-row__amount',
  ]) {
    it(`${selector}: nowrap + ellipsis`, () => {
      const b = block(selector)
      expect(b).toContain('white-space: nowrap')
      expect(b).toContain('overflow: hidden')
      expect(b).toContain('text-overflow: ellipsis')
    })
  }
  it('flex parents may shrink', () => {
    expect(block('.home-figures-card__stat')).toContain('min-width: 0')
    expect(block('.home-ops-row__aside')).toContain('min-width: 0')
  })
})
