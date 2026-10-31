import { describe, expect, it, vi } from 'vitest'

const remember = vi.hoisted(() => vi.fn())
vi.mock('./startLanguage', () => ({
  detectStartLanguage: () => 'uz',
  rememberLanguageInBrowser: remember,
}))

import i18n from './init'

describe('i18n/init start language wiring', () => {
  it('starts in the language detectStartLanguage returned', () => {
    expect(i18n.language).toBe('uz')
    expect(i18n.t('auth.retry')).toBe(
      (i18n.getResourceBundle('uz', 'translation') as { auth: { retry: string } }).auth.retry,
    )
  })

  it('remembers the language on every change', async () => {
    await i18n.changeLanguage('ru')
    expect(remember).toHaveBeenCalledWith('ru')
  })
})
