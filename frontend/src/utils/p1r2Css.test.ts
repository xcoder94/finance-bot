import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(__dirname, '..', 'index.css'), 'utf8')

function rule(selector: string): string {
  const match = new RegExp(`\\n${selector.replace(/[.[\]]/g, '\\$&')}(,|\\s*\\{)`).exec(css)
  const start = match ? match.index : -1
  expect(start, `rule ${selector} exists`).toBeGreaterThan(-1)
  return css.slice(css.indexOf('{', start), css.indexOf('}', start))
}

// P1 round 2 (QA P1-8): the spinner of a filled button must not be the accent colour on the accent background
describe('spinner inside a filled button is visible (P1-8)', () => {
  for (const button of ['.transaction-form__action-button', '.form-sheet-primary']) {
    it(`${button}: spinner takes the button text colour, not the accent`, () => {
      const b = rule(`${button} [role='status']`)
      expect(b).toContain('color: var(--acct)')
    })
  }
})

// P1 round 2 (QA P1-2): the range block is a single column, not the old two-column history grid
describe('range block layout (P1-2)', () => {
  it('the DateRangeFields root does not use the two-column history grid class', () => {
    const src = readFileSync(join(__dirname, '..', 'components', 'DateRangeFields.tsx'), 'utf8')
    expect(src).not.toContain('history-page__range-fields')
  })
  it('the old two-column grid rule is gone', () => {
    expect(css).not.toContain('.history-page__range-fields')
  })
})
