import { useCallback, useEffect, useMemo, useState } from 'react'
import { Select, Textarea } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import {
  fetchTransaction,
  fetchWallets,
  updateTransferTransaction,
  type TransactionResponse,
  type Wallet,
} from '../api/transactions'
import {
  LimitedDigitInput,
  MaskedDateTimeInput,
  TransactionFormField,
  TransactionFormLayout,
  TransactionFormLoadError,
  TransactionFormLoading,
  TransactionReceiveRow,
  TransactionSubmitError,
} from '../components/transaction-form/TransactionFormShared'
import { useAuthStore } from '../store/authStore'
import {
  cacheTransaction,
  getCachedTransaction,
  getCachedWallets,
  invalidateHomeData,
} from '../store/dataCacheStore'
import {
  computeTransferToAmount,
  formatReceiveAmount,
  formatWalletLabel,
  isoDatetimeToMaskedDatetime,
  isValidMaskedDatetime,
  maskedDatetimeToIso,
  parsePositiveInt,
} from '../utils/transactionForm'
import { getDisplayName } from '../utils/getDisplayName'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; wallets: Wallet[]; transaction: TransactionResponse }

export function EditTransferPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const familyId = useAuthStore((state) => state.user?.familyBudgetId ?? '')

  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [loadRetry, setLoadRetry] = useState(0)

  const [transactionDate, setTransactionDate] = useState('')
  const [dateError, setDateError] = useState(false)
  const [sourceWalletId, setSourceWalletId] = useState('')
  const [destWalletId, setDestWalletId] = useState('')
  const [amount, setAmount] = useState('')
  const [amountOverLimit, setAmountOverLimit] = useState(false)
  const [rate, setRate] = useState('')
  const [rateOverLimit, setRateOverLimit] = useState(false)
  const [comment, setComment] = useState('')

  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(false)

  const loadData = useCallback(async () => {
    if (!id) {
      setLoadState({ status: 'error' })
      return
    }

    setLoadState({ status: 'loading' })
    try {
      const [wallets, transaction] = await Promise.all([
        getCachedWallets(familyId, fetchWallets, loadRetry > 0),
        getCachedTransaction(familyId, id, () => fetchTransaction(id), loadRetry > 0),
      ])

      if (transaction.type !== 'transfer') {
        setLoadState({ status: 'error' })
        return
      }

      setTransactionDate(isoDatetimeToMaskedDatetime(transaction.transaction_date))
      setSourceWalletId(transaction.wallet_id)
      setDestWalletId(transaction.to_wallet_id ?? '')
      setAmount(String(transaction.amount))
      setRate(
        transaction.rate !== null ? String(Math.round(Number(transaction.rate))) : '',
      )
      setComment(transaction.comment ?? '')
      setLoadState({ status: 'success', wallets, transaction })
    } catch {
      setLoadState({ status: 'error' })
    }
  }, [familyId, id, loadRetry])

  useEffect(() => {
    void loadData()
  }, [loadData, loadRetry])

  const sourceWallet = useMemo(() => {
    if (loadState.status !== 'success') {
      return null
    }
    return loadState.wallets.find((wallet) => wallet.id === sourceWalletId) ?? null
  }, [loadState, sourceWalletId])

  const destWallet = useMemo(() => {
    if (loadState.status !== 'success') {
      return null
    }
    return loadState.wallets.find((wallet) => wallet.id === destWalletId) ?? null
  }, [loadState, destWalletId])

  const isCrossCurrency = Boolean(
    sourceWallet && destWallet && sourceWallet.currency !== destWallet.currency,
  )

  const receiveAmount = useMemo(() => {
    const parsedAmount = parsePositiveInt(amount)
    if (!sourceWallet || !destWallet || parsedAmount === null) {
      return 0
    }
    if (!isCrossCurrency) {
      return parsedAmount
    }
    const parsedRate = parsePositiveInt(rate)
    if (parsedRate === null) {
      return 0
    }
    return computeTransferToAmount(
      sourceWallet.currency,
      destWallet.currency,
      parsedAmount,
      parsedRate,
    )
  }, [amount, rate, sourceWallet, destWallet, isCrossCurrency])

  const handleSourceWalletChange = (nextSourceWalletId: string) => {
    setSourceWalletId(nextSourceWalletId)
    if (nextSourceWalletId === destWalletId && loadState.status === 'success') {
      const alternative = loadState.wallets.find((wallet) => wallet.id !== nextSourceWalletId)
      setDestWalletId(alternative?.id ?? '')
    }
  }

  const validateDate = () => {
    const valid = isValidMaskedDatetime(transactionDate)
    setDateError(!valid)
    return valid
  }

  const handleSubmit = async () => {
    if (!id || !validateDate()) {
      return
    }

    const parsedAmount = parsePositiveInt(amount)
    if (
      !parsedAmount ||
      !sourceWalletId ||
      !destWalletId ||
      sourceWalletId === destWalletId ||
      amountOverLimit
    ) {
      return
    }

    let parsedRate: number | undefined
    if (isCrossCurrency) {
      const rateValue = parsePositiveInt(rate)
      if (rateValue === null || rateOverLimit) {
        return
      }
      parsedRate = rateValue
    }

    const transactionDateIso = maskedDatetimeToIso(transactionDate)
    if (!transactionDateIso) {
      setDateError(true)
      return
    }

    setSubmitting(true)
    setSubmitError(false)

    try {
      const updated = await updateTransferTransaction(id, {
        transaction_date: transactionDateIso,
        wallet_id: sourceWalletId,
        to_wallet_id: destWalletId,
        amount: parsedAmount,
        ...(parsedRate !== undefined ? { rate: parsedRate } : {}),
        comment: comment.trim() || null,
      })
      cacheTransaction(familyId, updated)
      invalidateHomeData(familyId)
      navigate('/history', { replace: true })
    } catch {
      setSubmitError(true)
    } finally {
      setSubmitting(false)
    }
  }

  if (loadState.status === 'loading') {
    return <TransactionFormLoading />
  }

  if (loadState.status === 'error') {
    return (
      <TransactionFormLoadError onRetry={() => setLoadRetry((count) => count + 1)} />
    )
  }

  const { wallets } = loadState
  const destinationOptions = wallets.filter((wallet) => wallet.id !== sourceWalletId)
  const parsedAmount = parsePositiveInt(amount)
  const parsedRate = parsePositiveInt(rate)
  const canSubmit =
    wallets.length >= 2 &&
    parsedAmount !== null &&
    Boolean(sourceWalletId) &&
    Boolean(destWalletId) &&
    sourceWalletId !== destWalletId &&
    !amountOverLimit &&
    isValidMaskedDatetime(transactionDate) &&
    (!isCrossCurrency || (parsedRate !== null && !rateOverLimit))

  const amountLabel = sourceWallet
    ? t('addTransaction.amountWithCurrency', { currency: sourceWallet.currency })
    : t('addTransaction.amount')

  return (
    <TransactionFormLayout
      titleKey="editTransfer.title"
      submitLabelKey="editTransaction.save"
      onCancel={() => navigate('/history')}
      onSubmit={() => void handleSubmit()}
      submitting={submitting}
      submitDisabled={!canSubmit}
    >
      <TransactionFormField>
        <MaskedDateTimeInput
          value={transactionDate}
          onChange={setTransactionDate}
          hasError={dateError}
          onBlur={validateDate}
          onEdit={() => setDateError(false)}
        />
      </TransactionFormField>

      <TransactionFormField>
        <Select
          header={t('addTransaction.sourceWallet')}
          value={sourceWalletId}
          onChange={(event) => handleSourceWalletChange(event.target.value)}
          disabled={wallets.length === 0}
        >
          {wallets.map((wallet) => (
            <option key={wallet.id} value={wallet.id}>
              {formatWalletLabel(getDisplayName(wallet, t), wallet.currency)}
            </option>
          ))}
        </Select>
      </TransactionFormField>

      <TransactionFormField>
        <Select
          header={t('addTransaction.destinationWallet')}
          value={destWalletId}
          onChange={(event) => setDestWalletId(event.target.value)}
          disabled={destinationOptions.length === 0}
        >
          {destinationOptions.map((wallet) => (
            <option key={wallet.id} value={wallet.id}>
              {formatWalletLabel(getDisplayName(wallet, t), wallet.currency)}
            </option>
          ))}
        </Select>
      </TransactionFormField>

      <TransactionFormField>
        <LimitedDigitInput
          header={amountLabel}
          value={amount}
          onChange={setAmount}
          overLimit={amountOverLimit}
          onOverLimitChange={setAmountOverLimit}
        />
      </TransactionFormField>

      {isCrossCurrency ? (
        <TransactionFormField>
          <LimitedDigitInput
            header={t('addTransaction.rateLabel')}
            value={rate}
            onChange={setRate}
            overLimit={rateOverLimit}
            onOverLimitChange={setRateOverLimit}
          />
        </TransactionFormField>
      ) : null}

      {isCrossCurrency && destWallet ? (
        <TransactionReceiveRow
          label={t('addTransaction.walletWillReceive')}
          value={formatReceiveAmount(receiveAmount, destWallet.currency)}
        />
      ) : null}

      <TransactionFormField>
        <Textarea
          header={t('addTransaction.commentOptional')}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          rows={3}
        />
      </TransactionFormField>

      {submitError ? <TransactionSubmitError onRetry={() => void handleSubmit()} /> : null}
    </TransactionFormLayout>
  )
}
