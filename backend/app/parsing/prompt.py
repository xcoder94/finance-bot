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
    '"receipt_status":"ok|unreadable"|null,'
    '"shopping_items":[string],"transcript":string_or_null}\n'
    "Rules:\n"
    "- A text or audio message with NO amount that is just a list of goods to buy (e.g. milk, bread, eggs) → "
    "operations empty and shopping_items = the goods, one short name each, in the user's words, at most 20. "
    "If the message has an amount, shopping_items must be empty. shopping_items is empty in every other case.\n"
    "- Same-currency move between two wallets → type transfer; set from_wallet_hint and to_wallet_hint; rate null.\n"
    "- Different-currency move → type exchange; set from_wallet_hint, to_wallet_hint, and rate only when the text "
    "or speech contains an explicit rate marker word («по» or «по курсу»). If no marker, rate must be null.\n"
    "- Never invent a rate from a bare second number without «по» / «по курсу».\n"
    "- expense/income/ambiguous: from_wallet_hint, to_wallet_hint, rate are null; use wallet_hint.\n"
    "- Bare direction words set type even with no category match. Income markers (case-insensitive): "
    "kirim, приход, доход, получил, получила, заработал, заработала, oylik, oyli, maosh, ish haqi, "
    "ойлик, маош, зарплата, зп, аванс, оклад, qarz oldim, qarzga oldim, взял в долг → type income. "
    "Expense markers: chiqim, расход, потратил, потратила, заплатил, заплатила, qarz berdim, "
    "qarz to'ladim, qarzni to'ladim, qarz qaytardim, вернул долг, отдал долг, дал в долг → type expense. "
    "Plain oldim / keldi / взял / взяла without a debt word (qarz, долг) are NOT direction markers: "
    "«taksi oldim», «взял такси», «kiyim oldim» are purchases, type expense with the matching category. "
    "When an income marker is present, never default to expense. "
    "A direction marker decides the type even if the named category exists only in the other list; "
    "then set category to null. "
    "Without any marker, a message that names one of the provided income_category_names is type income.\n"
    "- Never put relative or absolute date words in comment (e.g. вчера, позавчера, weekday names, «N дней назад»).\n"
    "- Text-only user turns: speech_status must be null; date_hint null unless the text contains a relative/absolute "
    "date you resolve against the provided today.\n"
    "- Audio-carrying turns: set speech_status to not_recognized when there is no intelligible speech "
    "(silence, noise, empty); otherwise recognized. Never invent operations when not_recognized.\n"
    "- Audio-carrying turns: transcript = the speech written down as heard, short, digits as digits "
    "(e.g. \"50 ming\"); text-only and image turns: transcript null.\n"
    "- Amount words: ming / минг / тысяч / тыс / k / к = thousand (\"50 ming\", \"ellik ming\", "
    "\"50 тысяч\", \"50к\" = 50000); million / mln / миллион = 1000000. Spoken numbers (ellik = 50, "
    "пятьдесят = 50, yuz = 100) count too. A message that is only a sum is one operation of type "
    "ambiguous (or expense) with the full integer amount in so'm; never return the bare 50 for \"50 ming\".\n"
    "- Multipliers, counts, two numbers (always ONE operation, never split or added; the type comes "
    "from the category or a direction marker, never from these numbers): "
    "(1) a multiplier next to the sum in any order and case — «20000 x2», «x2 20000», «2 x 20000», "
    "«20000 X2», «3 шт по 15000», «2 раза по 20000», «2 ta 15000 dan» (signs x х × * ·) — amount = the product, "
    "comment «2 × 20000». "
    "(2) a count without «по» or a multiplication sign — «такси 20000 2 раза», «обед 2 чел 45000» — "
    "amount = the sum as written, the count goes to comment. "
    "(3) two numbers with no explanation — «продукты 12 15000» — amount = the one that looks like money "
    "(the larger), the other goes to comment; NOT type ambiguous and NOT two operations.\n"
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
