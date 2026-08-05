import { type ComponentProps } from 'react'
import { describe, expect, it } from 'vitest'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { I18nextProvider } from 'react-i18next'

import ru from '../../i18n/locales/ru.json'
import { CategoryFormSheet } from './CategoryFormSheet'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  fallbackLng: 'ru',
  interpolation: { escapeValue: false },
})

function renderCategoryForm(props: Partial<ComponentProps<typeof CategoryFormSheet>> = {}) {
  return renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <CategoryFormSheet
        open
        mode="create"
        kind="income"
        category={null}
        atLimit={false}
        editable
        onClose={() => undefined}
        onSave={async () => undefined}
        {...props}
      />
    </I18nextProvider>,
  )
}

const editCategory = { name: 'Зарплата' }

describe('CategoryFormSheet edit delete — income', () => {
  it('shows delete button in edit mode when onDelete is provided', () => {
    const html = renderCategoryForm({
      mode: 'edit',
      kind: 'income',
      category: editCategory,
      onDelete: () => undefined,
    })
    expect(html).toContain('form-sheet-danger-button')
    expect(html).toContain('Удалить')
  })

  it('hides delete button in create mode', () => {
    const html = renderCategoryForm({
      mode: 'create',
      kind: 'income',
      category: null,
      onDelete: () => undefined,
    })
    expect(html).not.toContain('form-sheet-danger-button')
  })

  it('hides delete button in edit mode without onDelete', () => {
    const html = renderCategoryForm({
      mode: 'edit',
      kind: 'income',
      category: editCategory,
    })
    expect(html).not.toContain('form-sheet-danger-button')
  })
})

describe('CategoryFormSheet edit delete — expense-subcategory', () => {
  it('shows delete button in edit mode when onDelete is provided', () => {
    const html = renderCategoryForm({
      mode: 'edit',
      kind: 'expense-subcategory',
      category: editCategory,
      parentName: 'Еда',
      onDelete: () => undefined,
    })
    expect(html).toContain('form-sheet-danger-button')
    expect(html).toContain('Удалить')
  })
})

describe('CategoryFormSheet edit delete — expense-parent', () => {
  it('never shows delete button even with onDelete', () => {
    const html = renderCategoryForm({
      mode: 'edit',
      kind: 'expense-parent',
      category: editCategory,
      onDelete: () => undefined,
    })
    expect(html).not.toContain('form-sheet-danger-button')
  })
})
