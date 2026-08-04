import uuid
from datetime import UTC, date, datetime

from aiogram import Bot
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal import Goal
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.goals import GoalCreate, GoalResponse, GoalUpdate
from app.services.goal_notify import fan_out_achievement, resolve_bot
from app.services.quick_entry_balance import wallet_balance
from app.services.wallets_categories import get_active_wallet


def progress_fields(
    balance: int,
    target: int,
    *,
    closed: bool,
    frozen: int | None,
) -> dict[str, int | bool | None]:
    if closed:
        return {
            "balance": frozen if frozen is not None else balance,
            "progress_pct": None,
            "excess_amount": None,
            "remaining_amount": None,
            "is_exactly_complete": False,
        }
    pct = min(100, round(balance * 100 / target)) if target > 0 else 0
    excess = balance - target if balance > target else None
    remaining = target - balance if balance < target else None
    return {
        "balance": balance,
        "progress_pct": pct,
        "excess_amount": excess,
        "remaining_amount": remaining,
        "is_exactly_complete": balance == target,
    }


def goal_to_response(goal: Goal, balance: int, user: User) -> GoalResponse:
    closed = goal.status == "closed"
    pf = progress_fields(
        balance,
        goal.target_amount,
        closed=closed,
        frozen=goal.frozen_balance if closed else None,
    )
    return GoalResponse(
        id=goal.id,
        wallet_id=goal.wallet_id,
        name=goal.name,
        target_amount=goal.target_amount,
        currency=goal.currency,
        deadline=goal.deadline,
        status=goal.status,
        balance=pf["balance"],
        progress_pct=pf["progress_pct"],
        excess_amount=pf["excess_amount"],
        remaining_amount=pf["remaining_amount"],
        is_exactly_complete=pf["is_exactly_complete"],
        closed_at=goal.closed_at,
        can_close=user.role == "owner" and goal.status == "active",
    )


async def get_goal_in_family(
    session: AsyncSession,
    goal_id: uuid.UUID,
    family_budget_id: uuid.UUID,
) -> Goal | None:
    stmt = select(Goal).where(
        Goal.id == goal_id,
        Goal.family_budget_id == family_budget_id,
    )
    return await session.scalar(stmt)


async def get_active_goal_for_wallet(
    session: AsyncSession,
    wallet_id: uuid.UUID,
) -> Goal | None:
    stmt = select(Goal).where(
        Goal.wallet_id == wallet_id,
        Goal.status == "active",
    )
    return await session.scalar(stmt)


async def check_goal_achievement(
    session: AsyncSession,
    wallet_id: uuid.UUID,
    *,
    bot: Bot | None = None,
) -> None:
    goal = await get_active_goal_for_wallet(session, wallet_id)
    if goal is None:
        return

    balance = await wallet_balance(session, wallet_id)
    now_crossed = balance >= goal.target_amount

    if now_crossed and not goal.crossed:
        resolved_bot, _owned = await resolve_bot(bot)
        await fan_out_achievement(session, goal, balance, resolved_bot)
        goal.crossed = True
        await session.commit()
    elif not now_crossed and goal.crossed:
        goal.crossed = False
        await session.commit()


async def list_goals(
    session: AsyncSession,
    user: User,
    status: str,
) -> list[GoalResponse]:
    stmt = (
        select(Goal)
        .where(
            Goal.family_budget_id == user.family_budget_id,
            Goal.status == status,
        )
        .order_by(Goal.created_at)
    )
    goals = (await session.scalars(stmt)).all()
    results: list[GoalResponse] = []
    for goal in goals:
        if goal.status == "active":
            balance = await wallet_balance(session, goal.wallet_id)
        else:
            balance = goal.frozen_balance or 0
        results.append(goal_to_response(goal, balance, user))
    return results


async def create_goal(
    session: AsyncSession,
    user: User,
    body: GoalCreate,
) -> GoalResponse:
    wallet = await get_active_wallet(session, body.wallet_id, user.family_budget_id)
    if wallet is None:
        raise HTTPException(status_code=404)
    if wallet.is_personal:
        raise HTTPException(status_code=400)
    existing = await session.scalar(
        select(Goal).where(
            Goal.wallet_id == body.wallet_id,
            Goal.status == "active",
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409)

    balance = await wallet_balance(session, wallet.id)
    name = body.name if body.name is not None and body.name.strip() else wallet.name

    goal = Goal(
        family_budget_id=user.family_budget_id,
        wallet_id=wallet.id,
        name=name,
        target_amount=body.target_amount,
        currency=wallet.currency,
        deadline=body.deadline,
        status="active",
        crossed=False,
    )
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    await check_goal_achievement(session, wallet.id)
    await session.refresh(goal)
    balance = await wallet_balance(session, wallet.id)
    return goal_to_response(goal, balance, user)


async def update_goal(
    session: AsyncSession,
    user: User,
    goal_id: uuid.UUID,
    body: GoalUpdate,
) -> GoalResponse:
    goal = await get_goal_in_family(session, goal_id, user.family_budget_id)
    if goal is None:
        raise HTTPException(status_code=404)
    if goal.status != "active":
        raise HTTPException(status_code=404)

    update_data = body.model_dump(exclude_unset=True)
    if "name" in update_data:
        name = update_data["name"]
        if name is not None and name.strip():
            goal.name = name
    if "target_amount" in update_data:
        goal.target_amount = update_data["target_amount"]
    if "deadline" in update_data:
        goal.deadline = update_data["deadline"]

    await session.commit()
    await session.refresh(goal)
    if "target_amount" in update_data:
        await check_goal_achievement(session, goal.wallet_id)
        await session.refresh(goal)
    balance = await wallet_balance(session, goal.wallet_id)
    return goal_to_response(goal, balance, user)


async def close_goal(
    session: AsyncSession,
    user: User,
    goal_id: uuid.UUID,
) -> GoalResponse:
    goal = await get_goal_in_family(session, goal_id, user.family_budget_id)
    if goal is None:
        raise HTTPException(status_code=404)
    if goal.status != "active":
        raise HTTPException(status_code=404)

    balance = await wallet_balance(session, goal.wallet_id)
    goal.frozen_balance = balance
    goal.status = "closed"
    goal.closed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(goal)
    return goal_to_response(goal, balance, user)
