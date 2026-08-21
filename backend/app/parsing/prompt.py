import json

from app.parsing.types import ParseRequest
from app.services.quick_entry_dates import tashkent_today

IMMUTABLE_PARSER_INSTRUCTIONS = (
    "Parse family budget chat messages. Reply with JSON only, no markdown:\n"
    '{"operations":[{"type":"expense|income|ambiguous|transfer|exchange",'
    '"amount":integer_or_null,"currency":"UZS|USD"|null,'
    '"wallet_hint":string_or_null,'
    '"from_wallet_hint":string_or_null,"to_wallet_hint":string_or_null,'
    '"rate":integer_or_null,'
    '"category":string_or_null,"comment":string_or_null}],'
    '"speech_status":"recognized|not_recognized"|null,'
    '"date_hint":"YYYY-MM-DD"|null,'
    '"receipt_status":"ok|unreadable"|null}\n'
    "Rules:\n"
    "- Same-currency move between two wallets → type transfer; set from_wallet_hint and to_wallet_hint; rate null.\n"
    "- Different-currency move → type exchange; set from_wallet_hint, to_wallet_hint, and rate only when the text "
    "or speech contains an explicit rate marker word («по» or «по курсу»). If no marker, rate must be null.\n"
    "- Never invent a rate from a bare second number without «по» / «по курсу».\n"
    "- expense/income/ambiguous: from_wallet_hint, to_wallet_hint, rate are null; use wallet_hint.\n"
    "- Bare direction words set type even with no category match. Income markers (case-insensitive): "
    "kirim, приход, доход, получил, получила, заработал, заработала, oylik, oyli, maosh, ish haqi, "
    "ойлик, маош, зарплата, зп, аванс, оклад → type income. "
    "Expense markers: chiqim, расход, потратил, потратила, заплатил, заплатила → type expense. "
    "When an income marker is present, never default to expense. "
    "When the message names or clearly matches one of the provided income_category_names, type is "
    "income even without a marker word.\n"
    "- Never put relative or absolute date words in comment (e.g. вчера, позавчера, weekday names, «N дней назад»).\n"
    "- Text-only user turns: speech_status must be null; date_hint null unless the text contains a relative/absolute "
    "date you resolve against the provided today.\n"
    "- Audio-carrying turns: set speech_status to not_recognized when there is no intelligible speech "
    "(silence, noise, empty); otherwise recognized. Never invent operations when not_recognized.\n"
    "- Text-only and audio turns: receipt_status must be null.\n"
    "- Receipt-image turns: set receipt_status to ok when the total amount is legible; unreadable "
    "when the image is not a receipt or the total cannot be read. One receipt = one expense for the "
    "total only — no line items. Put the merchant name in comment; infer category from merchant "
    "name and visible contents. Set date_hint from the receipt date when legible and within 31 days "
    "of today; otherwise null. When receipt_status is unreadable, return no operations."
)


def build_mutable_parser_payload(request: ParseRequest) -> str:
    return json.dumps(
        {
            "text": request.text,
            "wallet_names": request.wallet_names,
            "expense_category_names": request.expense_category_names,
            "income_category_names": request.income_category_names,
            "today": tashkent_today().isoformat(),
        },
        ensure_ascii=False,
    )


def build_parser_messages(request: ParseRequest) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": IMMUTABLE_PARSER_INSTRUCTIONS},
        {"role": "user", "content": build_mutable_parser_payload(request)},
    ]
