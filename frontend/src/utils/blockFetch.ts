export type BlockState<T> = { status: 'loading' } | { status: 'error' } | { status: 'success'; data: T }

export type BlockFetcher = {
  load: () => Promise<void>
  retry: () => Promise<void>
  /** Silent re-request: shows the old data meanwhile, keeps it on failure. */
  refresh: () => Promise<void>
  dispose: () => void
}

type Deps<T> = {
  fetcher: () => Promise<T>
  onChange: (state: BlockState<T>) => void
}

/** Framework-free state of one fetched block (e.g. the history summary): load, retry, silent refresh. */
export function createBlockFetcher<T>({ fetcher, onChange }: Deps<T>): BlockFetcher {
  let state: BlockState<T> = { status: 'loading' }
  let seq = 0
  let disposed = false

  const emit = (next: BlockState<T>) => {
    state = next
    if (!disposed) onChange(state)
  }

  const load = async () => {
    const mine = ++seq
    emit({ status: 'loading' })
    try {
      const data = await fetcher()
      if (mine === seq) emit({ status: 'success', data })
    } catch {
      if (mine === seq) emit({ status: 'error' })
    }
  }

  return {
    load,
    retry: load,
    async refresh() {
      if (disposed) return
      const mine = ++seq
      try {
        const data = await fetcher()
        if (mine === seq) emit({ status: 'success', data })
      } catch {
        if (mine !== seq) return
        // nothing to keep on screen yet: show the error with retry instead of an endless skeleton
        if (state.status === 'loading') emit({ status: 'error' })
      }
    },
    dispose() {
      disposed = true
    },
  }
}
