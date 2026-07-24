import { Placeholder } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

type PlaceholderPageProps = {
  titleKey: string
}

export function PlaceholderPage({ titleKey }: PlaceholderPageProps) {
  const { t } = useTranslation()

  return (
    <div className="page-content">
      <Placeholder header={t(titleKey)} description={t('placeholder.comingSoon')} />
    </div>
  )
}
