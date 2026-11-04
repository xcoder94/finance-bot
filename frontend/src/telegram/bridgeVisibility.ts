import { on } from '@tma.js/sdk-react'

type BridgeOn = (
  name: 'visibility_changed',
  cb: (payload: { is_visible?: boolean }) => void,
) => () => void

/**
 * Calls onVisible when the Telegram client reports (Mini Apps bridge event visibility_changed) that
 * the app became visible. Telegram does not always fire the browser visibilitychange event, so
 * screens that refresh on return listen to both. No bridge (plain browser, tests): a no-op.
 */
export function subscribeBridgeVisible(
  onVisible: () => void,
  subscribe: BridgeOn = on as unknown as BridgeOn,
): () => void {
  try {
    const off = subscribe('visibility_changed', (payload) => {
      if (payload?.is_visible) onVisible()
    })
    return () => {
      try {
        off()
      } catch {
        // already gone
      }
    }
  } catch {
    return () => {}
  }
}
