import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

;(globalThis as unknown as { document: { documentElement: { lang: string } } }).document ??= {
  documentElement: { lang: '' },
}

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}))

vi.mock('../utils/periodFilter', () => ({ getLocale: () => 'ru-RU' }))

const { DateChips } = await import('./DateChips')
const { DateRangeFields } = await import('./DateRangeFields')
const { addDays, todayTashkent } = await import('../utils/dateChips')

function pressed(html: string): string[] {
  return [...html.matchAll(/aria-pressed="true"[^>]*>([^<]*)</g)].map((m) => m[1])
}

describe('DateChips', () => {
  it('renders the four chips and selects today by default value', () => {
    const html = renderToStaticMarkup(<DateChips value={todayTashkent()} onChange={() => undefined} />)
    for (const key of ['today', 'yesterday', 'dayBefore', 'other']) {
      expect(html).toContain(`dateChips.${key}`)
    }
    expect(pressed(html)).toEqual(['dateChips.today'])
  })

  it('selects Yesterday for yesterday', () => {
    const html = renderToStaticMarkup(
      <DateChips value={addDays(todayTashkent(), -1)} onChange={() => undefined} />,
    )
    expect(pressed(html)).toEqual(['dateChips.yesterday'])
  })

  it('a stored date 3 days ago selects the last chip and shows the date', () => {
    const html = renderToStaticMarkup(
      <DateChips value={addDays(todayTashkent(), -3)} onChange={() => undefined} />,
    )
    const [label] = pressed(html)
    expect(label).not.toBe('dateChips.other')
    expect(label).toMatch(/\d/)
  })

  it('the native calendar cannot pick tomorrow (max = today) and is the only date input', () => {
    const html = renderToStaticMarkup(<DateChips value={todayTashkent()} onChange={() => undefined} />)
    expect(html).toContain(`max="${todayTashkent()}"`)
    expect(html).toContain('type="date"')
    expect(html).not.toContain('type="text"')
  })
})

describe('DateRangeFields', () => {
  const render = (invalid: boolean) =>
    renderToStaticMarkup(
      <DateRangeFields
        rangeFrom="2026-10-01"
        rangeTo="2026-10-31"
        onRangeFromChange={() => undefined}
        onRangeToChange={() => undefined}
        rangeOrderInvalid={invalid}
      />,
    )

  it('shows the four presets and two native date inputs, no text input', () => {
    const html = render(false)
    for (const key of ['days7', 'days30', 'thisMonth', 'lastMonth']) {
      expect(html).toContain(`dateChips.${key}`)
    }
    expect(html.match(/type="date"/g)).toHaveLength(2)
    expect(html).not.toContain('type="text"')
    expect(html).not.toContain('history.invalidRange')
  })

  it('To cannot be earlier than From (min) and From cannot pass To (max)', () => {
    const html = render(false)
    expect(html).toContain('min="2026-10-01"')
    expect(html).toContain('max="2026-10-31"')
  })

  it('shows the order message when From is after To', () => {
    expect(render(true)).toContain('history.invalidRange')
  })
})

describe('quick chips hide the fallback date field (P1-4)', () => {
  it('pickQuickChip closes the fallback and sets the day', async () => {
    const { pickQuickChip } = await import('./DateChips')
    const calls: string[] = []
    pickQuickChip('2026-11-10', -1, (v) => calls.push(`set ${v}`), () => calls.push('close'))
    expect(calls).toEqual(['close', 'set 2026-11-09'])
  })
})
