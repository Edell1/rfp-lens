import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { api, type AnalysisOverview, type RequirementRecord } from "../src/app/api";
import { AnalysisOverviewPage } from "../src/features/overview/AnalysisOverviewPage";

const requirement: RequirementRecord = {
  id: "11111111-1111-4111-8111-111111111111",
  project_id: "project-1",
  document_id: "document-1",
  text: "중소기업만 신청 가능",
  category: "eligibility",
  mandatory: true,
  confidence: "high",
  review_state: "confirmed",
  created_at: "2026-08-27T00:00:00Z",
  updated_at: "2026-08-27T00:00:00Z",
  evidence: [{
    id: "evidence-1",
    block_id: "block-1",
    quote: "중소기업만 신청 가능",
    verified: true,
    locator: { format: "hwpx", section: "section0.xml", paragraph: 0, table: 2, row: 1, column: 3 },
  }],
};

const overview: AnalysisOverview = {
  empty: false,
  effective_scope: "reviewed",
  summary_state: "succeeded",
  stale: false,
  stats: { total: 3, confirmed_or_edited: 1, pending: 1, rejected: 1, unverified_evidence: 1 },
  category_counts: { eligibility: 1, exclusion: 0, schedule: 0, budget: 0, submission: 0, technical_goal: 0, quantitative_target: 0, evaluation: 0, other: 0 },
  highlights: [{ category: "eligibility", headline: "중소기업 지원 자격", detail: "신청 가능 기업 유형 확인", requirement_ids: [requirement.id] }],
  fallback_requirements: [],
  updated_at: "2026-08-27T00:00:00Z",
};

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function renderPage(): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={["/projects/project-1/overview"]}><Routes><Route path="/projects/:projectId/overview" element={<AnalysisOverviewPage />} /></Routes></MemoryRouter></QueryClientProvider>);
}

describe("analysis overview", () => {
  it("shows deterministic stats, AI highlight, evidence, and review deep link", async () => {
    vi.spyOn(api, "getAnalysisOverview").mockResolvedValue(overview);
    vi.spyOn(api, "listRequirements").mockResolvedValue([requirement]);

    renderPage();

    expect(await screen.findByText("중소기업 지원 자격")).toBeInTheDocument();
    expect(screen.getByText("전체 요구사항").parentElement).toHaveTextContent("3");
    expect(screen.getByText("중소기업만 신청 가능", { selector: "blockquote" })).toBeInTheDocument();
    expect(screen.getByText(/문단 0 · 표 2 · 1행 3열/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "요구사항 검토에서 열기" })).toHaveAttribute(
      "href",
      `/projects/project-1/review?requirement=${requirement.id}`,
    );
  });

  it("requests all scope when pre-review items are included", async () => {
    const getOverview = vi.spyOn(api, "getAnalysisOverview").mockResolvedValue(overview);
    vi.spyOn(api, "listRequirements").mockResolvedValue([requirement]);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("중소기업 지원 자격");

    await user.click(screen.getByRole("checkbox", { name: "검토 전 항목 포함" }));

    expect(getOverview).toHaveBeenCalledWith("project-1", "all");
  });

  it("keeps non-core fallback requirements in a separate review section", async () => {
    vi.spyOn(api, "getAnalysisOverview").mockResolvedValue({
      ...overview,
      summary_state: "failed",
      highlights: [],
      fallback_requirements: [{
        id: "other-1",
        text: "기타 협약 조건",
        category: "other",
        mandatory: false,
        review_state: "pending",
        evidence: [{ quote: "협약 시 별도 안내", verified: true, locator: { format: "pdf", page: 8 } }],
      }],
    });
    vi.spyOn(api, "listRequirements").mockResolvedValue([]);

    renderPage();

    expect(await screen.findByRole("heading", { name: "추가 검토 항목" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "핵심 조건" })).not.toBeInTheDocument();
    expect(screen.getByText("기타 요구사항 1건")).toBeInTheDocument();
    expect(screen.getByText("기타 협약 조건")).toBeInTheDocument();
  });

  it("shows a project link for an empty overview", async () => {
    vi.spyOn(api, "getAnalysisOverview").mockResolvedValue({
      ...overview,
      empty: true,
      stats: { total: 0, confirmed_or_edited: 0, pending: 0, rejected: 0, unverified_evidence: 0 },
      highlights: [],
    });
    vi.spyOn(api, "listRequirements").mockResolvedValue([]);

    renderPage();

    expect(await screen.findByRole("heading", { name: "아직 분석 결과가 없습니다" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "프로젝트 상세로 돌아가기" })).toHaveAttribute("href", "/projects/project-1");
  });

  it("labels a preserved summary when stale regeneration fails", async () => {
    vi.spyOn(api, "getAnalysisOverview").mockResolvedValue({
      ...overview,
      stale: true,
      summary_state: "failed",
    });
    vi.spyOn(api, "listRequirements").mockResolvedValue([requirement]);

    renderPage();

    expect(await screen.findByText("최신 요약 생성에 실패해 이전 요약을 표시합니다.")).toBeInTheDocument();
    expect(screen.getByText("중소기업 지원 자격")).toBeInTheDocument();
  });
});
