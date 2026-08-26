import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../../app/api";
import { useAuth } from "../auth/AuthProvider";

export function ProjectListPage(): React.ReactElement {
  const { user, logout } = useAuth();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
  const createProject = useMutation({
    mutationFn: api.createProject,
    onSuccess: () => { setName(""); void queryClient.invalidateQueries({ queryKey: ["projects"] }); },
  });
  const deleteProject = useMutation({
    mutationFn: api.deleteProject,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const normalized = name.trim();
    if (normalized) createProject.mutate(normalized);
  }

  return <main className="app-shell"><header className="topbar"><Link to="/projects" className="brand">RFP <em>Lens</em></Link><div><span className="muted">{user?.email}</span><Link className="text-button" to="/settings">분석 설정</Link><button className="text-button" onClick={logout}>로그아웃</button></div></header>
    <section className="page-heading"><p className="eyebrow">WORKSPACES</p><h1>제안 준비 프로젝트</h1><p>공고문을 올리고, 근거가 연결된 요구사항을 관리하세요.</p></section>
    <section className="create-project"><form onSubmit={submit}><label htmlFor="project-name">새 프로젝트 이름</label><div className="inline-form"><input id="project-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="예: 2027 스마트제조 R&D" maxLength={120} required /><button type="submit" disabled={createProject.isPending}>프로젝트 만들기</button></div>{createProject.isError && <p className="form-error" role="alert">프로젝트를 만들지 못했습니다.</p>}</form></section>
    {projects.isLoading && <p>프로젝트를 불러오는 중…</p>}
    {projects.isError && <p className="form-error" role="alert">프로젝트 목록을 불러오지 못했습니다.</p>}
    <section className="project-grid" aria-label="프로젝트 목록">{projects.data?.map((project) => <article key={project.id} className="project-card"><p className="eyebrow">PROJECT</p><h2><Link to={`/projects/${project.id}`}>{project.name}</Link></h2><p className="muted">마지막 수정 {new Date(project.updated_at).toLocaleDateString("ko-KR")}</p><div><Link className="button-link" to={`/projects/${project.id}`}>열기</Link><button className="text-button danger" onClick={() => deleteProject.mutate(project.id)} disabled={deleteProject.isPending}>삭제</button></div></article>)}</section>
    {projects.data?.length === 0 && <p className="empty-state">아직 프로젝트가 없습니다. 첫 공고문 분석 공간을 만들어 보세요.</p>}
  </main>;
}
