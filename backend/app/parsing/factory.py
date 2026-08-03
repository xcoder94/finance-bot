from app.config import PARSER_API_KEY, PARSER_MODEL, PARSER_PROVIDER
from app.parsing.base import MessageParser
from app.parsing.http_adapter import HttpParser
from app.parsing.types import ParseRequest, ParseResponse, ParserUnavailable


class _InactiveParser:
    async def parse(self, request: ParseRequest) -> ParseResponse:
        raise ParserUnavailable("parser is inactive: PARSER_API_KEY is not set")


def get_parser() -> MessageParser:
    if PARSER_API_KEY:
        return HttpParser(
            provider=PARSER_PROVIDER or "",
            api_key=PARSER_API_KEY,
            model=PARSER_MODEL or "",
        )
    return _InactiveParser()
