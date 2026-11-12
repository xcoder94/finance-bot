import { describe, expect, it, vi } from 'vitest'

// A person edits an operation, changes the amount, and is moved to another family before Save.
// - the operation is still readable: the typed amount must stay (it used to jump back to the saved one);
// - the operation stayed in the old budget and is unavailable: an honest sentence and a way out,
//   not a silent loss and not "failed to load".
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../test/hookHarness')
  return reactHarnessModule()
})
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('../i18n/t', () => ({ t: (key: string) => key }))
vi.mock('../i18n', () => ({ default: { language: 'ru' } }))

const world = vi.hoisted(() => ({
  familyId: 'old',
  readable: true,
  navigate: vi.fn(),
  tx: {
    id: 't1', type: 'expense', amount: 123321, wallet_id: 'w1', to_wallet_id: 'w2', rate: null,
    expense_category_id: 'food', income_category_id: 'salary', transaction_date: '2026-11-10T05:00:00+05:00',
    comment: null, changes: [],
  } as Record<string, unknown>,
  wallets: [
    { id: 'w1', name: 'Cash', currency: 'UZS', translation_key: null, is_personal: false },
    { id: 'w2', name: 'Card', currency: 'UZS', translation_key: null, is_personal: false },
  ],
  categories: [{ id: 'food', name: 'Еда', translation_key: null, parent_id: null }],
  incomeCategories: [{ id: 'salary', name: 'Зарплата', translation_key: null }],
}))
vi.mock('react-router-dom', () => ({
  useNavigate: () => world.navigate,
  useLocation: () => ({ state: null }),
  useParams: () => ({ id: 't1' }),
}))
vi.mock('@telegram-apps/telegram-ui', () => ({
  Spinner: () => null,
  Text: ({ children }: { children: unknown }) => children,
  Button: () => null,
}))
const changeFamily = async () => {
  world.familyId = 'new'
  const { FamilyChangedError } = await import('../api/familyChanged')
  throw new FamilyChangedError()
}
vi.mock('../api/transactions', () => ({
  fetchTransaction: async () => {
    if (!world.readable && world.familyId === 'new') throw new Error('404')
    return { ...world.tx, type: world.tx.type }
  },
  fetchWallets: async () => world.wallets,
  fetchExpenseCategories: async () => world.categories,
  fetchIncomeCategories: async () => world.incomeCategories,
  updateExpenseTransaction: () => changeFamily(),
  updateIncomeTransaction: () => changeFamily(),
  updateTransferTransaction: () => changeFamily(),
  deleteTransaction: vi.fn(),
}))
vi.mock('../store/authStore', () => ({
  useAuthStore: (select: (s: unknown) => unknown) => select({ user: { familyBudgetId: world.familyId } }),
}))
vi.mock('../store/dataCacheStore', () => ({
  cacheTransaction: vi.fn(),
  getCachedExpenseCategories: async () => world.categories,
  getCachedIncomeCategories: async () => world.incomeCategories,
  getCachedWallets: async () => world.wallets,
  getCachedTransaction: async (_f: string, _id: string, fetcher: () => Promise<unknown>) => fetcher(),
  invalidateTransactionData: vi.fn(),
}))
vi.mock('../store/successFlashStore', () => ({ celebrateSave: vi.fn() }))
vi.mock('../telegram/haptic', () => ({ haptic: { error: vi.fn() } }))
vi.mock('../components/nativeBackButtonContext', () => ({ useNativeBackButtonOverlay: () => undefined }))
vi.mock('../utils/periodFilter', () => ({ getLocale: () => 'ru-RU' }))
vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => undefined })
vi.stubGlobal('window', { history: { state: null } })

const { mountHook } = await import('../test/hookHarness')
const { findAll, textOf } = await import('../test/elementTree')
const { FormSheet } = await import('../components/forms/FormSheet')
const { FormSheetAmountField } = await import('../components/forms/transactionAddFields')
const { TransactionGoneSheet } = await import('../components/forms/TransactionGoneSheet')
const { TransactionSubmitError } = await import('../components/transaction-form/TransactionFormShared')

const pages = [
  ['expense', 'expense', async () => (await import('./EditExpensePage')).EditExpensePage],
  ['income', 'income', async () => (await import('./EditIncomePage')).EditIncomePage],
  ['transfer', 'transfer', async () => (await import('./EditTransferPage')).EditTransferPage],
] as const

async function openAndSave(kind: string, load: () => Promise<() => unknown>) {
  world.familyId = 'old'
  world.tx.type = kind
  world.navigate.mockClear()
  const Page = await load()
  const h = await mountHook(() => Page(), 40)
  const one = (type: unknown) => findAll(h.result(), (e) => e.type === type)[0] as { props: Record<string, any> } | undefined
  expect(one(FormSheetAmountField)!.props.value).toBe('123321')
  one(FormSheetAmountField)!.props.onChange('123322')
  await h.settle(2)
  one(FormSheet)!.props.onPrimary()
  await h.settle(40)
  return { h, one }
}

describe.each(pages)('Edit %s: moved to another family before Save', (_name, kind, load) => {
  it('the operation is still readable: the typed amount stays and the reason is shown', async () => {
    world.readable = true
    const { h, one } = await openAndSave(kind, load)
    expect(one(FormSheetAmountField)!.props.value).toBe('123322')
    const [error] = findAll(h.result(), (e) => e.type === TransactionSubmitError)
    expect(error.props.messageKey).toBe('familyChanged.message')
  })

  it('the operation stayed in the old budget: honest sentence, a button that closes the form', async () => {
    world.readable = false
    const { one } = await openAndSave(kind, load)
    expect(one(FormSheetAmountField)).toBeUndefined()
    // the sheet says it plainly, and its button closes the form
    const sheet = one(TransactionGoneSheet)!
    expect(sheet).toBeDefined()
    const rendered = (TransactionGoneSheet as unknown as (p: object) => unknown)(sheet.props)
    expect(textOf(rendered)).toContain('familyChanged.transactionGone')
    expect((findAll(rendered, (e) => e.type === FormSheet)[0] as { props: Record<string, any> }).props.primaryLabel).toBe('familyChanged.transactionGoneClose')
    sheet.props.onClose()
    expect(world.navigate).toHaveBeenCalled()
  })
})
