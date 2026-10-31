import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const css = readFileSync(new URL('./index.css', import.meta.url), 'utf8')
const block = (selector: string) => {
  const m = css.match(new RegExp(`${selector.replace(/[.[\]()]/g, '\\$&')}\\s*\\{([^}]*)\\}`))
  return m ? m[1] : ''
}

describe('tabbar and swipe-delete styles (m3-1 fix)', () => {
  it('B1: tab links may shrink so four tabs fit a 320px screen', () => {
    expect(block('.tabbar-link')).toMatch(/min-width:\s*0/)
  })
  it('m3-2 B3: tab labels use the small mockup size so long RU/UZ labels are not cut at 360px', () => {
    expect(css).toMatch(/\.app-shell__tabbar \.tabbar-link \* \{[^}]*font-size:\s*1[01](\.5)?px/)
  })
  it('B2: --bar/--bart tokens exist in both themes', () => {
    expect(block(':root')).toMatch(/--bar:\s*#17212b/)
    expect(block(':root')).toMatch(/--bart:\s*#f2f4f6/)
    expect(block(":root[data-theme='light']")).toMatch(/--bar:\s*#ffffff/)
    expect(block(":root[data-theme='light']")).toMatch(/--bart:\s*#101317/)
  })
  it('B2: tabbar is painted from --bar and theme tokens', () => {
    const b = block('.app-shell__tabbar')
    expect(b).toMatch(/--tgui--surface_primary:\s*var\(--bar\)/)
    expect(b).toMatch(/--tgui--secondary_hint_color:\s*var\(--hint\)/)
    expect(b).toMatch(/--tgui--link_color:\s*var\(--acc\)/)
    expect(b).toMatch(/--tgui--secondary_fill:\s*var\(--chip\)/)
  })
  it('B4: delete label uses on-accent token, not hardcoded white', () => {
    expect(block('.settings-swipe-row__delete')).toMatch(/color:\s*var\(--acct\)/)
  })
})
