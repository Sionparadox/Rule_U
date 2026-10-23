import { expect, test, type Page } from "@playwright/test";

async function choose(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /테이블 탐험/ }).click();
  await page.getByRole("button", { name: "이 게임으로 대화하기" }).click();
  await expect(page.getByRole("textbox", { name: "규칙 질문" })).toBeEnabled();
}
const question = (page: Page) =>
  page.getByRole("textbox", { name: "규칙 질문" });
const sendButton = (page: Page) =>
  page.getByRole("button", { name: "질문 보내기" });

test("question starters, source badge, feedback and saved rules", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await choose(page);
  const starters = page.getByRole("group", { name: "질문 예시" });
  await starters.getByRole("button", { name: "처음 세팅" }).click();
  // 예시는 초안만 채우고 바로 보내지 않는다.
  await expect(question(page)).toHaveValue(
    "테이블 탐험 처음 세팅은 어떻게 하나요?",
  );
  await expect(page.locator("article")).toHaveCount(0);
  await sendButton(page).click();
  const source = page.getByRole("button", { name: "출처 1 자세히" });
  await expect(source).toBeVisible();
  await expect(source.getByText("출처 미확인")).toBeVisible();

  await page.getByRole("button", { name: "규칙이 달라요" }).click();
  await page.getByText("출처 페이지가 맞지 않아요").click();
  await page.getByPlaceholder(/룰북 7쪽/).fill("3쪽에 있어요");
  await page.getByRole("button", { name: "보내기", exact: true }).click();
  await expect(page.getByText("알려주셔서 고마워요")).toBeVisible();
  await page.getByRole("button", { name: "규칙 저장" }).click();
  await expect(page.getByRole("button", { name: "저장됨" })).toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: /이전 대화 이어하기/ }).click();
  await expect(
    page.getByRole("button", { name: "규칙이 달라요" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "저장됨" })).toBeVisible();

  await page.getByRole("button", { name: "저장한 규칙", exact: true }).click();
  const sheet = page.getByRole("dialog", { name: "저장한 규칙" });
  await sheet
    .getByRole("button", { name: /처음 세팅은 어떻게 하나요/ })
    .click();
  await expect(
    sheet.getByText("자신의 턴이 끝난 뒤 사용할 수 있어요. [1]"),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("saved-rules.png"),
    fullPage: true,
  });
  await sheet.getByRole("button", { name: /테이블 탐험 규칙서/ }).click();
  await expect(
    page.getByRole("dialog", { name: "왜 이렇게 답변했나요?" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("situation memo persists across questions and reloads", async ({
  page,
}) => {
  await choose(page);
  await page.getByRole("button", { name: "상황 판정", exact: true }).click();
  await page.getByRole("button", { name: /상황 메모/ }).click();
  await page.getByLabel("관련 카드·요소").fill("암살자");
  await page.getByLabel("현재 단계").fill("상대 차례");
  await page.getByLabel("하려는 행동").fill("저지하기");
  // 질문 없이 상황 메모만으로도 보낼 수 있고, 메모는 질문 문장에 섞이지 않는다.
  await expect(sendButton(page)).toBeEnabled();
  await sendButton(page).click();
  await expect(
    page.getByText("이 상황을 판정해 주세요.", { exact: true }),
  ).toBeVisible();
  const memo = page.getByRole("status", { name: "적용 중인 상황 메모" });
  await expect(memo).toContainText("암살자 · 상대 차례 · 저지하기");
  await expect(page.getByLabel("관련 카드·요소")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "출처 1 자세히" }),
  ).toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: /이전 대화 이어하기/ }).click();
  await expect(memo).toContainText("암살자");
  await question(page).fill("정보 부족");
  await sendButton(page).click();
  await page.getByRole("button", { name: "상황 정리해서 답하기" }).click();
  await expect(page.getByLabel("관련 카드·요소")).toHaveValue("암살자");
  await page.getByRole("button", { name: "상황 메모 지우기" }).click();
  await expect(memo).toHaveCount(0);
  await expect(page.getByLabel("관련 카드·요소")).toHaveValue("");
});

test("answer draft streams before the validated answer replaces it", async ({
  page,
}, info) => {
  await choose(page);
  await question(page).fill("스트리밍: 턴이 끝났어요");
  await sendButton(page).click();
  const draft = page.getByTestId("answer-draft");
  await expect(draft).toContainText("작성 중 · 근거 확인 전");
  await expect(draft).toContainText("자신의");
  await page.screenshot({
    path: info.outputPath("answer-draft.png"),
    fullPage: true,
  });
  await expect(page.getByRole("button", { name: "근거 1 보기" })).toBeVisible({
    timeout: 15000,
  });
  await expect(draft).toHaveCount(0);
});

test("waiting shows elapsed time, accepts a draft and stops the BGG lookup", async ({
  page,
}, info) => {
  await choose(page);
  await question(page).fill("BGG 대기: 추가 근거가 필요한 질문");
  await sendButton(page).click();
  const thinking = page.getByRole("status", { name: "답변을 생각하고 있어요" });
  await expect(thinking.getByTestId("elapsed")).toContainText("초 지났어요");
  // 기다리는 동안 다음 질문 초안을 쓸 수 있지만 보내기는 막혀 있다.
  await question(page).fill("다음에 물어볼 질문");
  await expect(sendButton(page)).toBeDisabled();
  await expect(
    page.getByText("BGG에서 추가 근거를 확인하고 있어요"),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("bgg-waiting.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "추가 검색 중단" }).click();
  await expect(page.getByText(/BGG 추가 검색을 중단했어요/)).toBeVisible({
    timeout: 5000,
  });
  await expect(thinking).toHaveCount(0);
  await expect(question(page)).toHaveValue("다음에 물어볼 질문");
  await expect(sendButton(page)).toBeEnabled();
});

test("source links are usable while the explanation is still loading", async ({
  page,
}) => {
  await choose(page);
  await question(page).fill("턴이 끝났어요");
  await sendButton(page).click();
  await expect(page.getByRole("button", { name: "근거 1 보기" })).toBeVisible();
  await page.route("**/api/v1/conversations/*", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const response = await route.fetch();
    const body = await response.json();
    for (const message of body.messages ?? [])
      for (const source of message.citations ?? []) source.explanation = null;
    await route.fulfill({ response, json: body });
  });
  let release = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  await page.route("**/api/v1/sources/*/explanation", async (route) => {
    await held;
    await route.continue();
  });
  await page.reload();
  await page.getByRole("button", { name: /이전 대화 이어하기/ }).click();
  await page.getByRole("button", { name: "근거 1 보기" }).click();
  const modal = page.getByRole("dialog", { name: "왜 이렇게 답변했나요?" });
  await expect(
    modal.getByText("규칙과 답변의 연결을 정리하고 있어요…"),
  ).toBeVisible();
  await expect(
    modal.getByRole("link", { name: "원문 다운로드" }),
  ).toBeVisible();
  await expect(modal.getByText("2페이지", { exact: true })).toBeVisible();
  release();
  await expect(
    modal.getByRole("heading", { name: "이 답변에 적용한 이유" }),
  ).toBeVisible();
});
