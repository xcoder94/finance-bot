import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { ShoppingItem } from '../../api/shopping'
import type { AddResult, ShoppingStatus } from '../../store/shoppingStore'
import { useLeavingItems } from '../../hooks/useLeavingItems'
import { ShoppingAddRow } from './ShoppingAddRow'
import { ShoppingSwipeRow } from './ShoppingSwipeRow'
import { FailBox } from '../FailBox'
import { EmptyStateIcon } from '../EmptyStateIcon'

type ShoppingListViewProps = {
  status: ShoppingStatus
  items: ShoppingItem[]
  onRetry: () => void
  onAdd: (name: string) => Promise<AddResult>
  onEdit: (item: ShoppingItem) => void
  onDelete: (item: ShoppingItem) => void
  onStart: () => void
}

function ShoppingSkeleton() {
  return (
    <div className="shopping-skeleton" aria-busy="true">
      {[0, 1, 2, 3, 4, 5].map((key) => (
        <div key={key} className="shopping-skeleton__row">
          <div
            className="home-skeleton__line shopping-skeleton__line"
            style={{ width: `${[58, 42, 66, 36, 52, 46][key]}%` }}
          />
        </div>
      ))}
    </div>
  )
}

export function ShoppingListView({
  status,
  items,
  onRetry,
  onAdd,
  onEdit,
  onDelete,
  onStart,
}: ShoppingListViewProps) {
  const { t } = useTranslation()
  const [openId, setOpenId] = useState<string | null>(null)
  const displayed = useLeavingItems(items)

  const hasItems = items.length > 0
  const showSkeleton = (status === 'loading' || status === 'idle') && !hasItems
  const showError = status === 'error' && !hasItems
  const showEmpty = status === 'ready' && !hasItems

  return (
    <div className="shopping-page">
      <div className="shopping-page__header">
        <h1 className="shopping-page__title">{t('nav.shopping')}</h1>
        {hasItems ? (
          <div className="shopping-page__count">{t('shopping.count', { count: items.length })}</div>
        ) : null}
      </div>

      {showError ? (
        <FailBox onRetry={onRetry} />
      ) : (
        <ShoppingAddRow onAdd={onAdd} />
      )}

      {showSkeleton ? <ShoppingSkeleton /> : null}

      {showEmpty ? (
        <div className="goals-page__empty">
          <EmptyStateIcon className="goals-page__empty-icon" />
          <div className="goals-page__empty-title">{t('shopping.emptyTitle')}</div>
          <div className="goals-page__empty-subtitle">{t('shopping.emptyHint')}</div>
        </div>
      ) : null}

      {hasItems ? (
        <div className="shopping-list">
          {displayed.map(({ item, leaving }) => (
            <ShoppingSwipeRow
              key={item.id}
              leaving={leaving}
              name={item.name}
              open={openId === item.id}
              onOpenChange={(next) => setOpenId(next ? item.id : null)}
              onEdit={() => {
                setOpenId(null)
                onEdit(item)
              }}
              onDelete={() => {
                setOpenId(null)
                onDelete(item)
              }}
            />
          ))}
        </div>
      ) : null}

      {hasItems ? (
        <div className="shopping-page__start">
          <button type="button" className="shopping-page__start-btn" onClick={onStart}>
            {t('shopping.startTrip')}
          </button>
        </div>
      ) : null}
    </div>
  )
}
