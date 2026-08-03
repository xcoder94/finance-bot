import { ChartPie, House, Settings, Target, type LucideIcon } from 'lucide-react'

export const MAIN_TABS = [
  { path: '/', labelKey: 'nav.home', icon: House, end: true },
  { path: '/analytics', labelKey: 'nav.analytics', icon: ChartPie, end: false },
  { path: '/goals', labelKey: 'nav.goals', icon: Target, end: false },
  { path: '/settings', labelKey: 'nav.settings', icon: Settings, end: false },
] as const satisfies ReadonlyArray<{
  path: string
  labelKey: string
  icon: LucideIcon
  end: boolean
}>
