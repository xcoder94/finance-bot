import { useTranslation } from 'react-i18next'

import { useThemeStore, type ThemePreference } from '../../store/themeStore'

const OPTIONS: ThemePreference[] = ['system', 'light', 'dark']
const LABELS: Record<ThemePreference, string> = {
  system: 'settings.themeSystem',
  light: 'settings.themeLight',
  dark: 'settings.themeDark',
}

export function ThemeSwitch() {
  const { t } = useTranslation()
  const preference = useThemeStore((s) => s.preference)
  const setPreference = useThemeStore((s) => s.setPreference)

  return (
    <div className="theme-switch" role="radiogroup" aria-label={t('settings.theme')}>
      {OPTIONS.map((option) => (
        <button
          key={option}
          type="button"
          role="radio"
          aria-checked={preference === option}
          className={`theme-switch__option${preference === option ? ' theme-switch__option--on' : ''}`}
          onClick={() => setPreference(option)}
        >
          {t(LABELS[option])}
        </button>
      ))}
    </div>
  )
}
