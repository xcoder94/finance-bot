import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import {
  getIncomeCategories,
  getExpenseCategories,
  type ExpenseCategoryResponse,
  type IncomeCategoryResponse,
} from '../api/categories'
import { getWallets, type WalletResponse } from '../api/wallets'
import { SETTINGS_TOC_ICONS } from '../components/settings/settingsTocIcons'
import i18n from '../i18n'
import { useAuthStore } from '../store/authStore'
import {
  getCachedExpenseCategories,
  getCachedIncomeCategories,
  getCachedWallets,
  peekExpenseCategories,
  peekIncomeCategories,
  peekWallets,
} from '../store/dataCacheStore'
import { buildDisplayNameById } from '../utils/getDisplayName'
import {
  countExpenseParents,
  countExpenseSubcategories,
  countPersonalWallets,
  countSharedWallets,
  defaultWalletSubtitle,
  expenseCategoriesSubtitle,
  incomeCategoriesSubtitle,
  languageSubtitle,
  membersSubtitle,
  notificationsSubtitle,
  walletsSubtitle,
} from '../utils/settingsSubtitles'

type TocLoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | {
      status: 'success'
      wallets: WalletResponse[]
      incomeCategories: IncomeCategoryResponse[]
      expenseCategories: ExpenseCategoryResponse[]
    }

function SettingsTocIcon({ path }: { path: string }) {
  return (
    <svg
      className="settings-toc-row__icon"
      width="20"
      height="20"
      viewBox="0 0 22 22"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  )
}

export function SettingsPage() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const familyId = user?.familyBudgetId ?? ''

  const [loadState, setLoadState] = useState<TocLoadState>(() => {
    const wallets = peekWallets(familyId)
    const incomeCategories = peekIncomeCategories(familyId)
    const expenseCategories = peekExpenseCategories(familyId)
    if (wallets && incomeCategories && expenseCategories) {
      return {
        status: 'success',
        wallets,
        incomeCategories,
        expenseCategories,
      }
    }
    return { status: 'loading' }
  })

  const loadTocData = useCallback(async () => {
    if (!familyId) {
      return
    }

    setLoadState((current) => (current.status === 'success' ? current : { status: 'loading' }))

    try {
      const [wallets, incomeCategories, expenseCategories] = await Promise.all([
        getCachedWallets(familyId, getWallets),
        getCachedIncomeCategories(familyId, getIncomeCategories),
        getCachedExpenseCategories(familyId, getExpenseCategories),
      ])
      setLoadState({
        status: 'success',
        wallets,
        incomeCategories,
        expenseCategories,
      })
    } catch {
      setLoadState((current) => (current.status === 'success' ? current : { status: 'error' }))
    }
  }, [familyId])

  useEffect(() => {
    void loadTocData()
  }, [loadTocData])

  const subtitles = useMemo(() => {
    if (loadState.status !== 'success' || !user) {
      return null
    }

    const walletNames = buildDisplayNameById(loadState.wallets, t)
    const defaultWalletName =
      user.defaultWalletId ? walletNames.get(user.defaultWalletId) ?? null : null

    return {
      wallets: walletsSubtitle(
        countSharedWallets(loadState.wallets),
        countPersonalWallets(loadState.wallets),
      ),
      defaultWallet: defaultWalletSubtitle(defaultWalletName),
      income: incomeCategoriesSubtitle(loadState.incomeCategories.length),
      expense: expenseCategoriesSubtitle(
        countExpenseParents(loadState.expenseCategories),
        countExpenseSubcategories(loadState.expenseCategories),
      ),
      members: membersSubtitle(user.memberCount),
      notifications: notificationsSubtitle(
        user.eveningReminderEnabled,
        user.weeklyDigestEnabled,
      ),
      language: languageSubtitle(i18n.language),
    }
  }, [loadState, t, user])

  if (!user) {
    return null
  }

  const profileName = user.firstName ?? '—'
  const profileSubtitle =
    user.role === 'owner'
      ? t('settings.toc.profileOwner', { name: user.budgetName })
      : t('settings.toc.profileMember', { name: user.budgetName })
  const badgeText = t(`settings.roles.${user.role}`, { defaultValue: user.role })
  const badgeClass =
    user.role === 'owner'
      ? 'settings-profile-card__badge settings-profile-card__badge--owner'
      : 'settings-profile-card__badge settings-profile-card__badge--member'

  const rows = [
    {
      path: '/settings/wallets',
      title: t('settings.wallets'),
      subtitle: subtitles?.wallets ?? '—',
      icon: SETTINGS_TOC_ICONS.wallets,
    },
    {
      path: '/settings/default-wallet',
      title: t('settings.toc.defaultWallet'),
      subtitle: subtitles?.defaultWallet ?? '—',
      icon: SETTINGS_TOC_ICONS.defaultWallet,
    },
    {
      path: '/settings/income-categories',
      title: t('settings.categoriesIncome'),
      subtitle: subtitles?.income ?? '—',
      icon: SETTINGS_TOC_ICONS.income,
    },
    {
      path: '/settings/expense-categories',
      title: t('settings.categoriesExpense'),
      subtitle: subtitles?.expense ?? '—',
      icon: SETTINGS_TOC_ICONS.expense,
    },
    {
      path: '/settings/members',
      title: t('settings.toc.members'),
      subtitle: subtitles?.members ?? '—',
      icon: SETTINGS_TOC_ICONS.members,
    },
    {
      path: '/settings/notifications',
      title: t('settings.toc.notifications'),
      subtitle: subtitles?.notifications ?? '—',
      icon: SETTINGS_TOC_ICONS.notifications,
    },
    {
      path: '/settings/language',
      title: t('settings.language'),
      subtitle: subtitles?.language ?? '—',
      icon: SETTINGS_TOC_ICONS.language,
    },
  ]

  return (
    <div className="page-content settings-page">
      <h1 className="settings-page__title">{t('nav.settings')}</h1>

      <div className="settings-profile-card">
        <div className="settings-profile-card__info">
          <div className="settings-profile-card__name">{profileName}</div>
          <div className="settings-profile-card__subtitle">{profileSubtitle}</div>
        </div>
        <div className={badgeClass}>{badgeText}</div>
      </div>

      <div className="settings-toc-list">
        {rows.map((row) => (
          <Link key={row.path} to={row.path} className="settings-toc-row">
            <SettingsTocIcon path={row.icon} />
            <span className="settings-toc-row__content">
              <span className="settings-toc-row__title">{row.title}</span>
              <span className="settings-toc-row__subtitle">{row.subtitle}</span>
            </span>
            <span className="settings-toc-row__chevron" aria-hidden="true">›</span>
          </Link>
        ))}
      </div>

      <p className="settings-page__footer-hint">{t('settings.toc.footerHint')}</p>
    </div>
  )
}
