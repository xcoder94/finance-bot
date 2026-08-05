import { describe, expect, it } from 'vitest'

import {
  exceedsPointerDragThreshold,
  SETTINGS_SWIPE_DELETE_WIDTH,
  SETTINGS_SWIPE_POINTER_DRAG_THRESHOLD,
  shouldShowSwipeDeleteButton,
} from './settingsEntitySwipe'

describe('settings entity swipe delete', () => {
  it('uses design delete button width', () => {
    expect(SETTINGS_SWIPE_DELETE_WIDTH).toBe(96)
  })

  it('does not show inline delete until swipe reveals it', () => {
    expect(shouldShowSwipeDeleteButton(false)).toBe(false)
    expect(shouldShowSwipeDeleteButton(true)).toBe(true)
  })

  it('uses a small pointer drag threshold so taps stay clicks', () => {
    expect(SETTINGS_SWIPE_POINTER_DRAG_THRESHOLD).toBeGreaterThanOrEqual(6)
    expect(SETTINGS_SWIPE_POINTER_DRAG_THRESHOLD).toBeLessThanOrEqual(8)
  })

  it('does not treat sub-threshold movement as a drag', () => {
    expect(exceedsPointerDragThreshold(0)).toBe(false)
    expect(exceedsPointerDragThreshold(5)).toBe(false)
    expect(exceedsPointerDragThreshold(-6)).toBe(false)
  })

  it('treats movement at or above threshold as a drag', () => {
    expect(exceedsPointerDragThreshold(7)).toBe(true)
    expect(exceedsPointerDragThreshold(-8)).toBe(true)
    expect(exceedsPointerDragThreshold(20)).toBe(true)
  })
})
