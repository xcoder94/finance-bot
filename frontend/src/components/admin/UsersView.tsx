import { useTranslation } from 'react-i18next'

import type { AdminUser } from '../../api/admin'
import { formatLastSeen, formatRegisteredDate, telegramLink } from '../../utils/adminFormat'
import type { AdminUsersState } from '../../utils/adminUsersState'
import { AdminLoadError, AdminLoading } from './AdminStatus'

type Props = {
  state: AdminUsersState
  query: string
  onQuery: (value: string) => void
  onMore: () => void
  onRetry: () => void
}

function UserRow({ user }: { user: AdminUser }) {
  const { t } = useTranslation('admin')
  const dash = t('dash')
  const link = telegramLink(user.username)
  return (
    <li className="admin-user">
      <div className="admin-user__head">
        <span className="admin-user__name">{user.first_name ?? dash}</span>
        <span className="admin-user__lang">{t(user.language === 'uz' ? 'users.langUz' : 'users.langRu')}</span>
      </div>
      <div className="admin-user__line">
        {user.username ? (
          link ? (
            <a href={link} target="_blank" rel="noopener noreferrer">
              @{user.username.replace(/^@/, '')}
            </a>
          ) : (
            <span>@{user.username.replace(/^@/, '')}</span>
          )
        ) : (
          <span>{dash}</span>
        )}
        <span>{user.phone ?? dash}</span>
      </div>
      <div className="admin-user__line">
        <span>{t('users.registered', { date: formatRegisteredDate(user.registered_at) })}</span>
        <span>{t('users.lastSeen', { value: formatLastSeen(user.last_seen_at) })}</span>
      </div>
      <div className="admin-user__line">
        <span>
          {t('users.family', {
            count: user.family_members,
            role: t(user.family_role === 'owner' ? 'users.owner' : 'users.member'),
          })}
        </span>
        <span>{t('users.operations', { count: user.operations_count })}</span>
      </div>
    </li>
  )
}

export function UsersView({ state, query, onQuery, onMore, onRetry }: Props) {
  const { t } = useTranslation('admin')
  return (
    <div className="admin-users">
      <input
        type="search"
        className="admin-search"
        placeholder={t('users.search')}
        aria-label={t('users.search')}
        value={query}
        maxLength={64}
        onChange={(e) => onQuery(e.target.value)}
      />
      {state.status === 'loading' ? <AdminLoading /> : null}
      {state.status === 'error' ? <AdminLoadError onRetry={onRetry} /> : null}
      {state.status === 'ready' ? (
        <>
          <p className="admin-caption">{t('users.total', { count: state.total })}</p>
          {state.items.length === 0 ? (
            <p className="admin-note">{t('empty')}</p>
          ) : (
            <ul className="admin-user-list">
              {state.items.map((u) => (
                <UserRow key={u.id} user={u} />
              ))}
            </ul>
          )}
          {state.moreFailed ? <p className="admin-note">{t('loadFailed')}</p> : null}
          {state.nextCursor ? (
            <button type="button" className="admin-btn" disabled={state.loadingMore} onClick={onMore}>
              {state.loadingMore ? t('loading') : t('users.more')}
            </button>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
