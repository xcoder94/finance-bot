import { useTranslation } from 'react-i18next'

import type { OnboardingState } from '../../api/me'
import { CountUp } from '../CountUp'
import { groupThousands } from '../../utils/groupThousands'

function formatSumNumber(value: number): string {
  const sign = value < 0 ? '-' : ''
  return `${sign}${groupThousands(Math.abs(value))}`
}

/** Longer amounts step the font down so «сум»/«so'm» is never cut off on 360px. */
export function sumSizeClass(text: string): string {
  if (text.length >= 11) return ' home-left__value--xlong'
  if (text.length >= 9) return ' home-left__value--long'
  return ''
}

/** Balance card (30px mono): shrink from 15 characters of text (owner decision) so the unit stays visible at 360px; the digit count differs by language («so'm» vs «сум»). */
export function balanceSizeClass(text: string): string {
  if (text.length >= 17) return ' home-figures-card__balance--xlong'
  if (text.length >= 15) return ' home-figures-card__balance--long'
  return ''
}

function SumAmount({ id, value, negative }: { id: string; value: number; negative: boolean }) {
  const { t } = useTranslation()
  const text = formatSumNumber(value)
  return (
    <div
      className={`home-left__value${negative ? ' home-left__value--negative' : ''}${sumSizeClass(text)}`}
    >
      <CountUp id={id} value={value} format={formatSumNumber} /> <span className="home-left__unit">{t('home.unitSum')}</span>
    </div>
  )
}

export function HomeLeftBlock({
  perDay,
  days,
  noIncome = false,
}: {
  perDay: number | null
  days: number | null
  noIncome?: boolean
}) {
  const { t } = useTranslation()
  return (
    <div className="home-left">
      <div className="home-left__plate">
        <div className="home-left__label">{t('home.leftPerDay')}</div>
        {perDay === null || noIncome ? (
          <div className="home-left__value">—</div>
        ) : (
          <SumAmount id="home-per-day" value={perDay} negative={perDay < 0} />
        )}
        <div className="home-left__hint">
          {noIncome
            ? t('home.leftPerDayNoIncome')
            : perDay === null || days === null
              ? t('home.leftPerDayDone')
              : t('home.leftPerDayHint', { days })}
        </div>
      </div>
    </div>
  )
}

export function HomeLeftSkeleton() {
  return (
    <div className="home-left" aria-hidden="true">
      {[0].map((key) => (
        <div key={key} className="home-left__plate home-left__plate--skeleton">
          <div className="home-skeleton__line home-skeleton__line--label" />
          <div className="home-skeleton__line home-left__skeleton-value" />
        </div>
      ))}
    </div>
  )
}

export function HomeOnboardingCard({
  steps,
  onStart,
  onStartIncome,
  onClose,
}: {
  steps: OnboardingState['steps']
  onStart: () => void
  onStartIncome: () => void
  onClose: () => void
}) {
  const { t } = useTranslation()
  const items = [
    { done: steps.firstOperation, label: t('home.onboarding.step1') },
    { done: steps.defaultWalletChecked, label: t('home.onboarding.step2') },
    { done: steps.familyInvited, label: t('home.onboarding.step3') },
  ]
  const currentIndex = items.findIndex((item) => !item.done)
  return (
    <div className="home-onboarding">
      <button
        type="button"
        className="home-onboarding__close"
        aria-label={t('home.onboarding.close')}
        onClick={onClose}
      >
        ×
      </button>
      <div className="home-onboarding__title">{t('home.onboarding.title')}</div>
      <ol className="home-onboarding__steps">
        {items.map((item, index) => {
          const state = item.done ? 'done' : index === currentIndex ? 'current' : 'next'
          return (
            <li
              key={index}
              className={`home-onboarding__step home-onboarding__step--${state}`}
              aria-current={state === 'current' ? 'step' : undefined}
            >
              <span className="home-onboarding__num">
                {item.done ? (
                  <svg
                    className="home-onboarding__check"
                    width="14"
                    height="14"
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M3 8.5l3.2 3.2L13 4.8" />
                  </svg>
                ) : (
                  index + 1
                )}
              </span>
              <span className="home-onboarding__label">{item.label}</span>
            </li>
          )
        })}
      </ol>
      {currentIndex === 0 ? (
        <button type="button" className="home-onboarding__cta" onClick={onStart}>
          {t('home.onboarding.cta')}
        </button>
      ) : currentIndex === 1 ? (
        <button type="button" className="home-onboarding__cta" onClick={onStartIncome}>
          {t('home.onboarding.ctaIncome')}
        </button>
      ) : null}
    </div>
  )
}

export { FailBox as HomeFailBox } from '../FailBox'
