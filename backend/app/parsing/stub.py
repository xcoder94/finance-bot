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
    )
}


class StubParser:
    def __init__(self, responses: dict[str, ParseResponse] | None = None) -> None:
        merged = dict(_DEFAULT_RESPONSES)
        if responses is not None:
            merged.update(responses)
        self._responses = merged

    async def parse(self, request: ParseRequest) -> ParseResponse:
        if request.text in self._responses:
            return self._responses[request.text]
        return ParseResponse(operations=[])
