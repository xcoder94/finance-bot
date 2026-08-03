import { useCallback, useEffect, useMemo, useState } from 'react'
import { Spinner } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import {
  deleteTransaction,
  fetchTransaction,
  fetchWallets,
  updateTransferTransaction,
  type TransactionResponse,
  type Wallet,
} from '../api/transactions'
import { DeleteConfirmSheet } from '../components/forms/DeleteConfirmSheet'
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
  cacheTransaction,
  getCachedTransaction,
  getCachedWallets,
  invalidateTransactionData,
} from '../store/dataCacheStore'
import { getDisplayName } from '../utils/getDisplayName'
import type { TFunction } from 'i18next'
import { computeTransferToAmount, parsePositiveInt } from '../utils/transactionForm'
import {
  buildEditSheetTitle,
  formatTransferResultLine,
  isoToMaskedDateInTashkent,
  isTransferCrossCurrency,
  maskedDateToTashkentIso,
  pickAlternateWalletId,
  resolveEditSheetLabel,
  shouldShowTransferRateField,
  walletCurrencySuffix,
} from '../utils/transactionFormFields'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; wallets: Wallet[]; transaction: TransactionResponse }

function buildTransferSubtitle(
  sourceWallet: Wallet | null,
  destWallet: Wallet | null,
  t: TFunction,
): string {
  const sourceName = sourceWallet ? getDisplayName(sourceWallet, t) : '—'
  const destName = destWallet ? getDisplayName(destWallet, t) : '—'
  return `${sourceName} → ${destName}`
}

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

  const [sourcePickerOpen, setSourcePickerOpen] = useState(false)
  const [destPickerOpen, setDestPickerOpen] = useState(false)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(false)
  const [submitError, setSubmitError] = useState(false)

  const closeSheet = useCallback(() => {
    if (typeof window.history.state?.idx === 'number' && window.history.state.idx > 0) {
      navigate(-1)
      return
    }
    navigate('/history', { replace: true })
  }, [navigate])

  useNativeBackButtonOverlay(
    !sourcePickerOpen && !destPickerOpen && !deleteConfirmOpen,
    closeSheet,
  )

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

      setTransactionDate(isoToMaskedDateInTashkent(transaction.transaction_date))
      setSourceWalletId(transaction.wallet_id)
      setDestWalletId(transaction.to_wallet_id ?? '')
      setAmount(String(transaction.amount))
      setRate(transaction.rate !== null ? String(Math.round(Number(transaction.rate))) : '')
      setComment(transaction.comment ?? '')
      setLoadState({ status: 'success', wallets, transaction })
    } catch {
      setLoadState({ status: 'error' })
    }
  }, [familyId, id, loadRetry])

  useEffect(() => {
    void loadData()
  }, [loadData, loadRetry])

  const sourceWallet =
    loadState.status === 'success'
      ? loadState.wallets.find((wallet) => wallet.id === sourceWalletId) ?? null
      : null

  const destWallet =
    loadState.status === 'success'
      ? loadState.wallets.find((wallet) => wallet.id === destWalletId) ?? null
      : null

  const isCrossCurrency = isTransferCrossCurrency(
    sourceWallet?.currency,
    destWallet?.currency,
  )

  const transferSubtitle = buildTransferSubtitle(sourceWallet, destWallet, t)

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
    if (nextSourceWalletId === destWalletId && loadState.status === 'success') {
      setDestWalletId(pickAlternateWalletId(loadState.wallets, nextSourceWalletId))
    }
  }

  const validateDate = () => {
    const valid = isFormSheetDateValid(transactionDate)
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

    const transactionDateIso = maskedDateToTashkentIso(transactionDate)
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
      invalidateTransactionData(familyId, id)
      closeSheet()
    } catch {
      setSubmitError(true)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!id || loadState.status !== 'success') {
      return
    }

    setDeleting(true)
    setDeleteError(false)
    try {
      await deleteTransaction(id)
      invalidateTransactionData(familyId, id)
      closeSheet()
    } catch {
      setDeleteError(true)
      setDeleteConfirmOpen(true)
    } finally {
      setDeleting(false)
    }
  }

  const sheetTitle =
    loadState.status === 'success'
      ? buildEditSheetTitle(resolveEditSheetLabel(comment, transferSubtitle))
      : t('editTransfer.title')

  const sheetIntro = isCrossCurrency
    ? t('formSheet.transferDiffIntro')
    : t('formSheet.transferSameIntro')

  const parsedAmount = parsePositiveInt(amount)
  const parsedRate = parsePositiveInt(rate)
  const canSubmit =
    loadState.status === 'success' &&
    loadState.wallets.length >= 2 &&
    parsedAmount !== null &&
    Boolean(sourceWalletId) &&
    Boolean(destWalletId) &&
    sourceWalletId !== destWalletId &&
    !amountOverLimit &&
    isFormSheetDateValid(transactionDate) &&
    comment.length <= 200 &&
    (!isCrossCurrency || (parsedRate !== null && !rateOverLimit))

  if (loadState.status === 'loading') {
    return (
      <FormSheet open title={t('editTransfer.title')} onClose={closeSheet} showPrimary={false}>
        <div className="form-sheet-loading" role="status" aria-live="polite">
          <Spinner size="m" aria-hidden="true" />
          <span className="visually-hidden">{t('home.loading')}</span>
        </div>
      </FormSheet>
    )
  }

  if (loadState.status === 'error') {
    return (
      <FormSheet open title={t('editTransfer.title')} onClose={closeSheet} showPrimary={false}>
        <div className="form-sheet-load-error" role="alert">
          <p>{t('addTransaction.loadError')}</p>
          <button type="button" onClick={() => setLoadRetry((count) => count + 1)}>
            {t('auth.retry')}
          </button>
        </div>
      </FormSheet>
    )
  }

  const { wallets, transaction } = loadState
  const destinationWallets = wallets.filter((wallet) => wallet.id !== sourceWalletId)
  const deleteCurrency = (sourceWallet?.currency ?? 'UZS') as 'UZS' | 'USD'
  const deleteAmount = parsePositiveInt(amount) ?? transaction.amount

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
        danger={
          <button
            type="button"
            className="form-sheet-danger-button"
            onClick={() => {
              setDeleteError(false)
              setDeleteConfirmOpen(true)
            }}
          >
            {t('formSheet.deleteRecord')}
          </button>
        }
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

      <DeleteConfirmSheet
        open={deleteConfirmOpen}
        onClose={() => {
          setDeleteConfirmOpen(false)
          setDeleteError(false)
        }}
        onConfirm={() => void handleDelete()}
        comment={comment}
        categoryLabel={transferSubtitle}
        amount={deleteAmount}
        currency={deleteCurrency}
        confirming={deleting}
        error={deleteError}
      />
    </>
  )
}
