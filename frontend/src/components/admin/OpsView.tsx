import { useTranslation } from 'react-i18next'

import type { AdminUsage, AdminUsagePeriod } from '../../api/admin'
import { formatTokens, formatUsd, unparsedValue, type OpsState } from '../../utils/adminOps'
import { AdminLoadError, AdminLoading } from './AdminStatus'

const PERIODS: Array<[AdminUsagePeriod, string]> = [
  ['day', 'ops.periodDay'],
  ['week', 'ops.periodWeek'],
  ['month', 'ops.periodMonth'],
]
const CHANNELS = ['text', 'voice', 'photo', 'app', 'unknown', 'total'] as const

type Props = { state: OpsState; onPeriod: (period: AdminUsagePeriod) => void; onRetry: () => void }

function Block({ title, rows }: { title: string; rows: Array<[string, string | number]> }) {
  return (
    <section className="admin-block">
      <h2 className="admin-block__title">{title}</h2>
      {rows.map(([label, value]) => (
        <div key={label} className="admin-block__row">
          <span>{label}</span>
          <span className="admin-block__value">{value}</span>
        </div>
      ))}
    </section>
  )
}

function UsageBlocks({ data }: { data: AdminUsage }) {
  const { t } = useTranslation('admin')
  const { ai } = data
  const threshold =
    ai.threshold_usd === null
      ? t('ops.thresholdNone')
      : t('ops.thresholdSet', {
          limit: formatUsd(ai.threshold_usd, false),
          today: formatUsd(ai.cost_today_usd, ai.cost_incomplete),
        })
  return (
    <div className="admin-ops">
      <Block title={t('ops.channels')} rows={CHANNELS.map((c) => [t(`ops.${c}`), data.operations[c]])} />
      <Block
        title={t('ops.ai')}
        rows={[
          [t('ops.calls'), ai.calls],
          [t('ops.cost'), formatUsd(ai.cost_usd, ai.cost_incomplete)],
          [t('ops.tokens'), `${formatTokens(ai.input_tokens)} / ${formatTokens(ai.output_tokens)}`],
        ]}
      />
      <Block
        title={t('ops.unparsed')}
        rows={[
          [
            t('ops.unparsed'),
            unparsedValue(ai.unparsed, ai.messages, (percent, n, total) => t('ops.unparsedValue', { percent, n, total })),
          ],
        ]}
      />
      <Block title={t('ops.errors')} rows={[[t('ops.errors'), ai.errors]]} />
      <Block title={t('ops.threshold')} rows={[[threshold, '']]} />
    </div>
  )
}

export function OpsView({ state, onPeriod, onRetry }: Props) {
  const { t } = useTranslation('admin')
  return (
    <div>
      <div className="analytics-toolbar">
        <div className="analytics-tabs" role="tablist" aria-label={t('tabs.ops')}>
          {PERIODS.map(([period, key]) => (
            <button
              key={period}
              type="button"
              role="tab"
              aria-selected={state.period === period}
              className={state.period === period ? 'analytics-tabs__btn analytics-tabs__btn--active' : 'analytics-tabs__btn'}
              onClick={() => onPeriod(period)}
            >
              {t(key)}
            </button>
          ))}
        </div>
      </div>
      {state.status === 'loading' ? <AdminLoading /> : null}
      {state.status === 'error' ? <AdminLoadError onRetry={onRetry} /> : null}
      {state.status === 'ready' ? <UsageBlocks data={state.data} /> : null}
    </div>
  )
}
