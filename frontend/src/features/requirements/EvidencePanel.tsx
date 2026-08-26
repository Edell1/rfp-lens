import type { RequirementEvidence } from "../../app/api";

export function formatLocator(locator: RequirementEvidence["locator"]): string {
  if (locator.format === "pdf") return locator.page ? `PDF p.${locator.page}` : "PDF 위치 정보 없음";
  const parts = ["HWPX"];
  if (locator.section) parts.push(locator.section);
  if (locator.paragraph !== undefined) parts.push(`문단 ${locator.paragraph}`);
  if (locator.table !== undefined) {
    const position = [locator.row !== undefined ? `${locator.row}행` : "", locator.column !== undefined ? `${locator.column}열` : ""].filter(Boolean).join(" ");
    parts.push(`표 ${locator.table}${position ? ` · ${position}` : ""}`);
  }
  return parts.join(" · ");
}

export function EvidencePanel({ evidence }: { evidence: RequirementEvidence[] }): React.ReactElement {
  if (!evidence.length) return <aside className="evidence-panel"><p className="muted">연결된 원문 근거가 없습니다.</p></aside>;
  return <aside className="evidence-panel" aria-label="원문 근거">
    <p className="eyebrow">SOURCE EVIDENCE</p><h2>원문 근거</h2>
    {evidence.map((item) => <article key={item.id} className="evidence-card"><div className="evidence-meta"><span>{formatLocator(item.locator)}</span><span className={item.verified ? "verified" : "unverified"}>{item.verified ? "인용 검증됨" : "인용 확인 필요"}</span></div><blockquote>{item.quote}</blockquote></article>)}
  </aside>;
}
