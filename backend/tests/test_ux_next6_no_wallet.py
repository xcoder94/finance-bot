"""ux-next6 L2: the person sees no usable wallet -> a clear message, not silence or a crash."""

from types import SimpleNamespace

from app.services.bot_texts import t
from app.models.wallet import Wallet
from bot.quick_entry.handlers import handle_quick_entry_text, set_parser_override
from app.parsing.stub import StubParser

from tests.test_phase16_prefilter_handlers import (
    SessionFactory,
    create_user,
    make_message,
    pytestmark,  # noqa: F401
    reset_parser_override,  # noqa: F401
    rollback_session,
)
from tests.test_phase16_prefilter_handlers import make_wallet


async def test_default_wallet_of_another_family_is_not_used(monkeypatch) -> None:
    async with rollback_session() as session:
        user, budget = await create_user(session, telegram_id=9_177_701)
        _other, other_budget = await create_user(session, telegram_id=9_177_702)
        foreign = make_wallet(other_budget, name="Чужой")
        session.add(foreign)
        await session.flush()
        user.default_wallet_id = foreign.id
        await session.flush()
        set_parser_override(StubParser())
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )
        message = make_message(telegram_id=user.telegram_id, text="такси 20000")
        await handle_quick_entry_text(message, SimpleNamespace())
        message.answer.assert_awaited_once()
        assert message.answer.await_args.args[0] == t(user, "quick.no_wallet")
