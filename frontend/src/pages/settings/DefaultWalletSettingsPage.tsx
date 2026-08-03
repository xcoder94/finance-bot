import { useTranslation } from 'react-i18next'

import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'

export function DefaultWalletSettingsPage() {
  const { t } = useTranslation()

  return (
    <SettingsSubPageShell
      title={t('settings.toc.defaultWallet')}
      backLabel={t('settings.toc.back')}
      backTo="/settings"
    />
  )
}
