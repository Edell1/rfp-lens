from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

import pytest

from app.parsing.hwpx import HwpxParseError, HwpxParser
from tests.fixtures.hwpx_factory import DEFAULT_SECTION, build_hwpx


def paragraph_section(text: str) -> str:
    return f"""<sec xmlns:hp="urn:paragraph">
      <hp:p><hp:run><hp:t>{text}</hp:t></hp:run></hp:p>
    </sec>"""


def test_hwpx_parser_preserves_paragraph_table_order_and_locators(
    tmp_path: Path,
) -> None:
    path = build_hwpx(tmp_path / "rfp.hwpx")

    result = HwpxParser().parse(path)

    assert [block.text for block in result.blocks] == [
        "1. 지원 자격",
        "중소기업만 신청 가능",
        "평가항목",
    ]
    assert [block.kind for block in result.blocks] == ["heading", "paragraph", "table"]
    assert result.blocks[1].heading_path == ["1. 지원 자격"]
    assert result.blocks[0].locator.section == "Contents/section0.xml"
    assert result.blocks[0].locator.paragraph == 0
    assert result.blocks[1].locator.paragraph == 1
    assert result.blocks[2].locator.table == 0


def test_hwpx_parser_follows_spine_order_not_filename_order(tmp_path: Path) -> None:
    sections = {
        "Contents/a.xml": paragraph_section("나중 섹션"),
        "Contents/z.xml": paragraph_section("먼저 섹션"),
    }
    path = build_hwpx(
        tmp_path / "ordered.hwpx", sections=sections, spine=["Contents/z.xml", "Contents/a.xml"]
    )

    result = HwpxParser().parse(path)

    assert [block.text for block in result.blocks] == ["먼저 섹션", "나중 섹션"]


def test_hwpx_parser_accepts_hancom_root_qualified_section_href(
    tmp_path: Path,
) -> None:
    manifest = """<opf:package xmlns:opf="http://www.idpf.org/2007/opf">
      <opf:manifest>
        <opf:item id="section0" href="Contents/section0.xml" />
      </opf:manifest>
      <opf:spine><opf:itemref idref="section0" /></opf:spine>
    </opf:package>"""
    path = build_hwpx(tmp_path / "hancom.hwpx", content_hpf=manifest)

    result = HwpxParser().parse(path)

    assert result.blocks[0].text == "1. 지원 자격"
    assert result.blocks[0].locator.section == "Contents/section0.xml"


def test_hwpx_parser_rejects_parent_traversal(tmp_path: Path) -> None:
    path = build_hwpx(
        tmp_path / "traversal.hwpx", extra_members={"../escape.xml": b"escape"}
    )

    with pytest.raises(HwpxParseError, match="invalid_hwpx"):
        HwpxParser().parse(path)


def test_hwpx_parser_rejects_501_members(tmp_path: Path) -> None:
    members = {f"Contents/item-{index}.xml": b"x" for index in range(498)}
    path = build_hwpx(tmp_path / "many.hwpx", extra_members=members)

    with pytest.raises(HwpxParseError, match="invalid_hwpx"):
        HwpxParser().parse(path)


def test_hwpx_parser_rejects_xml_entities(tmp_path: Path) -> None:
    unsafe = """<!DOCTYPE sec [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <sec xmlns:hp="urn:paragraph"><hp:p><hp:t>&xxe;</hp:t></hp:p></sec>"""
    path = build_hwpx(
        tmp_path / "entity.hwpx", sections={"Contents/section0.xml": unsafe}
    )

    with pytest.raises(HwpxParseError, match="unsafe_xml"):
        HwpxParser().parse(path)


def test_hwpx_parser_rejects_missing_spine_entry(tmp_path: Path) -> None:
    manifest = """<package xmlns="http://www.idpf.org/2007/opf">
      <manifest><item id="known" href="section0.xml" /></manifest>
      <spine><itemref idref="missing" /></spine>
    </package>"""
    path = build_hwpx(tmp_path / "missing.hwpx", content_hpf=manifest)

    with pytest.raises(HwpxParseError, match="invalid_hwpx"):
        HwpxParser().parse(path)


def test_hwpx_parser_rejects_malformed_section_xml(tmp_path: Path) -> None:
    path = build_hwpx(
        tmp_path / "malformed.hwpx",
        sections={"Contents/section0.xml": "<sec><broken></sec>"},
    )

    with pytest.raises(HwpxParseError, match="malformed_xml"):
        HwpxParser().parse(path)
