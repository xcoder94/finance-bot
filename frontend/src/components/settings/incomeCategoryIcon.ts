import {
  BriefcaseBusiness,
  CircleDollarSign,
  CreditCard,
  Folder,
  Gift,
  House,
  PartyPopper,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react'

const KEYWORD_ICONS: ReadonlyArray<[string, LucideIcon]> = [
  ['зарплат', CircleDollarSign],
  ['salary', CircleDollarSign],
  ['ish haqi', CircleDollarSign],
  ['freelance', BriefcaseBusiness],
  ['фриланс', BriefcaseBusiness],
  ['gift', Gift],
  ['подар', Gift],
  ['sovg', Gift],
  ['bonus', PartyPopper],
  ['бонус', PartyPopper],
  ['dividend', TrendingUp],
  ['invest', TrendingUp],
  ['инвест', TrendingUp],
  ['rent', House],
  ['аренд', House],
  ['ijara', House],
  ['cashback', CreditCard],
  ['кэшбэк', CreditCard],
]

export function getIncomeCategoryIcon(name: string): LucideIcon {
  const lower = name.toLowerCase()

  for (const [keyword, Icon] of KEYWORD_ICONS) {
    if (lower.includes(keyword)) {
      return Icon
    }
  }

  return Folder
}
