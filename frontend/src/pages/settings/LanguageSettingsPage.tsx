import { useTranslation } from 'react-i18next'

import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'

export function LanguageSettingsPage() {
  const { t } = useTranslation()

  return (
    <SettingsSubPageShell
      title={t('settings.language')}
      backLabel={t('settings.toc.back')}
      backTo="/settings"
    />
  )
}
