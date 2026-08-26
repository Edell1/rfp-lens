import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type { AnalysisSettings } from "../src/app/api";
import { createQueryClient } from "../src/app/query-client";
import { AnalysisSettingsPage } from "../src/features/settings/AnalysisSettingsPage";

const baseUrl = "http://localhost:8000/api";
const patchRequest = vi.fn();
const testRequest = vi.fn();
let currentSettings: AnalysisSettings;

function settingsFixture(overrides: Partial<AnalysisSettings> = {}): AnalysisSettings {
  return {
    ai_provider: "openai",
    openai_model: "gpt-5-mini",
    openai_api_key_set: false,
    local_base_url: "http://localhost:11434/v1",
    local_model: "",
    updated_at: "2026-08-26T00:00:00Z",
    ...overrides,
  };
}

const server = setupServer(
  http.get(`${baseUrl}/settings/analysis`, () => HttpResponse.json(currentSettings)),
  http.patch(`${baseUrl}/settings/analysis`, async ({ request }) => {
    const payload = (await request.json()) as Record<string, unknown>;
    patchRequest(payload);
    return HttpResponse.json({ ...currentSettings, ...payload, openai_api_key_set: true });
  }),
  http.post(`${baseUrl}/settings/analysis/test`, async ({ request }) => {
    const payload = (await request.json()) as { local_model?: string };
    testRequest(payload);
    if (payload.local_model === "missing-model") {
      return HttpResponse.json({
        ok: false,
        detail: "모델을 찾을 수 없습니다: missing-model",
        models: ["present-a"],
      });
    }
    return HttpResponse.json({ ok: true, detail: "연결 성공 · 모델 1개", models: ["present-a"] });
  }),
);

function renderSettingsPage(): void {
  render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={["/settings"]}>
        <Routes>
          <Route path="/settings" element={<AnalysisSettingsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  patchRequest.mockReset();
  testRequest.mockReset();
});
afterAll(() => server.close());

describe("analysis settings page", () => {
  it("loads stored settings into the form", async () => {
    currentSettings = settingsFixture({
      ai_provider: "local",
      local_base_url: "http://host.docker.internal:11434/v1",
      local_model: "qwen2.5:7b",
    });
    renderSettingsPage();

    const provider = await screen.findByLabelText("분석 엔진");
    expect(provider).toHaveValue("local");
    expect(screen.getByLabelText("로컬 서버 주소")).toHaveValue(
      "http://host.docker.internal:11434/v1"
    );
    expect(screen.getByLabelText("로컬 모델명")).toHaveValue("qwen2.5:7b");
  });

  it("saves a local model without sending an api key", async () => {
    const user = userEvent.setup();
    currentSettings = settingsFixture({ ai_provider: "openai" });
    renderSettingsPage();

    const providerSelect = await screen.findByLabelText("분석 엔진");
    await waitFor(() => expect(providerSelect).toHaveValue("openai"));
    await user.selectOptions(providerSelect, "local");
    await user.type(screen.getByLabelText("로컬 모델명"), "qwen2.5:7b");
    await user.click(screen.getByRole("button", { name: "저장" }));

    await waitFor(() =>
      expect(patchRequest).toHaveBeenCalledWith(
        expect.objectContaining({
          ai_provider: "local",
          local_model: "qwen2.5:7b",
        })
      )
    );
    expect(await screen.findByRole("status")).toHaveTextContent("설정이 저장되었습니다.");
  });

  it("hides the api key field and shows masking state for the local engine", async () => {
    currentSettings = settingsFixture({ ai_provider: "local", openai_api_key_set: true });
    renderSettingsPage();

    await screen.findByLabelText("분석 엔진");
    expect(screen.queryByLabelText("OpenAI API 키")).not.toBeInTheDocument();
  });

  it("keeps the stored key when submitting without typing a new one", async () => {
    const user = userEvent.setup();
    currentSettings = settingsFixture({ openai_api_key_set: true });
    renderSettingsPage();

    const providerSelect = await screen.findByLabelText("분석 엔진");
    await waitFor(() => expect(providerSelect).toHaveValue("openai"));
    await screen.findByText(/저장된 키 사용 중/);
    await user.click(screen.getByRole("button", { name: "저장" }));

    await waitFor(() =>
      expect(patchRequest).toHaveBeenCalledWith(
        expect.not.objectContaining({ openai_api_key: expect.anything() })
      )
    );
  });

  it("shows a successful connection test for a reachable local model", async () => {
    const user = userEvent.setup();
    currentSettings = settingsFixture({
      ai_provider: "local",
      local_base_url: "http://host.docker.internal:1234/v1",
      local_model: "qwen/qwen3.6-27b",
    });
    renderSettingsPage();

    await waitFor(() =>
      expect(screen.getByLabelText("분석 엔진")).toHaveValue("local")
    );
    await user.click(screen.getByRole("button", { name: "연결 테스트" }));

    await waitFor(() => expect(testRequest).toHaveBeenCalledOnce());
    expect(await screen.findByRole("status")).toHaveTextContent("연결 성공");
  });

  it("surfaces model errors from the connection test", async () => {
    const user = userEvent.setup();
    currentSettings = settingsFixture({ ai_provider: "local" });
    renderSettingsPage();

    const providerSelect = await screen.findByLabelText("분석 엔진");
    await waitFor(() => expect(providerSelect).toHaveValue("local"));
    await user.type(screen.getByLabelText("로컬 모델명"), "missing-model");
    await user.click(screen.getByRole("button", { name: "연결 테스트" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("모델을 찾을 수 없습니다");
    expect(alert).toHaveTextContent("present-a");
  });
});
