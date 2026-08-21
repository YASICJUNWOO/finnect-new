// 공고 목록·상세 시안 넷을 실측해 대조표로 뽑는다.
// 사용: `node assets/measure.mjs` (notice 폴더에서 · `npm i -D playwright` 필요)
//
// 왜 이 항목들인가 — 전부 DESIGN.md 가 숫자로 못 박은 규칙이다(2026-08-21 15절 판).
//   본문 최소      §3 "14px 과 15px 이 없는 것이 이 표의 요점이다. 본문은 16px 이상이다"
//   최장 줄        §5 "줄길이는 62ch 이하"
//   최소 타깃      §5 "터치 타깃은 44px 이상"
//   채운 버튼      §4 "화면당 하나. 행마다 반복되는 자리에는 두지 않는다"
//   크기 종류      §3 관측된 단계는 16 · 16 · 20 셋이다
//   첫 화면 행 수  §1 "조밀하고 크롬이 적은 정보 설계" — 밀도를 체감이 아니라 수로 잰다
//   그림자 수      §6 "모든 카드에 같은 옅은 그림자를 바르지 않는다"
//
// 재는 방법에서 조심할 곳 둘. 랜딩 하네스가 먼저 밟은 자리다 —
//  1) **모든** 글자의 최소 크기를 재면 배지 안 숫자가 잡혀 전부 "본문 11px" 로 나온다.
//     본문은 산문이다 — 제 텍스트가 25자 넘는 요소만 본다.
//  2) 줄길이를 canvas 의 "0" 폭으로 나누면 한글이 전각이라 값이 두 배로 부푼다.
//     Range.getClientRects() 로 실제 렌더된 줄을 받아 글자 폭을 평균 낸다.
//  3) 하네스 바(.hns)는 목업 전용이라 전부 제외한다. 안 빼면 채운 버튼 수가 시안마다 +2 다.
import { chromium } from "playwright";

const SIZE = { width: 1440, height: 1000 };
const FILES = [
  ["현행", "base.html"],
  ["A 규범", "a-spec.html"],
  ["E 관제", "e-console.html"],
  ["R 적응", "r-adaptive.html"],
];

const probe = ({ foldH }) => {
  const inHarness = (el) => el.closest(".hns, .hns-out") !== null;
  const vis = (el) => {
    const s = getComputedStyle(el);
    if (s.visibility === "hidden" || s.display === "none" || s.opacity === "0") return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const all = [...document.querySelectorAll("body *")].filter((el) => !inHarness(el) && vis(el));

  // 본문 최소 — 제 텍스트(자식 제외)가 25자 넘는 요소만 산문으로 본다
  let bodyMin = Infinity;
  const sizes = new Set();
  for (const el of all) {
    const own = [...el.childNodes]
      .filter((n) => n.nodeType === 3)
      .map((n) => n.textContent.trim())
      .join("");
    const px = parseFloat(getComputedStyle(el).fontSize);
    if (own.length > 0) sizes.add(Math.round(px));
    if (own.length > 25) bodyMin = Math.min(bodyMin, px);
  }

  // 최장 줄 — 실제 렌더된 줄의 폭을 글자 폭 평균으로 나눈다
  let maxCh = 0;
  for (const el of all) {
    const own = [...el.childNodes].filter((n) => n.nodeType === 3);
    for (const n of own) {
      if (n.textContent.trim().length < 25) continue;
      const r = document.createRange();
      r.selectNodeContents(n);
      const rects = [...r.getClientRects()];
      if (!rects.length) continue;
      const chars = n.textContent.trim().length;
      const totalW = rects.reduce((a, b) => a + b.width, 0);
      const avg = totalW / chars;
      for (const rect of rects) maxCh = Math.max(maxCh, Math.round(rect.width / avg));
    }
  }

  // 채운 버튼 — 배경이 투명하지 않고 글자가 그 위에 반전된 조작 요소
  let filled = 0;
  let minTarget = Infinity;
  for (const el of all) {
    if (!el.matches("a, button")) continue;
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    const bg = s.backgroundColor;
    const opaque = bg && bg !== "transparent" && !/rgba\(0, 0, 0, 0\)/.test(bg);
    if (opaque) filled++;
    // 인라인 링크(문장 안의 것)는 타깃 규칙 밖이다 — 블록으로 잡힌 것만 본다
    if (s.display !== "inline" && r.height > 0) minTarget = Math.min(minTarget, Math.round(r.height));
  }

  // 그림자
  const shadows = all.filter((el) => {
    const v = getComputedStyle(el).boxShadow;
    return v && v !== "none";
  }).length;

  // 첫 화면에 보이는 공고 행 — 밀도의 본 지표
  const rowSel = ".item, .card, .grid > article";
  const rows = [...document.querySelectorAll(rowSel)].filter((el) => !inHarness(el) && vis(el));
  const inFold = rows.filter((el) => el.getBoundingClientRect().top < foldH).length;
  const heights = rows.map((el) => Math.round(el.getBoundingClientRect().height)).sort((a, b) => a - b);
  const medianH = heights.length ? heights[Math.floor(heights.length / 2)] : 0;

  return {
    bodyMin: bodyMin === Infinity ? 0 : Math.round(bodyMin),
    maxCh,
    filled,
    minTarget: minTarget === Infinity ? 0 : minTarget,
    shadows,
    rows: rows.length,
    inFold,
    medianH,
    docH: Math.round(document.documentElement.scrollHeight),
    sizeKinds: sizes.size,
  };
};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: SIZE });
const out = [];

for (const [label, file] of FILES) {
  await page.goto(new URL(file, import.meta.url).href);
  // 서체가 붙기 전에 재면 줄길이가 시스템 서체 기준으로 잡힌다
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(150);
  const list = await page.evaluate(probe, { foldH: SIZE.height });
  await page.evaluate(() => {
    document.body.dataset.screen = "detail";
  });
  await page.waitForTimeout(150);
  const detail = await page.evaluate(probe, { foldH: SIZE.height });
  out.push({ label, list, detail });
}

await browser.close();

const COLS = [
  ["본문 최소", (r) => r.list.bodyMin, "px"],
  ["최장 줄", (r) => r.list.maxCh, "ch"],
  ["크기 종류", (r) => r.list.sizeKinds, ""],
  ["채운 버튼", (r) => r.list.filled, ""],
  ["최소 타깃", (r) => r.list.minTarget, "px"],
  ["그림자", (r) => r.list.shadows, ""],
  ["행 높이", (r) => r.list.medianH, "px"],
  ["첫 화면 행", (r) => r.list.inFold, ""],
  ["목록 세로", (r) => r.list.docH, "px"],
  ["상세 세로", (r) => r.detail.docH, "px"],
];

const W = 11;
const pad = (s, w = W) => String(s).padStart(w);
const base = out[0];

console.log("\n" + " ".repeat(12) + COLS.map((c) => pad(c[0])).join(""));
for (const r of out) {
  const cells = COLS.map((c) => {
    const v = c[1](r);
    if (r === base) return pad(v);
    const d = v - c[1](base);
    return pad(v + (d === 0 ? "" : d > 0 ? " +" + d : " " + d));
  });
  console.log(r.label.padEnd(12) + cells.join(""));
}
console.log("\n기준 — 본문 16px 이상 · 최장 줄 62ch 이하 · 최소 타깃 44px 이상 (DESIGN.md §3 · §5)\n");
