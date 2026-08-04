/** Mini-app confirmation copy for leave / remove / transfer — verbatim approved strings. */

export function leaveConfirmBody(budgetName: string): string {
  return `Вы выйдете из бюджета «${budgetName}». Ваши личные кошельки и операции по ним перейдут в ваш собственный бюджет. Операции по общим кошелькам останутся в этой семье.`
}

export function removeConfirmBody(memberName: string): string {
  return `Удалить ${memberName} из бюджета? Его личные кошельки и операции по ним перейдут в его собственный бюджет. Операции по общим кошелькам останутся здесь.`
}

export function transferConfirmBody(memberName: string): string {
  return `Передать владение бюджетом ${memberName}? Он должен подтвердить. После этого вы останетесь обычным участником. Отменить в одиночку нельзя.`
}

export const LEAVE_CONFIRM_ACTION = 'Выйти'
export const REMOVE_CONFIRM_ACTION = 'Удалить'
export const TRANSFER_CONFIRM_ACTION = 'Передать'
export const MEMBER_CONFIRM_CANCEL = 'Отмена'
