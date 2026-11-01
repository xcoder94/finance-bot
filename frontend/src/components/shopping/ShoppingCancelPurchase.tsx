import { useState } from 'react'
import { useTranslation } from 'react-i18next'

type ShoppingCancelPurchaseProps = {
  onConfirm: () => void
  busy: boolean
  failed: boolean
  initialConfirming?: boolean
}

/** Secondary «Отменить закупку» with an explicit confirmation step (no accidental cancel). */
export function ShoppingCancelPurchase({
  onConfirm,
  busy,
  failed,
  initialConfirming = false,
}: ShoppingCancelPurchaseProps) {
  const { t } = useTranslation()
  const [confirming, setConfirming] = useState(initialConfirming)

  return (
    <div className="shopping-cancel">
      {confirming ? (
        <div className="shopping-cancel__confirm" role="alertdialog" aria-label={t('shopping.cancelPurchase')}>
          <div className="shopping-cancel__text">{t('shopping.cancelConfirmText')}</div>
          <div className="shopping-cancel__actions">
            <button type="button" className="shopping-cancel__no" disabled={busy} onClick={() => setConfirming(false)}>
              {t('shopping.cancelConfirmNo')}
            </button>
            <button type="button" className="shopping-cancel__yes" disabled={busy} onClick={onConfirm}>
              {t('shopping.cancelConfirmYes')}
            </button>
          </div>
        </div>
      ) : (
        <button type="button" className="shopping-cancel__open" disabled={busy} onClick={() => setConfirming(true)}>
          {t('shopping.cancelPurchase')}
        </button>
      )}
      {failed ? (
        <div className="shopping-amount__fail" role="alert">
          {t('shopping.cancelFailed')}
        </div>
      ) : null}
    </div>
  )
}
