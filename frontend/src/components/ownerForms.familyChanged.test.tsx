import { describe, expect, it, vi } from 'vitest'

// Category, goal and wallet forms: the person became a member (or moved to another family) under
// an open form. They must see why (by role), the form must not lose its Save/explanation, and no
// "Try again" that repeats a refusal forever.
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../test/hookHarness')
  return reactHarnessModule()
})
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('../i18n/t', () => ({ t: (key: string) => key }))
vi.mock('../i18n', () => ({ default: { language: 'ru' } }))
vi.mock('./nativeBackButtonContext', () => ({ useNativeBackButtonOverlay: () => undefined }))
vi.mock('./NativeDatePicker', () => ({ NativeDatePicker: () => null }))
vi.mock('./forms/FormSheet', () => ({ FormSheet: () => null }))

const { mountHook } = await import('../test/hookHarness')
const { findAll, textOf } = await import('../test/elementTree')
const { FamilyChangedError } = await import('../api/familyChanged')
const { useAuthStore } = await import('../store/authStore')
const { FormSheet } = await import('./forms/FormSheet')
const { FormNotice } = await import('./FormNotice')
const { CategoryFormSheet } = await import('./settings/CategoryFormSheet')
const { GoalFormSheet } = await import('./goals/GoalFormSheet')
const { WalletFormSheet } = await import('./settings/WalletFormSheet')

const setRole = (role: string) =>
  useAuthStore.setState({ status: 'ready', user: { id: 'u', familyBudgetId: 'f', role } as never })

const alerts = (tree: unknown) => findAll(tree, (e) => e.type === FormNotice)
const retryButtons = (tree: unknown) =>
  findAll(tree, (e) => e.type === 'button' && textOf(e.props.children) === 'auth.retry')
const sheet = (tree: unknown) => findAll(tree, (e) => e.type === FormSheet)[0] as { props: Record<string, any> }

describe('CategoryFormSheet', () => {
  const base = {
    open: true, mode: 'edit', kind: 'expense-parent', category: { name: 'Еда' }, atLimit: false,
    onClose: () => undefined,
  } as const

  it('a member who opens it (or became one) sees the owner-only sentence and Save is off', async () => {
    const h = await mountHook(() => CategoryFormSheet({ ...base, editable: false, onSave: async () => undefined }), 5)
    expect(textOf(alerts(h.result()))).toContain('familyChanged.categoriesOwnerOnly')
    expect(sheet(h.result()).props.primaryDisabled).toBe(true)
  })

  it('refused after the role changed: owner-only sentence, no retry button', async () => {
    setRole('member')
    const h = await mountHook(
      () => CategoryFormSheet({ ...base, editable: true, onSave: async () => { throw new FamilyChangedError() } }),
      5,
    )
    sheet(h.result()).props.onPrimary()
    await h.settle(5)
    expect(textOf(alerts(h.result()))).toContain('familyChanged.categoriesOwnerOnly')
    expect(retryButtons(h.result())).toHaveLength(0)
  })

  it('refused with the role unchanged (another family): generic sentence, no retry button', async () => {
    setRole('owner')
    const h = await mountHook(
      () => CategoryFormSheet({ ...base, editable: true, onSave: async () => { throw new FamilyChangedError() } }),
      5,
    )
    sheet(h.result()).props.onPrimary()
    await h.settle(5)
    expect(textOf(alerts(h.result()))).toContain('familyChanged.generic')
    expect(textOf(alerts(h.result()))).not.toContain('Owner')
    expect(retryButtons(h.result())).toHaveLength(0)
  })

  it('an ordinary failure keeps its retry button', async () => {
    const h = await mountHook(
      () => CategoryFormSheet({ ...base, editable: true, onSave: async () => { throw new Error('x') } }),
      5,
    )
    sheet(h.result()).props.onPrimary()
    await h.settle(5)
    expect(textOf(alerts(h.result()))).toContain('settings.submitError')
    expect(retryButtons(h.result())).toHaveLength(1)
  })
})

describe('GoalFormSheet', () => {
  const wallet = { id: 'w', name: 'W', currency: 'UZS', is_personal: false, has_active_goal: false, translation_key: null }
  const wallets = [wallet]
  const props = (onCreate: () => Promise<unknown>, editable = true) =>
    ({ open: true, mode: 'create', goal: null, wallets, editable, onClose: () => undefined, onCreate, onUpdate: async () => undefined }) as never

  async function submitted(onCreate: () => Promise<unknown>) {
    const h = await mountHook(() => GoalFormSheet(props(onCreate)), 5)
    const field = findAll(h.result(), (e) => e.props.label === 'goals.form.targetAmountLabel')[0] as { props: Record<string, any> }
    field.props.onChange('5000')
    await h.settle(3)
    sheet(h.result()).props.onPrimary()
    await h.settle(5)
    return h
  }

  it('refused after the role changed: goals are owner-only sentence, no retry', async () => {
    setRole('member')
    const h = await submitted(async () => { throw new FamilyChangedError() })
    expect(textOf(alerts(h.result()))).toContain('familyChanged.goalsOwnerOnly')
    expect(retryButtons(h.result())).toHaveLength(0)
  })

  it('a member sees the owner-only sentence up front and Save is off', async () => {
    const h = await mountHook(() => GoalFormSheet(props(async () => undefined, false)), 5)
    expect(textOf(alerts(h.result()))).toContain('familyChanged.goalsOwnerOnly')
    expect(sheet(h.result()).props.primaryDisabled).toBe(true)
  })
})

describe('WalletFormSheet', () => {
  it('another family: generic sentence (no category/wallet wording), no retry', async () => {
    const h = await mountHook(
      () =>
        WalletFormSheet({
          open: true, mode: 'create', wallet: null, sharedWalletCount: 0, personalWalletCount: 0,
          canPickWalletType: false, editable: true, onClose: () => undefined,
          onSave: async () => { throw new FamilyChangedError() },
          walletTypePickerOpen: false, onWalletTypePickerOpenChange: () => undefined,
        } as never),
      5,
    )
    const name = findAll(h.result(), (e) => e.type === 'input')[0] as { props: Record<string, any> }
    name.props.onChange({ target: { value: 'Копилка' } })
    await h.settle(3)
    sheet(h.result()).props.onPrimary()
    await h.settle(5)
    expect(textOf(alerts(h.result()))).toContain('familyChanged.generic')
    expect(retryButtons(h.result())).toHaveLength(0)
  })
})
