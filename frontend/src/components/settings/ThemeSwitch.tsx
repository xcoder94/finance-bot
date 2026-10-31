import { useTranslation } from 'react-i18next'

import { useThemeStore, type Theme } from '../../store/themeStore'

const OPTIONS: Theme[] = ['dark', 'light']

export function ThemeSwitch() {
  const { t } = useTranslation()
  const theme = useThemeStore((s) => s.theme)
  const setTheme = useThemeStore((s) => s.setTheme)

  return (
    <div className="theme-switch" role="radiogroup" aria-label={t('settings.theme')}>
      {OPTIONS.map((option) => (
        <button
          key={option}
          type="button"
          role="radio"
          aria-checked={theme === option}
          className={`theme-switch__option${theme === option ? ' theme-switch__option--on' : ''}`}
          onClick={() => setTheme(option)}
        >
          {t(option === 'dark' ? 'settings.themeDark' : 'settings.themeLight')}
        </button>
      ))}
    </div>
  )
}
