import { useCallback, useEffect, useMemo, useState } from 'react'
import { Select, Textarea } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import {
  fetchExpenseCategories,
  fetchTransaction,
  fetchWallets,
  updateExpenseTransaction,
  type ExpenseCategory,
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
  getCachedExpenseCategories,
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

function getTopLevelCategories(categories: ExpenseCategory[]): ExpenseCategory[] {
  return categories.filter((category) => category.parent_id === null)
}

function getSubcategories(
  categories: ExpenseCategory[],
  parentId: string,
): ExpenseCategory[] {
  return categories.filter((category) => category.parent_id === parentId)
}

function resolveExpenseCategorySelection(
  categories: ExpenseCategory[],
  expenseCategoryId: string,
): { parentCategoryId: string; subcategoryId: string } {
  const category = categories.find((item) => item.id === expenseCategoryId)
  if (!category) {
    return { parentCategoryId: '', subcategoryId: '' }
  }
  if (category.parent_id === null) {
    return { parentCategoryId: category.id, subcategoryId: category.id }
  }
  return { parentCategoryId: category.parent_id, subcategoryId: category.id }
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; wallets: Wallet[]; categories: ExpenseCategory[]; transaction: TransactionResponse }

export function EditExpensePage() {
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
  const [parentCategoryId, setParentCategoryId] = useState('')
  const [subcategoryId, setSubcategoryId] = useState('')
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
        getCachedExpenseCategories(familyId, fetchExpenseCategories, loadRetry > 0),
        getCachedTransaction(familyId, id, () => fetchTransaction(id), loadRetry > 0),
      ])

      if (transaction.type !== 'expense') {
        setLoadState({ status: 'error' })
        return
      }

      const selection = resolveExpenseCategorySelection(
        categories,
        transaction.expense_category_id ?? '',
      )

      setTransactionDate(isoDatetimeToMaskedDatetime(transaction.transaction_date))
      setAmount(String(transaction.amount))
      setWalletId(transaction.wallet_id)
      setParentCategoryId(selection.parentCategoryId)
      setSubcategoryId(selection.subcategoryId)
      setComment(transaction.comment ?? '')
      setLoadState({ status: 'success', wallets, categories, transaction })
    } catch {
      setLoadState({ status: 'error' })
    }
  }, [familyId, id, loadRetry])

  useEffect(() => {
    void loadData()
  }, [loadData, loadRetry])

  const topLevelCategories = useMemo(() => {
    if (loadState.status !== 'success') {
      return []
    }
    return getTopLevelCategories(loadState.categories)
  }, [loadState])

  const subcategories = useMemo(() => {
    if (loadState.status !== 'success' || !parentCategoryId) {
      return []
    }
    return getSubcategories(loadState.categories, parentCategoryId)
  }, [loadState, parentCategoryId])

  const handleParentCategoryChange = (nextParentId: string) => {
    setParentCategoryId(nextParentId)
    const nextSubcategories =
      loadState.status === 'success'
        ? getSubcategories(loadState.categories, nextParentId)
        : []
    setSubcategoryId(nextSubcategories[0]?.id ?? '')
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
    if (!parsedAmount || !walletId || !subcategoryId || amountOverLimit) {
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
      const updated = await updateExpenseTransaction(id, {
        transaction_date: transactionDateIso,
        amount: parsedAmount,
        wallet_id: walletId,
        expense_category_id: subcategoryId,
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
  const canSubmit =
    wallets.length > 0 &&
    topLevelCategories.length > 0 &&
    parsePositiveInt(amount) !== null &&
    Boolean(walletId) &&
    Boolean(subcategoryId) &&
    !amountOverLimit &&
    isValidMaskedDatetime(transactionDate)

  return (
    <TransactionFormLayout
      titleKey="editExpense.title"
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
          value={parentCategoryId}
          onChange={(event) => handleParentCategoryChange(event.target.value)}
          disabled={topLevelCategories.length === 0}
        >
          {topLevelCategories.map((category) => (
            <option key={category.id} value={category.id}>
              {getDisplayName(category, t)}
            </option>
          ))}
        </Select>
      </TransactionFormField>

      <TransactionFormField>
        <Select
          header={t('addTransaction.subcategory')}
          value={subcategoryId}
          onChange={(event) => setSubcategoryId(event.target.value)}
          disabled={subcategories.length === 0}
        >
          {subcategories.map((category) => (
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
