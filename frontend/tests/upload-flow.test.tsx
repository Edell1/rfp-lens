import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type { DocumentRecord } from "../src/app/api";
import { createQueryClient } from "../src/app/query-client";
import { AppRouter } from "../src/app/router";
import { AuthProvider } from "../src/features/auth/AuthProvider";
import { documentPollingInterval, ProjectPage } from "../src/features/projects/ProjectPage";

const baseUrl = "http://localhost:8000/api";
let activeDocument: DocumentRecord;
const processRequest = vi.fn();
const deleteRequest = vi.fn();
const server = setupServer(
  http.get(`${baseUrl}/projects/project-1/documents`, () => HttpResponse.json([activeDocument])),
  http.post(`${baseUrl}/projects/project-1/documents`, () => HttpResponse.json(activeDocument, { status: 201 })),
  http.post(`${baseUrl}/projects/project-1/documents/:documentId/process`, () => {
    processRequest();
    return HttpResponse.json({ ...activeDocument, state: "parsing" });
  }),
  http.delete(`${baseUrl}/projects/project-1/documents/:documentId`, () => {
    deleteRequest();
    return new HttpResponse(null, { status: 204 });
  }),
);

function fixture(state: DocumentRecord["state"], errorCode: string | null = null): DocumentRecord {
  return {
    id: "document-1", project_id: "project-1", original_name: "2027-rfp.hwpx",
    media_type: "application/hwp+zip", checksum_sha256: "a".repeat(64), state,
    error_code: errorCode, error_message: null, block_count: 3,
    created_at: "2026-08-26T00:00:00Z", updated_at: "2026-08-26T00:00:00Z",
  };
}

function renderProjectPageWithApi(document: DocumentRecord): void {
  activeDocument = document;
  render(<QueryClientProvider client={createQueryClient()}><MemoryRouter initialEntries={["/projects/project-1"]}><Routes><Route path="/projects/:projectId" element={<ProjectPage />} /></Routes></MemoryRouter></QueryClientProvider>);
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => { cleanup(); server.resetHandlers(); processRequest.mockReset(); deleteRequest.mockReset(); });
afterAll(() => server.close());

describe("project upload flow", () => {
  it("shows OCR guidance when the server marks a scan", async () => {
    renderProjectPageWithApi(fixture("ocr_required", "ocr_required"));
    expect(await screen.findByText("텍스트가 없는 스캔 PDF입니다")).toBeInTheDocument();
    expect(screen.getByText("텍스트 PDF 또는 HWPX로 다시 업로드해 주세요")).toBeInTheDocument();
  });

  it("accepts PDF and HWPX in the file picker", async () => {
    renderProjectPageWithApi(fixture("uploaded"));
    const picker = await screen.findByLabelText("파일 선택");
    expect(picker).toHaveAttribute("accept", ".pdf,.hwpx,application/pdf,application/hwp+zip");
  });

  it("rejects legacy HWP before upload", async () => {
    renderProjectPageWithApi(fixture("uploaded"));
    fireEvent.change(await screen.findByLabelText("파일 선택"), {
      target: { files: [new File(["legacy"], "notice.hwp")] },
    });
    expect(screen.getByRole("alert")).toHaveTextContent("PDF 또는 HWPX 파일만");
  });

  it("rejects files over 25MiB before upload", async () => {
    renderProjectPageWithApi(fixture("uploaded"));
    const oversized = new File([new Uint8Array(26_214_401)], "large.pdf", { type: "application/pdf" });
    fireEvent.change(await screen.findByLabelText("파일 선택"), { target: { files: [oversized] } });
    expect(screen.getByRole("alert")).toHaveTextContent("25MiB");
  });

  it("shows a partial result banner and retries failed processing", async () => {
    const user = userEvent.setup();
    renderProjectPageWithApi(fixture("partial"));
    expect(await screen.findByText("일부 요구사항만 추출됐습니다")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "다시 분석" }));
    await waitFor(() => expect(processRequest).toHaveBeenCalledOnce());
  });

  it("starts analysis for an uploaded document", async () => {
    const user = userEvent.setup();
    renderProjectPageWithApi(fixture("uploaded"));
    await user.click(await screen.findByRole("button", { name: "분석 시작" }));
    await waitFor(() => expect(processRequest).toHaveBeenCalledOnce());
  });

  it("removes an uploaded document", async () => {
    const user = userEvent.setup();
    renderProjectPageWithApi(fixture("review_required"));
    await user.click(await screen.findByRole("button", { name: "삭제" }));
    await waitFor(() => expect(deleteRequest).toHaveBeenCalledOnce());
  });

  it("polls only while a document is active", () => {
    expect(documentPollingInterval([fixture("analyzing")])).toBe(2_000);
    expect(documentPollingInterval([fixture("review_required")])).toBe(false);
  });

  it("redirects unauthenticated users to login", async () => {
    sessionStorage.clear();
    render(<QueryClientProvider client={createQueryClient()}><MemoryRouter initialEntries={["/projects"]}><AuthProvider><AppRouter /></AuthProvider></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByRole("heading", { name: "다시 오셨네요" })).toBeInTheDocument();
  });
});
