import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { ExpenseCategory, IncomeCategory } from '../../api/transactions'
import { getDisplayName } from '../../utils/getDisplayName'
import {
  buildExpenseCategoryDisplayLabel,
  filterUncategorizedCategories,
} from '../../utils/transactionFormFields'
import { useNativeBackButtonOverlay } from '../nativeBackButtonContext'
import { FormSheet } from './FormSheet'

type ExpenseCategorySelection = {
  categoryId: string
  parentId: string
  subcategoryId: string | null
  label: string
}

type CategoryPickerSheetProps =
  | {
      variant: 'expense'
      open: boolean
      categories: ExpenseCategory[]
      selectedCategoryId: string | null
      onClose: () => void
      onSelect: (selection: ExpenseCategorySelection) => void
    }
  | {
      variant: 'income'
      open: boolean
      categories: IncomeCategory[]
      selectedCategoryId: string | null
      onClose: () => void
      onSelect: (selection: { categoryId: string; label: string }) => void
    }

function getTopLevelExpenseCategories(categories: ExpenseCategory[]): ExpenseCategory[] {
  return filterUncategorizedCategories(categories.filter((category) => category.parent_id === null))
}

function getExpenseSubcategories(
  categories: ExpenseCategory[],
  parentId: string,
): ExpenseCategory[] {
  return filterUncategorizedCategories(
    categories.filter((category) => category.parent_id === parentId),
  )
}

export function CategoryPickerSheet(props: CategoryPickerSheetProps) {
  const { open, onClose } = props
  const { t } = useTranslation()
  const [expandedParentId, setExpandedParentId] = useState<string | null>(null)

  const incomeCategories = useMemo(() => {
    if (props.variant !== 'income') {
      return []
    }
    return filterUncategorizedCategories(props.categories)
  }, [props])

  const expenseParents = useMemo(() => {
    if (props.variant !== 'expense') {
      return []
    }
    return getTopLevelExpenseCategories(props.categories)
  }, [props])

  const resolveExpenseSelection = (
    parent: ExpenseCategory,
    subcategory: ExpenseCategory | null,
  ): ExpenseCategorySelection => {
    const parentName = getDisplayName(parent, t)
    if (subcategory) {
      const subcategoryName = getDisplayName(subcategory, t)
      return {
        categoryId: subcategory.id,
        parentId: parent.id,
        subcategoryId: subcategory.id,
        label: buildExpenseCategoryDisplayLabel(parentName, subcategoryName),
      }
    }

    return {
      categoryId: parent.id,
      parentId: parent.id,
      subcategoryId: null,
      label: parentName,
    }
  }

  const title =
    props.variant === 'expense'
      ? t('categoryPicker.expenseTitle')
      : t('categoryPicker.incomeTitle')

  const intro = props.variant === 'expense' ? t('categoryPicker.expenseIntro') : undefined

  useNativeBackButtonOverlay(open, onClose)

  return (
    <FormSheet open={open} title={title} intro={intro} onClose={onClose} showPrimary={false}>
      <div className="category-picker">
        {props.variant === 'income'
          ? incomeCategories.map((category) => {
              const label = getDisplayName(category, t)
              const selected = props.selectedCategoryId === category.id

              return (
                <button
                  key={category.id}
                  type="button"
                  className="category-picker__row"
                  onClick={() => {
                    props.onSelect({ categoryId: category.id, label })
                    onClose()
                  }}
                >
                  <span
                    className={[
                      'category-picker__radio',
                      selected ? 'category-picker__radio--selected' : '',
                    ]
                      .filter(Boolean)
                      .join(' ')}
                    aria-hidden="true"
                  >
                    <span className="category-picker__radio-dot" />
                  </span>
                  <span className="category-picker__name">{label}</span>
                </button>
              )
            })
          : expenseParents.map((parent) => {
              const parentName = getDisplayName(parent, t)
              const expanded = expandedParentId === parent.id
              const subcategories = getExpenseSubcategories(props.categories, parent.id)
              return (
                <div key={parent.id} className="category-picker__group">
                  <button
                    type="button"
                    className={[
                      'category-picker__row',
                      'category-picker__row--parent',
                      expanded ? 'category-picker__row--expanded' : '',
                    ]
                      .filter(Boolean)
                      .join(' ')}
                    onClick={() =>
                      setExpandedParentId((current) => (current === parent.id ? null : parent.id))
                    }
                  >
                    <span className="category-picker__name">{parentName}</span>
                    <span className="category-picker__chevron" aria-hidden="true">
                      {expanded ? '⌄' : '›'}
                    </span>
                  </button>

                  {expanded ? (
                    <>
                      <button
                        type="button"
                        className="category-picker__row category-picker__row--nested"
                        onClick={() => {
                          props.onSelect(resolveExpenseSelection(parent, null))
                          onClose()
                        }}
                      >
                        <span
                          className={[
                            'category-picker__radio',
                            props.selectedCategoryId === parent.id
                              ? 'category-picker__radio--selected'
                              : '',
                          ]
                            .filter(Boolean)
                            .join(' ')}
                          aria-hidden="true"
                        >
                          <span className="category-picker__radio-dot" />
                        </span>
                        <span className="category-picker__name category-picker__name--muted">
                          {t('categoryPicker.parentOnly', { parent: parentName })}
                        </span>
                      </button>

                      {subcategories.map((subcategory) => {
                        const subcategoryName = getDisplayName(subcategory, t)
                        const selected = props.selectedCategoryId === subcategory.id

                        return (
                          <button
                            key={subcategory.id}
                            type="button"
                            className="category-picker__row category-picker__row--nested"
                            onClick={() => {
                              props.onSelect(resolveExpenseSelection(parent, subcategory))
                              onClose()
                            }}
                          >
                            <span
                              className={[
                                'category-picker__radio',
                                selected ? 'category-picker__radio--selected' : '',
                              ]
                                .filter(Boolean)
                                .join(' ')}
                              aria-hidden="true"
                            >
                              <span className="category-picker__radio-dot" />
                            </span>
                            <span className="category-picker__name">{subcategoryName}</span>
                          </button>
                        )
                      })}
                    </>
                  ) : null}
                </div>
              )
            })}
      </div>
    </FormSheet>
  )
}
