from app.parsing.types import ParseRequest, ParseResponse, ParsedOperation

_DEFAULT_RESPONSES: dict[str, ParseResponse] = {
    "такси 25 тысяч": ParseResponse(
        operations=[
            ParsedOperation(
                type="expense",
                amount=25000,
                currency="UZS",
                wallet_hint=None,
                category="Такси",
                comment=None,
            )
        ]
    ),
    "переложил 500 тысяч с карты на наличные": ParseResponse(
        operations=[
            ParsedOperation(
                type="transfer",
                amount=500_000,
                currency="UZS",
                wallet_hint=None,
                category=None,
                comment=None,
                from_wallet_hint="карта",
                to_wallet_hint="наличные",
                rate=None,
            )
        ]
    ),
    "поменял 100 долларов на сумы по 12800": ParseResponse(
        operations=[
            ParsedOperation(
                type="exchange",
                amount=100,
                currency="USD",
                wallet_hint=None,
                category=None,
                comment=None,
                from_wallet_hint="Карта USD",
                to_wallet_hint="Карта сум",
                rate=12_800,
            )
        ]
    ),
    "перевел с карты доллара на карту сум 50$": ParseResponse(
        operations=[
            ParsedOperation(
                type="exchange",
                amount=50,
                currency="USD",
                wallet_hint=None,
                category=None,
                comment=None,
                from_wallet_hint="карта доллара",
                to_wallet_hint="карта сум",
                rate=None,
            )
        ]
    ),
    "dollar kartasidan so'm kartasiga 50$ o'tkazdim": ParseResponse(
        operations=[
            ParsedOperation(
                type="exchange",
                amount=50,
                currency="USD",
                wallet_hint=None,
                category=None,
                comment=None,
                from_wallet_hint="Карта USD",
                to_wallet_hint="Карта сум",
                rate=None,
            )
        ]
    ),
    "поменял 100 долларов на сумы 12800": ParseResponse(
        operations=[
            ParsedOperation(
                type="exchange",
                amount=100,
                currency="USD",
                wallet_hint=None,
                category=None,
                comment=None,
                from_wallet_hint="Карта USD",
                to_wallet_hint="Карта сум",
                rate=None,
            )
        ]
    ),
    "Kirim 500000 som": ParseResponse(
        operations=[
            ParsedOperation(
                type="income",
                amount=500_000,
                currency="UZS",
                wallet_hint=None,
                category=None,
                comment=None,
            )
        ]
    ),
    "kirim 500 ming": ParseResponse(
        operations=[
            ParsedOperation(
                type="income",
                amount=500_000,
                currency="UZS",
                wallet_hint=None,
                category=None,
                comment=None,
            )
        ]
    ),
    "Chiqim 500000 som": ParseResponse(
        operations=[
            ParsedOperation(
                type="expense",
                amount=500_000,
                currency="UZS",
                wallet_hint=None,
                category=None,
                comment=None,
            )
        ]
    ),
}


class StubParser:
    def __init__(
        self,
        responses: dict[str, ParseResponse] | None = None,
        audio_responses: dict[str, ParseResponse] | None = None,
    ) -> None:
        merged = dict(_DEFAULT_RESPONSES)
        if responses is not None:
            merged.update(responses)
        self._responses = merged
        self._audio_responses = audio_responses or {}

    async def parse(self, request: ParseRequest) -> ParseResponse:
        if request.audio_base64 is not None:
            if "__audio__" in self._audio_responses:
                return self._audio_responses["__audio__"]
            return ParseResponse(operations=[])
        if request.text in self._responses:
            return self._responses[request.text]
        return ParseResponse(operations=[])
