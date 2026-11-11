import { useEffect } from 'react'

import { invalidateFamilyData } from '../store/dataCacheStore'
import { subscribeBridgeVisible } from '../telegram/bridgeVisibility'
import { createReturnRefresher } from '../utils/returnRefresh'

type WebAppLike = {
  onEvent?: (name: string, cb: () => void) => void
  offEvent?: (name: string, cb: () => void) => void
}

/**
 * Re-reads the family data when the user comes back to the app (browser visibilitychange, Telegram
 * `activated`, Mini Apps bridge visibility_changed). Throttled, no polling, no pull-to-refresh.
 * Invalidation bumps homeEpoch, which Home, Wallets and Analytics already depend on.
 */
export function useRefreshOnReturn(familyId: string): void {
  useEffect(() => {
    if (!familyId) return
    const refresher = createReturnRefresher({
      now: Date.now,
      onRefresh: () => invalidateFamilyData(familyId),
    })
    const onReturn = () => refresher.onReturn()
    const onVisibility = () => {
      if (document.visibilityState === 'visible') onReturn()
    }
    document.addEventListener('visibilitychange', onVisibility)
    const stopBridge = subscribeBridgeVisible(onReturn)
    const app = (window as unknown as { Telegram?: { WebApp?: WebAppLike } }).Telegram?.WebApp
    app?.onEvent?.('activated', onReturn)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      stopBridge()
      app?.offEvent?.('activated', onReturn)
    }
  }, [familyId])
}
