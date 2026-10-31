import { useTranslation } from 'react-i18next'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { AdminOverview } from '../../api/admin'
import { CHART_TOOLTIP_SEPARATOR, formatDayLabel, formatSinceDate, retentionValue } from '../../utils/adminFormat'
import { AdminLoadError, AdminLoading } from './AdminStatus'

export type Loadable<T> = { status: 'loading' } | { status: 'error' } | { status: 'ready'; data: T }

const AXIS = 'var(--app-chart-axis)'
const TICK = { fill: AXIS, fontSize: 11 }

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

export function GrowthView({ state, onRetry }: { state: Loadable<AdminOverview>; onRetry: () => void }) {
  const { t } = useTranslation('admin')
  if (state.status === 'loading') return <AdminLoading />
  if (state.status === 'error') return <AdminLoadError onRetry={onRetry} />
  const d = state.data
  const nOfN = (n: number, total: number) => t('growth.nOfN', { n, total })
  const bars = d.daily_active.map((p) => ({ label: formatDayLabel(p.day), users: p.users }))
  return (
    <div className="admin-growth">
      <Block
        title={t('growth.totals')}
        rows={[
          [t('growth.users'), d.totals.users],
          [t('growth.families'), d.totals.families],
          [t('growth.familiesMulti'), d.totals.families_multi],
        ]}
      />
      <Block
        title={t('growth.newUsers')}
        rows={[
          [t('growth.today'), d.new_users.today],
          [t('growth.days7'), d.new_users.d7],
          [t('growth.days30'), d.new_users.d30],
        ]}
      />
      <Block
        title={t('growth.newFamilies')}
        rows={[
          [t('growth.today'), d.new_families.today],
          [t('growth.days7'), d.new_families.d7],
          [t('growth.days30'), d.new_families.d30],
        ]}
      />
      <Block
        title={t('growth.active')}
        rows={[
          [t('growth.dau'), d.active.dau],
          [t('growth.wau'), d.active.wau],
          [t('growth.mau'), d.active.mau],
        ]}
      />
      <Block
        title={t('growth.retention')}
        rows={[
          [t('growth.retentionD7'), retentionValue(d.retention.d7, nOfN)],
          [t('growth.retentionD30'), retentionValue(d.retention.d30, nOfN)],
        ]}
      />
      <section className="admin-block">
        <h2 className="admin-block__title">{t('growth.chart')}</h2>
        <div className="analytics-chart analytics-chart--wide">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={bars} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--app-chart-grid)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" tick={TICK} interval={4} axisLine={{ stroke: AXIS }} tickLine={{ stroke: AXIS }} />
              <YAxis tick={TICK} allowDecimals={false} width={32} axisLine={{ stroke: AXIS }} tickLine={{ stroke: AXIS }} />
              <Tooltip
                separator={CHART_TOOLTIP_SEPARATOR}
                contentStyle={{
                  backgroundColor: 'var(--app-chart-tooltip-bg)',
                  borderColor: 'var(--app-chart-tooltip-border)',
                  borderRadius: 8,
                  color: 'var(--app-chart-tooltip-text)',
                }}
                cursor={{ fill: 'var(--app-chart-cursor)' }}
              />
              <Bar dataKey="users" name={t('growth.activeSeries')} fill="var(--app-color-income)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
      {d.activity_since ? (
        <p className="admin-caption">{t('growth.since', { date: formatSinceDate(d.activity_since) })}</p>
      ) : null}
    </div>
  )
}
