import type { TFunction } from 'i18next'

import type { HistoryItem } from '../api/home'

export type TranslatableEntity = {
  name: string
  translation_key: string | null
}

export function getDisplayName(entity: TranslatableEntity, t: TFunction): string {
  return entity.translation_key
    ? t(`defaultEntities.${entity.translation_key}`)
    : entity.name
}

export function buildDisplayNameById<T extends TranslatableEntity & { id: string }>(
  entities: T[],
  t: TFunction,
): Map<string, string> {
  return new Map(entities.map((entity) => [entity.id, getDisplayName(entity, t)]))
}

export function resolveStoredEntityDisplayName(
  storedName: string | null | undefined,
  translationKey: string | null | undefined,
  t: TFunction,
): string | null {
  if (storedName == null) {
    return null
  }

  return translationKey ? t(`defaultEntities.${translationKey}`) : storedName
}

export function getHistoryItemTitle(
  item: HistoryItem,
  labels: { transfer: string; exchange: string },
  t: TFunction,
): string {
  if (item.type === 'income') {
    return (
      resolveStoredEntityDisplayName(
        item.income_category_name,
        item.income_category_translation_key,
        t,
      ) ?? '—'
    )
  }
  if (item.type === 'expense') {
    return (
      resolveStoredEntityDisplayName(
        item.expense_subcategory_name,
        item.expense_subcategory_translation_key,
        t,
      ) ?? '—'
    )
  }
  if (item.type === 'transfer' && item.currency !== item.to_currency) {
    return labels.exchange
  }
  return labels.transfer
}

export function getHistoryItemSubtitle(
  item: HistoryItem,
  incomeLabel: string,
  t: TFunction,
): string {
  if (item.type === 'income') {
    return incomeLabel
  }
  if (item.type === 'expense') {
    return (
      resolveStoredEntityDisplayName(
        item.expense_category_name,
        item.expense_category_translation_key,
        t,
      ) ?? '—'
    )
  }

  const sourceWallet =
    resolveStoredEntityDisplayName(
      item.wallet_name,
      item.wallet_translation_key,
      t,
    ) ?? '—'
  const destinationWallet = item.to_wallet_id
    ? (resolveStoredEntityDisplayName(
        item.to_wallet_name,
        item.to_wallet_translation_key,
        t,
      ) ?? '—')
    : (item.to_wallet_name ?? '—')

  return `${sourceWallet} → ${destinationWallet}`
}

export function getHistoryWalletDisplayName(item: HistoryItem, t: TFunction): string {
  return (
    resolveStoredEntityDisplayName(item.wallet_name, item.wallet_translation_key, t) ??
    '—'
  )
}

export function resolveCategoryAmountDisplayName(
  entry: {
    category_id: string
    category_name: string
    category_translation_key?: string | null
  },
  displayNameById: Map<string, string> | undefined,
  t: TFunction,
): string {
  if (entry.category_translation_key) {
    return t(`defaultEntities.${entry.category_translation_key}`)
  }
  return displayNameById?.get(entry.category_id) ?? entry.category_name
}

export function resolveSubcategoryAmountDisplayName(
  entry: {
    subcategory_id: string
    subcategory_name: string
    subcategory_translation_key?: string | null
  },
  displayNameById: Map<string, string> | undefined,
  t: TFunction,
): string {
  if (entry.subcategory_translation_key) {
    return t(`defaultEntities.${entry.subcategory_translation_key}`)
  }
  return displayNameById?.get(entry.subcategory_id) ?? entry.subcategory_name
}
