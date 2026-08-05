import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { I18nextProvider } from 'react-i18next'

import { patchMe } from '../../api/me'
import ru from '../../i18n/locales/ru.json'
import { notificationsSubtitle } from '../../utils/settingsSubtitles'
import { NotificationsSettingsBody } from './NotificationsSettingsShellPage'

const mockPatchMe = vi.mocked(patchMe)
const mockSetLocalEveningReminder = vi.fn()
const mockSetLocalWeeklyDigest = vi.fn()

const authState = {
  user: {
    eveningReminderEnabled: true,
    weeklyDigestEnabled: false,
  },
  setLocalEveningReminder: mockSetLocalEveningReminder,
  setLocalWeeklyDigest: mockSetLocalWeeklyDigest,
}

const capturedToggleRows: Array<{
  name: string
  enabled: boolean
  onToggle: () => void
}> = []

vi.mock('../../api/me', () => ({
  patchMe: vi.fn(),
}))

vi.mock('../../store/authStore', () => ({
  useAuthStore: (selector: (state: typeof authState) => unknown) => selector(authState),
}))

vi.mock('../../components/settings/SettingsToggleRow', () => ({
  SettingsToggleRow: ({
    name,
    subtitle,
    enabled,
    onToggle,
  }: {
    name: string
    subtitle?: string
    enabled: boolean
    onToggle: () => void
  }) => {
    capturedToggleRows.push({ name, enabled, onToggle })
    return (
      <button
        type="button"
        className="settings-toggle-row"
        role="switch"
        aria-checked={enabled}
        onClick={onToggle}
      >
        <span className="settings-toggle-row__text">
          <span className="settings-toggle-row__name">{name}</span>
          {subtitle ? <span className="settings-toggle-row__subtitle">{subtitle}</span> : null}
        </span>
        <span
          className={[
            'settings-toggle-row__track',
            enabled ? 'settings-toggle-row__track--on' : 'settings-toggle-row__track--off',
          ].join(' ')}
          aria-hidden="true"
        >
          <span className="settings-toggle-row__knob" />
        </span>
      </button>
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

function renderNotificationsBody() {
  capturedToggleRows.length = 0
  return renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <NotificationsSettingsBody />
    </I18nextProvider>,
  )
}

function findToggleRow(name: string) {
  const row = capturedToggleRows.find((entry) => entry.name === name)
  expect(row).toBeDefined()
  return row!
}

describe('NotificationsSettingsBody', () => {
  beforeEach(() => {
    authState.user.eveningReminderEnabled = true
    authState.user.weeklyDigestEnabled = false
    mockSetLocalEveningReminder.mockReset()
    mockSetLocalWeeklyDigest.mockReset()
    mockPatchMe.mockReset()
    mockSetLocalEveningReminder.mockImplementation((value: boolean) => {
      authState.user.eveningReminderEnabled = value
    })
    mockSetLocalWeeklyDigest.mockImplementation((value: boolean) => {
      authState.user.weeklyDigestEnabled = value
    })
    mockPatchMe.mockResolvedValue({
      id: 'user-1',
      telegramId: 123456789,
      familyBudgetId: 'family-1',
      role: 'owner',
      firstName: 'Тест',
      username: 'testuser',
      language: 'ru',
      budgetName: 'Семья',
      memberCount: 1,
      defaultWalletId: null,
      eveningReminderEnabled: true,
      weeklyDigestEnabled: false,
    })
  })

  it('renders static notification rows from design copy', () => {
    const html = renderNotificationsBody()
    expect(html).toContain('Напоминание вечером')
    expect(html).toContain('Если за день не было ни одной записи, 21:00')
    expect(html).toContain('Итоги недели')
    expect(html).toContain('Каждый понедельник в 10:00')
    expect(html).toContain('Два независимых переключателя')
  })

  it('renders exactly two toggle switches with correct checked state', () => {
    const html = renderNotificationsBody()
    const switches = html.match(/role="switch"/g) ?? []
    expect(switches).toHaveLength(2)
    expect(html).toContain('aria-checked="true"')
    expect(html).toContain('aria-checked="false"')
    expect(html).toContain('settings-toggle-row__track--on')
    expect(html).toContain('settings-toggle-row__track--off')
  })

  it('exposes exactly two switches and no goal-achievement switch', () => {
    const html = renderNotificationsBody()
    expect(html.match(/role="switch"/g) ?? []).toHaveLength(2)
    expect(html).not.toContain('Достижение цели')
    expect(html).not.toContain('goal')
  })

  describe('notifications TOC subtitle contract (notificationsSubtitle)', () => {
    it('both on → Напоминание вечером · Итоги недели', () => {
      expect(notificationsSubtitle(true, true)).toBe('Напоминание вечером · Итоги недели')
    })

    it('only evening → Напоминание вечером', () => {
      expect(notificationsSubtitle(true, false)).toBe('Напоминание вечером')
    })

    it('only weekly → Итоги недели', () => {
      expect(notificationsSubtitle(false, true)).toBe('Итоги недели')
    })

    it('both off → Выключены', () => {
      expect(notificationsSubtitle(false, false)).toBe('Выключены')
    })
  })

  describe('independent switch toggles', () => {
    it('toggling evening calls patchMe with only evening_reminder_enabled', () => {
      renderNotificationsBody()
      findToggleRow('Напоминание вечером').onToggle()

      expect(mockPatchMe).toHaveBeenCalledOnce()
      expect(mockPatchMe).toHaveBeenCalledWith({ evening_reminder_enabled: false })
      expect(mockSetLocalEveningReminder).toHaveBeenCalledWith(false)
      expect(mockSetLocalWeeklyDigest).not.toHaveBeenCalled()
      expect(authState.user.weeklyDigestEnabled).toBe(false)

      const html = renderNotificationsBody()
      expect(html).toContain('aria-checked="false"')
      expect(
        notificationsSubtitle(
          authState.user.eveningReminderEnabled,
          authState.user.weeklyDigestEnabled,
        ),
      ).toBe('Выключены')
    })

    it('toggling weekly calls patchMe with only weekly_digest_enabled', () => {
      renderNotificationsBody()
      findToggleRow('Итоги недели').onToggle()

      expect(mockPatchMe).toHaveBeenCalledOnce()
      expect(mockPatchMe).toHaveBeenCalledWith({ weekly_digest_enabled: true })
      expect(mockSetLocalWeeklyDigest).toHaveBeenCalledWith(true)
      expect(mockSetLocalEveningReminder).not.toHaveBeenCalled()
      expect(authState.user.eveningReminderEnabled).toBe(true)

      const html = renderNotificationsBody()
      expect(html.match(/aria-checked="true"/g) ?? []).toHaveLength(2)
      expect(
        notificationsSubtitle(
          authState.user.eveningReminderEnabled,
          authState.user.weeklyDigestEnabled,
        ),
      ).toBe('Напоминание вечером · Итоги недели')
    })
  })
})
