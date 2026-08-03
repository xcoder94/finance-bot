import { useTranslation } from 'react-i18next'

import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'

export function NotificationsSettingsShellPage() {
  const { t } = useTranslation()

  return (
    <SettingsSubPageShell
      title={t('settings.toc.notifications')}
      backLabel={t('settings.toc.back')}
      backTo="/settings"
    />
  )
}
