import { useCallback, useEffect } from 'react'
import { useRawInitData } from '@tma.js/sdk-react'

import { clearAppPass, readAppPass } from '../api/authHeader'
import { exchangeInitDataForPass } from '../api/authPass'
import { MeRequestError, fetchMe } from '../api/me'
import i18n from '../i18n'
import { useAuthStore, type AuthErrorType } from '../store/authStore'

type AttemptResult = 'ready' | 'handled_error' | 'retry'

function handleMeError(
  error: unknown,
  setError: (errorType: Exclude<AuthErrorType, null>) => void,
): 'handled_error' | 'retry' {
  if (error instanceof MeRequestError) {
    if (error.errorType === 'not_onboarded') {
      setError('not_onboarded')
      return 'handled_error'
    }
    if (error.errorType === 'removed_from_family') {
      setError('removed_from_family')
      return 'handled_error'
    }
  }
  return 'retry'
}

export function useAuthBootstrap() {
  const rawInitData = useRawInitData()
  const setLoading = useAuthStore((state) => state.setLoading)
  const setReady = useAuthStore((state) => state.setReady)
  const setError = useAuthStore((state) => state.setError)

  const authenticate = useCallback(async () => {
    setLoading()

    const attempt = async (): Promise<AttemptResult> => {
      if (readAppPass()) {
        try {
          const user = await fetchMe()
          await i18n.changeLanguage(user.language)
          setReady(user)
          return 'ready'
        } catch (error) {
          clearAppPass()
          const handled = handleMeError(error, setError)
          if (handled === 'handled_error') {
            return 'handled_error'
          }
        }
      }

      if (!rawInitData) {
        return 'retry'
      }

      try {
        await exchangeInitDataForPass(rawInitData)
        const user = await fetchMe()
        await i18n.changeLanguage(user.language)
        setReady(user)
        return 'ready'
      } catch (error) {
        clearAppPass()
        return handleMeError(error, setError)
      }
    }

    const first = await attempt()
    if (first === 'ready' || first === 'handled_error') {
      return
    }

    const second = await attempt()
    if (second === 'ready' || second === 'handled_error') {
      return
    }

    setError('pass_failed')
  }, [rawInitData, setError, setLoading, setReady])

  useEffect(() => {
    void authenticate()
  }, [authenticate])

  return { retry: authenticate }
}
