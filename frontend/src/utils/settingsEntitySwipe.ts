/** Swipe-reveal delete width from design (px). */
export const SETTINGS_SWIPE_DELETE_WIDTH = 96

/** Horizontal movement (px) before swipe drag captures the pointer. */
export const SETTINGS_SWIPE_POINTER_DRAG_THRESHOLD = 7

export function shouldShowSwipeDeleteButton(revealed: boolean): boolean {
  return revealed
}

export function exceedsPointerDragThreshold(
  deltaX: number,
  threshold = SETTINGS_SWIPE_POINTER_DRAG_THRESHOLD,
): boolean {
  return Math.abs(deltaX) >= threshold
}
