import { useTranslation } from 'react-i18next'

import type { ShoppingItem } from '../../api/shopping'
import { canFinishTrip } from '../../utils/shoppingTrip'

type ShoppingTripViewProps = {
  items: ShoppingItem[]
  checked: ReadonlySet<string>
  /** Id of the row that was just checked (plays the tick animation once). */
  popId: string | null
  onToggle: (id: string) => void
  onCancel: () => void
  onFinish: () => void
}

function Tick() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 8.5l3.2 3.2L13 4.8" />
    </svg>
  )
}

export function ShoppingTripView({
  items,
  checked,
  popId,
  onToggle,
  onCancel,
  onFinish,
}: ShoppingTripViewProps) {
  const { t } = useTranslation()
  const done = items.filter((item) => checked.has(item.id)).length

  return (
    <div className="shopping-page shopping-page--bar">
      <div className="shopping-page__header">
        <h1 className="shopping-page__title">{t('shopping.tripTitle')}</h1>
        <div className="shopping-page__count shopping-trip__counter">
          {done} / {items.length}
        </div>
      </div>

      <div className="shopping-list">
        {items.map((item) => {
          const on = checked.has(item.id)
          return (
            <button
              key={item.id}
              type="button"
              role="checkbox"
              aria-checked={on}
              className="shopping-trip__row"
              onClick={() => onToggle(item.id)}
            >
              <span
                className={`shopping-trip__cb${on ? ' shopping-trip__cb--on' : ''}${popId === item.id ? ' shopping-trip__cb--pop' : ''}`}
              >
                {on ? <Tick /> : null}
              </span>
              <span className={`shopping-trip__name${on ? ' shopping-trip__name--on' : ''}`}>
                {item.name}
              </span>
            </button>
          )
        })}
      </div>

      <div className="shopping-trip__bar">
        <button type="button" className="shopping-trip__cancel" onClick={onCancel}>
          {t('shopping.cancel')}
        </button>
        <button
          type="button"
          className="shopping-trip__finish"
          disabled={!canFinishTrip(checked)}
          onClick={onFinish}
        >
          {t('shopping.finish')}
        </button>
      </div>
    </div>
  )
}
