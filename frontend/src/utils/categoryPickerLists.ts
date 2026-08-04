import type { ExpenseCategory } from '../api/transactions'
import { filterUncategorizedCategories } from './transactionFormFields'

export function getExpensePickerParentCategories(
  categories: ExpenseCategory[],
): ExpenseCategory[] {
  return filterUncategorizedCategories(
    categories.filter((category) => category.parent_id === null),
  )
}

export function getExpensePickerSubcategories(
  categories: ExpenseCategory[],
  parentId: string,
): ExpenseCategory[] {
  return filterUncategorizedCategories(
    categories.filter((category) => category.parent_id === parentId),
  )
}
