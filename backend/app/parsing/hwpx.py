from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
from xml.etree.ElementTree import Element, ParseError
from zipfile import BadZipFile, ZipFile

from defusedxml import ElementTree as SafeElementTree
from defusedxml.common import DefusedXmlException

from app.documents.validation import DocumentValidationError, detect_document_format
from app.parsing.safety import (
    ArchiveSafetyError,
    normalize_block_text,
    resolve_archive_reference,
    validate_archive,
)
from app.parsing.types import DocumentBlock, ParseResult, SourceLocator


HEADING_PATTERN = re.compile(r"^(?:제\d+장|\d+[.)]|[가-힣][.)])\s*\S.+$")
CONTENT_MANIFEST = "Contents/content.hpf"


class HwpxParseError(ValueError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True)
class _SectionItem:
    kind: str
    text: str
    paragraph: int | None = None
    table: int | None = None


def _local_name(element: Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _text_content(element: Element) -> str:
    return normalize_block_text(
        "".join(
            descendant.text or ""
            for descendant in element.iter()
            if _local_name(descendant) == "t"
        )
    )


def _parse_xml(content: bytes) -> Element:
    try:
        return SafeElementTree.fromstring(content)
    except DefusedXmlException as error:
        raise HwpxParseError("unsafe_xml") from error
    except ParseError as error:
        raise HwpxParseError("malformed_xml") from error


class HwpxParser:
    def parse(self, path: Path) -> ParseResult:
        try:
            if detect_document_format(path) != "hwpx":
                raise HwpxParseError("invalid_hwpx")
        except DocumentValidationError as error:
            raise HwpxParseError(error.code, error.message) from error

        try:
            with ZipFile(path) as archive:
                try:
                    names = validate_archive(archive)
                    sections = self._section_paths(archive, names)
                except ArchiveSafetyError as error:
                    raise HwpxParseError("invalid_hwpx", error.reason) from error

                blocks: list[DocumentBlock] = []
                heading_path: list[str] = []
                order = 0
                for section_path in sections:
                    root = _parse_xml(archive.read(section_path))
                    for item in self._section_items(root):
                        kind = item.kind
                        if kind == "paragraph" and self._is_heading(item.text):
                            kind = "heading"
                            heading_path = [item.text]
                        section_name = PurePosixPath(section_path).stem
                        suffix = (
                            f"t{item.table}"
                            if item.kind == "table"
                            else f"p{item.paragraph}"
                        )
                        blocks.append(
                            DocumentBlock(
                                block_id=f"hwpx-{section_name}-{suffix}",
                                order=order,
                                kind=kind,
                                text=item.text,
                                heading_path=list(heading_path),
                                locator=SourceLocator(
                                    format="hwpx",
                                    section=section_path,
                                    paragraph=item.paragraph,
                                    table=item.table,
                                ),
                                metadata={},
                            )
                        )
                        order += 1

                if not blocks:
                    raise HwpxParseError("empty_hwpx")
                return ParseResult(blocks=blocks)
        except BadZipFile as error:
            raise HwpxParseError("invalid_hwpx", "malformed_zip") from error

    def _section_paths(self, archive: ZipFile, names: set[str]) -> list[str]:
        manifest = _parse_xml(archive.read(CONTENT_MANIFEST))
        item_paths: dict[str, str] = {}
        resolved_paths: set[str] = set()
        for element in manifest.iter():
            if _local_name(element) != "item":
                continue
            item_id = element.attrib.get("id")
            href = element.attrib.get("href")
            if not item_id or not href or item_id in item_paths:
                raise HwpxParseError("invalid_hwpx", "invalid_manifest_item")
            resolved = resolve_archive_reference(CONTENT_MANIFEST, href)
            if resolved in resolved_paths:
                raise HwpxParseError("invalid_hwpx", "duplicate_spine_path")
            item_paths[item_id] = resolved
            resolved_paths.add(resolved)

        section_paths: list[str] = []
        for element in manifest.iter():
            if _local_name(element) != "itemref":
                continue
            item_id = element.attrib.get("idref")
            if not item_id or item_id not in item_paths:
                raise HwpxParseError("invalid_hwpx", "missing_spine_entry")
            section_path = item_paths[item_id]
            if section_path not in names:
                raise HwpxParseError("invalid_hwpx", "missing_section")
            section_paths.append(section_path)
        if not section_paths:
            raise HwpxParseError("invalid_hwpx", "empty_spine")
        return section_paths

    def _section_items(self, root: Element) -> list[_SectionItem]:
        items: list[_SectionItem] = []
        paragraph_index = 0
        table_index = 0

        def walk(element: Element) -> None:
            nonlocal paragraph_index, table_index
            name = _local_name(element)
            if name == "tbl":
                rows: list[str] = []
                for row in (child for child in element.iter() if _local_name(child) == "tr"):
                    cells = [
                        _text_content(cell)
                        for cell in row.iter()
                        if _local_name(cell) == "tc"
                    ]
                    rows.append("\t".join(cells))
                table_text = "\n".join(rows).strip()
                if table_text:
                    items.append(
                        _SectionItem(kind="table", text=table_text, table=table_index)
                    )
                table_index += 1
                return
            if name == "p":
                text = _text_content(element)
                if text:
                    items.append(
                        _SectionItem(
                            kind="paragraph", text=text, paragraph=paragraph_index
                        )
                    )
                paragraph_index += 1
                return
            for child in element:
                walk(child)

        walk(root)
        return items

    @staticmethod
    def _is_heading(text: str) -> bool:
        return len(text) <= 100 and bool(HEADING_PATTERN.match(text))
