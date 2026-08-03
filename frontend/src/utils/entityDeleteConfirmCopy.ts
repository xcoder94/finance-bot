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

function subcategoryCountPhrase(count: number): string {
  const abs = count % 100
  const mod10 = count % 10

  if (mod10 === 1 && abs !== 11) {
    return `${count} подкатегория`
  }
  if (mod10 >= 2 && mod10 <= 4 && (abs < 10 || abs >= 20)) {
    return `${count} подкатегории`
  }
  return `${count} подкатегорий`
}

function subcategoryDeleteVerb(count: number): string {
  if (count % 10 === 1 && count % 100 !== 11) {
    return 'удалится'
  }
  return 'удалятся'
}

function subcategoryRemainVerb(count: number): string {
  if (count % 10 === 1 && count % 100 !== 11) {
    return 'останется'
  }
  return 'останутся'
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
export const CATEGORY_DELETE_DANGER_LABEL = 'Удалить категорию'
export const SUBCATEGORY_DELETE_DANGER_LABEL = 'Удалить подкатегорию'

export function formatEntityTransactionSubtitle(transactionCount: number): string {
  if (transactionCount <= 0) {
    return 'нет операций'
  }
  return operationCountPhrase(transactionCount)
}

export function buildIncomeCategoryDeleteIntro(transactionCount: number): string {
  if (transactionCount <= 0) {
    return 'Категория удалится. Отменить нельзя.'
  }

  const phrase = operationCountPhrase(transactionCount)
  const verb = operationsRemainVerb(transactionCount)
  return `Категория удалится, а ${phrase} ${verb} в истории и аналитике. Отменить нельзя.`
}

export function buildExpenseParentDeleteIntro(
  transactionCount: number,
  subcategoryCount: number,
): string {
  if (subcategoryCount > 0) {
    const subPhrase = subcategoryCountPhrase(subcategoryCount)
    const subVerb = subcategoryDeleteVerb(subcategoryCount)
    if (transactionCount <= 0) {
      return `Категория и ${subPhrase} ${subVerb}. Отменить нельзя.`
    }

    const phrase = operationCountPhrase(transactionCount)
    const verb = operationsRemainVerb(transactionCount)
    return `Категория и ${subPhrase} ${subVerb}, а ${phrase} ${verb} в истории и аналитике. Отменить нельзя.`
  }

  if (transactionCount <= 0) {
    return 'Категория удалится. Отменить нельзя.'
  }

  const phrase = operationCountPhrase(transactionCount)
  const verb = operationsRemainVerb(transactionCount)
  return `Категория удалится, а ${phrase} ${verb} в истории и аналитике. Отменить нельзя.`
}

export function buildSubcategoryDeleteIntro(
  transactionCount: number,
  parentName: string,
  year = new Date().getFullYear(),
): string {
  if (transactionCount <= 0) {
    return 'Подкатегория удалится. Отменить нельзя.'
  }

  const phrase = operationCountPhrase(transactionCount)
  const verb = subcategoryRemainVerb(transactionCount)
  return `Подкатегория удалится, а ${phrase} за ${year} год ${verb} в родительской категории «${parentName}». Отменить нельзя.`
}
