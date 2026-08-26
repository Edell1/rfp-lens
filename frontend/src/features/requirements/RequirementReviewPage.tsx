import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { ApiError, api, type RequirementPatch, type RequirementRecord } from "../../app/api";
import { EvidencePanel } from "./EvidencePanel";
import { RequirementCard } from "./RequirementCard";
import { categoryLabels } from "./filters";

export function RequirementReviewPage(): React.ReactElement {
  const { projectId } = useParams<{ projectId: string }>();
  const queryClient = useQueryClient();
  const [category, setCategory] = useState<"" | keyof typeof categoryLabels>("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  if (!projectId) return <p className="form-error">프로젝트를 찾을 수 없습니다.</p>;
  const requirements = useQuery({ queryKey: ["requirements", projectId, category], queryFn: () => api.listRequirements(projectId, category ? { category } : {}) });
  const patch = useMutation({
    mutationFn: ({ requirement, payload }: { requirement: RequirementRecord; payload: RequirementPatch }) => api.patchRequirement(projectId, requirement.id, payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["requirements", projectId] }),
    onError: (error) => { if (error instanceof ApiError && error.status === 409) { setConflict(true); void queryClient.invalidateQueries({ queryKey: ["requirements", projectId] }); } },
  });
  const selected = requirements.data?.find((item) => item.id === selectedId) ?? requirements.data?.[0];

  return <main className="app-shell"><header className="topbar"><Link to={`/projects/${projectId}`} className="brand">RFP <em>Lens</em></Link><Link to={`/projects/${projectId}/compliance`} className="text-button">컴플라이언스 표</Link></header>
    <section className="page-heading compact"><p className="eyebrow">EVIDENCE REVIEW</p><h1>요구사항 검토</h1><p>AI 추출 결과를 원문 근거와 비교하고 제안서 체크 항목으로 확정하세요.</p></section>
    {conflict && <div className="conflict-banner" role="alert">다른 변경이 먼저 저장됐습니다. 최신 내용으로 새로고침했습니다.<button className="text-button" onClick={() => setConflict(false)}>닫기</button></div>}
    <label className="filter-label" htmlFor="category-filter">분류 필터<select id="category-filter" value={category} onChange={(event) => setCategory(event.target.value as "" | keyof typeof categoryLabels)}><option value="">모든 분류</option>{Object.entries(categoryLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
    <section className="review-workspace"><div className="requirement-list">{requirements.isLoading && <p>요구사항을 불러오는 중…</p>}{requirements.isError && <p className="form-error" role="alert">요구사항을 불러오지 못했습니다.</p>}{requirements.data?.map((requirement) => <RequirementCard key={requirement.id} requirement={requirement} selected={selected?.id === requirement.id} onSelect={() => setSelectedId(requirement.id)} onPatch={(payload) => patch.mutate({ requirement, payload })} isSaving={patch.isPending && patch.variables?.requirement.id === requirement.id} />)}{requirements.data?.length === 0 && <p className="empty-state">현재 필터에 맞는 요구사항이 없습니다.</p>}</div><EvidencePanel evidence={selected?.evidence ?? []} /></section>
  </main>;
}
