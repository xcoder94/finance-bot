import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button, Select, Text, Textarea } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import {
  createExpenseCategory,
  createExpenseTransaction,
  fetchExpenseCategories,
  fetchWallets,
  type ExpenseCategory,
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
  cacheExpenseCategory,
  getCachedExpenseCategories,
  getCachedWallets,
  invalidateHomeData,
  peekExpenseCategories,
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

const GENERAL_SUBCATEGORY_NAME = 'Общее'

type ReferenceState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; wallets: Wallet[]; categories: ExpenseCategory[] }

function getTopLevelCategories(categories: ExpenseCategory[]): ExpenseCategory[] {
  return categories.filter((category) => category.parent_id === null)
}

function getSubcategories(
  categories: ExpenseCategory[],
  parentId: string,
): ExpenseCategory[] {
  return categories.filter((category) => category.parent_id === parentId)
}

export function AddExpensePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const familyId = useAuthStore((state) => state.user?.familyBudgetId ?? '')

  const [referenceState, setReferenceState] = useState<ReferenceState>(() => {
    const wallets = peekWallets(familyId)
    const categories = peekExpenseCategories(familyId)
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
  const [parentCategoryId, setParentCategoryId] = useState('')
  const [subcategoryId, setSubcategoryId] = useState('')
  const [comment, setComment] = useState('')

  const [subcategoryLoading, setSubcategoryLoading] = useState(false)
  const [subcategoryError, setSubcategoryError] = useState(false)
  const [hiddenFallbackParentIds, setHiddenFallbackParentIds] = useState<Set<string>>(
    () => new Set(),
  )
  const subcategoryRequestId = useRef(0)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)

  const loadReferenceData = useCallback(async () => {
    setReferenceState({ status: 'loading' })
    try {
      const [wallets, categories] = await Promise.all([
        getCachedWallets(familyId, fetchWallets, referenceRetry > 0),
        getCachedExpenseCategories(familyId, fetchExpenseCategories, referenceRetry > 0),
      ])
      setReferenceState({ status: 'success', wallets, categories })
    } catch {
      setReferenceState({ status: 'error' })
    }
  }, [familyId, referenceRetry])

  useEffect(() => {
    void loadReferenceData()
  }, [loadReferenceData, referenceRetry])

  const topLevelCategories = useMemo(() => {
    if (referenceState.status !== 'success') {
      return []
    }
    return getTopLevelCategories(referenceState.categories)
  }, [referenceState])

  const subcategories = useMemo(() => {
    if (referenceState.status !== 'success' || !parentCategoryId) {
      return []
    }
    return getSubcategories(referenceState.categories, parentCategoryId)
  }, [referenceState, parentCategoryId])

  const ensureSubcategoryForParent = useCallback(
    async (parentId: string, categories: ExpenseCategory[]) => {
      const requestId = subcategoryRequestId.current + 1
      subcategoryRequestId.current = requestId
      setSubcategoryError(false)
      setSubcategoryLoading(false)

      const existing = getSubcategories(categories, parentId)
      if (existing.length > 0) {
        setSubcategoryId(existing[0].id)
        return
      }

      setHiddenFallbackParentIds((current) => new Set(current).add(parentId))
      setSubcategoryLoading(true)
      try {
        const created = await createExpenseCategory({
          name: GENERAL_SUBCATEGORY_NAME,
          parent_id: parentId,
        })
        if (subcategoryRequestId.current !== requestId) {
          return
        }
        cacheExpenseCategory(familyId, created)
        setReferenceState((current) => {
          if (current.status !== 'success') {
            return current
          }
          return {
            ...current,
            categories: [...current.categories, created],
          }
        })
        setSubcategoryId(created.id)
      } catch {
        if (subcategoryRequestId.current !== requestId) {
          return
        }
        setSubcategoryId('')
        setSubcategoryError(true)
      } finally {
        if (subcategoryRequestId.current === requestId) {
          setSubcategoryLoading(false)
        }
      }
    },
    [familyId],
  )

  useEffect(() => {
    if (referenceState.status !== 'success') {
      return
    }
    if (!walletId && referenceState.wallets.length > 0) {
      setWalletId(referenceState.wallets[0].id)
    }
    if (!parentCategoryId && topLevelCategories.length > 0) {
      const firstParentId = topLevelCategories[0].id
      setParentCategoryId(firstParentId)
      void ensureSubcategoryForParent(firstParentId, referenceState.categories)
    }
  }, [referenceState, walletId, parentCategoryId, topLevelCategories, ensureSubcategoryForParent])

  const handleParentCategoryChange = (nextParentId: string) => {
    setParentCategoryId(nextParentId)
    setSubcategoryId('')
    setSubcategoryError(false)
    if (referenceState.status === 'success') {
      void ensureSubcategoryForParent(nextParentId, referenceState.categories)
    }
  }

  const resetForm = useCallback(() => {
    setTransactionDate(nowMaskedDatetimeValue())
    setDateError(false)
    setAmount('')
    setAmountOverLimit(false)
    setComment('')
    setSubmitError(false)
    setSubcategoryError(false)
    setSubcategoryId('')
    if (referenceState.status === 'success') {
      if (referenceState.wallets.length > 0) {
        setWalletId(referenceState.wallets[0].id)
      }
      if (topLevelCategories.length > 0) {
        const firstParentId = topLevelCategories[0].id
        setParentCategoryId(firstParentId)
        void ensureSubcategoryForParent(firstParentId, referenceState.categories)
      }
    }
  }, [referenceState, topLevelCategories, ensureSubcategoryForParent])

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
      await createExpenseTransaction({
        transaction_date: transactionDateIso,
        amount: parsedAmount,
        wallet_id: walletId,
        expense_category_id: subcategoryId,
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
  const hideSubcategorySelect =
    !parentCategoryId ||
    subcategories.length === 0 ||
    hiddenFallbackParentIds.has(parentCategoryId)
  const canSubmit =
    wallets.length > 0 &&
    topLevelCategories.length > 0 &&
    parsePositiveInt(amount) !== null &&
    Boolean(walletId) &&
    Boolean(subcategoryId) &&
    !subcategoryLoading &&
    !amountOverLimit &&
    isValidMaskedDatetime(transactionDate)

  return (
    <>
      <TransactionFormLayout
        titleKey="addExpense.title"
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

        {!hideSubcategorySelect ? (
          <TransactionFormField>
            <Select
              header={t('addTransaction.subcategory')}
              value={subcategoryId}
              onChange={(event) => setSubcategoryId(event.target.value)}
              disabled={subcategories.length === 0 || subcategoryLoading}
            >
              {subcategories.map((category) => (
                <option key={category.id} value={category.id}>
                  {getDisplayName(category, t)}
                </option>
              ))}
            </Select>
          </TransactionFormField>
        ) : null}

        {subcategoryError ? (
          <div className="transaction-form__submit-error" role="alert">
            <Text>{t('addExpense.subcategoryCreateError')}</Text>
            <Button
              mode="plain"
              size="s"
              onClick={() =>
                void ensureSubcategoryForParent(parentCategoryId, referenceState.categories)
              }
            >
              {t('auth.retry')}
            </Button>
          </div>
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
