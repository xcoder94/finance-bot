"""m3-5 fix1 B1: change log stored as payload, rendered in the reader's language."""
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction_change_log import TransactionChangeLog
from app.services.change_log_format import (
    change_line,
    creation_line,
    render_change_payload,
)
from tests.test_phase10_change_log import (
    _create_owner_and_member,
    _seed_shared_expense,
)
from tests.test_transactions import api_client, auth_headers, txn_payload  # noqa: F401

ACTOR = {"id": None, "name": "Member"}


def _changed(field, old, new):
    return {"kind": "changed", "on": "2026-11-01", "actor": ACTOR,
            "field": field, "old": old, "new": new}


def test_ru_render_equals_legacy_line():
    created = {"kind": "created", "on": "2026-11-01", "actor": ACTOR}
    assert render_change_payload(created, "ru") == creation_line(
        created_on=date(2026, 11, 1), creator_name="Member")
    p = _changed("amount", 950000, 990000)
    assert render_change_payload(p, "ru") == change_line(
        edited_on=date(2026, 11, 1), editor_name="Member", field_label="сумма",
        old_value="950 000", new_value="990 000")
    assert render_change_payload(_changed("comment", None, "x"), "ru") == (
        "1 ноября · Member: комментарий  → x")
    ent = {"id": None, "name": "Продукты", "tk": "groceries"}
    assert render_change_payload(_changed("category", ent, None), "ru") == (
        "1 ноября · Member: категория Продукты → ")
    assert render_change_payload(_changed("date", "2026-10-02", "2026-11-01"), "ru") == (
        "1 ноября · Member: дата 02.10.2026 → 01.11.2026")


def test_uz_render_has_no_cyrillic_and_uses_tk():
    ent = {"id": None, "name": "Продукты", "tk": "groceries"}
    own = {"id": None, "name": "Моя", "tk": None}
    created = {"kind": "created", "on": "2026-11-01", "actor": ACTOR}
    lines = [
        render_change_payload(created, "uz"),
        render_change_payload(_changed("amount", 950000, 990000), "uz"),
        render_change_payload(_changed("category", ent, own), "uz"),
        render_change_payload(_changed("date", "2026-10-02", "2026-11-01"), "uz"),
        render_change_payload(_changed("rate", "12650.5", None), "uz"),
        render_change_payload(_changed("from", ent, None), "uz"),
    ]
    assert lines[0] == "1-noyabr · Member yaratdi"
    assert lines[1] == "1-noyabr · Member: summa 950 000 → 990 000"
    assert "Oziq-ovqat" in lines[2] and "Моя" in lines[2]
    for line in lines[:2] + lines[3:]:
        assert not any("а" <= c.lower() <= "я" for c in line), line


@pytest.mark.anyio
async def test_new_rows_are_payload_and_rendered_per_reader(api_client):
    client, session = api_client
    owner_tid, member_tid, owner, _m, budget = await _create_owner_and_member(session)
    owner.language = "uz"
    txn, wallet, _top, sub = await _seed_shared_expense(session, budget, owner)
    await session.flush()
    resp = await client.patch(
        f"/api/v1/transactions/{txn.id}",
        headers=auth_headers(member_tid),
        json=txn_payload(wallet_id=str(wallet.id), expense_category_id=str(sub.id),
                         amount=200_000, transaction_date=txn.transaction_date.isoformat()),
    )
    assert resp.status_code == 200, resp.text
    assert "сумма" in resp.json()["changes"][1]

    rows = (await session.scalars(select(TransactionChangeLog).where(
        TransactionChangeLog.transaction_id == txn.id))).all()
    assert len(rows) == 2
    assert all(r.format_version == 1 and r.line_text is None and r.payload for r in rows)

    got = await client.get(f"/api/v1/transactions/{txn.id}", headers=auth_headers(owner_tid))
    changes = got.json()["changes"]
    assert changes[0].endswith("yaratdi")
    assert "summa 20 000 → 200 000" in changes[1]


@pytest.mark.anyio
async def test_legacy_rows_served_as_is(api_client):
    client, session = api_client
    owner_tid, _mt, owner, _m, budget = await _create_owner_and_member(session)
    owner.language = "uz"
    txn, *_ = await _seed_shared_expense(session, budget, owner)
    session.add(TransactionChangeLog(transaction_id=txn.id, line_text="1 ноября · X: сумма 1 → 2",
                                     format_version=0))
    await session.flush()
    got = await client.get(f"/api/v1/transactions/{txn.id}", headers=auth_headers(owner_tid))
    assert got.json()["changes"] == ["1 ноября · X: сумма 1 → 2"]


@pytest.mark.parametrize(
    "text,expected",
    [("12 3 сум", None), ("41 2000 сум", None), ("5 12 сум", None), ("12 3 so'm", None),
     ("412 000 сум", 412_000), ("412000 сум", 412_000), ("1 500 000 сум", 1_500_000)],
)
def test_amount_with_unit_follows_separator_rule(text, expected):
    from bot.quick_entry.shopping_pending import bare_text_amount, is_malformed_number

    assert bare_text_amount(text) == expected
    assert is_malformed_number(text) is (expected is None)


def test_ru_render_matches_frozen_migration_render():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).parent.parent / "alembic/versions/x4a5b6c7d8e9_change_log_payload.py"
    spec = importlib.util.spec_from_file_location("mig_x4", path)
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    ent = {"id": None, "name": "Нал", "tk": "cash_uzs"}
    cases = [
        {"kind": "created", "on": "2026-01-05", "actor": ACTOR},
        _changed("amount", -1234567, 5),
        _changed("rate", None, "12650.5"),
        _changed("comment", "a: b", None),
        _changed("wallet", ent, None),
        _changed("date", "2026-02-28", "2026-12-01"),
    ]
    for c in cases:
        assert render_change_payload(c, "ru") == mig.render_ru(c)
