import { useTranslation } from 'react-i18next'

import { SettingsEntityGroup } from '../../components/settings/SettingsEntityGroup'
import { SettingsStaticRow } from '../../components/settings/SettingsStaticRow'
import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'

export const NOTIFICATION_SHELL_ROWS = [
  {
    titleKey: 'settings.notificationsScreen.eveningTitle',
    subtitleKey: 'settings.notificationsScreen.eveningSubtitle',
  },
  {
    titleKey: 'settings.notificationsScreen.weeklyTitle',
    subtitleKey: 'settings.notificationsScreen.weeklySubtitle',
  },
] as const

export function NotificationsSettingsBody() {
  const { t } = useTranslation()

  return (
    <SettingsEntityGroup
      title={t('settings.notificationsScreen.groupTitle')}
      note={t('settings.notificationsScreen.note')}
    >
      {NOTIFICATION_SHELL_ROWS.map((row) => (
        <SettingsStaticRow
          key={row.titleKey}
          name={t(row.titleKey)}
          subtitle={t(row.subtitleKey)}
        />
      ))}
    </SettingsEntityGroup>
  )
}

export function NotificationsSettingsShellPage() {
  const { t } = useTranslation()

  return (
    <SettingsSubPageShell
      title={t('settings.toc.notifications')}
      backLabel={t('settings.toc.back')}
      backTo="/settings"
    >
      <NotificationsSettingsBody />
    </SettingsSubPageShell>
  )
}
