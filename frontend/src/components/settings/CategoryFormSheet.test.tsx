import { type ComponentProps, type ReactElement, type ReactNode, isValidElement } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { I18nextProvider } from 'react-i18next'

import ru from '../../i18n/locales/ru.json'
import { CategoryFormSheet } from './CategoryFormSheet'

type CapturedFormSheet = { danger?: ReactNode }

const capturedFormSheets: CapturedFormSheet[] = []

vi.mock('../forms/FormSheet', () => ({
  FormSheet: ({
    danger,
    intro,
    children,
  }: {
    danger?: ReactNode
    intro?: string
    children?: ReactNode
  }) => {
    capturedFormSheets.push({ danger })
    return (
      <div className="form-sheet-mock">
        {intro ? <p className="form-sheet-intro">{intro}</p> : null}
        {children}
        {danger ? <div className="form-sheet-danger">{danger}</div> : null}
      </div>
    )
  },
}))

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  fallbackLng: 'ru',
  interpolation: { escapeValue: false },
})

function renderCategoryForm(props: Partial<ComponentProps<typeof CategoryFormSheet>> = {}) {
  capturedFormSheets.length = 0
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

type DangerButtonProps = { onClick?: () => void }

function getCapturedDanger(): ReactNode {
  const entry = capturedFormSheets.find((sheet) => sheet.danger != null)
  expect(entry).toBeDefined()
  return entry!.danger
}

function invokeDangerClick(danger: ReactNode) {
  expect(isValidElement(danger)).toBe(true)
  const button = danger as ReactElement<DangerButtonProps>
  expect(button.props.onClick).toBeTypeOf('function')
  button.props.onClick!()
}

describe('CategoryFormSheet edit delete — income', () => {
  beforeEach(() => {
    capturedFormSheets.length = 0
  })

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

  it('invokes onDelete when danger button is clicked in edit mode', () => {
    const onDelete = vi.fn()
    renderCategoryForm({
      mode: 'edit',
      kind: 'income',
      category: editCategory,
      onDelete,
    })
    invokeDangerClick(getCapturedDanger())
    expect(onDelete).toHaveBeenCalledOnce()
  })
})

describe('CategoryFormSheet edit delete — expense-subcategory', () => {
  beforeEach(() => {
    capturedFormSheets.length = 0
  })

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

  it('hides delete button in create mode', () => {
    const html = renderCategoryForm({
      mode: 'create',
      kind: 'expense-subcategory',
      category: null,
      parentName: 'Еда',
      onDelete: () => undefined,
    })
    expect(html).not.toContain('form-sheet-danger-button')
  })

  it('hides delete button in edit mode without onDelete', () => {
    const html = renderCategoryForm({
      mode: 'edit',
      kind: 'expense-subcategory',
      category: editCategory,
      parentName: 'Еда',
    })
    expect(html).not.toContain('form-sheet-danger-button')
  })

  it('invokes onDelete when danger button is clicked in edit mode', () => {
    const onDelete = vi.fn()
    renderCategoryForm({
      mode: 'edit',
      kind: 'expense-subcategory',
      category: editCategory,
      parentName: 'Еда',
      onDelete,
    })
    invokeDangerClick(getCapturedDanger())
    expect(onDelete).toHaveBeenCalledOnce()
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
