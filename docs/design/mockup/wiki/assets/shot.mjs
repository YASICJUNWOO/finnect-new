// 시안별 스크린샷을 일괄로 찍는다. 두 장씩 — 첫 화면과 전체.
// 사용: `node assets/shot.mjs` (landing 폴더에서). 결과는 /tmp/pw/landing/
//
// **모션을 끄고 찍는다.** C 의 스크롤 진입과 E 의 조립, B 의 점 켜짐이 도중에 잡히면
// 시안끼리 대조가 안 된다. reducedMotion 을 주면 셋 다 완성 상태로 선다.
// 첫 화면을 따로 찍는 이유 — 랜딩의 일은 첫 화면에서 결정된다(DESIGN.md §2-3).
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const OUT = "/tmp/pw/landing";
const SIZE = { width: 1600, height: 1000 };
const SETTLE = 500;

const FILES = [
  ["base", "base.html", "현행"],
  ["b", "b-console.html", "B 관제"],
  ["c", "c-drop.html", "C 던지기"],
  ["d", "d-plane.html", "D 면"],
  ["e", "e-assemble.html", "E 조립"],
  ["f", "f-plus.html", "F 현행+"],
];

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: SIZE, locale: "ko-KR", deviceScaleFactor: 1, reducedMotion: "reduce",
});

const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

for (const [id, file, label] of FILES) {
  errors.length = 0;
  await page.goto("file://" + process.cwd() + "/" + file, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(SETTLE);

  await page.screenshot({ path: `${OUT}/${id}-fold.png` });
  await page.screenshot({ path: `${OUT}/${id}-full.png`, fullPage: true });

  console.log(`${label.padEnd(10)} → ${OUT}/${id}-{fold,full}.png` +
    (errors.length ? `   [JS 오류] ${errors.join(" / ")}` : ""));
}

await browser.close();
