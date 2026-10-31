"""m3-5 QA r2: gaps found by mutation testing of fix1 (B1 change log, P3 parser, bot apostrophe)."""
import json
import re
from pathlib import Path

import pytest

from app.models.wallet import Wallet
from app.services.change_log_format import DEFAULT_ENTITY_UZ, render_change_payload
from tests.test_phase10_change_log import _create_owner_and_member, _seed_shared_expense
from tests.test_transactions import api_client, auth_headers, txn_payload  # noqa: F401

ACTOR = {"id": None, "name": "Ann"}


@pytest.mark.parametrize(
    "field,label",
    [("amount", "summa"), ("category", "toifa"), ("wallet", "hamyon"), ("date", "sana"),
     ("comment", "izoh"), ("from", "qayerdan"), ("to", "qayerga"), ("rate", "kurs")],
)
def test_every_uz_field_label(field, label):
    p = {"kind": "changed", "on": "2026-03-09", "actor": ACTOR, "field": field, "old": None, "new": None}
    assert render_change_payload(p, "uz") == f"9-mart · Ann: {label}  → "


def test_uz_default_entity_names_match_frontend_uz_json():
    uz = Path(__file__).resolve().parents[2] / "frontend/src/i18n/locales/uz.json"
    if not uz.exists():
        pytest.skip("frontend not checked out")
    assert DEFAULT_ENTITY_UZ == json.loads(uz.read_text())["defaultEntities"]


@pytest.mark.anyio
async def test_uz_editor_patch_response_and_default_wallet_by_tk(api_client):
    """Writer stores tk; PATCH answers in the editor's language; default names are translated."""
    client, session = api_client
    owner_tid, member_tid, owner, member, budget = await _create_owner_and_member(session)
    member.language = "uz"
    txn, wallet, _top, sub = await _seed_shared_expense(session, budget, owner)
    wallet.name, wallet.translation_key = "Наличные сум", "cash_uzs"
    card = Wallet(family_budget_id=budget.id, name="Карта сум", currency="UZS", translation_key="card_uzs")
    session.add(card)
    await session.flush()
    resp = await client.patch(
        f"/api/v1/transactions/{txn.id}",
        headers=auth_headers(member_tid),
        json=txn_payload(wallet_id=str(card.id), expense_category_id=str(sub.id),
                         amount=txn.amount, transaction_date=txn.transaction_date.isoformat()),
    )
    assert resp.status_code == 200, resp.text
    changes = resp.json()["changes"]
    assert changes[-1].endswith("hamyon Naqd so'm → So'm kartasi"), changes
    assert changes[0].endswith("yaratdi") and not any(re.search("создал|кошел", c) for c in changes), changes
    ru = await client.get(f"/api/v1/transactions/{txn.id}", headers=auth_headers(owner_tid))
    assert ru.json()["changes"][-1].endswith("кошелёк Наличные сум → Карта сум")


@pytest.mark.anyio
async def test_empty_comment_equals_no_comment(api_client):
    client, session = api_client
    owner_tid, _mt, owner, _m, budget = await _create_owner_and_member(session)
    txn, wallet, _top, sub = await _seed_shared_expense(session, budget, owner, comment=None)
    resp = await client.patch(
        f"/api/v1/transactions/{txn.id}",
        headers=auth_headers(owner_tid),
        json=txn_payload(wallet_id=str(wallet.id), expense_category_id=str(sub.id), amount=txn.amount,
                         transaction_date=txn.transaction_date.isoformat(), comment=""),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["changes"] == []


@pytest.mark.parametrize("text", ["12 3 СУМ", "41 2000 Сум", "12 3 SO'M", "5 12 UZS"])
def test_unit_case_does_not_bypass_separator_rule(text):
    from bot.quick_entry.shopping_pending import bare_text_amount, is_malformed_number

    assert bare_text_amount(text) is None
    assert is_malformed_number(text) is True


def test_bot_uz_texts_use_ascii_apostrophe():
    root = Path(__file__).resolve().parents[1]
    bad = []
    for path in list((root / "bot").rglob("*.py")) + list((root / "app").rglob("*.py")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search("[‘’ʻʼ]", line):
                bad.append(f"{path.relative_to(root)}:{n}")
    assert bad == []
