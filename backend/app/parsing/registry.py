from collections.abc import Mapping

from app.parsing.types import DocumentParser


class UnsupportedParserError(LookupError):
    def __init__(self, format_name: str) -> None:
        self.format_name = format_name
        super().__init__(f"unsupported_parser: {format_name}")


class ParserRegistry:
    def __init__(self, parsers: Mapping[str, DocumentParser]) -> None:
        self._parsers = dict(parsers)

    def get(self, format_name: str) -> DocumentParser:
        try:
            return self._parsers[format_name]
        except KeyError as error:
            raise UnsupportedParserError(format_name) from error
