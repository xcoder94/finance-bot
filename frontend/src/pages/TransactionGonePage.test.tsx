import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppRoot } from '@telegram-apps/telegram-ui'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter } from 'react-router-dom'

import ru from '../i18n/locales/ru.json'
import { TransactionGonePage } from './TransactionGonePage'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('TransactionGonePage', () => {
  beforeEach(async () => {
    mockNavigate.mockReset()
    await i18n.use(initReactI18next).init({
      lng: 'ru',
      resources: { ru: { translation: ru } },
    })
  })

  it('shows the gone message and a home button', () => {
    const html = renderToStaticMarkup(
      <AppRoot>
        <I18nextProvider i18n={i18n}>
          <MemoryRouter>
            <TransactionGonePage />
          </MemoryRouter>
        </I18nextProvider>
      </AppRoot>,
    )

    expect(html).toContain('Запись больше не существует.')
    expect(html).toContain('На главную')
  })
})
