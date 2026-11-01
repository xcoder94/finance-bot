import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { AdminOverview, AdminUsagePeriod } from '../../api/admin'
import type { OpsState } from '../../utils/adminOps'
import type { AdminUsersState } from '../../utils/adminUsersState'
import { AdminTabs, type AdminTab } from './AdminTabs'
import { GrowthView, type Loadable } from './GrowthView'
import { OpsView } from './OpsView'
import { UsersView } from './UsersView'

type Props = {
  tab: AdminTab
  onTab: (tab: AdminTab) => void
  growth: Loadable<AdminOverview>
  onRetryGrowth: () => void
  users: AdminUsersState
  query: string
  onQuery: (value: string) => void
  onMore: () => void
  onRetryUsers: () => void
  ops: OpsState
  onPeriod: (period: AdminUsagePeriod) => void
  onRetryOps: () => void
}

export function AdminScreen(p: Props) {
  const { t } = useTranslation('admin')
  return (
    <div className="page-content settings-sub-page admin-page">
      <Link to="/settings" className="settings-sub-page__back">
        {t('back')}
      </Link>
      <h1 className="settings-sub-page__title">{t('title')}</h1>
      <AdminTabs active={p.tab} onChange={p.onTab} />
      {p.tab === 'growth' ? <GrowthView state={p.growth} onRetry={p.onRetryGrowth} /> : null}
      {p.tab === 'ops' ? <OpsView state={p.ops} onPeriod={p.onPeriod} onRetry={p.onRetryOps} /> : null}
      {p.tab === 'users' ? (
        <UsersView state={p.users} query={p.query} onQuery={p.onQuery} onMore={p.onMore} onRetry={p.onRetryUsers} />
      ) : null}
    </div>
  )
}
