import { useTranslation } from 'react-i18next'

import {
  addDays,
  type ChipKey,
  chipKeyFor,
  formatChipDate,
  isValidIsoDate,
  todayTashkent,
} from '../utils/dateChips'
import { getLocale } from '../utils/periodFilter'
import { NativeDatePicker } from './NativeDatePicker'

type DateChipsProps = {
  /** `YYYY-MM-DD`, Tashkent calendar day; empty/invalid shows no chip selected. */
  value: string
  onChange: (value: string) => void
  hasError?: boolean
}

const QUICK_CHIPS: { key: Exclude<ChipKey, 'other'>; offset: number }[] = [
  { key: 'today', offset: 0 },
  { key: 'yesterday', offset: -1 },
  { key: 'dayBefore', offset: -2 },
]

export function DateChips({ value, onChange, hasError = false }: DateChipsProps) {
  const { t } = useTranslation()
  const today = todayTashkent()
  const selected: ChipKey | null = isValidIsoDate(value) ? chipKeyFor(value, today) : null
  const otherLabel =
    selected === 'other' ? formatChipDate(value, today, getLocale()) : t('dateChips.other')

  return (
    <div className="date-chips" role="group" aria-label={t('formSheet.date')}>
      {QUICK_CHIPS.map(({ key, offset }) => (
        <button
          key={key}
          type="button"
          className={`date-chip${selected === key ? ' date-chip--selected' : ''}`}
          aria-pressed={selected === key}
          onClick={() => onChange(addDays(today, offset))}
        >
          {t(`dateChips.${key}`)}
        </button>
      ))}
      <NativeDatePicker value={value} onChange={onChange} max={today}>
        {(open) => (
          <button
            type="button"
            className={`date-chip${selected === 'other' ? ' date-chip--selected' : ''}${hasError ? ' date-chip--error' : ''}`}
            aria-pressed={selected === 'other'}
            onClick={open}
          >
            {otherLabel}
          </button>
        )}
      </NativeDatePicker>
    </div>
  )
}
