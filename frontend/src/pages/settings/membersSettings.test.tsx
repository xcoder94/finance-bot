import { describe, expect, it } from 'vitest'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter } from 'react-router-dom'

import ru from '../../i18n/locales/ru.json'
import { LIMIT_MEMBERS } from '../../constants/entityLimits'
import { InviteLinkSheet } from '../../components/settings/InviteLinkSheet'
import { MembersSettingsBody, MembersSettingsPageChrome } from './MembersSettingsPage'
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
    created_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 'member-id',
    first_name: 'Дилноза',
    username: null,
    role: 'member',
    created_at: '2026-03-12T10:00:00Z',
  },
]

function renderMembersBody(isOwner: boolean, currentUserId: string) {
  return renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <MembersSettingsBody
        members={FIXTURE_MEMBERS}
        currentUserId={currentUserId}
        isOwner={isOwner}
        onOpenMember={() => undefined}
      />
    </I18nextProvider>,
  )
}

function renderInviteSheet(atLimit: boolean) {
  return renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <InviteLinkSheet
        open
        inviteLink="t.me/chontak_bot?start=inv_test"
        atLimit={atLimit}
        loading={false}
        reissuing={false}
        onClose={() => undefined}
        onCopy={() => undefined}
        onReissue={() => undefined}
      />
    </I18nextProvider>,
  )
}

describe('MembersSettingsBody', () => {
  it('renders owner list with join dates and chevrons', () => {
    const html = renderMembersBody(true, 'owner-id')
    expect(html).toContain('2 из 4 · вы владелец')
    expect(html).toContain('Рустам')
    expect(html).toContain('Дилноза')
    expect(html).toContain('Владелец · вы')
    expect(html).toContain('Участник · с 12.03.2026')
    expect(html).toContain('settings-swipe-row__chevron')
  })

  it('renders member group title for non-owner viewer', () => {
    const html = renderMembersBody(false, 'member-id')
    expect(html).toContain('2 из 4 · вы участник')
    expect(html).toContain('Участник · вы')
  })

  it('shows owner note for owner viewer', () => {
    const html = renderMembersBody(true, 'owner-id')
    expect(html).toContain('Передача прав владения и удаление участника')
    expect(html).not.toContain('Приглашать новых может только владелец')
  })

  it('shows member note for non-owner viewer', () => {
    const html = renderMembersBody(false, 'member-id')
    expect(html).toContain('Приглашать новых может только владелец')
  })
})

describe('MembersSettingsPage chrome', () => {
  it('shows invite action for owner and no exit control', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <I18nextProvider i18n={testI18n}>
          <MembersSettingsPageChrome isOwner>
            <div />
          </MembersSettingsPageChrome>
        </I18nextProvider>
      </MemoryRouter>,
    )
    expect(html).toContain('Ссылка-приглашение')
    expect(html).toContain('settings-sub-page__action')
    expect(html).not.toContain('Выйти из бюджета')
    expect(html).not.toContain('settings-sub-page__danger')
  })

  it('shows exit danger for member and no invite action', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <I18nextProvider i18n={testI18n}>
          <MembersSettingsPageChrome isOwner={false}>
            <div />
          </MembersSettingsPageChrome>
        </I18nextProvider>
      </MemoryRouter>,
    )
    expect(html).toContain('Выйти из бюджета')
    expect(html).toContain('settings-sub-page__danger')
    expect(html).not.toContain('Ссылка-приглашение')
    expect(html).not.toContain('settings-sub-page__action')
  })
})

describe('InviteLinkSheet', () => {
  it('shows member limit hint and disables copy at four members', () => {
    const html = renderInviteSheet(true)
    expect(html).toContain(LIMIT_MEMBERS)
    expect(html).toContain('form-sheet-primary')
    expect(html).toMatch(/disabled/)
  })

  it('allows copy when below member limit', () => {
    const html = renderInviteSheet(false)
    expect(html).not.toContain(LIMIT_MEMBERS)
    expect(html).toContain('Скопировать')
    expect(html).toContain('Перевыпустить')
  })
})
