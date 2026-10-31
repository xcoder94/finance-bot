import { t } from '../i18n/t'

function opsPhrase(count: number): string {
  return t('entityDelete.ops', { count })
}

function subsPhrase(count: number): string {
  return t('entityDelete.subs', { count })
}

function subDeleteVerb(count: number): string {
  return t('entityDelete.willDelete', { count })
}

function remainVerb(count: number): string {
  return t('entityDelete.remain', { count })
}

export function buildEntityDeleteTitle(entityName: string): string {
  return t('entityDelete.title', { name: entityName })
}

export function buildWalletDeleteIntro(transactionCount: number): string {
  if (transactionCount <= 0) {
    return t('entityDelete.walletPlain')
  }
  return t('entityDelete.walletOps', {
    ops: opsPhrase(transactionCount),
    verb: remainVerb(transactionCount),
  })
}

export function walletDeleteDangerLabel(): string {
  return t('entityDelete.dangerWallet')
}

export function categoryDeleteDangerLabel(): string {
  return t('entityDelete.dangerCategory')
}

export function subcategoryDeleteDangerLabel(): string {
  return t('entityDelete.dangerSubcategory')
}

export function formatEntityTransactionSubtitle(transactionCount: number): string {
  if (transactionCount <= 0) {
    return t('entityDelete.noOps')
  }
  return opsPhrase(transactionCount)
}

export function buildIncomeCategoryDeleteIntro(transactionCount: number): string {
  if (transactionCount <= 0) {
    return t('entityDelete.categoryPlain')
  }
  return t('entityDelete.categoryOps', {
    ops: opsPhrase(transactionCount),
    verb: remainVerb(transactionCount),
  })
}

export function buildExpenseParentDeleteIntro(
  transactionCount: number,
  subcategoryCount: number,
): string {
  if (subcategoryCount > 0) {
    const subs = subsPhrase(subcategoryCount)
    const subVerb = subDeleteVerb(subcategoryCount)
    if (transactionCount <= 0) {
      return t('entityDelete.categorySubs', { subs, subVerb })
    }
    return t('entityDelete.categorySubsOps', {
      subs,
      subVerb,
      ops: opsPhrase(transactionCount),
      verb: remainVerb(transactionCount),
    })
  }

  return buildIncomeCategoryDeleteIntro(transactionCount)
}

export function buildSubcategoryDeleteIntro(
  transactionCount: number,
  parentName: string,
  year = new Date().getFullYear(),
): string {
  if (transactionCount <= 0) {
    return t('entityDelete.subPlain')
  }
  return t('entityDelete.subOps', {
    ops: opsPhrase(transactionCount),
    verb: remainVerb(transactionCount),
    parent: parentName,
    year,
  })
}
