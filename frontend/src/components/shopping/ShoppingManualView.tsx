import { useTranslation } from 'react-i18next'

import type { PendingMethod } from '../../api/shopping'
import { parsePositiveInt } from '../../utils/transactionForm'
import { FormSheetAmountField } from '../forms/transactionAddFields'

type ShoppingManualViewProps = {
  method: PendingMethod
  /** `awaiting`: the bot still waits, nothing was sent yet; `unrecognized`: the bot could not read it. */
  status: 'awaiting' | 'unrecognized'
  amount: string
  overLimit: boolean
  currencySuffix: string
  busy: boolean
  failed: boolean
  /** The ticked items are known on this device, so the bot way can be repeated. */
  canRetry: boolean
  onAmount: (value: string) => void
  onOverLimit: (value: boolean) => void
  onSubmit: () => void
  onRetry: () => void
  onCancel: () => void
}

/** «Введите сумму вручную»: the bot could not read the amount, or the user came back himself. */
export function ShoppingManualView({
  method,
  status,
  amount,
  overLimit,
  currencySuffix,
  busy,
  failed,
  canRetry,
  onAmount,
  onOverLimit,
  onSubmit,
  onRetry,
  onCancel,
}: ShoppingManualViewProps) {
  const { t } = useTranslation()
  const canSubmit = parsePositiveInt(amount) !== null && !overLimit && !busy

  return (
    <div className="shopping-page shopping-page--bar">
      <div className="shopping-page__header">
        <h1 className="shopping-page__title">{t('shopping.manualTitle')}</h1>
      </div>
      <div className="shopping-amount__caption">
        {status === 'awaiting'
          ? t('shopping.manualWaiting')
          : method === 'voice'
            ? t('shopping.manualVoice')
            : t('shopping.manualReceipt')}
      </div>

      <FormSheetAmountField
        value={amount}
        currencySuffix={currencySuffix}
        overLimit={overLimit}
        onChange={onAmount}
        onOverLimitChange={onOverLimit}
      />

      {canRetry ? (
        <button type="button" className="shopping-method" onClick={onRetry} disabled={busy}>
          {method === 'voice' ? t('shopping.retryVoice') : t('shopping.retryReceipt')}
        </button>
      ) : null}

      {failed ? (
        <div className="shopping-amount__fail" role="alert">
          {t('shopping.recordFailed')}
        </div>
      ) : null}

      <div className="shopping-trip__bar">
        <button type="button" className="shopping-trip__cancel" onClick={onCancel} disabled={busy}>
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
