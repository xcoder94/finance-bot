import { useTranslation } from 'react-i18next'

export type AdminTab = 'growth' | 'ops' | 'users'
const TABS: AdminTab[] = ['growth', 'ops', 'users']

type Props = { active: AdminTab; onChange: (tab: AdminTab) => void }

export function AdminTabs({ active, onChange }: Props) {
  const { t } = useTranslation('admin')
  return (
    <div className="analytics-toolbar">
      <div className="analytics-tabs" role="tablist" aria-label={t('title')}>
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={active === tab}
            className={active === tab ? 'analytics-tabs__btn analytics-tabs__btn--active' : 'analytics-tabs__btn'}
            onClick={() => onChange(tab)}
          >
            {t(`tabs.${tab}`)}
          </button>
        ))}
      </div>
    </div>
  )
}
