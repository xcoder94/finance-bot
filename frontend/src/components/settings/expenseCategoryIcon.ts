import {
  BookOpen,
  CarFront,
  Clapperboard,
  Coffee,
  Folder,
  Fuel,
  Flame,
  Hospital,
  House,
  Lightbulb,
  PawPrint,
  Pill,
  Plane,
  Shirt,
  ShoppingCart,
  Utensils,
  Wrench,
  type LucideIcon,
} from 'lucide-react'

const KEYWORD_ICONS: ReadonlyArray<[string, LucideIcon]> = [
  ['еда', Utensils],
  ['food', Utensils],
  ['ovqat', Utensils],
  ['рестор', Utensils],
  ['cafeteria', Coffee],
  ['транспорт', CarFront],
  ['transport', CarFront],
  ['taxi', CarFront],
  ['taksi', CarFront],
  ['benzin', Fuel],
  ['бензин', Fuel],
  ['жкх', Lightbulb],
  ['kommunal', Lightbulb],
  ['коммун', Lightbulb],
  ['utility', Lightbulb],
  ['electric', Lightbulb],
  ['elektr', Lightbulb],
  ['gas', Flame],
  ['gaz', Flame],
  ['здоров', Hospital],
  ['health', Hospital],
  ['salomat', Hospital],
  ['apteka', Pill],
  ['аптек', Pill],
  ['покуп', ShoppingCart],
  ['shop', ShoppingCart],
  ['xarid', ShoppingCart],
  ['market', ShoppingCart],
  ['развле', Clapperboard],
  ['entertain', Clapperboard],
  ['kino', Clapperboard],
  ['кино', Clapperboard],
  ['образ', BookOpen],
  ['education', BookOpen],
  ['ta\'lim', BookOpen],
  ['одежд', Shirt],
  ['clothing', Shirt],
  ['kiyim', Shirt],
  ['дом', House],
  ['home', House],
  ['uy ', House],
  ['repair', Wrench],
  ['remont', Wrench],
  ['ремонт', Wrench],
  ['travel', Plane],
  ['путеш', Plane],
  ['sayohat', Plane],
  ['pet', PawPrint],
  ['живот', PawPrint],
  ['hayvon', PawPrint],
]

export function getExpenseCategoryIcon(name: string): LucideIcon {
  const lower = name.toLowerCase()

  for (const [keyword, Icon] of KEYWORD_ICONS) {
    if (lower.includes(keyword)) {
      return Icon
    }
  }

  return Folder
}
