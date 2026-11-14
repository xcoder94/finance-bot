import type { ReactNode } from 'react'

import { revealMessage } from '../utils/revealMessage'

import type { NoticeKind } from '../utils/noticeKind'

const ICON: Record<NoticeKind, string> = { error: '!', warning: '!', info: 'i' }

/**
 * The one status message of every form (expense, income, transfer, goal, wallet, category, purchase):
 * same size, icon and left alignment; only the colour tells error / warning / hint apart.
 * `reveal` scrolls it into view above the sticky button row when it appears (forms inside a sheet).
 */
export function FormNotice({
  kind,
  children,
  reveal = false,
  role,
  className = '',
}: {
  kind: NoticeKind
  children: ReactNode
  reveal?: boolean
  role?: 'alert' | 'status'
  className?: string
}) {
  return (
    <div
      className={`form-notice form-notice--${kind}${className ? ` ${className}` : ''}`}
      role={role ?? (kind === 'info' ? 'status' : 'alert')}
      ref={reveal ? revealMessage : undefined}
    >
      <span className="form-notice__icon" aria-hidden="true">
        {ICON[kind]}
      </span>
      <div className="form-notice__body">{children}</div>
    </div>
  )
}
