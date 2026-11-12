import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
import { useRecentCategoryIds } from '../hooks/useRecentCategoryIds'
import { RecentCategoryChips } from '../components/forms/RecentCategoryChips'
import {
  FormSheetAmountField,
  FormSheetCommentField,
  FormSheetDateField,
  isFormSheetDateValid,
  WalletPickerSheet,
} from '../components/forms/transactionAddFields'
import { useNativeBackButtonOverlay } from '../components/nativeBackButtonContext'
import { saveErrorKey } from '../api/familyChanged'
import { TransactionSubmitError } from '../components/transaction-form/TransactionFormShared'
import { useAuthStore } from '../store/authStore'
import {
  getCachedExpenseCategories,
  getCachedWallets,
  invalidateHomeData,
  peekExpenseCategories,
  peekWallets,
} from '../store/dataCacheStore'
import { evaluateAddSubmit } from '../utils/addFormGate'
import { getDisplayName } from '../utils/getDisplayName'
import {
  recordRecentCategory,
  resolveRecentChips,
} from '../utils/recentCategories'
import { parsePositiveInt } from '../utils/transactionForm'
import { todayTashkent, dateToTransactionIso } from '../utils/dateChips'
import {
  buildExpenseCategoryDisplayLabel,
  filterUncategorizedCategories,
  resolveDefaultWalletId,
  walletCurrencySuffix,
} from '../utils/transactionFormFields'
import { celebrateSave } from '../store/successFlashStore'
import { haptic } from '../telegram/haptic'

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

  const [transactionDate, setTransactionDate] = useState(todayTashkent)
  const [dateError, setDateError] = useState(false)
  const [amount, setAmount] = useState('')
  const [amountOverLimit, setAmountOverLimit] = useState(false)
  const [walletId, setWalletId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [categoryLabel, setCategoryLabel] = useState('')
  const [categoryError, setCategoryError] = useState(false)
  const [comment, setComment] = useState('')

  const [categoryPickerOpen, setCategoryPickerOpen] = useState(false)
  const [walletPickerOpen, setWalletPickerOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // The person moved to another family while the form was open (the app rereads /me on return): say why.
  const shownFamily = useRef(familyId)
  useEffect(() => {
    if (shownFamily.current === familyId) return
    shownFamily.current = familyId
    setSubmitError('familyChanged.message')
  }, [familyId])

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

  // The family can change under an open form (409 family_changed): drop what the new budget lacks.
  useEffect(() => {
    if (referenceState.status !== 'success') {
      return
    }
    if (categoryId && !referenceState.categories.some((category) => category.id === categoryId)) {
      setCategoryId('')
      setCategoryLabel('')
    }
    if (walletId && !referenceState.wallets.some((wallet) => wallet.id === walletId)) {
      setWalletId('')
    }
  }, [referenceState, categoryId, walletId])

  useEffect(() => {
    if (referenceState.status !== 'success') {
      return
    }

    if (!walletId && referenceState.wallets.length > 0) {
      setWalletId(resolveDefaultWalletId(referenceState.wallets, defaultWalletId))
    }
  }, [referenceState, walletId, defaultWalletId])

  const recentIds = useRecentCategoryIds(
    familyId,
    'expense',
    referenceState.status === 'success' ? referenceState.categories : [],
    referenceState.status === 'success',
  )
  const recentChips = useMemo(
    () =>
      resolveRecentChips(
        recentIds,
        referenceState.status === 'success' ? referenceState.categories : [],
        (category, parent) =>
          parent
            ? buildExpenseCategoryDisplayLabel(getDisplayName(parent, t), getDisplayName(category, t))
            : getDisplayName(category, t),
      ),
    [recentIds, referenceState, t],
  )

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
    const verdict = evaluateAddSubmit({ parsedAmount, walletId, categoryId, amountOverLimit })
    if (verdict === 'category') {
      setCategoryError(true)
      return
    }
    if (verdict !== 'ok' || !parsedAmount) {
      return
    }

    const transactionDateIso = dateToTransactionIso(transactionDate)
    if (!transactionDateIso) {
      setDateError(true)
      return
    }

    setSubmitting(true)
    setSubmitError(null)

    try {
      await createExpenseTransaction({
        transaction_date: transactionDateIso,
        amount: parsedAmount,
        wallet_id: walletId,
        expense_category_id: categoryId,
        comment: comment.trim() || null,
      })
      recordRecentCategory(familyId, 'expense', categoryId)
      invalidateHomeData(familyId)
      celebrateSave()
      closeSheet()
    } catch (error) {
      haptic.error()
      setSubmitError(saveErrorKey(error, 'addTransaction.submitError', 'familyChanged.message'))
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
          autoFocus
          value={amount}
          currencySuffix={walletCurrencySuffix(selectedWallet?.currency ?? 'UZS')}
          overLimit={amountOverLimit}
          hint={t('formSheet.amountCurrencyHint')}
          onChange={setAmount}
          onOverLimitChange={setAmountOverLimit}
        />

        <RecentCategoryChips
          chips={recentChips}
          selectedId={categoryId}
          onSelect={(chip) => {
            setCategoryId(chip.id)
            setCategoryLabel(chip.label)
            setCategoryError(false)
          }}
        />

        <FormSheetField
          label={t('addTransaction.category')}
          right="›"
          muted={!categoryLabel}
          hint={categoryError ? t('addTransaction.chooseCategory') : undefined}
          hintError={categoryError}
          onClick={() => setCategoryPickerOpen(true)}
        >
          <span>{categoryLabel || t('addTransaction.chooseCategory')}</span>
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
          onChange={(next) => {
            setTransactionDate(next)
            setDateError(false)
          }}
        />

        <FormSheetCommentField value={comment} onChange={setComment} />

        {submitError ? <TransactionSubmitError messageKey={submitError} onRetry={() => void handleSubmit()} /> : null}
      </FormSheet>

      <CategoryPickerSheet
        variant="expense"
        open={categoryPickerOpen}
        categories={categories}
        selectedCategoryId={categoryId}
        onClose={() => setCategoryPickerOpen(false)}
        onSelect={(selection) => {
          setCategoryId(selection.categoryId)
          setCategoryError(false)
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
