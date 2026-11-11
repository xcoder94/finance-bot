import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(__dirname, '..', 'index.css'), 'utf8')

/** Body of the first rule with exactly this selector inside the @media (max-width: 360px) block. */
function narrowRule(selector: string): string {
  const mediaStart = css.indexOf('/* P1 polish: 320 px truncation */')
  expect(mediaStart).toBeGreaterThan(-1)
  const media = css.slice(mediaStart, css.indexOf('/* end P1 polish */', mediaStart))
  expect(media).toContain('@media (max-width: 360px)')
  const start = media.indexOf(`${selector} {`)
  expect(start).toBeGreaterThan(-1)
  return media.slice(start, media.indexOf('}', start))
}

describe('frequent-category chips are capped and truncated (designer P1)', () => {
  const start = css.indexOf('\n.recent-category-chips .date-chip {')
  const rule = css.slice(start, css.indexOf('}', start))
  it('a long label cannot take the whole row', () => {
    expect(start).toBeGreaterThan(-1)
    expect(rule).toContain('max-width: 60%')
    expect(rule).toContain('overflow: hidden')
    expect(rule).toContain('text-overflow: ellipsis')
    expect(rule).toContain('white-space: nowrap')
  })
})

describe('history rows at 320 px give the title room and never cut the amount (designer P1)', () => {
  it('title is never broken in the middle of a word: wraps by words or is cut with an ellipsis', () => {
    const media = css.slice(css.indexOf('/* P1 polish: 320 px truncation */'), css.indexOf('/* end P1 polish */'))
    expect(media).not.toContain('overflow-wrap: anywhere')
    expect(media).not.toContain('word-break: break-all')
    const base = css.match(/\n\.home-ops-row__title \{[^}]*\}/)?.[0] ?? ''
    expect(base).toContain('text-overflow: ellipsis')
    expect(base).toContain('white-space: nowrap')
  })
  it('amount steps down to 13px and still never wraps or gets cut', () => {
    const rule = narrowRule('.home-ops-row__amount')
    expect(rule).toContain('font-size: 13px')
    expect(rule).not.toContain('overflow')
    expect(rule).not.toContain('text-overflow')
  })
  it('the meta line stays on one line (rule untouched in the narrow block)', () => {
    expect(css).toMatch(/\.home-ops-row__meta \{[^}]*white-space: nowrap/)
  })
})
