import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

// B18: while the wallets list failed there is no «Добавить кошелёк»; member 404 has its own text
describe('settings error states (B18)', () => {
  it('Wallets settings gives the add action only when the list loaded', () => {
    const src = readFileSync(join(__dirname, 'WalletsSettingsPage.tsx'), 'utf8')
    expect(src).toContain("actionLabel={loadState.status === 'success' ? t('settings.addWallet') : undefined}")
    expect(src).toContain("onAction={loadState.status === 'success' ? openCreateForm : undefined}")
  })
  it('wrong member id shows «Участник не найден», not the load error', () => {
    const src = readFileSync(join(__dirname, 'MemberDetailPage.tsx'), 'utf8')
    expect(src).toContain("t('settings.membersScreen.notFound')")
  })
})
