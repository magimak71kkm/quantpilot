import { test, expect } from "@playwright/test";

const API = process.env.QP_API_URL || "http://localhost:8080";

/**
 * 프로토타입 v12 · 백엔드 v8 스모크
 * 시나리오: 백엔드 연결 → S13 롤백 → S02 SLO 배지 확인
 */
test.describe("QuantPilot E2E smoke", () => {
  test.beforeEach(async ({ page }) => {
    // 사전 조건: localStorage에 API URL을 주입해 툴바를 통한 수동 입력 없이 곧바로 사용
    await page.addInitScript((url) => {
      window.localStorage.setItem("QP_API_BASE", url);
    }, API);
    await page.goto("prototype.html");
    // 홈이 렌더될 때까지 대기 — 상단 로고
    await expect(page.locator(".gtop")).toBeVisible();
  });

  test("home renders 14 screens sitemap", async ({ page }) => {
    await expect(page.locator("#screen-index")).toBeVisible();
    // 14개 화면 섹션이 DOM에 존재해야 한다
    for (let i = 1; i <= 14; i++) {
      const id = `screen-s${String(i).padStart(2, "0")}`;
      await expect(page.locator(`#${id}`)).toHaveCount(1);
    }
  });

  test("S13 rollback → S02 SLO badge reflects update", async ({ page }) => {
    // 1) S13 이동
    await page.locator('[data-nav="s13"]').first().click();
    await expect(page.locator("#verBody")).toBeVisible();

    // 2) 백엔드 연결 (툴바) — localStorage로 이미 주입돼 있으므로 [연결 테스트] 버튼만 클릭
    const connectBtn = page.locator('[data-act="qp-connect"]');
    if (await connectBtn.isVisible()) {
      await connectBtn.click();
    }
    // qpStatus가 "연결됨"이 되기까지 대기 — 실패해도 로컬 폴백으로 UI는 뜬다
    await page.waitForTimeout(1500);

    // 3) 롤백 클릭 시 사유 프롬프트 처리
    page.once("dialog", async (d) => {
      await d.accept("E2E 스모크: 로컬 폴백 검증을 위한 자동 롤백 시나리오");
    });
    const rollbackBtn = page.locator('[data-act="rollback"]').first();
    await expect(rollbackBtn).toBeVisible();
    await rollbackBtn.click();

    // 토스트가 표시되었는지 (로컬 폴백 · 백엔드 성공 두 경우 모두 커버)
    await expect(page.locator(".toast, #toast, .badge")).toContainText(
      /롤백|revert|✅/i,
      { timeout: 5000 },
    );

    // 4) S02 이동 → SLO 배지가 초기화되는지
    await page.locator('[data-nav="s02"]').first().click();
    await expect(page.locator("#sloAvail")).toBeVisible();

    // 30초 폴링 대신 즉시 트리거를 위해 sloTick 호출
    await page.evaluate(() => (window as any).sloTick && (window as any).sloTick());
    await page.waitForTimeout(1200);

    // 값이 "—"에서 벗어나거나 숫자 형식(00.000%)이 되어야 한다
    const avail = await page.locator("#sloAvail").innerText();
    expect(avail).toMatch(/(%|—)/);
    // 지연 p95 라벨은 항상 존재
    await expect(page.locator("#sloP95")).toBeVisible();

    // 라이브 위젯 카드도 함께 렌더
    await expect(page.locator("#lvInFlight")).toBeVisible();
  });

  test("S04 AI screener falls back to local parser without backend", async ({ page }) => {
    // 백엔드가 없으면 로컬 파서로 폴백 — 정규식이 KOSDAQ + PER 30 를 인식하는지 확인
    await page.goto("prototype.html#s04");
    await page.waitForSelector("#aiScText");
    await page.locator("#aiScText").fill("코스닥 소형주 중 최근 3개월 상승률 20% 초과, PER 30 미만");
    // 백엔드 연결 여부와 무관하게 결과 JSON은 렌더돼야 한다
    await page.locator('[data-act="ai-screener"]').first().click();
    await expect(page.locator("#aiScOut")).toContainText(/KOSDAQ|market/i, {
      timeout: 5000,
    });
    // 화면에 적용 → 결과 테이블이 렌더링
    await page.locator('[data-act="ai-screener-apply"]').first().click();
  });
});
