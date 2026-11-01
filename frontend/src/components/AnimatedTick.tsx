/** Check mark whose stroke draws itself (CSS .motion-tick). Final state = fully drawn. */
export function AnimatedTick({ size = 26, strokeWidth = 2 }: { size?: number; strokeWidth?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path className="motion-tick" pathLength={1} d="M3 8.5l3.2 3.2L13 4.8" />
    </svg>
  )
}
