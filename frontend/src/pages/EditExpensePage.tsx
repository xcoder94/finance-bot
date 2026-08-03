import { useCallback, useEffect, useMemo, useState } from 'react'
import { Spinner } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import {
  deleteTransaction,
  fetchExpenseCategories,
  fetchTransaction,
  fetchWallets,
  updateExpenseTransaction,
  type ExpenseCategory,
  type TransactionResponse,
  type Wallet,
} from '../api/transactions'
import { DeleteConfirmSheet } from '../components/forms/DeleteConfirmSheet'
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
  cacheTransaction,
  getCachedExpenseCategories,
  getCachedTransaction,
  getCachedWallets,
  invalidateTransactionData,
} from '../store/dataCacheStore'
import { getDisplayName } from '../utils/getDisplayName'
import type { TFunction } from 'i18next'
import { parsePositiveInt } from '../utils/transactionForm'
import {
  buildEditSheetTitle,
  buildExpenseCategoryDisplayLabel,
  filterUncategorizedCategories,
  isoToMaskedDateInTashkent,
  maskedDateToTashkentIso,
  resolveEditSheetLabel,
  walletCurrencySuffix,
} from '../utils/transactionFormFields'

function resolveExpenseCategorySelectionWithT(
  categories: ExpenseCategory[],
  expenseCategoryId: string,
  t: TFunction,
): { categoryId: string; label: string } {
  const category = categories.find((item) => item.id === expenseCategoryId)
  if (!category) {
    return { categoryId: '', label: '' }
  }
  if (category.parent_id === null) {
    return {
      categoryId: category.id,
      label: getDisplayName(category, t),
    }
  }
  const parent = categories.find((item) => item.id === category.parent_id)
  const parentName = parent ? getDisplayName(parent, t) : '—'
  return {
    categoryId: category.id,
    label: buildExpenseCategoryDisplayLabel(parentName, getDisplayName(category, t)),
  }
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
  const [categoryId, setCategoryId] = useState('')
  const [categoryLabel, setCategoryLabel] = useState('')
  const [comment, setComment] = useState('')

  const [categoryPickerOpen, setCategoryPickerOpen] = useState(false)
  const [walletPickerOpen, setWalletPickerOpen] = useState(false)
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
    !categoryPickerOpen && !walletPickerOpen && !deleteConfirmOpen,
    closeSheet,
  )

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

      const selection = resolveExpenseCategorySelectionWithT(
        categories,
        transaction.expense_category_id ?? '',
        t,
      )

      setTransactionDate(isoToMaskedDateInTashkent(transaction.transaction_date))
      setAmount(String(transaction.amount))
      setWalletId(transaction.wallet_id)
      setCategoryId(selection.categoryId)
      setCategoryLabel(selection.label)
      setComment(transaction.comment ?? '')
      setLoadState({ status: 'success', wallets, categories, transaction })
    } catch {
      setLoadState({ status: 'error' })
    }
  }, [familyId, id, loadRetry, t])

  useEffect(() => {
    void loadData()
  }, [loadData, loadRetry])

  const topLevelCategories = useMemo(() => {
    if (loadState.status !== 'success') {
      return []
    }
    return filterUncategorizedCategories(
      loadState.categories.filter((category) => category.parent_id === null),
    )
  }, [loadState])

  const selectedWallet =
    loadState.status === 'success'
      ? loadState.wallets.find((wallet) => wallet.id === walletId) ?? null
      : null

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
      const updated = await updateExpenseTransaction(id, {
        transaction_date: transactionDateIso,
        amount: parsedAmount,
        wallet_id: walletId,
        expense_category_id: categoryId,
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
      ? buildEditSheetTitle(resolveEditSheetLabel(comment, categoryLabel))
      : t('editExpense.title')

  const canSubmit =
    loadState.status === 'success' &&
    loadState.wallets.length > 0 &&
    topLevelCategories.length > 0 &&
    parsePositiveInt(amount) !== null &&
    Boolean(walletId) &&
    Boolean(categoryId) &&
    !amountOverLimit &&
    isFormSheetDateValid(transactionDate) &&
    comment.length <= 200

  if (loadState.status === 'loading') {
    return (
      <FormSheet open title={t('editExpense.title')} onClose={closeSheet} showPrimary={false}>
        <div className="form-sheet-loading" role="status" aria-live="polite">
          <Spinner size="m" aria-hidden="true" />
          <span className="visually-hidden">{t('home.loading')}</span>
        </div>
      </FormSheet>
    )
  }

  if (loadState.status === 'error') {
    return (
      <FormSheet open title={t('editExpense.title')} onClose={closeSheet} showPrimary={false}>
        <div className="form-sheet-load-error" role="alert">
          <p>{t('addTransaction.loadError')}</p>
          <button type="button" onClick={() => setLoadRetry((count) => count + 1)}>
            {t('auth.retry')}
          </button>
        </div>
      </FormSheet>
    )
  }

  const { wallets, categories, transaction } = loadState
  const deleteCurrency = (selectedWallet?.currency ?? 'UZS') as 'UZS' | 'USD'
  const deleteAmount = parsePositiveInt(amount) ?? transaction.amount

  return (
    <>
      <FormSheet
        open
        title={sheetTitle}
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

      <DeleteConfirmSheet
        open={deleteConfirmOpen}
        onClose={() => {
          setDeleteConfirmOpen(false)
          setDeleteError(false)
        }}
        onConfirm={() => void handleDelete()}
        comment={comment}
        categoryLabel={categoryLabel}
        amount={deleteAmount}
        currency={deleteCurrency}
        confirming={deleting}
        error={deleteError}
      />
    </>
  )
}
