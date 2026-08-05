import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import {
  createExpenseCategory,
  deleteExpenseCategory,
  getExpenseCategories,
  patchExpenseCategory,
  type ExpenseCategoryResponse,
} from '../../api/categories'
import { CategoryFormSheet, type CategoryFormMode } from '../../components/settings/CategoryFormSheet'
import { EntityDeleteConfirmSheet } from '../../components/settings/EntityDeleteConfirmSheet'
import { SettingsSectionLoadError, SettingsSectionLoading } from '../../components/settings/EditableEntityList'
import { SettingsEntityGroup } from '../../components/settings/SettingsEntityGroup'
import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'
import { SwipeableSettingsRow } from '../../components/settings/SwipeableSettingsRow'
import { limitSubcategories, SUBCATEGORY_LIMIT } from '../../constants/entityLimits'
import { useAuthStore } from '../../store/authStore'
import {
  getCachedExpenseCategories,
  invalidateExpenseCategoryData,
  peekExpenseCategories,
} from '../../store/dataCacheStore'
import {
  buildExpenseParentDeleteIntro,
  buildSubcategoryDeleteIntro,
  CATEGORY_DELETE_DANGER_LABEL,
  formatEntityTransactionSubtitle,
  SUBCATEGORY_DELETE_DANGER_LABEL,
} from '../../utils/entityDeleteConfirmCopy'
import { getDisplayName } from '../../utils/getDisplayName'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; items: ExpenseCategoryResponse[] }

type SheetState =
  | { kind: 'closed' }
  | { kind: 'form'; mode: CategoryFormMode; categoryId: string | null }
  | { kind: 'delete'; target: 'parent' | 'subcategory'; categoryId: string }

export function ExpenseSubcategoriesSettingsPage() {
  const { parentId } = useParams<{ parentId: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
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
  const parent = useMemo(
    () => categories.find((category) => category.id === parentId && category.parent_id === null) ?? null,
    [categories, parentId],
  )
  const subcategories = useMemo(
    () => categories.filter((category) => category.parent_id === parentId),
    [categories, parentId],
  )
  const parentDisplayName = parent ? getDisplayName(parent, t) : '—'
  const subcategoryCount = subcategories.length

  const formCategory =
    sheetState.kind === 'form' && sheetState.categoryId
      ? subcategories.find((category) => category.id === sheetState.categoryId) ?? null
      : null

  const deleteSubcategoryTarget =
    sheetState.kind === 'delete' && sheetState.target === 'subcategory'
      ? subcategories.find((category) => category.id === sheetState.categoryId) ?? null
      : null

  const openCreateForm = () => {
    setSheetState({ kind: 'form', mode: 'create', categoryId: null })
  }

  const openEditForm = (categoryId: string) => {
    setSheetState({ kind: 'form', mode: 'edit', categoryId })
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
    if (sheetState.kind !== 'form' || !parentId) {
      return
    }

    if (sheetState.mode === 'create') {
      await createExpenseCategory({ name: payload.name, parent_id: parentId })
    } else if (sheetState.categoryId) {
      await patchExpenseCategory(sheetState.categoryId, payload)
    }
    refreshAfterMutation()
  }

  const handleConfirmDeleteParent = async () => {
    if (!parent) {
      return
    }

    setDeleting(true)
    setDeleteError(false)
    try {
      await deleteExpenseCategory(parent.id)
      closeSheets()
      invalidateExpenseCategoryData(familyId)
      navigate('/settings/expense-categories')
    } catch {
      setDeleteError(true)
    } finally {
      setDeleting(false)
    }
  }

  const handleConfirmDeleteSubcategory = async () => {
    if (!deleteSubcategoryTarget) {
      return
    }

    setDeleting(true)
    setDeleteError(false)
    try {
      await deleteExpenseCategory(deleteSubcategoryTarget.id)
      closeSheets()
      refreshAfterMutation()
    } catch {
      setDeleteError(true)
    } finally {
      setDeleting(false)
    }
  }

  const parentDeleteOpen = sheetState.kind === 'delete' && sheetState.target === 'parent' && parent !== null

  return (
    <>
      <SettingsSubPageShell
        title={parentDisplayName}
        backLabel={t('settings.toc.backExpenseCategories')}
        backTo="/settings/expense-categories"
        actionLabel={isOwner && parent ? t('settings.addSubcategory') : undefined}
        onAction={isOwner && parent ? openCreateForm : undefined}
        dangerLabel={
          isOwner && parent && !parent.is_protected ? CATEGORY_DELETE_DANGER_LABEL : undefined
        }
        onDanger={
          isOwner && parent && !parent.is_protected
            ? () => setSheetState({ kind: 'delete', target: 'parent', categoryId: parent.id })
            : undefined
        }
      >
        {loadState.status === 'loading' ? (
          <div className="settings-entity-page__loading">
            <SettingsSectionLoading />
          </div>
        ) : null}
        {loadState.status === 'error' ? (
          <SettingsSectionLoadError onRetry={() => setReloadCount((count) => count + 1)} />
        ) : null}
        {loadState.status === 'success' && !parent ? (
          <SettingsSectionLoadError onRetry={() => setReloadCount((count) => count + 1)} />
        ) : null}
        {loadState.status === 'success' && parent ? (
          <SettingsEntityGroup
            title={t('settings.categoryGroups.subcategoriesTitle')}
            note={t('settings.categoryGroups.subcategoriesNote')}
          >
            {subcategories.map((subcategory) => (
              <SwipeableSettingsRow
                key={subcategory.id}
                name={getDisplayName(subcategory, t)}
                subtitle={formatEntityTransactionSubtitle(subcategory.transaction_count)}
                onOpen={() => openEditForm(subcategory.id)}
                swipeDeleteEnabled={isOwner}
                onDelete={() =>
                  setSheetState({
                    kind: 'delete',
                    target: 'subcategory',
                    categoryId: subcategory.id,
                  })
                }
              />
            ))}
          </SettingsEntityGroup>
        ) : null}
      </SettingsSubPageShell>

      {sheetState.kind === 'form' && parent ? (
        <CategoryFormSheet
          open
          mode={sheetState.mode}
          kind="expense-subcategory"
          category={formCategory}
          displayName={formCategory ? getDisplayName(formCategory, t) : undefined}
          parentName={parentDisplayName}
          atLimit={sheetState.mode === 'create' && subcategoryCount >= SUBCATEGORY_LIMIT}
          limitMessage={
            sheetState.mode === 'create' && subcategoryCount >= SUBCATEGORY_LIMIT
              ? limitSubcategories(parentDisplayName)
              : undefined
          }
          editable={isOwner}
          onClose={closeSheets}
          onSave={handleSave}
        />
      ) : null}

      {parent && parentDeleteOpen ? (
        <EntityDeleteConfirmSheet
          open
          entityName={parentDisplayName}
          transactionCount={parent.transaction_count}
          intro={buildExpenseParentDeleteIntro(parent.transaction_count, subcategoryCount)}
          dangerLabel={CATEGORY_DELETE_DANGER_LABEL}
          onClose={closeSheets}
          onConfirm={() => void handleConfirmDeleteParent()}
          confirming={deleting}
          error={deleteError}
          errorMessage={t('settings.submitError')}
          retryLabel={t('auth.retry')}
        />
      ) : null}

      {deleteSubcategoryTarget ? (
        <EntityDeleteConfirmSheet
          open={sheetState.kind === 'delete' && sheetState.target === 'subcategory'}
          entityName={getDisplayName(deleteSubcategoryTarget, t)}
          transactionCount={deleteSubcategoryTarget.transaction_count}
          intro={buildSubcategoryDeleteIntro(
            deleteSubcategoryTarget.transaction_count,
            parentDisplayName,
          )}
          dangerLabel={SUBCATEGORY_DELETE_DANGER_LABEL}
          onClose={closeSheets}
          onConfirm={() => void handleConfirmDeleteSubcategory()}
          confirming={deleting}
          error={deleteError}
          errorMessage={t('settings.submitError')}
          retryLabel={t('auth.retry')}
        />
      ) : null}
    </>
  )
}
