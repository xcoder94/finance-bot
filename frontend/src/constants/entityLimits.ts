/** Product ceilings — must match backend `app.services.entity_limits` wording. */

export const SHARED_WALLET_LIMIT = 10
export const PERSONAL_WALLET_LIMIT = 5
export const PARENT_CATEGORY_LIMIT = 8
export const INCOME_CATEGORY_LIMIT = 8
export const SUBCATEGORY_LIMIT = 8
export const MEMBER_LIMIT = 4
export const ENTITY_NAME_MAX = 30

export const LIMIT_SHARED_WALLETS =
  'Больше 10 общих кошельков создать нельзя. Удалите ненужный — место освободится.'

export const LIMIT_PERSONAL_WALLETS =
  'Больше 5 личных кошельков создать нельзя. Удалите ненужный — место освободится.'

export const LIMIT_EXPENSE_PARENTS =
  'Больше 8 категорий расходов создать нельзя. Удалите ненужную — место освободится.'

export const LIMIT_INCOME_CATEGORIES =
  'Больше 8 категорий доходов создать нельзя. Удалите ненужную — место освободится.'

export const LIMIT_MEMBERS =
  'В семейном бюджете уже 4 участника — это предел.'

export function limitSubcategories(parentName: string): string {
  return `В категории «${parentName}» уже 8 подкатегорий — это предел. Удалите ненужную, чтобы добавить новую.`
}
