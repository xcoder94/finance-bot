import { useTranslation } from 'react-i18next'

import type { OnboardingState } from '../../api/me'
import { formatMillions, trendMonthLabel, type TrendBar } from '../../utils/homeTrend'
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
  remaining,
  perDay,
  days,
  noIncome = false,
}: {
  remaining: number
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
      <div className="home-left__plate">
        <div className="home-left__label">{t('home.leftTotal')}</div>
        <SumAmount id="home-left-total" value={remaining} negative={remaining < 0} />
        <div className="home-left__hint">{t('home.leftTotalHint')}</div>
      </div>
    </div>
  )
}

export function HomeLeftSkeleton() {
  return (
    <div className="home-left" aria-hidden="true">
      {[0, 1].map((key) => (
        <div key={key} className="home-left__plate home-left__plate--skeleton">
          <div className="home-skeleton__line home-skeleton__line--label" />
          <div className="home-skeleton__line home-left__skeleton-value" />
        </div>
      ))}
    </div>
  )
}

export function HomeTrendCard({ bars }: { bars: TrendBar[] }) {
  const { t } = useTranslation()
  return (
    <div className="home-trend">
      <div className="home-trend__head">
        <div className="home-trend__title">{t('home.trendTitle')}</div>
        <div className="home-trend__unit">{t('home.trendUnit')}</div>
      </div>
      <div className="home-trend__cols">
        {bars.map((bar) => {
          return (
            <div
              key={`${bar.year}-${bar.month}`}
              className={`home-trend__col${bar.current ? ' home-trend__col--current' : ''}`}
            >
              <div className="home-trend__value">{formatMillions(bar.expense)}</div>
              <div className="home-trend__bar" style={{ height: `${bar.heightPx}px` }} />
              <div className="home-trend__month">{trendMonthLabel(bar.month)}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/** Same box as HomeTrendCard so the page below does not move when the trend arrives. */
export function HomeTrendPlaceholder() {
  const { t } = useTranslation()
  return (
    <div className="home-trend home-trend--ph" aria-hidden="true">
      <div className="home-trend__head">
        <div className="home-trend__title">{t('home.trendTitle')}</div>
        <div className="home-trend__unit">{t('home.trendUnit')}</div>
      </div>
      <div className="home-trend__cols" />
    </div>
  )
}

export function HomeOnboardingCard({
  steps,
  onStart,
  onClose,
}: {
  steps: OnboardingState['steps']
  onStart: () => void
  onClose: () => void
}) {
  const { t } = useTranslation()
  const items = [
    { done: steps.firstOperation, label: t('home.onboarding.step1') },
    { done: steps.defaultWalletChecked, label: t('home.onboarding.step2') },
    { done: steps.familyInvited, label: t('home.onboarding.step3') },
  ]
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
        {items.map((item, index) => (
          <li
            key={index}
            className={`home-onboarding__step${item.done ? ' home-onboarding__step--done' : ''}`}
          >
            <span className="home-onboarding__num">{index + 1}</span>
            <span className="home-onboarding__label">{item.label}</span>
          </li>
        ))}
      </ol>
      <button type="button" className="home-onboarding__cta" onClick={onStart}>
        {t('home.onboarding.cta')}
      </button>
    </div>
  )
}

export function HomeFailBox({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="home-fail" role="alert">
      <div className="home-fail__icon" aria-hidden="true">!</div>
      <div className="home-fail__title">{t('home.loadError')}</div>
      <div className="home-fail__hint">{t('home.failHint')}</div>
      <button type="button" className="home-fail__btn" onClick={onRetry}>
        {t('home.retry')}
      </button>
    </div>
  )
}
