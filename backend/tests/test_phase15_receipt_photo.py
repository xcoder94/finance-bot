"""Phase 15 — receipt photo (unit section: Task 1)."""

from __future__ import annotations

import pytest

from app.config import receipt_photo_enabled
from app.parsing.prompt import IMMUTABLE_PARSER_INSTRUCTIONS
from app.parsing.types import ParseRequest, ParseResponse
from bot.quick_entry.texts import MSG_RECEIPT_UNREADABLE

MSG_RECEIPT_UNREADABLE_EXPECTED = (
    "Не разобрал чек. Сфотографируйте его целиком при хорошем свете или запишите\n"
    "сумму текстом."
)


def test_parse_request_accepts_optional_image_fields():
    req = ParseRequest(
        text="",
        wallet_names=[],
        expense_category_names=[],
        income_category_names=[],
        image_base64="AAAA",
        image_mime_type="image/jpeg",
    )
    assert req.image_base64 == "AAAA"
    assert req.image_mime_type == "image/jpeg"


def test_parse_response_accepts_receipt_status():
    r = ParseResponse(operations=[], receipt_status="unreadable")
    assert r.receipt_status == "unreadable"


def test_msg_receipt_unreadable_exact_prd_text():
    assert MSG_RECEIPT_UNREADABLE == MSG_RECEIPT_UNREADABLE_EXPECTED


def test_instructions_document_receipt_status_and_rules():
    assert "receipt_status" in IMMUTABLE_PARSER_INSTRUCTIONS
    lowered = IMMUTABLE_PARSER_INSTRUCTIONS.lower()
    assert "total" in lowered or "итог" in lowered


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),
        ("", False),
        ("0", False),
        ("false", False),
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("on", True),
    ],
)
def test_receipt_photo_enabled(monkeypatch: pytest.MonkeyPatch, value: str | None, expected: bool):
    monkeypatch.setattr("app.config.RECEIPT_PHOTO_ENABLED", value)
    assert receipt_photo_enabled() is expected
