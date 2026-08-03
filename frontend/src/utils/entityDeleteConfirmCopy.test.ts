import { describe, expect, it } from 'vitest'

import {
  buildEntityDeleteTitle,
  buildWalletDeleteIntro,
  WALLET_DELETE_DANGER_LABEL,
} from './entityDeleteConfirmCopy'

describe('entity delete confirm copy', () => {
  it('builds title with quoted entity name', () => {
    expect(buildEntityDeleteTitle('Тои и маърака')).toBe('Удалить «Тои и маърака»?')
  })

  it('builds wallet intro for zero transactions', () => {
    expect(buildWalletDeleteIntro(0)).toBe('Кошелёк удалится. Отменить нельзя.')
  })

  it('builds wallet intro for multiple transactions', () => {
    expect(buildWalletDeleteIntro(3)).toBe(
      'Кошелёк удалится, а 3 операции останутся в истории и аналитике. Отменить нельзя.',
    )
  })

  it('uses singular verb for one transaction', () => {
    expect(buildWalletDeleteIntro(1)).toBe(
      'Кошелёк удалится, а 1 операция останется в истории и аналитике. Отменить нельзя.',
    )
  })

  it('exports wallet danger label', () => {
    expect(WALLET_DELETE_DANGER_LABEL).toBe('Удалить кошелёк')
  })
})
