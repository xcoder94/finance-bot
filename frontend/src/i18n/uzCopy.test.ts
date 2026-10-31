import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { goalDueLabel, goalLeftLine } from '../components/goals/goalProgress'
import { limitMembers, limitSubcategories } from '../constants/entityLimits'
import { buildDeleteConfirmBody } from '../utils/formConfirmCopy'
import { dayCountLabel } from '../utils/dayCountLabel'
import {
  buildEntityDeleteTitle,
  buildExpenseParentDeleteIntro,
  buildSubcategoryDeleteIntro,
  buildWalletDeleteIntro,
  formatEntityTransactionSubtitle,
} from '../utils/entityDeleteConfirmCopy'
import { trendMonthLabel } from '../utils/homeTrend'
import { leaveConfirmBody, memberConfirmCancel, transferConfirmAction } from '../utils/memberConfirmCopy'
import { membersGroupTitle } from '../utils/memberDisplay'
import {
  expenseCategoriesSubtitle,
  incomeCategoriesSubtitle,
  notificationsSubtitle,
  walletsSubtitle,
} from '../utils/settingsSubtitles'
import { formatChartsEmptyMonth } from '../utils/analyticsChartsTab'
import { formatMonthLabel } from '../utils/periodFilter'
import i18n from './index'
import uz from './locales/uz.json'

const CYRILLIC = /[Ѐ-ӿ]/

describe('UZ copy built outside components has no Russian', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('uz')
  })
  afterEach(async () => {
    await i18n.changeLanguage('ru')
  })

  it('delete confirmations', () => {
    const texts = [
      buildEntityDeleteTitle('Humo'),
      buildWalletDeleteIntro(0),
      buildWalletDeleteIntro(9),
      buildExpenseParentDeleteIntro(0, 2),
      buildExpenseParentDeleteIntro(5, 2),
      buildSubcategoryDeleteIntro(3, 'Oziq-ovqat', 2026),
      formatEntityTransactionSubtitle(0),
      formatEntityTransactionSubtitle(9),
      buildDeleteConfirmBody({ comment: null, categoryLabel: 'Taksi', amount: 32000, currency: 'UZS' }),
    ]
    texts.forEach((text) => expect(text).not.toMatch(CYRILLIC))
    expect(formatEntityTransactionSubtitle(9)).toBe('9 ta operatsiya')
    expect(buildEntityDeleteTitle('Humo')).toBe("«Humo» o'chirilsinmi?")
  })

  it('member confirmations, limits, subtitles, goals', () => {
    const texts = [
      leaveConfirmBody('Oila'),
      memberConfirmCancel(),
      transferConfirmAction(),
      limitMembers(),
      limitSubcategories('Oziq-ovqat'),
      membersGroupTitle(2, true),
      walletsSubtitle(2, 1),
      incomeCategoriesSubtitle(3),
      expenseCategoriesSubtitle(4, 9),
      notificationsSubtitle(true, true),
      notificationsSubtitle(false, false),
      goalLeftLine({ done: false, balance: 10, target: 50, currency: 'UZS' }) ?? '',
      goalLeftLine({ done: true, balance: 10, target: 50, currency: 'UZS' }) ?? '',
      goalDueLabel(null, null, false),
      goalDueLabel('2026-12-31', null, false),
      dayCountLabel(14),
      trendMonthLabel(10),
      formatChartsEmptyMonth({ year: 2026, month: 10 }),
      formatMonthLabel({ year: 2026, month: 8 }),
    ]
    texts.forEach((text) => expect(text).not.toMatch(CYRILLIC))
    expect(expenseCategoriesSubtitle(4, 9)).toBe('4 ta asosiy · 9 ta ichki toifa')
    expect(dayCountLabel(14)).toBe('14 kun')
    expect(formatMonthLabel({ year: 2026, month: 8 })).toBe('2026-yil avgust')
  })
})

describe('RU plural forms stay correct after moving to i18n', () => {
  it('operations / subcategories agree with the number', () => {
    expect(formatEntityTransactionSubtitle(1)).toBe('1 операция')
    expect(formatEntityTransactionSubtitle(3)).toBe('3 операции')
    expect(formatEntityTransactionSubtitle(11)).toBe('11 операций')
    expect(formatEntityTransactionSubtitle(21)).toBe('21 операция')
    expect(buildWalletDeleteIntro(2)).toContain('2 операции останутся')
    expect(dayCountLabel(2)).toBe('2 дня')
    expect(dayCountLabel(12)).toBe('12 дней')
  })
})

describe('UZ Settings menu matches mvp3-strings', () => {
  it('uses «toifalari» and «Asosiy hamyon»', () => {
    const settings = (uz as { settings: Record<string, unknown> }).settings
    const toc = settings.toc as Record<string, string>
    expect(settings.wallets).toBe('Hamyonlar')
    expect(toc.defaultWallet).toBe('Asosiy hamyon')
    expect(settings.categoriesIncome).toBe('Daromad toifalari')
    expect(settings.categoriesExpense).toBe('Xarajat toifalari')
    expect(toc.members).toBe("A'zolar")
    expect(toc.notifications).toBe('Bildirishnomalar')
    expect(settings.language).toBe('Til')
  })
})
