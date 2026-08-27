import { Link } from "react-router-dom";
import type { SummaryHighlight } from "../../app/api";
import type { LinkedRequirement } from "./overview";
import { formatLocator } from "../requirements/EvidencePanel";

export function HighlightEvidence({ projectId, highlight, requirements }: { projectId: string; highlight?: SummaryHighlight; requirements: LinkedRequirement[] }): React.ReactElement {
  return <section className="highlight-evidence" aria-labelledby="highlight-evidence-title"><p className="eyebrow">LINKED EVIDENCE</p><h2 id="highlight-evidence-title">연결 요구사항과 근거</h2>{!highlight && <p className="muted">핵심 조건을 선택하세요.</p>}{highlight && requirements.length === 0 && <p className="muted">현재 연결된 요구사항을 불러오는 중입니다.</p>}{requirements.map((requirement) => <article key={requirement.id}><h3>{requirement.text}</h3><p className="requirement-summary-meta">{requirement.mandatory ? "필수" : "권고"} · {requirement.review_state}</p>{requirement.evidence.map((evidence, index) => <div className="overview-evidence-quote" key={`${requirement.id}-${index}`}><span>{formatLocator(evidence.locator)} · {evidence.verified ? "근거 확인됨" : "확인 필요"}</span><blockquote>{evidence.quote}</blockquote></div>)}<Link className="button-link" to={`/projects/${projectId}/review?requirement=${requirement.id}`}>요구사항 검토에서 열기</Link></article>)}</section>;
}
