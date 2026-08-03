import { useTranslation } from 'react-i18next'

import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'

export function ExpenseCategoriesSettingsPage() {
  const { t } = useTranslation()

  return (
    <SettingsSubPageShell
      title={t('settings.categoriesExpense')}
      backLabel={t('settings.toc.back')}
      backTo="/settings"
    />
  )
}
