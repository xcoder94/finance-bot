import { type ComponentProps } from 'react'
import { describe, expect, it } from 'vitest'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { I18nextProvider } from 'react-i18next'

import { LIMIT_PERSONAL_WALLETS } from '../../constants/entityLimits'
import ru from '../../i18n/locales/ru.json'
import { WalletFormSheet } from './WalletFormSheet'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  fallbackLng: 'ru',
  interpolation: { escapeValue: false },
})

function renderWalletForm(props: Partial<ComponentProps<typeof WalletFormSheet>> = {}) {
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
