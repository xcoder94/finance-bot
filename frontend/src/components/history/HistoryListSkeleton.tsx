const HISTORY_LIST_SKELETON_ROWS = 6

export function HistoryListSkeleton() {
  return (
    <div className="history-list-skeleton" aria-hidden="true">
      {Array.from({ length: HISTORY_LIST_SKELETON_ROWS }, (_, index) => (
        <div key={index} className="history-list-skeleton__row">
          <div className="history-list-skeleton__line history-list-skeleton__line--left" />
          <div className="history-list-skeleton__line history-list-skeleton__line--right" />
        </div>
      ))}
    </div>
  )
}
