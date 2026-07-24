import { useCallback, useEffect, useState } from 'react'
import { Select, Textarea } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import {
  createIncomeTransaction,
  fetchIncomeCategories,
  fetchWallets,
  type IncomeCategory,
  type Wallet,
} from '../api/transactions'
import {
  LimitedDigitInput,
  MaskedDateTimeInput,
  TransactionFormField,
  TransactionFormLayout,
  TransactionFormLoadError,
  TransactionFormLoading,
  TransactionSubmitError,
  TransactionSuccessModal,
} from '../components/transaction-form/TransactionFormShared'
import { useAuthStore } from '../store/authStore'
import {
  getCachedIncomeCategories,
  getCachedWallets,
  invalidateHomeData,
  peekIncomeCategories,
  peekWallets,
} from '../store/dataCacheStore'
import {
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
  | { status: 'success'; wallets: Wallet[]; categories: IncomeCategory[] }

export function AddIncomePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const familyId = useAuthStore((state) => state.user?.familyBudgetId ?? '')

  const [referenceState, setReferenceState] = useState<ReferenceState>(() => {
    const wallets = peekWallets(familyId)
    const categories = peekIncomeCategories(familyId)
    return wallets && categories
      ? { status: 'success', wallets, categories }
      : { status: 'loading' }
  })
  const [referenceRetry, setReferenceRetry] = useState(0)

  const [transactionDate, setTransactionDate] = useState(nowMaskedDatetimeValue)
  const [dateError, setDateError] = useState(false)
  const [amount, setAmount] = useState('')
  const [amountOverLimit, setAmountOverLimit] = useState(false)
  const [walletId, setWalletId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [comment, setComment] = useState('')

  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)

  const loadReferenceData = useCallback(async () => {
    setReferenceState({ status: 'loading' })
    try {
      const [wallets, categories] = await Promise.all([
        getCachedWallets(familyId, fetchWallets, referenceRetry > 0),
        getCachedIncomeCategories(familyId, fetchIncomeCategories, referenceRetry > 0),
      ])
      setReferenceState({ status: 'success', wallets, categories })
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
    if (!walletId && referenceState.wallets.length > 0) {
      setWalletId(referenceState.wallets[0].id)
    }
    if (!categoryId && referenceState.categories.length > 0) {
      setCategoryId(referenceState.categories[0].id)
    }
  }, [referenceState, walletId, categoryId])

  const resetForm = useCallback(() => {
    setTransactionDate(nowMaskedDatetimeValue())
    setDateError(false)
    setAmount('')
    setAmountOverLimit(false)
    setComment('')
    setSubmitError(false)
    if (referenceState.status === 'success') {
      if (referenceState.wallets.length > 0) {
        setWalletId(referenceState.wallets[0].id)
      }
      if (referenceState.categories.length > 0) {
        setCategoryId(referenceState.categories[0].id)
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
    if (!parsedAmount || !walletId || !categoryId || amountOverLimit) {
      return
    }

    const transactionDateIso = maskedDatetimeToIso(transactionDate)
    if (!transactionDateIso) {
      setDateError(true)
      return
    }

    setSubmitting(true)
    setSubmitError(false)

    try {
      await createIncomeTransaction({
        transaction_date: transactionDateIso,
        amount: parsedAmount,
        wallet_id: walletId,
        income_category_id: categoryId,
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

  const { wallets, categories } = referenceState
  const canSubmit =
    wallets.length > 0 &&
    categories.length > 0 &&
    parsePositiveInt(amount) !== null &&
    Boolean(walletId) &&
    Boolean(categoryId) &&
    !amountOverLimit &&
    isValidMaskedDatetime(transactionDate)

  return (
    <>
      <TransactionFormLayout
        titleKey="addIncome.title"
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
          <LimitedDigitInput
            header={t('addTransaction.amount')}
            value={amount}
            onChange={setAmount}
            overLimit={amountOverLimit}
            onOverLimitChange={setAmountOverLimit}
          />
        </TransactionFormField>

        <TransactionFormField>
          <Select
            header={t('addTransaction.wallet')}
            value={walletId}
            onChange={(event) => setWalletId(event.target.value)}
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
            header={t('addTransaction.category')}
            value={categoryId}
            onChange={(event) => setCategoryId(event.target.value)}
            disabled={categories.length === 0}
          >
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {getDisplayName(category, t)}
              </option>
            ))}
          </Select>
        </TransactionFormField>

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
