import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Button, Spinner, Text } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

type FetchState<T> =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; data: T }

export function useFetchBlock<T>(fetcher: () => Promise<T>, trigger: unknown, enabled: boolean) {
  const [state, setState] = useState<FetchState<T>>({ status: 'loading' })
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    if (!enabled) {
      return
    }

    let cancelled = false
    setState((current) => (current.status === 'success' ? current : { status: 'loading' }))

    void fetcher()
      .then((data) => {
        if (!cancelled) {
          setState({ status: 'success', data })
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState((current) => (current.status === 'success' ? current : { status: 'error' }))
        }
      })

    return () => {
      cancelled = true
    }
  }, [fetcher, trigger, retryCount, enabled])

  const retry = useCallback(() => {
    setRetryCount((count) => count + 1)
  }, [])

  return { state, retry }
}

export function BlockError({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation()

  return (
    <div className="home-block-error" role="alert">
      <Text>{t('home.loadError')}</Text>
      <Button mode="plain" size="s" onClick={onRetry}>
        {t('auth.retry')}
      </Button>
    </div>
  )
}

type AnalyticsCardProps = {
  title: string
  loading: boolean
  error: boolean
  onRetry?: () => void
  children: ReactNode
  onClick?: () => void
  compact?: boolean
}

export function AnalyticsCard({
  title,
  loading,
  error,
  onRetry,
  children,
  onClick,
  compact = false,
}: AnalyticsCardProps) {
  const { t } = useTranslation()
  const className = [
    'analytics-card',
    onClick ? 'analytics-card--clickable' : '',
    compact ? 'analytics-card--compact' : '',
  ]
    .filter(Boolean)
    .join(' ')

  const content = (
    <>
      <Text weight="2" className="analytics-card__title">
        {title}
      </Text>
      {error && onRetry ? <BlockError onRetry={onRetry} /> : null}
      {loading ? (
        <div className="home-block-loading" role="status" aria-live="polite">
          <Spinner size="m" aria-hidden="true" />
          <span className="visually-hidden">{t('home.loading')}</span>
        </div>
      ) : null}
      {!loading && !error ? children : null}
    </>
  )

  if (onClick) {
    return (
      <button type="button" className={className} onClick={onClick}>
        {content}
      </button>
    )
  }

  return <section className={className}>{content}</section>
}

type MetricValueProps = {
  loading?: boolean
  unavailable?: boolean
  className?: string
  children: string
}

export function MetricValue({ loading = false, unavailable, className, children }: MetricValueProps) {
  if (loading) {
    return <Spinner size="s" />
  }
  if (unavailable) {
    return <Text>—</Text>
  }
  return (
    <Text className={className} weight="2">
      {children}
    </Text>
  )
}
