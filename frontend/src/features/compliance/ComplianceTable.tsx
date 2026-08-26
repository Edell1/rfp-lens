import { useEffect, useState } from "react";

import type { CompliancePatch, ComplianceRecord, ComplianceStatus, Importance } from "../../app/api";

interface ComplianceTableProps {
  items: ComplianceRecord[];
  onSave(item: ComplianceRecord, patch: CompliancePatch): void;
  savingId: string | null;
}

interface Draft { importance: Importance; proposal_section: string; owner_note: string; status: ComplianceStatus; }

function initialDraft(item: ComplianceRecord): Draft {
  return { importance: item.importance, proposal_section: item.proposal_section, owner_note: item.owner_note, status: item.status };
}

export function ComplianceTable({ items, onSave, savingId }: ComplianceTableProps): React.ReactElement {
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  useEffect(() => setDrafts(Object.fromEntries(items.map((item) => [item.id, initialDraft(item)]))), [items]);
  function update(item: ComplianceRecord, field: keyof Draft, value: string): void { setDrafts((current) => ({ ...current, [item.id]: { ...(current[item.id] ?? initialDraft(item)), [field]: value } as Draft })); }

  if (!items.length) return <p className="empty-state">확정하거나 수정한 요구사항이 아직 없습니다.</p>;
  return <div className="table-scroll"><table className="compliance-table"><thead><tr><th>요구사항</th><th>근거</th><th>중요도</th><th>제안서 반영 위치</th><th>상태</th><th>메모</th><th>저장</th></tr></thead><tbody>{items.map((item) => {
    const draft = drafts[item.id] ?? initialDraft(item);
    return <tr key={item.id}><td><strong>{item.requirement_text}</strong><small>{item.category} · {item.mandatory ? "필수" : "권고"}</small></td><td><q>{item.evidence_quote}</q><small>{item.source_location}</small></td><td><label>중요도<select aria-label="중요도" value={draft.importance} onChange={(event) => update(item, "importance", event.target.value)}><option value="required">필수</option><option value="high">높음</option><option value="medium">중간</option><option value="low">낮음</option></select></label></td><td><label>제안서 반영 위치<input aria-label="제안서 반영 위치" value={draft.proposal_section} onChange={(event) => update(item, "proposal_section", event.target.value)} /></label></td><td><label>상태<select aria-label="상태" value={draft.status} onChange={(event) => update(item, "status", event.target.value)}><option value="not_started">미착수</option><option value="in_progress">진행 중</option><option value="complete">완료</option><option value="not_applicable">해당 없음</option></select></label></td><td><label>메모<textarea aria-label="메모" value={draft.owner_note} onChange={(event) => update(item, "owner_note", event.target.value)} /></label></td><td><button onClick={() => onSave(item, { updated_at: item.updated_at, ...draft })} disabled={savingId === item.id}>저장</button></td></tr>;
  })}</tbody></table></div>;
}
