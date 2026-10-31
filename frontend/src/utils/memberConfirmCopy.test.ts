import { describe, expect, it } from 'vitest'

import {
  leaveConfirmAction,
  memberConfirmCancel,
  removeConfirmAction,
  transferConfirmAction,
  leaveConfirmBody,
  removeConfirmBody,
  transferConfirmBody,
} from './memberConfirmCopy'

describe('memberConfirmCopy', () => {
  it('leave confirm body substitutes budget name verbatim', () => {
    expect(leaveConfirmBody('Семья Каримовых')).toBe(
      'Вы выйдете из бюджета «Семья Каримовых». Ваши личные кошельки и операции по ним перейдут в ваш собственный бюджет. Операции по общим кошелькам останутся в этой семье.',
    )
  })

  it('remove confirm body substitutes member name verbatim', () => {
    expect(removeConfirmBody('Рустам')).toBe(
      'Рустам больше не будет участником бюджета. Личные кошельки и операции по ним перейдут в собственный бюджет участника. Операции по общим кошелькам останутся здесь.',
    )
  })

  it('transfer confirm body substitutes member name verbatim', () => {
    expect(transferConfirmBody('Рустам')).toBe(
      'Новый владелец бюджета: Рустам. Нужно его подтверждение. После этого вы останетесь обычным участником. Отменить в одиночку нельзя.',
    )
  })
  it('confirm action labels are exact', () => {
    expect(leaveConfirmAction()).toBe('Выйти')
    expect(removeConfirmAction()).toBe('Удалить')
    expect(transferConfirmAction()).toBe('Передать')
    expect(memberConfirmCancel()).toBe('Отмена')
  })
})
