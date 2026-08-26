import { useState } from "react";

import type { RequirementPatch, RequirementRecord } from "../../app/api";
import { categoryLabels, reviewLabels } from "./filters";

interface RequirementCardProps {
  requirement: RequirementRecord;
  selected: boolean;
  onSelect(): void;
  onPatch(payload: RequirementPatch): void;
  isSaving?: boolean;
}

export function RequirementCard({ requirement, selected, onSelect, onPatch, isSaving = false }: RequirementCardProps): React.ReactElement {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(requirement.text);
  const [pendingPatch, setPendingPatch] = useState<RequirementPatch | null>(null);
  const unverified = requirement.evidence.some((evidence) => !evidence.verified);
  const base = { updated_at: requirement.updated_at };

  function requestPatch(payload: RequirementPatch): void {
    if (unverified && (payload.review_state === "confirmed" || payload.text !== undefined)) {
      setPendingPatch(payload);
      return;
    }
    onPatch(payload);
  }

  function saveEdit(): void {
    const normalized = text.trim();
    if (normalized.length < 3 || normalized === requirement.text) { setEditing(false); return; }
    requestPatch({ ...base, text: normalized });
    setEditing(false);
  }

  return <article className={`requirement-card ${selected ? "selected" : ""}`} onClick={onSelect}>
    <div className="requirement-meta"><span>{categoryLabels[requirement.category]}</span><span>{requirement.mandatory ? "필수" : "권고"}</span><span>{requirement.confidence} 신뢰도</span></div>
    {editing ? <textarea aria-label="요구사항 문구" value={text} onChange={(event) => setText(event.target.value)} onClick={(event) => event.stopPropagation()} /> : <h3>{requirement.text}</h3>}
    <div className="requirement-footer"><span className={`review-state ${requirement.review_state}`}>{reviewLabels[requirement.review_state]}</span><div className="card-actions" onClick={(event) => event.stopPropagation()}>
      {editing ? <><button className="text-button" onClick={() => setEditing(false)}>취소</button><button onClick={saveEdit} disabled={isSaving}>저장</button></> : <><button className="text-button" onClick={() => setEditing(true)}>수정</button><button className="text-button danger" onClick={() => requestPatch({ ...base, review_state: "rejected" })} disabled={isSaving}>제외</button><button onClick={() => requestPatch({ ...base, review_state: "confirmed" })} disabled={isSaving}>확정</button></>}
    </div></div>
    {pendingPatch && <div className="modal-backdrop" role="presentation" onClick={() => setPendingPatch(null)}><div className="confirmation-dialog" role="dialog" aria-modal="true" aria-label="검증되지 않은 근거" onClick={(event) => event.stopPropagation()}><h2>검증되지 않은 근거</h2><p>원문 인용이 자동으로 검증되지 않았습니다. 직접 확인한 뒤 계속할까요?</p><div><button className="text-button" onClick={() => setPendingPatch(null)}>취소</button><button onClick={() => { onPatch({ ...pendingPatch, confirm_unverified: true }); setPendingPatch(null); }} disabled={isSaving}>확인 후 계속</button></div></div></div>}
  </article>;
}
