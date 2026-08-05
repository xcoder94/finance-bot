import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const settingsDir = dirname(fileURLToPath(import.meta.url))

function readSettingsSource(filename: string): string {
  return readFileSync(join(settingsDir, filename), 'utf8')
}

describe('settings form delete wiring', () => {
  it('WalletsSettingsPage passes onDelete that opens delete sheet', () => {
    const source = readSettingsSource('WalletsSettingsPage.tsx')
    expect(source).toContain('onDelete={')
    expect(source).toContain("setSheetState({ kind: 'delete', walletId: formWallet.id })")
    expect(source).toContain('formWallet.is_personal || isOwner')
  })

  it('IncomeCategoriesSettingsPage passes onDelete that opens delete sheet', () => {
    const source = readSettingsSource('IncomeCategoriesSettingsPage.tsx')
    expect(source).toContain('onDelete={')
    expect(source).toContain("setSheetState({ kind: 'delete', categoryId: formCategory.id })")
    expect(source).toContain('sheetState.mode === \'edit\' && isOwner && formCategory')
  })

  it('ExpenseSubcategoriesSettingsPage passes onDelete that opens subcategory delete sheet', () => {
    const source = readSettingsSource('ExpenseSubcategoriesSettingsPage.tsx')
    expect(source).toContain('onDelete={')
    expect(source).toContain("kind: 'delete'")
    expect(source).toContain("target: 'subcategory'")
    expect(source).toContain('categoryId: formCategory.id')
    expect(source).toContain('sheetState.mode === \'edit\' && isOwner && formCategory')
  })
})
