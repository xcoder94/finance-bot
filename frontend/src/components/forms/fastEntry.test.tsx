import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

;(globalThis as unknown as { document: { documentElement: { lang: string } } }).document ??= {
  documentElement: { lang: '' },
}

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}))
vi.mock('@telegram-apps/telegram-ui', () => ({
  Spinner: () => <i {...{ 'data-spinner': 'true' }} />,
}))
vi.mock('../../i18n/t', () => ({ t: (key: string) => key }))
vi.mock('../../i18n', () => ({ default: { language: 'ru' } }))
vi.mock('../../utils/periodFilter', () => ({ getLocale: () => 'ru-RU' }))

const { RecentCategoryChips } = await import('./RecentCategoryChips')
const { FormSheet } = await import('./FormSheet')
const { FormSheetAmountField } = await import('./transactionAddFields')

describe('RecentCategoryChips', () => {
  const chips = [
    { id: 'a', label: 'Еда · Кафе' },
    { id: 'b', label: 'Дом' },
  ]

  it('renders nothing for a new person with no history', () => {
    expect(renderToStaticMarkup(<RecentCategoryChips chips={[]} selectedId="" onSelect={() => undefined} />)).toBe('')
  })

  it('renders chips in the given (newest first) order and marks the selected one', () => {
    const html = renderToStaticMarkup(<RecentCategoryChips chips={chips} selectedId="b" onSelect={() => undefined} />)
    expect(html.indexOf('Еда · Кафе')).toBeLessThan(html.indexOf('Дом'))
    expect([...html.matchAll(/aria-pressed="true"[^>]*>([^<]*)</g)].map((m) => m[1])).toEqual(['Дом'])
  })
})

describe('amount field', () => {
  it('uses the decimal keyboard', () => {
    const html = renderToStaticMarkup(
      <FormSheetAmountField
        value=""
        currencySuffix="so'm"
        overLimit={false}
        autoFocus
        onChange={() => undefined}
        onOverLimitChange={() => undefined}
      />,
    )
    expect(html).toContain('inputMode="decimal"')
  })
})

describe('FormSheet primary button', () => {
  const render = (loading: boolean) =>
    renderToStaticMarkup(
      <FormSheet open title="T" onClose={() => undefined} onPrimary={() => undefined} primaryLoading={loading}>
        <div />
      </FormSheet>,
    )

  it('shows a spinner, not an ellipsis, while sending', () => {
    const html = render(true)
    expect(html).not.toContain('…')
    expect(html).toContain('data-spinner')
    expect(html).toMatch(/form-sheet-primary[^>]*disabled/)
  })

  it('shows the label when idle', () => {
    expect(render(false)).toContain('formSheet.save')
  })

  it('keeps the action row sticky so Save stays above the keyboard', () => {
    const css = readFileSync(join(__dirname, '../../index.css'), 'utf8')
    const rule = /\.form-sheet-actions\s*\{[^}]*\}/.exec(css)?.[0] ?? ''
    expect(rule).toContain('position: sticky')
    expect(rule).toContain('bottom: 0')
  })
})

describe('sheet content scrolls above the sticky Save bar (N3)', () => {
  const css = readFileSync(join(__dirname, '../../index.css'), 'utf8')
  it('the panel has no bottom padding, so sticky bottom:0 is the real edge', () => {
    const panel = /\n\.form-sheet-panel \{[^}]*padding: 16px 16px 0;[^}]*\}/.exec(css)
    expect(panel).not.toBeNull()
    const actions = /\.form-sheet-actions\s*\{[^}]*\}/.exec(css)?.[0] ?? ''
    expect(actions).toContain('margin: 2px -16px 0;')
    expect(actions).toContain('padding: 8px 16px 24px;')
  })
  it('a sheet without an action row keeps its bottom padding', () => {
    expect(css).toContain('.form-sheet-panel:not(:has(.form-sheet-actions))')
  })
})

describe('FormSheet delete button (B22)', () => {
  it('renders the visible Удалить block above the sticky save bar', () => {
    const html = renderToStaticMarkup(
      <FormSheet
        open
        title="T"
        onClose={() => undefined}
        onPrimary={() => undefined}
        danger={<button className="form-sheet-danger-button">Удалить</button>}
      >
        <div />
      </FormSheet>,
    )
    expect(html).toContain('form-sheet-danger-button')
    expect(html.indexOf('form-sheet-danger')).toBeLessThan(html.indexOf('form-sheet-actions'))
  })
})

describe('editing a record with a future day (P1-5)', () => {
  it('its own stored day stays valid, another future day does not', async () => {
    const { isFormSheetDateValid } = await import('./transactionAddFields')
    const { addDays, todayTashkent } = await import('../../utils/dateChips')
    const future = addDays(todayTashkent(), 1)
    expect(isFormSheetDateValid(future)).toBe(false)
    expect(isFormSheetDateValid(future, future)).toBe(true)
    expect(isFormSheetDateValid(addDays(future, 1), future)).toBe(false)
  })
})
