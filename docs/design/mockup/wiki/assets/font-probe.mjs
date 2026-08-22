// 요청한 font-weight 가 실제로 렌더되는지 확인한다.
// 사용: `node assets/font-probe.mjs [파일] [폰트스택]` (wiki 폴더에서)
//
// 왜 필요한가 — 폰트에 그 weight face 가 없으면 브라우저는 **조용히 가장 가까운 값으로
// 떨어뜨린다.** 에러도 경고도 없다. 그래서 `fontWeight: active ? 500 : 400` 같은 강조가
// 아무 효과 없이 몇 달을 사는 일이 생긴다.
//
// ── 폭으로 재면 안 된다. 이 도구가 한 번 틀린 답을 줬다 ──────────────────
// 원래 판별법은 **같은 문자열을 weight 만 바꿔 재고 폭이 같으면 같은 face** 였다.
// 라틴에서는 맞는다. **한글에서는 틀린다** — 한글 글리프는 대개 고정폭(전각)이라
// 굵기가 바뀌어도 advance 가 거의 안 변한다.
//
// 실제로 2026-08-21 이 도구가 IBM Plex Sans KR 에 대해
//   "400·600 이 같은 face" · "실제 구분되는 굵기 3종"
// 이라고 보고했다. 사실이면 `--w-medium`(600)이 무효라는 뜻이라 확인했더니 **아니었다.**
// 같은 표본을 canvas 에 그려 알파 채널 합(잉크량)을 재니 넷이 다 갈렸다 —
//   400: 984 · 500: 1,209 · 600: 1,413 · 700: 1,546
// 폭은 398.41 · 399.71 · 404.50 · 405.85 로 1.9% 안에 모여 있었다.
//
// 그래서 **잉크량으로 잰다.** 획이 굵어지면 칠해진 픽셀이 늘고, 그건 고정폭 글자에서도
// 반드시 는다. 폭도 같이 찍어 두되 판정에는 안 쓴다.
import { chromium } from "playwright";

const FILE = process.argv[2] || "../base.html";  // 잴 목업. 껍데기가 같으니 아무 시안이나 된다
const SAMPLE = "사업자 정보 0123";                 // 한글+숫자를 섞는다
const WEIGHTS = [300, 400, 450, 500, 600, 700, 800];
const FONT_CSS = process.argv[3] || "var(--font-sans)";  // 잴 폰트 스택. tokens.css 가 정본이다

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 800 }, locale: "ko-KR" });
await page.goto(new URL(FILE, import.meta.url).href, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(500);

const r = await page.evaluate(
  ({ sample, weights, fontCss }) => {
    /* 폰트 스택을 실제 값으로 푼다. `var(--font-sans)` 는 canvas 의 font 에 못 넣는다 */
    const probeEl = document.createElement("span");
    probeEl.style.cssText = "position:absolute;visibility:hidden;font-family:" + fontCss;
    document.body.appendChild(probeEl);
    const family = getComputedStyle(probeEl).fontFamily;
    probeEl.remove();

    const cv = document.createElement("canvas");
    cv.width = 900;
    cv.height = 90;
    const g = cv.getContext("2d");

    const out = {};
    for (const w of weights) {
      g.clearRect(0, 0, cv.width, cv.height);
      g.fillStyle = "#000";
      g.font = `${w} 42px ${family}`;
      g.fillText(sample, 4, 58);
      const d = g.getImageData(0, 0, cv.width, cv.height).data;
      let ink = 0;
      for (let k = 3; k < d.length; k += 4) ink += d[k];
      out[w] = { ink: Math.round(ink / 1000), width: +g.measureText(sample).width.toFixed(2) };
    }
    return { family, out };
  },
  { sample: SAMPLE, weights: WEIGHTS, fontCss: FONT_CSS }
);

console.log(`폰트: ${r.family.split(",")[0].replace(/"/g, "")}`);
console.log(`표본: "${SAMPLE}"\n`);
console.log("  굵기   잉크    폭      판정");
console.log("  ───── ─────── ─────── ────────────────");

const rows = WEIGHTS.map((w) => ({ w, ...r.out[w] }));
let prev = null;
for (const row of rows) {
  /* 잉크가 1% 안쪽이면 같은 face 로 본다. 폭은 참고로만 찍는다 */
  const same = prev && Math.abs(row.ink - prev.ink) / prev.ink < 0.01;
  console.log(
    "  " + String(row.w).padEnd(5) + " " + String(row.ink).padStart(7) +
    " " + String(row.width).padStart(7) + "   " +
    (same ? `← ${prev.w} 과 같은 face 로 떨어진다` : "구분됨")
  );
  prev = row;
}

const distinct = rows.filter((row, i2) => i2 === 0 || Math.abs(row.ink - rows[i2 - 1].ink) / rows[i2 - 1].ink >= 0.01).length;
console.log(`\n실제 구분되는 굵기 ${distinct}종 / 요청 ${WEIGHTS.length}종.`);
if (distinct < WEIGHTS.length) {
  console.log("요청해도 무시되는 weight 가 있다 — 실제 있는 값만 쓰거나 가변 폰트로 바꿀 것.");
}
console.log("**폭으로 판정하지 않는다.** 한글은 고정폭이라 굵기가 바뀌어도 폭이 거의 같다.");

await browser.close();
