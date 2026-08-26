import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { ComplianceRecord } from "../src/app/api";
import { ComplianceTable } from "../src/features/compliance/ComplianceTable";

const item: ComplianceRecord = {
  id: "item-1", requirement_id: "requirement-1", requirement_text: "중소기업만 신청 가능",
  category: "eligibility", mandatory: true, evidence_quote: "중소기업만 신청 가능",
  source_location: "Contents/section0.xml 문단 8", importance: "required",
  proposal_section: "", owner_note: "", status: "not_started",
  created_at: "2026-08-26T00:00:00Z", updated_at: "2026-08-26T00:00:00Z",
};

afterEach(cleanup);

describe("compliance matrix", () => {
  it("saves explicit row edits with the row timestamp", async () => {
    const user = userEvent.setup();
    const save = vi.fn().mockResolvedValue(undefined);
    render(<ComplianceTable items={[item]} onSave={save} savingId={null} />);

    await user.selectOptions(screen.getByLabelText("중요도"), "high");
    await user.type(screen.getByLabelText("제안서 반영 위치"), "2. 연구개발 필요성");
    await user.click(screen.getByRole("button", { name: "저장" }));

    expect(save).toHaveBeenCalledWith(item, expect.objectContaining({
      updated_at: item.updated_at, importance: "high", proposal_section: "2. 연구개발 필요성",
    }));
  });
});
