import { type ComponentProps, type ReactElement, type ReactNode, isValidElement } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { I18nextProvider } from 'react-i18next'

import { LIMIT_PERSONAL_WALLETS } from '../../constants/entityLimits'
import ru from '../../i18n/locales/ru.json'
import { WalletFormSheet } from './WalletFormSheet'

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

function renderWalletForm(props: Partial<ComponentProps<typeof WalletFormSheet>> = {}) {
  capturedFormSheets.length = 0
  return renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <WalletFormSheet
        open
        mode="create"
        wallet={null}
        sharedWalletCount={0}
        personalWalletCount={5}
        canPickWalletType={false}
        editable
        onClose={() => undefined}
        onSave={async () => undefined}
        currencyPickerOpen={false}
        onCurrencyPickerOpenChange={() => undefined}
        walletTypePickerOpen={false}
        onWalletTypePickerOpenChange={() => undefined}
        {...props}
      />
    </I18nextProvider>,
  )
}

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

describe('WalletFormSheet create limits', () => {
  it('shows personal limit hint when member is at 5 personal wallets', () => {
    const html = renderWalletForm({ personalWalletCount: 5, canPickWalletType: false })
    expect(html).toContain(LIMIT_PERSONAL_WALLETS)
  })

  it('shows member create intro when type is locked to personal', () => {
    const html = renderWalletForm({ canPickWalletType: false })
    expect(html).toContain('Вы можете создать только личный кошелёк.')
  })

  it('shows type field as personal for member create', () => {
    const html = renderWalletForm({ canPickWalletType: false })
    expect(html).toContain('Тип')
    expect(html).toContain('Личный')
  })
})

const editWallet = {
  id: 'wallet-1',
  name: 'Наличные',
  currency: 'UZS',
  translation_key: null,
  balance: 0,
  is_personal: true,
  transaction_count: 0,
  has_active_goal: false,
} as const

describe('WalletFormSheet edit delete', () => {
  beforeEach(() => {
    capturedFormSheets.length = 0
  })

  it('shows delete button in edit mode when onDelete is provided', () => {
    const html = renderWalletForm({
      mode: 'edit',
      wallet: editWallet,
      onDelete: () => undefined,
    })
    expect(html).toContain('form-sheet-danger-button')
    expect(html).toContain('Удалить')
  })

  it('hides delete button in create mode', () => {
    const html = renderWalletForm({
      mode: 'create',
      wallet: null,
      onDelete: () => undefined,
    })
    expect(html).not.toContain('form-sheet-danger-button')
  })

  it('hides delete button in edit mode without onDelete', () => {
    const html = renderWalletForm({
      mode: 'edit',
      wallet: editWallet,
    })
    expect(html).not.toContain('form-sheet-danger-button')
  })

  it('invokes onDelete when danger button is clicked in edit mode', () => {
    const onDelete = vi.fn()
    renderWalletForm({
      mode: 'edit',
      wallet: editWallet,
      onDelete,
    })
    invokeDangerClick(getCapturedDanger())
    expect(onDelete).toHaveBeenCalledOnce()
  })
})
