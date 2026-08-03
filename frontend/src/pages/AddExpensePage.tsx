import { useCallback, useEffect, useMemo, useState } from 'react'
import { Spinner } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import {
  createExpenseTransaction,
  fetchExpenseCategories,
  fetchWallets,
  type ExpenseCategory,
  type Wallet,
} from '../api/transactions'
import { CategoryPickerSheet } from '../components/forms/CategoryPickerSheet'
import { FormSheet } from '../components/forms/FormSheet'
import { FormSheetField } from '../components/forms/FormSheetField'
import {
  FormSheetAmountField,
  FormSheetCommentField,
  FormSheetDateField,
  isFormSheetDateValid,
  WalletPickerSheet,
} from '../components/forms/transactionAddFields'
import { useNativeBackButtonOverlay } from '../components/nativeBackButtonContext'
import { TransactionSubmitError } from '../components/transaction-form/TransactionFormShared'
import { useAuthStore } from '../store/authStore'
import {
  getCachedExpenseCategories,
  getCachedWallets,
  invalidateHomeData,
  peekExpenseCategories,
  peekWallets,
} from '../store/dataCacheStore'
import { getDisplayName } from '../utils/getDisplayName'
import { parsePositiveInt } from '../utils/transactionForm'
import {
  filterUncategorizedCategories,
  maskedDateToTashkentIso,
  nowMaskedDateInTashkent,
  resolveDefaultWalletId,
  walletCurrencySuffix,
} from '../utils/transactionFormFields'

type ReferenceState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; wallets: Wallet[]; categories: ExpenseCategory[] }

function getTopLevelCategories(categories: ExpenseCategory[]): ExpenseCategory[] {
  return filterUncategorizedCategories(categories.filter((category) => category.parent_id === null))
}

export function AddExpensePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const familyId = useAuthStore((state) => state.user?.familyBudgetId ?? '')
  const defaultWalletId = useAuthStore((state) => state.user?.defaultWalletId ?? null)

  const [referenceState, setReferenceState] = useState<ReferenceState>(() => {
    const wallets = peekWallets(familyId)
    const categories = peekExpenseCategories(familyId)
    return wallets && categories
      ? { status: 'success', wallets, categories }
      : { status: 'loading' }
  })
  const [referenceRetry, setReferenceRetry] = useState(0)

  const [transactionDate, setTransactionDate] = useState(nowMaskedDateInTashkent)
  const [dateError, setDateError] = useState(false)
  const [amount, setAmount] = useState('')
  const [amountOverLimit, setAmountOverLimit] = useState(false)
  const [walletId, setWalletId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [categoryLabel, setCategoryLabel] = useState('')
  const [comment, setComment] = useState('')

  const [categoryPickerOpen, setCategoryPickerOpen] = useState(false)
  const [walletPickerOpen, setWalletPickerOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(false)

  const closeSheet = useCallback(() => {
    if (typeof window.history.state?.idx === 'number' && window.history.state.idx > 0) {
      navigate(-1)
      return
    }
    navigate('/', { replace: true })
  }, [navigate])

  useNativeBackButtonOverlay(!categoryPickerOpen && !walletPickerOpen, closeSheet)

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

  useEffect(() => {
    if (referenceState.status !== 'success') {
      return
    }

    if (!walletId && referenceState.wallets.length > 0) {
      setWalletId(resolveDefaultWalletId(referenceState.wallets, defaultWalletId))
    }

    if (!categoryId && topLevelCategories.length > 0) {
      const firstParent = topLevelCategories[0]
      setCategoryId(firstParent.id)
      setCategoryLabel(getDisplayName(firstParent, t))
    }
  }, [referenceState, walletId, categoryId, topLevelCategories, defaultWalletId, t])

  const selectedWallet =
    referenceState.status === 'success'
      ? referenceState.wallets.find((wallet) => wallet.id === walletId) ?? null
      : null

  const showDefaultWalletHint =
    Boolean(defaultWalletId) &&
    selectedWallet?.id === defaultWalletId &&
    referenceState.status === 'success'

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
    if (!parsedAmount || !walletId || !categoryId || amountOverLimit) {
      return
    }

    const transactionDateIso = maskedDateToTashkentIso(transactionDate)
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
        expense_category_id: categoryId,
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

  const canSubmit =
    referenceState.status === 'success' &&
    referenceState.wallets.length > 0 &&
    topLevelCategories.length > 0 &&
    parsePositiveInt(amount) !== null &&
    Boolean(walletId) &&
    Boolean(categoryId) &&
    !amountOverLimit &&
    isFormSheetDateValid(transactionDate) &&
    comment.length <= 200

  if (referenceState.status === 'loading') {
    return (
      <FormSheet open title={t('addExpense.title')} onClose={closeSheet} showPrimary={false}>
        <div className="form-sheet-loading" role="status" aria-live="polite">
          <Spinner size="m" aria-hidden="true" />
          <span className="visually-hidden">{t('home.loading')}</span>
        </div>
      </FormSheet>
    )
  }

  if (referenceState.status === 'error') {
    return (
      <FormSheet open title={t('addExpense.title')} onClose={closeSheet} showPrimary={false}>
        <div className="form-sheet-load-error" role="alert">
          <p>{t('addTransaction.loadError')}</p>
          <button type="button" onClick={() => setReferenceRetry((count) => count + 1)}>
            {t('auth.retry')}
          </button>
        </div>
      </FormSheet>
    )
  }

  const { wallets, categories } = referenceState

  return (
    <>
      <FormSheet
        open
        title={t('addExpense.title')}
        onClose={closeSheet}
        onPrimary={() => void handleSubmit()}
        primaryDisabled={!canSubmit}
        primaryLoading={submitting}
      >
        <FormSheetAmountField
          value={amount}
          currencySuffix={walletCurrencySuffix(selectedWallet?.currency ?? 'UZS')}
          overLimit={amountOverLimit}
          hint={t('formSheet.amountCurrencyHint')}
          onChange={setAmount}
          onOverLimitChange={setAmountOverLimit}
        />

        <FormSheetField
          label={t('addTransaction.category')}
          right="›"
          onClick={() => setCategoryPickerOpen(true)}
        >
          <span>{categoryLabel || '—'}</span>
        </FormSheetField>

        <FormSheetField
          label={t('addTransaction.wallet')}
          right="›"
          hint={showDefaultWalletHint ? t('formSheet.defaultWalletHint') : undefined}
          onClick={() => setWalletPickerOpen(true)}
        >
          <span>{selectedWallet ? getDisplayName(selectedWallet, t) : '—'}</span>
        </FormSheetField>

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

      <CategoryPickerSheet
        variant="expense"
        open={categoryPickerOpen}
        categories={categories}
        selectedCategoryId={categoryId}
        onClose={() => setCategoryPickerOpen(false)}
        onSelect={(selection) => {
          setCategoryId(selection.categoryId)
          setCategoryLabel(selection.label)
        }}
      />

      <WalletPickerSheet
        open={walletPickerOpen}
        wallets={wallets}
        selectedWalletId={walletId}
        onClose={() => setWalletPickerOpen(false)}
        onSelect={setWalletId}
      />
    </>
  )
}
