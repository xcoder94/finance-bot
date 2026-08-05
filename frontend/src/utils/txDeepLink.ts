const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export type TxLaunchAction =
  | { kind: 'none' }
  | { kind: 'invalid' }
  | { kind: 'fetch'; transactionId: string }

function searchParamsFrom(search: string): URLSearchParams {
  const normalized = search.startsWith('?') ? search.slice(1) : search
  return new URLSearchParams(normalized)
}

export function parseTxParam(search: string): string | null {
  const tx = searchParamsFrom(search).get('tx')
  if (!tx || !UUID_RE.test(tx)) {
    return null
  }
  return tx
}

export function resolveTxLaunchAction(search: string): TxLaunchAction {
  const params = searchParamsFrom(search)
  const tx = params.get('tx')
  if (!tx) {
    return { kind: 'none' }
  }
  if (!UUID_RE.test(tx)) {
    return { kind: 'invalid' }
  }
  return { kind: 'fetch', transactionId: tx }
}

export function clearTxParamFromUrl(): void {
  const url = new URL(window.location.href)
  if (!url.searchParams.has('tx')) {
    return
  }
  url.searchParams.delete('tx')
  const search = url.searchParams.toString()
  const nextUrl = `${url.pathname}${search ? `?${search}` : ''}${url.hash}`
  window.history.replaceState(window.history.state, '', nextUrl)
}
