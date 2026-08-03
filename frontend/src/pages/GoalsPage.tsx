import { Title } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

export function GoalsPage() {
  const { t } = useTranslation()

  return (
    <div className="page-content goals-page">
      <Title level="1" weight="2" className="home-page__title">
        {t('nav.goals')}
      </Title>
    </div>
  )
}
