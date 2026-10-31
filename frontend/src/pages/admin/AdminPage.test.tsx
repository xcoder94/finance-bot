import { describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'

const state = vi.hoisted(() => ({ isAdmin: false }))
vi.mock('../../store/authStore', () => ({
  useAuthStore: (selector: (s: { user: { isAdmin: boolean } }) => unknown) =>
    selector({ user: { isAdmin: state.isAdmin } }),
}))
vi.mock('../../api/admin', async () => {
  const actual = await vi.importActual<typeof import('../../api/admin')>('../../api/admin')
  return { ...actual, fetchAdminOverview: vi.fn(() => new Promise(() => {})), fetchAdminUsers: vi.fn(() => new Promise(() => {})) }
})

import adminRu from '../../i18n/locales/admin.ru.json'
import ru from '../../i18n/locales/ru.json'
import { fetchAdminOverview } from '../../api/admin'
import { adminRedirectTarget } from '../../utils/adminGuard'
import { AdminPage } from './AdminPage'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru, admin: adminRu } },
  lng: 'ru',
  interpolation: { escapeValue: false },
})
const render = () =>
  renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <MemoryRouter initialEntries={['/admin']}>
        <AdminPage />
      </MemoryRouter>
    </I18nextProvider>,
  )

describe('admin route guard', () => {
  it('redirects non-admins to Settings, admins stay', () => {
    expect(adminRedirectTarget(false)).toBe('/settings')
    expect(adminRedirectTarget(true)).toBeNull()
  })
  it('renders nothing and never calls the API for a non-admin', () => {
    state.isAdmin = false
    expect(render()).toBe('')
    expect(fetchAdminOverview).not.toHaveBeenCalled()
  })
  it('renders the screen with the Growth tab for an admin', () => {
    state.isAdmin = true
    const html = render()
    expect(html).toContain('Админка')
    expect(html).toContain('aria-selected="true"')
  })
})
