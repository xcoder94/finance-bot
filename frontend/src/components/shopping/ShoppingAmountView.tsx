import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { PendingMethod } from '../../api/shopping'
import { parsePositiveInt } from '../../utils/transactionForm'
import { FormSheet } from '../forms/FormSheet'
import { FormSheetAmountField } from '../forms/transactionAddFields'

type FinishMethod = 'manual' | PendingMethod

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
  /** Way the user just tapped; keeps that tab open while the wait is being created. */
  botMethod: PendingMethod | null
  /** First tab shown (default: manual). Mainly for tests. */
  initialMethod?: FinishMethod
  onBotMethod: (method: PendingMethod) => void
  onAmount: (value: string) => void
  onOverLimit: (value: boolean) => void
  onSubmit: () => void
  onBack: () => void
}

function MethodIcon({ method }: { method: PendingMethod }) {
  const d =
    method === 'receipt'
      ? 'M5 3h12v16l-2-1.4-2 1.4-2-1.4-2 1.4-2-1.4L5 19zM8 8h6M8 12h6'
      : 'M11 3a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 10a6 6 0 0 0 12 0M11 16v3'
  return (
    <svg width="20" height="20" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  )
}

/** «Завершить закупку»: bottom sheet over the trip list, as in the mockup (shop: finish). */
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
  initialMethod,
  onBotMethod,
  onAmount,
  onOverLimit,
  onSubmit,
  onBack,
}: ShoppingAmountViewProps) {
  const { t } = useTranslation()
  const [picked, setPicked] = useState<FinishMethod>(initialMethod ?? 'manual')
  const requested: FinishMethod = botMethod ?? picked
  const method: FinishMethod = requested === 'receipt' && !photoEnabled ? 'manual' : requested
  const parsed = parsePositiveInt(amount)
  const canSubmit = parsed !== null && !overLimit && !busy

  const tabs: { id: FinishMethod; label: string }[] = [
    { id: 'manual', label: t('shopping.tabManual') },
    ...(photoEnabled ? [{ id: 'receipt' as const, label: t('shopping.tabReceipt') }] : []),
    { id: 'voice', label: t('shopping.tabVoice') },
  ]

  return (
    <FormSheet
      open
      title={t('shopping.finish')}
      intro={t('shopping.amountCaption', { n: count })}
      onClose={onBack}
      showPrimary={false}
    >
      <div className="shopping-seg" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={method === tab.id}
            className={`shopping-seg__item${method === tab.id ? ' shopping-seg__item--on' : ''}`}
            disabled={busy}
            onClick={() => setPicked(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {method === 'manual' ? (
        <>
          <FormSheetAmountField
            label={t('shopping.amountTitle')}
            value={amount}
            currencySuffix={currencySuffix}
            overLimit={overLimit}
            onChange={onAmount}
            onOverLimitChange={onOverLimit}
          />
          <button type="button" className="shopping-sheet__primary" disabled={!canSubmit} onClick={onSubmit}>
            {t('shopping.record')}
          </button>
        </>
      ) : (
        <>
          <div className="shopping-sheet__hint">
            <span className="shopping-sheet__hint-icon">
              <MethodIcon method={method} />
            </span>
            <div role="status">{method === 'voice' ? t('shopping.hintVoice') : t('shopping.hintReceipt')}</div>
          </div>
          <button
            type="button"
            className="shopping-sheet__primary"
            disabled={busy}
            onClick={() => onBotMethod(method)}
          >
            {method === 'voice' ? t('shopping.methodVoice') : t('shopping.methodReceipt')}
          </button>
        </>
      )}

      {failed || noWallet ? (
        <div className="shopping-amount__fail" role="alert">
          {t('shopping.recordFailed')}
        </div>
      ) : null}

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
    </FormSheet>
  )
}
