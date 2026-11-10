import { useTranslation } from 'react-i18next'

import type { SummaryResponse } from '../../api/history'
import { formatCurrency, type Currency } from '../../utils/formatCurrency'
import { summaryCurrenciesPresent } from '../../utils/historySummaryLine'

/** One line per currency that has operations in the period: «Доход … · Расход …». */
export function HistorySummaryLine({ summary }: { summary: SummaryResponse | null }) {
  const { t } = useTranslation()
  if (!summary) {
    return null
  }
  const rows = summaryCurrenciesPresent(summary.by_currency)
  if (rows.length === 0) {
    return null
  }
  return (
    <div className="history-summary-line" data-testid="history-summary-line">
      {rows.map((row) => (
        <div key={row.currency} className="history-summary-line__row">
          <span className="history-summary-line__income">
            {t('home.income')} {formatCurrency(row.income, row.currency as Currency)}
          </span>
          {' · '}
          <span className="history-summary-line__expense">
            {t('home.expense')} {formatCurrency(row.expense, row.currency as Currency)}
          </span>
        </div>
      ))}
    </div>
  )
}
