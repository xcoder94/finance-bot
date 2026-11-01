import { useTranslation } from 'react-i18next'

import type { PendingMethod, PendingStatus } from '../../api/shopping'
import { ShoppingCancelPurchase } from './ShoppingCancelPurchase'

type ShoppingWaitingBannerProps = {
  method: PendingMethod
  status: PendingStatus
  onManual: () => void
  onCancelPurchase: () => void
  cancelBusy: boolean
  cancelFailed: boolean
}

/** Shown on the «Покупки» tab while the bot still waits for the receipt / voice amount. */
export function ShoppingWaitingBanner({
  method,
  status,
  onManual,
  onCancelPurchase,
  cancelBusy,
  cancelFailed,
}: ShoppingWaitingBannerProps) {
  const { t } = useTranslation()
  return (
    <div className="shopping-wait" role="status">
      {status === 'awaiting' ? (
        <div className="shopping-wait__text">
          {method === 'voice' ? t('shopping.waitVoice') : t('shopping.waitReceipt')}
        </div>
      ) : null}
      <button type="button" className="shopping-wait__manual" onClick={onManual}>
        {t('shopping.manualLink')}
      </button>
      <ShoppingCancelPurchase onConfirm={onCancelPurchase} busy={cancelBusy} failed={cancelFailed} />
    </div>
  )
}
