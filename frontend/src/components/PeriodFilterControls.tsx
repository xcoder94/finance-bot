import { useState } from 'react'
import { SegmentedControl, Text } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import {
  formatMonthLabel,
  initializeRangeFromMonth,
  shiftMonth,
  type PeriodTab,
  type SelectedMonth,
} from '../utils/periodFilter'
import { DateRangeFields } from './DateRangeFields'

type PeriodFilterControlsProps = {
  periodTab: PeriodTab
  onPeriodTabChange: (tab: PeriodTab) => void
  selectedMonth: SelectedMonth
  onSelectedMonthChange: (month: SelectedMonth) => void
  rangeFrom: string
  rangeTo: string
  onRangeFromChange: (value: string) => void
  onRangeToChange: (value: string) => void
  rangeOrderInvalid: boolean
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
  rangeOrderInvalid,
  periodHint,
}: PeriodFilterControlsProps) {
  const { t } = useTranslation()
  const [rangeInitialized, setRangeInitialized] = useState(false)

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
      <div className="segmented-control-wrap analytics-page__period-tabs">
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
        <div className="home-month-bar analytics-page__month-bar">
          <button
            type="button"
            className="home-month-bar__nav"
            aria-label={t('home.previousMonth')}
            onClick={() => onSelectedMonthChange(shiftMonth(selectedMonth, -1))}
          >
            ‹
          </button>
          <div className="analytics-page__month-label-wrap">
            <div className="home-month-bar__label">{formatMonthLabel(selectedMonth)}</div>
            {periodHint ? (
              <Text className="analytics-page__period-hint">{periodHint}</Text>
            ) : null}
          </div>
          <button
            type="button"
            className="home-month-bar__nav"
            aria-label={t('home.nextMonth')}
            onClick={() => onSelectedMonthChange(shiftMonth(selectedMonth, 1))}
          >
            ›
          </button>
        </div>
      ) : (
        <DateRangeFields
          rangeFrom={rangeFrom}
          rangeTo={rangeTo}
          onRangeFromChange={onRangeFromChange}
          onRangeToChange={onRangeToChange}
          rangeOrderInvalid={rangeOrderInvalid}
        />
      )}
    </>
  )
}
