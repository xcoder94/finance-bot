import { useCallback, useEffect, useRef, useState } from 'react'
import { Button, Modal, Spinner, Text } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { useNavigate } from 'react-router-dom'

import type { HistoryItem } from '../api/history'
import { getMembers, type MemberResponse } from '../api/members'
import {
  deleteTransaction,
  fetchExpenseCategories,
  fetchIncomeCategories,
  fetchTransaction,
  fetchWallets,
  type ExpenseCategory,
  type IncomeCategory,
  type TransactionResponse,
  type Wallet,
} from '../api/transactions'
import { useAuthStore } from '../store/authStore'
import {
  getCachedExpenseCategories,
  getCachedIncomeCategories,
  getCachedTransaction,
  getCachedWallets,
  invalidateTransactionData,
} from '../store/dataCacheStore'
import { formatCurrency, type Currency } from '../utils/formatCurrency'
import {
  getDisplayName,
  getHistoryItemSubtitle,
  getHistoryItemTitle,
  getHistoryWalletDisplayName,
  resolveStoredEntityDisplayName,
} from '../utils/getDisplayName'
import { useNativeBackButtonOverlay } from './nativeBackButtonContext'

type ModalView = 'detail' | 'confirmDelete'

type DetailReferences = {
  wallets: Wallet[]
  incomeCategories: IncomeCategory[]
  expenseCategories: ExpenseCategory[]
  members: MemberResponse[]
}

const EMPTY_REFERENCES: DetailReferences = {
  wallets: [],
  incomeCategories: [],
  expenseCategories: [],
  members: [],
}

type TransactionDetailModalProps = {
  listItem: HistoryItem | null
  onClose: () => void
  onDeleted: () => void
}

function isExchangeTransfer(item: HistoryItem): boolean {
  return item.type === 'transfer' && item.currency !== item.to_currency
}

function formatTransactionDateTime(isoDate: string): string {
  const date = new Date(isoDate)
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const year = date.getFullYear()
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${day}.${month}.${year} ${hours}:${minutes}`
}

function formatSignedAmount(item: HistoryItem): string {
  const formatted = formatCurrency(item.amount, item.currency as Currency)
  if (item.type === 'income') {
    return `+${formatted}`
  }
  if (item.type === 'expense') {
    return `-${formatted}`
  }
  return formatted
}

function resolveReferenceName<T extends { id: string; name: string; translation_key: string | null }>(
  items: T[],
  id: string | null,
  t: TFunction,
): string | null {
  if (!id) {
    return null
  }
  const item = items.find((entry) => entry.id === id)
  return item ? getDisplayName(item, t) : null
}

function buildAuthoritativeHistoryItem(
  transaction: TransactionResponse,
  references: DetailReferences,
  fallback: HistoryItem,
  t: TFunction,
): HistoryItem {
  const wallet = references.wallets.find((item) => item.id === transaction.wallet_id)
  const toWallet = references.wallets.find((item) => item.id === transaction.to_wallet_id)
  const expenseCategory = references.expenseCategories.find(
    (item) => item.id === transaction.expense_category_id,
  )
  const expenseParent = expenseCategory?.parent_id
    ? references.expenseCategories.find((item) => item.id === expenseCategory.parent_id)
    : null
  const member = references.members.find((item) => item.id === transaction.created_by_user_id)

  return {
    id: transaction.id,
    type: transaction.type,
    transaction_date: transaction.transaction_date,
    amount: transaction.amount,
    currency:
      wallet?.currency ??
      (fallback.wallet_id === transaction.wallet_id ? fallback.currency : ''),
    wallet_id: transaction.wallet_id,
    wallet_name:
      (wallet ? getDisplayName(wallet, t) : null) ??
      (fallback.wallet_id === transaction.wallet_id
        ? resolveStoredEntityDisplayName(
            fallback.wallet_name,
            fallback.wallet_translation_key,
            t,
          )
        : '—') ??
      '—',
    wallet_translation_key:
      wallet?.translation_key ??
      (fallback.wallet_id === transaction.wallet_id ? fallback.wallet_translation_key : null),
    to_wallet_id: transaction.to_wallet_id,
    to_wallet_name:
      (toWallet ? getDisplayName(toWallet, t) : null) ??
      (fallback.to_wallet_id === transaction.to_wallet_id
        ? resolveStoredEntityDisplayName(
            fallback.to_wallet_name,
            fallback.to_wallet_translation_key,
            t,
          )
        : null),
    to_wallet_translation_key:
      toWallet?.translation_key ??
      (fallback.to_wallet_id === transaction.to_wallet_id
        ? fallback.to_wallet_translation_key
        : null),
    to_amount: transaction.to_amount,
    to_currency:
      toWallet?.currency ??
      (fallback.to_wallet_id === transaction.to_wallet_id ? fallback.to_currency : null),
    income_category_name:
      resolveReferenceName(references.incomeCategories, transaction.income_category_id, t) ??
      (transaction.type === 'income'
        ? resolveStoredEntityDisplayName(
            fallback.income_category_name,
            fallback.income_category_translation_key,
            t,
          )
        : null),
    income_category_translation_key:
      references.incomeCategories.find((item) => item.id === transaction.income_category_id)
        ?.translation_key ??
      (transaction.type === 'income' ? fallback.income_category_translation_key : null),
    expense_category_name:
      (expenseParent ? getDisplayName(expenseParent, t) : null) ??
      (transaction.type === 'expense'
        ? resolveStoredEntityDisplayName(
            fallback.expense_category_name,
            fallback.expense_category_translation_key,
            t,
          )
        : null),
    expense_category_translation_key:
      expenseParent?.translation_key ??
      (transaction.type === 'expense' ? fallback.expense_category_translation_key : null),
    expense_subcategory_name:
      (expenseCategory ? getDisplayName(expenseCategory, t) : null) ??
      (transaction.type === 'expense'
        ? resolveStoredEntityDisplayName(
            fallback.expense_subcategory_name,
            fallback.expense_subcategory_translation_key,
            t,
          )
        : null),
    expense_subcategory_translation_key:
      expenseCategory?.translation_key ??
      (transaction.type === 'expense' ? fallback.expense_subcategory_translation_key : null),
    comment: transaction.comment,
    created_by:
      member?.first_name ??
      (member?.username ? `@${member.username}` : null) ??
      fallback.created_by,
  }
}

function TransactionDetails({
  item,
  transferLabels,
  incomeLabel,
  destinationAmountLabel,
  t,
}: {
  item: HistoryItem
  transferLabels: { transfer: string; exchange: string }
  incomeLabel: string
  destinationAmountLabel: (amount: string) => string
  t: TFunction
}) {
  return (
    <>
      <Text className={titleClass(item.type)} weight="2">
        {getHistoryItemTitle(item, transferLabels, t)}
      </Text>
      <Text className="history-detail-modal__subtitle">
        {getHistoryItemSubtitle(item, incomeLabel, t)}
      </Text>
      <Text className={amountClass(item.type)} weight="2">
        {formatSignedAmount(item)}
      </Text>
      {isExchangeTransfer(item) && item.to_amount !== null && item.to_currency ? (
        <Text className="history-detail-modal__destination-amount" weight="2">
          {destinationAmountLabel(
            formatCurrency(item.to_amount, item.to_currency as Currency),
          )}
        </Text>
      ) : null}
      <Text className="history-detail-modal__meta">
        {formatTransactionDateTime(item.transaction_date)}
      </Text>
      {item.type !== 'transfer' ? (
        <Text className="history-detail-modal__meta">
          {getHistoryWalletDisplayName(item, t)}
        </Text>
      ) : null}
      {item.created_by ? (
        <Text className="history-detail-modal__meta">{item.created_by}</Text>
      ) : null}
      {item.comment ? (
        <Text className="history-detail-modal__comment">{item.comment}</Text>
      ) : null}
    </>
  )
}

function amountClass(type: string): string {
  if (type === 'expense') {
    return 'history-detail-modal__amount history-detail-modal__amount--expense'
  }
  if (type === 'income') {
    return 'history-detail-modal__amount history-detail-modal__amount--income'
  }
  return 'history-detail-modal__amount'
}

function titleClass(type: string): string {
  if (type === 'expense') {
    return 'history-detail-modal__title history-detail-modal__title--expense'
  }
  if (type === 'income') {
    return 'history-detail-modal__title history-detail-modal__title--income'
  }
  return 'history-detail-modal__title'
}

function canModifyTransaction(
  user: { id: string; role: string } | null,
  transaction: TransactionResponse | null,
): boolean {
  if (!user || !transaction) {
    return false
  }
  return user.role === 'owner' || user.id === transaction.created_by_user_id
}

function editRouteForType(type: string, id: string): string {
  if (type === 'income') {
    return `/edit-income/${id}`
  }
  if (type === 'expense') {
    return `/edit-expense/${id}`
  }
  return `/edit-transfer/${id}`
}

export function TransactionDetailModal({
  listItem,
  onClose,
  onDeleted,
}: TransactionDetailModalProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)
  const familyId = user?.familyBudgetId ?? ''

  const [view, setView] = useState<ModalView>('detail')
  const [transaction, setTransaction] = useState<TransactionResponse | null>(null)
  const [references, setReferences] = useState<DetailReferences>(EMPTY_REFERENCES)
  const [loadStatus, setLoadStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle')
  const [loadRetryCount, setLoadRetryCount] = useState(0)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(false)
  const loadRequestId = useRef(0)

  const open = listItem !== null
  const handleClose = useCallback(() => {
    onClose()
  }, [onClose])

  useNativeBackButtonOverlay(open, handleClose)

  const loadTransaction = useCallback(async (transactionId: string) => {
    const requestId = ++loadRequestId.current
    setLoadStatus('loading')
    setTransaction(null)
    setReferences(EMPTY_REFERENCES)
    try {
      const data = await getCachedTransaction(
        familyId,
        transactionId,
        () => fetchTransaction(transactionId),
        true,
      )
      const [wallets, incomeCategories, expenseCategories, members] = await Promise.allSettled([
        getCachedWallets(familyId, fetchWallets),
        getCachedIncomeCategories(familyId, fetchIncomeCategories),
        getCachedExpenseCategories(familyId, fetchExpenseCategories),
        getMembers(),
      ])
      if (requestId !== loadRequestId.current) {
        return
      }
      setTransaction(data)
      setReferences({
        wallets: wallets.status === 'fulfilled' ? wallets.value : [],
        incomeCategories: incomeCategories.status === 'fulfilled' ? incomeCategories.value : [],
        expenseCategories: expenseCategories.status === 'fulfilled' ? expenseCategories.value : [],
        members: members.status === 'fulfilled' ? members.value : [],
      })
      setLoadStatus('success')
    } catch {
      if (requestId === loadRequestId.current) {
        setLoadStatus('error')
      }
    }
  }, [familyId])

  useEffect(() => {
    if (!listItem) {
      loadRequestId.current += 1
      setView('detail')
      setTransaction(null)
      setReferences(EMPTY_REFERENCES)
      setLoadStatus('idle')
      setDeleteError(false)
      setDeleting(false)
      return
    }

    void loadTransaction(listItem.id)
  }, [listItem, loadRetryCount, loadTransaction])

  const handleEdit = () => {
    if (!transaction) {
      return
    }
    navigate(editRouteForType(transaction.type, transaction.id))
  }

  const handleConfirmDelete = async () => {
    if (!listItem) {
      return
    }

    setDeleting(true)
    setDeleteError(false)
    try {
      await deleteTransaction(listItem.id)
      invalidateTransactionData(familyId, listItem.id)
      onDeleted()
      onClose()
    } catch {
      setDeleteError(true)
    } finally {
      setDeleting(false)
    }
  }

  const transferLabels = {
    transfer: t('history.transfer'),
    exchange: t('history.exchange'),
  }

  const showModifyActions = canModifyTransaction(user, transaction)
  const authoritativeItem =
    transaction && listItem
      ? buildAuthoritativeHistoryItem(transaction, references, listItem, t)
      : null

  return (
    <Modal open={open} onOpenChange={(nextOpen) => !nextOpen && handleClose()}>
      <Modal.Header>
        {view === 'confirmDelete' ? t('history.delete') : t('history.detailTitle')}
      </Modal.Header>

      <div className="history-detail-modal">
        {view === 'confirmDelete' ? (
          <>
            <Text>{t('history.confirmDelete')}</Text>
            {deleteError ? (
              <div className="home-block-error" role="alert">
                <Text>{t('history.deleteError')}</Text>
                <Button mode="plain" size="s" onClick={() => void handleConfirmDelete()}>
                  {t('auth.retry')}
                </Button>
              </div>
            ) : null}
            <div className="history-detail-modal__actions">
              <Button
                mode="gray"
                size="l"
                stretched
                disabled={deleting}
                onClick={() => {
                  setDeleteError(false)
                  setView('detail')
                }}
              >
                {t('addTransaction.cancel')}
              </Button>
              <Button
                mode="gray"
                size="l"
                stretched
                loading={deleting}
                className="history-detail-modal__delete-button"
                onClick={() => void handleConfirmDelete()}
              >
                {t('history.delete')}
              </Button>
            </div>
          </>
        ) : null}

        {view === 'detail' && loadStatus === 'loading' ? (
          <div className="history-detail-modal__preview" aria-busy="true">
            {listItem ? (
              <TransactionDetails
                item={listItem}
                transferLabels={transferLabels}
                incomeLabel={t('home.income')}
                destinationAmountLabel={(amount) => t('history.destinationAmount', { amount })}
                t={t}
              />
            ) : null}
            <div className="history-detail-modal__loading" role="status" aria-live="polite">
              <Spinner size="m" aria-hidden="true" />
              <span className="visually-hidden">{t('home.loading')}</span>
            </div>
          </div>
        ) : null}

        {view === 'detail' && loadStatus === 'error' ? (
          <div className="home-block-error" role="alert">
            <Text>{t('home.loadError')}</Text>
            <Button mode="plain" size="s" onClick={() => setLoadRetryCount((count) => count + 1)}>
              {t('auth.retry')}
            </Button>
          </div>
        ) : null}

        {view === 'detail' && loadStatus === 'success' && authoritativeItem ? (
          <>
            <TransactionDetails
              item={authoritativeItem}
              transferLabels={transferLabels}
              incomeLabel={t('home.income')}
              destinationAmountLabel={(amount) => t('history.destinationAmount', { amount })}
              t={t}
            />

            <div className="history-detail-modal__actions">
              {showModifyActions ? (
                <>
                  <Button mode="bezeled" size="l" stretched onClick={handleEdit}>
                    {t('history.edit')}
                  </Button>
                  <Button
                    mode="gray"
                    size="l"
                    stretched
                    className="history-detail-modal__delete-button"
                    onClick={() => {
                      setDeleteError(false)
                      setView('confirmDelete')
                    }}
                  >
                    {t('history.delete')}
                  </Button>
                </>
              ) : null}
              <Button mode="gray" size="l" stretched onClick={handleClose}>
                {t('history.close')}
              </Button>
            </div>
          </>
        ) : null}
      </div>
    </Modal>
  )
}
