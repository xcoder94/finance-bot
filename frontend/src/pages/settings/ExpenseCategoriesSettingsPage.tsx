import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import {
  createExpenseCategory,
  deleteExpenseCategory,
  getExpenseCategories,
  type ExpenseCategoryResponse,
} from '../../api/categories'
import { CategoryFormSheet } from '../../components/settings/CategoryFormSheet'
import { EntityDeleteConfirmSheet } from '../../components/settings/EntityDeleteConfirmSheet'
import { SettingsSectionLoadError, SettingsSectionLoading } from '../../components/settings/EditableEntityList'
import { SettingsEntityGroup } from '../../components/settings/SettingsEntityGroup'
import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'
import { SwipeableSettingsRow } from '../../components/settings/SwipeableSettingsRow'
import { LIMIT_EXPENSE_PARENTS, PARENT_CATEGORY_LIMIT } from '../../constants/entityLimits'
import { useAuthStore } from '../../store/authStore'
import {
  getCachedExpenseCategories,
  invalidateExpenseCategoryData,
  peekExpenseCategories,
} from '../../store/dataCacheStore'
import {
  buildExpenseParentDeleteIntro,
  CATEGORY_DELETE_DANGER_LABEL,
} from '../../utils/entityDeleteConfirmCopy'
import { getDisplayName } from '../../utils/getDisplayName'
import {
  countExpenseParents,
  countExpenseSubcategories,
  countNonProtectedExpenseParents,
  expenseCategoriesSubtitle,
  expenseParentRowSubtitle,
} from '../../utils/settingsSubtitles'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; items: ExpenseCategoryResponse[] }

type SheetState =
  | { kind: 'closed' }
  | { kind: 'form' }
  | { kind: 'delete'; categoryId: string }

function groupParents(categories: ExpenseCategoryResponse[]) {
  const parents = categories.filter((category) => category.parent_id === null)
  return parents.map((parent) => ({
    parent,
    subcategories: categories.filter((category) => category.parent_id === parent.id),
  }))
}

export function ExpenseCategoriesSettingsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)
  const isOwner = user?.role === 'owner'
  const familyId = user?.familyBudgetId ?? ''

  const [loadState, setLoadState] = useState<LoadState>(() => {
    const cached = peekExpenseCategories(familyId)
    return cached ? { status: 'success', items: cached } : { status: 'loading' }
  })
  const [reloadCount, setReloadCount] = useState(0)
  const [sheetState, setSheetState] = useState<SheetState>({ kind: 'closed' })
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(false)

  const loadCategories = useCallback(async () => {
    setLoadState((current) => (current.status === 'success' ? current : { status: 'loading' }))
    try {
      const items = await getCachedExpenseCategories(
        familyId,
        getExpenseCategories,
        reloadCount > 0,
      )
      setLoadState({ status: 'success', items })
    } catch {
      setLoadState((current) => (current.status === 'success' ? current : { status: 'error' }))
    }
  }, [familyId, reloadCount])

  useEffect(() => {
    void loadCategories()
  }, [loadCategories])

  const categories = loadState.status === 'success' ? loadState.items : []
  const grouped = useMemo(() => groupParents(categories), [categories])
  const parentCount = countExpenseParents(categories)
  const nonProtectedParentCount = countNonProtectedExpenseParents(categories)
  const subcategoryCount = countExpenseSubcategories(categories)

  const deleteTarget =
    sheetState.kind === 'delete'
      ? grouped.find((group) => group.parent.id === sheetState.categoryId)?.parent ?? null
      : null

  const deleteSubcategoryCount =
    sheetState.kind === 'delete'
      ? grouped.find((group) => group.parent.id === sheetState.categoryId)?.subcategories.length ?? 0
      : 0

  const openCreateForm = () => {
    setSheetState({ kind: 'form' })
  }

  const closeSheets = () => {
    setSheetState({ kind: 'closed' })
    setDeleteError(false)
  }

  const refreshAfterMutation = () => {
    invalidateExpenseCategoryData(familyId)
    setReloadCount((count) => count + 1)
  }

  const handleSave = async (payload: { name: string }) => {
    await createExpenseCategory(payload)
    refreshAfterMutation()
  }

  const handleConfirmDelete = async () => {
    if (!deleteTarget) {
      return
    }

    setDeleting(true)
    setDeleteError(false)
    try {
      await deleteExpenseCategory(deleteTarget.id)
      closeSheets()
      refreshAfterMutation()
    } catch {
      setDeleteError(true)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <SettingsSubPageShell
        title={t('settings.categoriesExpense')}
        backLabel={t('settings.toc.back')}
        backTo="/settings"
        actionLabel={isOwner ? t('settings.addCategory') : undefined}
        onAction={isOwner ? openCreateForm : undefined}
      >
        {loadState.status === 'loading' ? (
          <div className="settings-entity-page__loading">
            <SettingsSectionLoading />
          </div>
        ) : null}
        {loadState.status === 'error' ? (
          <SettingsSectionLoadError onRetry={() => setReloadCount((count) => count + 1)} />
        ) : null}
        {loadState.status === 'success' ? (
          <SettingsEntityGroup
            title={expenseCategoriesSubtitle(parentCount, subcategoryCount)}
            note={t('settings.categoryGroups.expenseNote')}
          >
            {grouped.map((group) => (
              <SwipeableSettingsRow
                key={group.parent.id}
                name={getDisplayName(group.parent, t)}
                subtitle={expenseParentRowSubtitle(group.subcategories.length)}
                onOpen={() => navigate(`/settings/expense-categories/${group.parent.id}`)}
                swipeDeleteEnabled={isOwner && !group.parent.is_protected}
                onDelete={() => setSheetState({ kind: 'delete', categoryId: group.parent.id })}
              />
            ))}
          </SettingsEntityGroup>
        ) : null}
      </SettingsSubPageShell>

      {sheetState.kind === 'form' ? (
        <CategoryFormSheet
          open
          mode="create"
          kind="expense-parent"
          category={null}
          atLimit={nonProtectedParentCount >= PARENT_CATEGORY_LIMIT}
          limitMessage={
            nonProtectedParentCount >= PARENT_CATEGORY_LIMIT ? LIMIT_EXPENSE_PARENTS : undefined
          }
          editable={isOwner}
          onClose={closeSheets}
          onSave={handleSave}
        />
      ) : null}

      {deleteTarget ? (
        <EntityDeleteConfirmSheet
          open={sheetState.kind === 'delete'}
          entityName={getDisplayName(deleteTarget, t)}
          transactionCount={deleteTarget.transaction_count}
          intro={buildExpenseParentDeleteIntro(
            deleteTarget.transaction_count,
            deleteSubcategoryCount,
          )}
          dangerLabel={CATEGORY_DELETE_DANGER_LABEL}
          onClose={closeSheets}
          onConfirm={() => void handleConfirmDelete()}
          confirming={deleting}
          error={deleteError}
          errorMessage={t('settings.submitError')}
          retryLabel={t('auth.retry')}
        />
      ) : null}
    </>
  )
}
