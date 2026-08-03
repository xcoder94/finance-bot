import { useTranslation } from 'react-i18next'

import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'

export function IncomeCategoriesSettingsPage() {
  const { t } = useTranslation()

  return (
    <SettingsSubPageShell
      title={t('settings.categoriesIncome')}
      backLabel={t('settings.toc.back')}
      backTo="/settings"
    />
  )
}
