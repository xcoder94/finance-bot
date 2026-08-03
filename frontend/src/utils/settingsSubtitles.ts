export type WalletSubtitleInput = {
  is_personal?: boolean
}

export type ExpenseCategorySubtitleInput = {
  parent_id: string | null
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

export function notificationsSubtitle(): string {
  return 'Выключены'
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

export function countExpenseSubcategories(categories: ExpenseCategorySubtitleInput[]): number {
  return categories.filter((category) => category.parent_id !== null).length
}
