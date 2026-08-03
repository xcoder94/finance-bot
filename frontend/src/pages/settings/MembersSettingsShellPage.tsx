import { useTranslation } from 'react-i18next'

import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'

export function MembersSettingsShellPage() {
  const { t } = useTranslation()

  return (
    <SettingsSubPageShell
      title={t('settings.toc.members')}
      backLabel={t('settings.toc.back')}
      backTo="/settings"
    />
  )
}
