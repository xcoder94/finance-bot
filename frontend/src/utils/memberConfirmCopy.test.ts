import { describe, expect, it } from 'vitest'

import {
  LEAVE_CONFIRM_ACTION,
  MEMBER_CONFIRM_CANCEL,
  REMOVE_CONFIRM_ACTION,
  TRANSFER_CONFIRM_ACTION,
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
    expect(removeConfirmBody('Рустама')).toBe(
      'Удалить Рустама из бюджета? Его личные кошельки и операции по ним перейдут в его собственный бюджет. Операции по общим кошелькам останутся здесь.',
    )
  })

  it('transfer confirm body substitutes member name verbatim', () => {
    expect(transferConfirmBody('Рустаму')).toBe(
      'Передать владение бюджетом Рустаму? Он должен подтвердить. После этого вы останетесь обычным участником. Отменить в одиночку нельзя.',
    )
  })

  it('confirm action labels are exact', () => {
    expect(LEAVE_CONFIRM_ACTION).toBe('Выйти')
    expect(REMOVE_CONFIRM_ACTION).toBe('Удалить')
    expect(TRANSFER_CONFIRM_ACTION).toBe('Передать')
    expect(MEMBER_CONFIRM_CANCEL).toBe('Отмена')
  })
})
