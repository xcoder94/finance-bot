import type { ReactNode } from 'react'

/** The one screen header style (B14): left-aligned like Goals / Settings. */
export function ScreenTitle({ children }: { children: ReactNode }) {
  return <h1 className="screen-title">{children}</h1>
}
