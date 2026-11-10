import { useTranslation } from 'react-i18next'

/** The one full-block error state (B18): same title, hint and «Попробовать снова» everywhere. */
export function FailBox({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="home-fail" role="alert">
      <div className="home-fail__icon" aria-hidden="true">!</div>
      <div className="home-fail__title">{t('home.loadError')}</div>
      <div className="home-fail__hint">{t('home.failHint')}</div>
      <button type="button" className="home-fail__btn" onClick={onRetry}>
        {t('auth.retry')}
      </button>
    </div>
  )
}
