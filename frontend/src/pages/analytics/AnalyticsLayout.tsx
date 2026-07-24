import { useMemo, useState } from 'react'
import { Outlet } from 'react-router-dom'

import { AnalyticsProvider } from '../../contexts/AnalyticsContext'
import {
  currentMonth,
  useResolvedRange,
  type PeriodTab,
  type SelectedMonth,
} from '../../utils/periodFilter'
import type { Currency } from '../../utils/formatCurrency'

export function AnalyticsLayout() {
  const [periodTab, setPeriodTab] = useState<PeriodTab>('month')
  const [selectedMonth, setSelectedMonth] = useState<SelectedMonth>(currentMonth)
  const [rangeFrom, setRangeFrom] = useState('')
  const [rangeTo, setRangeTo] = useState('')
  const [rangeFromTouched, setRangeFromTouched] = useState(false)
  const [rangeToTouched, setRangeToTouched] = useState(false)
  const [currency, setCurrency] = useState<Currency>('UZS')

  const { range, rangeOrderInvalid } = useResolvedRange(
    periodTab,
    selectedMonth,
    rangeFrom,
    rangeTo,
  )
  const rangeKey = range ? `${range.dateFrom}|${range.dateTo}` : 'invalid'
  const rangeFetchEnabled = range !== null
  const fetchKey = `${rangeKey}|${currency}`

  const contextValue = useMemo(
    () => ({
      periodTab,
      setPeriodTab,
      selectedMonth,
      setSelectedMonth,
      rangeFrom,
      setRangeFrom,
      rangeTo,
      setRangeTo,
      rangeFromTouched,
      setRangeFromTouched,
      rangeToTouched,
      setRangeToTouched,
      currency,
      setCurrency,
      range,
      rangeOrderInvalid,
      rangeFetchEnabled,
      rangeKey,
      fetchKey,
    }),
    [
      periodTab,
      selectedMonth,
      rangeFrom,
      rangeTo,
      rangeFromTouched,
      rangeToTouched,
      currency,
      range,
      rangeOrderInvalid,
      rangeFetchEnabled,
      rangeKey,
      fetchKey,
    ],
  )

  return (
    <AnalyticsProvider value={contextValue}>
      <Outlet />
    </AnalyticsProvider>
  )
}
