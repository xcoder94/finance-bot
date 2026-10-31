import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import ru from './locales/ru.json'
import uz from './locales/uz.json'
import adminRu from './locales/admin.ru.json'
import { detectStartLanguage, rememberLanguageInBrowser } from './startLanguage'

if (!i18n.isInitialized) {
  void i18n.use(initReactI18next).init({
    resources: {
      ru: { translation: ru, admin: adminRu },
      // The admin section is RU-only (analyst decision): UZ users never see it, and the owner reads RU.
      uz: { translation: uz, admin: adminRu },
    },
    lng: detectStartLanguage(),
    fallbackLng: 'ru',
    interpolation: {
      escapeValue: false,
    },
  })

  const syncDocumentLanguage = (language: string) => {
    if (typeof document === 'undefined') {
      return
    }
    document.documentElement.lang = language.startsWith('uz') ? 'uz' : 'ru'
  }

  syncDocumentLanguage(i18n.language)
  i18n.on('languageChanged', syncDocumentLanguage)
  i18n.on('languageChanged', rememberLanguageInBrowser)
}

export default i18n
