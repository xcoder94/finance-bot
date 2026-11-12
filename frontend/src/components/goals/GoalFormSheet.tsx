import { ownerFormErrorKey } from '../../api/familyChanged'
import { revealMessage } from '../../utils/revealMessage'
import {
  type KeyboardEvent,
  type ClipboardEvent,
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
  formatThousandsDigits,
  insertDigitAt,
  MAX_AMOUNT_DIGITS,
} from '../../utils/transactionForm'
import {
  walletCurrencySuffix,
} from '../../utils/transactionFormFields'
import { ENTITY_NAME_MAX } from '../../constants/entityLimits'
import { clampEntityName } from '../settings/entityNameValidation'
import { useNameOverflow } from '../settings/useNameOverflow'
import { goalDeadlineValidation } from './goalFormDeadline'
import { formatChipDate, todayTashkent } from '../../utils/dateChips'
import { getLocale } from '../../utils/periodFilter'
import { NativeDatePicker } from '../NativeDatePicker'
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
  /** false for a member: the sentence 'only the owner' is shown and Save is off */
  editable?: boolean
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
  editable = true,
  onClose,
  onCreate,
  onUpdate,
}: GoalFormSheetProps) {
  const { t } = useTranslation()
  const [walletId, setWalletId] = useState('')
  const [targetAmountDigits, setTargetAmountDigits] = useState('')
  const [amountOverLimit, setAmountOverLimit] = useState(false)
  const [name, setName] = useState('')
  const nameOverflow = useNameOverflow()
  const [deadline, setDeadline] = useState('')
  const [deadlineTouched, setDeadlineTouched] = useState(false)
  const [walletPickerOpen, setWalletPickerOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const selectableWallets = useMemo(
    () =>
      mode === 'create'
        ? wallets.filter((wallet) => !wallet.is_personal && !wallet.has_active_goal)
        : wallets,
    [mode, wallets],
  )

  // The family can change under an open form (409 family_changed): forget a wallet the new budget lacks.
  useEffect(() => {
    if (walletId && !wallets.some((wallet) => wallet.id === walletId)) {
      setWalletId('')
    }
  }, [wallets, walletId])

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
      nameOverflow.reset()
      setDeadline(goal.deadline ?? '')
      setDeadlineTouched(false)
    } else {
      const firstWallet = selectableWallets[0]
      setWalletId(firstWallet?.id ?? '')
      setTargetAmountDigits('')
      setName('')
      setDeadline('')
      setDeadlineTouched(false)
    }

    setAmountOverLimit(false)
    setSaving(false)
    setSaveError(null)
    setWalletPickerOpen(false)
  }, [open, mode, goal, selectableWallets])

  useNativeBackButtonOverlay(open && !walletPickerOpen, onClose)

  const existingDeadline = mode === 'edit' && goal?.deadline ? goal.deadline : ''
  const deadlineValidation = goalDeadlineValidation(deadline, {
    mode,
    existingDeadline,
  })
  const deadlineValid = deadlineValidation.valid
  const deadlineHintKey = deadlineTouched ? deadlineValidation.hintKey : null
  const targetAmount = Number(targetAmountDigits)
  const hasValidAmount = targetAmountDigits.length > 0 && targetAmount > 0 && !amountOverLimit
  const canSave =
    editable &&
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

  const handleSave = async () => {
    if (!canSave) {
      return
    }

    const deadlineValue = deadline.length > 0 ? deadline : null

    const trimmedName = name.trim()

    setSaving(true)
    setSaveError(null)
    try {
      if (mode === 'create') {
        await onCreate({
          wallet_id: walletId,
          target_amount: targetAmount,
          name: trimmedName.length > 0 ? trimmedName : null,
          deadline: deadlineValue,
        })
      } else if (goal) {
        await onUpdate(goal.id, {
          target_amount: targetAmount,
          name: trimmedName.length > 0 ? trimmedName : null,
          deadline: deadlineValue,
        })
      }
      onClose()
    } catch (error) {
      setSaveError(ownerFormErrorKey(error, 'settings.submitError', 'familyChanged.goalsOwnerOnly'))
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
        hint={nameOverflow.overflow ? t('settings.nameTooLong30') : t('goals.form.nameHint')}
        hintError={nameOverflow.overflow}
        muted={name.trim().length === 0}
      >
        <input
          className="form-sheet-field__input"
          value={name}
          maxLength={ENTITY_NAME_MAX}
          onPaste={nameOverflow.onPaste}
          onChange={(event) => {
            const next = clampEntityName(event.target.value)
            nameOverflow.onValueChange(next)
            setName(next)
            setSaveError(null)
          }}
        />
      </FormSheetField>

      <NativeDatePicker
        value={deadline}
        onChange={(next) => {
          setDeadline(next)
          setDeadlineTouched(true)
        }}
        min={existingDeadline && existingDeadline < todayTashkent() ? existingDeadline : todayTashkent()}
        max="2100-12-31"
      >
        {(openCalendar) => (
          <FormSheetField
            label={t('goals.form.deadlineLabel')}
            right="›"
            muted={deadline.length === 0}
            hint={deadlineHintKey ? t(deadlineHintKey) : undefined}
            hintError={deadlineTouched && !deadlineValid}
            onClick={openCalendar}
          >
            <span>
              {deadline.length > 0
                ? formatChipDate(deadline, todayTashkent(), getLocale())
                : t('goals.form.deadlineNotSelected')}
            </span>
          </FormSheetField>
        )}
      </NativeDatePicker>
      {deadline.length > 0 ? (
        <button
          type="button"
          className="goal-deadline-clear"
          onClick={() => {
            setDeadline('')
            setDeadlineTouched(false)
          }}
        >
          {t('goals.form.deadlineClear')}
        </button>
      ) : null}

      {!editable || saveError ? (
        <div className="form-sheet-load-error" role="alert" ref={revealMessage}>
          <p>{t(editable ? saveError! : 'familyChanged.goalsOwnerOnly')}</p>
          {editable && saveError === 'settings.submitError' ? (
            <button type="button" onClick={() => void handleSave()} disabled={saving}>
              {t('auth.retry')}
            </button>
          ) : null}
        </div>
      ) : null}
    </FormSheet>
  )
}
