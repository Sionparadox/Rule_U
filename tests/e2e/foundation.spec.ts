import { expect, test } from "@playwright/test";

test("select game, save question, restore after reload", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByText("서비스 연결됨")).toBeVisible();
  await page.getByRole("button", { name: /연결 확인용 샘플 게임/ }).click();
  await page.getByRole("textbox", { name: "규칙 질문" }).fill("저장된 대화를 다시 볼 수 있나요?");
  await page.getByRole("button", { name: "질문 보내기" }).click();
  await expect(page.getByText(/\[테스트 응답\]/)).toBeVisible();
  await page.reload();
  await expect(page.getByText("저장된 대화를 다시 볼 수 있나요?")).toBeVisible();
  await expect(page.getByText(/\[테스트 응답\]/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("foundation.png"), fullPage: true });
});
