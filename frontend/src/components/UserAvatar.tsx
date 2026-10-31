import { useState } from 'react'
import { useRawInitData } from '@tma.js/sdk-react'

import { useAuthStore } from '../store/authStore'
import { parseInitDataUser, userInitials } from '../utils/userAvatar'

type UserAvatarViewProps = {
  photoUrl: string | null
  initials: string
  className?: string
}

export function UserAvatarView({ photoUrl, initials, className }: UserAvatarViewProps) {
  const [failed, setFailed] = useState(false)
  const cls = `user-avatar${className ? ` ${className}` : ''}`

  if (photoUrl && !failed) {
    return (
      <span className={cls}>
        <img
          className="user-avatar__img"
          src={photoUrl}
          alt=""
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
        />
      </span>
    )
  }
  return (
    <span className={cls} aria-hidden="true">
      <span className="user-avatar__initials">{initials}</span>
    </span>
  )
}

/** Current user's avatar: Telegram photo_url, else initials. */
export function UserAvatar({ className }: { className?: string }) {
  const rawInitData = useRawInitData()
  const user = useAuthStore((state) => state.user)
  const tg = parseInitDataUser(rawInitData)
  const initials = userInitials(tg.firstName ?? user?.firstName ?? null, tg.lastName)
  return <UserAvatarView photoUrl={tg.photoUrl} initials={initials} className={className} />
}
