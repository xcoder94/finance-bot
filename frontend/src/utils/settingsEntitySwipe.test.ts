import { describe, expect, it } from 'vitest'

import {
  SETTINGS_SWIPE_DELETE_WIDTH,
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
})
