import i18next from 'i18next'
import { afterEach, describe, expect, it } from 'vitest'

import '../i18n/init'
import { getDisplayName, resolveStoredEntityDisplayName } from './getDisplayName'

// dev-fix9: backend keeps translation_key after a rename, so a renamed default wallet or category
// must still show the user's own name (not the localized default).
describe('display name of default entities', () => {
  afterEach(async () => {
    await i18next.changeLanguage('ru')
  })

  it('shows the localized default while the name is still a default', async () => {
    await i18next.changeLanguage('uz')
    expect(getDisplayName({ name: 'Наличный сум', translation_key: 'cash_uzs' }, i18next.t)).toBe(
      i18next.t('defaultEntities.cash_uzs'),
    )
    expect(getDisplayName({ name: "Naqd so'm", translation_key: 'cash_uzs' }, i18next.t)).toBe(
      i18next.t('defaultEntities.cash_uzs'),
    )
  })

  it('shows the user name when the default entity was renamed', () => {
    expect(getDisplayName({ name: 'Карта-новая', translation_key: 'card_uzs' }, i18next.t)).toBe('Карта-новая')
    expect(resolveStoredEntityDisplayName('Моя аренда', 'rent', i18next.t)).toBe('Моя аренда')
  })

  it('entities without key keep their name', () => {
    expect(getDisplayName({ name: 'X', translation_key: null }, i18next.t)).toBe('X')
  })
})
