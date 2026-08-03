import { useCallback, useEffect, useMemo, useState } from 'react'
import { Spinner } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { createTransferTransaction, fetchWallets, type Wallet } from '../api/transactions'
import { FormSheet } from '../components/forms/FormSheet'
import { FormSheetField } from '../components/forms/FormSheetField'
import {
  FormSheetAmountField,
  FormSheetCommentField,
  FormSheetDateField,
  FormSheetRateField,
  isFormSheetDateValid,
  WalletPickerSheet,
} from '../components/forms/transactionAddFields'
import { useNativeBackButtonOverlay } from '../components/nativeBackButtonContext'
import { TransactionSubmitError } from '../components/transaction-form/TransactionFormShared'
import { useAuthStore } from '../store/authStore'
import {
  getCachedWallets,
  invalidateHomeData,
  peekWallets,
} from '../store/dataCacheStore'
import { getDisplayName } from '../utils/getDisplayName'
import { computeTransferToAmount, parsePositiveInt } from '../utils/transactionForm'
import {
  formatTransferResultLine,
  isTransferCrossCurrency,
  maskedDateToTashkentIso,
  nowMaskedDateInTashkent,
  pickAlternateWalletId,
  resolveDefaultWalletId,
  shouldShowTransferRateField,
  walletCurrencySuffix,
} from '../utils/transactionFormFields'

type ReferenceState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; wallets: Wallet[] }

export function AddTransferPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const familyId = useAuthStore((state) => state.user?.familyBudgetId ?? '')
  const defaultWalletId = useAuthStore((state) => state.user?.defaultWalletId ?? null)

  const [referenceState, setReferenceState] = useState<ReferenceState>(() => {
    const wallets = peekWallets(familyId)
    return wallets ? { status: 'success', wallets } : { status: 'loading' }
  })
  const [referenceRetry, setReferenceRetry] = useState(0)

  const [transactionDate, setTransactionDate] = useState(nowMaskedDateInTashkent)
  const [dateError, setDateError] = useState(false)
  const [sourceWalletId, setSourceWalletId] = useState('')
  const [destWalletId, setDestWalletId] = useState('')
  const [amount, setAmount] = useState('')
  const [amountOverLimit, setAmountOverLimit] = useState(false)
  const [rate, setRate] = useState('')
  const [rateOverLimit, setRateOverLimit] = useState(false)
  const [comment, setComment] = useState('')

  const [sourcePickerOpen, setSourcePickerOpen] = useState(false)
  const [destPickerOpen, setDestPickerOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(false)

  const closeSheet = useCallback(() => {
    if (typeof window.history.state?.idx === 'number' && window.history.state.idx > 0) {
      navigate(-1)
      return
    }
    navigate('/', { replace: true })
  }, [navigate])

  useNativeBackButtonOverlay(!sourcePickerOpen && !destPickerOpen, closeSheet)

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
      const nextSourceId = resolveDefaultWalletId(wallets, defaultWalletId)
      setSourceWalletId(nextSourceId)
      setDestWalletId(pickAlternateWalletId(wallets, nextSourceId))
    }
  }, [referenceState, sourceWalletId, defaultWalletId])

  useEffect(() => {
    if (sourceWalletId && sourceWalletId === destWalletId && referenceState.status === 'success') {
      setDestWalletId(pickAlternateWalletId(referenceState.wallets, sourceWalletId))
    }
  }, [sourceWalletId, destWalletId, referenceState])

  const sourceWallet =
    referenceState.status === 'success'
      ? referenceState.wallets.find((wallet) => wallet.id === sourceWalletId) ?? null
      : null

  const destWallet =
    referenceState.status === 'success'
      ? referenceState.wallets.find((wallet) => wallet.id === destWalletId) ?? null
      : null

  const isCrossCurrency = isTransferCrossCurrency(
    sourceWallet?.currency,
    destWallet?.currency,
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

  const transferResultHint = useMemo(() => {
    const parsedAmount = parsePositiveInt(amount)
    if (
      !shouldShowTransferRateField(sourceWallet?.currency, destWallet?.currency) ||
      !sourceWallet ||
      !destWallet ||
      parsedAmount === null ||
      parsePositiveInt(rate) === null ||
      receiveAmount <= 0
    ) {
      return undefined
    }
    return formatTransferResultLine(
      parsedAmount,
      sourceWallet.currency,
      receiveAmount,
      destWallet.currency,
    )
  }, [amount, rate, receiveAmount, sourceWallet, destWallet])

  const handleSourceWalletChange = (nextSourceWalletId: string) => {
    setSourceWalletId(nextSourceWalletId)
    if (nextSourceWalletId === destWalletId && referenceState.status === 'success') {
      setDestWalletId(pickAlternateWalletId(referenceState.wallets, nextSourceWalletId))
    }
  }

  const validateDate = () => {
    const valid = isFormSheetDateValid(transactionDate)
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

    const transactionDateIso = maskedDateToTashkentIso(transactionDate)
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
      closeSheet()
    } catch {
      setSubmitError(true)
    } finally {
      setSubmitting(false)
    }
  }

  const sheetTitle = isCrossCurrency ? t('addTransfer.titleExchange') : t('addTransfer.titleSame')
  const sheetIntro = isCrossCurrency
    ? t('formSheet.transferDiffIntro')
    : t('formSheet.transferSameIntro')

  const parsedAmount = parsePositiveInt(amount)
  const parsedRate = parsePositiveInt(rate)
  const canSubmit =
    referenceState.status === 'success' &&
    referenceState.wallets.length >= 2 &&
    parsedAmount !== null &&
    Boolean(sourceWalletId) &&
    Boolean(destWalletId) &&
    sourceWalletId !== destWalletId &&
    !amountOverLimit &&
    isFormSheetDateValid(transactionDate) &&
    comment.length <= 200 &&
    (!isCrossCurrency || (parsedRate !== null && !rateOverLimit))

  if (referenceState.status === 'loading') {
    return (
      <FormSheet open title={t('addTransfer.titleSame')} onClose={closeSheet} showPrimary={false}>
        <div className="form-sheet-loading" role="status" aria-live="polite">
          <Spinner size="m" aria-hidden="true" />
          <span className="visually-hidden">{t('home.loading')}</span>
        </div>
      </FormSheet>
    )
  }

  if (referenceState.status === 'error') {
    return (
      <FormSheet open title={t('addTransfer.titleSame')} onClose={closeSheet} showPrimary={false}>
        <div className="form-sheet-load-error" role="alert">
          <p>{t('addTransaction.loadError')}</p>
          <button type="button" onClick={() => setReferenceRetry((count) => count + 1)}>
            {t('auth.retry')}
          </button>
        </div>
      </FormSheet>
    )
  }

  const { wallets } = referenceState
  const destinationWallets = wallets.filter((wallet) => wallet.id !== sourceWalletId)

  return (
    <>
      <FormSheet
        open
        title={sheetTitle}
        intro={sheetIntro}
        onClose={closeSheet}
        onPrimary={() => void handleSubmit()}
        primaryDisabled={!canSubmit}
        primaryLoading={submitting}
      >
        <FormSheetField
          label={t('addTransaction.sourceWallet')}
          right="›"
          onClick={() => setSourcePickerOpen(true)}
        >
          <span>{sourceWallet ? getDisplayName(sourceWallet, t) : '—'}</span>
        </FormSheetField>

        <FormSheetField
          label={t('addTransaction.destinationWallet')}
          right="›"
          onClick={() => setDestPickerOpen(true)}
        >
          <span>{destWallet ? getDisplayName(destWallet, t) : '—'}</span>
        </FormSheetField>

        <FormSheetAmountField
          value={amount}
          currencySuffix={walletCurrencySuffix(sourceWallet?.currency ?? 'UZS')}
          overLimit={amountOverLimit}
          onChange={setAmount}
          onOverLimitChange={setAmountOverLimit}
        />

        {isCrossCurrency ? (
          <FormSheetRateField
            value={rate}
            overLimit={rateOverLimit}
            resultHint={transferResultHint}
            onChange={setRate}
            onOverLimitChange={setRateOverLimit}
          />
        ) : null}

        <FormSheetDateField
          value={transactionDate}
          hasError={dateError}
          onChange={setTransactionDate}
          onBlur={validateDate}
          onEdit={() => setDateError(false)}
        />

        <FormSheetCommentField value={comment} onChange={setComment} />

        {submitError ? <TransactionSubmitError onRetry={() => void handleSubmit()} /> : null}
      </FormSheet>

      <WalletPickerSheet
        open={sourcePickerOpen}
        title={t('addTransaction.sourceWallet')}
        wallets={wallets}
        selectedWalletId={sourceWalletId}
        onClose={() => setSourcePickerOpen(false)}
        onSelect={handleSourceWalletChange}
      />

      <WalletPickerSheet
        open={destPickerOpen}
        title={t('addTransaction.destinationWallet')}
        wallets={destinationWallets}
        selectedWalletId={destWalletId}
        onClose={() => setDestPickerOpen(false)}
        onSelect={setDestWalletId}
      />
    </>
  )
}
