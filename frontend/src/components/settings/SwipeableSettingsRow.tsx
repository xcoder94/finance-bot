import { type PointerEvent as ReactPointerEvent, useRef, useState } from 'react'

import {
  exceedsPointerDragThreshold,
  SETTINGS_SWIPE_DELETE_WIDTH,
} from '../../utils/settingsEntitySwipe'

type SwipeableSettingsRowProps = {
  name: string
  subtitle?: string
  onOpen: () => void
  onDelete?: () => void
  swipeDeleteEnabled?: boolean
}

export function SwipeableSettingsRow({
  name,
  subtitle,
  onOpen,
  onDelete,
  swipeDeleteEnabled = false,
}: SwipeableSettingsRowProps) {
  const [offset, setOffset] = useState(0)
  const startX = useRef(0)
  const startOffset = useRef(0)
  const pointerDown = useRef(false)
  const dragActive = useRef(false)

  const revealed = offset <= -SETTINGS_SWIPE_DELETE_WIDTH / 2
  const clampedOffset =
    swipeDeleteEnabled ? Math.max(-SETTINGS_SWIPE_DELETE_WIDTH, Math.min(0, offset)) : 0

  const finishDrag = () => {
    dragActive.current = false
    if (!swipeDeleteEnabled) {
      setOffset(0)
      return
    }
    setOffset(revealed ? -SETTINGS_SWIPE_DELETE_WIDTH : 0)
  }

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!swipeDeleteEnabled) {
      return
    }
    pointerDown.current = true
    dragActive.current = false
    startX.current = event.clientX
    startOffset.current = offset
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!pointerDown.current || !swipeDeleteEnabled) {
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
    setOffset(
      Math.max(
        -SETTINGS_SWIPE_DELETE_WIDTH,
        Math.min(0, startOffset.current + delta),
      ),
    )
  }

  const handlePointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!pointerDown.current) {
      return
    }
    pointerDown.current = false
    if (!dragActive.current) {
      return
    }
    event.currentTarget.releasePointerCapture(event.pointerId)
    finishDrag()
  }

  return (
    <div className="settings-swipe-row">
      {swipeDeleteEnabled ? (
        <button
          type="button"
          className="settings-swipe-row__delete"
          onClick={() => onDelete?.()}
        >
          Удалить
        </button>
      ) : null}
      <div
        className="settings-swipe-row__content"
        style={{ transform: `translateX(${clampedOffset}px)` }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <button type="button" className="settings-swipe-row__main" onClick={onOpen}>
          <span className="settings-swipe-row__text">
            <span className="settings-swipe-row__name">{name}</span>
            {subtitle ? (
              <span className="settings-swipe-row__subtitle">{subtitle}</span>
            ) : null}
          </span>
          <span className="settings-swipe-row__chevron" aria-hidden="true">›</span>
        </button>
      </div>
    </div>
  )
}
