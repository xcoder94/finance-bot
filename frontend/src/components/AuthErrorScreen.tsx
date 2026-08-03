import { Button, Placeholder } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import type { AuthErrorType } from '../store/authStore'

type AuthErrorScreenProps = {
  errorType: AuthErrorType
  onRetry: () => void
}

function errorMessageKey(errorType: AuthErrorType): string {
  switch (errorType) {
    case 'unauthorized':
      return 'auth.unauthorized'
    case 'not_onboarded':
      return 'auth.notOnboarded'
    case 'removed_from_family':
      return 'auth.removedFromFamily'
    case 'pass_failed':
      return 'auth.passFailed'
    case 'network':
      return 'auth.networkError'
    default:
      return 'auth.networkError'
  }
}

function showsRetryButton(errorType: AuthErrorType): boolean {
  return errorType === 'pass_failed' || errorType === 'network'
}

export function AuthErrorScreen({ errorType, onRetry }: AuthErrorScreenProps) {
  const { t } = useTranslation()

  return (
    <div className="auth-screen">
      <Placeholder header={t(errorMessageKey(errorType))} />
      {showsRetryButton(errorType) ? (
        <Button mode="filled" size="m" onClick={onRetry}>
          {t('auth.retry')}
        </Button>
      ) : null}
    </div>
  )
}
