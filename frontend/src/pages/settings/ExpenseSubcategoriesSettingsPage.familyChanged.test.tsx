import { describe, expect, it, vi } from 'vitest'

// The person is on a category's page (or has its subcategory form open) and moves to another
// family. That category does not exist there: no "failed to load data" dead end - the page goes
// back to the category list; an open form stays with the reason and does not call the old budget.
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../../test/hookHarness')
  return reactHarnessModule()
})
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('../../i18n/t', () => ({ t: (key: string) => key }))
vi.mock('../../i18n', () => ({ default: { language: 'ru' } }))
vi.mock('react-router-dom', () => ({
  Navigate: () => null,
  useNavigate: () => vi.fn(),
  useParams: () => ({ parentId: 'p1' }),
}))
vi.mock('../../components/nativeBackButtonContext', () => ({ useNativeBackButtonOverlay: () => undefined }))
vi.mock('../../components/forms/FormSheet', () => ({ FormSheet: () => null }))

const world = vi.hoisted(() => ({
  familyId: 'old',
  role: 'owner',
  categories: [] as unknown[],
  creates: 0,
}))
const cat = (id: string, parent: string | null, name: string) => ({
  id, name, parent_id: parent, translation_key: null, is_protected: false, transaction_count: 0,
})
vi.mock('../../api/categories', () => ({
  getExpenseCategories: async () => world.categories,
  createExpenseCategory: async () => {
    world.creates += 1
    const { FamilyChangedError } = await import('../../api/familyChanged')
    throw new FamilyChangedError()
  },
  patchExpenseCategory: vi.fn(),
  deleteExpenseCategory: vi.fn(),
}))
vi.mock('../../store/authStore', () => ({
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ user: { familyBudgetId: world.familyId, role: world.role } }),
}))
vi.mock('../../store/dataCacheStore', () => ({
  getCachedExpenseCategories: async () => world.categories,
  invalidateExpenseCategoryData: vi.fn(),
  peekExpenseCategories: () => (world.familyId === 'old' ? world.categories : null),
}))

const { mountHook } = await import('../../test/hookHarness')
const { findAll } = await import('../../test/elementTree')
const { Navigate } = await import('react-router-dom')
const { ExpenseSubcategoriesSettingsPage } = await import('./ExpenseSubcategoriesSettingsPage')
const { CategoryFormSheet } = await import('../../components/settings/CategoryFormSheet')
const { SettingsSectionLoadError } = await import('../../components/settings/EditableEntityList')
const { SettingsSubPageShell } = await import('../../components/settings/SettingsSubPageShell')

function reset() {
  world.familyId = 'old'
  world.role = 'owner'
  world.creates = 0
  world.categories = [cat('p1', null, 'Еда'), cat('s1', 'p1', 'Продукты')]
}
const moveAway = () => {
  world.familyId = 'new'
  world.role = 'member'
  world.categories = [cat('q1', null, 'Дом')]
}

describe('Subcategories page: the person moves to another family', () => {
  it('the category is gone: back to the category list, not a load error', async () => {
    reset()
    const h = await mountHook(() => ExpenseSubcategoriesSettingsPage(), 20)
    expect(findAll(h.result(), (e) => e.type === Navigate)).toHaveLength(0)
    moveAway()
    h.rerender()
    await h.settle(20)
    const [to] = findAll(h.result(), (e) => e.type === Navigate)
    expect(to?.props.to).toBe('/settings/expense-categories')
    expect(findAll(h.result(), (e) => e.type === SettingsSectionLoadError)).toHaveLength(0)
  })

  it('an open form stays with the reason; saving again does not go to the old budget', async () => {
    reset()
    const h = await mountHook(() => ExpenseSubcategoriesSettingsPage(), 20)
    const shell = findAll(h.result(), (e) => e.type === SettingsSubPageShell)[0]
    ;(shell.props.onAction as () => void)()
    await h.settle(3)
    const form = () => findAll(h.result(), (e) => e.type === CategoryFormSheet)[0] as { props: Record<string, any> }
    await form().props.onSave({ name: 'Фрукты' }).catch(() => undefined) // the server refuses: moved
    moveAway()
    h.rerender()
    await h.settle(20)

    expect(form()).toBeDefined() // not unmounted under the person's hands
    expect(form().props.editable).toBe(false) // a member now: the form says "only the owner"
    const before = world.creates
    await expect(form().props.onSave({ name: 'Фрукты' })).rejects.toBeDefined()
    expect(world.creates).toBe(before) // no request to the budget the person left
  })
})
