import { Button, Placeholder } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

export function TransactionGonePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  return (
    <div className="auth-screen">
      <Placeholder header={t('transaction.gone')} />
      <Button mode="filled" size="m" onClick={() => navigate('/', { replace: true })}>
        {t('addTransaction.goHome')}
      </Button>
    </div>
  )
}
