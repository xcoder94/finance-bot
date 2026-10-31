import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'

import { UserAvatarView } from './UserAvatar'

describe('UserAvatarView', () => {
  it('shows the photo when photo_url is present', () => {
    const html = renderToStaticMarkup(<UserAvatarView photoUrl="https://t.me/a.jpg" initials="AK" />)
    expect(html).toContain('<img')
    expect(html).toContain('https://t.me/a.jpg')
    expect(html).not.toContain('AK')
  })
  it('falls back to initials without photo_url', () => {
    const html = renderToStaticMarkup(<UserAvatarView photoUrl={null} initials="AK" />)
    expect(html).not.toContain('<img')
    expect(html).toContain('AK')
  })
})
