import {
  type ClipboardEvent,
  type KeyboardEvent,
  useEffect,
  useMemo,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'

import type { GoalResponse } from '../../api/goals'
import type { WalletResponse } from '../../api/wallets'
import { getDisplayName } from '../../utils/getDisplayName'
import {
  countDigitsBeforeCursor,
  cursorPosAfterDigits,
  deleteDigitAt,
  deleteDigitBefore,
  deleteDigitRange,
  extractDigits,
  formatDateDigits,
  formatThousandsDigits,
  insertDigitAt,
  isValidMaskedDate,
  MAX_AMOUNT_DIGITS,
} from '../../utils/transactionForm'
import {
  isoToMaskedDateInTashkent,
  maskedDateToTashkentIso,
  walletCurrencySuffix,
} from '../../utils/transactionFormFields'
import { useNativeBackButtonOverlay } from '../nativeBackButtonContext'
import { FormSheet } from '../forms/FormSheet'
import { FormSheetField } from '../forms/FormSheetField'
import { WalletPickerSheet } from '../forms/transactionAddFields'

export type GoalFormMode = 'create' | 'edit'

type GoalFormSheetProps = {
  open: boolean
  mode: GoalFormMode
  goal: GoalResponse | null
  wallets: WalletResponse[]
  onClose: () => void
  onCreate: (payload: {
    wallet_id: string
    target_amount: number
    name?: string | null
    deadline?: string | null
  }) => Promise<void>
  onUpdate: (
    goalId: string,
    payload: {
      name?: string | null
      target_amount?: number
      deadline?: string | null
    },
  ) => Promise<void>
}

function formatWalletPickerLabel(
  wallet: WalletResponse,
  t: ReturnType<typeof useTranslation>['t'],
): string {
  return `${getDisplayName(wallet, t)} ${wallet.currency}`
}

function maskedDateToIsoDate(value: string): string | null {
  const iso = maskedDateToTashkentIso(value)
  return iso ? iso.slice(0, 10) : null
}

type GoalAmountFieldProps = {
  label: string
  value: string
  currencySuffix: string
  overLimit: boolean
  onChange: (value: string) => void
  onOverLimitChange: (overLimit: boolean) => void
}

function GoalAmountField({
  label,
  value,
  currencySuffix,
  overLimit,
  onChange,
  onOverLimitChange,
}: GoalAmountFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const pendingCursor = useRef<number | null>(null)
  const displayValue = formatThousandsDigits(value)

  useLayoutEffect(() => {
    if (pendingCursor.current === null || !inputRef.current) {
      return
    }
    inputRef.current.setSelectionRange(pendingCursor.current, pendingCursor.current)
    pendingCursor.current = null
  }, [displayValue])

  const setDigits = (nextDigits: string, cursorDigitIndex: number) => {
    onChange(nextDigits)
    pendingCursor.current = cursorPosAfterDigits(formatThousandsDigits(nextDigits), cursorDigitIndex)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    const input = event.currentTarget
    const selectionStart = input.selectionStart ?? displayValue.length
    const selectionEnd = input.selectionEnd ?? selectionStart
    const digitStart = countDigitsBeforeCursor(displayValue, selectionStart)
    const digitEnd = countDigitsBeforeCursor(displayValue, selectionEnd)
    const hasSelection = selectionStart !== selectionEnd

    if (event.key === 'Backspace') {
      event.preventDefault()
      onOverLimitChange(false)
      if (hasSelection) {
        setDigits(deleteDigitRange(value, digitStart, digitEnd), digitStart)
        return
      }
      if (digitStart === 0) {
        return
      }
      setDigits(deleteDigitBefore(value, digitStart), digitStart - 1)
      return
    }

    if (event.key === 'Delete') {
      event.preventDefault()
      onOverLimitChange(false)
      if (hasSelection) {
        setDigits(deleteDigitRange(value, digitStart, digitEnd), digitStart)
        return
      }
      if (digitStart >= value.length) {
        return
      }
      setDigits(deleteDigitAt(value, digitStart), digitStart)
      return
    }

    if (event.key.length === 1 && /\d/.test(event.key)) {
      event.preventDefault()
      const nextDigits = hasSelection
        ? insertDigitAt(deleteDigitRange(value, digitStart, digitEnd), digitStart, event.key)
        : insertDigitAt(value, digitStart, event.key)
      if (nextDigits.length > MAX_AMOUNT_DIGITS) {
        onOverLimitChange(true)
        return
      }
      onOverLimitChange(false)
      setDigits(nextDigits, digitStart + 1)
      return
    }

    if (
      event.key.length === 1 &&
      event.key !== 'Tab' &&
      !event.metaKey &&
      !event.ctrlKey &&
      !event.altKey
    ) {
      event.preventDefault()
    }
  }

  const handlePaste = (event: ClipboardEvent<HTMLInputElement>) => {
    event.preventDefault()
    const input = event.currentTarget
    const selectionStart = input.selectionStart ?? displayValue.length
    const selectionEnd = input.selectionEnd ?? selectionStart
    const digitStart = countDigitsBeforeCursor(displayValue, selectionStart)
    const digitEnd = countDigitsBeforeCursor(displayValue, selectionEnd)
    const pasted = extractDigits(event.clipboardData.getData('text'))
    const combined = value.slice(0, digitStart) + pasted + value.slice(digitEnd)
    if (combined.length > MAX_AMOUNT_DIGITS) {
      onOverLimitChange(true)
      return
    }
    onOverLimitChange(false)
    setDigits(combined, digitStart + pasted.length)
  }

  return (
    <FormSheetField label={label} right={currencySuffix} mono hintError={overLimit}>
      <input
        ref={inputRef}
        className="form-sheet-field__input form-sheet-field__input--mono"
        value={displayValue}
        inputMode="numeric"
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onChange={() => undefined}
      />
    </FormSheetField>
  )
}

export function GoalFormSheet({
  open,
  mode,
  goal,
  wallets,
  onClose,
  onCreate,
  onUpdate,
}: GoalFormSheetProps) {
  const { t } = useTranslation()
  const [walletId, setWalletId] = useState('')
  const [targetAmountDigits, setTargetAmountDigits] = useState('')
  const [amountOverLimit, setAmountOverLimit] = useState(false)
  const [name, setName] = useState('')
  const [deadlineMasked, setDeadlineMasked] = useState('')
  const [deadlineTouched, setDeadlineTouched] = useState(false)
  const [walletPickerOpen, setWalletPickerOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(false)

  const selectableWallets = useMemo(
    () =>
      mode === 'create'
        ? wallets.filter((wallet) => !wallet.is_personal && !wallet.has_active_goal)
        : wallets,
    [mode, wallets],
  )

  const selectedWallet =
    selectableWallets.find((wallet) => wallet.id === walletId) ??
    wallets.find((wallet) => wallet.id === walletId) ??
    null

  const currency = (selectedWallet?.currency ?? goal?.currency ?? 'UZS') as 'UZS' | 'USD'
  const currencySuffix = walletCurrencySuffix(currency)
  const walletLocked = mode === 'edit'

  useEffect(() => {
    if (!open) {
      return
    }

    if (mode === 'edit' && goal) {
      setWalletId(goal.wallet_id)
      setTargetAmountDigits(String(goal.target_amount))
      setName(goal.name)
      setDeadlineMasked(
        goal.deadline ? isoToMaskedDateInTashkent(`${goal.deadline}T12:00:00.000Z`) : '',
      )
      setDeadlineTouched(false)
    } else {
      const firstWallet = selectableWallets[0]
      setWalletId(firstWallet?.id ?? '')
      setTargetAmountDigits('')
      setName('')
      setDeadlineMasked('')
      setDeadlineTouched(false)
    }

    setAmountOverLimit(false)
    setSaving(false)
    setSaveError(false)
    setWalletPickerOpen(false)
  }, [open, mode, goal, selectableWallets])

  useNativeBackButtonOverlay(open && !walletPickerOpen, onClose)

  const targetAmount = Number(targetAmountDigits)
  const hasValidAmount = targetAmountDigits.length > 0 && targetAmount > 0 && !amountOverLimit
  const deadlineValid = deadlineMasked.length === 0 || isValidMaskedDate(deadlineMasked)
  const canSave =
    hasValidAmount &&
    deadlineValid &&
    (mode === 'edit' ? goal !== null : walletId.length > 0) &&
    !saving

  const title =
    mode === 'create'
      ? t('goals.form.newTitle')
      : (goal?.name ?? t('goals.form.editTitle'))
  const primaryLabel = mode === 'create' ? t('goals.form.create') : t('goals.form.save')

  const walletDisplay =
    selectedWallet != null ? formatWalletPickerLabel(selectedWallet, t) : '—'

  const deadlineDisplay = deadlineMasked.length > 0 ? deadlineMasked : t('goals.form.deadlineNotSelected')

  const handleDeadlineKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Backspace') {
      event.preventDefault()
      setDeadlineMasked(formatDateDigits(extractDigits(deadlineMasked).slice(0, -1)))
      setDeadlineTouched(true)
      return
    }

    if (event.key.length === 1 && /\d/.test(event.key)) {
      event.preventDefault()
      const digits = extractDigits(deadlineMasked)
      if (digits.length >= 8) {
        return
      }
      setDeadlineMasked(formatDateDigits(digits + event.key))
      setDeadlineTouched(true)
    }
  }

  const handleSave = async () => {
    if (!canSave) {
      return
    }

    const deadline =
      deadlineMasked.length > 0 ? maskedDateToIsoDate(deadlineMasked) : null

    if (deadlineMasked.length > 0 && deadline === null) {
      setDeadlineTouched(true)
      return
    }

    const trimmedName = name.trim()

    setSaving(true)
    setSaveError(false)
    try {
      if (mode === 'create') {
        await onCreate({
          wallet_id: walletId,
          target_amount: targetAmount,
          name: trimmedName.length > 0 ? trimmedName : null,
          deadline,
        })
      } else if (goal) {
        await onUpdate(goal.id, {
          target_amount: targetAmount,
          name: trimmedName.length > 0 ? trimmedName : null,
          deadline,
        })
      }
      onClose()
    } catch {
      setSaveError(true)
    } finally {
      setSaving(false)
    }
  }

  if (walletPickerOpen) {
    return (
      <WalletPickerSheet
        open={open}
        title={t('goals.form.walletLabel')}
        wallets={selectableWallets}
        selectedWalletId={walletId}
        onClose={() => setWalletPickerOpen(false)}
        onSelect={setWalletId}
      />
    )
  }

  return (
    <FormSheet
      open={open}
      title={title}
      onClose={onClose}
      primaryLabel={primaryLabel}
      onPrimary={() => void handleSave()}
      primaryDisabled={!canSave}
      primaryLoading={saving}
    >
      <FormSheetField
        label={t('goals.form.walletLabel')}
        right={walletLocked ? undefined : '›'}
        hint={t('goals.form.walletHint')}
        onClick={
          walletLocked || selectableWallets.length === 0
            ? undefined
            : () => setWalletPickerOpen(true)
        }
      >
        <span className="form-sheet-field__value">{walletDisplay}</span>
      </FormSheetField>

      <GoalAmountField
        label={t('goals.form.targetAmountLabel')}
        value={targetAmountDigits}
        currencySuffix={currencySuffix}
        overLimit={amountOverLimit}
        onChange={setTargetAmountDigits}
        onOverLimitChange={setAmountOverLimit}
      />

      <FormSheetField
        label={t('goals.form.nameLabel')}
        hint={t('goals.form.nameHint')}
        muted={name.trim().length === 0}
      >
        <input
          className="form-sheet-field__input"
          value={name}
          onChange={(event) => {
            setName(event.target.value)
            setSaveError(false)
          }}
        />
      </FormSheetField>

      <FormSheetField
        label={t('goals.form.deadlineLabel')}
        right="›"
        muted={deadlineMasked.length === 0}
        hint={deadlineTouched && !deadlineValid ? t('goals.form.deadlineInvalid') : undefined}
        hintError={deadlineTouched && !deadlineValid}
      >
        <input
          className={[
            'form-sheet-field__input',
            deadlineMasked.length === 0 ? 'form-sheet-field__input--placeholder' : '',
          ]
            .filter(Boolean)
            .join(' ')}
          value={deadlineMasked.length > 0 ? deadlineMasked : ''}
          placeholder={t('goals.form.deadlineNotSelected')}
          inputMode="numeric"
          onBlur={() => setDeadlineTouched(true)}
          onKeyDown={handleDeadlineKeyDown}
          onChange={() => undefined}
        />
      </FormSheetField>

      {saveError ? (
        <div className="form-sheet-load-error" role="alert">
          <p>{t('settings.submitError')}</p>
          <button type="button" onClick={() => void handleSave()} disabled={saving}>
            {t('auth.retry')}
          </button>
        </div>
      ) : null}
    </FormSheet>
  )
}
