from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import fitz

from app.parsing.types import DocumentBlock, ParseResult, ParseWarning, SourceLocator


HEADING_PATTERN = re.compile(r"^(?:제\d+장|\d+[.)]|[가-힣][.)])\s*\S.+$")


class PdfParseError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _Candidate:
    y: float
    x: float
    kind: str
    text: str
    bbox: tuple[float, float, float, float]


def _normalize_text(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _heading_line(text: str) -> str | None:
    first_line = text.splitlines()[0]
    if len(first_line) <= 100 and HEADING_PATTERN.match(first_line):
        return first_line
    return None


class PdfParser:
    def __init__(self, min_text_chars_per_page: int = 20) -> None:
        self.min_text_chars_per_page = min_text_chars_per_page

    def parse(self, path: Path) -> ParseResult:
        try:
            document = fitz.open(path)
        except (fitz.FileDataError, RuntimeError) as error:
            raise PdfParseError("invalid_pdf") from error

        with document:
            if document.needs_pass:
                raise PdfParseError("encrypted_pdf")
            if document.page_count == 0:
                raise PdfParseError("empty_pdf")

            blocks: list[DocumentBlock] = []
            low_text_pages = 0
            current_heading: list[str] = []
            order = 0

            for page_number, page in enumerate(document, start=1):
                candidates = self._page_candidates(page)
                page_characters = sum(len(candidate.text) for candidate in candidates)
                if page_characters < self.min_text_chars_per_page:
                    low_text_pages += 1

                paragraph_index = 0
                table_index = 0
                for candidate in candidates:
                    heading = _heading_line(candidate.text)
                    block_kind = "table" if candidate.kind == "table" else "paragraph"
                    if heading is not None:
                        current_heading = [heading]
                        if "\n" not in candidate.text:
                            block_kind = "heading"

                    if candidate.kind == "table":
                        table_index += 1
                        block_id = f"pdf-p{page_number}-t{table_index}"
                    else:
                        paragraph_index += 1
                        block_id = f"pdf-p{page_number}-b{paragraph_index}"

                    blocks.append(
                        DocumentBlock(
                            block_id=block_id,
                            order=order,
                            kind=block_kind,
                            text=candidate.text,
                            heading_path=list(current_heading),
                            locator=SourceLocator(
                                format="pdf",
                                page=page_number,
                                bbox=candidate.bbox,
                            ),
                            metadata={},
                        )
                    )
                    order += 1

            requires_ocr = low_text_pages > document.page_count / 2
            warnings = (
                [
                    ParseWarning(
                        code="ocr_required",
                        message="More than half of the PDF pages contain too little text",
                    )
                ]
                if requires_ocr
                else []
            )
            return ParseResult(
                blocks=blocks,
                warnings=warnings,
                requires_ocr=requires_ocr,
            )

    def _page_candidates(self, page: fitz.Page) -> list[_Candidate]:
        table_candidates: list[_Candidate] = []
        table_rectangles: list[fitz.Rect] = []
        for table in page.find_tables().tables:
            rows = table.extract()
            text = "\n".join(
                "\t".join((cell or "").strip() for cell in row) for row in rows
            ).strip()
            if not text:
                continue
            rectangle = fitz.Rect(table.bbox)
            table_rectangles.append(rectangle)
            table_candidates.append(
                _Candidate(
                    y=rectangle.y0,
                    x=rectangle.x0,
                    kind="table",
                    text=text,
                    bbox=tuple(float(value) for value in table.bbox),
                )
            )

        text_candidates: list[_Candidate] = []
        for raw_block in page.get_text("blocks", sort=True):
            x0, y0, x1, y1, raw_text, _block_number, block_type = raw_block
            if block_type != 0:
                continue
            rectangle = fitz.Rect(x0, y0, x1, y1)
            if any(rectangle.intersects(table_rectangle) for table_rectangle in table_rectangles):
                continue
            text = _normalize_text(raw_text)
            if not text:
                continue
            text_candidates.append(
                _Candidate(
                    y=float(y0),
                    x=float(x0),
                    kind="text",
                    text=text,
                    bbox=(float(x0), float(y0), float(x1), float(y1)),
                )
            )

        return sorted(
            [*text_candidates, *table_candidates], key=lambda item: (item.y, item.x)
        )
