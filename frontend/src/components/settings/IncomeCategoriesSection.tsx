import { useCallback, useEffect, useState } from 'react'
import { Section } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import {
  createIncomeCategory,
  deleteIncomeCategory,
  getIncomeCategories,
  type IncomeCategoryResponse,
} from '../../api/categories'
import { useAuthStore } from '../../store/authStore'
import {
  getCachedIncomeCategories,
  invalidateIncomeCategoryData,
  peekIncomeCategories,
} from '../../store/dataCacheStore'
import {
  EditableEntityList,
  SettingsSectionLoadError,
  SettingsSectionLoading,
} from './EditableEntityList'
import { getIncomeCategoryIcon } from './incomeCategoryIcon'
import { getDisplayName } from '../../utils/getDisplayName'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; items: IncomeCategoryResponse[] }

export function IncomeCategoriesSection() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const isOwner = user?.role === 'owner'
  const familyId = user?.familyBudgetId ?? ''

  const [loadState, setLoadState] = useState<LoadState>(() => {
    const cached = peekIncomeCategories(familyId)
    return cached ? { status: 'success', items: cached } : { status: 'loading' }
  })
  const [reloadCount, setReloadCount] = useState(0)

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
  }, [loadCategories, reloadCount])

  const handleAdd = async (payload: { name: string }) => {
    await createIncomeCategory({ name: payload.name })
    invalidateIncomeCategoryData(familyId)
    setReloadCount((count) => count + 1)
  }

  const handleDelete = async (categoryId: string) => {
    await deleteIncomeCategory(categoryId)
    invalidateIncomeCategoryData(familyId)
    setReloadCount((count) => count + 1)
  }

  return (
    <Section header={t('settings.categoriesIncome')}>
      {loadState.status === 'loading' ? <SettingsSectionLoading /> : null}
      {loadState.status === 'error' ? (
        <SettingsSectionLoadError onRetry={() => setReloadCount((count) => count + 1)} />
      ) : null}
      {loadState.status === 'success' ? (
        <EditableEntityList
          items={loadState.items}
          editable={isOwner}
          addLabelKey="settings.addCategory"
          getItemDisplayName={(category) => getDisplayName(category, t)}
          renderBefore={(category) => {
            const CategoryIcon = getIncomeCategoryIcon(category.name)
            return <CategoryIcon className="settings-entity-icon" aria-hidden="true" />
          }}
          onAdd={handleAdd}
          onDelete={handleDelete}
        />
      ) : null}
    </Section>
  )
}
