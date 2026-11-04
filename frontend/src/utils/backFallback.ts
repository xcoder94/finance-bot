import { historyBackTarget } from './historyBackTarget'

/** Where the native Back button goes when there is no in-app history (page opened directly). */
export function backFallbackPath(pathname: string, locationState: unknown): string {
  if (pathname.startsWith('/edit-')) {
    return historyBackTarget(locationState) ?? '/history'
  }
  if (pathname === '/admin') {
    return '/settings'
  }
  if (/^\/wallets\/[^/]+\/?$/.test(pathname)) {
    return '/wallets'
  }
  return '/'
}
