import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(__dirname, '..', 'index.css'), 'utf8')

function block(selector: string): string {
  const start = css.indexOf(`\n${selector} {`)
  expect(start).toBeGreaterThan(-1)
  return css.slice(start, css.indexOf('}', start))
}

// B5 round 2: an amount never breaks and is never cut with an ellipsis; the font steps down / the title shrinks
describe('amount cells are never cut (B5)', () => {
  for (const selector of [
    '.home-figures-card__balance',
    '.home-figures-card__stat-value',
    '.home-ops-row__amount',
  ]) {
    it(`${selector}: nowrap, no ellipsis, no hidden overflow`, () => {
      const b = block(selector)
      expect(b).toContain('white-space: nowrap')
      expect(b).not.toContain('overflow: hidden')
      expect(b).not.toContain('text-overflow')
    })
  }
  it('the amount side of an operation row does not shrink, the title does', () => {
    expect(block('.home-ops-row__aside')).toContain('flex: none')
    expect(block('.home-ops-row > .home-ops-row__amount')).toContain('flex: none')
    expect(block('.home-ops-row__main')).toContain('min-width: 0')
  })
  it('half-width stat cells may shrink', () => {
    expect(block('.home-figures-card__stat')).toContain('min-width: 0')
  })
})

// B14: the title of a screen that already has the 14px page padding must not add its own 16px
describe('screen title alignment (B14)', () => {
  it('title inside .wallets-page has no horizontal padding of its own', () => {
    const b = block('.wallets-page > .screen-title')
    expect(b).toMatch(/padding-left:\s*0/)
    expect(b).toMatch(/padding-right:\s*0/)
  })
})
