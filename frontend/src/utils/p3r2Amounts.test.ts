import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement } from 'react'

import i18n from '../i18n'
import { formatCurrency } from './formatCurrency'
import { buildComparisonLine } from './analyticsComparison'
import { HistorySummaryLine } from '../pages/analytics/HistorySummaryLine'

const css = readFileSync(new URL('../index.css', import.meta.url), 'utf8')
function cssRule(selector: string): string {
  const start = css.indexOf(`\n${selector} {`)
  expect(start, `rule ${selector}`).toBeGreaterThan(-1)
  return css.slice(start, css.indexOf('}', start))
}

describe('amounts at 320 px (QA P3 round 2)', () => {
  it('personal block: stats wrap onto the next line instead of running past the edge', () => {
    expect(cssRule('.home-personal-card__stats')).toContain('flex-wrap: wrap')
    const stat = cssRule('.home-personal-card__stat')
    expect(stat).toContain('min-width: max-content')
    expect(cssRule('.home-personal-card__stat-value')).toContain('white-space: nowrap')
  })
  it('«left per day» plates: the unit may drop to a second line, the number stays whole', () => {
    expect(cssRule('.home-left__value')).not.toContain('white-space: nowrap')
    expect(cssRule('.home-left__num')).toContain('white-space: nowrap')
  })
  it('goal card: saved and target wrap as two lines when they do not fit', () => {
    expect(cssRule('.goals-card__amounts')).toContain('flex-wrap: wrap')
  })
  it('day total in History may break between currencies, not inside an amount', () => {
    expect(cssRule('.history-day__total')).not.toContain('white-space: nowrap')
  })
  it('History summary: «Расход» and its amount never part', async () => {
    await i18n.changeLanguage('ru')
    const html = renderToStaticMarkup(
      createElement(HistorySummaryLine, {
        summary: { by_currency: [{ currency: 'UZS', income: 5, expense: 7 }] } as never,
      }),
    )
    expect(html).toContain('Расход 7')
    expect(html).toContain('Доход 5')
  })
})

describe('minus sign is «−» everywhere (QA P4)', () => {
  it('formatCurrency', async () => {
    await i18n.changeLanguage('ru')
    expect(formatCurrency(-444444, 'UZS')).toBe('−444 444 сум')
    expect(formatCurrency(-5, 'USD')).toBe('−$5')
  })
})

describe('comparison percent has digit groups (QA P4)', () => {
  it('1483983% reads 1 483 983%', async () => {
    await i18n.changeLanguage('ru')
    const line = buildComparisonLine({
      total: 14_840_830,
      prevTotal: 1000,
      periodTab: 'month',
      selectedMonth: { year: 2026, month: 11 },
      rangeDays: 30,
    })
    expect(line).toMatch(/1[\u00a0 ]483[\u00a0 ]983%/)
  })
})
