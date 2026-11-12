import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  closeGoal,
  createGoal,
  listGoals,
  patchGoal,
  type GoalResponse,
} from '../api/goals'
import { HomeApiError } from '../api/home'
import { getWallets, type WalletResponse } from '../api/wallets'
import { BlockError } from '../components/BlockError'
import { GoalCard } from '../components/goals/GoalCard'
import { GoalFormSheet, type GoalFormMode } from '../components/goals/GoalFormSheet'
import { useAuthStore } from '../store/authStore'
import { useDataCacheStore } from '../store/dataCacheStore'
import { EmptyStateIcon } from '../components/EmptyStateIcon'

type GoalTab = 'active' | 'closed'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; items: GoalResponse[] }

type SheetState =
  | { kind: 'closed' }
  | { kind: 'form'; mode: GoalFormMode; goalId: string | null }

export function GoalsPage() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const isOwner = user?.role === 'owner'
  const familyId = user?.familyBudgetId ?? ''
  // moves on every data change, a return to the app and a change of family
  const homeEpoch = useDataCacheStore((state) => state.homeEpoch)

  const [tab, setTab] = useState<GoalTab>('active')
  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [wallets, setWallets] = useState<WalletResponse[]>([])
  const [reloadCount, setReloadCount] = useState(0)
  const [sheetState, setSheetState] = useState<SheetState>({ kind: 'closed' })
  const [closingGoalId, setClosingGoalId] = useState<string | null>(null)

  const loadGoals = useCallback(async () => {
    setLoadState((current) => (current.status === 'success' ? current : { status: 'loading' }))
    try {
      const items = await listGoals(tab)
      setLoadState({ status: 'success', items })
    } catch {
      setLoadState((current) => (current.status === 'success' ? current : { status: 'error' }))
    }
  }, [tab])

  useEffect(() => {
    void loadGoals()
  }, [loadGoals, reloadCount, familyId, homeEpoch])

  useEffect(() => {
    let cancelled = false

    void getWallets()
      .then((items) => {
        if (!cancelled) {
          setWallets(items)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setWallets([])
        }
      })

    return () => {
      cancelled = true
    }
  }, [reloadCount, familyId, homeEpoch])

  const goals = loadState.status === 'success' ? loadState.items : []
  const showEmpty = tab === 'active' && goals.length === 0 && loadState.status === 'success'

  const selectedGoal =
    sheetState.kind === 'form' && sheetState.goalId
      ? goals.find((goal) => goal.id === sheetState.goalId) ?? null
      : null

  const openCreateForm = () => {
    setSheetState({ kind: 'form', mode: 'create', goalId: null })
  }

  const openEditForm = (goal: GoalResponse) => {
    setSheetState({ kind: 'form', mode: 'edit', goalId: goal.id })
  }

  const closeSheets = () => {
    setSheetState({ kind: 'closed' })
  }

  const refreshAfterMutation = () => {
    setReloadCount((count) => count + 1)
  }

  const handleCreate = async (payload: {
    wallet_id: string
    target_amount: number
    name?: string | null
    deadline?: string | null
  }) => {
    try {
      await createGoal(payload)
    } catch (error) {
      // The wallet already has a goal (made on another device a moment ago): show it, no error.
      if (!(error instanceof HomeApiError) || error.code !== 'goal_already_exists') {
        throw error
      }
    }
    refreshAfterMutation()
  }

  const handleUpdate = async (
    goalId: string,
    payload: {
      name?: string | null
      target_amount?: number
      deadline?: string | null
    },
  ) => {
    await patchGoal(goalId, payload)
    refreshAfterMutation()
  }

  const handleCloseGoal = async (goalId: string) => {
    setClosingGoalId(goalId)
    try {
      await closeGoal(goalId)
      refreshAfterMutation()
    } finally {
      setClosingGoalId(null)
    }
  }

  return (
    <>
      <div className="page-content goals-page">
        <div className="goals-page__header">
          <h1 className="goals-page__title">{t('goals.title')}</h1>
          {isOwner ? (
            <button type="button" className="goals-page__new-btn" onClick={openCreateForm}>
              {t('goals.newGoal')}
            </button>
          ) : null}
        </div>

        <div className="goals-page__tabs analytics-tabs" role="tablist" aria-label={t('goals.title')}>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'active'}
            className={
              tab === 'active'
                ? 'analytics-tabs__btn analytics-tabs__btn--active'
                : 'analytics-tabs__btn'
            }
            onClick={() => setTab('active')}
          >
            {t('goals.tabActive')}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'closed'}
            className={
              tab === 'closed'
                ? 'analytics-tabs__btn analytics-tabs__btn--active'
                : 'analytics-tabs__btn'
            }
            onClick={() => setTab('closed')}
          >
            {t('goals.tabClosed')}
          </button>
        </div>

        {loadState.status === 'loading' ? (
          <div className="goals-page__loading" aria-busy="true" />
        ) : null}

        {loadState.status === 'error' ? (
          <BlockError onRetry={() => setReloadCount((count) => count + 1)} />
        ) : null}

        {showEmpty ? (
          <div className="goals-page__empty">
            <EmptyStateIcon className="goals-page__empty-icon" />
            <div className="goals-page__empty-title">{t('goals.emptyTitle')}</div>
            <div className="goals-page__empty-subtitle">{t('goals.emptySubtitle')}</div>
            {isOwner ? (
              <button type="button" className="goals-page__empty-create" onClick={openCreateForm}>
                {t('goals.createGoal')}
              </button>
            ) : null}
          </div>
        ) : null}

        {loadState.status === 'success' && goals.length > 0 ? (
          <div className="goals-page__list">
            {goals.map((goal) => (
              <GoalCard
                key={goal.id}
                goal={goal}
                isOwner={isOwner}
                closing={closingGoalId === goal.id}
                onClose={(goalId) => void handleCloseGoal(goalId)}
                onEdit={openEditForm}
              />
            ))}
          </div>
        ) : null}
      </div>

      {sheetState.kind === 'form' ? (
        <GoalFormSheet
          open
          mode={sheetState.mode}
          goal={selectedGoal}
          wallets={wallets}
          editable={isOwner}
          onClose={closeSheets}
          onCreate={handleCreate}
          onUpdate={handleUpdate}
        />
      ) : null}
    </>
  )
}
