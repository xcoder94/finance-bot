import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

// The expense form as it opens: the keyboard goes to the amount, the person's recent categories
// sit under it as one-tap chips.
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../test/hookHarness')
  return reactHarnessModule()
})
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('../i18n/t', () => ({ t: (key: string) => key }))
vi.mock('../i18n', () => ({ default: { language: 'ru' } }))
vi.mock('react-router-dom', () => ({ useNavigate: () => vi.fn() }))
vi.mock('@telegram-apps/telegram-ui', () => ({ Spinner: () => null }))

const WALLETS = [{ id: 'w1', name: 'Cash', currency: 'UZS', translation_key: null, is_personal: false }]
const CATEGORIES = [
  { id: 'food', name: 'Еда', translation_key: null, parent_id: null },
  { id: 'cafe', name: 'Кафе', translation_key: null, parent_id: 'food' },
  { id: 'home', name: 'Дом', translation_key: null, parent_id: null },
  { id: 'fun', name: 'Отдых', translation_key: null, parent_id: null },
]
vi.mock('../api/transactions', () => ({
  createExpenseTransaction: vi.fn(),
  fetchExpenseCategories: async () => CATEGORIES,
  fetchWallets: async () => WALLETS,
}))
vi.mock('../api/history', () => ({
  fetchHistoryPage: async () => ({ items: [], total_count: 0 }),
}))
vi.mock('../store/authStore', () => ({
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ user: { familyBudgetId: 'fam', defaultWalletId: null } }),
}))
vi.mock('../store/dataCacheStore', () => ({
  getCachedExpenseCategories: async () => CATEGORIES,
  getCachedWallets: async () => WALLETS,
  invalidateHomeData: vi.fn(),
  peekExpenseCategories: () => CATEGORIES,
  peekWallets: () => WALLETS,
}))
vi.mock('../store/successFlashStore', () => ({ celebrateSave: vi.fn() }))
vi.mock('../telegram/haptic', () => ({ haptic: { error: vi.fn() } }))
vi.mock('../components/nativeBackButtonContext', () => ({ useNativeBackButtonOverlay: () => undefined }))
vi.mock('../utils/periodFilter', () => ({ getLocale: () => 'ru-RU' }))

// this device's own recent list: «Дом» was used last, then «Кафе»
vi.stubGlobal('localStorage', {
  getItem: (key: string) => (key === 'recent-categories:fam:expense' ? JSON.stringify(['home', 'cafe']) : null),
  setItem: () => undefined,
})
vi.stubGlobal('window', { history: { state: null } })

const { mountHook } = await import('../test/hookHarness')
const { findAll } = await import('../test/elementTree')
const { AddExpensePage } = await import('./AddExpensePage')
const { FormSheetAmountField } = await import('../components/forms/transactionAddFields')
const { RecentCategoryChips } = await import('../components/forms/RecentCategoryChips')

async function openForm() {
  const h = await mountHook(() => AddExpensePage(), 40)
  return h.result()
}

describe('Add expense form', () => {
  it('puts the keyboard on the amount field when it opens', async () => {
    const tree = await openForm()
    const [field] = findAll(tree, (el) => el.type === FormSheetAmountField)
    expect(field).toBeDefined()

    // run the field itself with a stand-in input and see whether the form focuses it
    const focus = vi.fn()
    const mounted = await mountHook(
      () => (FormSheetAmountField as (p: unknown) => unknown)(field.props),
      4,
      (output) => {
        const [input] = findAll(output, (el) => el.type === 'input')
        ;(input.props.ref as { current: unknown }).current = { focus, setSelectionRange: () => undefined }
      },
    )
    await mounted.settle(2)
    expect(focus).toHaveBeenCalledTimes(1)
  })

  it('shows this person\'s recent categories as chips, latest first, with the parent in the name', async () => {
    const tree = await openForm()
    const [chips] = findAll(tree, (el) => el.type === RecentCategoryChips)
    expect(chips).toBeDefined()
    const html = renderToStaticMarkup(
      (RecentCategoryChips as (p: unknown) => React.ReactElement)(chips.props),
    )
    const labels = [...html.matchAll(/<button[^>]*>([^<]*)<\/button>/g)].map((m) => m[1])
    expect(labels).toEqual(['Дом', 'Еда · Кафе'])
  })
})
