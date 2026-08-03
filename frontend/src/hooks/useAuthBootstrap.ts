import { useCallback, useEffect } from 'react'
import { useRawInitData } from '@tma.js/sdk-react'

import { exchangeInitDataForPass } from '../api/authPass'
import { MeRequestError, fetchMe } from '../api/me'
import i18n from '../i18n'
import { useAuthStore } from '../store/authStore'

export function useAuthBootstrap() {
  const rawInitData = useRawInitData()
  const setLoading = useAuthStore((state) => state.setLoading)
  const setReady = useAuthStore((state) => state.setReady)
  const setError = useAuthStore((state) => state.setError)

  const authenticate = useCallback(async () => {
    setLoading()

    try {
      if (!rawInitData) {
        setError('unauthorized')
        return
      }

      await exchangeInitDataForPass(rawInitData)
      const user = await fetchMe()
      await i18n.changeLanguage(user.language)
      setReady(user)
    } catch (error) {
      if (error instanceof MeRequestError) {
        setError(error.errorType)
        return
      }
      setError('network')
    }
  }, [rawInitData, setError, setLoading, setReady])

  useEffect(() => {
    void authenticate()
  }, [authenticate])

  return { retry: authenticate }
}
