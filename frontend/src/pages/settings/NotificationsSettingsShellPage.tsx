import { useTranslation } from 'react-i18next'

import { patchMe } from '../../api/me'
import { SettingsEntityGroup } from '../../components/settings/SettingsEntityGroup'
import { SettingsToggleRow } from '../../components/settings/SettingsToggleRow'
import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'
import { useAuthStore } from '../../store/authStore'

export const NOTIFICATION_SHELL_ROWS = [
  {
    titleKey: 'settings.notificationsScreen.eveningTitle',
    subtitleKey: 'settings.notificationsScreen.eveningSubtitle',
    prefKey: 'evening' as const,
  },
  {
    titleKey: 'settings.notificationsScreen.weeklyTitle',
    subtitleKey: 'settings.notificationsScreen.weeklySubtitle',
    prefKey: 'weekly' as const,
  },
] as const

export function NotificationsSettingsBody() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const setLocalEveningReminder = useAuthStore((state) => state.setLocalEveningReminder)
  const setLocalWeeklyDigest = useAuthStore((state) => state.setLocalWeeklyDigest)

  const eveningEnabled = user?.eveningReminderEnabled ?? true
  const weeklyEnabled = user?.weeklyDigestEnabled ?? true

  const handleEveningToggle = () => {
    const nextValue = !eveningEnabled
    const previousValue = eveningEnabled
    setLocalEveningReminder(nextValue)

    void patchMe({ evening_reminder_enabled: nextValue }).catch(() => {
      setLocalEveningReminder(previousValue)
    })
  }

  const handleWeeklyToggle = () => {
    const nextValue = !weeklyEnabled
    const previousValue = weeklyEnabled
    setLocalWeeklyDigest(nextValue)

    void patchMe({ weekly_digest_enabled: nextValue }).catch(() => {
      setLocalWeeklyDigest(previousValue)
    })
  }

  const toggleHandlers = {
    evening: handleEveningToggle,
    weekly: handleWeeklyToggle,
  }

  const enabledByPref = {
    evening: eveningEnabled,
    weekly: weeklyEnabled,
  }

  return (
    <SettingsEntityGroup
      title={t('settings.notificationsScreen.groupTitle')}
      note={t('settings.notificationsScreen.note')}
    >
      {NOTIFICATION_SHELL_ROWS.map((row) => (
        <SettingsToggleRow
          key={row.titleKey}
          name={t(row.titleKey)}
          subtitle={t(row.subtitleKey)}
          enabled={enabledByPref[row.prefKey]}
          onToggle={toggleHandlers[row.prefKey]}
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
