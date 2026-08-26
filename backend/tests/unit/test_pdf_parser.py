from pathlib import Path

import pytest

from app.parsing.pdf import PdfParseError, PdfParser
from tests.fixtures.pdf_factory import make_encrypted_pdf, make_pdf


def test_pdf_parser_preserves_page_locator(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "rfp.pdf", ["1. 지원 자격\n중소기업만 신청 가능"])

    result = PdfParser().parse(path)

    assert result.blocks[0].text == "1. 지원 자격\n중소기업만 신청 가능"
    assert result.blocks[0].locator.page == 1
    assert result.blocks[0].heading_path == ["1. 지원 자격"]


def test_pdf_parser_preserves_page_order(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "pages.pdf", ["첫 페이지", "둘째 페이지"])

    result = PdfParser().parse(path)

    assert [block.text for block in result.blocks] == ["첫 페이지", "둘째 페이지"]
    assert [block.locator.page for block in result.blocks] == [1, 2]
    assert [block.order for block in result.blocks] == [0, 1]


def test_blank_page_requires_ocr(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "scan.pdf", [""])

    result = PdfParser(min_text_chars_per_page=20).parse(path)

    assert result.requires_ocr is True
    assert result.warnings[0].code == "ocr_required"


def test_half_blank_pages_do_not_mark_entire_document_for_ocr(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "mixed.pdf", ["충분한 디지털 텍스트입니다 1234567890", ""])

    result = PdfParser(min_text_chars_per_page=20).parse(path)

    assert result.requires_ocr is False


def test_encrypted_pdf_is_rejected(tmp_path: Path) -> None:
    path = make_encrypted_pdf(tmp_path / "encrypted.pdf")

    with pytest.raises(PdfParseError, match="encrypted_pdf"):
        PdfParser().parse(path)
