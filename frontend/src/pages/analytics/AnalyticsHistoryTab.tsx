import { Text } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

export function AnalyticsHistoryTab() {
  const { t } = useTranslation()

  return (
    <div className="analytics-page__history-stub">
      <Text>{t('analytics.tabHistory')}</Text>
    </div>
  )
}
