from typing import Protocol

from app.parsing.types import ParseRequest, ParseResponse


class MessageParser(Protocol):
    async def parse(self, request: ParseRequest) -> ParseResponse: ...
