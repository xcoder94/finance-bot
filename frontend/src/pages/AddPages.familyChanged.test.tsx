import { describe, expect, it, vi } from 'vitest'

// Normal path on every add form: the form is open, the person is moved to another family in the
// bot, comes back (the app rereads /me) and taps Save. The form must say why and must not keep a
// category/wallet that belongs to the old budget. Same when the refusal comes from the save itself.
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../test/hookHarness')
  return reactHarnessModule()
})
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('../i18n/t', () => ({ t: (key: string) => key }))
vi.mock('../i18n', () => ({ default: { language: 'ru' } }))
vi.mock('react-router-dom', () => ({ useNavigate: () => vi.fn() }))
vi.mock('@telegram-apps/telegram-ui', () => ({
  Spinner: () => null,
  Text: ({ children }: { children: unknown }) => children,
  Button: () => null,
}))

const world = vi.hoisted(() => ({
  familyId: 'old',
  wallets: [
    { id: 'w1', name: 'Cash', currency: 'UZS', translation_key: null, is_personal: false },
    { id: 'w3', name: 'Safe', currency: 'UZS', translation_key: null, is_personal: false },
  ] as unknown[],
  categories: [{ id: 'food', name: 'Еда', translation_key: null, parent_id: null }] as unknown[],
  incomeCategories: [{ id: 'salary', name: 'Зарплата', translation_key: null }] as unknown[],
  failSave: false,
}))
const moveToNewFamily = () => {
  world.familyId = 'new'
  world.wallets = [
    { id: 'w2', name: 'Card', currency: 'UZS', translation_key: null, is_personal: false },
    { id: 'w4', name: 'Jar', currency: 'UZS', translation_key: null, is_personal: false },
  ]
  world.categories = [{ id: 'food2', name: 'Еда', translation_key: null, parent_id: null }]
  world.incomeCategories = [{ id: 'salary2', name: 'Зарплата', translation_key: null }]
}
const save = async () => {
  moveToNewFamily()
  const { FamilyChangedError } = await import('../api/familyChanged')
  throw new FamilyChangedError()
}
vi.mock('../api/transactions', () => ({
  createExpenseTransaction: save,
  createIncomeTransaction: save,
  createTransferTransaction: save,
  fetchExpenseCategories: async () => world.categories,
  fetchIncomeCategories: async () => world.incomeCategories,
  fetchWallets: async () => world.wallets,
}))
vi.mock('../api/history', () => ({ fetchHistoryPage: async () => ({ items: [], total_count: 0 }) }))
vi.mock('../store/authStore', () => ({
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ user: { familyBudgetId: world.familyId, defaultWalletId: null } }),
}))
const peek = (v: () => unknown) => () => (world.familyId === 'old' ? v() : null)
vi.mock('../store/dataCacheStore', () => ({
  getCachedExpenseCategories: async () => world.categories,
  getCachedIncomeCategories: async () => world.incomeCategories,
  getCachedWallets: async () => world.wallets,
  invalidateHomeData: vi.fn(),
  peekExpenseCategories: peek(() => world.categories),
  peekIncomeCategories: peek(() => world.incomeCategories),
  peekWallets: peek(() => world.wallets),
}))
vi.mock('../store/successFlashStore', () => ({ celebrateSave: vi.fn() }))
vi.mock('../telegram/haptic', () => ({ haptic: { error: vi.fn() } }))
vi.mock('../components/nativeBackButtonContext', () => ({ useNativeBackButtonOverlay: () => undefined }))
vi.mock('../utils/periodFilter', () => ({ getLocale: () => 'ru-RU' }))
vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => undefined })
vi.stubGlobal('window', { history: { state: null } })

const { mountHook } = await import('../test/hookHarness')
const { findAll } = await import('../test/elementTree')
const { FormSheet } = await import('../components/forms/FormSheet')
const { FormSheetAmountField } = await import('../components/forms/transactionAddFields')
const { CategoryPickerSheet } = await import('../components/forms/CategoryPickerSheet')
const { TransactionSubmitError } = await import('../components/transaction-form/TransactionFormShared')

const pages = [
  ['expense', async () => (await import('./AddExpensePage')).AddExpensePage],
  ['income', async () => (await import('./AddIncomePage')).AddIncomePage],
  ['transfer', async () => (await import('./AddTransferPage')).AddTransferPage],
] as const

async function open(kind: string, load: () => Promise<() => unknown>) {
  world.familyId = 'old'
  world.wallets = [
    { id: 'w1', name: 'Cash', currency: 'UZS', translation_key: null, is_personal: false },
    { id: 'w3', name: 'Safe', currency: 'UZS', translation_key: null, is_personal: false },
  ]
  world.categories = [{ id: 'food', name: 'Еда', translation_key: null, parent_id: null }]
  world.incomeCategories = [{ id: 'salary', name: 'Зарплата', translation_key: null }]
  const Page = await load()
  const h = await mountHook(() => Page(), 40)
  const one = (type: unknown) => findAll(h.result(), (e) => e.type === type)[0] as { props: Record<string, any> } | undefined
  one(FormSheetAmountField)!.props.onChange('50000')
  const picker = one(CategoryPickerSheet)
  if (picker) picker.props.onSelect({ categoryId: kind === 'income' ? 'salary' : 'food', label: 'c' })
  await h.settle(2)
  return { h, one }
}

describe.each(pages)('Add %s: moved to another family', (kind, load) => {
  it('came back to the app (the person is reread): the form says why, the typed amount stays', async () => {
    const { h, one } = await open(kind, load)
    moveToNewFamily() // the app rereads /me on return: the store now holds the new family
    h.rerender()
    await h.settle(40)
    const [error] = findAll(h.result(), (e) => e.type === TransactionSubmitError)
    expect(error?.props.messageKey).toBe('familyChanged.message')
    expect(one(FormSheetAmountField)!.props.value).toBe('50000')
    expect(one(FormSheet)!.props.open).toBe(true)
  })

  it('Save refused for the family change: the same sentence, the amount stays', async () => {
    const { h, one } = await open(kind, load)
    one(FormSheet)!.props.onPrimary()
    await h.settle(40)
    const [error] = findAll(h.result(), (e) => e.type === TransactionSubmitError)
    expect(error?.props.messageKey).toBe('familyChanged.message')
    expect(one(FormSheetAmountField)!.props.value).toBe('50000')
  })
})
