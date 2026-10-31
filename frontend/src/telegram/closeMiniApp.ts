import { miniApp } from '@tma.js/sdk-react'

/** Minimise the Mini App so the user lands in the bot chat. No-op outside Telegram. */
export function closeMiniApp(): void {
  try {
    if (miniApp.close.isAvailable()) miniApp.close()
  } catch {
    // outside Telegram or unsupported client version
  }
}
