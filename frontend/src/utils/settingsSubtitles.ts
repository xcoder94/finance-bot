export type WalletSubtitleInput = {
  is_personal?: boolean
}

export type ExpenseCategorySubtitleInput = {
  parent_id: string | null
  is_protected?: boolean
}

export function walletsSubtitle(sharedCount: number, personalCount: number): string {
  return `${sharedCount} общих · ${personalCount} личных`
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
  return Math.abs(amount).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

function formatWalletSettingsAmount(balance: number, currency: string): string {
  const sign = balance < 0 ? '-' : ''
  const grouped = formatGroupedAmount(balance)
  if (currency === 'USD') {
    return `${sign}$${grouped}`
  }
  return `${sign}${grouped} сум`
}

export function formatWalletSettingsSubtitle(
  currency: string,
  balance: number,
  hasActiveGoal: boolean,
): string {
  const base = `${currency} · ${formatWalletSettingsAmount(balance, currency)}`
  return hasActiveGoal ? `${base} · цель` : base
}

function categoryWordRu(count: number): string {
  const abs = Math.abs(count)
  const mod10 = abs % 10
  const mod100 = abs % 100

  if (mod100 >= 11 && mod100 <= 14) {
    return 'категорий'
  }
  if (mod10 === 1) {
    return 'категория'
  }
  if (mod10 >= 2 && mod10 <= 4) {
    return 'категории'
  }
  return 'категорий'
}

export function incomeCategoriesSubtitle(count: number): string {
  return `${count} ${categoryWordRu(count)}`
}

function subcategoryWordRu(count: number): string {
  const abs = Math.abs(count)
  const mod10 = abs % 10
  const mod100 = abs % 100

  if (mod100 >= 11 && mod100 <= 14) {
    return 'подкатегорий'
  }
  if (mod10 === 1) {
    return 'подкатегория'
  }
  if (mod10 >= 2 && mod10 <= 4) {
    return 'подкатегории'
  }
  return 'подкатегорий'
}

export function expenseCategoriesSubtitle(parentCount: number, subcategoryCount: number): string {
  return `${parentCount} родительских · ${subcategoryCount} ${subcategoryWordRu(subcategoryCount)}`
}

export function expenseParentRowSubtitle(subcategoryCount: number): string {
  return `${subcategoryCount} ${subcategoryWordRu(subcategoryCount)}`
}

export function membersSubtitle(memberCount: number): string {
  return `${memberCount} из 4`
}

export function notificationsSubtitle(eveningEnabled: boolean, weeklyEnabled: boolean): string {
  if (!eveningEnabled && !weeklyEnabled) {
    return 'Выключены'
  }

  const parts: string[] = []
  if (eveningEnabled) {
    parts.push('Напоминание вечером')
  }
  if (weeklyEnabled) {
    parts.push('Итоги недели')
  }
  return parts.join(' · ')
}

export function languageSubtitle(language: string): string {
  return language.startsWith('uz') ? 'Oʻzbekcha' : 'Русский'
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
