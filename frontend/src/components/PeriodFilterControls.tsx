import {
  type ClipboardEvent,
  type KeyboardEvent,
  useState,
} from 'react'
import { Input, SegmentedControl, Text } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import {
  formatMonthLabel,
  initializeRangeFromMonth,
  shiftMonth,
  type PeriodTab,
  type SelectedMonth,
} from '../utils/periodFilter'
import {
  extractDigits,
  formatDateDigits,
  isValidMaskedDate,
} from '../utils/transactionForm'

type MaskedDateInputProps = {
  header: string
  value: string
  onChange: (value: string) => void
  hasError: boolean
  errorText?: string
  onBlur: () => void
  onEdit: () => void
}

function MaskedDateInput({
  header,
  value,
  onChange,
  hasError,
  errorText,
  onBlur,
  onEdit,
}: MaskedDateInputProps) {
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
    <div className="history-range-field">
      <Input
        header={header}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        value={value}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onBlur={onBlur}
        onChange={(event) => {
          const digits = extractDigits(event.target.value).slice(0, 8)
          onChange(formatDateDigits(digits))
          onEdit()
        }}
        status={hasError ? 'error' : 'default'}
      />
      {hasError && errorText ? (
        <Text className="history-range-field__error" role="alert">{errorText}</Text>
      ) : null}
    </div>
  )
}

type PeriodFilterControlsProps = {
  periodTab: PeriodTab
  onPeriodTabChange: (tab: PeriodTab) => void
  selectedMonth: SelectedMonth
  onSelectedMonthChange: (month: SelectedMonth) => void
  rangeFrom: string
  rangeTo: string
  onRangeFromChange: (value: string) => void
  onRangeToChange: (value: string) => void
  rangeFromTouched: boolean
  rangeToTouched: boolean
  onRangeFromTouched: () => void
  onRangeToTouched: () => void
  rangeOrderInvalid: boolean
  monthSelectorClassName?: string
  periodHint?: string
}

export function PeriodFilterControls({
  periodTab,
  onPeriodTabChange,
  selectedMonth,
  onSelectedMonthChange,
  rangeFrom,
  rangeTo,
  onRangeFromChange,
  onRangeToChange,
  rangeFromTouched,
  rangeToTouched,
  onRangeFromTouched,
  onRangeToTouched,
  rangeOrderInvalid,
  monthSelectorClassName = 'home-page__month-selector',
  periodHint,
}: PeriodFilterControlsProps) {
  const { t } = useTranslation()
  const [rangeInitialized, setRangeInitialized] = useState(false)

  const rangeFromInvalid = periodTab === 'range' && rangeFromTouched && !isValidMaskedDate(rangeFrom)
  const rangeToInvalid = periodTab === 'range' && rangeToTouched && !isValidMaskedDate(rangeTo)
  const showRangeOrderError =
    periodTab === 'range' && rangeOrderInvalid && rangeFromTouched && rangeToTouched

  const handlePeriodTabChange = (tab: PeriodTab) => {
    if (tab === 'range' && !rangeInitialized) {
      const initialRange = initializeRangeFromMonth(selectedMonth)
      onRangeFromChange(initialRange.rangeFrom)
      onRangeToChange(initialRange.rangeTo)
      setRangeInitialized(true)
    }
    onPeriodTabChange(tab)
  }

  return (
    <>
      <div className="segmented-control-wrap history-page__period-tabs">
        <SegmentedControl>
          <SegmentedControl.Item
            selected={periodTab === 'month'}
            onClick={() => handlePeriodTabChange('month')}
          >
            {t('history.tabMonth')}
          </SegmentedControl.Item>
          <SegmentedControl.Item
            selected={periodTab === 'range'}
            onClick={() => handlePeriodTabChange('range')}
          >
            {t('history.tabRange')}
          </SegmentedControl.Item>
        </SegmentedControl>
      </div>

      {periodTab === 'month' ? (
        <div className={monthSelectorClassName}>
          <button
            type="button"
            className="home-month-nav__button analytics-page__month-nav"
            aria-label={t('home.previousMonth')}
            onClick={() => onSelectedMonthChange(shiftMonth(selectedMonth, -1))}
          >
            ‹
          </button>
          <div className="analytics-page__month-label-wrap">
            <Text weight="2" className="home-page__month-label analytics-page__month-label">
              {formatMonthLabel(selectedMonth)}
            </Text>
            {periodHint ? (
              <Text className="analytics-page__period-hint">{periodHint}</Text>
            ) : null}
          </div>
          <button
            type="button"
            className="home-month-nav__button analytics-page__month-nav"
            aria-label={t('home.nextMonth')}
            onClick={() => onSelectedMonthChange(shiftMonth(selectedMonth, 1))}
          >
            ›
          </button>
        </div>
      ) : (
        <div className="history-page__range-fields">
          <MaskedDateInput
            header={t('history.dateFrom')}
            value={rangeFrom}
            onChange={onRangeFromChange}
            hasError={rangeFromInvalid}
            errorText={rangeFromInvalid ? t('history.invalidDate') : undefined}
            onBlur={onRangeFromTouched}
            onEdit={() => {
              onRangeFromTouched()
              if (rangeToTouched) {
                onRangeToTouched()
              }
            }}
          />
          <MaskedDateInput
            header={t('history.dateTo')}
            value={rangeTo}
            onChange={onRangeToChange}
            hasError={rangeToInvalid || showRangeOrderError}
            errorText={
              rangeToInvalid
                ? t('history.invalidDate')
                : showRangeOrderError
                  ? t('history.invalidRange')
                  : undefined
            }
            onBlur={onRangeToTouched}
            onEdit={() => {
              onRangeToTouched()
              if (rangeFromTouched) {
                onRangeFromTouched()
              }
            }}
          />
        </div>
      )}
    </>
  )
}
