import { useTranslation } from 'react-i18next'

import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'

export function WalletsSettingsPage() {
  const { t } = useTranslation()

  return (
    <SettingsSubPageShell
      title={t('settings.wallets')}
      backLabel={t('settings.toc.back')}
      backTo="/settings"
    />
  )
}
