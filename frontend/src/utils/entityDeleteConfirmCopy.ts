function operationCountPhrase(count: number): string {
  const abs = count % 100
  const mod10 = count % 10

  if (mod10 === 1 && abs !== 11) {
    return `${count} операция`
  }
  if (mod10 >= 2 && mod10 <= 4 && (abs < 10 || abs >= 20)) {
    return `${count} операции`
  }
  return `${count} операций`
}

function operationsRemainVerb(count: number): string {
  if (count % 10 === 1 && count % 100 !== 11) {
    return 'останется'
  }
  return 'останутся'
}

export function buildEntityDeleteTitle(entityName: string): string {
  return `Удалить «${entityName}»?`
}

export function buildWalletDeleteIntro(transactionCount: number): string {
  if (transactionCount <= 0) {
    return 'Кошелёк удалится. Отменить нельзя.'
  }

  const phrase = operationCountPhrase(transactionCount)
  const verb = operationsRemainVerb(transactionCount)
  return `Кошелёк удалится, а ${phrase} ${verb} в истории и аналитике. Отменить нельзя.`
}

export const WALLET_DELETE_DANGER_LABEL = 'Удалить кошелёк'
