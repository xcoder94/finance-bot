import { useCallback, useEffect, useState } from 'react'
import { Select, Textarea } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import {
  fetchIncomeCategories,
  fetchTransaction,
  fetchWallets,
  updateIncomeTransaction,
  type IncomeCategory,
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
  TransactionSubmitError,
} from '../components/transaction-form/TransactionFormShared'
import { useAuthStore } from '../store/authStore'
import {
  cacheTransaction,
  getCachedIncomeCategories,
  getCachedTransaction,
  getCachedWallets,
  invalidateHomeData,
} from '../store/dataCacheStore'
import {
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
  | { status: 'success'; wallets: Wallet[]; categories: IncomeCategory[]; transaction: TransactionResponse }

export function EditIncomePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const familyId = useAuthStore((state) => state.user?.familyBudgetId ?? '')

  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [loadRetry, setLoadRetry] = useState(0)

  const [transactionDate, setTransactionDate] = useState('')
  const [dateError, setDateError] = useState(false)
  const [amount, setAmount] = useState('')
  const [amountOverLimit, setAmountOverLimit] = useState(false)
  const [walletId, setWalletId] = useState('')
  const [categoryId, setCategoryId] = useState('')
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
      const [wallets, categories, transaction] = await Promise.all([
        getCachedWallets(familyId, fetchWallets, loadRetry > 0),
        getCachedIncomeCategories(familyId, fetchIncomeCategories, loadRetry > 0),
        getCachedTransaction(familyId, id, () => fetchTransaction(id), loadRetry > 0),
      ])

      if (transaction.type !== 'income') {
        setLoadState({ status: 'error' })
        return
      }

      setTransactionDate(isoDatetimeToMaskedDatetime(transaction.transaction_date))
      setAmount(String(transaction.amount))
      setWalletId(transaction.wallet_id)
      setCategoryId(transaction.income_category_id ?? '')
      setComment(transaction.comment ?? '')
      setLoadState({ status: 'success', wallets, categories, transaction })
    } catch {
      setLoadState({ status: 'error' })
    }
  }, [familyId, id, loadRetry])

  useEffect(() => {
    void loadData()
  }, [loadData, loadRetry])

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
      const updated = await updateIncomeTransaction(id, {
        transaction_date: transactionDateIso,
        amount: parsedAmount,
        wallet_id: walletId,
        income_category_id: categoryId,
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

  const { wallets, categories } = loadState
  const canSubmit =
    wallets.length > 0 &&
    categories.length > 0 &&
    parsePositiveInt(amount) !== null &&
    Boolean(walletId) &&
    Boolean(categoryId) &&
    !amountOverLimit &&
    isValidMaskedDatetime(transactionDate)

  return (
    <TransactionFormLayout
      titleKey="editIncome.title"
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
  )
}
