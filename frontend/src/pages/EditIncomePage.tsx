import { useCallback, useEffect, useRef, useState } from 'react'
import { Spinner } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate, useLocation, useParams } from 'react-router-dom'

import {
  deleteTransaction,
  fetchIncomeCategories,
  fetchTransaction,
  fetchWallets,
  updateIncomeTransaction,
  type IncomeCategory,
  type TransactionResponse,
  type Wallet,
} from '../api/transactions'
import { DeleteConfirmSheet } from '../components/forms/DeleteConfirmSheet'
import { CategoryPickerSheet } from '../components/forms/CategoryPickerSheet'
import { ChangesBlock } from '../components/forms/ChangesBlock'
import { FormSheet } from '../components/forms/FormSheet'
import { TransactionGoneSheet } from '../components/forms/TransactionGoneSheet'
import { FormSheetField } from '../components/forms/FormSheetField'
import {
  FormSheetAmountField,
  FormSheetCommentField,
  FormSheetDateField,
  isFormSheetDateValid,
  WalletPickerSheet,
} from '../components/forms/transactionAddFields'
import { useNativeBackButtonOverlay } from '../components/nativeBackButtonContext'
import { saveErrorKey } from '../api/familyChanged'
import { matchCategoryInBudget } from '../utils/matchCategory'
import { TransactionSubmitError } from '../components/transaction-form/TransactionFormShared'
import { useAuthStore } from '../store/authStore'
import {
  cacheTransaction,
  getCachedIncomeCategories,
  getCachedTransaction,
  getCachedWallets,
  invalidateTransactionData,
} from '../store/dataCacheStore'
import { getDisplayName } from '../utils/getDisplayName'
import { parsePositiveInt } from '../utils/transactionForm'
import { historyBackTarget } from '../utils/historyBackTarget'
import { tashkentDateOf, dateToTransactionIso } from '../utils/dateChips'
import {
  buildEditSheetTitle,
  filterUncategorizedCategories,
  resolveEditSheetLabel,
  walletCurrencySuffix,
} from '../utils/transactionFormFields'
import { celebrateSave } from '../store/successFlashStore'
import { haptic } from '../telegram/haptic'

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  /** the person moved to another family; this operation stayed in the old budget */
  | { status: 'gone' }
  | { status: 'success'; wallets: Wallet[]; categories: IncomeCategory[]; transaction: TransactionResponse }

export function EditIncomePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const { id } = useParams<{ id: string }>()
  const familyId = useAuthStore((state) => state.user?.familyBudgetId ?? '')

  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [loadRetry, setLoadRetry] = useState(0)
  // The fields are filled from the saved operation once; a reload (family changed) must not overwrite what was typed.
  const filledFor = useRef<string | null>(null)
  const filledFamily = useRef<string | null>(null)
  // What the person picked by hand, and what the form shows now (loadData reads these when the family changes).
  const picked = useRef({ wallet: false, category: false })
  const shown = useRef({ walletId: '', categoryId: '' })
  const shownCategories = useRef<Array<{ id: string; name: string; translation_key?: string | null; parent_id?: string | null }>>([])

  const [transactionDate, setTransactionDate] = useState('')
  const [dateError, setDateError] = useState(false)
  const [amount, setAmount] = useState('')
  const [amountOverLimit, setAmountOverLimit] = useState(false)
  const [walletId, setWalletId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [categoryLabel, setCategoryLabel] = useState('')
  shown.current = { walletId, categoryId }
  const [comment, setComment] = useState('')

  const [categoryPickerOpen, setCategoryPickerOpen] = useState(false)
  const [walletPickerOpen, setWalletPickerOpen] = useState(false)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const closeSheet = useCallback(() => {
    if (typeof window.history.state?.idx === 'number' && window.history.state.idx > 0) {
      navigate(-1)
      return
    }
    navigate(historyBackTarget(location.state) ?? '/history', { replace: true })
  }, [location.state, navigate])

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
        getCachedIncomeCategories(familyId, fetchIncomeCategories, loadRetry > 0),
        getCachedTransaction(familyId, id, () => fetchTransaction(id), loadRetry > 0),
      ])

      if (transaction.type !== 'income') {
        setLoadState({ status: 'error' })
        return
      }

      const category = categories.find((item) => item.id === transaction.income_category_id)
      const categoryName = category ? getDisplayName(category, t) : '—'

      if (filledFor.current !== id) {
        setTransactionDate(tashkentDateOf(transaction.transaction_date))
        setAmount(String(transaction.amount))
        setWalletId(transaction.wallet_id)
        setCategoryId(transaction.income_category_id ?? '')
        setCategoryLabel(categoryName)
        setComment(transaction.comment ?? '')
        filledFor.current = id
        filledFamily.current = familyId
      } else if (filledFamily.current !== familyId) {
        // The person moved to another family and the operation moved with them: its category and wallet
        // now have the new budget's ids. What the person picked by hand stays when the new budget has it;
        // amount, date and comment stay as typed. Either way they are told, before anything is written.
        const labelOf = (id: string) => {
          const found = categories.find((item) => item.id === id)
          return found ? getDisplayName(found, t) : '—'
        }
        let notice = 'familyChanged.message'
        if (picked.current.wallet && wallets.some((item) => item.id === shown.current.walletId)) {
          // wallets keep their ids when a person moves: the pick stays
        } else {
          setWalletId(transaction.wallet_id)
          if (picked.current.wallet) notice = 'familyChanged.pickReplaced'
        }
        const matched = picked.current.category
          ? matchCategoryInBudget(shownCategories.current, categories, shown.current.categoryId)
          : null
        if (matched) {
          setCategoryId(matched)
          setCategoryLabel(labelOf(matched))
        } else {
          setCategoryId(transaction.income_category_id ?? '')
          setCategoryLabel(categoryName)
          if (picked.current.category) notice = 'familyChanged.pickReplaced'
        }
        setSubmitError(notice)
        filledFamily.current = familyId
      }
      shownCategories.current = categories
      setLoadState({ status: 'success', wallets, categories, transaction })
    } catch {
      setLoadState({ status: filledFor.current === id ? 'gone' : 'error' })
    }
  }, [familyId, id, loadRetry, t])

  useEffect(() => {
    void loadData()
  }, [loadData, loadRetry])

  const selectedWallet =
    loadState.status === 'success'
      ? loadState.wallets.find((wallet) => wallet.id === walletId) ?? null
      : null

  const validateDate = () => {
    const valid = isFormSheetDateValid(
      transactionDate,
      loadState.status === 'success' ? tashkentDateOf(loadState.transaction.transaction_date) : undefined,
    )
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

    const transactionDateIso = dateToTransactionIso(transactionDate, loadState.status === 'success' ? loadState.transaction.transaction_date : undefined)
    if (!transactionDateIso) {
      setDateError(true)
      return
    }

    setSubmitting(true)
    setSubmitError(null)

    try {
      const updated = await updateIncomeTransaction(id, {
        transaction_date: transactionDateIso,
        amount: parsedAmount,
        wallet_id: walletId,
        income_category_id: categoryId,
        comment: comment.trim() || null,
      })
      cacheTransaction(familyId, updated)
      invalidateTransactionData(familyId, id)
      celebrateSave()
      closeSheet()
    } catch (error) {
      haptic.error()
      setSubmitError(saveErrorKey(error, 'addTransaction.submitError', 'familyChanged.message'))
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
      : t('editIncome.title')

  const canSubmit =
    loadState.status === 'success' &&
    loadState.wallets.length > 0 &&
    loadState.categories.length > 0 &&
    parsePositiveInt(amount) !== null &&
    Boolean(walletId) &&
    Boolean(categoryId) &&
    !amountOverLimit &&
    isFormSheetDateValid(
      transactionDate,
      loadState.status === 'success' ? tashkentDateOf(loadState.transaction.transaction_date) : undefined,
    ) &&
    comment.length <= 200

  if (loadState.status === 'loading') {
    return (
      <FormSheet open title={t('editIncome.title')} onClose={closeSheet} showPrimary={false}>
        <div className="form-sheet-loading" role="status" aria-live="polite">
          <Spinner size="m" aria-hidden="true" />
          <span className="visually-hidden">{t('home.loading')}</span>
        </div>
      </FormSheet>
    )
  }

  if (loadState.status === 'gone') {
    return <TransactionGoneSheet title={t('editIncome.title')} onClose={closeSheet} />
  }

  if (loadState.status === 'error') {
    return (
      <FormSheet open title={t('editIncome.title')} onClose={closeSheet} showPrimary={false}>
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
        changes={<ChangesBlock lines={transaction.changes ?? []} />}
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
          onChange={setAmount}
          onOverLimitChange={setAmountOverLimit}
        />

        <FormSheetField
          label={t('addTransaction.category')}
          right="›"
          hint={t('formSheet.incomeCategoryHint')}
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
          onChange={(next) => {
            setTransactionDate(next)
            setDateError(false)
          }}
        />

        <FormSheetCommentField value={comment} onChange={setComment} />

        {submitError ? <TransactionSubmitError messageKey={submitError} onRetry={() => void handleSubmit()} /> : null}
      </FormSheet>

      <CategoryPickerSheet
        variant="income"
        open={categoryPickerOpen}
        categories={filterUncategorizedCategories(categories)}
        selectedCategoryId={categoryId}
        onClose={() => setCategoryPickerOpen(false)}
        onSelect={(selection) => {
          picked.current.category = true
          setCategoryId(selection.categoryId)
          setCategoryLabel(selection.label)
        }}
      />

      <WalletPickerSheet
        open={walletPickerOpen}
        wallets={wallets}
        selectedWalletId={walletId}
        onClose={() => setWalletPickerOpen(false)}
        onSelect={(id) => {
          picked.current.wallet = true
          setWalletId(id)
        }}
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
