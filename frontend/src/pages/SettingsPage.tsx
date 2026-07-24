import { Cell, Section, SegmentedControl, Text, Title } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import { ExpenseCategoriesSection } from '../components/settings/ExpenseCategoriesSection'
import { IncomeCategoriesSection } from '../components/settings/IncomeCategoriesSection'
import { WalletsSection } from '../components/settings/WalletsSection'
import i18n from '../i18n'
import { useAuthStore } from '../store/authStore'

const SUPPORTED_LANGUAGES = ['ru', 'uz'] as const

export function SettingsPage() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const setLocalLanguage = useAuthStore((state) => state.setLocalLanguage)

  if (!user) {
    return null
  }

  const activeLanguage = i18n.language.startsWith('uz') ? 'uz' : 'ru'

  const handleLanguageChange = (language: (typeof SUPPORTED_LANGUAGES)[number]) => {
    void i18n.changeLanguage(language)
    setLocalLanguage(language)
  }

  return (
    <div className="page-content settings-page">
      <Title level="1" weight="2" className="home-page__title">
        {t('nav.settings')}
      </Title>

      <Section>
        <Cell subtitle={t('settings.role')}>
          <Text>{t(`settings.roles.${user.role}`, { defaultValue: user.role })}</Text>
        </Cell>
        <Cell subtitle={t('settings.firstName')}>
          <Text>{user.firstName ?? '—'}</Text>
        </Cell>
      </Section>

      <Section header={t('settings.language')}>
        <div className="segmented-control-wrap settings-page__language-toggle">
          <SegmentedControl>
            {SUPPORTED_LANGUAGES.map((language) => (
              <SegmentedControl.Item
                key={language}
                selected={activeLanguage === language}
                onClick={() => handleLanguageChange(language)}
              >
                {language.toUpperCase()}
              </SegmentedControl.Item>
            ))}
          </SegmentedControl>
        </div>
      </Section>

      <WalletsSection />
      <IncomeCategoriesSection />
      <ExpenseCategoriesSection />
    </div>
  )
}
