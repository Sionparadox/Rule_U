import { expect, test, type Page } from "@playwright/test";

async function choose(page: Page, name = "테이블 탐험") {
  const closeSource = page.getByRole("button", {name:"출처 설명 닫기"});
  if (await closeSource.isVisible()) await closeSource.click();
  await page.getByRole("button", {name:"Rule_U 게임 선택으로"}).click();
  await page.getByRole("button", { name: new RegExp(name) }).click();
  await page.getByRole("button", { name: "이 게임으로 대화하기" }).click();
  await expect(page.getByRole("textbox", { name: "규칙 질문" })).toBeEnabled();
}
async function send(page: Page, text: string) {
  await page.getByRole("textbox", { name: "규칙 질문" }).fill(text);
  await page.getByRole("button", { name: "질문 보내기" }).click();
}

test("game, ruling, citation, original, restore and switch", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByText("서비스 연결됨")).toBeVisible();
  await page.getByRole("button", { name: /테이블 탐험/ }).click();
  await page.getByLabel("야간 탐험").check();
  await page.getByRole("button", { name: "이 게임으로 대화하기" }).click();
  await page.getByRole("button", { name: "상황 판정", exact: true }).click();
  await send(page, "턴이 끝났어요. 카드를 쓸 수 있나요?");
  await page.getByRole("button", { name: "근거 1 보기" }).click();
  await expect(page.getByRole("heading", { name: "테이블 탐험 규칙서" })).toBeVisible();
  await expect(page.getByText("2페이지", { exact: true })).toBeVisible();
  await expect(page.getByRole("dialog", {name:"왜 이렇게 답변했나요?"})).toBeVisible();
  await expect(page.getByText("카드는 자신의 턴이 끝난 뒤에 사용할 수 있는 규칙입니다.")).toBeVisible();
  await expect(page.getByText("질문에서는 이미 턴이 끝났으므로, 이 사용 시점 조건을 충족한다고 답변했어요.")).toBeVisible();
  await expect(page.getByText("자신의 턴 이후에만 사용합니다.", {exact:true})).toHaveCount(0);
  await expect(page.getByText("공식 출처 확인이 필요한 자료")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "원문 다운로드" }).click();
  expect((await download).suggestedFilename()).toBe("fixture.pdf");
  await page.reload();
  await page.getByRole("button", {name:/이전 대화 이어하기/}).click();
  await expect(page.getByText("턴이 끝났어요. 카드를 쓸 수 있나요?", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "근거 1 보기" }).click();
  await choose(page, "숲속 산책");
  await expect(page.getByText("턴이 끝났어요. 카드를 쓸 수 있나요?", { exact: true })).toHaveCount(0);
  await page.getByRole("button", {name:"Rule_U 게임 선택으로"}).click();
  await page.getByRole("button", { name: /테이블 탐험/ }).click();
  await page.getByLabel("야간 탐험").check();
  await page.getByRole("button", { name: "이 게임으로 대화하기" }).click();
  await expect(page.getByText("턴이 끝났어요. 카드를 쓸 수 있나요?", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "근거 1 보기" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
  await expect(page.getByRole("heading", {name:"테이블 탐험 규칙서"})).toBeVisible();
  await expect(page.getByTestId("source-body")).toHaveCSS("opacity","1");
  await page.screenshot({ path: info.outputPath("stage4-citation.png"), fullPage: true });
});

test("pending request resumes after reload and second question is new", async ({ page }) => {
  await page.goto("/"); await choose(page);
  await send(page, "느린 질문: 턴 이후인가요?");
  await expect(page.getByText("규칙 근거를 찾고 있어요")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", {name:"게임 선택"})).toBeVisible();
  await page.getByRole("button", {name:/이전 대화 이어하기/}).click();
  await expect(page.getByRole("button", { name: "근거 1 보기" })).toBeVisible();
  await send(page, "다음 질문입니다");
  await expect(page.getByRole("button", { name: "근거 1 보기" })).toHaveCount(2);
  await expect(page.getByText("다음 질문입니다", { exact: true })).toHaveCount(1);
});

test("provider failure retries with a new request; clarification and no evidence", async ({ page }) => {
  await page.goto("/"); await choose(page);
  await send(page, "실패 테스트");
  const retry = page.getByRole("button", { name: "질문 다시 시도" });
  await retry.click();
  await expect(page.getByRole("button", { name: "근거 1 보기" })).toBeVisible();
  await send(page, "정보 부족");
  await expect(page.getByText("어떤 카드이며 누구의 턴인가요?", { exact: true })).toBeVisible();
  await send(page, "근거 없음");
  await expect(page.getByText("현재 확인된 근거만으로는 답변을 확인할 수 없습니다.", { exact: true })).toBeVisible();
});

test("filters, semantic search, empty result and keyboard", async ({ page }) => {
  await page.goto("/");
  await page.getByText("인원·시간으로 더 찾아보기").click();
  await page.getByLabel("플레이 인원").fill("4");
  await page.getByLabel("최대 시간 (분)").fill("30");
  await page.getByRole("button", { name: "게임 찾기", exact: true }).click();
  await expect(page.getByText("2개의 게임", {exact:true})).toBeVisible();
  await page.getByLabel("자연어로 찾기").check();
  await page.getByLabel("자연어 조건", {exact:true}).fill("함께 즐길 전략 게임");
  await page.getByRole("button", { name: "게임 찾기", exact: true }).click();
  await expect(page.getByText("2개의 게임", {exact:true})).toBeVisible();
  await page.getByLabel("플레이 인원").fill("8");
  await page.getByRole("button", { name: "게임 찾기", exact: true }).click();
  await expect(page.getByText(/조건에 맞는 게임이 없어요/)).toBeVisible();
  await page.getByRole("textbox", {name:"자연어 조건", exact:true}).focus();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", {name:"게임 찾기", exact:true})).toBeFocused();
});

test("360px and tablet layout with reduced motion", async ({ page }, info) => {
  await page.emulateMedia({reducedMotion:'reduce'});
  for (const width of [360, 768, 1440]) {
    await page.setViewportSize({width,height:900}); await page.goto("/");
    await expect(page.getByRole("button", {name:/테이블 탐험/})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({path:info.outputPath(`stage4-${width}.png`),fullPage:true});
  }
});

test("ambiguous submission reuses client id without duplicate messages", async ({ page }) => {
  await page.goto("/"); await choose(page);
  let first = true;
  const ids: string[] = [];
  await page.route("**/api/v1/conversations/*/messages", async route => {
    ids.push(route.request().postDataJSON().client_request_id);
    if (first) {
      first = false;
      await route.fetch();
      await route.abort("connectionreset");
    } else await route.continue();
  });
  await send(page, "응답을 받지 못한 질문");
  await page.getByRole("button", { name: "전송 다시 확인" }).click();
  await expect(page.getByRole("button", { name: "근거 1 보기" })).toBeVisible();
  expect(ids).toHaveLength(2);
  expect(ids[0]).toBe(ids[1]);
  await expect(page.getByText("응답을 받지 못한 질문", {exact:true})).toHaveCount(1);
});

test("expired anonymous session clears inaccessible conversation", async ({page, context}) => {
  await page.goto("/"); await choose(page);
  await send(page,"세션 확인 질문");
  await expect(page.getByRole("button", { name: "근거 1 보기" })).toBeVisible();
  await context.clearCookies();
  await page.reload();
  await expect(page.getByRole("button", {name:/테이블 탐험/})).toBeVisible();
  await expect(page.getByText("세션 확인 질문",{exact:true})).toHaveCount(0);
  await choose(page);
  await expect(page.getByText("세션 확인 질문",{exact:true})).toHaveCount(0);
});

test("game lobby first, setup focus and visible thinking skeleton", async ({page},info) => {
  await page.setViewportSize({width:360,height:800});
  await page.goto("/");
  await expect(page.getByRole("heading", {name:"어떤 게임을 할까요?"})).toBeVisible();
  await expect(page.getByRole("textbox", {name:"게임 이름"})).toBeVisible();
  await expect(page.getByRole("region", {name:"규칙 대화",exact:true})).toHaveCount(0);
  await page.getByRole("button", {name:"테이블 탐험 선택"}).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("button", {name:"판본 선택 닫기"})).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await choose(page);
  await send(page,"느린 질문: 생각하는 중인가요?");
  const thinking=page.getByRole("status", {name:"답변을 생각하고 있어요"});
  await expect(thinking).toBeVisible();
  await expect(thinking.locator(".spinner")).toBeVisible();
  await expect(thinking.locator(".skeleton-line")).toHaveCount(3);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath("mobile-thinking.png"),fullPage:true});
  await expect(page.getByRole("button",{name:"근거 1 보기"})).toBeVisible();
  await expect(thinking).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading",{name:"어떤 게임을 할까요?"})).toBeVisible();
  await expect(page.getByRole("region", {name:"규칙 대화",exact:true})).toHaveCount(0);
});

test("legacy source explanation retries in modal and restores focus", async ({page},info) => {
  await page.goto("/"); await choose(page);
  await send(page,"턴이 끝났어요");
  await expect(page.getByRole("button", {name:"근거 1 보기"})).toBeVisible();
  await page.route("**/api/v1/conversations/*", async route => {
    if(route.request().method()!=="GET")return route.continue();
    const response=await route.fetch();
    const body=await response.json();
    for(const message of body.messages??[])for(const source of message.citations??[])source.explanation=null;
    await route.fulfill({response,json:body});
  });
  let first=true;
  await page.route("**/api/v1/sources/*/explanation", async route => {
    if(first){first=false;await route.fulfill({status:503,json:{detail:"explanation_unavailable"}});}
    else await route.continue();
  });
  await page.reload();
  await page.getByRole("button",{name:/이전 대화 이어하기/}).click();
  const trigger=page.getByRole("button",{name:"근거 1 보기"});
  await trigger.click();
  const modal=page.getByRole("dialog",{name:"왜 이렇게 답변했나요?"});
  await expect(modal).toBeVisible();
  await expect(page.getByRole("button",{name:"출처 설명 닫기"})).toBeFocused();
  await page.getByRole("button",{name:"설명 다시 불러오기"}).click();
  await expect(modal.getByRole("heading",{name:"이 답변에 적용한 이유"})).toBeVisible();
  await expect(modal.getByText("자신의 턴 이후에만 사용합니다.",{exact:true})).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath("source-explanation-modal.png"),fullPage:true});
  await page.keyboard.press("Escape");
  await expect(modal).toHaveCount(0);
  await expect(trigger).toBeFocused();
});
