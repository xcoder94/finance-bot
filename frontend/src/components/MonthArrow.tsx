import { ChevronLeft, ChevronRight } from 'lucide-react'

type MonthArrowProps = {
  direction: 'prev' | 'next'
  label: string
  onClick: () => void
}

/** Month switch arrow: icon, 44x44 tap zone — the same on every screen with a month switch. */
export function MonthArrow({ direction, label, onClick }: MonthArrowProps) {
  const Icon = direction === 'prev' ? ChevronLeft : ChevronRight
  return (
    <button type="button" className="month-arrow" aria-label={label} onClick={onClick}>
      <Icon size={20} aria-hidden="true" />
    </button>
  )
}
