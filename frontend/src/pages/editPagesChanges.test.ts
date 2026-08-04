import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const pagesDir = dirname(fileURLToPath(import.meta.url))

function readPageSource(filename: string): string {
  return readFileSync(join(pagesDir, filename), 'utf8')
}

const changesProp = 'changes={<ChangesBlock lines={transaction.changes ?? []} />}'

describe('edit pages change log wiring', () => {
  it('EditExpensePage passes changes to FormSheet', () => {
    expect(readPageSource('EditExpensePage.tsx')).toContain(changesProp)
  })

  it('EditIncomePage passes changes to FormSheet', () => {
    expect(readPageSource('EditIncomePage.tsx')).toContain(changesProp)
  })

  it('EditTransferPage passes changes to FormSheet', () => {
    expect(readPageSource('EditTransferPage.tsx')).toContain(changesProp)
  })
})

describe('edit pages have no operation type switch', () => {
  it('EditExpensePage only updates expense transactions', () => {
    const source = readPageSource('EditExpensePage.tsx')
    expect(source).toContain('updateExpenseTransaction')
    expect(source).not.toContain('updateIncomeTransaction')
    expect(source).not.toContain('updateTransferTransaction')
    expect(source).not.toMatch(/add-expense|add-income|add-transfer/)
  })

  it('EditIncomePage only updates income transactions', () => {
    const source = readPageSource('EditIncomePage.tsx')
    expect(source).toContain('updateIncomeTransaction')
    expect(source).not.toContain('updateExpenseTransaction')
    expect(source).not.toContain('updateTransferTransaction')
    expect(source).not.toMatch(/add-expense|add-income|add-transfer/)
  })

  it('EditTransferPage only updates transfer transactions', () => {
    const source = readPageSource('EditTransferPage.tsx')
    expect(source).toContain('updateTransferTransaction')
    expect(source).not.toContain('updateExpenseTransaction')
    expect(source).not.toContain('updateIncomeTransaction')
    expect(source).not.toMatch(/add-expense|add-income|add-transfer/)
  })
})
