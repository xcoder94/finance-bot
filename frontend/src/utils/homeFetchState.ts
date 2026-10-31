export type FetchState<T> =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; data: T }

export type KeyedFetchState<T> = { key: string; state: FetchState<T> }

/** A stored result is only valid for the key (month) it was fetched for. */
export function resolveFetchState<T>(
  stored: KeyedFetchState<T>,
  key: string,
  initialData: T | null,
): FetchState<T> {
  if (stored.key === key) {
    return stored.state
  }
  return initialData !== null ? { status: 'success', data: initialData } : { status: 'loading' }
}
