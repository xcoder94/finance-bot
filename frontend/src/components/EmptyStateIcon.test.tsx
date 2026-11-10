import { renderToStaticMarkup } from 'react-dom/server'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import { EmptyStateIcon } from './EmptyStateIcon'

describe('empty states have a real icon (B13)', () => {
  it('renders an svg glyph inside the tile', () => {
    const html = renderToStaticMarkup(<EmptyStateIcon className="home-empty-card__icon" />)
    expect(html).toContain('<svg')
    expect(html).toContain('home-empty-card__icon')
  })
  it('no empty icon div is left in Home, History list, Shopping, Goals', () => {
    for (const file of [
      'pages/HomePage.tsx',
      'components/history/HistoryTransactionList.tsx',
      'components/shopping/ShoppingListView.tsx',
      'pages/GoalsPage.tsx',
    ]) {
      const src = readFileSync(join(__dirname, '..', file), 'utf8')
      expect(src).not.toMatch(/<div className="(home-empty-card__icon|goals-page__empty-icon)"[^>]*\/>/)
      expect(src).toContain('EmptyStateIcon')
    }
  })
})
