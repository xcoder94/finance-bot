import {
  type ClipboardEvent,
  type KeyboardEvent,
  useId,
  useLayoutEffect,
  useRef,
} from 'react'
import { useTranslation } from 'react-i18next'

import type { Wallet } from '../../api/transactions'
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
  formatCommentCounter,
  isCommentTooLong,
  MAX_COMMENT_LENGTH,
  transferRateFieldSuffix,
} from '../../utils/transactionFormFields'
import { FormSheet } from './FormSheet'
import { useNativeBackButtonOverlay } from '../nativeBackButtonContext'
import { FormSheetField } from './FormSheetField'

type FormSheetAmountFieldProps = {
  value: string
  currencySuffix: string
  overLimit: boolean
  hint?: string
  onChange: (value: string) => void
  onOverLimitChange: (overLimit: boolean) => void
}

export function FormSheetAmountField({
  value,
  currencySuffix,
  overLimit,
  hint,
  onChange,
  onOverLimitChange,
}: FormSheetAmountFieldProps) {
  const { t } = useTranslation()
  const inputRef = useRef<HTMLInputElement>(null)
  const pendingCursor = useRef<number | null>(null)
  const errorId = useId()
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
    <FormSheetField
      label={t('addTransaction.amount')}
      right={currencySuffix}
      mono
      hint={hint}
      hintError={overLimit}
    >
      <input
        ref={inputRef}
        className="form-sheet-field__input form-sheet-field__input--mono"
        type="text"
        inputMode="numeric"
        autoComplete="off"
        placeholder="0"
        value={displayValue}
        aria-invalid={overLimit}
        aria-describedby={overLimit ? errorId : undefined}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onChange={(event) => {
          const digits = extractDigits(event.target.value)
          if (digits.length > MAX_AMOUNT_DIGITS) {
            onOverLimitChange(true)
            return
          }
          onOverLimitChange(false)
          onChange(digits)
          pendingCursor.current = cursorPosAfterDigits(formatThousandsDigits(digits), digits.length)
        }}
      />
      {overLimit ? (
        <span id={errorId} className="visually-hidden">
          {t('addTransaction.amountTooLong')}
        </span>
      ) : null}
    </FormSheetField>
  )
}

type FormSheetCommentFieldProps = {
  value: string
  onChange: (value: string) => void
}

export function FormSheetCommentField({ value, onChange }: FormSheetCommentFieldProps) {
  const { t } = useTranslation()
  const tooLong = isCommentTooLong(value)

  return (
    <FormSheetField
      label={t('formSheet.comment')}
      right={formatCommentCounter(value.length)}
      muted={value.length === 0}
      hint={tooLong ? t('formSheet.commentTooLong') : undefined}
      hintError={tooLong}
    >
      <textarea
        className="form-sheet-field__textarea"
        value={value}
        rows={1}
        maxLength={MAX_COMMENT_LENGTH}
        onChange={(event) => onChange(event.target.value.slice(0, MAX_COMMENT_LENGTH))}
      />
    </FormSheetField>
  )
}

type FormSheetDateFieldProps = {
  value: string
  hasError: boolean
  onChange: (value: string) => void
  onBlur: () => void
  onEdit: () => void
}

export function FormSheetDateField({
  value,
  hasError,
  onChange,
  onBlur,
  onEdit,
}: FormSheetDateFieldProps) {
  const { t } = useTranslation()

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Backspace') {
      event.preventDefault()
      onChange(formatDateDigits(extractDigits(value).slice(0, -1)))
      onEdit()
      return
    }

    if (event.key.length === 1 && /\d/.test(event.key)) {
      event.preventDefault()
      const digits = extractDigits(value)
      if (digits.length >= 8) {
        return
      }
      onChange(formatDateDigits(digits + event.key))
      onEdit()
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
    const pasted = extractDigits(event.clipboardData.getData('text'))
    const combined = (extractDigits(value) + pasted).slice(0, 8)
    onChange(formatDateDigits(combined))
    onEdit()
  }

  return (
    <FormSheetField
      label={t('formSheet.date')}
      right="›"
      hint={hasError ? t('addTransaction.invalidDate') : undefined}
      hintError={hasError}
    >
      <input
        className="form-sheet-field__input"
        type="text"
        inputMode="numeric"
        autoComplete="off"
        value={value}
        aria-invalid={hasError}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onBlur={onBlur}
        onChange={(event) => {
          onChange(formatDateDigits(extractDigits(event.target.value).slice(0, 8)))
          onEdit()
        }}
      />
    </FormSheetField>
  )
}

export function isFormSheetDateValid(value: string): boolean {
  return isValidMaskedDate(value)
}

type FormSheetRateFieldProps = {
  value: string
  overLimit: boolean
  resultHint?: string
  onChange: (value: string) => void
  onOverLimitChange: (overLimit: boolean) => void
}

export function FormSheetRateField({
  value,
  overLimit,
  resultHint,
  onChange,
  onOverLimitChange,
}: FormSheetRateFieldProps) {
  const { t } = useTranslation()
  const inputRef = useRef<HTMLInputElement>(null)
  const pendingCursor = useRef<number | null>(null)
  const errorId = useId()
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
    <FormSheetField
      label={t('addTransaction.rateLabel')}
      right={transferRateFieldSuffix()}
      mono
      hint={resultHint ?? (overLimit ? t('addTransaction.amountTooLong') : undefined)}
      hintError={overLimit}
    >
      <input
        ref={inputRef}
        className="form-sheet-field__input form-sheet-field__input--mono"
        type="text"
        inputMode="numeric"
        autoComplete="off"
        placeholder="0"
        value={displayValue}
        aria-invalid={overLimit}
        aria-describedby={overLimit ? errorId : undefined}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onChange={(event) => {
          const digits = extractDigits(event.target.value)
          if (digits.length > MAX_AMOUNT_DIGITS) {
            onOverLimitChange(true)
            return
          }
          onOverLimitChange(false)
          onChange(digits)
          pendingCursor.current = cursorPosAfterDigits(formatThousandsDigits(digits), digits.length)
        }}
      />
      {overLimit ? (
        <span id={errorId} className="visually-hidden">
          {t('addTransaction.amountTooLong')}
        </span>
      ) : null}
    </FormSheetField>
  )
}

type WalletPickerSheetProps = {
  open: boolean
  title?: string
  wallets: Wallet[]
  selectedWalletId: string | null
  onClose: () => void
  onSelect: (walletId: string) => void
}

export function WalletPickerSheet({
  open,
  title,
  wallets,
  selectedWalletId,
  onClose,
  onSelect,
}: WalletPickerSheetProps) {
  const { t } = useTranslation()

  useNativeBackButtonOverlay(open, onClose)

  return (
    <FormSheet open={open} title={title ?? t('addTransaction.wallet')} onClose={onClose} showPrimary={false}>
      <div className="category-picker">
        {wallets.map((wallet) => {
          const label = getDisplayName(wallet, t)
          const selected = selectedWalletId === wallet.id

          return (
            <button
              key={wallet.id}
              type="button"
              className="category-picker__row"
              onClick={() => {
                onSelect(wallet.id)
                onClose()
              }}
            >
              <span
                className={[
                  'category-picker__radio',
                  selected ? 'category-picker__radio--selected' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                aria-hidden="true"
              >
                <span className="category-picker__radio-dot" />
              </span>
              <span className="category-picker__name">{label}</span>
            </button>
          )
        })}
      </div>
    </FormSheet>
  )
}
