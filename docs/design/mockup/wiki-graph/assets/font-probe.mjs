// 요청한 font-weight 가 실제로 렌더되는지 확인한다.
// 사용: 목업 폴더에 복사한 뒤 `node font-probe.mjs`
//
// 왜 필요한가 — 폰트에 그 weight face 가 없으면 브라우저는 **조용히 가장 가까운 값으로
// 떨어뜨린다.** 에러도 경고도 없다. 그래서 `fontWeight: active ? 500 : 400` 같은 강조가
// 아무 효과 없이 몇 달을 사는 일이 생긴다.
//
// 판별법: 같은 문자열을 weight 만 바꿔 재고 **폭이 같으면 같은 face** 다.
// (weight 가 다르면 자간·자폭이 반드시 조금은 달라진다)
import { chromium } from "playwright";

const FILE = process.argv[2] || "b-blocks.html";  // 잴 목업
const SAMPLE = "사업자 정보 0123";                 // 한글+숫자를 섞는다
const WEIGHTS = [300, 400, 450, 500, 600, 700, 800];
const FONT_CSS = process.argv[3] || "var(--display)";  // 잴 폰트 스택

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 800 }, locale: "ko-KR" });
await page.goto("file://" + process.cwd() + "/" + FILE, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(500);

const r = await page.evaluate(
  ({ sample, weights, fontCss }) => {
    const probe = document.createElement("span");
    probe.textContent = sample;
    probe.style.cssText =
      "position:absolute;visibility:hidden;white-space:nowrap;font-size:14px;font-family:" + fontCss;
    document.body.appendChild(probe);
    const out = {};
    for (const w of weights) {
      probe.style.fontWeight = String(w);
      out[w] = +probe.getBoundingClientRect().width.toFixed(2);
    }
    const family = getComputedStyle(probe).fontFamily.split(",")[0].replace(/['"]/g, "");
    probe.remove();
    return { widths: out, family };
  },
  { sample: SAMPLE, weights: WEIGHTS, fontCss: FONT_CSS }
);

console.log(`폰트: ${r.family}`);
console.log(`표본: "${SAMPLE}"\n`);

// 폭이 같은 weight 끼리 묶는다 — 한 묶음 = 실제로는 한 face
const buckets = new Map();
for (const [w, px] of Object.entries(r.widths)) {
  if (!buckets.has(px)) buckets.set(px, []);
  buckets.get(px).push(w);
}
for (const [px, ws] of buckets) {
  const note = ws.length > 1 ? `  ← ${ws.length}개가 같은 face 로 떨어진다` : "";
  console.log(`  ${px}px : weight ${ws.join(", ")}${note}`);
}
console.log(
  `\n실제 구분되는 굵기 ${buckets.size}종. ` +
  (buckets.size < WEIGHTS.length
    ? "요청해도 무시되는 weight 가 있다 — 강조를 굵기로 주려면 실제 있는 값만 쓰거나 가변 폰트로 바꿀 것."
    : "요청한 weight 가 전부 구분된다.")
);

await browser.close();
