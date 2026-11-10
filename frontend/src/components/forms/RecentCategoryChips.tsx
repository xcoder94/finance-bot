import type { RecentChip } from '../../utils/recentCategories'

type RecentCategoryChipsProps = {
  chips: RecentChip[]
  selectedId: string
  onSelect: (chip: RecentChip) => void
}

export function RecentCategoryChips({ chips, selectedId, onSelect }: RecentCategoryChipsProps) {
  if (chips.length === 0) {
    return null
  }

  return (
    <div className="date-chips recent-category-chips" role="group">
      {chips.map((chip) => (
        <button
          key={chip.id}
          type="button"
          className={`date-chip${chip.id === selectedId ? ' date-chip--selected' : ''}`}
          aria-pressed={chip.id === selectedId}
          onClick={() => onSelect(chip)}
        >
          {chip.label}
        </button>
      ))}
    </div>
  )
}
