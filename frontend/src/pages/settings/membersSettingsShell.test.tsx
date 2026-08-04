import { describe, expect, it } from 'vitest'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { I18nextProvider } from 'react-i18next'

import ru from '../../i18n/locales/ru.json'
import { MembersSettingsBody } from './MembersSettingsShellPage'
import type { MemberResponse } from '../../api/members'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  fallbackLng: 'ru',
  interpolation: { escapeValue: false },
})

const FIXTURE_MEMBERS: MemberResponse[] = [
  {
    id: 'owner-id',
    first_name: 'Рустам',
    username: null,
    role: 'owner',
  },
  {
    id: 'member-id',
    first_name: 'Дилноза',
    username: null,
    role: 'member',
  },
]

function renderMembersBody(isOwner: boolean, currentUserId: string) {
  return renderToStaticMarkup(
  <I18nextProvider i18n={testI18n}>
    <MembersSettingsBody
      members={FIXTURE_MEMBERS}
      currentUserId={currentUserId}
      isOwner={isOwner}
    />
  </I18nextProvider>,
  )
}

describe('MembersSettingsBody', () => {
  it('renders read-only member list with group title', () => {
    const html = renderMembersBody(true, 'owner-id')
    expect(html).toContain('2 из 4 · вы владелец')
    expect(html).toContain('Рустам')
    expect(html).toContain('Дилноза')
    expect(html).toContain('Владелец · вы')
    expect(html).toContain('Участник')
  })

  it('has no invite link button or shell actions', () => {
    const html = renderMembersBody(true, 'owner-id')
    expect(html).not.toContain('Ссылка-приглашение')
    expect(html).not.toContain('settings-sub-page__action')
    expect(html).not.toContain('settings-sub-page__danger')
    expect(html).not.toContain('Скопировать')
    expect(html).not.toContain('Выйти из бюджета')
    expect(html).not.toContain('settings-swipe-row__delete')
  })

  it('shows member group title for non-owner viewer', () => {
    const html = renderMembersBody(false, 'member-id')
    expect(html).toContain('2 из 4 · вы участник')
    expect(html).toContain('Участник · вы')
  })
})
