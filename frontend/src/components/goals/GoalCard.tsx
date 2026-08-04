import type { GoalResponse } from '../../api/goals'
import type { GoalCurrency } from './goalProgress'
import {
  formatGoalMoney,
  goalDueLabel,
  goalLeftLine,
  goalProgressBarWidth,
  goalShowCloseButton,
  goalShowOwnerNote,
} from './goalProgress'

type GoalCardProps = {
  goal: GoalResponse
  isOwner: boolean
  onClose: (goalId: string) => void
  onEdit: (goal: GoalResponse) => void
  closing?: boolean
}

export function GoalCard({ goal, isOwner, onClose, onEdit, closing = false }: GoalCardProps) {
  const done = goal.status === 'closed'
  const currency = goal.currency as GoalCurrency
  const hasBar = !done
  const pctLabel = done ? 'Закрыта' : `${goal.progress_pct ?? 0}%`
  const left = goalLeftLine({
    done,
    balance: goal.balance,
    target: goal.target_amount,
    currency,
  })
  const due = goalDueLabel(goal.deadline, goal.closed_at, done)
  const showClose = goalShowCloseButton({
    isOwner,
    canClose: goal.can_close,
    excessAmount: goal.excess_amount,
    status: goal.status,
  })
  const showOwnerNote = goalShowOwnerNote({
    isOwner,
    excessAmount: goal.excess_amount,
    status: goal.status,
  })
  const barWidth = goalProgressBarWidth(goal.progress_pct, goal.balance, goal.target_amount)
  const editable = isOwner && goal.status === 'active'

  const handleCardClick = () => {
    if (editable) {
      onEdit(goal)
    }
  }

  return (
    <div
      className={['goals-card', editable ? 'goals-card--editable' : ''].filter(Boolean).join(' ')}
      onClick={editable ? handleCardClick : undefined}
      onKeyDown={
        editable
          ? (event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                onEdit(goal)
              }
            }
          : undefined
      }
      role={editable ? 'button' : undefined}
      tabIndex={editable ? 0 : undefined}
    >
      <div className="goals-card__header">
        <div className="goals-card__name">{goal.name}</div>
        <div
          className={[
            'goals-card__pct',
            done ? 'goals-card__pct--closed' : '',
          ]
            .filter(Boolean)
            .join(' ')}
        >
          {pctLabel}
        </div>
      </div>

      {hasBar ? (
        <div className="goals-card__bar-track">
          <div className="goals-card__bar-fill" style={{ width: barWidth }} />
        </div>
      ) : null}

      <div className="goals-card__amounts">
        <div className="goals-card__saved">{formatGoalMoney(goal.balance, currency)}</div>
        <div className="goals-card__target">из {formatGoalMoney(goal.target_amount, currency)}</div>
      </div>

      <div className="goals-card__meta">
        <div className="goals-card__left">{left}</div>
        <div className="goals-card__due">{due}</div>
      </div>

      {showClose ? (
        <button
          type="button"
          className="goals-card__close"
          disabled={closing}
          onClick={(event) => {
            event.stopPropagation()
            onClose(goal.id)
          }}
        >
          Закрыть цель
        </button>
      ) : null}

      {showOwnerNote ? (
        <div className="goals-card__owner-note">Закрыть цель может только владелец бюджета.</div>
      ) : null}
    </div>
  )
}
