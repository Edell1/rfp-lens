import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { api, type RequirementRecord } from "../src/app/api";
import { EvidencePanel } from "../src/features/requirements/EvidencePanel";
import { RequirementCard } from "../src/features/requirements/RequirementCard";
import { RequirementReviewPage } from "../src/features/requirements/RequirementReviewPage";

const requirement: RequirementRecord = {
  id: "requirement-1", project_id: "project-1", document_id: "document-1",
  text: "중소기업만 신청 가능", category: "eligibility", mandatory: true,
  confidence: "high", review_state: "pending", created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
  evidence: [{ id: "evidence-1", block_id: "block-1", quote: "중소기업만 신청 가능", verified: false, locator: { format: "hwpx", section: "Contents/section0.xml", paragraph: 8, table: 2, row: 1, column: 1 } }],
};

afterEach(cleanup);

describe("requirement review", () => {
  it("requires confirmation before accepting unverified evidence", async () => {
    const user = userEvent.setup();
    const patch = vi.fn();
    render(<RequirementCard requirement={requirement} selected onSelect={vi.fn()} onPatch={patch} />);

    await user.click(screen.getByRole("button", { name: "확정" }));

    expect(screen.getByRole("dialog", { name: "검증되지 않은 근거" })).toBeInTheDocument();
    expect(patch).not.toHaveBeenCalled();
  });

  it("displays only source fields available for a PDF locator", () => {
    render(<EvidencePanel evidence={[{ ...requirement.evidence[0], locator: { format: "pdf", page: 12 } }]} />);

    expect(screen.getByText("PDF p.12")).toBeInTheDocument();
    expect(screen.queryByText(/HWPX/)).not.toBeInTheDocument();
  });

  it("opens the requirement selected by the overview deep link", async () => {
    const target = {
      ...requirement,
      id: "requirement-2",
      text: "정부출연금은 5억원 이내",
      category: "budget" as const,
      evidence: [{
        ...requirement.evidence[0],
        id: "evidence-2",
        quote: "정부출연금은 총 5억원 이내이다.",
      }],
    };
    vi.spyOn(api, "listRequirements").mockResolvedValue([requirement, target]);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={["/projects/project-1/review?requirement=requirement-2"]}><Routes><Route path="/projects/:projectId/review" element={<RequirementReviewPage />} /></Routes></MemoryRouter></QueryClientProvider>);

    expect(await screen.findByText("정부출연금은 총 5억원 이내이다.", { selector: "blockquote" })).toBeInTheDocument();
  });
});
