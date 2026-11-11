import { describe, expect, it, vi } from 'vitest'

// The date field a person can open from «Другая дата». The WebView may have no calendar popup
// (showPicker missing): then a plain date field appears and the person can type any date.
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../test/hookHarness')
  return reactHarnessModule()
})
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('../utils/periodFilter', () => ({ getLocale: () => 'ru-RU' }))

const { mountHook } = await import('../test/hookHarness')
const { findAll, findButton } = await import('../test/elementTree')
const { DateChips } = await import('./DateChips')
const { NativeDatePicker } = await import('./NativeDatePicker')
const { addDays, todayTashkent } = await import('../utils/dateChips')

type Input = { props: Record<string, unknown> }

async function openFallbackField(onChange: (value: string) => void) {
  const chips = await mountHook(() => DateChips({ value: todayTashkent(), onChange }))
  const root = chips.result() as unknown as { props: { children: { props: Record<string, unknown> } } }
  const picker = root.props.children
  const h = await mountHook(() => NativeDatePicker(picker.props as never))
  const first = h.result()
  const input = findAll(first, (el) => el.type === 'input')[0] as Input
  // a WebView without showPicker: only a focusable input
  ;(input.props.ref as { current: unknown }).current = { focus: () => undefined }
  const other = findButton(first, 'dateChips.other')!
  ;(other.props.onClick as () => void)()
  await h.settle(2)
  h.rerender()
  const shown = findAll(h.result(), (el) => el.type === 'input')[0] as Input
  return { shown, input }
}

describe('date field behind «Другая дата»', () => {
  it('opens as a visible field when the system calendar is not available', async () => {
    const { shown } = await openFallbackField(() => undefined)
    expect(String(shown.props.className)).toContain('date-chips__native--visible')
  })

  it('a future date typed into it becomes today, not the future day', async () => {
    const onChange = vi.fn()
    const { shown } = await openFallbackField(onChange)
    const tomorrow = addDays(todayTashkent(), 1)
    ;(shown.props.onChange as (e: unknown) => void)({ target: { value: tomorrow } })
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith(todayTashkent())
  })

  it('offers no day after today to pick in the first place', async () => {
    const { shown } = await openFallbackField(() => undefined)
    expect(shown.props.max).toBe(todayTashkent())
  })

  it('a past date typed into it is kept as typed', async () => {
    const onChange = vi.fn()
    const { shown } = await openFallbackField(onChange)
    const past = addDays(todayTashkent(), -5)
    ;(shown.props.onChange as (e: unknown) => void)({ target: { value: past } })
    expect(onChange).toHaveBeenCalledWith(past)
  })
})
