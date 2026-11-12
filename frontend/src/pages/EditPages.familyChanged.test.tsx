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
  moved: null as null | Record<string, string>,
  saved: [] as Array<Record<string, unknown>>,
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
// the first save finds the person in another family; after that the server accepts only the new budget's ids
const save = async (body: Record<string, unknown>) => {
  if (world.familyId === 'old') return changeFamily()
  const ids = [body.wallet_id, body.expense_category_id, body.income_category_id].filter(Boolean)
  if (world.moved && ids.some((x) => x === 'w1' || x === 'food' || x === 'salary')) throw new Error('404')
  world.saved.push(body)
  return { ...world.tx, ...body }
}
vi.mock('../api/transactions', () => ({
  fetchTransaction: async () => {
    if (!world.readable && world.familyId === 'new') throw new Error('404')
    return { ...world.tx, type: world.tx.type, ...(world.familyId === 'new' ? world.moved : null) }
  },
  fetchWallets: async () => world.wallets,
  fetchExpenseCategories: async () => world.categories,
  fetchIncomeCategories: async () => world.incomeCategories,
  updateExpenseTransaction: (_id: string, body: Record<string, unknown>) => save(body),
  updateIncomeTransaction: (_id: string, body: Record<string, unknown>) => save(body),
  updateTransferTransaction: (_id: string, body: Record<string, unknown>) => save(body),
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

async function openAndSave(kind: string, load: () => Promise<() => unknown>, moved: Record<string, string> | null = null) {
  world.familyId = 'old'
  world.moved = moved
  world.saved = []
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

describe.each(pages.slice(0, 2))('Edit %s: the operation moved with the person to the new budget', (_name, kind, load) => {
  it('takes the category and wallet of the new budget, keeps typed amount, and the next Save goes through', async () => {
    const saved = { wallets: world.wallets, categories: world.categories, incomeCategories: world.incomeCategories }
    world.wallets = [...saved.wallets, { id: 'w9', name: 'Наличные', currency: 'UZS', translation_key: null, is_personal: false }]
    world.categories = [...saved.categories, { id: 'food9', name: 'Еда', translation_key: null, parent_id: null }]
    world.incomeCategories = [...saved.incomeCategories, { id: 'salary9', name: 'Зарплата', translation_key: null }]
    try {
      world.readable = true
      // the first Save finds the person in the new budget, where this operation has other wallet/category ids
      const { h, one } = await openAndSave(kind, load, { wallet_id: 'w9', expense_category_id: 'food9', income_category_id: 'salary9' })
      const sheetProps = (type: unknown) => (findAll(h.result(), (e) => e.type === type)[0] as { props: Record<string, any> }).props
      const { WalletPickerSheet } = await import('../components/forms/transactionAddFields')
      const { CategoryPickerSheet } = await import('../components/forms/CategoryPickerSheet')
      expect(sheetProps(WalletPickerSheet).selectedWalletId).toBe('w9')
      expect(sheetProps(CategoryPickerSheet).selectedCategoryId).toBe(kind === 'expense' ? 'food9' : 'salary9')
      expect(one(FormSheetAmountField)!.props.value).toBe('123322')
      one(FormSheet)!.props.onPrimary()
      await h.settle(40)
      expect(world.saved).toHaveLength(1)
      expect(world.saved[0]).toMatchObject({ amount: 123322, wallet_id: 'w9' })
    } finally {
      world.wallets = saved.wallets
      world.categories = saved.categories
      world.incomeCategories = saved.incomeCategories
    }
  })
})
