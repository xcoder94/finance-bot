import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import ru from '../../i18n/locales/ru.json'
import uz from '../../i18n/locales/uz.json'

const read = (rel: string) => readFileSync(new URL(rel, import.meta.url), 'utf8')

describe('U4 structure', () => {
  it('has no «Самый дорогой день» tile or strings anywhere', () => {
    const tab = read('./AnalyticsChartsTab.tsx')
    expect(tab).not.toContain('mostExpensive')
    expect(JSON.stringify(ru)).not.toContain('Самый дорогой день')
    expect(JSON.stringify(uz)).not.toContain('mostExpensiveDay')
  })

  it('hint texts are the plain-words ones', () => {
    expect(ru.analytics.hintRoot).toBe('Нажмите на категорию, чтобы увидеть подробности')
    expect(ru.analytics.hintOther).toBe('Мелкие категории собраны в «Другое»')
    expect(JSON.stringify(ru)).not.toContain('девятой')
    expect(JSON.stringify(ru)).not.toContain('второго уровня')
  })

  it('personal-only empty state text', () => {
    expect(ru.analytics.personalOnly).toBe(
      'Здесь только общие кошельки. Личные траты в аналитику не входят.',
    )
  })

  it('breadcrumb and parent link strings', () => {
    expect(ru.analytics.allExpenses).toBe('Все расходы')
    expect(ru.analytics.allOpsOf.replace('{{name}}', 'Еда')).toBe('Все операции «Еда» ›')
  })

  it('analytics title is gone from the header (tab bar says it)', () => {
    expect(read('./AnalyticsLayout.tsx')).not.toContain('home-header__title')
  })

  it('the parent link opens History with the parent id; first load uses skeletons', () => {
    const tab = read('./AnalyticsChartsTab.tsx')
    expect(tab).toMatch(/openParentHistory[\s\S]*id: drillParent\.id/)
    expect(tab).not.toContain('<Spinner')
  })

  it('income block is rendered only with rows; headline delta is neutral colour', () => {
    const tab = read('./AnalyticsChartsTab.tsx')
    expect(tab).toContain('incomeRows.length > 0')
    const css = read('../../index.css')
    const rule = css.match(/\.analytics-charts-headline__compare \{[^}]*\}/)?.[0] ?? ''
    expect(rule).toContain('var(--hint)')
  })

  it('drill heading, amount and caption are block-level (B8)', () => {
    const css = read('../../index.css')
    expect(css.match(/\.analytics-charts-donut-card__drill-sum \{[^}]*\}/)?.[0]).toContain('display: block')
    expect(css.match(/\.analytics-charts-donut-card__shares \{[^}]*\}/)?.[0]).toContain('display: block')
  })
})

describe('polish2: every range-bound block re-fetches on return to the app', () => {
  it('summary (header "Расход за") is keyed by fetchKey (with homeEpoch), not by the bare range', () => {
    const src = read('./AnalyticsChartsTab.tsx')
    const summaryBlock = src.slice(src.indexOf('const summaryFetch = useFetchBlock('))
    const head = summaryBlock.slice(0, summaryBlock.indexOf('const trendEndMonth'))
    expect(head).toContain('fetchKey,')
    expect(head).not.toMatch(/\n\s+rangeKey,\n\s+rangeFetchEnabled/)
  })
})
