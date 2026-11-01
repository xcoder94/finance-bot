import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const css = readFileSync(new URL('./index.css', import.meta.url), 'utf8')
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8')

const block = (selector: string) => {
  const m = css.match(new RegExp(`${selector.replace(/[.[\]()]/g, '\\$&')}\\s*\\{([^}]*)\\}`))
  return m ? m[1] : ''
}

describe('iOS focus zoom (dev-fix2)', () => {
  it('global rule keeps every input, textarea and select at 16px or more', () => {
    expect(css).toMatch(
      /:is\(input, textarea, select\):not\(\[type='checkbox'\]\):not\(\[type='radio'\]\)\s*\{[^}]*font-size:\s*max\(16px,\s*1em\)/,
    )
  })
  it('no field class sets a size below 16px', () => {
    for (const sel of ['.shopping-add__input', '.admin-search', '.form-sheet-field__input--mono']) {
      const m = block(sel).match(/font-size:\s*([\d.]+)px/)
      if (m) expect(Number(m[1]), sel).toBeGreaterThanOrEqual(16)
    }
  })
  it('zoom is not switched off (accessibility)', () => {
    expect(html).not.toMatch(/maximum-scale|user-scalable/i)
  })
})
