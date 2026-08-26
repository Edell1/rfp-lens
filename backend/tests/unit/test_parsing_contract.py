from pathlib import Path

from pydantic import ValidationError
import pytest

from app.parsing.registry import ParserRegistry, UnsupportedParserError
from app.parsing.types import DocumentBlock, ParseResult, SourceLocator


def paragraph(block_id: str = "pdf-p1-b1", order: int = 0) -> DocumentBlock:
    return DocumentBlock(
        block_id=block_id,
        order=order,
        kind="paragraph",
        text="중소기업만 신청 가능",
        heading_path=["1. 지원 자격"],
        locator=SourceLocator(format="pdf", page=1),
        metadata={},
    )


def test_document_block_rejects_blank_text() -> None:
    with pytest.raises(ValidationError):
        DocumentBlock(
            block_id="pdf-p1-b1",
            order=0,
            kind="paragraph",
            text="   ",
            heading_path=[],
            locator=SourceLocator(format="pdf", page=1),
            metadata={},
        )


def test_document_block_is_immutable() -> None:
    block = paragraph()

    with pytest.raises(ValidationError):
        block.text = "변경"


def test_parse_result_rejects_duplicate_block_ids() -> None:
    with pytest.raises(ValidationError, match="unique"):
        ParseResult(blocks=[paragraph(order=0), paragraph(order=1)])


def test_successful_parse_requires_at_least_one_block() -> None:
    with pytest.raises(ValidationError, match="at least one block"):
        ParseResult(blocks=[])


def test_ocr_required_parse_can_be_empty() -> None:
    result = ParseResult(blocks=[], requires_ocr=True)

    assert result.blocks == []


def test_registry_returns_registered_parser() -> None:
    class PdfParser:
        def parse(self, path: Path) -> ParseResult:
            return ParseResult(blocks=[paragraph()])

    parser = PdfParser()
    registry = ParserRegistry({"pdf": parser})

    assert registry.get("pdf") is parser


def test_registry_rejects_unknown_format() -> None:
    registry = ParserRegistry({})

    with pytest.raises(UnsupportedParserError, match="unsupported_parser"):
        registry.get("hwp")
