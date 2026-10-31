import { Spinner } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

export function SplashScreen() {
  const { t } = useTranslation()
  return (
    <div className="auth-screen">
      <Spinner size="m" />
      <p className="auth-screen__message">{t('common.loading')}</p>
    </div>
  )
}
