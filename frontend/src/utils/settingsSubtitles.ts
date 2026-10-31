import { t } from '../i18n/t'
import { sumUnit } from './currencyUnit'
import { groupThousands } from './groupThousands'
export type WalletSubtitleInput = {
  is_personal?: boolean
}

export type ExpenseCategorySubtitleInput = {
  parent_id: string | null
  is_protected?: boolean
}

export function walletsSubtitle(sharedCount: number, personalCount: number): string {
  return t('settings.sub.wallets', { shared: sharedCount, personal: personalCount })
}

export function defaultWalletSubtitle(walletName: string | null | undefined): string {
  return walletName ?? '—'
}

export function formatDefaultWalletRowSubtitle(
  isPersonal: boolean,
  currency: string,
  sharedLabel: string,
  personalLabel: string,
): string {
  const typeLabel = isPersonal ? personalLabel : sharedLabel
  return `${typeLabel} · ${currency}`
}

function formatGroupedAmount(amount: number): string {
  return groupThousands(Math.abs(amount))
}

function formatWalletSettingsAmount(balance: number, currency: string): string {
  const sign = balance < 0 ? '-' : ''
  const grouped = formatGroupedAmount(balance)
  if (currency === 'USD') {
    return `${sign}$${grouped}`
  }
  return `${sign}${grouped} ${sumUnit()}`
}

export function formatWalletSettingsSubtitle(
  currency: string,
  balance: number,
  hasActiveGoal: boolean,
): string {
  const base = `${currency} · ${formatWalletSettingsAmount(balance, currency)}`
  return hasActiveGoal ? `${base} · ${t('settings.sub.goalSuffix')}` : base
}

export function incomeCategoriesSubtitle(count: number): string {
  return t('settings.sub.categories', { count })
}

export function expenseCategoriesSubtitle(parentCount: number, subcategoryCount: number): string {
  return t('settings.sub.expense', {
    parents: parentCount,
    subs: t('settings.sub.subcategories', { count: subcategoryCount }),
  })
}

export function expenseParentRowSubtitle(subcategoryCount: number): string {
  return t('settings.sub.subcategories', { count: subcategoryCount })
}

export function membersSubtitle(memberCount: number): string {
  return t('settings.sub.members', { count: memberCount })
}

export function notificationsSubtitle(eveningEnabled: boolean, weeklyEnabled: boolean): string {
  if (!eveningEnabled && !weeklyEnabled) {
    return t('settings.sub.notifOff')
  }

  const parts: string[] = []
  if (eveningEnabled) {
    parts.push(t('settings.sub.notifEvening'))
  }
  if (weeklyEnabled) {
    parts.push(t('settings.sub.notifWeekly'))
  }
  return parts.join(' · ')
}

export function languageSubtitle(language: string): string {
  return language.startsWith('uz') ? "O'zbekcha" : 'Русский'
}

export function countSharedWallets(wallets: WalletSubtitleInput[]): number {
  return wallets.filter((wallet) => !wallet.is_personal).length
}

export function countPersonalWallets(wallets: WalletSubtitleInput[]): number {
  return wallets.filter((wallet) => wallet.is_personal).length
}

export function countExpenseParents(categories: ExpenseCategorySubtitleInput[]): number {
  return categories.filter((category) => category.parent_id === null).length
}

export function countNonProtectedExpenseParents(
  categories: Array<{ parent_id: string | null; is_protected?: boolean }>,
): number {
  return categories.filter((c) => c.parent_id === null && !c.is_protected).length
}

export function countExpenseSubcategories(categories: ExpenseCategorySubtitleInput[]): number {
  return categories.filter((category) => category.parent_id !== null).length
}
