import json

from app.parsing.types import ParseRequest

IMMUTABLE_PARSER_INSTRUCTIONS = (
    "Parse family budget chat messages. Reply with JSON only, no markdown:\n"
    '{"operations":[{"type":"expense|income|ambiguous|transfer|exchange",'
    '"amount":integer_or_null,"currency":"UZS|USD"|null,'
    '"wallet_hint":string_or_null,'
    '"from_wallet_hint":string_or_null,"to_wallet_hint":string_or_null,'
    '"rate":integer_or_null,'
    '"category":string_or_null,"comment":string_or_null}]}\n'
    "Rules:\n"
    "- Same-currency move between two wallets → type transfer; set from_wallet_hint and to_wallet_hint; rate null.\n"
    "- Different-currency move → type exchange; set from_wallet_hint, to_wallet_hint, and rate only when the text "
    "contains an explicit rate marker word («по» or «по курсу»). If no marker, rate must be null.\n"
    "- Never invent a rate from a bare second number without «по» / «по курсу».\n"
    "- expense/income/ambiguous: from_wallet_hint, to_wallet_hint, rate are null; use wallet_hint."
)


def build_mutable_parser_payload(request: ParseRequest) -> str:
    return json.dumps(
        {
            "text": request.text,
            "wallet_names": request.wallet_names,
            "expense_category_names": request.expense_category_names,
            "income_category_names": request.income_category_names,
        },
        ensure_ascii=False,
    )


def build_parser_messages(request: ParseRequest) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": IMMUTABLE_PARSER_INSTRUCTIONS},
        {"role": "user", "content": build_mutable_parser_payload(request)},
    ]
