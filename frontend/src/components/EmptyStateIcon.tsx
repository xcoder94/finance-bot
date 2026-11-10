/** Icon of every empty state (B13): a real glyph on a soft tile, never an empty grey square. */
export function EmptyStateIcon({ className }: { className: string }) {
  return (
    <div className={`${className} empty-state-icon`} aria-hidden="true">
      <svg
        className="empty-state-icon__glyph"
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M3 13l2.2-6.2A2 2 0 0 1 7.1 5.5h9.8a2 2 0 0 1 1.9 1.3L21 13" />
        <path d="M3 13v5a1.5 1.5 0 0 0 1.5 1.5h15A1.5 1.5 0 0 0 21 18v-5h-5.2a3.8 3.8 0 0 1-7.6 0H3z" />
      </svg>
    </div>
  )
}
