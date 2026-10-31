/** Product ceilings — must match backend `app.services.entity_limits` wording. */
import { t } from '../i18n/t'

export const SHARED_WALLET_LIMIT = 10
export const PERSONAL_WALLET_LIMIT = 5
export const PARENT_CATEGORY_LIMIT = 8
export const INCOME_CATEGORY_LIMIT = 8
export const SUBCATEGORY_LIMIT = 8
export const MEMBER_LIMIT = 4
export const ENTITY_NAME_MAX = 30

export const limitSharedWallets = (): string => t('limits.sharedWallets')
export const limitPersonalWallets = (): string => t('limits.personalWallets')
export const limitExpenseParents = (): string => t('limits.expenseParents')
export const limitIncomeCategories = (): string => t('limits.incomeCategories')
export const limitMembers = (): string => t('limits.members')

export function limitSubcategories(parentName: string): string {
  return t('limits.subcategories', { parent: parentName })
}
