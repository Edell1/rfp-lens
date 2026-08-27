import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api, type SummaryHighlight } from "../../app/api";
import { CoreHighlights } from "./CoreHighlights";
import { AdditionalHighlights } from "./AdditionalHighlights";
import { HighlightEvidence } from "./HighlightEvidence";
import { OverviewStats } from "./OverviewStats";
import { ReviewProgress } from "./ReviewProgress";
import { fallbackAsHighlights, linkedRequirements, overviewPollingInterval } from "./overview";

export function AnalysisOverviewPage(): React.ReactElement {
  const { projectId } = useParams<{ projectId: string }>();
  const [includePending, setIncludePending] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const requestedScope = includePending ? "all" : "auto";
  if (!projectId) return <p className="form-error">프로젝트를 찾을 수 없습니다.</p>;
  const overview = useQuery({ queryKey: ["analysis-overview", projectId, requestedScope], queryFn: () => api.getAnalysisOverview(projectId, requestedScope), refetchInterval: (query) => overviewPollingInterval(query.state.data) });
  const requirements = useQuery({ queryKey: ["requirements", projectId], queryFn: () => api.listRequirements(projectId) });
  const highlights = useMemo(() => overview.data?.highlights.length ? overview.data.highlights : fallbackAsHighlights(overview.data?.fallback_requirements ?? []), [overview.data]);
  const selected = highlights.find((item) => `${item.category}-${item.headline}` === selectedKey) ?? highlights[0];
  const connected = overview.data?.fallback_requirements.length ? overview.data.fallback_requirements.filter((item) => selected?.requirement_ids.includes(item.id)) : linkedRequirements(selected, requirements.data);

  return <main className="app-shell"><header className="topbar"><Link to={`/projects/${projectId}`} className="brand">RFP <em>Lens</em></Link><div><Link to={`/projects/${projectId}/review`} className="text-button">요구사항 검토</Link><Link to={`/projects/${projectId}/compliance`} className="text-button">컴플라이언스 표</Link></div></header>
    <section className="page-heading compact overview-heading"><div><p className="eyebrow">ANALYSIS OVERVIEW</p><h1>최종 분석 결과</h1><p>핵심 조건과 검토 현황을 한눈에 보고 원문 근거까지 확인하세요.</p></div><label className="scope-toggle"><input type="checkbox" checked={includePending} onChange={(event) => setIncludePending(event.target.checked)} />검토 전 항목 포함</label></section>
    {overview.isLoading && <p>분석 결과를 불러오는 중…</p>}{overview.isError && <p className="form-error" role="alert">최종 분석 결과를 불러오지 못했습니다.</p>}
    {overview.data?.empty && <section className="empty-state overview-empty"><h2>아직 분석 결과가 없습니다</h2><p>공고문을 업로드하고 분석을 완료하면 핵심 조건과 검토 현황이 표시됩니다.</p><Link className="button-link" to={`/projects/${projectId}`}>프로젝트 상세로 돌아가기</Link></section>}
    {overview.data && !overview.data.empty && <><OverviewStats stats={overview.data.stats} />{overview.data.effective_scope === "all" && !includePending && <p className="scope-note">확정·수정된 항목이 없어 검토 전 요구사항 기준으로 표시합니다.</p>}{overview.data.stale && <div className="status-card warning">{overview.data.summary_state === "failed" ? "최신 요약 생성에 실패해 이전 요약을 표시합니다." : "기존 요약을 표시하며 최신 검토 내용으로 업데이트 중입니다."}</div>}<section className="overview-main"><div>{highlights.length > 0 ? <CoreHighlights highlights={highlights} selected={selected} onSelect={(item: SummaryHighlight) => setSelectedKey(`${item.category}-${item.headline}`)} /> : <div className="summary-state-card"><h2>핵심 조건을 정리하고 있어요</h2><p>{overview.data.summary_state === "failed" ? "AI 요약에 실패했습니다. 원문 요구사항을 확인해 주세요." : "통계는 먼저 확인할 수 있습니다. 요약이 완료되면 자동으로 표시됩니다."}</p></div>}<AdditionalHighlights highlights={highlights} selected={selected} onSelect={(item) => setSelectedKey(`${item.category}-${item.headline}`)} /></div><ReviewProgress stats={overview.data.stats} /></section><HighlightEvidence projectId={projectId} highlight={selected} requirements={connected} /></>}
  </main>;
}
