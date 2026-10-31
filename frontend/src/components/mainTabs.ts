import { ChartPie, House, ShoppingCart, Target, type LucideIcon } from 'lucide-react'

export const MAIN_TABS = [
  { path: '/', labelKey: 'nav.home', icon: House, end: true },
  { path: '/shopping', labelKey: 'nav.shopping', icon: ShoppingCart, end: false },
  { path: '/analytics', labelKey: 'nav.analytics', icon: ChartPie, end: false },
  { path: '/goals', labelKey: 'nav.goals', icon: Target, end: false },
] as const satisfies ReadonlyArray<{
  path: string
  labelKey: string
  icon: LucideIcon
  end: boolean
}>
