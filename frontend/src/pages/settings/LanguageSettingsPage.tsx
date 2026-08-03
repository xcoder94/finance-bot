import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { patchMe } from '../../api/me'
import { SettingsEntityGroup } from '../../components/settings/SettingsEntityGroup'
import { SettingsRadioRow } from '../../components/settings/SettingsRadioRow'
import { SettingsSubPageShell } from '../../components/settings/SettingsSubPageShell'
import i18n from '../../i18n'
import { useAuthStore } from '../../store/authStore'

type LanguageOption = {
  code: 'ru' | 'uz'
  label: string
  subtitle?: string
}

const LANGUAGE_OPTIONS: LanguageOption[] = [
  { code: 'ru', label: 'Русский' },
  { code: 'uz', label: 'Oʻzbekcha', subtitle: 'Lotin' },
]

export function LanguageSettingsPage() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const setLocalLanguage = useAuthStore((state) => state.setLocalLanguage)
  const [selectedLanguage, setSelectedLanguage] = useState<'ru' | 'uz'>(
    user?.language?.startsWith('uz') ? 'uz' : 'ru',
  )

  useEffect(() => {
    setSelectedLanguage(user?.language?.startsWith('uz') ? 'uz' : 'ru')
  }, [user?.language])

  const handleSelect = (language: 'ru' | 'uz') => {
    if (language === selectedLanguage) {
      return
    }

    const previousLanguage = selectedLanguage
    setSelectedLanguage(language)
    setLocalLanguage(language)
    void i18n.changeLanguage(language)

    void patchMe({ language }).catch(() => {
      setSelectedLanguage(previousLanguage)
      setLocalLanguage(previousLanguage)
      void i18n.changeLanguage(previousLanguage)
    })
  }

  return (
    <SettingsSubPageShell
      title={t('settings.language')}
      backLabel={t('settings.toc.back')}
      backTo="/settings"
    >
      <SettingsEntityGroup
        title={t('settings.languageScreen.groupTitle')}
        note={t('settings.languageScreen.note')}
      >
        <div className="category-picker">
          {LANGUAGE_OPTIONS.map((option) => (
            <SettingsRadioRow
              key={option.code}
              label={option.label}
              subtitle={option.subtitle}
              selected={selectedLanguage === option.code}
              onSelect={() => handleSelect(option.code)}
            />
          ))}
        </div>
      </SettingsEntityGroup>
    </SettingsSubPageShell>
  )
}
