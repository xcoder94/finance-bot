import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

// The person taps "Save" while they are being moved to another family: the server says 409
// family_changed. The form must stay open with the amount, say why, and drop a category/wallet
// that does not exist in the new budget.
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../test/hookHarness')
  return reactHarnessModule()
})
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => (key === 'familyChanged.message' ? 'FAMILY CHANGED' : key) }),
}))
vi.mock('../i18n/t', () => ({ t: (key: string) => key }))
vi.mock('../i18n', () => ({ default: { language: 'ru' } }))
vi.mock('react-router-dom', () => ({ useNavigate: () => vi.fn() }))
vi.mock('@telegram-apps/telegram-ui', () => ({
  Spinner: () => null,
  Text: ({ children }: { children: unknown }) => <span>{children as never}</span>,
  Button: ({ children }: { children: unknown }) => <button>{children as never}</button>,
}))

const world = vi.hoisted(() => ({
  familyId: 'old',
  wallets: [{ id: 'w1', name: 'Cash', currency: 'UZS', translation_key: null, is_personal: false }] as unknown[],
  categories: [
    { id: 'food', name: 'Еда', translation_key: null, parent_id: null },
    { id: 'home', name: 'Дом', translation_key: null, parent_id: null },
  ] as unknown[],
  saves: 0,
}))
vi.mock('../api/transactions', async () => ({
  createExpenseTransaction: vi.fn(async () => {
    world.saves += 1
    // the server moved the person: new budget, other wallet, no "Дом"
    world.familyId = 'new'
    world.wallets = [{ id: 'w2', name: 'Card', currency: 'UZS', translation_key: null, is_personal: false }]
    world.categories = [{ id: 'food2', name: 'Еда', translation_key: null, parent_id: null }]
    const { FamilyChangedError } = await import('../api/familyChanged')
    throw new FamilyChangedError()
  }),
  fetchExpenseCategories: async () => world.categories,
  fetchWallets: async () => world.wallets,
}))
vi.mock('../api/history', () => ({ fetchHistoryPage: async () => ({ items: [], total_count: 0 }) }))
vi.mock('../store/authStore', () => ({
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ user: { familyBudgetId: world.familyId, defaultWalletId: null } }),
}))
vi.mock('../store/dataCacheStore', () => ({
  getCachedExpenseCategories: async () => world.categories,
  getCachedWallets: async () => world.wallets,
  invalidateHomeData: vi.fn(),
  peekExpenseCategories: () => (world.familyId === 'old' ? world.categories : null),
  peekWallets: () => (world.familyId === 'old' ? world.wallets : null),
}))
vi.mock('../store/successFlashStore', () => ({ celebrateSave: vi.fn() }))
vi.mock('../telegram/haptic', () => ({ haptic: { error: vi.fn() } }))
vi.mock('../components/nativeBackButtonContext', () => ({ useNativeBackButtonOverlay: () => undefined }))
vi.mock('../utils/periodFilter', () => ({ getLocale: () => 'ru-RU' }))
vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => undefined })
vi.stubGlobal('window', { history: { state: null } })

const { mountHook } = await import('../test/hookHarness')
const { findAll } = await import('../test/elementTree')
const { AddExpensePage } = await import('./AddExpensePage')
const { FormSheet } = await import('../components/forms/FormSheet')
const { FormSheetAmountField, WalletPickerSheet } = await import('../components/forms/transactionAddFields')
const { CategoryPickerSheet } = await import('../components/forms/CategoryPickerSheet')
const { TransactionSubmitError } = await import('../components/transaction-form/TransactionFormShared')

describe('Add expense: 409 family_changed', () => {
  it('keeps the form and amount, explains it, resets the category and wallet that are gone', async () => {
    const h = await mountHook(() => AddExpensePage(), 40)
    const one = (type: unknown) => {
      const [el] = findAll(h.result(), (e) => e.type === type)
      return el as { props: Record<string, any> }
    }

    one(FormSheetAmountField).props.onChange('50000')
    one(CategoryPickerSheet).props.onSelect({ categoryId: 'home', label: 'Дом' })
    await h.settle(2)
    expect(one(CategoryPickerSheet).props.selectedCategoryId).toBe('home')
    expect(one(WalletPickerSheet).props.selectedWalletId).toBe('w1')

    one(FormSheet).props.onPrimary()
    await h.settle(40)

    expect(world.saves).toBe(1) // no automatic retry
    expect(one(FormSheet).props.open).toBe(true)
    expect(one(FormSheetAmountField).props.value).toBe('50000')
    const [error] = findAll(h.result(), (e) => e.type === TransactionSubmitError)
    expect(renderToStaticMarkup((TransactionSubmitError as (p: unknown) => never)(error.props))).toContain('FAMILY CHANGED')
    expect(one(CategoryPickerSheet).props.selectedCategoryId).toBe('')
    expect(one(WalletPickerSheet).props.selectedWalletId).toBe('w2')
  })
})
