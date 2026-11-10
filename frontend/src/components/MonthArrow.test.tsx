import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'

import { MonthArrow } from './MonthArrow'

describe('MonthArrow', () => {
  it('renders an svg icon, not a text glyph, with an aria-label', () => {
    const html = renderToStaticMarkup(<MonthArrow direction="prev" label="Предыдущий месяц" onClick={() => {}} />)
    expect(html).toContain('<svg')
    expect(html).toContain('aria-label="Предыдущий месяц"')
    expect(html).not.toContain('‹')
  })

  it('has a 44x44 tap zone', () => {
    const css = readFileSync(new URL('../index.css', import.meta.url), 'utf8')
    const rule = css.match(/\.month-arrow \{[^}]*\}/)?.[0] ?? ''
    expect(rule).toContain('width: 44px')
    expect(rule).toContain('height: 44px')
  })

  it('every month switch uses it (no text arrows left)', () => {
    for (const f of ['../pages/HomePage.tsx', './PeriodFilterControls.tsx', './wallets/WalletOpsView.tsx']) {
      const src = readFileSync(new URL(f, import.meta.url), 'utf8')
      expect(src).toContain('<MonthArrow')
      expect(src).not.toMatch(/>\s*[‹]\s*</)
    }
  })
})
