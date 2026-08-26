import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { RequirementRecord } from "../src/app/api";
import { EvidencePanel } from "../src/features/requirements/EvidencePanel";
import { RequirementCard } from "../src/features/requirements/RequirementCard";

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
});
