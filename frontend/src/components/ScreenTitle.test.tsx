import { renderToStaticMarkup } from 'react-dom/server'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import { ScreenTitle } from './ScreenTitle'

const css = readFileSync(join(__dirname, '..', 'index.css'), 'utf8')

describe('screen header is one left-aligned style (B14)', () => {
  it('renders an h1 with the shared class', () => {
    expect(renderToStaticMarkup(<ScreenTitle>Кошельки</ScreenTitle>)).toBe(
      '<h1 class="screen-title">Кошельки</h1>',
    )
  })
  it('the shared class is left-aligned and same size as Goals / Settings titles', () => {
    const block = css.slice(css.indexOf('\n.screen-title {'))
    const body = block.slice(0, block.indexOf('}'))
    expect(body).toContain('text-align: left')
    expect(body).toContain('font-size: 18px')
    expect(body).not.toContain('center')
  })
  it('Wallets and wallet card use it (no centred home-page__title left)', () => {
    for (const f of ['wallets/WalletsView.tsx', 'wallets/WalletOpsView.tsx']) {
      const src = readFileSync(join(__dirname, f), 'utf8')
      expect(src).toContain('<ScreenTitle>')
      expect(src).not.toContain('home-page__title')
    }
  })
})
