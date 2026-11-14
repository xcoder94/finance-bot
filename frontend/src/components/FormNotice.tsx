import { Button } from '@telegram-apps/telegram-ui'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

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

/** The "Try again" control inside a message: one look and one tap target (36 px) on every form. */
export function NoticeRetry({ onClick, disabled = false }: { onClick: () => void; disabled?: boolean }) {
  const { t } = useTranslation()
  return (
    <Button mode="plain" size="s" className="form-notice__retry" onClick={onClick} disabled={disabled}>
      {t('auth.retry')}
    </Button>
  )
}
