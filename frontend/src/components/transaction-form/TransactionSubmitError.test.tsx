import { describe, expect, it, vi } from 'vitest'

// At 320 px the message sits under the fields, below the visible part of the sheet: it must scroll
// itself into view. A refusal because the family changed is not retried with the same button.
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('@telegram-apps/telegram-ui', () => ({
  Spinner: () => null,
  Text: ({ children }: { children: unknown }) => children,
  Button: () => null,
}))
vi.mock('../../i18n/t', () => ({ t: (key: string) => key }))
vi.mock('../../i18n', () => ({ default: { language: 'ru' } }))

const { TransactionSubmitError } = await import('./TransactionFormShared')
const { FormNotice } = await import('../FormNotice')
const { findAll } = await import('../../test/elementTree')

const render = (messageKey?: string) =>
  (TransactionSubmitError as unknown as (p: object) => never)({ messageKey, onRetry: () => undefined })

describe('TransactionSubmitError', () => {
  it('scrolls itself into view when it appears', () => {
    const root = render('familyChanged.message') as unknown as { type: (p: object) => { ref: (el: unknown) => void }; props: { reveal: boolean } }
    expect(root.type).toBe(FormNotice)
    expect(root.props.reveal).toBe(true)
    const notice = FormNotice(root.props as never) as unknown as { ref: (el: unknown) => void }
    const scrollIntoView = vi.fn()
    notice.ref({ scrollIntoView })
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
  })

  it('the usual failure keeps the retry button', () => {
    expect(findAll(render('addTransaction.submitError'), (e) => e.type !== 'div' && typeof e.type === 'function' && e.props.onClick !== undefined)).toHaveLength(1)
  })

  it('a family change has no retry button', () => {
    expect(findAll(render('familyChanged.message'), (e) => e.props.onClick !== undefined)).toHaveLength(0)
    expect(findAll(render('familyChanged.generic'), (e) => e.props.onClick !== undefined)).toHaveLength(0)
  })
})
