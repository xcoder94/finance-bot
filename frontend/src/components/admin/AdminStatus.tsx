import { useTranslation } from 'react-i18next'

export function AdminLoading() {
  const { t } = useTranslation('admin')
  return <p className="admin-note">{t('loading')}</p>
}

export function AdminLoadError({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation('admin')
  return (
    <div className="admin-note">
      <p>{t('loadFailed')}</p>
      <button type="button" className="admin-btn" onClick={onRetry}>
        {t('retry')}
      </button>
    </div>
  )
}
