import { useTranslation } from 'react-i18next'

import type { PendingMethod } from '../../api/shopping'
import { parsePositiveInt } from '../../utils/transactionForm'
import { FormSheetAmountField } from '../forms/transactionAddFields'

type ShoppingAmountViewProps = {
  count: number
  amount: string
  overLimit: boolean
  currencySuffix: string
  categoryLabel: string
  walletLabel: string
  busy: boolean
  failed: boolean
  noWallet: boolean
  /** Photo way is offered only when the server says the bot reads receipts. */
  photoEnabled: boolean
  /** Way the user just tapped: shows the minimise hint while the wait is being created. */
  botMethod: PendingMethod | null
  onBotMethod: (method: PendingMethod) => void
  onAmount: (value: string) => void
  onOverLimit: (value: boolean) => void
  onSubmit: () => void
  onBack: () => void
}

export function ShoppingAmountView({
  count,
  amount,
  overLimit,
  currencySuffix,
  categoryLabel,
  walletLabel,
  busy,
  failed,
  noWallet,
  photoEnabled,
  botMethod,
  onBotMethod,
  onAmount,
  onOverLimit,
  onSubmit,
  onBack,
}: ShoppingAmountViewProps) {
  const { t } = useTranslation()
  const parsed = parsePositiveInt(amount)
  const canSubmit = parsed !== null && !overLimit && !busy

  return (
    <div className="shopping-page shopping-page--bar">
      <div className="shopping-page__header">
        <h1 className="shopping-page__title">{t('shopping.amountTitle')}</h1>
      </div>
      <div className="shopping-amount__caption">{t('shopping.amountCaption', { n: count })}</div>

      <FormSheetAmountField
        value={amount}
        currencySuffix={currencySuffix}
        overLimit={overLimit}
        onChange={onAmount}
        onOverLimitChange={onOverLimit}
      />

      <div className="shopping-amount__rows">
        <div className="shopping-amount__row">
          <span className="shopping-amount__label">{t('shopping.rowCategory')}</span>
          <span className="shopping-amount__value">{categoryLabel}</span>
        </div>
        <div className="shopping-amount__row">
          <span className="shopping-amount__label">{t('shopping.rowWallet')}</span>
          <span className="shopping-amount__value">{walletLabel}</span>
        </div>
      </div>

      <div className="shopping-methods">
        {photoEnabled ? (
          <button
            type="button"
            className="shopping-method"
            disabled={busy}
            onClick={() => onBotMethod('receipt')}
          >
            {t('shopping.methodReceipt')}
          </button>
        ) : null}
        <button
          type="button"
          className="shopping-method"
          disabled={busy}
          onClick={() => onBotMethod('voice')}
        >
          {t('shopping.methodVoice')}
        </button>
        {botMethod ? (
          <div className="shopping-amount__caption" role="status">
            {botMethod === 'voice' ? t('shopping.hintVoice') : t('shopping.hintReceipt')}
          </div>
        ) : null}
      </div>

      {failed || noWallet ? (
        <div className="shopping-amount__fail" role="alert">
          {t('shopping.recordFailed')}
        </div>
      ) : null}

      <div className="shopping-trip__bar">
        <button type="button" className="shopping-trip__cancel" onClick={onBack} disabled={busy}>
          {t('shopping.cancel')}
        </button>
        <button
          type="button"
          className="shopping-trip__finish"
          disabled={!canSubmit}
          onClick={onSubmit}
        >
          {t('shopping.record')}
        </button>
      </div>
    </div>
  )
}
