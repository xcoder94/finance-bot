import { useTranslation } from 'react-i18next'

type ChangesBlockProps = {
  lines: string[]
}

export function ChangesBlock({ lines }: ChangesBlockProps) {
  const { t } = useTranslation()

  if (lines.length === 0) {
    return null
  }

  return (
    <div className="form-sheet-changes">
      <div className="form-sheet-changes__title">{t('formSheet.changes')}</div>
      <div className="form-sheet-changes__list">
        {lines.map((line) => (
          <div key={line} className="form-sheet-changes__line">
            {line}
          </div>
        ))}
      </div>
    </div>
  )
}
