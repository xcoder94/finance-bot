import { describe, expect, it } from 'vitest'
import { Folder } from 'lucide-react'

import { getExpenseCategoryIcon } from './expenseCategoryIcon'
import { getIncomeCategoryIcon } from './incomeCategoryIcon'

const EXPENSE = [
  'Еда', 'Продукты', 'Кафе и доставка', 'Транспорт', 'Такси и проезд', 'Автомобиль', 'Дом',
  'Аренда', 'Коммуналка и связь', 'Ремонт и вещи для дома', 'Дети', 'Учёба и кружки',
  'Детские товары', 'Здоровье', 'Аптека', 'Врачи', 'Тои и подарки', 'Тои и маърака', 'Подарки',
  'Помощь родным', 'Личное и досуг', 'Одежда', 'Красота и уход', 'Развлечения и подписки',
]
const INCOME = ['Зарплата', 'Бизнес и подработка', 'Переводы и подарки']

describe('seed category icons', () => {
  it.each(EXPENSE)('expense "%s" has a specific icon', (name) => {
    expect(getExpenseCategoryIcon(name)).not.toBe(Folder)
  })
  it.each(INCOME)('income "%s" has a specific icon', (name) => {
    expect(getIncomeCategoryIcon(name)).not.toBe(Folder)
  })
})
