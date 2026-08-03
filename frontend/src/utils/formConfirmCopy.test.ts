import { describe, expect, it } from 'vitest'

import { buildDeleteConfirmBody } from './formConfirmCopy'

describe('buildDeleteConfirmBody', () => {
  it('uses comment as label for UZS amount with spaced thousands', () => {
    expect(
      buildDeleteConfirmBody({
        comment: 'Такси до школы',
        categoryLabel: 'Транспорт',
        amount: 200_000,
        currency: 'UZS',
      }),
    ).toBe(
      'Запись «Такси до школы» на 200 000 сум удалится из истории и из аналитики. Отменить нельзя.',
    )
  })

  it('falls back to category label when comment is missing', () => {
    expect(
      buildDeleteConfirmBody({
        comment: null,
        categoryLabel: 'Продукты',
        amount: 1_284_000,
        currency: 'UZS',
      }),
    ).toBe(
      'Запись «Продукты» на 1 284 000 сум удалится из истории и из аналитики. Отменить нельзя.',
    )
  })

  it('falls back to category label for blank comment', () => {
    expect(
      buildDeleteConfirmBody({
        comment: '   ',
        categoryLabel: 'Зарплата',
        amount: 9_800_000,
        currency: 'UZS',
      }),
    ).toBe(
      'Запись «Зарплата» на 9 800 000 сум удалится из истории и из аналитики. Отменить нельзя.',
    )
  })

  it('formats USD with dollar word after amount', () => {
    expect(
      buildDeleteConfirmBody({
        comment: 'Обмен',
        categoryLabel: 'Перевод',
        amount: 100,
        currency: 'USD',
      }),
    ).toBe(
      'Запись «Обмен» на 100 $ удалится из истории и из аналитики. Отменить нельзя.',
    )
  })
})
