// 시안·상태별 스크린샷을 일괄로 찍는다. 목업 폴더에서 `node assets/shot.mjs`.
//
// **코드만 읽고 판단하지 않는다**(DESIGN.md §9). 3D 는 특히 코드로 안 보인다 —
// 겹침 순서와 원근 왜곡은 그려 봐야 안다.
//
// 전환에 CSS 트랜지션이 걸려 있으면 바꾸자마자 찍을 때 이전 화면이 잡힌다. SETTLE 이 그 대기다.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const OUT = "/tmp/pw/wiki-graph";
const SIZE = { width: 1240, height: 1400 };
const SETTLE = 500;

mkdirSync(OUT, { recursive: true });

// **클로저는 브라우저로 넘어가지 않는다.** 값은 인자로 준다 — 위에서 잡은 변수를
// 쓰면 페이지 안에서 ReferenceError 로 죽고, 그러면 이전 화면이 그대로 찍힌다
const pick = (k) => document.querySelector(`[data-key="${k}"]`)
  ?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

const targets = [
  { id: "base", file: "base.html", label: "현행",    states: [["base-picked", pick, "customer"]] },
  { id: "a", file: "a-planet.html", label: "A 행성", states: [["a-picked", pick, "customer"]] },
  { id: "b", file: "b-glass.html", label: "B 유리",  states: [["b-picked", pick, "customer"]] },
  { id: "c", file: "c-jelly.html", label: "C 젤리",  states: [["c-picked", pick, "customer"]] },
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: SIZE, locale: "ko-KR", deviceScaleFactor: 2 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

for (const t of targets) {
  errors.length = 0;
  await page.goto("file://" + process.cwd() + "/" + t.file, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  // 구면은 저절로 돈다. 찍는 동안 멈춰야 같은 각도가 잡힌다
  await page.evaluate(() => { if (typeof AUTO !== "undefined") AUTO.v = 0; });
  await page.waitForTimeout(SETTLE);
  await page.screenshot({ path: `${OUT}/${t.id}.png` });
  console.log(`${t.label.padEnd(12)} → ${OUT}/${t.id}.png${errors.length ? "  ⚠︎ " + errors.join(" / ") : ""}`);

  for (const [name, fn, arg] of t.states ?? []) {
    // **상태마다 다시 읽는다.** 앞 상태의 인라인 스타일이 남으면 다음 컷이 그걸 물고 찍힌다
    await page.goto("file://" + process.cwd() + "/" + t.file, { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => { if (typeof AUTO !== "undefined") AUTO.v = 0; });
    await page.waitForTimeout(SETTLE);
    await page.evaluate(fn, arg);
    await page.waitForTimeout(SETTLE);
    await page.screenshot({ path: `${OUT}/${name}.png` });
    console.log(`${" ".repeat(12)} → ${OUT}/${name}.png`);
  }
}
await browser.close();
if (errors.length) console.log("\n⚠︎ 페이지 오류가 있었다. 위 표시를 볼 것.");
