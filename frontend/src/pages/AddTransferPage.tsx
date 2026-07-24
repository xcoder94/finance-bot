import { useCallback, useEffect, useMemo, useState } from 'react'
import { Select, Textarea } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import {
  createTransferTransaction,
  fetchWallets,
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
  TransactionSuccessModal,
} from '../components/transaction-form/TransactionFormShared'
import { useAuthStore } from '../store/authStore'
import {
  getCachedWallets,
  invalidateHomeData,
  peekWallets,
} from '../store/dataCacheStore'
import {
  computeTransferToAmount,
  formatReceiveAmount,
  formatWalletLabel,
  isValidMaskedDatetime,
  maskedDatetimeToIso,
  nowMaskedDatetimeValue,
  parsePositiveInt,
} from '../utils/transactionForm'
import { getDisplayName } from '../utils/getDisplayName'

type ReferenceState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; wallets: Wallet[] }

function pickDefaultDestWalletId(wallets: Wallet[], sourceWalletId: string): string {
  const alternative = wallets.find((wallet) => wallet.id !== sourceWalletId)
  return alternative?.id ?? ''
}

export function AddTransferPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const familyId = useAuthStore((state) => state.user?.familyBudgetId ?? '')

  const [referenceState, setReferenceState] = useState<ReferenceState>(() => {
    const wallets = peekWallets(familyId)
    return wallets ? { status: 'success', wallets } : { status: 'loading' }
  })
  const [referenceRetry, setReferenceRetry] = useState(0)

  const [transactionDate, setTransactionDate] = useState(nowMaskedDatetimeValue)
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
  const [showSuccess, setShowSuccess] = useState(false)

  const loadReferenceData = useCallback(async () => {
    setReferenceState({ status: 'loading' })
    try {
      const wallets = await getCachedWallets(familyId, fetchWallets, referenceRetry > 0)
      setReferenceState({ status: 'success', wallets })
    } catch {
      setReferenceState({ status: 'error' })
    }
  }, [familyId, referenceRetry])

  useEffect(() => {
    void loadReferenceData()
  }, [loadReferenceData, referenceRetry])

  useEffect(() => {
    if (referenceState.status !== 'success') {
      return
    }
    const { wallets } = referenceState
    if (!sourceWalletId && wallets.length > 0) {
      setSourceWalletId(wallets[0].id)
      setDestWalletId(pickDefaultDestWalletId(wallets, wallets[0].id))
    }
  }, [referenceState, sourceWalletId])

  useEffect(() => {
    if (sourceWalletId && sourceWalletId === destWalletId && referenceState.status === 'success') {
      setDestWalletId(pickDefaultDestWalletId(referenceState.wallets, sourceWalletId))
    }
  }, [sourceWalletId, destWalletId, referenceState])

  const sourceWallet = useMemo(() => {
    if (referenceState.status !== 'success') {
      return null
    }
    return referenceState.wallets.find((wallet) => wallet.id === sourceWalletId) ?? null
  }, [referenceState, sourceWalletId])

  const destWallet = useMemo(() => {
    if (referenceState.status !== 'success') {
      return null
    }
    return referenceState.wallets.find((wallet) => wallet.id === destWalletId) ?? null
  }, [referenceState, destWalletId])

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
    if (nextSourceWalletId === destWalletId && referenceState.status === 'success') {
      setDestWalletId(pickDefaultDestWalletId(referenceState.wallets, nextSourceWalletId))
    }
  }

  const resetForm = useCallback(() => {
    setTransactionDate(nowMaskedDatetimeValue())
    setDateError(false)
    setAmount('')
    setAmountOverLimit(false)
    setRate('')
    setRateOverLimit(false)
    setComment('')
    setSubmitError(false)
    if (referenceState.status === 'success') {
      const { wallets } = referenceState
      if (wallets.length > 0) {
        setSourceWalletId(wallets[0].id)
        setDestWalletId(pickDefaultDestWalletId(wallets, wallets[0].id))
      }
    }
  }, [referenceState])

  const validateDate = () => {
    const valid = isValidMaskedDatetime(transactionDate)
    setDateError(!valid)
    return valid
  }

  const handleSubmit = async () => {
    if (!validateDate()) {
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
      await createTransferTransaction({
        transaction_date: transactionDateIso,
        wallet_id: sourceWalletId,
        to_wallet_id: destWalletId,
        amount: parsedAmount,
        ...(parsedRate !== undefined ? { rate: parsedRate } : {}),
        comment: comment.trim() || null,
      })
      invalidateHomeData(familyId)
      resetForm()
      setShowSuccess(true)
    } catch {
      setSubmitError(true)
    } finally {
      setSubmitting(false)
    }
  }

  if (referenceState.status === 'loading') {
    return <TransactionFormLoading />
  }

  if (referenceState.status === 'error') {
    return (
      <TransactionFormLoadError onRetry={() => setReferenceRetry((count) => count + 1)} />
    )
  }

  const { wallets } = referenceState
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
    <>
      <TransactionFormLayout
        titleKey="addTransfer.title"
        onCancel={() => navigate('/')}
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

      <TransactionSuccessModal
        open={showSuccess}
        onGoHome={() => navigate('/')}
        onAddAnother={() => {
          setShowSuccess(false)
        }}
      />
    </>
  )
}
