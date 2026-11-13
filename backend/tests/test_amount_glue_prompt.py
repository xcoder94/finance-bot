"""Model prompt carries the multiplier / count rule; one-operation answer parses.

The real model is not exercised here: only the prompt text and the parsing of
the answer shape the rule asks for.
"""

from app.parsing.http_adapter import _parse_response_payload
from app.parsing.prompt import IMMUTABLE_PARSER_INSTRUCTIONS as PROMPT


def test_prompt_has_multiplier_and_count_rule() -> None:
    for marker in ("x2", "х2", "*2", "×2", "2 раза", "2 marta", "2 шт", "2 чел"):
        assert marker in PROMPT
    assert "one operation" in PROMPT
    assert "NOT two operations" in PROMPT


def test_single_operation_answer_for_multiplier_parses() -> None:
    resp = _parse_response_payload(
        {
            "operations": [
                {"type": "expense", "amount": 40000, "currency": "UZS", "category": "Такси", "comment": "x2"}
            ]
        }
    )
    assert len(resp.operations) == 1
    assert resp.operations[0].amount == 40000
