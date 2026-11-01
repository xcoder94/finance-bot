import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import type { ShoppingPurchase } from '../../api/shopping'
import { haptic } from '../../telegram/haptic'
import { AnimatedTick } from '../AnimatedTick'
import { formatCurrency } from '../../utils/formatCurrency'

type ShoppingResultViewProps = {
  purchase: ShoppingPurchase
  /** How many items were sent; fewer recorded means someone else already bought some. */
  requested?: number
  /** Translated labels known on the client; fall back to the API text. */
  categoryLabel: string | null
  walletLabel: string | null
  onDone: () => void
}

export function ShoppingResultView({
  purchase,
  requested,
  categoryLabel,
  walletLabel,
  onDone,
}: ShoppingResultViewProps) {
  const { t } = useTranslation()
  const currency = purchase.currency === 'USD' ? 'USD' : 'UZS'
  const line = [categoryLabel ?? purchase.category_label, walletLabel ?? purchase.wallet_name].join(' · ')
  useEffect(() => {
    haptic.success()
  }, [])
  const lost = requested !== undefined && purchase.items_recorded < requested

  return (
    <div className="shopping-page shopping-result">
      <div className="shopping-result__tick" aria-hidden="true">
        <AnimatedTick size={26} />
      </div>
      <div className="shopping-result__title" role="status">
        {t('shopping.resultTitle', { count: purchase.items_recorded })}
      </div>
      <div className="shopping-list shopping-result__card">
        <div className="shopping-result__row">
          <span className="shopping-result__key">{t('shopping.resultSum')}</span>
          <span className="shopping-result__val shopping-result__val--exp">
            −{formatCurrency(purchase.amount, currency)}
          </span>
        </div>
        <div className="shopping-result__row">
          <span className="shopping-result__key">{t('shopping.resultLeft')}</span>
          <span className="shopping-result__val">{formatCurrency(purchase.remaining, 'UZS')}</span>
        </div>
      </div>
      <div className="shopping-result__note">
        {line}
        <br />
        {t('shopping.resultNote', { k: purchase.items_left })}
        {lost ? (
          <>
            <br />
            {t('shopping.alreadyBought')}
          </>
        ) : null}
      </div>
      <button type="button" className="shopping-page__start-btn shopping-result__done" onClick={onDone}>
        {t('shopping.done')}
      </button>
    </div>
  )
}
