import {
  type ClipboardEvent,
  type KeyboardEvent,
  type ReactNode,
  useId,
  useLayoutEffect,
  useRef,
} from 'react'
import { Button, Input, Modal, Spinner, Text, Title } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import {
  countDigitsBeforeCursor,
  cursorPosAfterDigits,
  deleteDigitAt,
  deleteDigitBefore,
  deleteDigitRange,
  extractDigits,
  formatDatetimeDigits,
  formatThousandsDigits,
  insertDigitAt,
  MAX_AMOUNT_DIGITS,
} from '../../utils/transactionForm'

type TransactionFormLayoutProps = {
  titleKey: string
  children: ReactNode
  onCancel: () => void
  onSubmit: () => void
  submitting: boolean
  submitDisabled?: boolean
  submitLabelKey?: string
}

export function TransactionFormLayout({
  titleKey,
  children,
  onCancel,
  onSubmit,
  submitting,
  submitDisabled = false,
  submitLabelKey = 'addTransaction.add',
}: TransactionFormLayoutProps) {
  const { t } = useTranslation()

  return (
    <div className="transaction-form-page">
      <Title level="1" weight="2" className="transaction-form__title">
        {t(titleKey)}
      </Title>

      <div className="transaction-form__fields">{children}</div>

      <div className="transaction-form__actions">
        <Button
          type="button"
          mode="gray"
          size="l"
          stretched
          className="transaction-form__action-button"
          onClick={onCancel}
          disabled={submitting}
        >
          {t('addTransaction.cancel')}
        </Button>
        <Button
          type="button"
          mode="filled"
          size="l"
          stretched
          className="transaction-form__action-button"
          onClick={onSubmit}
          loading={submitting}
          disabled={submitDisabled || submitting}
        >
          {t(submitLabelKey)}
        </Button>
      </div>
    </div>
  )
}

export function TransactionFormLoadError({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation()

  return (
    <div className="transaction-form-page">
      <div className="transaction-form__load-error" role="alert">
        <Text>{t('addTransaction.loadError')}</Text>
        <Button mode="plain" size="s" onClick={onRetry}>
          {t('auth.retry')}
        </Button>
      </div>
    </div>
  )
}

export function TransactionFormLoading() {
  const { t } = useTranslation()

  return (
    <div
      className="transaction-form-page transaction-form-page--centered"
      role="status"
      aria-live="polite"
    >
      <Spinner size="m" aria-hidden="true" />
      <span className="visually-hidden">{t('home.loading')}</span>
    </div>
  )
}

export function TransactionSubmitError({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation()

  return (
    <div className="transaction-form__submit-error" role="alert">
      <Text>{t('addTransaction.submitError')}</Text>
      <Button mode="plain" size="s" onClick={onRetry}>
        {t('auth.retry')}
      </Button>
    </div>
  )
}

type TransactionSuccessModalProps = {
  open: boolean
  onGoHome: () => void
  onAddAnother: () => void
}

export function TransactionSuccessModal({
  open,
  onGoHome,
  onAddAnother,
}: TransactionSuccessModalProps) {
  const { t } = useTranslation()

  return (
    <Modal open={open} onOpenChange={() => undefined} dismissible={false}>
      <Modal.Header>{t('addTransaction.successTitle')}</Modal.Header>
      <div className="transaction-success-modal">
        <Button stretched size="l" onClick={onGoHome}>
          {t('addTransaction.goHome')}
        </Button>
        <Button stretched size="l" mode="bezeled" onClick={onAddAnother}>
          {t('addTransaction.addAnother')}
        </Button>
      </div>
    </Modal>
  )
}

export function TransactionFormField({ children }: { children: ReactNode }) {
  return <div className="transaction-form__field">{children}</div>
}

export function TransactionReceiveRow({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="transaction-form__receive-row">
      <Text className="transaction-form__receive-label">{label}</Text>
      <Text className="transaction-form__receive-value" weight="2">
        {value}
      </Text>
    </div>
  )
}

type MaskedDateTimeInputProps = {
  value: string
  onChange: (value: string) => void
  hasError: boolean
  onBlur: () => void
  onEdit: () => void
}

export function MaskedDateTimeInput({
  value,
  onChange,
  hasError,
  onBlur,
  onEdit,
}: MaskedDateTimeInputProps) {
  const { t } = useTranslation()

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Backspace') {
      event.preventDefault()
      onChange(formatDatetimeDigits(extractDigits(value).slice(0, -1)))
      onEdit()
      return
    }

    if (event.key.length === 1 && /\d/.test(event.key)) {
      event.preventDefault()
      const digits = extractDigits(value)
      if (digits.length >= 12) {
        return
      }
      onChange(formatDatetimeDigits(digits + event.key))
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
    const combined = (extractDigits(value) + pasted).slice(0, 12)
    onChange(formatDatetimeDigits(combined))
    onEdit()
  }

  return (
    <div className="transaction-form__field-control">
      <Input
        header={t('addTransaction.dateTime')}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        value={value}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onBlur={onBlur}
        onChange={(event) => {
          const digits = extractDigits(event.target.value).slice(0, 12)
          onChange(formatDatetimeDigits(digits))
          onEdit()
        }}
        status={hasError ? 'error' : 'default'}
      />
      {hasError ? (
        <Text className="transaction-form__field-error" role="alert">
          {t('addTransaction.invalidDateTime')}
        </Text>
      ) : null}
    </div>
  )
}

type LimitedDigitInputProps = {
  header: string
  value: string
  onChange: (value: string) => void
  overLimit: boolean
  onOverLimitChange: (overLimit: boolean) => void
  placeholder?: string
}

export function LimitedDigitInput({
  header,
  value,
  onChange,
  overLimit,
  onOverLimitChange,
  placeholder = '0',
}: LimitedDigitInputProps) {
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
        const nextDigits = deleteDigitRange(value, digitStart, digitEnd)
        setDigits(nextDigits, digitStart)
        return
      }

      if (digitStart === 0) {
        return
      }

      const nextDigits = deleteDigitBefore(value, digitStart)
      setDigits(nextDigits, digitStart - 1)
      return
    }

    if (event.key === 'Delete') {
      event.preventDefault()
      onOverLimitChange(false)

      if (hasSelection) {
        const nextDigits = deleteDigitRange(value, digitStart, digitEnd)
        setDigits(nextDigits, digitStart)
        return
      }

      if (digitStart >= value.length) {
        return
      }

      const nextDigits = deleteDigitAt(value, digitStart)
      setDigits(nextDigits, digitStart)
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
    <div className="transaction-form__field-control">
      <Input
        ref={inputRef}
        header={header}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        value={displayValue}
        placeholder={placeholder}
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
        status={overLimit ? 'error' : 'default'}
        aria-invalid={overLimit}
        aria-describedby={overLimit ? errorId : undefined}
      />
      {overLimit ? (
        <Text id={errorId} className="transaction-form__field-error" role="alert">
          {t('addTransaction.amountTooLong')}
        </Text>
      ) : null}
    </div>
  )
}
