import { expect, test } from "@playwright/test";

import { buildHwpxBuffer } from "./fixtures/build-hwpx";

test("register, analyze hwpx, inspect overview, review, and export xlsx", async ({
  page,
}) => {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}@example.com`;

  await page.goto("/register");
  await page.getByLabel("이메일").fill(email);
  await page.getByLabel("비밀번호").fill("Correct-Horse-2026");
  await page.getByRole("button", { name: "계정 만들기" }).click();
  await expect(page).toHaveURL(/\/projects$/);

  await page.getByLabel("새 프로젝트 이름").fill("E2E 합성 공고");
  await page.getByRole("button", { name: "프로젝트 만들기" }).click();
  const projectLink = page.getByRole("link", { name: "E2E 합성 공고" });
  await expect(projectLink).toBeVisible();
  await projectLink.click();

  await page
    .getByLabel("파일 선택")
    .setInputFiles({
      name: "synthetic-rfp.hwpx",
      mimeType: "application/octet-stream",
      buffer: buildHwpxBuffer(),
    });
  await expect(page.getByText("분석을 시작할 준비가 됐어요")).toBeVisible();
  await page.getByRole("button", { name: "분석 시작" }).click();
  await expect(page.getByText("검토할 요구사항이 준비됐어요")).toBeVisible({
    timeout: 30_000,
  });

  await page.getByRole("link", { name: "최종 분석 결과" }).click();
  await expect(page.getByRole("heading", { name: "최종 분석 결과" })).toBeVisible();
  await expect(page.getByText("전체 요구사항").locator("..")).toContainText("2");
  await page.getByRole("button", { name: /중소기업만 신청 가능/ }).click();
  await expect(page.getByText("중소기업만 신청 가능", { exact: true }).last()).toBeVisible();
  await page.getByRole("link", { name: "요구사항 검토에서 열기" }).click();
  await expect(page).toHaveURL(/\/review\?requirement=/);
  const card = page.locator(".requirement-card", {
    hasText: "중소기업만 신청 가능",
  });
  await expect(card).toBeVisible();
  await card.getByRole("button", { name: "확정" }).click();
  await expect(
    page.locator(".requirement-card .review-state.confirmed")
  ).toHaveCount(1);

  await page.getByRole("link", { name: "컴플라이언스 표" }).click();
  await expect(page.getByRole("heading", { name: "제안서 반영 현황" })).toBeVisible();
  await page.getByLabel("제안서 반영 위치").fill("3. 연구개발 목표");
  await page.getByLabel("상태").selectOption({ label: "완료" });
  const saveResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/compliance/") &&
      response.request().method() === "PATCH"
  );
  await page.getByRole("button", { name: "저장" }).click();
  expect((await saveResponse).status()).toBe(200);

  const [download, exportResponse] = await Promise.all([
    page.waitForEvent("download"),
    page.waitForResponse((response) => response.url().includes("compliance.xlsx")),
    page.getByRole("button", { name: "Excel 내보내기" }).click(),
  ]);
  expect(exportResponse.headers()["content-type"]).toContain(
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  );
  expect(download.suggestedFilename()).toBe("compliance.xlsx");
});
