import { type PointerEvent as ReactPointerEvent, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { exceedsPointerDragThreshold } from '../../utils/settingsEntitySwipe'

/** Two actions (Изменить + Удалить), 96px each. */
export const SHOPPING_SWIPE_WIDTH = 192

type ShoppingSwipeRowProps = {
  name: string
  /** Row was just removed: plays the collapse animation, then the parent drops it. */
  leaving?: boolean
  open: boolean
  onOpenChange: (open: boolean) => void
  onEdit: () => void
  onDelete: () => void
}

export function ShoppingSwipeRow({
  name,
  leaving = false,
  open,
  onOpenChange,
  onEdit,
  onDelete,
}: ShoppingSwipeRowProps) {
  const { t } = useTranslation()
  const [drag, setDrag] = useState<number | null>(null)
  const startX = useRef(0)
  const startOffset = useRef(0)
  const pointerDown = useRef(false)
  const dragActive = useRef(false)
  const justDragged = useRef(false)

  const baseOffset = open ? -SHOPPING_SWIPE_WIDTH : 0
  const offset = drag ?? baseOffset

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    pointerDown.current = true
    dragActive.current = false
    startX.current = event.clientX
    startOffset.current = baseOffset
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!pointerDown.current) {
      return
    }
    const delta = event.clientX - startX.current
    if (!dragActive.current) {
      if (!exceedsPointerDragThreshold(delta)) {
        return
      }
      dragActive.current = true
      event.currentTarget.setPointerCapture(event.pointerId)
    }
    setDrag(Math.max(-SHOPPING_SWIPE_WIDTH, Math.min(0, startOffset.current + delta)))
  }

  const handlePointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!pointerDown.current) {
      return
    }
    pointerDown.current = false
    if (!dragActive.current) {
      return
    }
    dragActive.current = false
    justDragged.current = true
    event.currentTarget.releasePointerCapture(event.pointerId)
    const finalOffset = drag ?? baseOffset
    setDrag(null)
    onOpenChange(finalOffset <= -SHOPPING_SWIPE_WIDTH / 2)
  }

  const handleClick = () => {
    if (justDragged.current) {
      justDragged.current = false
      return
    }
    onOpenChange(!open)
  }

  return (
    <div className={`shopping-row${leaving ? ' shopping-row--leaving' : ''}`}>
      <div className="shopping-row__actions">
        <button
          type="button"
          className="shopping-row__action shopping-row__action--edit"
          tabIndex={open ? 0 : -1}
          onClick={onEdit}
        >
          {t('shopping.swipeEdit')}
        </button>
        <button
          type="button"
          className="shopping-row__action shopping-row__action--delete"
          tabIndex={open ? 0 : -1}
          onClick={onDelete}
        >
          {t('shopping.swipeDelete')}
        </button>
      </div>
      <div
        className="shopping-row__content"
        style={{
          transform: `translateX(${offset}px)`,
          transition: drag === null ? undefined : 'none',
        }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <button type="button" className="shopping-row__main" onClick={handleClick}>
          <span className="shopping-row__name" title={name}>
            {name}
          </span>
        </button>
      </div>
    </div>
  )
}
