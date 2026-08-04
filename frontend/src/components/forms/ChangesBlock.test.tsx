import { describe, expect, it } from 'vitest'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { renderToStaticMarkup } from 'react-dom/server'
import { I18nextProvider } from 'react-i18next'

import ru from '../../i18n/locales/ru.json'
import { ChangesBlock } from './ChangesBlock'
import { FormSheet } from './FormSheet'

const testI18n = i18n.createInstance()
void testI18n.use(initReactI18next).init({
  resources: { ru: { translation: ru } },
  lng: 'ru',
  fallbackLng: 'ru',
  interpolation: { escapeValue: false },
})

function renderChangesBlock(lines: string[]) {
  return renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <ChangesBlock lines={lines} />
    </I18nextProvider>,
  )
}

describe('ChangesBlock', () => {
  it('renders nothing when lines empty', () => {
    expect(renderChangesBlock([])).toBe('')
  })

  it('renders title and lines', () => {
    const html = renderChangesBlock([
      '1 августа · создал Рустам',
      '2 августа · Дилноза: сумма 20 000 → 200 000',
    ])
    expect(html).toContain('Изменения')
    expect(html).toContain('1 августа · создал Рустам')
    expect(html).toContain('2 августа · Дилноза: сумма 20 000 → 200 000')
  })
})

function renderFormSheetWithChanges() {
  return renderToStaticMarkup(
    <I18nextProvider i18n={testI18n}>
      <FormSheet
        open
        title="t"
        onClose={() => undefined}
        changes={<ChangesBlock lines={['1 августа · создал Рустам']} />}
      >
        <div>field</div>
      </FormSheet>
    </I18nextProvider>,
  )
}

describe('FormSheet changes slot', () => {
  it('renders changes between fields and primary actions', () => {
    const html = renderFormSheetWithChanges()
    expect(html).toContain('Изменения')
    expect(html).toContain('1 августа · создал Рустам')
    const fieldsIndex = html.indexOf('form-sheet-fields')
    const changesIndex = html.indexOf('form-sheet-changes')
    const actionsIndex = html.indexOf('form-sheet-actions')
    expect(fieldsIndex).toBeGreaterThan(-1)
    expect(changesIndex).toBeGreaterThan(fieldsIndex)
    expect(actionsIndex).toBeGreaterThan(changesIndex)
  })
})
