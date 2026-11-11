import { useCallback, useEffect, useRef, useState } from 'react'

import { resolveFetchState, type FetchState, type KeyedFetchState } from '../utils/homeFetchState'

/**
 * Home data block: shows `initialData` (cache) at once, then fetches.
 * `initialData` is deliberately NOT an effect dependency: callers pass a fresh cache read on every
 * render (a forced fetch stores a new array), and depending on it re-ran the fetch forever.
 * A new fetch starts only when fetcher, trigger, retry or dataKey change.
 */
export function useFetchBlock<T>(
  fetcher: () => Promise<T>,
  trigger: unknown,
  initialData: T | null = null,
  dataKey = 'static',
) {
  const initialRef = useRef<T | null>(initialData)
  initialRef.current = initialData
  const [stored, setStored] = useState<KeyedFetchState<T>>(() => ({
    key: dataKey,
    state: initialData ? { status: 'success', data: initialData } : { status: 'loading' },
  }))
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    const seed = initialRef.current
    setStored({
      key: dataKey,
      state: seed ? { status: 'success', data: seed } : { status: 'loading' },
    })

    void fetcher()
      .then((data) => {
        if (!cancelled) {
          setStored({ key: dataKey, state: { status: 'success', data } })
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStored({ key: dataKey, state: { status: 'error' } })
        }
      })

    return () => {
      cancelled = true
    }
  }, [fetcher, trigger, retryCount, dataKey])

  const retry = useCallback(() => {
    setRetryCount((count) => count + 1)
  }, [])

  const state: FetchState<T> = resolveFetchState(stored, dataKey, initialData)
  return { state, retry }
}
