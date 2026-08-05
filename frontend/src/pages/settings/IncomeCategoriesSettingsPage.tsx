import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  createIncomeCategory,
  deleteIncomeCategory,
  getIncomeCategories,
  patchIncomeCategory,
  type IncomeCategoryResponse,
} from '../../api/categories'
import { CategoryFormSheet, type CategoryFormMode } from '../../components/settings/CategoryFormSheet'
import { EntityDeleteConfirmSheet } from '../../components/settings/EntityDeleteConfirmSheet'
import { SettingsSectionLoadError, SettingsSectionLoading } from '../../components/settings/EditableEntityList'
import { SettingsEntityGroup } from '../../components/settings/SettingsEntityGroup'
import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'
import { SwipeableSettingsRow } from '../../components/settings/SwipeableSettingsRow'
import {
  INCOME_CATEGORY_LIMIT,
  LIMIT_INCOME_CATEGORIES,
} from '../../constants/entityLimits'
import { useAuthStore } from '../../store/authStore'
import {
  getCachedIncomeCategories,
  invalidateIncomeCategoryData,
  peekIncomeCategories,
} from '../../store/dataCacheStore'
import {
  buildIncomeCategoryDeleteIntro,
  CATEGORY_DELETE_DANGER_LABEL,
  formatEntityTransactionSubtitle,
} from '../../utils/entityDeleteConfirmCopy'
import { getDisplayName } from '../../utils/getDisplayName'
import { incomeCategoriesSubtitle } from '../../utils/settingsSubtitles'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; items: IncomeCategoryResponse[] }

type SheetState =
  | { kind: 'closed' }
  | { kind: 'form'; mode: CategoryFormMode; categoryId: string | null }
  | { kind: 'delete'; categoryId: string }

export function IncomeCategoriesSettingsPage() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const isOwner = user?.role === 'owner'
  const familyId = user?.familyBudgetId ?? ''

  const [loadState, setLoadState] = useState<LoadState>(() => {
    const cached = peekIncomeCategories(familyId)
    return cached ? { status: 'success', items: cached } : { status: 'loading' }
  })
  const [reloadCount, setReloadCount] = useState(0)
  const [sheetState, setSheetState] = useState<SheetState>({ kind: 'closed' })
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(false)

  const loadCategories = useCallback(async () => {
    setLoadState((current) => (current.status === 'success' ? current : { status: 'loading' }))
    try {
      const items = await getCachedIncomeCategories(
        familyId,
        getIncomeCategories,
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
  const categoryCount = categories.length

  const formCategory =
    sheetState.kind === 'form' && sheetState.categoryId
      ? categories.find((category) => category.id === sheetState.categoryId) ?? null
      : null

  const deleteTarget =
    sheetState.kind === 'delete'
      ? categories.find((category) => category.id === sheetState.categoryId) ?? null
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
    invalidateIncomeCategoryData(familyId)
    setReloadCount((count) => count + 1)
  }

  const handleSave = async (payload: { name: string }) => {
    if (sheetState.kind !== 'form') {
      return
    }

    if (sheetState.mode === 'create') {
      await createIncomeCategory(payload)
    } else if (sheetState.categoryId) {
      await patchIncomeCategory(sheetState.categoryId, payload)
    }
    refreshAfterMutation()
  }

  const handleConfirmDelete = async () => {
    if (!deleteTarget) {
      return
    }

    setDeleting(true)
    setDeleteError(false)
    try {
      await deleteIncomeCategory(deleteTarget.id)
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
        title={t('settings.categoriesIncome')}
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
            title={incomeCategoriesSubtitle(categoryCount)}
            note={t('settings.categoryGroups.incomeNote')}
          >
            {categories.map((category) => (
              <SwipeableSettingsRow
                key={category.id}
                name={getDisplayName(category, t)}
                subtitle={formatEntityTransactionSubtitle(category.transaction_count)}
                onOpen={() => openEditForm(category.id)}
                swipeDeleteEnabled={isOwner}
                onDelete={() => setSheetState({ kind: 'delete', categoryId: category.id })}
              />
            ))}
          </SettingsEntityGroup>
        ) : null}
      </SettingsSubPageShell>

      {sheetState.kind === 'form' ? (
        <CategoryFormSheet
          open
          mode={sheetState.mode}
          kind="income"
          category={formCategory}
          displayName={formCategory ? getDisplayName(formCategory, t) : undefined}
          atLimit={sheetState.mode === 'create' && categoryCount >= INCOME_CATEGORY_LIMIT}
          limitMessage={
            sheetState.mode === 'create' && categoryCount >= INCOME_CATEGORY_LIMIT
              ? LIMIT_INCOME_CATEGORIES
              : undefined
          }
          editable={isOwner}
          onClose={closeSheets}
          onSave={handleSave}
          onDelete={
            sheetState.mode === 'edit' && isOwner && formCategory
              ? () => setSheetState({ kind: 'delete', categoryId: formCategory.id })
              : undefined
          }
        />
      ) : null}

      {deleteTarget ? (
        <EntityDeleteConfirmSheet
          open={sheetState.kind === 'delete'}
          entityName={getDisplayName(deleteTarget, t)}
          transactionCount={deleteTarget.transaction_count}
          intro={buildIncomeCategoryDeleteIntro(deleteTarget.transaction_count)}
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
