import { readFileSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { CategoryDonutChart } from './CategoryDonutChart'

const NAME30 = 'Абвгдежзиклмнопрстуфхцчшщъыэ'.slice(0, 30)

const slices = [
  { key: 'a', name: 'Еда', value: 700_000, color: '#111', prev: 625_000 },
  { key: 'b', name: NAME30, value: 200_000, color: '#222', prev: 0 },
  { key: 'c', name: 'Транспорт', value: 100_000, color: '#333', prev: 200_000 },
  { key: 'other', name: 'Другое', value: 50_000, color: '#444' },
]

describe('CategoryDonutChart list', () => {
  const html = renderToStaticMarkup(
    <CategoryDonutChart slices={slices} onSliceActivate={() => undefined} centerLabel="Расход" />,
  )

  it('shows delta per row: +12%, новая, real minus', () => {
    expect(html).toContain('+12%')
    expect(html).toContain('новая')
    expect(html).toContain('−50%')
  })

  it('rows that drill have a chevron button, «Другое» does not', () => {
    expect(html.match(/<button/g)?.length).toBe(3)
    expect(html.match(/analytics-donut__legend-chevron[^>]*>›/g)?.length).toBe(3)
  })

  it('«Другое» row has no delta', () => {
    const otherRow = html.split('<div class="analytics-donut__legend-item"')[1] ?? ''
    expect(otherRow).toContain('Другое')
    expect(otherRow).not.toMatch(/\+\d+%|новая|−\d+%/)
  })

  it('30-char names are in the DOM in full and clamped to two lines by CSS', () => {
    expect(html).toContain(NAME30)
    const css = readFileSync(new URL('../../index.css', import.meta.url), 'utf8')
    const rule = css.match(/\.analytics-donut__legend-name \{[^}]*\}/)?.[0] ?? ''
    expect(rule).toContain('-webkit-line-clamp: 2')
    expect(rule).toContain('min-width: 0')
  })

  it('names wrap at word boundaries, never mid-word, and 320 px gives them a full-width line (QA #9)', () => {
    const css = readFileSync(new URL('../../index.css', import.meta.url), 'utf8')
    const rule = css.match(/\.analytics-donut__legend-name \{[^}]*\}/)?.[0] ?? ''
    expect(rule).toContain('overflow-wrap: break-word')
    expect(rule).not.toContain('anywhere')
    const media = css.slice(css.indexOf('@media (max-width: 359px) {\n  .analytics-donut__legend-item'))
    expect(media).toContain("'dot name name name chev'")
    expect(media).toContain('grid-area: name')
  })

  it('centre amount carries a fit-to-ring font size', () => {
    const big = renderToStaticMarkup(
      <CategoryDonutChart
        slices={[{ key: 'a', name: 'X', value: 2_002_658_999, color: '#111', prev: 1 }]}
        centerLabel="Расход"
      />,
    )
    const small = renderToStaticMarkup(
      <CategoryDonutChart
        slices={[{ key: 'a', name: 'X', value: 1000, color: '#111', prev: 1 }]}
        centerLabel="Расход"
      />,
    )
    const sizeOf = (h: string) =>
      Number(h.match(/analytics-donut__center-value[^>]*font-size:(\d+)px/)?.[1])
    expect(sizeOf(big)).toBeLessThan(sizeOf(small))
    expect(sizeOf(big) * 0.62 * '2 002 658 999'.length).toBeLessThanOrEqual(116)
  })

  it('without delta data (showDelta=false) no delta text', () => {
    const plain = renderToStaticMarkup(<CategoryDonutChart slices={slices} showDelta={false} />)
    expect(plain).not.toContain('новая')
  })
})
