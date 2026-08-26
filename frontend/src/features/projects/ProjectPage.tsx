import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api, type DocumentRecord } from "../../app/api";
import { ProcessingStatus, isPollingState } from "../documents/ProcessingStatus";
import { UploadPanel } from "../documents/UploadPanel";

export function documentPollingInterval(documents: DocumentRecord[] | undefined): number | false {
  return documents?.some((document) => isPollingState(document.state)) ? 2_000 : false;
}

export function ProjectPage(): React.ReactElement {
  const { projectId } = useParams<{ projectId: string }>();
  const queryClient = useQueryClient();
  if (!projectId) return <p className="form-error">프로젝트를 찾을 수 없습니다.</p>;
  const documents = useQuery({
    queryKey: ["documents", projectId],
    queryFn: () => api.listDocuments(projectId),
    refetchInterval: (query) => documentPollingInterval(query.state.data),
  });
  const upload = useMutation({
    mutationFn: (file: File) => api.uploadDocument(projectId, file),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["documents", projectId] }),
  });
  const process = useMutation({
    mutationFn: (document: DocumentRecord) => api.startProcessing(projectId, document.id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["documents", projectId] }),
  });

  return <main className="app-shell"><header className="topbar"><Link to="/projects" className="brand">RFP <em>Lens</em></Link><Link to="/projects" className="text-button">프로젝트 목록</Link></header>
    <section className="page-heading compact"><p className="eyebrow">PROJECT DETAIL</p><h1>공고문 분석</h1><p>파일을 올린 뒤 처리 상태를 확인하세요. 분석 완료 후 근거 기반 검토 화면으로 이어집니다.</p></section>
    <UploadPanel onUpload={async (file) => { await upload.mutateAsync(file); }} isUploading={upload.isPending} />
    <section className="document-history" aria-labelledby="document-history-title"><div className="section-heading"><div><p className="eyebrow">DOCUMENTS</p><h2 id="document-history-title">업로드한 공고문</h2></div>{documents.isFetching && <span className="muted">상태 갱신 중</span>}</div>
      {documents.isLoading && <p>문서 목록을 불러오는 중…</p>}
      {documents.isError && <p className="form-error" role="alert">문서 목록을 불러오지 못했습니다.</p>}
      <div className="document-list">{documents.data?.map((document) => <article key={document.id} className="document-row"><div><h3>{document.original_name}</h3><p className="muted">{document.media_type === "application/pdf" ? "PDF" : "HWPX"} · {document.block_count}개 블록</p></div><ProcessingStatus document={document} onRetry={(entry) => process.mutate(entry)} isRetrying={process.isPending && process.variables?.id === document.id} /></article>)}</div>
      {documents.data?.length === 0 && <p className="empty-state">아직 업로드한 공고문이 없습니다.</p>}
    </section>
  </main>;
}
