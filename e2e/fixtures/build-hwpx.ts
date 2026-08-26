import { strToU8, zipSync } from "fflate";

const SECTION_XML = `<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.owpml.org/owpml/2021/section"
        xmlns:hp="http://www.owpml.org/owpml/2021/paragraph">
  <hp:p><hp:run><hp:t>1. 지원 자격</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>중소기업만 신청 가능</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>2. 사업 개요</hp:t></hp:run></hp:p>
  <hp:tbl>
    <hp:tr><hp:tc><hp:subList><hp:p><hp:run><hp:t>정부출연금은 총 5억원 이내이다.</hp:t></hp:run></hp:p></hp:subList></hp:tc></hp:tr>
  </hp:tbl>
</hs:sec>
`;

const CONTENT_HPF =
  '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">' +
  '<opf:manifest><opf:item id="s0" href="section0.xml" /></opf:manifest>' +
  '<opf:spine><opf:itemref idref="s0" /></opf:spine>' +
  "</opf:package>";

export function buildHwpxBuffer(): Buffer {
  const zipped = zipSync({
    mimetype: [strToU8("application/hwp+zip"), { level: 0 }],
    "Contents/content.hpf": strToU8(CONTENT_HPF),
    "Contents/section0.xml": strToU8(SECTION_XML),
  });
  return Buffer.from(zipped);
}
