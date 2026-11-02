import { describe, expect, it } from 'vitest'

import { pageScreenKey, transitionDirection } from './pageTransition'

describe('pageScreenKey', () => {
  it('is the full path, trailing slash ignored', () => {
    expect(pageScreenKey('/settings/wallets/')).toBe('/settings/wallets')
    expect(pageScreenKey('/')).toBe('/')
  })
  it('analytics keeps one screen for all its inner routes', () => {
    expect(pageScreenKey('/analytics/categories')).toBe('/analytics')
    expect(pageScreenKey('/analytics')).toBe('/analytics')
  })
})

describe('transitionDirection', () => {
  it('same screen: no animation', () => {
    expect(transitionDirection('/analytics', '/analytics/x', 'PUSH')).toBeNull()
    expect(transitionDirection('/history', '/history', 'PUSH')).toBeNull()
  })
  it('tabs: moves in the direction of the tab order', () => {
    expect(transitionDirection('/', '/shopping', 'PUSH')).toBe('tab-next')
    expect(transitionDirection('/goals', '/analytics', 'PUSH')).toBe('tab-prev')
    expect(transitionDirection('/shopping', '/', 'POP')).toBe('tab-prev')
  })
  it('deeper level slides in from the right', () => {
    expect(transitionDirection('/settings', '/settings/wallets', 'PUSH')).toBe('forward')
    expect(transitionDirection('/', '/settings', 'PUSH')).toBe('forward')
    expect(transitionDirection('/settings/expense-categories', '/settings/expense-categories/5', 'PUSH')).toBe('forward')
  })
  it('shallower level goes back, even through navigate() (not POP)', () => {
    expect(transitionDirection('/settings/wallets', '/settings', 'REPLACE')).toBe('back')
    expect(transitionDirection('/history', '/', 'PUSH')).toBe('back')
  })
  it('same depth: POP is back, otherwise forward', () => {
    expect(transitionDirection('/settings', '/history', 'POP')).toBe('back')
    expect(transitionDirection('/settings', '/history', 'PUSH')).toBe('forward')
  })
  it('leaving a non-tab screen into a tab: back', () => {
    expect(transitionDirection('/settings', '/shopping', 'PUSH')).toBe('back')
  })
  it('first screen: plain fade', () => {
    expect(transitionDirection(null, '/', 'POP')).toBe('fade')
  })
})
