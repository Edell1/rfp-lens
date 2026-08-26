from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile


DEFAULT_SECTION = """<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.owpml.org/owpml/2021/section"
        xmlns:hp="http://www.owpml.org/owpml/2021/paragraph">
  <hp:p><hp:run><hp:t>1. 지원 자격</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>중소기업만 신청 가능</hp:t></hp:run></hp:p>
  <hp:tbl>
    <hp:tr><hp:tc><hp:subList><hp:p><hp:run><hp:t>평가항목</hp:t></hp:run></hp:p></hp:subList></hp:tc></hp:tr>
  </hp:tbl>
</hs:sec>
"""


def build_hwpx(
    path: Path,
    *,
    sections: dict[str, str] | None = None,
    spine: list[str] | None = None,
    extra_members: dict[str, bytes] | None = None,
    content_hpf: str | None = None,
) -> Path:
    section_map = sections or {"Contents/section0.xml": DEFAULT_SECTION}
    spine_order = spine or list(section_map)
    if content_hpf is None:
        manifest = "".join(
            f'<opf:item id="s{index}" href="{name.removeprefix("Contents/")}" />'
            for index, name in enumerate(section_map)
        )
        id_by_name = {name: f"s{index}" for index, name in enumerate(section_map)}
        itemrefs = "".join(
            f'<opf:itemref idref="{id_by_name[name]}" />' for name in spine_order
        )
        content_hpf = (
            '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
            f"<opf:manifest>{manifest}</opf:manifest>"
            f"<opf:spine>{itemrefs}</opf:spine>"
            "</opf:package>"
        )

    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/hwp+zip", compress_type=ZIP_STORED)
        archive.writestr("Contents/content.hpf", content_hpf)
        for name, xml in section_map.items():
            archive.writestr(name, xml, compress_type=ZIP_DEFLATED)
        for name, data in (extra_members or {}).items():
            archive.writestr(name, data, compress_type=ZIP_DEFLATED)
    return path
