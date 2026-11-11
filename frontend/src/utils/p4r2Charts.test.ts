import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import type { TFunction } from 'i18next'

import { formatSharePercents, prepareDonutSlices } from './analyticsCharts'
import { CHART_CATEGORY_COLORS, OTHER_CATEGORY_COLOR, UNCATEGORIZED_COLOR } from './chartColors'
import { extendCategoryColorMap } from './analyticsChartsTab'

const css = readFileSync(new URL('../index.css', import.meta.url), 'utf8')

describe('shares add up to 100% (QA #7)', () => {
  const sum = (labels: string[]) =>
    labels.reduce((s, l) => s + (l.startsWith('<') ? 0 : Number(l.replace('%', ''))), 0)

  it('QA case 75/15/5/2/1/~0: whole numbers, total 100, tiny shown as «<1%»', () => {
    const values = [7500, 1500, 500, 200, 100, 1, 1, 1, 1]
    const labels = formatSharePercents(values)
    expect(sum(labels)).toBe(100)
    expect(labels.filter((l) => l === '<1%')).toHaveLength(4)
    expect(labels).not.toContain('0%')
  })
  it('thirds: 34/33/33', () => {
    const labels = formatSharePercents([1, 1, 1])
    expect(labels.sort()).toEqual(['33%', '33%', '34%'])
  })
  it('single value 100%, empty total 0%', () => {
    expect(formatSharePercents([5])).toEqual(['100%'])
    expect(formatSharePercents([0, 0])).toEqual(['0%', '0%'])
  })
  it('always totals 100 for varied inputs', () => {
    for (const values of [[3, 3, 3, 1], [97, 1, 1, 1], [1, 2, 3, 4, 5, 6, 7], [50, 49, 1]]) {
      expect(sum(formatSharePercents(values))).toBe(100)
    }
  })
})

describe('«Другое» has its own colour (QA #6)', () => {
  it('differs from all 8 palette colours and from the uncategorized grey', () => {
    expect(CHART_CATEGORY_COLORS).not.toContain(OTHER_CATEGORY_COLOR)
    expect(OTHER_CATEGORY_COLOR).not.toBe(UNCATEGORIZED_COLOR)
  })
  it('the «Другое» donut slice uses it, and the variable is defined in both themes', () => {
    const t = ((k: string) => k) as TFunction
    const ids = Array.from({ length: 10 }, (_, i) => `c${i}`)
    const slices = prepareDonutSlices(
      ids.map((id, i) => ({ category_id: id, category_name: id, category_translation_key: null, amount: 100 - i })),
      ids,
      extendCategoryColorMap(ids, []),
      'Другое',
      t,
    )
    const other = slices.find((s) => s.name === 'Другое')
    expect(other?.color).toBe(OTHER_CATEGORY_COLOR)
    expect(css.match(/--app-category-color-other:/g)?.length).toBe(2)
  })
  it('«Другое» is a neutral grey (designer review): #6b7280 dark, #858b92 light, not the blue-grey of «Без категории»', () => {
    const vars = [...css.matchAll(/--app-category-color-(other|neutral): (#[0-9a-f]{6});/g)].map((m) => [m[1], m[2]])
    expect(vars).toEqual([
      ['neutral', '#8e9aa7'],
      ['other', '#6b7280'],
      ['neutral', '#727d89'],
      ['other', '#858b92'],
    ])
    const hue = (hex: string) => {
      const [r, , b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
      return b - r
    }
    // grey: almost no blue tint
    expect(hue('#6b7280')).toBeLessThan(25)
    expect(hue('#858b92')).toBeLessThan(25)
  })
})

describe('legend names wrap instead of being cut to 5 letters (QA #9)', () => {
  const rule = css.match(/\.analytics-donut__legend-name \{[^}]*\}/)?.[0] ?? ''
  it('the name may take two lines', () => {
    expect(rule).toContain('-webkit-line-clamp: 2')
    expect(rule).not.toContain('white-space: nowrap')
  })
})

describe('income row tooltip is the displayed (localized) name (QA #10)', () => {
  it('title uses the resolved name, not the raw API name', () => {
    const tab = readFileSync(new URL('../pages/analytics/AnalyticsChartsTab.tsx', import.meta.url), 'utf8')
    expect(tab).toContain('title={displayName}')
    expect(tab).not.toContain('title={entry.category_name}')
  })
})

describe('units do not wrap away from their number at 320 px (QA #10)', () => {
  it('trend caption keeps «ming so\'m» together; CSS nowrap on the unit', async () => {
    const { trendAxisCaption, chooseTrendAxisScale } = await import('./trendAxis')
    const caption = trendAxisCaption(chooseTrendAxisScale(5000), 'UZS')
    expect(caption).toMatch(/ /)
    expect(caption).not.toMatch(/ /)
    const rule = css.match(/\.analytics-trend-chart__unit \{[^}]*\}/)?.[0] ?? ''
    expect(rule).toContain('white-space: nowrap')
  })
  it('headline joins amount and unit with a non-breaking space', () => {
    const tab = readFileSync(new URL('../pages/analytics/AnalyticsChartsTab.tsx', import.meta.url), 'utf8')
    expect(tab).toContain('${formatAnalyticsAmountDigits(expenseTotal)}\\u00A0${sumUnit()}')
  })
})

function cssRule(selector: string): string {
  const start = css.indexOf(`\n${selector} {`)
  expect(start, `rule ${selector}`).toBeGreaterThan(-1)
  return css.slice(start, css.indexOf('}', start))
}

describe('month switch label never runs under the arrow (QA #1)', () => {
  it('label is one line; the label box and the bar are not squeezed below their content', () => {
    expect(cssRule('.home-month-bar__label')).toContain('white-space: nowrap')
    const wrap = cssRule('.analytics-page__month-label-wrap')
    expect(wrap).toContain('flex: 1 0 auto')
    expect(wrap).not.toContain('min-width: 0')
    const bar = cssRule('.analytics-page__head-row .analytics-page__month-bar')
    expect(bar).toContain('flex: 0 0 auto')
    expect(bar).not.toContain('min-width: 0')
  })

  it('tabs and month bar share one row at 320 px: tabs give way (small basis), bar never shrinks', () => {
    expect(cssRule('.analytics-page__head-lead')).toMatch(/flex: 1 1 1[0-3]\dpx/)
    expect(cssRule('.analytics-page__head-row .month-arrow')).toMatch(/width: (2\d|3[0-4])px/)
    expect(cssRule('.analytics-page__head-row .analytics-page__month-label-wrap')).toContain('flex: 0 0 auto')
  })
})

describe('trend title does not strand «12» / unit on two lines at 320 px (QA N4)', () => {
  it('number and unit are joined by a no-break space in RU and UZ', async () => {
    const ru = (await import('../i18n/locales/ru.json')).default as { analytics: { trendTitle: string } }
    const uz = (await import('../i18n/locales/uz.json')).default as { analytics: { trendTitle: string } }
    expect(ru.analytics.trendTitle).toMatch(/12 месяцев$/)
    expect(uz.analytics.trendTitle).toMatch(/12 oy$/)
  })
})

describe('Analytics header at 320 px is two tidy rows, by design (designer review 4a)', () => {
  const start = css.indexOf('Designer decision (review-final 4a)')
  const media = css.slice(start, css.indexOf('\n}\n', css.indexOf('.analytics-page__month-label-wrap', start)) + 3)
  it('lives in a max-width: 359px block placed after the base header rules', () => {
    expect(start).toBeGreaterThan(css.indexOf('\n.analytics-page__head-row .home-month-bar__label {'))
    expect(media).toContain('@media (max-width: 359px)')
  })
  it('tabs and the month bar each take a full row, so they cannot sit side by side or overlap', () => {
    const rule = media.slice(media.indexOf('.analytics-page__head-lead,'), media.indexOf('}', media.indexOf('.analytics-page__head-lead,')))
    expect(rule).toContain('flex: 1 1 100%')
    expect(rule).toContain('width: 100%')
    expect(rule).toContain('min-width: 0')
  })
  it('44 px arrows at the edges, name centred between them, one equal gap between rows', () => {
    expect(media).toMatch(/\.month-arrow \{\s*width: 44px;/)
    expect(media).toMatch(/month-label-wrap \{[^}]*text-align: center/)
    expect(media).toMatch(/\.analytics-page__head-row \{\s*gap: 8px;/)
  })
  it('the month name stays on one line and the bar is not left-aligned', () => {
    expect(cssRule('.home-month-bar__label')).toContain('white-space: nowrap')
    expect(cssRule('.home-month-bar')).toContain('justify-content: space-between')
  })
})

describe('polish2: «Другое» in the light theme reads against the page (>= 3:1)', () => {
  const lum = (hex: string) => {
    const [r, g, b] = [1, 3, 5].map((i) => {
      const c = parseInt(hex.slice(i, i + 2), 16) / 255
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
  }
  const ratio = (a: string, b: string) => {
    const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
    return (hi + 0.05) / (lo + 0.05)
  }
  const other = [...css.matchAll(/--app-category-color-other: (#[0-9a-f]{6});/g)][1]?.[1] ?? ''
  it('contrast with the white page and the grey card is at least 3:1', () => {
    expect(ratio(other, '#ffffff')).toBeGreaterThanOrEqual(3)
    expect(ratio(other, '#f1f3f5')).toBeGreaterThanOrEqual(3)
  })
})

describe('polish2: recent category chips are one scrollable row (320 px)', () => {
  const rule = css.match(/\.recent-category-chips \{[^}]*\}/)?.[0] ?? ''
  it('do not wrap into several rows and scroll inside the block', () => {
    expect(rule).toContain('flex-wrap: nowrap')
    expect(rule).toContain('overflow-x: auto')
  })
})
