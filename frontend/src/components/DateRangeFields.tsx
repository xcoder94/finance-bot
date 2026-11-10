import { useTranslation } from 'react-i18next'

import {
  formatChipDate,
  isValidIsoDate,
  presetRange,
  type RangePreset,
  todayTashkent,
} from '../utils/dateChips'
import { getLocale } from '../utils/periodFilter'
import { NativeDatePicker } from './NativeDatePicker'

const PRESETS: RangePreset[] = ['days7', 'days30', 'thisMonth', 'lastMonth']

type DateRangeFieldsProps = {
  rangeFrom: string
  rangeTo: string
  onRangeFromChange: (value: string) => void
  onRangeToChange: (value: string) => void
  rangeOrderInvalid: boolean
}

type RowProps = {
  label: string
  value: string
  max: string
  min?: string
  onChange: (value: string) => void
  hasError: boolean
}

function DateRow({ label, value, max, min, onChange, hasError }: RowProps) {
  const { t } = useTranslation()
  const text = isValidIsoDate(value)
    ? formatChipDate(value, todayTashkent(), getLocale())
    : t('dateChips.pickDate')
  return (
    <div className="history-range-field">
      <NativeDatePicker value={value} onChange={onChange} max={max} min={min}>
        {(open) => (
          <button
            type="button"
            className={`form-sheet-field form-sheet-field--button date-range-row${hasError ? ' date-range-row--error' : ''}`}
            onClick={open}
          >
            <span className="form-sheet-field__label">{label}</span>
            <span className="form-sheet-field__control">
              <span className="form-sheet-field__value">{text}</span>
              <span className="form-sheet-field__right">›</span>
            </span>
          </button>
        )}
      </NativeDatePicker>
    </div>
  )
}

export function DateRangeFields({
  rangeFrom,
  rangeTo,
  onRangeFromChange,
  onRangeToChange,
  rangeOrderInvalid,
}: DateRangeFieldsProps) {
  const { t } = useTranslation()
  const today = todayTashkent()

  return (
    <div className="history-page__range-fields date-range-fields">
      <div className="date-range-presets">
        {PRESETS.map((preset) => (
          <button
            key={preset}
            type="button"
            className="date-chip"
            onClick={() => {
              const range = presetRange(preset, today)
              onRangeFromChange(range.from)
              onRangeToChange(range.to)
            }}
          >
            {t(`dateChips.${preset}`)}
          </button>
        ))}
      </div>
      <div className="date-range-rows">
        <DateRow
          label={t('history.dateFrom')}
          value={rangeFrom}
          max={isValidIsoDate(rangeTo) && rangeTo < today ? rangeTo : today}
          onChange={onRangeFromChange}
          hasError={rangeOrderInvalid}
        />
        <DateRow
          label={t('history.dateTo')}
          value={rangeTo}
          max={today}
          min={isValidIsoDate(rangeFrom) ? rangeFrom : undefined}
          onChange={onRangeToChange}
          hasError={rangeOrderInvalid}
        />
        {rangeOrderInvalid ? (
          <div className="history-range-field__error" role="alert">
            {t('history.invalidRange')}
          </div>
        ) : null}
      </div>
    </div>
  )
}
