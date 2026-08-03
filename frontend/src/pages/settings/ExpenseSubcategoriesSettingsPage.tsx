import { useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'
import { useAuthStore } from '../../store/authStore'
import { peekExpenseCategories } from '../../store/dataCacheStore'
import { getDisplayName } from '../../utils/getDisplayName'

export function ExpenseSubcategoriesSettingsPage() {
  const { parentId } = useParams<{ parentId: string }>()
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const familyId = user?.familyBudgetId ?? ''
  const cached = peekExpenseCategories(familyId)
  const parent = cached?.find((category) => category.id === parentId)
  const title = parent ? getDisplayName(parent, t) : '—'

  return (
    <SettingsSubPageShell
      title={title}
      backLabel={t('settings.toc.backExpenseCategories')}
      backTo="/settings/expense-categories"
    />
  )
}
