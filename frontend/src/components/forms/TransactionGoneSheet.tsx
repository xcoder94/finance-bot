import { useTranslation } from 'react-i18next'

import { FormSheet } from './FormSheet'

/**
 * The operation being edited stayed in the budget the person has just left: it cannot be opened
 * here. Said plainly, with one button that closes the form (nothing is lost silently).
 */
export function TransactionGoneSheet({ title, onClose }: { title: string; onClose: () => void }) {
  const { t } = useTranslation()
  return (
    <FormSheet
      open
      title={title}
      onClose={onClose}
      primaryLabel={t('familyChanged.transactionGoneClose')}
      onPrimary={onClose}
    >
      <div className="form-sheet-load-error" role="alert">
        <p>{t('familyChanged.transactionGone')}</p>
      </div>
    </FormSheet>
  )
}
