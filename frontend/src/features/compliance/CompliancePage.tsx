import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { ApiError, api, type CompliancePatch, type ComplianceRecord } from "../../app/api";
import { ComplianceTable } from "./ComplianceTable";
import { ExportButton } from "./ExportButton";

export function CompliancePage(): React.ReactElement {
  const { projectId } = useParams<{ projectId: string }>();
  const queryClient = useQueryClient();
  const [conflict, setConflict] = useState(false);
  if (!projectId) return <p className="form-error">프로젝트를 찾을 수 없습니다.</p>;
  const matrix = useQuery({ queryKey: ["compliance", projectId], queryFn: () => api.listCompliance(projectId) });
  const patch = useMutation({
    mutationFn: ({ item, payload }: { item: ComplianceRecord; payload: CompliancePatch }) => api.patchCompliance(projectId, item.id, payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["compliance", projectId] }),
    onError: (error) => { if (error instanceof ApiError && error.status === 409) { setConflict(true); void queryClient.invalidateQueries({ queryKey: ["compliance", projectId] }); } },
  });
  return <main className="app-shell"><header className="topbar"><Link to={`/projects/${projectId}`} className="brand">RFP <em>Lens</em></Link><Link to={`/projects/${projectId}/review`} className="text-button">요구사항 검토</Link></header>
    <section className="page-heading compact"><p className="eyebrow">COMPLIANCE MATRIX</p><h1>제안서 반영 현황</h1><p>확정한 공고문 요구사항을 제안서 목차와 연결해 관리하세요.</p><ExportButton projectId={projectId} /></section>
    {conflict && <div className="conflict-banner" role="alert">다른 변경이 먼저 저장됐습니다. 최신 내용으로 새로고침했습니다.<button className="text-button" onClick={() => setConflict(false)}>닫기</button></div>}
    {matrix.isLoading && <p>컴플라이언스 표를 불러오는 중…</p>}{matrix.isError && <p className="form-error" role="alert">컴플라이언스 표를 불러오지 못했습니다.</p>}{matrix.data && <ComplianceTable items={matrix.data} onSave={(item, payload) => patch.mutate({ item, payload })} savingId={patch.isPending ? patch.variables?.item.id ?? null : null} />}
  </main>;
}
