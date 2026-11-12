import { describe, expect, it, vi } from 'vitest'

// 1) The goal list follows the person's family without a restart (same as Home/History/Analytics).
// 2) A goal for that wallet was created from another device: 409 goal_already_exists. The list is
//    reread and the goal shown, not the generic "failed to save".
vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../test/hookHarness')
  return reactHarnessModule()
})
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('../i18n/t', () => ({ t: (key: string) => key }))
vi.mock('../i18n', () => ({ default: { language: 'ru' } }))

const world = vi.hoisted(() => ({
  familyId: 'old',
  epoch: 0,
  goals: [] as Array<{ id: string; name: string }>,
  listCalls: 0,
}))
vi.mock('../api/goals', async () => {
  const { HomeApiError } = await import('../api/home')
  return {
    listGoals: async () => {
      world.listCalls += 1
      return world.goals
    },
    createGoal: async () => {
      // somebody else created it on that wallet a moment ago
      world.goals = [{ id: 'g1', name: 'Машина' }]
      throw new HomeApiError(undefined, 'goal_already_exists')
    },
    patchGoal: vi.fn(),
    closeGoal: vi.fn(),
  }
})
vi.mock('../api/wallets', () => ({ getWallets: async () => [] }))
vi.mock('../store/authStore', () => ({
  useAuthStore: (select: (s: unknown) => unknown) => select({ user: { familyBudgetId: world.familyId, role: 'owner' } }),
}))
vi.mock('../store/dataCacheStore', () => ({
  useDataCacheStore: (select: (s: unknown) => unknown) => select({ homeEpoch: world.epoch }),
}))
vi.mock('../components/BlockError', () => ({ BlockError: () => null }))
vi.mock('../components/EmptyStateIcon', () => ({ EmptyStateIcon: () => null }))
vi.mock('../components/goals/GoalCard', () => ({ GoalCard: () => null }))
vi.mock('../components/goals/GoalFormSheet', () => ({ GoalFormSheet: () => null }))

const { mountHook } = await import('../test/hookHarness')
const { findAll } = await import('../test/elementTree')
const { GoalsPage } = await import('./GoalsPage')
const { GoalCard } = await import('../components/goals/GoalCard')
const { GoalFormSheet } = await import('../components/goals/GoalFormSheet')

describe('Goals page', () => {
  it('rereads the goals when the family data is invalidated (return to the app, family change)', async () => {
    world.goals = []
    world.listCalls = 0
    const h = await mountHook(() => GoalsPage(), 10)
    expect(world.listCalls).toBe(1)
    world.epoch += 1
    world.familyId = 'new'
    h.rerender()
    await h.settle(10)
    expect(world.listCalls).toBeGreaterThan(1)
  })

  it('goal_already_exists: the goal is reread and shown, the form closes without an error', async () => {
    world.goals = []
    const h = await mountHook(() => GoalsPage(), 10)
    const newButton = findAll(h.result(), (e) => e.type === 'button' && e.props.className === 'goals-page__new-btn')[0]
    ;(newButton.props.onClick as () => void)()
    await h.settle(3)
    const form = () => findAll(h.result(), (e) => e.type === GoalFormSheet)[0] as { props: Record<string, any> }
    await expect(form().props.onCreate({ wallet_id: 'w', target_amount: 5 })).resolves.toBeUndefined()
    await h.settle(10)
    expect(findAll(h.result(), (e) => e.type === GoalCard)).toHaveLength(1)
  })
})
